import socket
import threading
import ctypes  # Para definir o título da janela no Windows
from ctypes import wintypes
import sys
import logging
from logging.handlers import RotatingFileHandler

# Configura o logger para gravar as mensagens no arquivo proxy_tcp.log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
logger = logging.getLogger('proxy_tcp_logger')

file_handler = RotatingFileHandler('proxy_tcp.log', maxBytes=5*1024*1024, backupCount=3)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Cria um mutex
mutex = ctypes.windll.kernel32.CreateMutexW(None, wintypes.BOOL(True), "Global\\temerproxy")

# Verifica se o mutex já existe
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    logger.error("Já existe uma instância do programa em execução. Programa encerrado.")
    sys.exit(0)

class SocksProxy:
    def __init__(self, local_port, bind_ip):
        self.local_port = local_port
        self.bind_ip = bind_ip  # IP local para fazer o bind e onde o tráfego será encaminhado
        self.clear_log_file('proxy_tcp.log')  # Limpa o arquivo de log ao iniciar o programa

    def clear_log_file(self, log_file_path):
        open(log_file_path, 'w').close()

    def start_socks_proxy(self):
        # Define o título da janela como "Proxy TCP"
        ctypes.windll.kernel32.SetConsoleTitleW("Proxy TCP")

        # Estabelece uma escuta na porta local
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('0.0.0.0', self.local_port))
        server.listen(100)
        logger.info(f"Proxy SOCKS iniciado: 0.0.0.0:{self.local_port}")

        while True:
            client_socket, _ = server.accept()
            logger.info(f"Conexão recebida na porta local {self.local_port}")
            threading.Thread(target=self.handle_socks_connection, args=(client_socket,)).start()

    def handle_socks_connection(self, client_socket):
        try:
            # Handshake SOCKS5: lendo os dois primeiros bytes (versão e número de métodos)
            handshake = client_socket.recv(2)
            if len(handshake) < 2:
                logger.warning(f"Handshake incompleto recebido: {handshake}")
                client_socket.close()
                return

            version, n_methods = handshake
            logger.info(f"Versão SOCKS recebida: {version}, Métodos de autenticação: {n_methods}")

            # Verifica se a versão SOCKS é 5
            if version != 0x05:
                logger.error(f"Versão SOCKS não suportada: {version}")
                client_socket.close()
                return
            
            # Lê os métodos de autenticação
            methods = client_socket.recv(n_methods)
            logger.info(f"Métodos de autenticação suportados: {methods}")

            # Envia resposta ao handshake (sem autenticação)
            client_socket.sendall(b'\x05\x00')

            # Recebe o pedido SOCKS (versão, comando, reservado, tipo de endereço)
            request = client_socket.recv(4)
            if len(request) < 4:
                logger.warning(f"Pedido SOCKS incompleto recebido: {request}")
                client_socket.close()
                return

            version, cmd, reserved, addr_type = request
            logger.info(f"Pedido SOCKS: versão {version}, comando {cmd}, tipo de endereço {addr_type}")

            # Verifica se a versão SOCKS é 5 (novamente no pedido)
            if version != 0x05:
                logger.error(f"Versão SOCKS não suportada no pedido: {version}")
                client_socket.close()
                return

            # Rejeita tráfego IPv6
            if addr_type == 0x04:  # IPv6
                logger.warning("Tráfego IPv6 detectado. Conexão rejeitada.")
                client_socket.sendall(b'\x05\x08\x00\x01' + socket.inet_aton('0.0.0.0') + b'\x00\x00')
                client_socket.close()
                return

            # Obtém o endereço de destino baseado no tipo de endereço
            if addr_type == 0x01:  # IPv4
                addr = socket.inet_ntoa(client_socket.recv(4))
            elif addr_type == 0x03:  # Domínio
                addr_len = client_socket.recv(1)[0]
                addr = client_socket.recv(addr_len).decode()
            else:
                logger.error("Tipo de endereço não suportado.")
                client_socket.close()
                return

            # Recebe a porta de destino
            port = int.from_bytes(client_socket.recv(2), 'big')
            logger.info(f"Encaminhando para {addr}:{port}")

            # Responde ao cliente SOCKS que a solicitação foi bem-sucedida
            client_socket.sendall(b'\x05\x00\x00\x01' + socket.inet_aton('0.0.0.0') + b'\x00\x00')

            # Estabelece uma conexão com o endereço e porta de destino recebidos do cliente
            remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote_socket.bind((self.bind_ip, 0))  # O sistema escolherá a porta de saída
            remote_socket.connect((addr, port))

            # Encaminha os dados entre o cliente e a conexão remota
            threading.Thread(target=self.forward_data, args=(client_socket, remote_socket)).start()
            threading.Thread(target=self.forward_data, args=(remote_socket, client_socket)).start()

        except Exception as e:
            logger.error(f"Erro ao lidar com a conexão SOCKS: {e}")
            client_socket.close()

    def forward_data(self, source, destination):
        try:
            while True:
                data = source.recv(4096)
                if len(data) == 0:
                    logger.info("Nenhum dado recebido, fechando conexão.")
                    break
                destination.send(data)
        except OSError as e:
            logger.error(f"Erro de soquete: {e}")
        except Exception as e:
            logger.error(f"Erro no encaminhamento de dados: {e}")
        finally:
            source.close()
            destination.close()

# Instancia a classe e inicia o proxy SOCKS
if __name__ == '__main__':
    local_port = 8889              # Porta local para o proxy SOCKS
    bind_ip = '192.168.100.2'      # IP local para bind (interface de saída, onde o tráfego será encaminhado)

    proxy = SocksProxy(local_port, bind_ip)
    proxy.start_socks_proxy()
