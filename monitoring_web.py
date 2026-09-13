import base64
import copy
import hashlib
import ipaddress
import json
import mimetypes
import os
import queue
import socket
import socketserver
import struct
import sys
import threading
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit


class MonitoringState:
    """Thread-safe, in-memory state shared by Tkinter and the web panel."""

    def __init__(self):
        self._lock = threading.RLock()
        self._listeners = []
        self._data = {
            "providers": {
                "eth2": {"name": "Unifique", "running": False, "output": "", "history": [], "drops": []},
                "eth4": {"name": "Claro", "running": False, "output": "", "history": [], "drops": []},
                "eth5": {"name": "Coopera", "running": False, "output": "", "history": [], "drops": []},
                "tun0": {"name": "OMR VPN", "running": False, "output": "", "history": [], "drops": []},
            },
            "tests": {str(i): {"running": False, "method": "mtr", "host": "", "port": "",
                                "output": "", "history": [], "drops": []} for i in range(3)},
            "omr": {
                "vpn": {"running": False, "output": "", "averages": ""},
                "jogo": {"running": False, "output": "", "averages": ""},
            },
        }

    def subscribe(self, listener):
        with self._lock:
            self._listeners.append(listener)

    def unsubscribe(self, listener):
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self._data)

    def update(self, section, key, **values):
        with self._lock:
            target = self._data[section].setdefault(str(key), {})
            target.update(values)
            snapshot = copy.deepcopy(self._data)
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(snapshot)
            except Exception:
                pass

    def append_history(self, section, key, point, limit=86400):
        with self._lock:
            target = self._data[section].setdefault(str(key), {})
            history = target.setdefault("history", [])
            history.append(point)
            if len(history) > limit:
                del history[:-limit]
            snapshot = copy.deepcopy(self._data)
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(snapshot)
            except Exception:
                pass

    def append_drop(self, section, key, timestamp, limit=86400):
        with self._lock:
            target = self._data[section].setdefault(str(key), {})
            drops = target.setdefault("drops", [])
            drops.append(timestamp)
            if len(drops) > limit:
                del drops[:-limit]
            snapshot = copy.deepcopy(self._data)
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(snapshot)
            except Exception:
                pass


def resource_path(relative_path):
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, relative_path)


