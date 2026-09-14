import base64
import copy
import hashlib
import ipaddress
import json
import logging
import mimetypes
import os
import socket
import socketserver
import struct
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit


class MonitoringState:
    """Thread-safe, in-memory state shared by Tkinter and the web panel."""

    def __init__(self, footer_text=""):
        self._lock = threading.RLock()
        self._listeners = []
        self._revision = 0
        self._data = {
            "app": {"footer_text": footer_text},
            "providers": {
                "eth2": {"name": "Unifique", "running": False, "output": "", "history": [], "drops": []},
                "eth4": {"name": "Claro", "running": False, "output": "", "history": [], "drops": []},
                "eth5": {"name": "Coopera", "running": False, "output": "", "history": [], "drops": []},
                "tun0": {"name": "OMR VPN", "running": False, "output": "", "history": [], "drops": []},
            },
            "tests": {str(i): {"running": False, "method": "mtr", "host": "", "port": "", "hosts": [],
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

    def snapshot(self, history_limit=None, with_revision=False):
        with self._lock:
            snapshot = copy.deepcopy(self._data)
            revision = self._revision
        if history_limit is not None:
            for section in ("providers", "tests"):
                for item in snapshot.get(section, {}).values():
                    for field in ("history", "drops"):
                        values = item.get(field)
                        if isinstance(values, list) and len(values) > history_limit:
                            item[field] = values[-history_limit:]
        return (snapshot, revision) if with_revision else snapshot

    def _notify(self, event, listeners):
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                pass

    def update(self, section, key, **values):
        with self._lock:
            key = str(key)
            target = self._data[section].setdefault(key, {})
            target.update(values)
            self._revision += 1
            listeners = list(self._listeners)
            event = {
                "section": section, "key": key, "revision": self._revision,
                "changes": copy.deepcopy(values),
            }
        self._notify(event, listeners)

    def append_history(self, section, key, point, limit=86400):
        with self._lock:
            key = str(key)
            target = self._data[section].setdefault(key, {})
            history = target.setdefault("history", [])
            history.append(point)
            if len(history) > limit:
                del history[:-limit]
            self._revision += 1
            listeners = list(self._listeners)
            event = {
                "section": section, "key": key, "revision": self._revision,
                "points": [copy.deepcopy(point)],
            }
        self._notify(event, listeners)

    def append_drop(self, section, key, timestamp, limit=86400):
        with self._lock:
            key = str(key)
            target = self._data[section].setdefault(key, {})
            drops = target.setdefault("drops", [])
            drops.append(timestamp)
            if len(drops) > limit:
                del drops[:-limit]
            self._revision += 1
            listeners = list(self._listeners)
            event = {
                "section": section, "key": key, "revision": self._revision,
                "drops": [copy.deepcopy(timestamp)],
            }
        self._notify(event, listeners)


def resource_paths(relative_path):
    roots = []
    if getattr(sys, "frozen", False):
        roots.append(os.path.dirname(sys.executable))
    else:
        roots.append(os.path.dirname(os.path.abspath(__file__)))
    roots.append(os.getcwd())
    if hasattr(sys, "_MEIPASS"):
        roots.append(sys._MEIPASS)

    paths = []
    seen = set()
    for root in roots:
        path = os.path.abspath(os.path.join(root, relative_path))
        normalized = os.path.normcase(path)
        if normalized not in seen:
            paths.append(path)
            seen.add(normalized)
    return paths


def resource_path(relative_path):
    return next((path for path in resource_paths(relative_path) if os.path.isfile(path)), None)


def bundled_resource_path(relative_path):
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, relative_path)


class _ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = os.name != "nt"
    daemon_threads = True

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class MonitoringWebServer:
    def __init__(self, state, command_handler, host="0.0.0.0", port=5005, logger=None):
        self.state = state
        self.command_handler = command_handler
        self.host = host
        self.port = port
        self.logger = logger or logging.getLogger(__name__)
        self._server = None
        self._thread = None
        self._clients = {}
        self._clients_lock = threading.Lock()
        self._pending = {}
        self._pending_lock = threading.Lock()
        self._pending_ready = threading.Event()
        self._publisher_thread = None
        self._running = threading.Event()

    def start(self):
        if self._running.is_set():
            return
        owner = self

        class Handler(BaseHTTPRequestHandler):
            # A resposta 101 do WebSocket deve usar HTTP/1.1. O padrao desta
            # classe e HTTP/1.0, que navegadores rejeitam silenciosamente.
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                client_address = self.client_address[0]
                request_path = urlsplit(self.path).path
                owner.logger.info("Painel web: conexao HTTP aceita de %s para %s", client_address, request_path)
                try:
                    if not owner._is_local_address(client_address):
                        owner.logger.warning("Painel web: acesso recusado para endereco nao local %s", client_address)
                        self.send_error(403)
                        return
                    if request_path == "/ws":
                        if self.headers.get("Upgrade", "").lower() != "websocket":
                            owner.logger.warning("Painel web: handshake WebSocket invalido de %s (Upgrade ausente)", client_address)
                            self.send_response(426, "Upgrade Required")
                            self.send_header("Upgrade", "websocket")
                            self.send_header("Content-Length", "0")
                            self.end_headers()
                            return
                        origin = self.headers.get("Origin")
                        request_host = self.headers.get("Host", "").lower()
                        if origin and urlsplit(origin).netloc.lower() != request_host:
                            owner.logger.warning("Painel web: handshake WebSocket recusado por origem divergente de %s", client_address)
                            self.send_error(403)
                            return
                        self.close_connection = True
                        owner._handle_websocket(self)
                        return
                    owner._serve_static(self)
                except (ConnectionError, OSError, TimeoutError) as exc:
                    owner.logger.warning("Painel web: conexao HTTP encerrada por %s: %s", client_address, exc)
                except Exception:
                    owner.logger.exception("Painel web: erro inesperado ao atender %s", client_address)

            def log_message(self, fmt, *args):
                return

        try:
            self._server = _ThreadingServer((self.host, self.port), Handler)
        except OSError as exc:
            self.logger.error("Painel web: falha ao vincular %s:%s: %s", self.host, self.port, exc)
            raise
        self._running.set()
        self.state.subscribe(self.publish)
        self._thread = threading.Thread(target=self._server.serve_forever, name="monitor-http", daemon=True)
        self._publisher_thread = threading.Thread(target=self._publisher_loop, name="monitor-ws-publisher", daemon=True)
        self._thread.start()
        self._publisher_thread.start()
        self.logger.info("Painel web: servidor HTTP/WebSocket ativo em %s:%s (rota /ws)", self.host, self.port)

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
        self.logger.info("Painel web: servidor encerrado")

    def publish(self, event):
        identity = (event["section"], event["key"])
        with self._pending_lock:
            pending = self._pending.setdefault(identity, {
                "section": event["section"], "key": event["key"]
            })
            pending["revision"] = event["revision"]
            if event.get("changes"):
                pending.setdefault("changes", {}).update(event["changes"])
            if event.get("points"):
                pending["points"] = event["points"][-1:]
            if event.get("drops"):
                pending["drops"] = event["drops"][-1:]
        self._pending_ready.set()

    def _publisher_loop(self):
        publish_interval = 0.25
        while self._running.is_set():
            if not self._pending_ready.wait(timeout=0.5):
                continue
            time.sleep(publish_interval)
            if not self._running.is_set():
                break
            with self._pending_lock:
                patches = sorted(self._pending.values(), key=lambda patch: patch["revision"])
                self._pending.clear()
                self._pending_ready.clear()
            if not patches:
                continue
            payload = json.dumps({"type": "patch", "patches": patches}, ensure_ascii=False)
            with self._clients_lock:
                clients = list(self._clients.items())
            disconnected = []
            for client, send_lock in clients:
                try:
                    with send_lock:
                        self._send_frame(client, payload)
                except OSError as exc:
                    self.logger.info("Painel web: cliente WebSocket desconectado durante envio: %s", exc)
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
        request_path = handler.path.split("?", 1)[0]
        files = {
            "/": os.path.join("web_monitor", "index.html"),
            "/index.html": os.path.join("web_monitor", "index.html"),
            "/app.js": os.path.join("web_monitor", "app.js"),
            "/styles.css": os.path.join("web_monitor", "styles.css"),
        }
        if request_path == "/OMR_logo.png":
            attempted_paths = resource_paths("OMR_logo.png")
            path = resource_path("OMR_logo.png")
        else:
            relative_path = files.get(request_path)
            if not relative_path:
                handler.send_error(404)
                return
            path = bundled_resource_path(relative_path)
            attempted_paths = [path]

        if not path:
            self.logger.warning(
                "Painel web: arquivo estatico nao encontrado; caminhos tentados: %s",
                ", ".join(attempted_paths),
            )
            handler.send_error(404, "Arquivo do painel nao encontrado")
            return
        try:
            with open(path, "rb") as resource:
                content = resource.read()
        except OSError as exc:
            self.logger.warning(
                "Painel web: nao foi possivel abrir arquivo estatico %s: %s",
                path,
                exc,
            )
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
        client_address = handler.client_address[0]
        key = handler.headers.get("Sec-WebSocket-Key")
        connection_tokens = {
            token.strip().lower() for token in handler.headers.get("Connection", "").split(",")
        }
        try:
            valid_key = len(base64.b64decode(key or "", validate=True)) == 16
        except (ValueError, TypeError):
            valid_key = False
        if "upgrade" not in connection_tokens or handler.headers.get("Sec-WebSocket-Version") != "13" or not valid_key:
            self.logger.warning("Painel web: erro de protocolo no handshake WebSocket de %s", client_address)
            handler.send_error(400, "Handshake WebSocket invalido")
            return
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        handler.send_response(101, "Switching Protocols")
        handler.send_header("Upgrade", "websocket")
        handler.send_header("Connection", "Upgrade")
        handler.send_header("Sec-WebSocket-Accept", accept)
        handler.end_headers()
        client = handler.connection
        send_lock = threading.Lock()
        try:
            send_lock.acquire()
            try:
                with self._clients_lock:
                    self._clients[client] = send_lock
                self.logger.info("Painel web: handshake aceito; cliente WebSocket conectado de %s", client_address)
                snapshot, revision = self.state.snapshot(history_limit=3600, with_revision=True)
                initial = json.dumps({"type": "state", "revision": revision, "data": snapshot}, ensure_ascii=False)
                self._send_frame(client, initial)
            finally:
                send_lock.release()
            while self._running.is_set():
                opcode, payload = self._read_frame(client)
                if opcode == 8:
                    with send_lock:
                        self._send_frame(client, payload, opcode=8)
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
        except ValueError as exc:
            self.logger.warning("Painel web: erro de protocolo WebSocket de %s: %s", client_address, exc)
            try:
                with send_lock:
                    self._send_frame(client, struct.pack("!H", 1002), opcode=8)
            except OSError:
                pass
        except (ConnectionError, OSError, TimeoutError) as exc:
            self.logger.info("Painel web: cliente WebSocket %s desconectado: %s", client_address, exc)
        except Exception:
            self.logger.exception("Painel web: erro inesperado no cliente WebSocket %s", client_address)
        finally:
            with self._clients_lock:
                self._clients.pop(client, None)
            try:
                client.close()
            except OSError:
                pass
            self.logger.info("Painel web: conexao WebSocket de %s encerrada", client_address)

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
        if first & 0x70:
            raise ValueError("bits RSV nao suportados")
        if not first & 0x80:
            raise ValueError("frames fragmentados nao suportados")
        opcode = first & 0x0F
        if opcode not in (1, 8, 9, 10):
            raise ValueError("opcode nao suportado")
        masked = bool(second & 0x80)
        if not masked:
            raise ValueError("frame do cliente sem mascara")
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(client, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(client, 8))[0]
        if length > 1_000_000:
            raise ValueError("Mensagem WebSocket muito grande")
        if opcode >= 8 and length > 125:
            raise ValueError("frame de controle muito grande")
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
