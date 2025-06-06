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
import subprocess
import re
import time

# Cria a pasta Logs se ela não existir
log_dir = 'Logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Configuração do logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
logger = logging.getLogger('proxy_tcp_udp_logger')

# Define o caminho do arquivo de log dentro da pasta Logs
log_file_path = os.path.join(log_dir, 'proxy_tcp_udp_jogo.log')

# Configura o RotatingFileHandler para salvar na pasta Logs
file_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=3)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Mutex permanece o mesmo
mutex = ctypes.windll.kernel32.CreateMutexW(None, wintypes.BOOL(True), "Global\\temerproxy-jogo")
if ctypes.windll.kernel32.GetLastError() == 183:
    logger.error("Já existe uma instância do programa em execução. Programa encerrado.")
    sys.exit(0)

class SocksProxy:
    def __init__(self, local_port, bind_ip, bind_ipv6=None):
        self.local_port = local_port
        self.bind_ip = bind_ip
        self.bind_ipv6 = bind_ipv6 if bind_ipv6 else self._get_available_ipv6_address()  # Detecta IPv6 automaticamente
        self.udp_sessions = {}
        self.running = True
        self.clear_log_file('proxy_tcp_udp_jogo.log')

    def _get_available_ipv6_address(self):
        """Obtém um endereço IPv6 global válido com múltiplos métodos de fallback"""
        try:
            # Método 1: Usando socket (funciona na maioria dos sistemas)
            with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as s:
                try:
                    s.connect(('2606:4700:4700::1111', 80))  # DNS IPv6 do Cloudflare
                    local_ip = s.getsockname()[0]
                    if '%' in local_ip:
                        local_ip = local_ip.split('%')[0]  # Remove o identificador de interface
                    if not local_ip.startswith(('fe80::', '::1')):  # Filtra link-local e loopback
                        logger.info(f"Endereço IPv6 detectado (Método 1): {local_ip}")
                        return local_ip
                except:
                    pass

            # Método 2: Para Windows (ipconfig)
            if os.name == 'nt':
                try:
                    result = subprocess.run(['ipconfig'], capture_output=True, text=True, encoding='utf-8')
                    for line in result.stdout.split('\n'):
                        if 'IPv6 Address' in line and not 'Temporary' in line:
                            # Extrai o endereço IPv6 usando expressão regular
                            match = re.search(r'([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}', line)
                            if match:
                                addr = match.group(0).split('%')[0]
                                if not addr.startswith(('fe80::', '::1')):
                                    logger.info(f"Endereço IPv6 detectado (Método 2): {addr}")
                                    return addr
                except:
                    pass

            # Método 3: Lista todas interfaces (Linux/Windows)
            try:
                for interface in socket.if_nameindex():
                    try:
                        ifaddrs = socket.getaddrinfo(interface[1], None, socket.AF_INET6)
                        for addr in ifaddrs:
                            ip = addr[4][0]
                            if '%' in ip:
                                ip = ip.split('%')[0]
                            if not ip.startswith(('fe80::', '::1')):
                                logger.info(f"Endereço IPv6 detectado (Método 3): {ip}")
                                return ip
                    except:
                        continue
            except:
                pass

            # Método 4: Último recurso - endereço estático configurável
            fallback_ipv6 = "2804:5020:23:4001:ff78:fbfe:75da:8abc"  # Pode ser configurado
            logger.warning(f"Nenhum IPv6 válido detectado. Usando endereço IPv6 fallback: {fallback_ipv6}")
            return fallback_ipv6

        except Exception as e:
            logger.error(f"Erro crítico ao obter IPv6: {str(e)}")
            return None

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

        # Servidor TCP (IPv4)
        tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_server.bind(('0.0.0.0', self.local_port))
        tcp_server.listen(100)
        logger.info(f"Proxy SOCKS iniciado (TCP/UDP): {self.bind_ip}:{self.local_port}")
        if self.bind_ipv6:
            logger.info(f"Endereço IPv6 configurado: {self.bind_ipv6}")

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
            elif addr_type == 0x04:  # IPv6
                raw_addr = client_socket.recv(16)
                dest_addr = socket.inet_ntop(socket.AF_INET6, raw_addr)
            else:
                logger.warning("Tipo de endereço não suportado")
                client_socket.sendall(b'\x05\x08\x00\x01' + socket.inet_aton('0.0.0.0') + b'\x00\x00')
                client_socket.close()
                return

            dest_port = int.from_bytes(client_socket.recv(2), 'big')
            
            # Mensagem de log modificada para mostrar o IP correto baseado no tipo
            cmd_name = "TCP" if cmd == 0x01 else "UDP" if cmd == 0x03 else f"cmd={cmd}"
            if addr_type == 0x04:  # IPv6
                logger.info(f"Pedido IPv6: {cmd_name}, {dest_addr} de {client_addr} Encaminhado para: WIFI COOPERA:{dest_port}")
            else:
                logger.info(f"Pedido IPv4: {cmd_name}, {dest_addr} de {client_addr} Encaminhado para: {self.bind_ip}:{dest_port}")

            if cmd == 0x01:  # CONNECT (TCP)
                self.handle_tcp_connection(client_socket, dest_addr, dest_port, addr_type)
            elif cmd == 0x03:  # UDP ASSOCIATE
                self.handle_udp_associate(client_socket, client_addr, dest_addr, dest_port, addr_type)
            else:
                logger.error(f"Comando não suportado: {cmd_name}")
                client_socket.sendall(b'\x05\x07\x00\x01' + socket.inet_aton('0.0.0.0') + b'\x00\x00')
                client_socket.close()

        except Exception as e:
            logger.error(f"Erro na conexão SOCKS: {e}")
            client_socket.close()

    def handle_udp_associate(self, client_socket, client_addr, dest_addr, dest_port, addr_type):
        try:
            # Criar dois sockets UDP separados:
            # 1. Para receber do cliente (na rede 192.168.0.x)
            # 2. Para enviar para internet (na rede 192.168.100.x)
            
            # Socket para receber do cliente - bind em 0.0.0.0 (todas interfaces)
            recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            recv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            recv_socket.bind(('0.0.0.0', 0))
            recv_port = recv_socket.getsockname()[1]
            
            # Socket para enviar para internet - bind na interface específica (192.168.100.2)
            send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            send_socket.bind((self.bind_ip, 0))  # self.bind_ip = 192.168.100.2
            
            logger.info(f"UDP Associate: Relay criado (recebe em 0.0.0.0:{recv_port}, envia por {self.bind_ip})")
            logger.info(f"UDP Associate: Cliente original em {client_addr[0]}:{client_addr[1]}")
            logger.info(f"UDP Associate: Destino solicitado {dest_addr}:{dest_port}")

            # Responder ao cliente com endereço do relay (usando o IP da interface que o cliente pode alcançar)
            response = struct.pack('!BBBB4sH', 
                0x05, 0x00, 0x00, 0x01,
                socket.inet_aton('192.168.0.4'),  # IP que o cliente pode alcançar
                recv_port
            )
            client_socket.sendall(response)

            # Configurar sessão UDP
            session = {
                'client_socket': client_socket,
                'recv_socket': recv_socket,  # Socket para receber do cliente
                'send_socket': send_socket,    # Socket para enviar para internet
                'client_addr': client_addr[0],
                'client_port': None,  # Será definido quando recebermos o primeiro pacote
                'remote_addr': None,
                'remote_port': None,
                'addr_type': addr_type,
                'last_activity': time.time()
            }

            session_key = (recv_socket.getsockname()[0], recv_port)
            self.udp_sessions[session_key] = session

            udp_thread = threading.Thread(target=self.handle_udp_traffic, args=(session,))
            udp_thread.daemon = True
            udp_thread.start()

            # Monitorar conexão TCP para saber quando encerrar
            while self.running:
                try:
                    client_socket.settimeout(1.0)
                    data = client_socket.recv(1)
                    if not data:
                        break
                except socket.timeout:
                    continue
                except Exception:
                    break

            self.cleanup_udp_session(session_key)

        except Exception as e:
            logger.error(f"Erro no UDP Associate: {e}")
            client_socket.close()

    def handle_udp_traffic(self, session):
        recv_socket = session['recv_socket']  # Recebe do cliente (0.0.0.0)
        send_socket = session['send_socket']  # Envia/recebe da internet (192.168.100.2)
        addr_type = session['addr_type']

        while self.running:
            try:
                # Monitorar ambos os sockets
                readable, _, _ = select.select([recv_socket, send_socket], [], [], 1.0)
                if not readable:
                    continue

                for sock in readable:
                    # Receber dados do socket
                    data, addr = sock.recvfrom(65535)
                    if not data:
                        continue

                    # Pacote do cliente (recebido pelo recv_socket)
                    if sock is recv_socket:
                        logger.debug(f"UDP: Recebido pacote do cliente {addr[0]}:{addr[1]}")

                        # Atualizar porta do cliente se necessário
                        if session['client_port'] is None or addr[0] == session['client_addr']:
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
                        elif atyp == 0x04:  # IPv6
                            dest_addr = socket.inet_ntop(socket.AF_INET6, data[4:20])
                            dest_port = struct.unpack('!H', data[20:22])[0]
                            header_size = 22
                        else:
                            continue

                        # Atualizar endereço remoto
                        if session['remote_addr'] != dest_addr or session['remote_port'] != dest_port:
                            session['remote_addr'] = dest_addr
                            session['remote_port'] = dest_port
                            logger.info(f"UDP: Novo destino configurado {dest_addr}:{dest_port}")

                        # Enviar payload para o destino usando o socket de envio
                        payload = data[header_size:]
                        try:
                            send_socket.sendto(payload, (dest_addr, dest_port))
                            logger.debug(f"UDP: Enviado para {dest_addr}:{dest_port} via {self.bind_ip}")
                        except Exception as e:
                            logger.error(f"Erro ao enviar pacote UDP: {e}")

                    # Resposta do servidor (recebida pelo send_socket)
                    elif sock is send_socket:
                        logger.debug(f"UDP: Recebido pacote do servidor {addr[0]}:{addr[1]}")

                        # Verificar se é uma resposta do destino esperado
                        if (session['remote_addr'] == addr[0] and 
                            session['remote_port'] == addr[1]):
                            
                            # Construir cabeçalho SOCKS UDP para enviar ao cliente
                            udp_header = struct.pack('!HB', 0, 0)  # RSV, FRAG
                            
                            if addr_type == 0x04:  # IPv6
                                udp_header += bytes([0x04])  # ATYP (IPv6)
                                udp_header += socket.inet_pton(socket.AF_INET6, addr[0])
                            else:  # IPv4
                                udp_header += bytes([0x01])  # ATYP (IPv4)
                                udp_header += socket.inet_aton(addr[0])
                            
                            udp_header += struct.pack('!H', addr[1])  # PORT
                            
                            # Enviar pacote completo para o cliente
                            full_packet = udp_header + data
                            recv_socket.sendto(full_packet, 
                                              (session['client_addr'], session['client_port']))
                            logger.debug(f"UDP: Resposta encaminhada para cliente {session['client_addr']}:{session['client_port']}")

            except Exception as e:
                logger.error(f"Erro no processamento UDP: {e}")
                break

    def handle_tcp_connection(self, client_socket, addr, port, addr_type):
        try:
            if addr_type == 0x04:  # IPv6
                # Usar o endereço IPv6 configurado como destino
                remote_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                remote_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                remote_socket.bind((self.bind_ipv6, 0))
                remote_socket.connect((self.bind_ipv6 if addr == '::' else addr, port))
            else:
                # IPv4 ou domínio
                remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                remote_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                remote_socket.bind((self.bind_ip, 0))
                remote_socket.connect((addr, port))

            # Responder ao cliente
            if addr_type == 0x04:  # IPv6
                response = struct.pack('!BBBB', 0x05, 0x00, 0x00, 0x04)
                response += socket.inet_pton(socket.AF_INET6, self.bind_ipv6)
                response += struct.pack('!H', 0)
            else:
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
    local_port = 8890
    bind_ip = '192.168.100.2'
    bind_ipv6 = None  # Opcional: pode definir um IPv6 manualmente aqui se quiser

    proxy = SocksProxy(local_port, bind_ip, bind_ipv6)
    try:
        proxy.start_socks_proxy()
    except KeyboardInterrupt:
        logger.info("Encerrando proxy...")
        proxy.shutdown()