class _ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class MonitoringWebServer:
    def __init__(self, state, command_handler, host="0.0.0.0", port=5005):
        self.state = state
        self.command_handler = command_handler
        self.host = host
        self.port = port
        self._server = None
        self._thread = None
        self._clients = {}
        self._clients_lock = threading.Lock()
        self._outgoing = queue.Queue(maxsize=2)
        self._publisher_thread = None
        self._running = threading.Event()

    def start(self):
        if self._running.is_set():
            return
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if not owner._is_local_address(self.client_address[0]):
                    self.send_error(403)
                    return
                if self.headers.get("Upgrade", "").lower() == "websocket" and self.path == "/ws":
                    origin = self.headers.get("Origin")
                    request_host = self.headers.get("Host", "").lower()
                    if origin and urlsplit(origin).netloc.lower() != request_host:
                        self.send_error(403)
                        return
                    owner._handle_websocket(self)
                    return
                owner._serve_static(self)

            def log_message(self, fmt, *args):
                return

        self._server = _ThreadingServer((self.host, self.port), Handler)
        self._running.set()
        self.state.subscribe(self.publish)
        self._thread = threading.Thread(target=self._server.serve_forever, name="monitor-http", daemon=True)
        self._publisher_thread = threading.Thread(target=self._publisher_loop, name="monitor-ws-publisher", daemon=True)
        self._thread.start()
        self._publisher_thread.start()

    def stop(self):
        if not self._running.is_set():
            return
        self._running.clear()
        self.state.unsubscribe(self.publish)
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        with self._clients_lock:
            clients = list(self._clients)
            self._clients.clear()
        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
                client.close()
            except OSError:
                pass

    def publish(self, snapshot):
        try:
            while self._outgoing.full():
                self._outgoing.get_nowait()
            self._outgoing.put_nowait(snapshot)
        except queue.Empty:
            pass

    def _publisher_loop(self):
        while self._running.is_set():
            try:
                snapshot = self._outgoing.get(timeout=0.5)
            except queue.Empty:
                continue
            payload = json.dumps({"type": "state", "data": snapshot}, ensure_ascii=False)
            with self._clients_lock:
                clients = list(self._clients.items())
            disconnected = []
            for client, send_lock in clients:
                try:
                    with send_lock:
                        self._send_frame(client, payload)
                except OSError:
                    disconnected.append(client)
            if disconnected:
                with self._clients_lock:
                    for client in disconnected:
                        self._clients.pop(client, None)

    @staticmethod
    def _is_local_address(address):
        try:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
            return ip.is_private or ip.is_loopback or ip.is_link_local
        except ValueError:
            return False

    def _serve_static(self, handler):
        files = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}
        filename = files.get(handler.path.split("?", 1)[0])
        if not filename:
            handler.send_error(404)
            return
        path = resource_path(os.path.join("web_monitor", filename))
        try:
            with open(path, "rb") as resource:
                content = resource.read()
        except OSError:
            handler.send_error(404, "Arquivo do painel nao encontrado")
            return
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        handler.send_response(200)
        handler.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") else ""))
        handler.send_header("Content-Length", str(len(content)))
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        handler.wfile.write(content)

    def _handle_websocket(self, handler):
        key = handler.headers.get("Sec-WebSocket-Key")
        if not key:
            handler.send_error(400)
            return
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        handler.send_response(101, "Switching Protocols")
        handler.send_header("Upgrade", "websocket")
        handler.send_header("Connection", "Upgrade")
        handler.send_header("Sec-WebSocket-Accept", accept)
        handler.end_headers()
        client = handler.connection
        send_lock = threading.Lock()
        with self._clients_lock:
            self._clients[client] = send_lock
        try:
            initial = json.dumps({"type": "state", "data": self.state.snapshot()}, ensure_ascii=False)
            with send_lock:
                self._send_frame(client, initial)
            while self._running.is_set():
                opcode, payload = self._read_frame(client)
                if opcode == 8:
                    break
                if opcode == 9:
                    with send_lock:
                        self._send_frame(client, payload, opcode=10)
                    continue
                if opcode != 1:
                    continue
                try:
                    message = json.loads(payload.decode("utf-8"))
                    self.command_handler(message)
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
                    error = json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False)
                    with send_lock:
                        self._send_frame(client, error)
        except (ConnectionError, OSError, TimeoutError, ValueError):
            pass
        finally:
            with self._clients_lock:
                self._clients.pop(client, None)
            try:
                client.close()
            except OSError:
                pass

    @staticmethod
    def _read_exact(client, size):
        data = bytearray()
        while len(data) < size:
            chunk = client.recv(size - len(data))
            if not chunk:
                raise ConnectionError("WebSocket desconectado")
            data.extend(chunk)
        return bytes(data)

    def _read_frame(self, client):
        first, second = self._read_exact(client, 2)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(client, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(client, 8))[0]
        if length > 1_000_000:
            raise ValueError("Mensagem WebSocket muito grande")
        mask = self._read_exact(client, 4) if masked else None
        payload = self._read_exact(client, length)
        if mask:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return opcode, payload

    @staticmethod
    def _send_frame(client, payload, opcode=1):
        data = payload.encode("utf-8") if isinstance(payload, str) else payload
        header = bytearray([0x80 | opcode])
        if len(data) < 126:
            header.append(len(data))
        elif len(data) < 65536:
            header.extend([126])
            header.extend(struct.pack("!H", len(data)))
        else:
            header.extend([127])
            header.extend(struct.pack("!Q", len(data)))
        client.sendall(bytes(header) + data)
