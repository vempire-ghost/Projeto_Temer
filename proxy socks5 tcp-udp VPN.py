import socket
import threading
import ctypes
from ctypes import wintypes
import sys
import logging
from logging.handlers import RotatingFileHandler
import select
import struct
import os

# Cria a pasta Logs se ela não existir
log_dir = 'Logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Configuração do logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
logger = logging.getLogger('proxy_tcp_udp_logger')

# Define o caminho do arquivo de log dentro da pasta Logs
log_file_path = os.path.join(log_dir, 'proxy_tcp_udp_vpn.log')

# Configura o RotatingFileHandler para salvar na pasta Logs
file_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=3)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Mutex permanece o mesmo
mutex = ctypes.windll.kernel32.CreateMutexW(None, wintypes.BOOL(True), "Global\\temerproxy-vpn")
if ctypes.windll.kernel32.GetLastError() == 183:
    logger.error("Já existe uma instância do programa em execução. Programa encerrado.")
    sys.exit(0)

class SocksProxy:
    def __init__(self, local_port, bind_ip):
        self.local_port = local_port
        self.bind_ip = bind_ip
        self.udp_sessions = {}
        self.running = True
        self.clear_log_file('proxy_tcp_udp_vpn.log')

    def clear_log_file(self, log_file_name, log_dir='Logs'):
        # Define o caminho completo do arquivo de log
        log_file_path = os.path.join(log_dir, log_file_name)
        # Verifica se o arquivo existe antes de tentar limpá-lo
        if os.path.exists(log_file_path):
            open(log_file_path, 'w').close()
        else:
            print(f"Arquivo de log não encontrado: {log_file_path}")

    def start_socks_proxy(self):
        ctypes.windll.kernel32.SetConsoleTitleW("Proxy TCP/UDP")

        # Servidor TCP
        tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_server.bind(('0.0.0.0', self.local_port))
        tcp_server.listen(100)
        logger.info(f"Proxy SOCKS iniciado (TCP/UDP): 192.168.101.2:{self.local_port}")

        while self.running:
            try:
                client_socket, client_addr = tcp_server.accept()
                threading.Thread(target=self.handle_socks_connection, args=(client_socket, client_addr)).start()
            except Exception as e:
                logger.error(f"Erro ao aceitar conexão TCP: {e}")

    def handle_socks_connection(self, client_socket, client_addr):
        try:
            # Handshake SOCKS5
            handshake = client_socket.recv(2)
            if len(handshake) < 2:
                logger.warning("Handshake incompleto")
                client_socket.close()
                return

            version, n_methods = handshake
            if version != 0x05:
                logger.error(f"Versão SOCKS não suportada: {version}")
                client_socket.close()
                return

            methods = client_socket.recv(n_methods)
            client_socket.sendall(b'\x05\x00')  # Sem autenticação

            # Recebe pedido SOCKS
            request = client_socket.recv(4)
            if len(request) < 4:
                logger.warning("Pedido SOCKS incompleto")
                client_socket.close()
                return

            version, cmd, reserved, addr_type = request

            # Obtém endereço de destino
            dest_addr = None
            if addr_type == 0x01:  # IPv4
                raw_addr = client_socket.recv(4)
                dest_addr = socket.inet_ntoa(raw_addr)
            elif addr_type == 0x03:  # Domain
                addr_len = client_socket.recv(1)[0]
                dest_addr = client_socket.recv(addr_len).decode()
            else:
                logger.warning("Tipo de endereço não suportado")
                client_socket.sendall(b'\x05\x08\x00\x01' + socket.inet_aton('0.0.0.0') + b'\x00\x00')
                client_socket.close()
                return

            dest_port = int.from_bytes(client_socket.recv(2), 'big')
            
            logger.info(f"Pedido SOCKS5: cmd={cmd}, addr={dest_addr}, 192.168.101.2 port={dest_port}")

            if cmd == 0x01:  # CONNECT (TCP)
                self.handle_tcp_connection(client_socket, dest_addr, dest_port)
            elif cmd == 0x03:  # UDP ASSOCIATE
                self.handle_udp_associate(client_socket, client_addr, dest_addr, dest_port)
            else:
                logger.error(f"Comando não suportado: {cmd}")
                client_socket.sendall(b'\x05\x07\x00\x01' + socket.inet_aton('0.0.0.0') + b'\x00\x00')
                client_socket.close()

        except Exception as e:
            logger.error(f"Erro na conexão SOCKS: {e}")
            client_socket.close()

    def handle_udp_associate(self, client_socket, client_addr, dest_addr, dest_port):
        try:
            # Criar socket UDP para relay
            relay_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            relay_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            relay_socket.bind((self.bind_ip, 0))
            relay_addr, relay_port = relay_socket.getsockname()

            logger.info(f"UDP Associate: Relay criado em {relay_addr}:{relay_port}")
            logger.info(f"UDP Associate: Cliente original em {client_addr[0]}:{client_addr[1]}")
            logger.info(f"UDP Associate: Destino solicitado {dest_addr}:{dest_port}")

            # Responder ao cliente com endereço do relay
            response = struct.pack('!BBBB4sH', 
                0x05, 0x00, 0x00, 0x01,
                socket.inet_aton(self.bind_ip),
                relay_port
            )
            client_socket.sendall(response)

            # Configurar sessão UDP - Agora armazenando o endereço real do cliente
            session = {
                'client_socket': client_socket,
                'relay_socket': relay_socket,
                'client_addr': client_addr[0],  # Endereço real do cliente
                'client_port': None,  # Será definido quando recebermos o primeiro pacote
                'remote_addr': None,
                'remote_port': None
            }

            # Usar endereço do relay como chave da sessão
            session_key = (relay_addr, relay_port)
            self.udp_sessions[session_key] = session

            udp_thread = threading.Thread(target=self.handle_udp_traffic, args=(session,))
            udp_thread.daemon = True
            udp_thread.start()

            while self.running:
                try:
                    client_socket.setblocking(False)
                    data = client_socket.recv(1)
                    if not data:
                        break
                except BlockingIOError:
                    pass
                except Exception:
                    break

            self.cleanup_udp_session(session_key)

        except Exception as e:
            logger.error(f"Erro no UDP Associate: {e}")
            client_socket.close()

    def handle_udp_traffic(self, session):
        relay_socket = session['relay_socket']

        while self.running:
            try:
                readable, _, _ = select.select([relay_socket], [], [], 1.0)
                if not readable:
                    continue

                data, addr = relay_socket.recvfrom(65535)
                if not data:
                    continue

                logger.debug(f"UDP: Recebido pacote de {addr[0]}:{addr[1]}")

                # Se for um pacote do cliente
                if session['client_port'] is None or addr[0] == session['client_addr']:
                    # Atualizar a porta do cliente se ainda não definida
                    if session['client_port'] is None:
                        session['client_port'] = addr[1]
                        logger.info(f"UDP: Porta do cliente definida como {addr[1]}")

                    # Processar cabeçalho SOCKS UDP
                    if len(data) < 10:
                        continue

                    frag = data[2]
                    atyp = data[3]
                    
                    if frag != 0:
                        continue

                    if atyp == 0x01:  # IPv4
                        dest_addr = socket.inet_ntoa(data[4:8])
                        dest_port = struct.unpack('!H', data[8:10])[0]
                        header_size = 10
                    elif atyp == 0x03:  # Domain
                        length = data[4]
                        dest_addr = data[5:5+length].decode()
                        dest_port = struct.unpack('!H', data[5+length:7+length])[0]
                        header_size = 7 + length
                    else:
                        continue

                    # Atualizar endereço remoto
                    if session['remote_addr'] != dest_addr or session['remote_port'] != dest_port:
                        session['remote_addr'] = dest_addr
                        session['remote_port'] = dest_port
                        logger.info(f"UDP: Novo destino configurado {dest_addr}:{dest_port}")

                    # Enviar payload para o destino
                    payload = data[header_size:]
                    relay_socket.sendto(payload, (dest_addr, dest_port))
                    logger.debug(f"UDP: Enviado para {dest_addr}:{dest_port}")

                # Se for resposta do servidor
                elif addr[0] == session['remote_addr'] and addr[1] == session['remote_port']:
                    # Construir resposta SOCKS UDP
                    udp_header = struct.pack('!HB', 0, 0) + \
                                bytes([0x01]) + \
                                socket.inet_aton(addr[0]) + \
                                struct.pack('!H', addr[1])
                    
                    response = udp_header + data
                    # Usar o endereço real do cliente em vez de 0.0.0.0
                    relay_socket.sendto(response, (session['client_addr'], session['client_port']))
                    logger.debug(f"UDP: Resposta enviada para {session['client_addr']}:{session['client_port']}")

            except Exception as e:
                logger.error(f"Erro no processamento UDP: {e}")
                break

    def handle_tcp_connection(self, client_socket, addr, port):
        try:
            remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            remote_socket.bind((self.bind_ip, 0))
            remote_socket.connect((addr, port))

            response = struct.pack('!BBBB4sH', 
                0x05, 0x00, 0x00, 0x01,
                socket.inet_aton('0.0.0.0'),
                0
            )
            client_socket.sendall(response)

            threading.Thread(target=self.forward_data, args=(client_socket, remote_socket)).start()
            threading.Thread(target=self.forward_data, args=(remote_socket, client_socket)).start()

        except Exception as e:
            logger.error(f"Erro na conexão TCP: {e}")
            client_socket.close()

    def cleanup_udp_session(self, session_key):
        if session_key in self.udp_sessions:
            session = self.udp_sessions[session_key]
            try:
                session['relay_socket'].close()
                session['client_socket'].close()
            except:
                pass
            del self.udp_sessions[session_key]
            logger.info(f"Sessão UDP encerrada para {session_key}")

    def forward_data(self, source, destination):
        try:
            while self.running:
                data = source.recv(8192)
                if not data:
                    break
                destination.send(data)
        except:
            pass
        finally:
            try:
                source.close()
                destination.close()
            except:
                pass

    def shutdown(self):
        self.running = False
        for session_key in list(self.udp_sessions.keys()):
            self.cleanup_udp_session(session_key)

if __name__ == '__main__':
    local_port = 8889
    bind_ip = '192.168.101.2'

    proxy = SocksProxy(local_port, bind_ip)
    try:
        proxy.start_socks_proxy()
    except KeyboardInterrupt:
        logger.info("Encerrando proxy...")
        proxy.shutdown()
