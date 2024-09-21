import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, scrolledtext, colorchooser, ttk, Menu
import os
import json
import subprocess
import threading
import tempfile
import shlex
import shutil
import uuid
import time
import zipfile
import ctypes
import socket
import sys
import webview
import logging
from logging.handlers import RotatingFileHandler
import winreg
import queue
import paramiko
import configparser
import re
import select
import pyte
from datetime import datetime
from ctypes import wintypes
from pystray import Icon, MenuItem, Menu as TrayMenu
from PIL import Image, ImageTk, ImageDraw

# Cria um mutex
mutex = ctypes.windll.kernel32.CreateMutexW(None, wintypes.BOOL(True), "Global\\MyProgramMutex")

# Verifica se o mutex já existe
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    print("Já existe uma instância do programa em execução. Programa encerrado.")
    sys.exit(0)

# Configuração básica do logging para salvar em dois arquivos diferentes
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')

# Criando o Formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')

# Logger principal
logger_main = logging.getLogger('main_logger')
# Usando RotatingFileHandler em vez de FileHandler, com limite de 5 MB e até 3 backups
main_handler = RotatingFileHandler('app.log', maxBytes=5*1024*1024, backupCount=3)
main_handler.setLevel(logging.INFO)
main_handler.setFormatter(formatter)
logger_main.addHandler(main_handler)

# Logger secundário para o run_test_command
logger_test_command = logging.getLogger('test_command_logger')
test_command_handler = RotatingFileHandler('test_command.log', maxBytes=5*1024*1024, backupCount=3)
test_command_handler.setLevel(logging.INFO)
test_command_handler.setFormatter(formatter)
logger_test_command.addHandler(test_command_handler)

# Logger para provedor_test
logger_provedor_test = logging.getLogger('provedor_test_logger')
provedor_test_handler = RotatingFileHandler('provedor_test.log', maxBytes=5*1024*1024, backupCount=3)
provedor_test_handler.setLevel(logging.INFO)
provedor_test_handler.setFormatter(formatter)
logger_provedor_test.addHandler(provedor_test_handler)

# Logger para proxy
logger_proxy = logging.getLogger('proxy_logger')
proxy_handler = RotatingFileHandler('proxy.log', maxBytes=5*1024*1024, backupCount=3)
proxy_handler.setLevel(logging.INFO)
proxy_handler.setFormatter(formatter)
logger_proxy.addHandler(proxy_handler)

class ButtonManager:
    def __init__(self, master):
        self.master = master
        self.command_timeout = 5  # Timeout em segundos
        self.script_finished = False  # Inicializa a variável de controle para o término do script
        self.monitor_xray = False # Variável para rastrear o estado do monitoramento do Xray JOGO
        self.botao_monitorar_xray = True  # Variável para rastrear o estado do botão monitoramento do Xray JOGO
        self.verificar_vm = True  # Variável que controla a verificação das VMs
        self.ping_forever = True # Variavel para ligar/desligar testes de ping.
        self.criar_usuario_ssh = True # Variavel para definir se cria ou não o usuario ssh no OMR
        self.execute_initial_test=True # Variavel para definir se o teste inicial de ping do omr vpn/jogo será executado ou não
        self.ping_provedor = threading.Event() # Variavel para executar o teste de ping nas interfaces de cada provedor
        self.stop_ping_provedor = threading.Event() # Variavel para parar o teste de ping nas interfaces de cada provedor
        self.connection_established_ssh_omr_vpn = threading.Event()  # Evento para sinalizar conexão estabelecida
        self.connection_established_ssh_omr_jogo = threading.Event() # Evento para sinalizar conexão estabelecida
        self.connection_established_ssh_vps_vpn = threading.Event() # Evento para sinalizar conexão estabelecida
        self.connection_established_ssh_vps_jogo = threading.Event() # Evento para sinalizar conexão estabelecida
        self.connection_established_ssh_vps_vpn_bind = threading.Event() # Evento para sinalizar conexão estabelecida
        self.connection_established_ssh_vps_jogo_bind = threading.Event() # Evento para sinalizar conexão estabelecida
        self.stop_event_ssh = threading.Event()
        self.stop_event_proxy = threading.Event()
        self.transport_lock = threading.Lock()
        self.transport = None
        self.thread = None
        self.buttons = []
        self.button_frame = None
        self.second_tab_button_frame = None
        self.button_counter = 1  # Inicializa o contador de botões
        self.load_window_position()
        self.load_initial_test()  # Carregar a configuração do arquivo config.ini ao inicializar

        self.clear_log_file('app.log')  # Limpa o arquivo de log ao iniciar o programa
        self.clear_log_file('test_command.log')  # Limpa o arquivo de log ao iniciar o programa
        self.clear_log_file('provedor_test.log')  # Limpa o arquivo de log ao iniciar o programa
        self.clear_log_file('proxy.log')  # Limpa o arquivo de log ao iniciar o programa

        # Verifica e cria o arquivo de configuração se não existir
        self.config_file = 'config.ini'
        self.config = configparser.ConfigParser()
        if not os.path.isfile(self.config_file):
            self.create_default_config()

        # Verifica se o Bitvise e o VirtualBox estão instalados
        if not self.check_software_installation():
            return  # Interrompe a execução do restante do __init__ se a checagem falhar

        # Carregar as configurações ssh do arquivo ini
        self.load_ssh_configurations()
        
        self.ssh_client = None  # Inicializa ssh_client aqui
  
        #Carrega nome das VMs
        self.vm_config_file = "vm_config.json"  # Caminho para o arquivo JSON
        self.vm_names = {
            "vpn": "OpenMPTCP_OCI",
            "jogo": "OpenMPTCP"
        }
        self.create_widgets()
        self.load_buttons()
        self.load_color_map()  # Carrega o mapeamento de cores
        self.top = None
        
        # Cria menu
        self.create_menu_button()
        self.url_to_ping_vps_jogo = None
        self.url_to_ping_vps_vpn = None
        self.load_addresses()
        
        # Executa a checagem de scheduler ao selecionar a aba.
        #self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)
        
        # Inicia as threads de ping se os endereços estiverem configurados
        if (self.url_to_ping_vps_jogo and self.url_to_ping_vps_vpn and 
            self.url_to_ping_omr_vpn and self.url_to_ping_omr_jogo):
            self.start_pinging_threads()
        else:
            messagebox.showinfo("Info", "Por favor, configure todos os endereços de ping nas opções.")

        # Criação de um evento para capturar quando a janela for minimizada
        self.master.bind("<Unmap>", self.on_minimize)

        # Carregar o ícone da bandeja (substitua pelo seu caminho da imagem)
        self.icon_image = Image.open("omr-logo.png")  # Carrega a imagem "omr-logo.png"

        # Criar o ícone da bandeja usando TrayMenu em vez de Menu
        self.tray_icon = Icon("MeuApp", self.icon_image, menu=TrayMenu(
            MenuItem('Restaurar', self.restore_window),
            MenuItem('Sair', self.on_close)
        ))

        # Iniciar o ícone da bandeja em uma thread separada
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

        # Definir o comportamento ao clicar com o botão esquerdo no ícone da bandeja
        self.tray_icon.on_left_click = self.restore_window  # Restaurar janela ao clicar no ícone
        
        # Configura o tratamento para fechar a janela
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        # Cria a pasta de imagens se não existir
        if not os.path.exists('imagens'):
            os.makedirs('imagens')

        # Cria a pasta de chaves ssh se não existir
        if not os.path.exists('ssh_keys'):
            os.makedirs('ssh_keys')

# FUNÇÃO PARA MINIMIZAR E RESTAURAR O PROGRAMA NO SYSTEM TRAY
    def on_minimize(self, event):
        """Captura o evento de minimizar a janela."""
        if self.master.state() == "iconic":  # Verifica se a janela foi minimizada
            self.minimize_to_tray()

    def minimize_to_tray(self):
        """Minimiza o aplicativo para a bandeja do sistema."""
        self.master.withdraw()  # Oculta a janela principal

    def restore_window(self, icon=None, item=None):
        """Restaura a janela principal."""
        self.master.deiconify()  # Restaura a janela principal
        self.master.lift()  # Traz a janela para o topo

            
#FUNÇÃO RELACIONADAS A ARQUIVO .INI
    # Função para ler e criar o arquivo ini
    def create_default_config(self):
        """Cria um arquivo de configuração com valores padrão."""
        # Adiciona a seção 'ssh_vpn'
        self.config.add_section('ssh_vpn')
        self.config.set('ssh_vpn', 'host', '')
        self.config.set('ssh_vpn', 'username', '')
        self.config.set('ssh_vpn', 'password', '')
        self.config.set('ssh_vpn', 'port', '')

        # Adiciona a seção 'ssh_jogo'
        self.config.add_section('ssh_jogo')
        self.config.set('ssh_jogo', 'host', '')
        self.config.set('ssh_jogo', 'username', '')
        self.config.set('ssh_jogo', 'password', '')
        self.config.set('ssh_jogo', 'port', '')

        # Adiciona a seção 'ssh_vps_vpn'
        self.config.add_section('ssh_vps_vpn')
        self.config.set('ssh_vps_vpn', 'host', '')
        self.config.set('ssh_vps_vpn', 'username', '')
        self.config.set('ssh_vps_vpn', 'password', '')
        self.config.set('ssh_vps_vpn', 'port', '')

        # Adiciona a seção 'ssh_vps_jogo'
        self.config.add_section('ssh_vps_jogo')
        self.config.set('ssh_vps_jogo', 'host', '')
        self.config.set('ssh_vps_jogo', 'username', '')
        self.config.set('ssh_vps_jogo', 'password', '')
        self.config.set('ssh_vps_jogo', 'port', '')

        # Adiciona a seção 'ssh_vps_vpn_bind'
        self.config.add_section('ssh_vps_vpn_bind')
        self.config.set('ssh_vps_vpn_bind', 'host', '')
        self.config.set('ssh_vps_vpn_bind', 'username', '')
        self.config.set('ssh_vps_vpn_bind', 'password', '')
        self.config.set('ssh_vps_vpn_bind', 'port', '')

        # Adiciona a seção 'ssh_vps_jogo_bind'
        self.config.add_section('ssh_vps_jogo_bind')
        self.config.set('ssh_vps_jogo_bind', 'host', '')
        self.config.set('ssh_vps_jogo_bind', 'username', '')
        self.config.set('ssh_vps_jogo_bind', 'password', '')
        self.config.set('ssh_vps_jogo_bind', 'port', '')

        # Adiciona a seção 'general' para configurações gerais
        self.config.add_section('general')
        self.config.set('general', 'criar_usuario_ssh', str(self.criar_usuario_ssh))

        # Grava as configurações no arquivo
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

    def load_general_config(self):
        """Carrega configurações gerais do arquivo .ini."""
        self.config.read(self.config_file)
        self.criar_usuario_ssh = self.config.getboolean('general', 'criar_usuario_ssh', fallback=False)
        self.test_provedor_url = self.config.get('general', 'test_provedor_url', fallback="")

    def save_general_config(self):
        """Salva configurações gerais no arquivo .ini."""
        self.config.set('general', 'criar_usuario_ssh', str(self.criar_usuario_ssh))
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

    def load_ssh_configurations(self):
        # Recarrega as configurações de SSH para vpn e jogo
        self.config.read(self.config_file)
        self.ssh_vpn_config = {
            'host': self.config.get('ssh_vpn', 'host', fallback=''),
            'username': self.config.get('ssh_vpn', 'username', fallback=''),
            'password': self.config.get('ssh_vpn', 'password', fallback=''),
            'port': self.config.get('ssh_vpn', 'port', fallback='')
        }
        self.ssh_jogo_config = {
            'host': self.config.get('ssh_jogo', 'host', fallback=''),
            'username': self.config.get('ssh_jogo', 'username', fallback=''),
            'password': self.config.get('ssh_jogo', 'password', fallback=''),
            'port': self.config.get('ssh_jogo', 'port', fallback='')
        }
        self.ssh_vps_vpn_config = {
            'host': self.config.get('ssh_vps_vpn', 'host', fallback=''),
            'username': self.config.get('ssh_vps_vpn', 'username', fallback=''),
            'password': self.config.get('ssh_vps_vpn', 'password', fallback=''),
            'port': self.config.get('ssh_vps_vpn', 'port', fallback='')
        }
        self.ssh_vps_jogo_config = {
            'host': self.config.get('ssh_vps_jogo', 'host', fallback=''),
            'username': self.config.get('ssh_vps_jogo', 'username', fallback=''),
            'password': self.config.get('ssh_vps_jogo', 'password', fallback=''),
            'port': self.config.get('ssh_vps_jogo', 'port', fallback='')
        }
        self.ssh_vps_vpn_bind_config = {
            'host': self.config.get('ssh_vps_vpn_bind', 'host', fallback=''),
            'username': self.config.get('ssh_vps_vpn_bind', 'username', fallback=''),
            'password': self.config.get('ssh_vps_vpn_bind', 'password', fallback=''),
            'port': self.config.get('ssh_vps_vpn_bind', 'port', fallback='')
        }
        self.ssh_vps_jogo_bind_config = {
            'host': self.config.get('ssh_vps_jogo_bind', 'host', fallback=''),
            'username': self.config.get('ssh_vps_jogo_bind', 'username', fallback=''),
            'password': self.config.get('ssh_vps_jogo_bind', 'password', fallback=''),
            'port': self.config.get('ssh_vps_jogo_bind', 'port', fallback='')
        }
        self.load_general_config()  # Carrega as configurações gerais

        print("Configurações de SSH recarregadas com sucesso.")

# FUNÇÃO PARA VERIFICA INSTALAÇÃO DE PROGRAMAS NECESSARIOS PARA O FUNCIONAMENTO DO SISTEMA
    def check_software_installation(self):
        """Verifica se o VirtualBox está instalado no sistema."""
        virtualbox_installed = self.is_program_installed("VirtualBox.exe", check_registry=True)
        
        if not virtualbox_installed:
            msg = "O VirtualBox não está instalado. Por favor, instale-o para continuar."
            if messagebox.askokcancel("Programa faltando", msg, icon="warning"):
                self.master.destroy()  # Fecha a janela principal, encerrando o programa
                return False  # Retorna False para indicar falha na checagem
        
        return True  # Retorna True para indicar que a checagem foi bem-sucedida

    def is_program_installed(self, program_name, check_registry=False):
        """Verifica se um programa está instalado, buscando pelo nome do executável ou no registro."""
        if check_registry:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Oracle\VirtualBox")
                values = []
                i = 0
                while True:
                    try:
                        value = winreg.EnumValue(key, i)
                        values.append(value)
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
                print("Valores na chave de registro do VirtualBox:")
                for v in values:
                    print(v)
                # Retorna verdadeiro se encontrou a chave, o que indica que o VirtualBox está instalado
                return True
            except FileNotFoundError:
                return False

        # Verifica nos diretórios do PATH
        for path in os.environ["PATH"].split(os.pathsep):
            full_path = os.path.join(path, program_name)
            if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                return True
        
        return False

# LOGICA PARA CARREGAR VALOR DE TESTE INICIAL DE PING DO OMR VPN/JOGO
    def load_initial_test(self):
        # Método para carregar a configuração de execute_initial_test do arquivo config.ini
        config = configparser.ConfigParser()
        config.read('config.ini')

        # Se a seção 'general' e a opção 'execute_initial_test' existirem no arquivo, carrega o valor
        if config.has_section('general') and config.has_option('general', 'execute_initial_test'):
            self.execute_initial_test = config.getboolean('general', 'execute_initial_test')
        else:
            # Caso contrário, assume o valor padrão (True)
            self.execute_initial_test = True

        print(f"Configuração carregada: execute_initial_test = {self.execute_initial_test}")

    def set_execute_initial_test(self, value):
        # Método para atualizar o valor de execute_initial_test
        self.execute_initial_test = value
        print(f"execute_initial_test atualizado para: {self.execute_initial_test}")
         
    # Cria um botão de menu no canto superior esquerdo
    def create_menu_button(self):
        menu_bar = tk.Menu(self.master)
        self.master.config(menu=menu_bar)

        # Menu de Configurações
        config_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Configurações", menu=config_menu)
        config_menu.add_command(label="Configurações do Gerenciador de VPS", command=self.open_omr_manager)
        config_menu.add_command(label="Configurações de Cores", command=self.open_color_config)
        config_menu.add_command(label="Ajuda", command=self.abrir_arquivo_ajuda)
        config_menu.add_command(label="Sobre", command=self.about)

        # Novo Menu "Gerenciar Conexões"
        connections_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Gerenciar Conexões", menu=connections_menu)
        connections_menu.add_command(label="Reconectar ssh OMR VPN", command=self.reconectar_omr_vpn)
        connections_menu.add_command(label="Reconectar ssh OMR JOGO", command=self.reconectar_omr_jogo)
        connections_menu.add_command(label="Reconectar ssh VPS VPN", command=self.reconectar_vps_vpn)
        connections_menu.add_command(label="Reconectar ssh VPS JOGO", command=self.reconectar_vps_jogo)
        connections_menu.add_command(label="Reconectar ssh via VPS VPN", command=self.reconectar_vps_vpn_bind)
        connections_menu.add_command(label="Reconectar ssh via VPS JOGO", command=self.reconectar_vps_jogo_bind)

    # Reconecta OMR VPN
    def reconectar_omr_vpn(self):
        self.ssh_vpn_client.close()
        self.update_all_statuses_offline()
        self.ping_provedor.clear()
        self.stop_ping_provedor.set()
        self.ssh_vpn_client = None
        self.connection_established_ssh_omr_vpn.clear()

    # Reconecta OMR JOGO
    def reconectar_omr_jogo(self):
        self.ssh_jogo_client.close()
        self.ssh_jogo_client = None
        self.connection_established_ssh_omr_jogo.clear()

    # Reconecta VPS VPN
    def reconectar_vps_vpn(self):
        self.ssh_vps_vpn_client.close()
        self.ssh_vps_vpn_client = None
        self.connection_established_ssh_vps_vpn.clear()

    # Reconecta VPS Jogo
    def reconectar_vps_jogo(self):
        self.ssh_vps_jogo_client.close()
        self.ping_provedor.clear()
        self.stop_ping_provedor.set()
        self.ssh_vps_jogo_client = None
        self.connection_established_ssh_vps_jogo.clear()

    # Reconecta VPS VPN Bind
    def reconectar_vps_vpn_bind(self):
        self.ssh_vps_vpn_bind_client.close()
        self.ssh_vps_vpn_bind_client = None
        self.connection_established_ssh_vps_vpn_bind.clear()
        self.master.after(1000, lambda: threading.Thread(target=self.establish_ssh_vps_vpn_bind_connection).start())

    # Reconecta VPS Jogo Bind
    def reconectar_vps_jogo_bind(self):
        self.ssh_vps_jogo_bind_client.close()
        self.ssh_vps_jogo_bind_client = None
        self.connection_established_ssh_vps_jogo_bind.clear()
        self.master.after(1000, lambda: threading.Thread(target=self.establish_ssh_vps_jogo_bind_connection).start())

    def abrir_arquivo_ajuda (self):
        caminho_arquivo_ajuda = os.path.abspath("Ajuda.chm")
        if os.path.exists(caminho_arquivo_ajuda):
            ctypes.windll.shell32.ShellExecuteW(None, "open", caminho_arquivo_ajuda, None, None, 1)
        else:
            print("Arquivo de ajuda não encontrado.")

    def options_address(self):
        dialog = open_options_address(self.master)
        self.master.wait_window(dialog.top)

    def about(self):
        dialog = about(self.master)
        self.master.wait_window(dialog.top)

    def open_omr_manager(self):
        dialog = OMRManagerDialog(self.master, self)  # Passa a instância de ButtonManager para OMRManagerDialog
        self.master.wait_window(dialog.top)  # Espera até que a janela de diálogo seja fechada

    def set_execute_initial_test(self, value):
        # Método para atualizar o valor de execute_initial_test
        self.execute_initial_test = value
        print(f"execute_initial_test atualizado para: {self.execute_initial_test}")

    def open_color_config(self):
        dialog = ConfigDialog(self.master, self.color_map, self.top)
        self.master.wait_window(dialog.top)
        if dialog.updated_color_map:
            self.color_map = dialog.updated_color_map
            self.save_color_map()

    # Mapeamento de valores para cores
    def load_color_map(self):
        if os.path.isfile("color_map.json"):
            with open("color_map.json", "r") as f:
                self.color_map = json.load(f)
        else:
            self.color_map = {}

    def save_color_map(self):
        with open("color_map.json", "w") as f:
            json.dump(self.color_map, f)
   
    def load_window_position(self):
        if os.path.isfile("window_position.json"):
            with open("window_position.json", "r") as f:
                position = json.load(f)
                self.master.geometry("+{}+{}".format(position["x"], position["y"]))

    def save_window_position(self):
        position = {
            "x": self.master.winfo_x(),
            "y": self.master.winfo_y()
        }
        with open("window_position.json", "w") as f:
            json.dump(position, f)

# FUNÇÃO DE ENDERRAMENTO DO PROGRAMA ENCERRANDO OS THREADS E ESPERANDO PARA NÃO CAUSAR NENHUM PROBLEMA.
    def suicidar_temer(self):
        try:
            # Comando para finalizar o processo
            subprocess.run(['taskkill', '/IM', 'Gerenciador de VPS.exe', '/F'], check=True)
            print("Processo 'Gerenciador de VPS.exe' finalizado com sucesso.")
        except subprocess.CalledProcessError:
            print("Falha ao tentar finalizar o processo.")

    def on_close(self):
        self.master.after(100, self.prepare_for_closing)  # Agendar a execução de prepare_for_closing após 100 ms

    def prepare_for_closing(self):
        # Criar e exibir a tela de alerta
        #self.show_closing_alert()

        # Colocar aqui toda chamada de encerramento de threads que estiverem sendo executadas de forma initerrupta e qualquer função a ser chamada no encerramento do programa.
        # Sinaliza para as threads que devem encerrar
        self.ping_forever = False
        self.stop_event_proxy.set()
        self.stop_event_ssh.set()
        self.stop_ping_provedor.set()
        self.stop_pinging_threads()
        self.stop_verificar_vm()
        self.save_window_position()
        self.master.after(1000, self.suicidar_temer)
        self.save_color_map()  # Salva o mapeamento de cores

        # Aguardar 900ms antes de destruir o widget
        self.master.after(900, self.destroy_widget)

    def show_closing_alert(self):
        # Criar uma nova janela para a mensagem de encerramento
        self.alert_window = tk.Toplevel(self.master)
        self.alert_window.title("Encerrando")
        self.alert_window.geometry("200x75")  # Definir o tamanho da janela

        # Carregar a posição salva
        self.load_show_closing_alert_position()

        # Criar um Frame cinza para o rótulo
        frame = tk.Frame(self.alert_window, bg="lightgray", borderwidth=2)
        frame.pack(padx=10, pady=10, expand=True, fill="both")

        # Criar um rótulo para mostrar a mensagem dentro do Frame
        message_label = tk.Label(frame, text="Encerrando, aguarde...", padx=20, pady=20, bg="lightgray")
        message_label.pack(expand=True)

        # Agendar a chamada de salvar a posição e fechar a janela
        self.alert_window.after(1900, self.save_and_close_alert_window)

    def load_show_closing_alert_position(self):
        if os.path.isfile("show_closing_alert_position.json"):
            with open("show_closing_alert_position.json", "r") as f:
                position = json.load(f)
                self.alert_window.geometry("+{}+{}".format(position["x"], position["y"]))

    def save_and_close_alert_window(self):
        # Salvar a posição da janela e depois fechar a janela de alerta
        self.save_alert_window_position()
        self.alert_window.destroy()

    def save_alert_window_position(self):
        if hasattr(self, 'alert_window') and self.alert_window is not None:
            position = {
                "x": self.alert_window.winfo_x(),
                "y": self.alert_window.winfo_y()
            }
            with open("show_closing_alert_position.json", "w") as f:
                json.dump(position, f)

    def destroy_widget(self):
        self.tray_icon.stop()
        self.master.destroy()

# FUNÇÃO PARA ENCONTRAR A LETRA DA UNIDADE ONDE O PROGRAMA SE ENCONTRA E UTILIZAR NAS FUNÇÕES DO MESMO.
    def get_executable_dir(self):
        """Obtém o diretório onde o executável ou script está localizado."""
        if getattr(sys, 'frozen', False):
            # Se o script está sendo executado a partir de um pacote PyInstaller
            return os.path.dirname(os.path.abspath(sys.executable))
        else:
            # Se o script está sendo executado diretamente
            return os.path.dirname(os.path.abspath(__file__))

    def get_drive_letter(self):
        """Retorna a letra da unidade onde o script está sendo executado."""
        if getattr(sys, 'frozen', False):  # Verifica se o código está congelado/compilado
            script_path = os.path.abspath(sys.executable)
        else:
            script_path = os.path.abspath(__file__)
        drive_letter = os.path.splitdrive(script_path)[0]
        return drive_letter

    def os_letter(self, relative_path):
        """Constrói o caminho absoluto a partir de um caminho relativo."""
        drive_letter = self.get_drive_letter()
        # Se o caminho relativo já inclui uma unidade (letra de drive), não substituímos
        if os.path.splitdrive(relative_path)[0]:
            return os.path.abspath(relative_path)
        else:
            # Garantir que a barra invertida seja adicionada após a letra da unidade
            return os.path.join(drive_letter + os.sep, relative_path)

    def abrir_arquivo_vps_jogo(self):
        # Função para abrir o bitvise do VPS JOGO
        relative_path = r"Dropbox Compartilhado\AmazonWS\Google Debian 5.4 Instance 3\OpenMPTCP.tlp"  # Substitua pelo caminho relativo do seu arquivo
        filepath = self.os_letter(relative_path)
        if os.path.exists(filepath):
            subprocess.Popen(['start', '', filepath], shell=True)  # Abre o arquivo no sistema operacional padrão
        else:
            print(f"Arquivo não encontrado: {filepath}")

    def abrir_arquivo_vps_vpn(self):
        # Função para abrir o bitvise do VPS VPN
        relative_path = r"Dropbox Compartilhado\AmazonWS\Oracle Ubuntu 22.04 Instance 2\OpenMPTCP.tlp"  # Substitua pelo caminho relativo do seu arquivo
        filepath = self.os_letter(relative_path)
        if os.path.exists(filepath):
            subprocess.Popen(['start', '', filepath], shell=True)  # Abre o arquivo no sistema operacional padrão
        else:
            print(f"Arquivo não encontrado: {filepath}")

    def open_OMR_VPN(self, event=None):
        window = webview.create_window('OMR VPN', 'http://192.168.101.1', width=1045, height=787)
        webview.start(self.submit_login, window)

    def open_OMR_JOGO(self, event=None):
        window = webview.create_window('OMR JOGO', 'http://192.168.100.1', width=1045, height=787)
        webview.start(self.submit_login, window)

    def submit_login(self, window):
        js_code = """
        window.addEventListener('load', function() {
            var form = document.querySelector('form'); // Seleciona o primeiro formulário na página
            if (form) {
                form.submit(); // Submete o formulário
            }
        });
        """
        window.evaluate_js(js_code)

    #def on_tab_change(self, event):
        # Obtemos a aba selecionada
        #current_tab = self.notebook.select()
    
        #if self.notebook.tab(current_tab, "text") == "Scheduler":
            # Executa os comandos apenas quando a aba Scheduler é selecionada
            #self.executar_comandos_scheduler()

    def create_widgets(self):
        # Cria o frame superior
        self.top_frame = tk.Frame(self.master, bg='lightgray', borderwidth=1, relief=tk.RAISED)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)

        # Frame superior que irá conter o label de status geral
        self.general_status_frame = tk.Frame(self.master, bg='red', borderwidth=1, relief=tk.RAISED)
        self.general_status_frame.pack(side=tk.TOP, fill=tk.X)
        self.general_status_label = tk.Label(self.general_status_frame, text="Desconectado", bg='red', fg='black', justify=tk.CENTER)
        self.general_status_label.pack()

        self.top_frame = tk.Frame(self.master, bg='lightgray', borderwidth=1, relief=tk.RAISED)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)

        # Configura o peso das colunas para expandir uniformemente
        self.top_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Label e valor para VPS VPN
        frame_vps_vpn = tk.Frame(self.top_frame, bg='lightgray')
        frame_vps_vpn.grid(row=0, column=1, padx=5, pady=5, sticky=tk.E+tk.W)
        btn_vps_vpn = tk.Button(frame_vps_vpn, text=" VPS  VPN: ", bg='lightgray', justify=tk.CENTER, command=self.abrir_arquivo_vps_vpn, width=9, height=1).pack(side=tk.LEFT)
        self.status_label_vps_vpn = tk.Label(frame_vps_vpn, text="Aguarde...", bg='lightgray', fg='white', justify=tk.CENTER, borderwidth=1, relief=tk.GROOVE, width=9, height=1)
        self.status_label_vps_vpn.pack(side=tk.LEFT, padx=5)

        # Label e valor para VPS JOGO
        frame_vps_jogo = tk.Frame(self.top_frame, bg='lightgray')
        frame_vps_jogo.grid(row=0, column=2, padx=5, pady=5, sticky=tk.E+tk.W)
        btn_vps_jogo = tk.Button(frame_vps_jogo, text=" VPS  JOGO: ", bg='lightgray', justify=tk.CENTER, command=self.abrir_arquivo_vps_jogo, width=9, height=1).pack(side=tk.LEFT)
        self.status_label_vps_jogo = tk.Label(frame_vps_jogo, text="Aguarde...", bg='lightgray', fg='white', justify=tk.CENTER, borderwidth=1, relief=tk.GROOVE, width=9, height=1)
        self.status_label_vps_jogo.pack(side=tk.LEFT, padx=5)

        # Frame para OMR VPN com fundo lightgray
        frame_omr_vpn = tk.Frame(self.top_frame, bg='lightgray')
        frame_omr_vpn.grid(row=1, column=1, padx=5, pady=5, sticky=tk.E+tk.W)
        self.label_omr_vpn = tk.Button(frame_omr_vpn, text="OMR VPN:", bg='lightgray', justify=tk.CENTER, borderwidth=2, relief=tk.RAISED, command=self.show_omr_vpn_menu, width=9, height=1)
        self.label_omr_vpn.pack(side=tk.LEFT)
        self.status_label_omr_vpn = tk.Label(frame_omr_vpn, text="Aguarde...", bg='lightgray', fg='white', justify=tk.CENTER, borderwidth=1, relief=tk.GROOVE, width=9, height=1)
        self.status_label_omr_vpn.pack(side=tk.LEFT, padx=5)

        # Frame para OMR JOGO com fundo lightgray
        frame_omr_jogo = tk.Frame(self.top_frame, bg='lightgray')
        frame_omr_jogo.grid(row=1, column=2, padx=5, pady=5, sticky=tk.E+tk.W)
        self.label_omr_jogo = tk.Button(frame_omr_jogo, text="OMR JOGO:", bg='lightgray', justify=tk.CENTER, borderwidth=2, relief=tk.RAISED, command=self.show_omr_jogo_menu, width=9, height=1)
        self.label_omr_jogo.pack(side=tk.LEFT)
        self.status_label_omr_jogo = tk.Label(frame_omr_jogo, text="Aguarde...", bg='lightgray', fg='white', justify=tk.CENTER, borderwidth=1, relief=tk.GROOVE, width=9, height=1)
        self.status_label_omr_jogo.pack(side=tk.LEFT, padx=5)

        # Frame para VM VPN com fundo lightgray
        frame_vm_vpn = tk.Frame(self.top_frame, bg='lightgray')
        frame_vm_vpn.grid(row=2, column=1, padx=5, pady=5, sticky=tk.E+tk.W)
        self.label_vm_vpn = tk.Button(frame_vm_vpn, text="VM VPN:", bg='lightgray', justify=tk.CENTER, borderwidth=2, relief=tk.RAISED, command=self.show_vm_vpn_menu, width=9, height=1)
        self.label_vm_vpn.pack(side=tk.LEFT)
        self.value_vm_vpn = tk.Label(frame_vm_vpn, text="Aguarde...", bg='lightgray', justify=tk.CENTER)
        self.value_vm_vpn.pack(side=tk.LEFT, padx=5)

        # Frame para VM JOGO com fundo lightgray
        frame_vm_jogo = tk.Frame(self.top_frame, bg='lightgray')
        frame_vm_jogo.grid(row=2, column=2, padx=5, pady=5, sticky=tk.E+tk.W)
        self.label_vm_jogo = tk.Button(frame_vm_jogo, text="VM JOGO:", bg='lightgray', justify=tk.CENTER, borderwidth=2, relief=tk.RAISED, command=self.show_vm_jogo_menu, width=9, height=1)
        self.label_vm_jogo.pack(side=tk.LEFT)
        self.value_vm_jogo = tk.Label(frame_vm_jogo, text="Aguarde...", bg='lightgray', justify=tk.CENTER)
        self.value_vm_jogo.pack(side=tk.LEFT, padx=5)

        # Carregar os nomes da VMs e iniciar a atualização dos valores das VMs
        self.load_vm_names()
        self.update_vm_status()

        # Frame de status
        self.status_frame = tk.Frame(self.master, bg='lightgray', borderwidth=1, relief=tk.RAISED)
        self.status_frame.pack(side=tk.TOP, fill=tk.X)

        # Configura o peso das colunas para expandir uniformemente
        self.status_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Botão para Unifique
        self.unifique_status = tk.Button(self.status_frame, text="UNIFIQUE: Offline", bg='red', fg='black', justify=tk.CENTER, borderwidth=1, relief=tk.SOLID, command=self.test_unifique)
        self.unifique_status.grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        # Ping para Unifique
        self.unifique_status_label = tk.Label(self.status_frame, text="--", bg='lightgray')
        self.unifique_status_label.grid(row=1, column=0, padx=5, pady=0, sticky=tk.N)

        # Botão para Claro
        self.claro_status = tk.Button(self.status_frame, text="CLARO: Offline", bg='red', fg='black', justify=tk.CENTER, borderwidth=1, relief=tk.SOLID, command=self.test_claro)
        self.claro_status.grid(row=0, column=1, padx=5, pady=2, sticky=tk.W)
        # Ping para Claro
        self.claro_status_label = tk.Label(self.status_frame, text="--", bg='lightgray')
        self.claro_status_label.grid(row=1, column=1, padx=5, pady=0, sticky=tk.N)

        # Botão para Coopera
        self.coopera_status = tk.Button(self.status_frame, text="COOPERA: Offline", bg='red', fg='black', justify=tk.CENTER, borderwidth=1, relief=tk.SOLID, command=self.test_coopera)
        self.coopera_status.grid(row=0, column=2, padx=5, pady=2, sticky=tk.W)
        # Ping para Cooper
        self.coopera_status_label = tk.Label(self.status_frame, text="--", bg='lightgray')
        self.coopera_status_label.grid(row=1, column=2, padx=5, pady=0, sticky=tk.N)

        # Inicia a atualização do status das conexões SSH com atraso
        self.master.after(1000, lambda: threading.Thread(target=self.establish_ssh_vpn_connection).start())
        self.master.after(2000, lambda: threading.Thread(target=self.establish_ssh_jogo_connection).start())
        self.master.after(3000, lambda: threading.Thread(target=self.establish_ssh_vps_vpn_connection).start())
        self.master.after(4000, lambda: threading.Thread(target=self.establish_ssh_vps_jogo_connection).start())
        self.master.after(5000, lambda: threading.Thread(target=self.establish_ssh_vps_vpn_bind_connection).start())
        self.master.after(6000, lambda: threading.Thread(target=self.establish_ssh_vps_jogo_bind_connection).start())

        # Cria o Notebook
        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(expand=1, fill='both')

        # Cria a primeira aba
        self.tab1 = tk.Frame(self.notebook)
        self.notebook.add(self.tab1, text="VPS")

        # Cria a segunda aba
        self.tab2 = tk.Frame(self.notebook)
        self.notebook.add(self.tab2, text="OMR")

        # Adicionar a terceira aba ao Notebook
        self.tab3 = tk.Frame(self.notebook)
        self.notebook.add(self.tab3, text="Scheduler")

        # Configuração da primeira aba (botões existentes)
        self.button_frame = tk.Frame(self.tab1, borderwidth=2, relief=tk.SUNKEN)
        self.button_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.bottom_frame = tk.Frame(self.tab1, borderwidth=2, relief=tk.RAISED)
        self.bottom_frame.pack(side=tk.BOTTOM)

        self.folder_menu_button = tk.Menubutton(self.bottom_frame, text="Abrir Pasta", relief=tk.RAISED)
        self.folder_menu_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.folder_menu = tk.Menu(self.folder_menu_button, tearoff=0)
        self.folder_menu_button.config(menu=self.folder_menu)

        self.folder_menu.add_command(label="Pasta VPS", command=lambda: self.open_folder(self.os_letter("Dropbox Compartilhado/AmazonWS")))
        self.folder_menu.add_command(label="Pasta VMs", command=lambda: self.open_folder(self.os_letter("Maquinas Virtuais/Virtual Box Machines")))

        self.cmd_button = tk.Button(self.bottom_frame, text="Conectar M2", command=self.open_useall)
        self.cmd_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.add_button_button = tk.Button(self.bottom_frame, text="Adicionar Servidor", command=self.add_new_button)
        self.add_button_button.pack(side=tk.LEFT, padx=5, pady=5)

        # Configuração da segunda aba (novos botões)
        self.second_tab_button_frame = tk.Frame(self.tab2, borderwidth=2, relief=tk.SUNKEN)
        self.second_tab_button_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.bottom_frame2 = tk.Frame(self.tab2, borderwidth=2, relief=tk.RAISED)
        self.bottom_frame2.pack(side=tk.BOTTOM)

        # Cria o botão de menu na segunda aba
        self.folder_menu_button_tab2 = tk.Menubutton(self.bottom_frame2, text="Abrir Pasta", relief=tk.RAISED)
        self.folder_menu_button_tab2.pack(side=tk.LEFT, padx=5, pady=5)  # Empacota na parte inferior do frame

        # Cria o menu associado ao botão na segunda aba
        self.folder_menu_tab2 = tk.Menu(self.folder_menu_button_tab2, tearoff=0)
        self.folder_menu_button_tab2.config(menu=self.folder_menu_tab2)

        # Adiciona comandos ao menu na segunda aba
        self.folder_menu_tab2.add_command(label="Pasta VPS", command=lambda: self.open_folder(self.os_letter("Dropbox Compartilhado/AmazonWS")))
        self.folder_menu_tab2.add_command(label="Pasta VMs", command=lambda: self.open_folder(self.os_letter("Maquinas Virtuais/Virtual Box Machines")))

        self.cmd_button = tk.Button(self.bottom_frame2, text="Conectar M2", command=self.open_useall)
        self.cmd_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.add_button_button_tab2 = tk.Button(self.bottom_frame2, text="Adicionar OMR", command=self.add_new_button_tab2)
        self.add_button_button_tab2.pack(side=tk.LEFT, padx=5, pady=5)

        # Configuração da terceira aba (Scheduler)
        self.frame_geral = tk.Frame(self.tab3, borderwidth=2, relief=tk.SUNKEN)
        self.frame_geral.pack(padx=10, pady=0, fill=tk.BOTH)

        # Criação do frame no topo da terceira aba
        self.top_frame_vm = tk.Frame(self.tab3, borderwidth=2, relief=tk.RAISED)
        self.top_frame_vm.pack(side=tk.TOP, fill=tk.X)

        self.frame_geral = tk.Frame(self.tab3, borderwidth=2, relief=tk.SUNKEN)
        self.frame_geral.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.frame_vps = tk.Frame(self.frame_geral, borderwidth=2, relief=tk.RAISED)
        self.frame_vps.pack(pady=10)

        self.frame_omr = tk.Frame(self.frame_geral, borderwidth=2, relief=tk.RAISED)
        self.frame_omr.pack(pady=10)

        self.frame_atualizar = tk.Frame(self.frame_geral, borderwidth=2, relief=tk.RAISED)
        self.frame_atualizar.pack(pady=10)

        # Labels e resultados para VPS VPN
        self.frame_vps_vpn = tk.Frame(self.frame_vps, borderwidth=1, relief=tk.SOLID)
        self.frame_vps_vpn.grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        self.label_vps_vpn = tk.Label(self.frame_vps_vpn, text="VPS VPN: Off", fg="red")
        self.label_vps_vpn.pack(anchor=tk.W)
        self.label_vps_vpn_scheduler = tk.Label(self.frame_vps_vpn, text="Scheduler: Aguarde...")
        self.label_vps_vpn_scheduler.pack(anchor=tk.W)
        self.label_vps_vpn_cc = tk.Label(self.frame_vps_vpn, text="CC: Aguarde...")
        self.label_vps_vpn_cc.pack(anchor=tk.W)

        # Labels e resultados para VPS JOGO
        self.frame_vps_jogo = tk.Frame(self.frame_vps, borderwidth=1, relief=tk.SOLID)
        self.frame_vps_jogo.grid(row=0, column=1, padx=10, pady=5, sticky=tk.W)
        self.label_vps_jogo = tk.Label(self.frame_vps_jogo, text="VPS JOGO: Off", fg="red")
        self.label_vps_jogo.pack(anchor=tk.W)
        self.label_vps_jogo_scheduler = tk.Label(self.frame_vps_jogo, text="Scheduler: Aguarde...")
        self.label_vps_jogo_scheduler.pack(anchor=tk.W)
        self.label_vps_jogo_cc = tk.Label(self.frame_vps_jogo, text="CC: Aguarde...")
        self.label_vps_jogo_cc.pack(anchor=tk.W)

        # Labels e resultados para OMR VPN
        self.frame_omr_vpn = tk.Frame(self.frame_omr, borderwidth=1, relief=tk.SOLID)
        self.frame_omr_vpn.grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        self.label_omr_vpn = tk.Label(self.frame_omr_vpn, text="OMR VPN: Off", fg="red")
        self.label_omr_vpn.pack(anchor=tk.W)
        self.label_omr_vpn_scheduler = tk.Label(self.frame_omr_vpn, text="Scheduler: Aguarde...")
        self.label_omr_vpn_scheduler.pack(anchor=tk.W)
        self.label_omr_vpn_cc = tk.Label(self.frame_omr_vpn, text="CC: Aguarde...")
        self.label_omr_vpn_cc.pack(anchor=tk.W)

        # Labels e resultados para OMR JOGO
        self.frame_omr_jogo = tk.Frame(self.frame_omr, borderwidth=1, relief=tk.SOLID)
        self.frame_omr_jogo.grid(row=0, column=1, padx=10, pady=5, sticky=tk.W)
        self.label_omr_jogo = tk.Label(self.frame_omr_jogo, text="OMR JOGO: Off", fg="red")
        self.label_omr_jogo.pack(anchor=tk.W)
        self.label_omr_jogo_scheduler = tk.Label(self.frame_omr_jogo, text="Scheduler: Aguarde...")
        self.label_omr_jogo_scheduler.pack(anchor=tk.W)
        self.label_omr_jogo_cc = tk.Label(self.frame_omr_jogo, text="CC: Aguarde...")
        self.label_omr_jogo_cc.pack(anchor=tk.W)

        # Inicia a verificação periódica dos eventos
        self.update_labels_ssh()

        # Botão para Atualizar Scheduler e CC
        self.botao_atualizar_scheduler = tk.Button(self.frame_atualizar, text="Atualizar Scheduler e CC", command=self.executar_comandos_scheduler)
        self.botao_atualizar_scheduler.grid(row=0, column=0, padx=10, pady=5, sticky='n')

        # Botão para abrir a visualização do log
        self.botao_abrir_logs = tk.Button(self.frame_atualizar, text="Visualizar Logs", command=self.abrir_janela_logs)
        self.botao_abrir_logs.grid(row=2, column=0, padx=10, pady=5, sticky='n')

        # Botão único que alterna entre iniciar e parar
        self.botao_alternar = tk.Button(self.frame_atualizar, text="Iniciar Monitoramento do OMR", command=self.alternar_monitoramento)
        self.botao_alternar.grid(row=1, column=0, padx=10, pady=5, sticky='n')

        # Frame inferior com borda e botões
        self.frame_inferior_scheduler = tk.Frame(self.tab3, borderwidth=2, relief=tk.RAISED)
        self.frame_inferior_scheduler.pack(pady=0, side=tk.BOTTOM)

        # Configurar o frame para que a coluna e a linha sejam ajustadas de acordo com o conteúdo
        self.frame_inferior_scheduler.grid_columnconfigure(0, weight=1)
        self.frame_inferior_scheduler.grid_columnconfigure(1, weight=1)
        self.frame_inferior_scheduler.grid_rowconfigure(0, weight=1)

        # Botão para reiniciar o omr-tracker VPN
        self.botao_reiniciar_vpn_scheduler = tk.Button(self.frame_inferior_scheduler, text="Reiniciar OpenVPN", command=self.reiniciar_glorytun_vpn)
        self.botao_reiniciar_vpn_scheduler.grid(row=0, column=0, padx=10, pady=5, sticky='ew')

        # Botão para reiniciar o omr-tracker JOGO
        self.botao_reiniciar_jogo_scheduler = tk.Button(self.frame_inferior_scheduler, text="Reiniciar Xray JOGO", command=self.reiniciar_xray_jogo)
        self.botao_reiniciar_jogo_scheduler.grid(row=0, column=1, padx=10, pady=5, sticky='ew')

        # Adicionar uma coluna extra para garantir que os botões fiquem centralizados
        self.frame_inferior_scheduler.grid_columnconfigure(2, weight=1)

        # Cria o frame para o rodapé da janela
        self.footer_frame = tk.Frame(self.master, bg='lightgray', borderwidth=1, relief=tk.RAISED)
        self.footer_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Adiciona o label de versão ao rodapé
        self.version_label = tk.Label(self.footer_frame, text="Projeto Temer - ©VempirE_GhosT - Versão: beta 74.5", bg='lightgray', fg='black')
        self.version_label.pack(side=tk.LEFT, padx=0, pady=0)

# METODO PARA MONITORAR O TRAFEGO EM TEMPO REAL DAS INTERFACES
    def show_omr_menu(self, options):
        menu = Menu(self.master, tearoff=0)
        for label, command in options:
            menu.add_command(label=label, command=command)
        menu.post(self.master.winfo_pointerx(), self.master.winfo_pointery())

    def show_omr_vpn_menu(self):
        options = [
            ("Abrir Luci", self.open_OMR_VPN),
            ("Abrir Monitor de Trafego", self.monitor_bmon_vpn)
        ]
        self.show_omr_menu(options)

    def show_omr_jogo_menu(self):
        options = [
            ("Abrir Luci", self.open_OMR_JOGO),
            ("Abrir Monitor de Trafego", self.monitor_bmon_jogo)
        ]
        self.show_omr_menu(options)

    # Abre uma janela para monitorar o tráfego da VPN
    def monitor_bmon_vpn(self):
        self.open_monitor_window(self.ssh_vpn_client, "Trafego OMR VPN")
            # Abre uma janela para monitorar o tráfego do Jogo
    def monitor_bmon_jogo(self):
        self.open_monitor_window(self.ssh_jogo_client, "Trafego OMR JOGO")

    # Função para abrir uma tela de terminal com os dados do bmon para monitorar o trafego de rede.
    def open_monitor_window(self, ssh_client, title):
        # Cria uma nova janela para exibir a saída do bmon
        bmon_window = tk.Toplevel(self.master)

        # Define o título da janela
        bmon_window.title(title)

        # Define o tamanho da janela
        bmon_window.geometry("651x180")

        # Carrega a posição da janela salva, se disponível
        self.load_bmon_position(bmon_window)

        # Cria um Frame para o cabeçalho
        header_frame = tk.Frame(bmon_window, height=50)
        header_frame.pack(fill='x', padx=5, pady=5)

        # Adiciona rótulos no cabeçalho usando grid
        interface_label = tk.Label(header_frame, text="Interface:", anchor='w')
        interface_label.grid(row=0, column=0, padx=5, sticky='w')

        # Adiciona uma coluna extra para o espaçamento do "Download"
        header_frame.grid_columnconfigure(0, weight=1)  # Coluna 0 com peso 1
        header_frame.grid_columnconfigure(1, weight=2)  # Coluna 1 com peso 2 (espaço adicional para deslocamento)
        header_frame.grid_columnconfigure(2, weight=1)  # Coluna 2 com peso 1

        download_label = tk.Label(header_frame, text="Download:", anchor='center')
        download_label.grid(row=0, column=1, padx=5, sticky='n')  # Coluna 1 para deslocar para a direita

        upload_label = tk.Label(header_frame, text="Upload:", anchor='e')
        upload_label.grid(row=0, column=2, padx=5, sticky='e')

        # Configura as colunas para ter uma largura relativa
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=2)  # Aumenta o peso da coluna para o deslocamento
        header_frame.grid_columnconfigure(2, weight=1)

        # Cria um Frame para a área de texto
        text_frame = tk.Frame(bmon_window)
        text_frame.pack(expand=True, fill='both', padx=5, pady=5)

        # Cria um widget Text para exibir a saída
        text_area = tk.Text(text_frame, wrap='word')
        text_area.pack(expand=True, fill='both')

        # Cria um terminal virtual usando pyte
        screen = pyte.Screen(80, 25)
        stream = pyte.Stream(screen)

        def check_bmon(command, ssh_transport):
            session = ssh_transport.open_session()
            session.get_pty()
            session.exec_command(command)
            output = ""
            while True:
                if session.recv_ready():
                    output += session.recv(1024).decode('utf-8')
                if session.exit_status_ready():
                    break
            session.close()
            return output

        def monitor_bmon_in_real_time():
            try:
                # Estabelece uma sessão SSH
                ssh_transport = ssh_client.get_transport()

                # Verifica se o bmon está disponível
                which_output = check_bmon('which bmon', ssh_transport)

                if not which_output.strip():
                    # bmon não encontrado, perguntar se deseja instalar
                    install_bmon = messagebox.askyesno("Instalar bmon", "O bmon não foi encontrado. Deseja instalá-lo?")

                    if install_bmon:
                        text_area.insert(tk.END, "bmon não encontrado. Instalando...\n")

                        # Executa o comando de instalação e captura a saída
                        install_output = check_bmon('opkg update', ssh_transport)
                        text_area.insert(tk.END, f"Saída do opkg update:\n{install_output}\n")

                        time.sleep(5)  # Espera um pouco para garantir que o opkg update seja concluído

                        install_output = check_bmon('opkg install bmon', ssh_transport)
                        text_area.insert(tk.END, f"Saída do opkg install bmon:\n{install_output}\n")

                        text_area.insert(tk.END, "bmon instalado. Reinicie a visualização.\n")
                    else:
                        text_area.insert(tk.END, "Instalação do bmon cancelada.\n")
                    return  # Retorna para sair da função após a instalação ou cancelamento

                # Executa o comando bmon com o caminho absoluto
                while True:
                    session = ssh_transport.open_session()  # Abrir novo canal para o bmon
                    session.get_pty()  # Abre o pseudo-terminal
                    session.exec_command('bmon -o ascii')

                    # Lê a saída em tempo real e atualiza o widget Text
                    while True:
                        if session.recv_ready():
                            output = session.recv(1024).decode('utf-8')
                            stream.feed(output)

                            # Filtra e atualiza o texto
                            filtered_output = ''
                            for line in screen.display:
                                if 'eth' in line:
                                    filtered_output += line + '\n'

                            text_area.delete(1.0, tk.END)
                            text_area.insert(tk.END, filtered_output)
                            text_area.see(tk.END)  # Rola o widget para a linha mais recente
                            text_area.update()

                        if session.exit_status_ready():
                            break

                    session.close()
                    time.sleep(1.1)  # Aguarda um pouco antes de reiniciar o loop

            except Exception as e:
                text_area.insert(tk.END, f"Erro ao executar o bmon: {e}\n")

        # Adiciona a lógica para salvar a posição da janela quando ela for fechada
        bmon_window.protocol("WM_DELETE_WINDOW", lambda: self.on_close_bmon(bmon_window))

        # Executa o monitoramento do bmon em uma thread separada
        threading.Thread(target=monitor_bmon_in_real_time).start()

    def load_bmon_position(self, window):
        if os.path.isfile("bmon_position.json"):
            with open("bmon_position.json", "r") as f:
                position = json.load(f)
                window.geometry("+{}+{}".format(position["x"], position["y"]))

    def save_bmon_position(self, window):
        position = {
            "x": window.winfo_x(),
            "y": window.winfo_y()
        }
        with open("bmon_position.json", "w") as f:
            json.dump(position, f)

    def on_close_bmon(self, window):
        self.save_bmon_position(window)
        window.destroy()

# METODO PARA INICIAR SOCKS5 TCP PARA SER USADO PARA ENCAMINHAR O TRAFEGO PARA O TUNEL MPTCP
    def iniciar_proxy_socks5(self):
        # Verifica se o programa está rodando como executável compilado ou script Python
        if getattr(sys, 'frozen', False):  # Indica que o programa está compilado
            pasta_atual = os.path.dirname(sys.executable)
        else:
            pasta_atual = os.path.dirname(os.path.abspath(__file__))
        
        # Caminho completo para o executável "proxy socks5 tcp.exe"
        caminho_executavel = os.path.join(pasta_atual, 'proxy socks5 tcp.exe')
        
        try:
            # Inicia o programa "proxy socks5 tcp.exe"
            subprocess.Popen([caminho_executavel], shell=True)
            print("Proxy SOCKS5 TCP iniciado com sucesso.")
        except Exception as e:
            print(f"Erro ao iniciar o proxy SOCKS5 TCP: {e}")

# LOGICA PARA ESTABELECER CONEXÕES SSH E UTILIZA-LAS NO PROGRAMA
    def establish_ssh_vpn_connection(self):
        """Estabelece e mantém uma conexão SSH persistente para VPN."""
        self.establish_ssh_connection('vpn')

    def establish_ssh_jogo_connection(self):
        """Estabelece e mantém uma conexão SSH persistente para Jogo."""
        self.establish_ssh_connection('jogo')

    def establish_ssh_vps_vpn_connection(self):
        """Estabelece e mantém uma conexão SSH persistente para VPS VPN."""
        self.establish_ssh_connection('vps_vpn')

    def establish_ssh_vps_jogo_connection(self):
        """Estabelece e mantém uma conexão SSH persistente para VPS Jogo."""
        self.establish_ssh_connection('vps_jogo')

    def establish_ssh_vps_vpn_bind_connection(self, bind_ip='192.168.101.2'):
        """Estabelece e mantém uma conexão SSH persistente via VPS VPN."""
        self.establish_ssh_connection('vps_vpn_bind', bind_ip)

    def establish_ssh_vps_jogo_bind_connection(self, bind_ip='192.168.100.2'):
        """Estabelece e mantém uma conexão SSH persistente via VPS Jogo."""
        self.establish_ssh_connection('vps_jogo_bind', bind_ip)

    def establish_ssh_connection(self, connection_type, bind_ip=None, port_local=None):
        """Estabelece e mantém uma conexão SSH persistente com tentativas de reconexão contínuas."""
        max_retries = 500000
        retry_delay = 5
        attempt = 0

        while not self.stop_event_ssh.is_set():
            # Recarregar configurações antes de tentar conectar
            self.load_ssh_configurations()

            # Seleciona a configuração com base no tipo de conexão
            if connection_type == 'vpn':
                config = self.config['ssh_vpn']
                connection_event = self.connection_established_ssh_omr_vpn
                port_local = config.get('port_local', None)
            elif connection_type == 'jogo':
                config = self.config['ssh_jogo']
                connection_event = self.connection_established_ssh_omr_jogo
                port_local = config.get('port_local', None)
            elif connection_type == 'vps_vpn':
                config = self.config['ssh_vps_vpn']
                connection_event = self.connection_established_ssh_vps_vpn
                port_local = config.get('port_local', None)
            elif connection_type == 'vps_jogo':
                config = self.config['ssh_vps_jogo']
                connection_event = self.connection_established_ssh_vps_jogo
                port_local = config.get('port_local', None)
            elif connection_type == 'vps_vpn_bind':
                config = self.config['ssh_vps_vpn_bind']
                connection_event = self.connection_established_ssh_vps_vpn_bind
                port_local = config.get('port_local', None)
            elif connection_type == 'vps_jogo_bind':
                config = self.config['ssh_vps_jogo_bind']
                connection_event = self.connection_established_ssh_vps_jogo_bind
                port_local = config.get('port_local', None)
            else:
                logger_test_command.error("Tipo de conexão inválido.")
                return

            # Obter a porta da configuração (definir um valor padrão caso não esteja presente)
            port = int(config.get('port', 22))  # Por padrão, usa a porta 22 se não estiver definida

            # Adicionando o teste de conexão na porta definida usando socket
            try:
                if bind_ip:
                    # Cria e vincula o socket ao IP especificado
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.bind((bind_ip, 0))  # Vincula o socket ao IP especificado e a qualquer porta disponível
                    sock.connect((config['host'], port))

                    # Teste de envio de dados ao host
                    test_message = b'ping'  # Mensagem simples de teste
                    sock.sendall(test_message)  # Envia a mensagem para o host

                    # Tenta receber uma resposta (tempo limite de 2 segundos)
                    sock.settimeout(2)
                    response = sock.recv(1024)  # Recebe até 1024 bytes de resposta

                    if response:
                        logger_test_command.info(f"Resposta do host '{config['host']}' recebida na porta {port} com bind IP ({bind_ip}).")
                        sock.close()
                    else:
                        logger_test_command.warning(f"Nenhuma resposta do host '{config['host']}' ao tentar envio de dados na porta {port} com bind IP ({bind_ip}).")
                        sock.close()
                        raise socket.error(f"Sem resposta do host '{config['host']}'.")

                    logger_test_command.info(f"Conexão TCP com bind IP ({bind_ip}) na porta {port} com '{config['host']}' bem-sucedida.")

                else:
                    # Conexão padrão
                    socket_info = socket.getaddrinfo(config['host'], port, socket.AF_INET, socket.SOCK_STREAM)
                    conn = socket.create_connection(socket_info[0][4], timeout=2)

                    # Teste de envio de dados ao host
                    test_message = b'ping'  # Mensagem simples de teste
                    conn.sendall(test_message)  # Envia a mensagem para o host

                    # Tenta receber uma resposta (tempo limite de 2 segundos)
                    conn.settimeout(2)
                    response = conn.recv(1024)  # Recebe até 1024 bytes de resposta

                    if response:
                        logger_test_command.info(f"Resposta do host '{config['host']}' recebida na porta {port} sem bind IP.")
                        conn.close()
                    else:
                        logger_test_command.warning(f"Nenhuma resposta do host '{config['host']}' ao tentar envio de dados na porta {port} sem bind IP.")
                        conn.close()
                        raise socket.error(f"Sem resposta do host '{config['host']}'.")

                    logger_test_command.info(f"Conexão TCP na porta {port} com '{config['host']}' bem-sucedida.")

            except (socket.timeout, socket.error) as e:
                logger_test_command.warning(f"Falha na conexão TCP {'com bind IP' if bind_ip else ''} na porta {port} com '{config['host']}': {e}. Tentando novamente em {retry_delay} segundos...")
                attempt += 1
                if attempt < max_retries:
                    if self.stop_event_ssh.wait(retry_delay):
                        break
                    continue  # Tenta novamente após o tempo de espera
                else:
                    logger_test_command.error(f"Número máximo de tentativas de conexão atingido devido à falha na porta {port} com '{config['host']}'.")
                    connection_event.clear()  # Marca a conexão como falhada
                    if connection_type == 'vpn':
                        self.update_all_statuses_offline()  # Atualiza o status de todas as conexões para offline (somente para VPN)
                    break  # Sai do loop de tentativa de conexão

            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Usar a função para obter o diretório do executável
            exec_dir = self.get_executable_dir()
            key_dir = os.path.join(exec_dir, 'ssh_keys')

            # Verifica se o diretório de chaves existe
            if os.path.isdir(key_dir):
                key_files = [os.path.join(key_dir, f) for f in os.listdir(key_dir) if os.path.isfile(os.path.join(key_dir, f))]
            else:
                logger_test_command.error(f"Diretório de chaves não encontrado: {key_dir}")
                key_files = []

            try:
                if bind_ip:
                    print(f"Attempting to bind socket to IP: {bind_ip}")
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                    try:
                        sock.bind((bind_ip, 0))
                        logger_test_command.info(f"Socket bound to IP {bind_ip}")
                    except Exception as e:
                        logger_test_command.info(f"Failed to bind socket to IP {bind_ip}: {e}")
                        raise

                    sock.connect((config['host'], port))
                    transport = paramiko.Transport(sock)
                    transport.start_client()

                    # Atribuindo transport específico para cada tipo de conexão
                    if connection_type == 'vps_vpn_bind':
                        self.transport_vps_vpn_bind = transport
                    elif connection_type == 'vps_jogo_bind':
                        self.transport_vps_jogo_bind = transport
                    # Você pode adicionar outras opções de conexão aqui...

                    # Tentativa de autenticação com todas as chaves disponíveis
                    if key_files:
                        authenticated = False
                        for key_file in key_files:
                            try:
                                private_key = paramiko.RSAKey(filename=key_file)
                                transport.auth_publickey(config['username'], private_key)
                                logger_test_command.info(f"Autenticação bem-sucedida com a chave: {key_file}")
                                authenticated = True
                                break  # Sai do loop se a autenticação for bem-sucedida
                            except paramiko.AuthenticationException as e:
                                logger_test_command.warning(f"Falha de autenticação com a chave {key_file}: {e}")
                                continue  # Tenta a próxima chave

                        if not authenticated:
                            logger_test_command.error("Falha de autenticação com todas as chaves. Tentando com senha...")
                            transport.auth_password(config['username'], config['password'], look_for_keys=True)
                    else:
                        # Se não houver arquivos de chave, tenta autenticação com senha diretamente
                        logger_test_command.info("Nenhuma chave encontrada. Tentando autenticação com senha...")
                        transport.auth_password(config['username'], config['password'], look_for_keys=True)

                    logger_test_command.info("Connection established using bound socket.")

                    # Configura keep-alive
                    transport.set_keepalive(30)
                    ssh_client._transport = transport  # Atribua o transporte ao cliente SSH

                else:
                    print(f"Connecting to {config['host']} on port {port} without bind IP")
                    ssh_client.connect(
                        config['host'],
                        port=port,
                        username=config['username'],
                        password=config['password'],
                        key_filename=key_files,
                        look_for_keys=True,
                        allow_agent=True
                    )
                    print("Connection established without binding.")

                # Usar lock para proteger o acesso ao cliente SSH e transporte
                with self.transport_lock:
                    if connection_type == 'vpn':
                        self.iniciar_proxy_socks5()
                        self.ssh_vpn_client = ssh_client
                        self.master.after(1000, self.executar_comandos_scheduler)
                        self.stop_ping_provedor.clear()
                        ping_thread = threading.Thread(target=self.run_vps_vpn_pings)
                        ping_thread.start()
                        self.ping_provedor.set()
                        if hasattr(self, 'update_status_labels'):
                            self.master.after(1000, self.update_status_labels)
                        logger_test_command.info("Conexão SSH (vpn) estabelecida com sucesso iniciando teste das conexões.")
                    elif connection_type == 'jogo':
                        self.ssh_jogo_client = ssh_client
                        self.master.after(1000, self.executar_comandos_scheduler)
                        logger_test_command.info("Conexão SSH (jogo) estabelecida com sucesso.")
                    elif connection_type == 'vps_vpn':
                        self.ssh_vps_vpn_client = ssh_client
                        self.stop_ping_provedor.clear()
                        ping_thread = threading.Thread(target=self.run_vps_vpn_pings)
                        ping_thread.start()
                        self.ping_provedor.set()
                        self.master.after(1000, self.executar_comandos_scheduler)
                        logger_test_command.info("Conexão SSH (vps_vpn) estabelecida com sucesso.")
                    elif connection_type == 'vps_jogo':
                        self.ssh_vps_jogo_client = ssh_client
                        self.stop_ping_provedor.clear()
                        ping_thread = threading.Thread(target=self.run_vps_vpn_pings)
                        ping_thread.start()
                        self.ping_provedor.set()
                        self.master.after(1000, self.executar_comandos_scheduler)
                        logger_test_command.info("Conexão SSH (vps_jogo) estabelecida com sucesso.")
                    elif connection_type == 'vps_vpn_bind':
                        self.ssh_vps_vpn_bind_client = ssh_client
                        logger_test_command.info("Conexão SSH (vps_vpn_bind) estabelecida com sucesso.")
                    elif connection_type == 'vps_jogo_bind':
                        self.ssh_vps_jogo_bind_client = ssh_client
                        logger_test_command.info("Conexão SSH (vps_jogo_bind) estabelecida com sucesso.")

                    # Verifica se `port_local` foi fornecido
                    if port_local:
                        # Verifica o tipo de conexão
                        if connection_type == 'vps_vpn_bind':
                            if self.transport_vps_vpn_bind is None:
                                logger_proxy.error("O transporte SSH (vps_vpn_bind) não foi inicializado corretamente.")
                                return

                            self.transport_vps_vpn_bind.set_keepalive(30)  # Envia pacotes keepalive a cada 30 segundos
                            logger_proxy.info("Keepalive configurado para o transporte SSH (vps_vpn_bind).")

                            logger_proxy.info(f"Iniciando túnel SSH na porta local {port_local} para o tipo de conexão {connection_type}.")
                            # Passa a instância de transporte específica para o SOCKS proxy
                            threading.Thread(target=self.start_socks_proxy, args=(port_local, connection_type, self.transport_vps_vpn_bind)).start()

                        elif connection_type == 'vps_jogo_bind':
                            if self.transport_vps_jogo_bind is None:
                                logger_proxy.error("O transporte SSH (vps_jogo_bind) não foi inicializado corretamente.")
                                return

                            self.transport_vps_jogo_bind.set_keepalive(30)  # Envia pacotes keepalive a cada 30 segundos
                            logger_proxy.info("Keepalive configurado para o transporte SSH (vps_jogo_bind).")

                            logger_proxy.info(f"Iniciando túnel SSH na porta local {port_local} para o tipo de conexão {connection_type}.")
                            # Passa a instância de transporte específica para o SOCKS proxy
                            threading.Thread(target=self.start_socks_proxy, args=(port_local, connection_type, self.transport_vps_jogo_bind)).start()

                        else:
                            self.transport = ssh_client.get_transport()
                            if self.transport is None:
                                logger_proxy.error("O transporte SSH não foi inicializado corretamente.")
                                return

                            self.transport.set_keepalive(30)  # Envia pacotes keepalive a cada 30 segundos
                            logger_proxy.info("Keepalive configurado para o transporte SSH.")

                            logger_proxy.info(f"Iniciando túnel SSH na porta local {port_local} para o tipo de conexão {connection_type}.")
                            # Passa a instância atual de `self.transport` para o SOCKS proxy
                            threading.Thread(target=self.start_socks_proxy, args=(port_local, connection_type, self.transport)).start()

                    connection_event.set()  # Marca a conexão como estabelecida

                connection_event.set()  # Marca a conexão como estabelecida

                # Aguarda até que a conexão seja interrompida ou o programa seja fechado
                while not self.stop_event_ssh.is_set():
                    try:
                        if bind_ip:
                            # Verifica a conexão via Transport
                            logger_test_command.info(f"Verificando conexão SSH via Transport ({connection_type})...")

                            # Loga a instância de self.transport
                            transport = None
                            if connection_type == 'vps_vpn_bind':
                                transport = self.transport_vps_vpn_bind
                            elif connection_type == 'vps_jogo_bind':
                                transport = self.transport_vps_jogo_bind
                            else:
                                transport = self.transport
                            
                            if transport is None:
                                logger_test_command.error(f"Transport para o tipo de conexão {connection_type} não foi inicializado corretamente.")
                                break

                            # Loga o Transport e verifica se contém "unconnected"
                            transport_info = f"Executando comando na conexão SSH (via Transport) com cliente: {transport}"
                            logger_test_command.info(transport_info)
                            
                            if 'unconnected' in transport_info:
                                raise ConnectionError(f"O Transport para o tipo de conexão {connection_type} está desconectado.")

                            def execute_command():
                                nonlocal transport
                                session = transport.open_session()
                                session.exec_command('echo 1')  # Alternativa ao 'ping'
                                
                                # Aguarda resposta ou timeout de 5 segundos
                                ready = select.select([session], [], [], 5)[0]
                                if not ready:
                                    raise TimeoutError("Nenhum retorno do comando dentro do tempo limite.")
                                
                                output = session.recv(1024).decode()
                                if not output:
                                    raise TimeoutError("Nenhum dado recebido após o comando.")
                                
                                #logger_test_command.info(f"Saída do comando: {output}")
                                session.close()

                            # Cria e inicia a thread
                            command_thread = threading.Thread(target=execute_command)
                            command_thread.start()

                            # Aguarda o término da thread ou timeout
                            command_thread.join(timeout=10)
                            if command_thread.is_alive():
                                logger_test_command.error("O comando excedeu o tempo limite de 5 segundos.")
                                # A thread não pode ser interrompida diretamente. Dependendo da lógica, pode-se precisar de um tratamento adicional.

                                # Você pode optar por registrar o erro e continuar o loop ou levantar uma exceção
                                raise TimeoutError("O comando SSH excedeu o tempo limite de 5 segundos.")
                            
                            time.sleep(10)  # Ajuste o intervalo conforme necessário

                        else:
                            # Verifica a conexão via SSHClient
                            logger_test_command.info(f"Verificando conexão SSH ({connection_type})...")

                            # Loga a instância de ssh_client
                            ssh_client = None
                            if connection_type == 'vpn':
                                ssh_client = self.ssh_vpn_client
                            elif connection_type == 'jogo':
                                ssh_client = self.ssh_jogo_client
                            elif connection_type == 'vps_vpn':
                                ssh_client = self.ssh_vps_vpn_client
                            elif connection_type == 'vps_jogo':
                                ssh_client = self.ssh_vps_jogo_client
                            elif connection_type == 'vps_vpn_bind':
                                ssh_client = self.ssh_vps_vpn_bind_client
                            elif connection_type == 'vps_jogo_bind':
                                ssh_client = self.ssh_vps_jogo_bind_client
                            
                            if ssh_client is None:
                                logger_test_command.error(f"SSHClient para o tipo de conexão {connection_type} não foi inicializado corretamente.")
                                break

                            # Loga o SSHClient e verifica se contém "unconnected"
                            ssh_client_info = f"Executando comando na conexão SSH (via SSHClient) com cliente: {ssh_client}"
                            logger_test_command.info(ssh_client_info)
                            
                            if 'unconnected' in ssh_client_info:
                                raise ConnectionError(f"O SSHClient para o tipo de conexão {connection_type} está desconectado.")

                            stdin, stdout, stderr = ssh_client.exec_command('echo 1', timeout=5)  # Alternativa ao 'ping'

                            # Aguarda resposta ou timeout de 5 segundos
                            ready = select.select([stdout.channel], [], [], 5)[0]
                            if not ready:
                                raise TimeoutError("Nenhum retorno do comando dentro do tempo limite.")

                            output = stdout.read(1024).decode()
                            error_output = stderr.read().decode()

                            if not output and not error_output:
                                raise TimeoutError("Nenhum dado recebido após o comando.")

                            #if output:
                                #logger_test_command.info(f"Saída do comando: {output}")
                            if error_output:
                                logger_test_command.error(f"Erro no comando: {error_output}")

                            time.sleep(10)  # Ajuste o intervalo conforme necessário

                    except Exception as e:
                        # Tratamento de exceções e limpeza
                        logger_test_command.error(f"Conexão SSH ({connection_type}) perdida: {e}")

                        if connection_type == 'vpn':
                            self.ssh_vpn_client.close()
                            self.update_all_statuses_offline()
                            self.ping_provedor.clear()
                            self.stop_ping_provedor.set()
                            self.ssh_vpn_client = None
                            self.connection_established_ssh_omr_vpn.clear()
                        elif connection_type == 'jogo':
                            self.ssh_jogo_client.close()
                            self.ssh_jogo_client = None
                            self.connection_established_ssh_omr_jogo.clear()
                        elif connection_type == 'vps_vpn':
                            self.ssh_vps_vpn_client.close()
                            self.ssh_vps_vpn_client = None
                            self.connection_established_ssh_vps_vpn.clear()
                        elif connection_type == 'vps_jogo':
                            self.ssh_vps_jogo_client.close()
                            self.ping_provedor.clear()
                            self.stop_ping_provedor.set()
                            self.ssh_vps_jogo_client = None
                            self.connection_established_ssh_vps_jogo.clear()
                        elif connection_type == 'vps_vpn_bind':
                            self.ssh_vps_vpn_bind_client.close()
                            self.ssh_vps_vpn_bind_client = None
                            self.connection_established_ssh_vps_vpn_bind.clear()
                        elif connection_type == 'vps_jogo_bind':
                            self.ssh_vps_jogo_bind_client.close()
                            self.ssh_vps_jogo_bind_client = None
                            self.connection_established_ssh_vps_jogo_bind.clear()
                        break

            except paramiko.AuthenticationException as e:
                logger_test_command.error(f"Erro de autenticação ao estabelecer conexão SSH ({connection_type}): {e}")
                connection_event.clear()

                if self.criar_usuario_ssh and connection_type in ['vpn', 'jogo']:  # Criar usuário SSH apenas para vpn e jogo
                    try:
                        logger_test_command.info("Tentando criar usuário SSH via root...")
                        # Comando para criar o usuário via SSH como root
                        ssh_cmd = f"echo '{config['username']}:x:0:0:root:/root:/bin/ash' >> /etc/passwd && echo '{config['username']}:{config['password']}' | chpasswd"
                        root_user = "root"
                        ssh_command = f"ssh -o StrictHostKeyChecking=no {root_user}@{config['host']} \"{ssh_cmd}\""
                        subprocess.run(ssh_command, shell=True, check=True)
                        logger_test_command.info("Usuário SSH criado com sucesso.")
                    except subprocess.CalledProcessError as err:
                        logger_test_command.error(f"Falha ao criar o usuário SSH: {err}")
                        break  # Se falhar, sair do loop de tentativa de conexão
                elif connection_type in ['vps_vpn', 'vps_jogo', 'vps_vpn_bind', 'vps_jogo_bind']:
                    logger_test_command.error(f"Falha na conexão com {connection_type}. Verifique os dados de login nas configurações e reinicie o programa.")
                    break  # Sair do loop de tentativa de conexão
                else:
                    logger_test_command.info("A opção Criar usuário SSH automaticamente não está marcada, marque a opção ou crie o usuário manualmente e reinicie o programa.")
                    break  # Sair do loop de tentativa de conexão

            except paramiko.SSHException as e:
                # Captura erros específicos relacionados ao banner SSH
                if "banner" in str(e).lower():
                    logger_test_command.error(f"Erro de banner SSH ao estabelecer conexão ({connection_type}): {e}")
                    
                    # Se a conexão for com bind IP, reinicia o loop para tentar novamente
                    if bind_ip:
                        logger_test_command.warning("Erro de banner SSH detectado em conexão com bind IP. Tentando reconectar...")
                        attempt += 1
                        if attempt < max_retries:
                            if self.stop_event_ssh.wait(retry_delay):
                                break
                            continue  # Retorna ao início do loop de reconexão
                        else:
                            logger_test_command.error("Número máximo de tentativas de conexão atingido devido a erro de banner SSH.")
                            connection_event.clear()  # Marca a conexão como falhada
                            if connection_type == 'vpn':
                                self.update_all_statuses_offline()  # Atualiza o status de todas as conexões para offline (somente para VPN)
                            break  # Sai do loop de tentativa de conexão
                    
                    # Se não for uma conexão com bind IP, interrompe o loop como antes
                    logger_test_command.error("Verifique a configuração da porta SSH nas configurações e corrija o problema.")
                    break  # Sai do loop de tentativa de conexão

            except Exception as e:
                logger_test_command.error(f"Erro ao estabelecer conexão SSH ({connection_type}): {e}")
                attempt += 1
                if attempt < max_retries:
                    logger_test_command.info(f"Tentando novamente em {retry_delay} segundos...")
                    if self.stop_event_ssh.wait(retry_delay):
                        break
                else:
                    logger_test_command.error("Número máximo de tentativas de conexão atingido.")
                    connection_event.clear()
                    if connection_type == 'vpn':
                        self.update_all_statuses_offline()  # Atualiza o status de todas as conexões para offline (somente para VPN)
                    break  # Sai do loop de tentativa de conexão

    def start_socks_proxy(self, port_local, connection_type, transport):
        """Inicia um proxy SOCKS usando a conexão SSH."""
        try:
            # Verifique se o transporte passado como argumento é válido
            if transport is None or not transport.is_active():
                logger_proxy.error("Transport SSH não está disponível ou conexão SSH caiu.")
                return

            logger_proxy.info(f"Transport SSH está disponível e correto: {transport}")

            # Convertendo para inteiro se necessário
            if isinstance(port_local, str):
                try:
                    port_local = int(port_local)
                except ValueError:
                    logger_proxy.error(f"Porta local inválida: {port_local}")
                    return

            if not isinstance(port_local, int):
                logger_proxy.error(f"Porta local deve ser um número inteiro, mas recebeu: {port_local}")
                return

            # Log incluindo o connection_type
            logger_proxy.info(f"Proxy SOCKS iniciado na porta {port_local} para o tipo de conexão {connection_type}.")

            # Cria o servidor SOCKS local
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            server.bind(('0.0.0.0', port_local))
            server.listen(5)

            logger_proxy.info(f"Proxy SOCKS na porta {port_local} está aguardando conexões.")

            while not self.stop_event_proxy.is_set():
                # Verifique se a conexão SSH ainda está ativa
                if not transport.is_active():
                    logger_proxy.error("Conexão SSH caiu, encerrando proxy SOCKS.")
                    break

                try:
                    # Timeout para que accept não bloqueie indefinidamente
                    server.settimeout(1)
                    client_socket, _ = server.accept()
                    logger_proxy.info("Nova conexão SOCKS aceita.")
                    # Passa a instância de transporte específica e o evento de parada para a função de conexão
                    thread = threading.Thread(target=self.handle_socks_connection, args=(client_socket, transport))
                    thread.daemon = True  # Torna a thread daemon para garantir que o processo termine corretamente
                    thread.start()
                except socket.timeout:
                    continue  # Continua o loop, verificando se stop_event_proxy foi setado
                except socket.error as e:
                    logger_proxy.error(f"Erro no servidor SOCKS: {e}")
                    break

        except Exception as e:
            logger_proxy.error(f"Erro ao iniciar o proxy SOCKS: {e}")
        finally:
            # Feche o socket para liberar a porta
            server.close()
            logger_proxy.info(f"Proxy SOCKS na porta {port_local} foi fechado.")
        
    def handle_socks_connection(self, client_socket, transport):
        """Lida com uma conexão SOCKS usando o transporte SSH específico."""
        try:
            if transport is None:
                logger_proxy.error("Transport SSH não está disponível.")
                client_socket.close()
                return

            logger_proxy.info("Transport SSH está disponível durante o manuseio da conexão SOCKS.")

            # Handshake SOCKS5
            handshake = client_socket.recv(2)
            if len(handshake) < 2:
                logger_proxy.warning(f"Handshake incompleto recebido: {handshake}")
                client_socket.close()
                return

            version, n_methods = handshake
            if version != 0x05:
                logger_proxy.warning(f"Versão SOCKS não suportada: {version}")
                client_socket.close()
                return

            methods = client_socket.recv(n_methods)
            client_socket.sendall(b'\x05\x00')

            # Recebe o pedido SOCKS
            request = client_socket.recv(4)
            if len(request) < 4:
                logger_proxy.warning(f"Pedido SOCKS incompleto recebido: {request}")
                client_socket.close()
                return

            version, cmd, reserved, addr_type = request
            if version != 0x05:
                logger_proxy.warning(f"Versão SOCKS não suportada no pedido: {version}")
                client_socket.close()
                return

            # Obtém o endereço de destino
            if addr_type == 0x01:  # IPv4
                addr = socket.inet_ntoa(client_socket.recv(4))
            elif addr_type == 0x03:  # Domínio
                addr_len = client_socket.recv(1)[0]
                addr = client_socket.recv(addr_len).decode()
            elif addr_type == 0x04:  # IPv6
                addr = socket.inet_ntop(socket.AF_INET6, client_socket.recv(16))
            else:
                logger_proxy.warning("Tipo de endereço não suportado.")
                client_socket.close()
                return

            # Recebe a porta de destino
            port = int.from_bytes(client_socket.recv(2), 'big')

            logger_proxy.info(f"Encaminhando para {addr}:{port}")

            # Responde ao cliente SOCKS
            client_socket.sendall(b'\x05\x00\x00\x01' + socket.inet_aton('0.0.0.0') + b'\x00\x00')

            # Estabelece a conexão no túnel SSH
            remote_socket = transport.open_channel('direct-tcpip', (addr, port), client_socket.getpeername())
            if remote_socket is not None:
                logger_proxy.info("Canal SSH aberto com sucesso.")
                # Passa o evento de parada para as threads de encaminhamento de dados
                threading.Thread(target=self.forward_data, args=(client_socket, remote_socket, self.stop_event_proxy)).start()
                threading.Thread(target=self.forward_data, args=(remote_socket, client_socket, self.stop_event_proxy)).start()
            else:
                logger_proxy.error("Falha ao abrir o canal: remote_socket é None")
                client_socket.close()
        except paramiko.SSHException as e:
            logger_proxy.error(f"Falha ao abrir o canal: {e}")
            client_socket.close()
        except Exception as e:
            logger_proxy.error(f"Erro ao lidar com a conexão SOCKS: {e}")
            client_socket.close()

    def forward_data(self, source, destination, stop_event):
        try:
            while not stop_event.is_set():
                data = source.recv(4096)
                if len(data) == 0:
                    print("Nenhum dado recebido, fechando conexão.")
                    break
                destination.send(data)
        except OSError as e:
            print(f"Erro de soquete: {e}")
        except Exception as e:
            print(f"Erro no encaminhamento de dados: {e}")
        finally:
            source.close()
            destination.close()

    def close_ssh_connection(self):
        """Fecha todas as conexões SSH abertas."""
        if hasattr(self, 'ssh_vpn_client') and self.ssh_vpn_client is not None:
            self.ssh_vpn_client.close()
            self.ping_provedor.clear()
            self.stop_ping_provedor.set()
            logger_test_command.info("Conexão SSH (vpn) fechada.")
            self.ssh_vpn_client = None
            self.connection_established_ssh_omr_vpn.clear()

        if hasattr(self, 'ssh_jogo_client') and self.ssh_jogo_client is not None:
            self.ssh_jogo_client.close()
            logger_test_command.info("Conexão SSH (jogo) fechada.")
            self.ssh_jogo_client = None
            self.connection_established_ssh_omr_jogo.clear()

        if hasattr(self, 'ssh_vps_vpn_client') and self.ssh_vps_vpn_client is not None:
            self.ssh_vps_vpn_client.close()
            logger_test_command.info("Conexão SSH (vps_vpn) fechada.")
            self.ssh_vps_vpn_client = None
            self.connection_established_ssh_vps_vpn.clear()

        if hasattr(self, 'ssh_vps_jogo_client') and self.ssh_vps_jogo_client is not None:
            self.ssh_vps_jogo_client.close()
            self.stop_ping_provedor.set()
            self.ping_provedor.clear()
            logger_test_command.info("Conexão SSH (vps_jogo) fechada.")
            self.ssh_vps_jogo_client = None
            self.connection_established_ssh_vps_jogo.clear()
            
        if hasattr(self, 'ssh_vps_vpn_bind_client') and self.ssh_vps_vpn_bind_client is not None:
            self.ssh_vps_vpn_bind_client.close()
            logger_test_command.info("Conexão SSH (vps_vpn_bind) fechada.")
            self.ssh_vps_vpn_bind_client = None
            self.connection_established_ssh_vps_vpn_bind.clear()

        if hasattr(self, 'ssh_vps_jogo_bind_client') and self.ssh_vps_jogo_bind_client is not None:
            self.ssh_vps_jogo_bind_client.close()
            logger_test_command.info("Conexão SSH (vps_jogo_bind) fechada.")
            self.ssh_vps_jogo_bind_client = None
            self.connection_established_ssh_vps_jogo_bind.clear()

# LOGICA PARA TESTAR ESTADO DAS CONEXÕES A INTERNET.
    # Função para ping nas interfaces
    def run_vps_vpn_pings(self):
        """Executa os comandos ping na conexão SSH VPN e atualiza a UI."""

        # Checa se o evento ping_provedor está setado (True)
        if self.ping_provedor.is_set():
            logger_test_command.info("O teste de ping dos provedores já está em execução, parando...")
            return  # Não executa o restante da função

        # Verifica se o host está online antes de continuar
        host = self.ssh_vps_jogo_config['host']
        port = 65222
        timeout = 5

        try:
            # Tenta obter as informações de socket e criar a conexão TCP
            socket_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
            conn = socket.create_connection(socket_info[0][4], timeout=timeout)
            conn.close()
            logger_provedor_test.info(f"Conexão TCP na porta {port} com {host} bem-sucedida.")
        except (OSError, socket.timeout):
            logger_test_command.info(f"Não foi possível conectar ao host {host} na porta {port}. O host pode estar offline.")
            time.sleep(2)  # Aguarda 2 segundos antes de alterar o evento
            self.ping_provedor.clear()  # Limpa o evento para False
            logger_test_command.info("O evento ping_provedor foi definido como False.")  # Log da alteração
            time.sleep(2)  # Aguarda mais 2 segundos
            # Verifica e exibe o estado real do evento
            if not self.ping_provedor.is_set():
                logger_test_command.info(f"O estado final do evento ping_provedor é {self.ping_provedor.is_set()}.")
            return  # Não executa o restante da função

        # Continua com a execução se o evento ping_provedor não estiver setado (False) e o host estiver online
        interfaces = ['eth2', 'eth4', 'eth5']
        labels = [self.unifique_status_label, self.claro_status_label, self.coopera_status_label]

        for interface, label in zip(interfaces, labels):
            self.ping_thread = threading.Thread(target=self.execute_ping_command, args=(interface, label, self.stop_ping_provedor))
            self.ping_thread.start()

    def execute_ping_command(self, interface, label, stop_ping_provedor):
        """Executa o comando ping via SSH indefinidamente e atualiza a label com a latência."""
        if hasattr(self, 'ssh_vpn_client') and self.ssh_vpn_client is not None:
            try:
                # Executa o ping com limite de tempo ou pacotes
                stdin, stdout, stderr = self.ssh_vpn_client.exec_command(f"ping -I {interface} {self.ssh_vps_jogo_config['host']}")
                logger_test_command.info("Ping iniciado com sucesso")

                # Loop para ler as respostas do ping até que o `stop_ping_provedor` seja acionado
                while not stop_ping_provedor.is_set():
                    # Usa select para esperar com timeout
                    if select.select([stdout.channel], [], [], 5)[0]:  # Timeout de 5 segundos
                        line = stdout.readline().strip()  # Lê cada linha de saída do comando
                        if not line:
                            continue

                        # Filtra a latência usando regex
                        match = re.search(r'time=(\d+\.?\d*) ms', line)
                        if match:
                            latency = match.group(1) + " ms"
                        else:
                            latency = "--"

                        # Atualiza a label com a latência ou com traços
                        self.update_ping_result(label, latency)
                    else:
                        logger_test_command.info("Timeout na leitura do ping")
                        break  # Sai do loop se houver timeout na leitura

                # Após a interrupção do teste, define a label para "--"
                self.update_ping_result(label, "--")

            except Exception as e:
                logger_provedor_test.error(f"Falha ao executar ping em {interface}: {e}")
                self.update_ping_result(label, "--")  # Atualiza para "--" em caso de erro
        else:
            logger_provedor_test.error(f"SSH não está conectado para {interface}.")
            self.update_ping_result(label, "--")  # Atualiza para "--" se SSH não estiver conectado

    def update_ping_result(self, label, result):
        """Atualiza o texto da label com o resultado do ping."""
        label.config(text=result)

    # Funções para os botões de teste
    def test_unifique(self):
        """Executa o teste para a conexão UNIFIQUE usando a conexão SSH VPN."""
        if not hasattr(self, 'ssh_vpn_client') or self.ssh_vpn_client is None:
            logger_provedor_test.error("Conexão SSH VPN não está estabelecida para o teste UNIFIQUE.")
            return

        threading.Thread(target=self.check_interface_status, args=('eth2', self.unifique_status, 'UNIFIQUE', self.ssh_vpn_client)).start()

    def test_claro(self):
        """Executa o teste para a conexão CLARO usando a conexão SSH VPN."""
        if not hasattr(self, 'ssh_vpn_client') or self.ssh_vpn_client is None:
            logger_provedor_test.error("Conexão SSH VPN não está estabelecida para o teste CLARO.")
            return

        threading.Thread(target=self.check_interface_status, args=('eth4', self.claro_status, 'CLARO', self.ssh_vpn_client)).start()

    def test_coopera(self):
        """Executa o teste para a conexão COOPERA usando a conexão SSH VPN."""
        if not hasattr(self, 'ssh_vpn_client') or self.ssh_vpn_client is None:
            logger_provedor_test.error("Conexão SSH VPN não está estabelecida para o teste COOPERA.")
            return

        threading.Thread(target=self.check_interface_status, args=('eth5', self.coopera_status, 'COOPERA', self.ssh_vpn_client)).start()

    def run_provedor_test(self, ssh_client, interface, output_queue, test_name):
        """Executa um comando utilizando a conexão SSH estabelecida com um timeout."""
        if ssh_client is None:
            logger_provedor_test.error(f"{test_name}: Conexão SSH não está estabelecida.")
            output_queue.put(None)
            return

        command = f'curl --interface {interface} "{self.test_provedor_url}"'
        logger_provedor_test.info(f"Testando conexão com {test_name} na {interface}: {command}")

        def run_command():
            try:
                stdin, stdout, stderr = ssh_client.exec_command(command)
                output = stdout.read().decode()
                error_output = stderr.read().decode()

                if output:
                    logger_provedor_test.info(f"Teste de conexão com {test_name}: {output}")
                    output_queue.put(output)
                else:
                    logger_provedor_test.error(f"{test_name}: Saída vazia. Erro: {error_output}")
                    output_queue.put(None)
            except Exception as e:
                logger_provedor_test.error(f"{test_name}: Erro ao executar comando: {e}")
                output_queue.put(None)

        # Cria e inicia a thread para executar o comando
        command_thread = threading.Thread(target=run_command)
        command_thread.start()

        # Espera pelo comando com timeout
        command_thread.join(timeout=self.command_timeout)

        # Verifica se a thread ainda está ativa
        if command_thread.is_alive():
            logger_provedor_test.error(f"{test_name}: Timeout na execução do comando.")
            output_queue.put(None)
            # Aqui você pode adicionar qualquer lógica adicional necessária para finalizar a execução, se possível

    def update_all_statuses_offline(self):
        """Atualiza o status de todas as conexões para offline."""
        self.unifique_status.config(text="UNIFIQUE: Offline", bg='red')
        self.claro_status.config(text="CLARO: Offline", bg='red')
        self.coopera_status.config(text="COOPERA: Offline", bg='red')

    def update_status_labels(self):
        """Atualiza os labels a cada 30 segundos, se a conexão SSH estiver estabelecida."""
        # Verifica se a conexão SSH ainda está estabelecida
        if self.connection_established_ssh_omr_vpn.is_set():
            self.check_status()  # Chama o método para atualizar o status
            self.master.after(30000, self.update_status_labels)  # Chama update_status_labels novamente após 30 segundos
        else:
            logger_provedor_test.info("Conexão SSH perdida. Parando a checagem das conexões.")
            self.update_all_statuses_offline()  # Atualiza o status de todas as conexões para offline

    def check_interface_status(self, interface, button, name, ssh_client):
        output_queue = queue.Queue()

        # Executa o comando em uma thread
        threading.Thread(target=self.run_provedor_test, args=(ssh_client, interface, output_queue, name)).start()

        def thread_function():
            try:
                output = output_queue.get()  # Espera até receber o output
                if output is None:
                    logger_provedor_test.error(f"Erro: A saída do comando é None.")
                    self.master.after(0, lambda: button.config(text=f"{name}: Offline", bg='red'))
                    return

                if name.lower() in output.lower():
                    self.master.after(0, lambda: button.config(text=f"{name}: Online", bg='green'))
                else:
                    self.master.after(0, lambda: button.config(text=f"{name}: Offline", bg='red'))
            except Exception as e:
                logger_provedor_test.error(f"Erro ao verificar status: {e}")

        # Cria e inicia a thread para processar o resultado
        threading.Thread(target=thread_function).start()

    def check_status(self):
        """Verifica o status das interfaces usando as conexões SSH apropriadas."""
        if hasattr(self, 'ssh_vpn_client') and self.ssh_vpn_client is not None:
            threading.Thread(target=self.check_interface_status, args=('eth2', self.unifique_status, 'UNIFIQUE', self.ssh_vpn_client)).start()
            threading.Thread(target=self.check_interface_status, args=('eth4', self.claro_status, 'CLARO', self.ssh_vpn_client)).start()
            threading.Thread(target=self.check_interface_status, args=('eth5', self.coopera_status, 'COOPERA', self.ssh_vpn_client)).start()

#LOGICA PARA EXIBIR STATUS E MENUS DAS VMS
    # Configura menus nos botões de VMs
    def show_vm_vpn_menu(self):
        self.show_vm_menu(self.vm_names['vpn'])

    def show_vm_jogo_menu(self):
        self.show_vm_menu(self.vm_names['jogo'])

    def show_vm_menu(self, vm_name):
        menu = Menu(self.master, tearoff=0)
        menu.add_command(label="Ligar", command=lambda: self.run_command("startvm", vm_name))
        menu.add_command(label="Salvar Estado", command=lambda: self.run_command("savestate", vm_name))
        menu.add_command(label="Desligar", command=lambda: self.run_command("acpipowerbutton", vm_name))
        menu.add_command(label="Forçar Desligamento", command=lambda: self.run_command("poweroff", vm_name))
        menu.post(self.master.winfo_pointerx(), self.master.winfo_pointery())

    def run_command(self, action, vm_name):
        commands = {
            "startvm": f'"C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe" startvm "{vm_name}" --type headless',
            "savestate": f'"C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe" controlvm "{vm_name}" savestate',
            "acpipowerbutton": f'"C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe" controlvm "{vm_name}" acpipowerbutton',
            "poweroff": f'"C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe" controlvm "{vm_name}" poweroff'
        }
        command = commands.get(action)
        if command:
            try:
                subprocess.run(command, shell=True, check=True)
                logging.info(f"Comando '{command}' executado com sucesso.")
            except subprocess.CalledProcessError as e:
                logging.error(f"Erro ao executar o comando: {e}")

    # Carrega os nomes das VMs    
    def load_vm_names(self):
        if os.path.exists(self.vm_config_file):
            with open(self.vm_config_file, 'r') as file:
                config = json.load(file)
                self.vm_names['vpn'] = config.get('vm_vpn_name', self.vm_names['vpn'])
                self.vm_names['jogo'] = config.get('vm_jogo_name', self.vm_names['jogo'])
        else:
            print(f"Arquivo de configuração '{self.vm_config_file}' não encontrado.")

    # Função que faz o monitoramento das VMs
    def update_vm_status(self):
        if not self.verificar_vm:
            return  # Se verificar_vm for False, interrompe o loop

        # Função que executa o comando para VM VPN e VM JOGO
        def get_vm_state(vm_name):
            try:
                result = subprocess.check_output(
                    f'"C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe" showvminfo "{vm_name}" --machinereadable | findstr /C:"VMState="',
                    shell=True, text=True
                )
                # Extrai o estado da VM do resultado do comando
                state = result.strip().split('=')[1].replace('"', '')
                return state
            except subprocess.CalledProcessError:
                return "Erro"

        def update_label(label, state):
            if state == "stopping":
                label.config(text="Desligando", fg="blue")
            elif state == "starting":
                label.config(text="Ligando", fg="blue")
            elif state == "running":
                label.config(text="Ligado", fg="green")
            elif state == "poweroff":
                label.config(text="Desligado", fg="red")
            elif state == "saved":
                label.config(text="Salva", fg="red")
            elif state == "restoring":
                label.config(text="Restaurando", fg="blue")
            elif state == "saving":
                label.config(text="Salvando", fg="blue")
            else:
                label.config(text=state, fg="black")

        def threaded_update():
            vpn_state = get_vm_state(self.vm_names['vpn'])
            jogo_state = get_vm_state(self.vm_names['jogo'])
            # Atualiza as labels na thread principal
            self.master.after(0, lambda: update_label(self.value_vm_vpn, vpn_state))
            self.master.after(0, lambda: update_label(self.value_vm_jogo, jogo_state))

        # Executa a atualização em uma nova thread
        thread = threading.Thread(target=threaded_update)
        thread.start()

        # Agenda a próxima atualização em 5 segundos se verificar_vm for True
        if self.verificar_vm:
            self.master.after(5000, self.update_vm_status)

    # Desliga o monitoramento das VMs
    def stop_verificar_vm(self):
        self.verificar_vm = False

#LOGICA PARA SALVAMENTO E EXIBIÇÃO DE LOGS EM TEMPO REAL.
    def abrir_janela_logs(self):
        log_window = tk.Toplevel(self.master)
        log_window.title("Visualização de Logs")
        log_window.geometry("877x656")  # Definir o tamanho da janela

        # Carregar a posição salva
        self.load_log_position(log_window)

        # Cria um notebook (abas)
        notebook = ttk.Notebook(log_window)
        notebook.pack(expand=1, fill='both')

        # Aba 1: Logs principais
        log_frame_main = tk.Frame(notebook)
        log_text_main = scrolledtext.ScrolledText(log_frame_main, wrap=tk.WORD, state=tk.NORMAL)
        log_text_main.pack(expand=1, fill=tk.BOTH)
        notebook.add(log_frame_main, text='Monitoramento do OMR')

        # Aba 2: Logs do Test Command
        log_frame_test = tk.Frame(notebook)
        log_text_test = scrolledtext.ScrolledText(log_frame_test, wrap=tk.WORD, state=tk.NORMAL)
        log_text_test.pack(expand=1, fill=tk.BOTH)
        notebook.add(log_frame_test, text='Logs das Conexões')

        # Aba 3: Logs do Provedor
        log_frame_provedor = tk.Frame(notebook)
        log_text_provedor = scrolledtext.ScrolledText(log_frame_provedor, wrap=tk.WORD, state=tk.NORMAL)
        log_text_provedor.pack(expand=1, fill=tk.BOTH)
        notebook.add(log_frame_provedor, text='Logs de teste de Provedores')

        # Aba 4: Logs do Proxy SSH
        log_frame_proxy = tk.Frame(notebook)
        log_text_proxy = scrolledtext.ScrolledText(log_frame_proxy, wrap=tk.WORD, state=tk.NORMAL)
        log_text_proxy.pack(expand=1, fill=tk.BOTH)
        notebook.add(log_frame_proxy, text='Logs do Proxy SSH')

        # Aba 5: Logs do Proxy TCP
        log_frame_proxy_tcp = tk.Frame(notebook)
        log_text_proxy_tcp = scrolledtext.ScrolledText(log_frame_proxy_tcp, wrap=tk.WORD, state=tk.NORMAL)
        log_text_proxy_tcp.pack(expand=1, fill=tk.BOTH)
        notebook.add(log_frame_proxy_tcp, text='Logs do Proxy TCP')

        # Variável para controlar o scroll automático
        self.auto_scroll = True
        self.update_logs_id = None

        # Função para atualizar o widget de texto com novas entradas de log
        def update_logs():
            if self.auto_scroll:  # Atualiza apenas se o scroll automático estiver ativo
                with open('app.log', 'r') as file:
                    logs_main = file.read()
                log_text_main.delete(1.0, tk.END)
                log_text_main.insert(tk.END, logs_main)
                log_text_main.see(tk.END)

                with open('test_command.log', 'r') as file:
                    logs_test = file.read()
                log_text_test.delete(1.0, tk.END)
                log_text_test.insert(tk.END, logs_test)
                log_text_test.see(tk.END)

                with open('provedor_test.log', 'r') as file:
                    logs_provedor = file.read()
                log_text_provedor.delete(1.0, tk.END)
                log_text_provedor.insert(tk.END, logs_provedor)
                log_text_provedor.see(tk.END)

                # Novo: Carregar os logs do Proxy
                with open('proxy.log', 'r') as file:
                    logs_proxy = file.read()
                log_text_proxy.delete(1.0, tk.END)
                log_text_proxy.insert(tk.END, logs_proxy)
                log_text_proxy.see(tk.END)

                # Novo: Carregar os logs do Proxy TCP
                with open('proxy_tcp.log', 'r') as file:
                    logs_proxy_tcp = file.read()
                log_text_proxy_tcp.delete(1.0, tk.END)
                log_text_proxy_tcp.insert(tk.END, logs_proxy_tcp)
                log_text_proxy_tcp.see(tk.END)

            # Agendar a próxima atualização
            self.update_logs_id = log_window.after(1000, update_logs)

        # Função para alternar entre parar e continuar o scroll automático
        def toggle_scroll():
            if self.auto_scroll:
                self.auto_scroll = False
                toggle_button.config(text="Continuar Scroll")
                if self.update_logs_id:
                    log_window.after_cancel(self.update_logs_id)
            else:
                self.auto_scroll = True
                toggle_button.config(text="Parar Scroll")
                update_logs()  # Atualiza imediatamente e reinicia o loop

        # Botão para alternar scroll automático
        button_frame = tk.Frame(log_window)
        button_frame.pack(fill=tk.X, pady=5)

        toggle_button = tk.Button(button_frame, text="Parar Scroll", command=toggle_scroll)
        toggle_button.pack(side=tk.LEFT, padx=5)

        # Inicia o loop de atualização dos logs
        update_logs()

        # Adiciona a lógica para salvar a posição da janela quando ela for fechada
        log_window.protocol("WM_DELETE_WINDOW", lambda: self.on_close_log(log_window))

    def load_log_position(self, window):
        if os.path.isfile("log_position.json"):
            with open("log_position.json", "r") as f:
                position = json.load(f)
                window.geometry("+{}+{}".format(position["x"], position["y"]))

    def save_log_position(self, window):
        position = {
            "x": window.winfo_x(),
            "y": window.winfo_y()
        }
        with open("log_position.json", "w") as f:
            json.dump(position, f)

    def on_close_log(self, window):
        self.save_log_position(window)
        window.destroy()

    def clear_log_file(self, log_file_path):
        open(log_file_path, 'w').close()

#LOGICA PARA MONITORAMENTO DA CONEXÃO DOS OMR E REINICIO DO GLORYTUN/XRAY CASO NECESSARIO.
    def monitor_ping_direto(self):
        while self.monitor_xray:
            logger_main.info(f"Verificando conexão com o VPS VPN ({self.url_to_ping_vps_vpn}) ou VPS VPN 1 ({self.url_to_ping_vps_vpn_1})...")

            # Tenta pingar ambos os endereços
            status_vpn, _ = self.ping_direto(self.url_to_ping_vps_vpn)
            status_vpn_1, _ = self.ping_direto(self.url_to_ping_vps_vpn_1)

            # Verifica se pelo menos um dos pings foi bem-sucedido
            if status_vpn == "OFF" and status_vpn_1 == "OFF":
                logger_main.error("Falha na conexão com ambos os VPS VPNs. Aguardando 5 segundos para testar novamente...")
                # Aguardar 5 segundos antes de realizar o próximo teste
                for _ in range(5):
                    if not self.monitor_xray:
                        logger_main.info("Teste do VPS VPN interrompido.")
                        return
                    time.sleep(1)  # Aguarde 1 segundo
            else:
                if status_vpn != "OFF":
                    logger_main.info(f"Conexão com o VPS VPN ({self.url_to_ping_vps_vpn}) concluída com êxito. Prosseguindo...")
                if status_vpn_1 != "OFF":
                    logger_main.info(f"Conexão com o VPS VPN 1 ({self.url_to_ping_vps_vpn_1}) concluída com êxito. Prosseguindo...")
            
                self.monitor_xray = False
                self.start_monitoring()  # Inicia o monitoramento principal
                return  # Interrompe o loop após iniciar o monitoramento principal

    def ping_glorytun_vpn(self, host, port=80, timeout=1):
        def test_connection(ip, port, timeout, bind_ip=None):
            try:
                # Cria um socket
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conn:
                    if bind_ip:
                        conn.bind((bind_ip, 0))  # Bind ao IP de origem com uma porta qualquer
                    conn.settimeout(timeout)
                    conn.connect((ip, port))
                return True
            except (socket.timeout, socket.error):
                return False

        # Teste inicial de conexão ao endereço 192.168.101.1 na porta 80
        logger_main.info("Iniciando teste de conexão com o IP 192.168.101.1...")
        if not test_connection('192.168.101.1', 80, timeout):
            logger_main.error("Falha na conexão com o IP 192.168.101.1. Aguardando 5 segundos para testar novamente...")
            for _ in range(5):  # Divida a espera em intervalos de 1 segundo
                if not self.monitor_xray:
                    logger_main.info("Monitoramento interrompido durante a espera.")
                    return "OFF", "red"
                time.sleep(1)  # Aguarde 1 segundo
            return self.ping_glorytun_vpn(host, port, timeout)

        # Teste de conexão ao host fornecido na porta 80 com bind no IP 192.168.101.2
        logger_main.info(f"Verificando conexão com o host {host} na porta {port}...")
        if test_connection(host, port, timeout, bind_ip='192.168.101.2'):
            logger_main.info(f"Conexão com o host {host} bem-sucedida.")
            return "ON", "green"
        else:
            logger_main.error(f"Falha na conexão com o host {host}.")
            return "OFF", "blue"

    def ping_xray_jogo(self, host, port=65222, timeout=1):
        def test_connection(ip, port, timeout, bind_ip=None):
            try:
                # Cria um socket
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conn:
                    if bind_ip:
                        conn.bind((bind_ip, 0))  # Bind ao IP de origem com uma porta qualquer
                    conn.settimeout(timeout)
                    conn.connect((ip, port))
                return True
            except (socket.timeout, socket.error):
                return False

        # Teste inicial de conexão ao endereço 192.168.100.1 na porta 80
        logger_main.info("Iniciando teste de conexão com o IP 192.168.100.1...")
        if not test_connection('192.168.100.1', 80, timeout):
            logger_main.error("Falha na conexão com o IP 192.168.100.1. Aguardando 5 segundos para testar novamente...")
            for _ in range(5):  # Divida a espera em intervalos de 1 segundo
                if not self.monitor_xray:
                    logger_main.info("Monitoramento interrompido durante a espera.")
                    return "OFF", "red"
                time.sleep(1)  # Aguarde 1 segundo
            return self.ping_xray_jogo(host, port, timeout)

        # Teste de conexão ao host fornecido na porta 65222 com bind no IP 192.168.100.2
        logger_main.info(f"Verificando conexão com o host {host} na porta {port}...")
        try:
            start_time = time.time()
            socket_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conn:
                conn.bind(('192.168.100.2', 0))
                conn.settimeout(timeout)
                conn.connect(socket_info[0][4])
                conn.sendall(b'PING')
                response = conn.recv(1024)
            
            end_time = time.time()
            response_time = int((end_time - start_time) * 1000 / 2)  # Converte para milissegundos

            if response:
                logger_main.info(f"Conexão com o host {host} bem-sucedida. Tempo de resposta: {response_time} ms")
                return f"ON ({response_time} ms)", "green"
            else:
                logger_main.warning(f"Falha na conexão com o host {host} (sem resposta).")
                return "OFF", "blue"
        except (socket.timeout, socket.error) as e:
            logger_main.error(f"Falha na conexão com o host {host} (exceção: {e}).")
            return "OFF", "blue"

    def ping_direto(self, host, port=65222, timeout=1):
        try:
            start_time = time.time()
            socket_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
            conn = socket.create_connection(socket_info[0][4], timeout=timeout)
            
            # Envia alguns bytes de dados
            conn.sendall(b'PING')
            
            # Recebe alguns bytes de dados
            response = conn.recv(1024)
            
            conn.close()
            end_time = time.time()
            response_time = int((end_time - start_time) * 1000/2)  # Converte para milissegundos e arredonda para inteiro
            
            # Verifica se a resposta é válida
            if response:
                return f"ON ({response_time} ms)", "green"
            else:
                return "OFF", "red"
        except (socket.timeout, socket.error):
            return "OFF", "red"

    def monitor_loop(self):
        first_failure_vpn = True
        first_failure_xray = True
        while self.monitor_xray:
            # Inicialize flags e contadores fora do loop interno
            consecutive_failures_vpn = 0
            consecutive_failures_xray = 0

            # Verificação do Glorytun VPN
            while consecutive_failures_vpn < 6 and self.monitor_xray:
                logger_main.info("Verificando conexão com o Glorytun VPN...")
                status_vpn, _ = self.ping_glorytun_vpn(self.url_to_ping_omr_vpn)
                if status_vpn == "OFF":
                    if first_failure_vpn:
                        logger_main.error("Primeira falha na conexão com o Glorytun VPN. Reiniciando imediatamente...")
                        first_failure_vpn = False
                        try:
                            # Reinicia o omr-tracker antes do Glorytun VPN
                            if hasattr(self, 'ssh_vpn_client') and self.ssh_vpn_client is not None:
                                try:
                                    self.ssh_vpn_client.exec_command("/etc/init.d/omr-tracker restart")
                                except Exception:
                                    pass
                            logger_main.info("Comando de reinício do omr-tracker executado.")

                            # Aguarda 20 segundos, verificando se ainda deve continuar
                            for _ in range(20):
                                if not self.monitor_xray:
                                    return
                                time.sleep(1)

                            # Realiza um novo teste de conexão antes de reiniciar o Glorytun
                            logger_main.info("Realizando um novo teste de conexão antes de reiniciar o Glorytun...")
                            status_vpn_recheck, _ = self.ping_glorytun_vpn(self.url_to_ping_omr_vpn)
                            if status_vpn_recheck == "ON":
                                logger_main.info("Conexão restaurada. Reinicialização do Glorytun cancelada.")
                                break  # Sai do loop e não reinicia o Glorytun

                            # Se a conexão ainda estiver off, reinicia o Glorytun
                            if hasattr(self, 'ssh_vpn_client') and self.ssh_vpn_client is not None:
                                try:
                                    self.ssh_vpn_client.exec_command("/etc/init.d/glorytun restart")
                                except Exception:
                                    pass
                            logger_main.info("Comando de reinício do Glorytun VPN executado.")
                        except Exception as e:
                            logger_main.error(f"Erro ao executar o comando de reinício do Glorytun VPN: {e}")
                    else:
                        consecutive_failures_vpn += 1
                        logger_main.error(f"Falha {consecutive_failures_vpn}/6 na conexão com o Glorytun VPN. Aguardando 5 segundos para testar novamente...")
                        for _ in range(5):
                            if not self.monitor_xray:
                                return
                            time.sleep(1)
                else:
                    logger_main.info("Conexão com o Glorytun VPN bem-sucedida.")
                    break  # Sai do loop do Glorytun VPN

            if status_vpn == "OFF":
                logger_main.error("Falha na conexão com o Glorytun VPN após 6 tentativas. Executando o comando de reinício do Glorytun novamente...")
                try:
                    # Reinicia o omr-tracker antes do Glorytun VPN
                    if hasattr(self, 'ssh_vpn_client') and self.ssh_vpn_client is not None:
                        try:
                            self.ssh_vpn_client.exec_command("/etc/init.d/omr-tracker restart")
                        except Exception:
                            pass
                    logger_main.info("Comando de reinício do omr-tracker executado.")

                    # Aguarda 5 segundos, verificando se ainda deve continuar
                    for _ in range(5):
                        if not self.monitor_xray:
                            return
                        time.sleep(1)

                    if hasattr(self, 'ssh_vpn_client') and self.ssh_vpn_client is not None:
                        try:
                            self.ssh_vpn_client.exec_command("/etc/init.d/glorytun restart")
                        except Exception:
                            pass
                    logger_main.info("Comando de reinício do Glorytun VPN executado.")
                except Exception as e:
                    logger_main.error(f"Erro ao executar o comando de reinício do Glorytun VPN: {e}")
                continue  # Reinicia o loop para testar o Glorytun novamente

            # Verificação do Xray Jogo (só prossegue se a conexão com o Glorytun for bem-sucedida)
            while consecutive_failures_xray < 4 and self.monitor_xray:
                logger_main.info("Verificando conexão com o Xray Jogo...")
                status_xray, _ = self.ping_xray_jogo(self.url_to_ping_omr_jogo)
                if status_xray == "OFF":
                    if first_failure_xray:
                        logger_main.error("Primeira falha na conexão com o Xray Jogo. Reiniciando imediatamente...")
                        first_failure_xray = False
                        try:
                            # Reinicia o omr-tracker antes do Xray Jogo
                            if hasattr(self, 'ssh_jogo_client') and self.ssh_jogo_client is not None:
                                try:
                                    self.ssh_jogo_client.exec_command("/etc/init.d/omr-tracker restart")
                                except Exception:
                                    pass
                            logger_main.info("Comando de reinício do omr-tracker executado.")

                            # Aguarda 20 segundos, verificando se ainda deve continuar
                            for _ in range(20):
                                if not self.monitor_xray:
                                    return
                                time.sleep(1)

                            # Realiza um novo teste antes de reiniciar o Xray
                            logger_main.info("Realizando novo teste de conexão com o Xray Jogo antes do reinício...")
                            status_xray, _ = self.ping_xray_jogo(self.url_to_ping_omr_jogo)

                            if status_xray == "ON":
                                logger_main.info("Novo teste bem-sucedido, não será necessário reiniciar o Xray Jogo.")
                                break  # Sai do loop e encerra a verificação
                            else:
                                logger_main.error("Novo teste falhou, reiniciando Xray Jogo...")
                                if hasattr(self, 'ssh_jogo_client') and self.ssh_jogo_client is not None:
                                    try:
                                        self.ssh_jogo_client.exec_command("/etc/init.d/xray restart")
                                    except Exception:
                                        pass
                                logger_main.info("Comando de reinício do Xray executado.")

                        except Exception as e:
                            logger_main.error(f"Erro ao executar o comando de reinício do Xray: {e}")
                    else:
                        consecutive_failures_xray += 1
                        logger_main.error(f"Falha {consecutive_failures_xray}/4 na conexão com o Xray Jogo. Aguardando 5 segundos para testar novamente...")
                        for _ in range(5):
                            if not self.monitor_xray:
                                return
                            time.sleep(1)
                else:
                    logger_main.info("Conexão com o Xray Jogo está OK.")
                    break  # Sai do loop do Xray Jogo

            if status_xray == "OFF":
                logger_main.error("Falha na conexão com o Xray Jogo após 4 tentativas. Executando o comando de reinício do Xray novamente...")
                try:
                    # Reinicia o omr-tracker antes do Xray Jogo
                    if hasattr(self, 'ssh_jogo_client') and self.ssh_jogo_client is not None:
                        try:
                            self.ssh_jogo_client.exec_command("/etc/init.d/omr-tracker restart")
                        except Exception:
                            pass
                    logger_main.info("Comando de reinício do omr-tracker executado.")

                    # Aguarda 5 segundos, verificando se ainda deve continuar
                    for _ in range(5):
                        if not self.monitor_xray:
                            return
                        time.sleep(1)

                    if hasattr(self, 'ssh_jogo_client') and self.ssh_jogo_client is not None:
                        try:
                            self.ssh_jogo_client.exec_command("/etc/init.d/xray restart")
                        except Exception:
                            pass
                    logger_main.info("Comando de reinício do Xray executado.")
                except Exception as e:
                    logger_main.error(f"Erro ao executar o comando de reinício do Xray: {e}")
                continue  # Reinicia o loop para testar o Xray novamente

            logger_main.info("Ambos os testes foram bem-sucedidos. Encerrando o monitoramento...")
            self.botao_alternar.after(0, self.stop_monitoring)
            return  # Sai do loop principal se ambos os testes forem bem-sucedidos

    def start_monitoring_delay(self):
        if not self.monitor_xray:
            logger_main.info("Aguardando 40 segundos antes de iniciar o monitoramento...")
            self.monitor_xray = True  # Use a variável existente
            # Agendar a execução do restante da função após 40 segundos
            self.botao_alternar.config(text="Parar Monitoramento do OMR")
            self.botao_alternar.after(40000, self.start_ping_direto_monitoring)

    def start_ping_direto_monitoring(self):
        if self.monitor_xray:
            logger_main.info(f"Iniciando teste do VPS VPN ({self.url_to_ping_vps_vpn})...")
            #self.monitor_xray = True  # Use a variável existente
            self.thread_ping_direto = threading.Thread(target=self.monitor_ping_direto)
            self.thread_ping_direto.start()
            self.botao_alternar.config(text="Parar Monitoramento do OMR")

    def start_monitoring(self):
        if not self.monitor_xray:
            logger_main.info("Iniciando monitoramento...")
            self.monitor_xray = True
            self.thread = threading.Thread(target=self.monitor_loop)
            self.thread.start()
            self.botao_alternar.config(text="Parar Monitoramento do OMR")

    def stop_monitoring(self):
        if self.monitor_xray:
            logger_main.info("Parando monitoramento...")
            self.monitor_xray = False

            if self.thread is not None:
                # Espera no máximo 5 segundos para a thread terminar
                self.thread.join(timeout=5)
                if self.thread.is_alive():
                    logger_main.warning("A thread de monitoramento não terminou após o timeout.")
                else:
                    logger_main.info("Thread de monitoramento terminada com sucesso.")

            self.botao_alternar.config(text="Iniciar Monitoramento do OMR")
            logger_main.info("Monitoramento parado.")

    def alternar_monitoramento(self):
        if self.monitor_xray:
            self.stop_monitoring()
        else:
            self.start_monitoring()

#lOGICA PARA FUNÇÃO DE ATUALIZAÇÃO DO SCHEDULER NA 3° ABA.
    def executar_comando_ssh(self, ssh_session, comando, is_transport=False):
        """Executa um comando via SSH (cliente ou sessão Transport) e retorna a saída com um timeout."""
        output_queue = queue.Queue()

        def run_command():
            try:
                if is_transport:
                    # Sessão manualmente aberta com Transport
                    ssh_session.exec_command(comando)

                    # Aguarda resposta ou timeout de 5 segundos
                    ready = select.select([ssh_session], [], [], 5)[0]
                    if not ready:
                        output_queue.put("Erro: Nenhum retorno dentro do tempo limite.")
                        return

                    # Recebe a saída do comando
                    saida = ssh_session.recv(1024).decode().strip()
                    if not saida:
                        output_queue.put(f"Erro: Nenhuma saída do comando '{comando}'.")
                    else:
                        output_queue.put(saida)

                else:
                    # Usando ssh_client (como um SSHClient normal)
                    stdin, stdout, stderr = ssh_session.exec_command(comando)
                    erro = stderr.read().decode().strip()
                    saida = stdout.read().decode().strip()
                    if erro:
                        output_queue.put(f"Erro: {erro}")
                    else:
                        output_queue.put(saida)

            except Exception as e:
                output_queue.put(f"Erro: {str(e)}")

        # Cria e inicia a thread para executar o comando
        command_thread = threading.Thread(target=run_command)
        command_thread.start()

        # Espera pelo comando com timeout
        command_thread.join(timeout=5)  # Timeout de 5 segundos

        if command_thread.is_alive():
            # Timeout ocorreu, encerra a thread e retorna erro
            command_thread.join(0)  # Espera a thread terminar, se possível
            return "Erro: Timeout na execução do comando."

        # Obtém a saída da fila
        try:
            result = output_queue.get_nowait()
        except queue.Empty:
            result = "Erro: Timeout na execução do comando."

        return result

    def truncar_texto(self, texto, limite=12):
        """Retorna 'Indisponível' se o texto exceder o limite, caso contrário retorna o texto."""
        if len(texto) > limite:
            return "Indisponível"
        return texto

    def atualizar_label_scheduler(self, label_scheduler, label_cc, ssh_client, comando_scheduler, comando_cc, conexao_nome):
        """Atualiza as labels com o resultado dos comandos SSH executados ou 'Offline' se a conexão não estiver estabelecida."""
        if ssh_client is None or not ssh_client.get_transport().is_active():
            # Atualiza o texto do label para "Offline" se a conexão não estiver estabelecida
            print(f"Conexão SSH ({conexao_nome}) não está estabelecida. Atualizando labels para Offline.")
            self.master.after(0, lambda: label_scheduler.config(text="Scheduler: Offline"))
            self.master.after(0, lambda: label_cc.config(text="CC: Offline"))
            return

        # Executa os comandos via SSH com timeout
        resultado_scheduler = self.executar_comando_ssh(ssh_client, comando_scheduler)
        resultado_cc = self.executar_comando_ssh(ssh_client, comando_cc)

        # Trunca os resultados se necessário
        resultado_scheduler_truncado = self.truncar_texto(resultado_scheduler)
        resultado_cc_truncado = self.truncar_texto(resultado_cc)

        # Imprime a origem dos resultados
        print(f"Resultado do comando scheduler ({conexao_nome}): {resultado_scheduler_truncado}")
        print(f"Resultado do comando CC ({conexao_nome}): {resultado_cc_truncado}")

        # Atualiza as labels com os resultados dos comandos
        self.master.after(0, lambda: label_scheduler.config(text=f"Scheduler: {resultado_scheduler_truncado}"))
        self.master.after(0, lambda: label_cc.config(text=f"CC: {resultado_cc_truncado}"))

    def executar_comandos_scheduler(self):
        """Executa os comandos do scheduler e CC em paralelo usando a conexão SSH correta."""
        # Define os comandos a serem executados e as conexões SSH associadas
        comandos = {
            (self.label_vps_vpn_scheduler, self.label_vps_vpn_cc): (
                self.ssh_vps_vpn_client if self.connection_established_ssh_vps_vpn.is_set() else None, 
                "cat /proc/sys/net/mptcp/mptcp_scheduler",
                "cat /proc/sys/net/ipv4/tcp_congestion_control",
                "VPS VPN"
            ),
            (self.label_vps_jogo_scheduler, self.label_vps_jogo_cc): (
                self.ssh_vps_jogo_client if self.connection_established_ssh_vps_jogo.is_set() else None, 
                "cat /proc/sys/net/mptcp/mptcp_scheduler",
                "cat /proc/sys/net/ipv4/tcp_congestion_control",
                "VPS Jogo"
            ),
            (self.label_omr_vpn_scheduler, self.label_omr_vpn_cc): (
                self.ssh_vpn_client if self.connection_established_ssh_omr_vpn.is_set() else None, 
                "cat /proc/sys/net/mptcp/mptcp_scheduler",
                "cat /proc/sys/net/ipv4/tcp_congestion_control",
                "VPN"
            ),
            (self.label_omr_jogo_scheduler, self.label_omr_jogo_cc): (
                self.ssh_jogo_client if self.connection_established_ssh_omr_jogo.is_set() else None, 
                "cat /proc/sys/net/mptcp/mptcp_scheduler",
                "cat /proc/sys/net/ipv4/tcp_congestion_control",
                "Jogo"
            ),
        }

        def processar_comandos():
            for (label_scheduler, label_cc), (ssh_client, comando_scheduler, comando_cc, conexao_nome) in comandos.items():
                # Verifica se o cliente SSH existe
                if ssh_client is None:
                    print(f"Conexão SSH ({conexao_nome}) não está estabelecida ou cliente SSH não está definido. Atualizando labels para Offline.")
                    self.master.after(0, lambda: label_scheduler.config(text="Scheduler: Offline"))
                    self.master.after(0, lambda: label_cc.config(text="CC: Offline"))
                    continue

                # Atualiza as labels com os resultados dos comandos
                self.atualizar_label_scheduler(label_scheduler, label_cc, ssh_client, comando_scheduler, comando_cc, conexao_nome)

        # Executar os comandos em uma thread separada para não bloquear a interface
        threading.Thread(target=processar_comandos).start()

    def update_labels_ssh(self):
        # Atualiza o status do VPS VPN
        if self.connection_established_ssh_vps_vpn.is_set():
            self.label_vps_vpn.config(text="VPS VPN: On", fg="green")
        else:
            self.label_vps_vpn.config(text="VPS VPN: Off", fg="red")

        # Atualiza o status do VPS JOGO
        if self.connection_established_ssh_vps_jogo.is_set():
            self.label_vps_jogo.config(text="VPS JOGO: On", fg="green")
        else:
            self.label_vps_jogo.config(text="VPS JOGO: Off", fg="red")

        # Atualiza o status do OMR VPN
        if self.connection_established_ssh_omr_vpn.is_set():
            self.label_omr_vpn.config(text="OMR VPN: On", fg="green")
        else:
            self.label_omr_vpn.config(text="OMR VPN: Off", fg="red")

        # Atualiza o status do OMR JOGO
        if self.connection_established_ssh_omr_jogo.is_set():
            self.label_omr_jogo.config(text="OMR JOGO: On", fg="green")
        else:
            self.label_omr_jogo.config(text="OMR JOGO: Off", fg="red")

        # Reagenda a verificação após 1000 ms (1 segundo)
        self.master.after(1000, self.update_labels_ssh)

#LOGICA PARA BOTÕES DE REINICIAR GLORYTUN E XRAY NA 3° ABA.
    def reiniciar_glorytun_vpn(self):
        """Reinicia o serviço Glorytun através da conexão SSH já estabelecida."""
        if self.connection_established_ssh_omr_vpn.is_set():
            try:
                self.ssh_vpn_client.exec_command("/etc/init.d/openvpn restart")
                logger_main.info("Serviço OpenVPN reiniciado com sucesso.")
            except Exception as e:
                logger_main.error(f"Erro ao reiniciar o serviço OpenVPN: {e}")
        else:
            logger_main.error("Não foi possível reiniciar o serviço OpenVPN. Conexão SSH OMR VPN não está ativa.")

    def reiniciar_xray_jogo(self):
        """Reinicia o serviço Xray através da conexão SSH já estabelecida com confirmação do usuário."""
        def confirmar_reiniciar():
            resposta = ctypes.windll.user32.MessageBoxW(
                0,
                "Você realmente deseja reiniciar o Xray?",
                "Confirmar",
                4  # MB_YESNO
            )
            if resposta == 6:  # IDYES
                if self.connection_established_ssh_omr_jogo.is_set():
                    try:
                       self.ssh_jogo_client.exec_command("/etc/init.d/xray restart")
                       logger_main.info("Serviço Xray reiniciado com sucesso.")
                    except Exception as e:
                        logger_main.error(f"Erro ao reiniciar o serviço Xray: {e}")
                else:
                    logger_main.error("Não foi possível reiniciar o serviço Xray. Conexão SSH OMR JOGO não está ativa.")

        confirmar_reiniciar()

#LOGICA PARA MONITORAMENTO DE VPS E OMR, E ATUALIZAR AS DEVIDAS LABELS NO TOPO DA JANELA PRINCIPAL DA APLICAÇÃO.
    # Inicia o looping de monitoramento de ping.
    def start_pinging_threads(self):
        interval = 2  # Define o intervalo de 2 segundos para os pings
        threading.Thread(target=self.ping_forever_vps_vpn, args=(self.url_to_ping_vps_vpn, self.update_status_vps_vpn), daemon=True).start()
        threading.Thread(target=self.ping_forever_vps_jogo, args=(self.url_to_ping_vps_jogo, self.update_status_vps_jogo), daemon=True).start()
        threading.Thread(target=self.ping_forever_omr_vpn, args=(self.url_to_ping_omr_vpn, self.update_status_omr_vpn), daemon=True).start()
        threading.Thread(target=self.ping_forever_omr_jogo, args=(self.url_to_ping_omr_jogo, self.update_status_omr_jogo), daemon=True).start()

    # Para o looping de monitoramento de ping.
    def stop_pinging_threads(self):
        self.ping_forever = False

    def load_addresses(self):
        try:
            with open('addresses.json', 'r') as f:
                addresses = json.load(f)
                self.url_to_ping_vps_jogo = addresses.get("vps_jogo")
                self.url_to_ping_vps_vpn = addresses.get("vps_vpn")
                self.url_to_ping_omr_vpn = addresses.get("omr_vpn")
                self.url_to_ping_omr_jogo = addresses.get("omr_jogo")
                self.url_to_ping_vps_vpn_1 = addresses.get("vps_vpn_1")
                self.url_to_ping_vps_jogo_1 = addresses.get("vps_jogo_1")
        except (FileNotFoundError, json.JSONDecodeError):
            self.url_to_ping_vps_jogo = None
            self.url_to_ping_vps_vpn = None
            self.url_to_ping_omr_vpn = None
            self.url_to_ping_omr_jogo = None
            self.url_to_ping_vps_vpn_1 = None
            self.url_to_ping_vps_jogo_1 = None

    def ping_omr_vpn(self, host, port=80, timeout=1):
        def test_connection(ip, port, timeout):
            try:
                # Cria um socket e faz o bind ao IP de origem
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_sock:
                    test_sock.bind(('192.168.101.2', 0))  # Bind ao IP de origem com uma porta qualquer
                    test_sock.settimeout(timeout)
                    test_sock.connect((ip, port))
                return True
            except (socket.timeout, socket.error):
                return False

        # Condição 1: O teste inicial só pode ser ignorado se o evento de conexão estiver ativo
        # Se o evento de conexão NÃO estiver ativo, sempre executa o teste inicial
        if not self.connection_established_ssh_vps_vpn_bind.is_set() or self.execute_initial_test:
            # Teste inicial de conexão ao endereço 192.168.101.1 na porta 80
            if not test_connection('192.168.101.1', 80, timeout):
                # Se falhar no teste inicial, retorna OFF em vermelho
                return "Desligado", "red"

        # Looping de ping até que a conexão SSH/VPN seja estabelecida
        while not self.connection_established_ssh_vps_vpn_bind.is_set():
            # Teste de conexão ao host fornecido na porta 80 (ping)
            try:
                # Cria um socket e faz o bind ao IP de origem
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conn:
                    conn.bind(('192.168.101.2', 0))  # Bind ao IP de origem com uma porta qualquer
                    conn.settimeout(timeout)
                    conn.connect((host, port))

                # Se o ping for bem-sucedido, verifica se a conexão SSH já foi estabelecida
                if self.connection_established_ssh_vps_vpn_bind.is_set():
                    # Se a conexão SSH/VPN estiver ativa, retorna ON (verde) e para os testes
                    return "Conectado", "green"
                # Caso contrário, retorna ON (amarelo)
                return "Conectando", "#B8860B"
            except (socket.timeout, socket.error):
                # Se o teste de ping falhar, atualiza para OFF em azul
                return "Ligado", "blue"

        # Se a conexão SSH/VPN estiver ativa, retorna ON (verde) diretamente
        return "Conectado", "green"

    def ping_forever_omr_vpn(self, url, update_func, interval=1):
        while self.ping_forever:
            status, color = self.ping_omr_vpn(url)
            update_func(status, color)
            time.sleep(interval)

    def ping_omr_jogo(self, host, port=65222, timeout=1):
        def test_connection(ip, port, timeout):
            try:
                # Cria um socket e faz o bind ao IP de origem
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_sock:
                    test_sock.bind(('192.168.100.2', 0))  # Bind ao IP de origem com uma porta qualquer
                    test_sock.settimeout(timeout)
                    test_sock.connect((ip, port))
                return True
            except (socket.timeout, socket.error):
                return False

        # Condição 1: O teste inicial só pode ser ignorado se o evento de conexão estiver ativo
        # Se o evento de conexão NÃO estiver ativo, sempre executa o teste inicial
        if not self.connection_established_ssh_vps_jogo_bind.is_set() or self.execute_initial_test:
            # Teste inicial de conexão ao endereço 192.168.100.1 na porta 80
            if not test_connection('192.168.100.1', 80, timeout):
                # Se falhar no teste inicial, retorna OFF em vermelho
                return "Desligado", "red"

        # Loop de ping até que a conexão SSH/VPN seja estabelecida
        while not self.connection_established_ssh_vps_jogo_bind.is_set():
            # Teste de conexão ao host fornecido na porta 65222
            try:
                # Cria um socket e faz o bind ao IP de origem
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conn:
                    conn.bind(('192.168.100.2', 0))  # Bind ao IP de origem com uma porta qualquer
                    conn.settimeout(timeout)
                    conn.connect((host, port))
                    
                    # Envia alguns bytes de dados
                    conn.sendall(b'PING')
                    
                    # Recebe alguns bytes de dados
                    response = conn.recv(1024)

                # Verifica se a resposta é válida
                if response:
                    # Se a conexão SSH/VPN estiver ativa, retorna ON (verde) e para os testes
                    if self.connection_established_ssh_vps_jogo_bind.is_set():
                        return "Conectado", "green"
                    # Caso contrário, retorna ON (amarelo)
                    return "Conectando", "#B8860B"
                else:
                    return "Ligado", "blue"
            except (socket.timeout, socket.error):
                return "Ligado", "blue"

        # Se a conexão SSH/VPN estiver ativa, retorna ON (verde) diretamente
        return "Conectado", "green"

    def ping_forever_omr_jogo(self, url, update_func, interval=1):
        while self.ping_forever:
            status, color = self.ping_omr_jogo(url)
            update_func(status, color)
            time.sleep(interval)

    def ping_vps_vpn(self, host, port=65222, timeout=1):
        # Verifica se a conexão SSH/VPN já está estabelecida
        if self.connection_established_ssh_vps_vpn.is_set():
            # Se a conexão SSH/VPN estiver ativa, retorna ON (verde)
            return "Ligado", "green"
        
        # Caso a conexão SSH/VPN não esteja ativa, realiza o teste de ping
        try:
            # Obtém as informações do socket
            socket_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
            
            # Cria a conexão
            conn = socket.create_connection(socket_info[0][4], timeout=timeout)
            
            # Envia alguns bytes de dados
            conn.sendall(b'PING')
            
            # Recebe alguns bytes de dados
            response = conn.recv(1024)
            
            # Fecha a conexão
            conn.close()

            # Verifica se a resposta é válida
            if response:
                # Se o ping foi bem-sucedido, retorna ON (amarelo)
                return "Ligando", "#B8860B"
            else:
                return "Desligado", "red"
        except (socket.timeout, socket.error):
            return "Desligado", "red"

    def ping_forever_vps_vpn(self, url, update_func, interval=1):
        while self.ping_forever:
            status, color = self.ping_vps_vpn(url)
            update_func(status, color)
            time.sleep(interval)

    def ping_vps_jogo(self, host, port=65222, timeout=1):
        # Verifica se a conexão SSH já está estabelecida
        if self.connection_established_ssh_vps_jogo.is_set():
            # Se a conexão SSH estiver ativa, retorna ON (verde)
            return "Ligado", "green"
        
        # Caso a conexão SSH não esteja ativa, realiza o teste de ping
        try:
            # Obtém as informações do socket
            socket_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
            
            # Cria a conexão
            conn = socket.create_connection(socket_info[0][4], timeout=timeout)
            
            # Envia alguns bytes de dados
            conn.sendall(b'PING')
            
            # Recebe alguns bytes de dados
            response = conn.recv(1024)
            
            # Fecha a conexão
            conn.close()

            # Verifica se a resposta é válida
            if response:
                # Se o ping foi bem-sucedido, retorna ON (amarelo)
                return "Ligando", "#B8860B"
            else:
                return "Desligado", "red"
        except (socket.timeout, socket.error):
            return "Desligado", "red"

    def ping_forever_vps_jogo(self, url, update_func, interval=1):
        while self.ping_forever:
            status, color = self.ping_vps_jogo(url)
            update_func(status, color)
            time.sleep(interval)

    def update_status_vps_jogo(self, status, color):
        # Define a fonte em negrito diretamente aqui
        bold_font = ("Segoe UI", 10, "underline")
        self.status_label_vps_jogo.config(text=status, bg=color)
        self.update_general_status()

    def update_status_vps_vpn(self, status, color):
        bold_font = ("Segoe UI", 8, "bold")
        self.status_label_vps_vpn.config(text=status, bg=color)
        self.update_general_status()

    def update_status_omr_vpn(self, status, color):
        bold_font = ("Segoe UI", 8, "bold") # font=bold_font
        self.status_label_omr_vpn.config(text=status, bg=color)
        self.update_general_status()

    def update_status_omr_jogo(self, status, color):
        bold_font = ("Segoe UI", 8, "bold")
        self.status_label_omr_jogo.config(text=status, bg=color)
        self.update_general_status()

    def update_general_status(self):
        # Captura as cores de fundo dos status individuais
        statuses = [
            self.status_label_vps_vpn.cget("bg"),
            self.status_label_vps_jogo.cget("bg"),
            self.status_label_omr_vpn.cget("bg"),
            self.status_label_omr_jogo.cget("bg")
        ]

        valid_colors = ["green", "yellow", "#B8860B", "blue"]  # Cores dos status para serem usadas na função abaixo, devem ser as cores das defs pings acima.

        # Se todos estiverem com cor vermelha
        if all(status == "red" for status in statuses):
            if self.script_finished:
                self.general_status_frame.config(bg="yellow")
                self.general_status_label.config(bg="yellow")
                self.display_connection_status("Conectando")  # Atualiza para "Conectando"
            else:
                self.general_status_frame.config(bg="red")
                self.general_status_label.config(text="Desconectado", bg="red", fg="black")
        # Se qualquer um estiver com cor verde ou amarelo
        elif any(status in valid_colors for status in statuses):
            # Se todos estiverem com cor verde
            if all(status == "green" for status in statuses):
                self.general_status_frame.config(bg="green")
                self.general_status_label.config(bg="green")
                self.script_finished = False
                self.display_connection_status("Conectado")  # Atualiza para "Conectado"
            else:
                self.general_status_frame.config(bg="yellow")
                self.general_status_label.config(bg="yellow")
                self.script_finished = False
                self.display_connection_status("Conectando")  # Atualiza para "Conectando"
        # Caso nenhum esteja verde ou amarelo, mantenha o desconectado
        else:
            self.general_status_frame.config(bg="red")
            self.general_status_label.config(text="Desconectado", bg="red", fg="black")
            self.script_finished = False

        # Verifica se o script terminou e atualiza o status para "Conectando" se necessário
        if self.script_finished:
            self.general_status_frame.config(bg="yellow")
            self.general_status_label.config(bg="yellow")
            self.display_connection_status("Conectando")  # Atualiza para "Conectando"

    def display_connection_status(self, status):
        try:
            with open("conection_status.txt", "r") as connection_file:
                lines = connection_file.readlines()
                if status == "Conectando":
                    self.general_status_label.config(text=lines[0].strip())
                elif status == "Conectado":
                    self.general_status_label.config(text=lines[1].strip())
        except FileNotFoundError:
            pass  # O arquivo não existe, então não há nada para mostrar

#LOGICA PARA ADICIONAR BOTÕES A SEGUNDA ABA.
    def add_new_button_tab2(self):
        dialog = AddButtonDialog(self.master, self.top)
        self.master.wait_window(dialog.top)
        if dialog.button_info:
            # Atribuir um novo ID único para o botão
            button_id = self.button_counter
            self.button_counter += 1
            
            # Adicionar o botão à segunda aba
            self.add_button_to_tab2(dialog.button_info['icon'], dialog.button_info['text'], dialog.button_info['link'],
                                    premium_link=dialog.button_info.get('premium_link'),
                                    standard_link=dialog.button_info.get('standard_link'),
                                    button_id=button_id)
            self.save_buttons()  # Salva os botões após adicionar um novo

    def add_button_to_tab2(self, icon_path, text, link, button_id, premium_link=None, standard_link=None):
        # Copia a imagem para a pasta "imagens" e gera um nome único
        unique_name = str(uuid.uuid4()) + os.path.splitext(icon_path)[1]
        dest_path = os.path.join('imagens', unique_name)
        shutil.copy(icon_path, dest_path)

        button_frame = tk.Frame(self.second_tab_button_frame)  # Cria um frame para conter a imagem e o botão de texto
        button_frame.pack(side=tk.TOP, padx=5, pady=5)

        icon_label = tk.Label(button_frame)  # Label para exibir a imagem
        with Image.open(dest_path) as img:
            img = img.resize((40, 40), Image.LANCZOS)
            icon = ImageTk.PhotoImage(img)

        icon_label.icon = icon
        icon_label.config(image=icon_label.icon)
        icon_label.pack(side=tk.LEFT)

        text_button = tk.Button(button_frame, text=text, justify="center", anchor="center")  # Botão para exibir o texto
        text_button.pack(side=tk.LEFT, padx=5, pady=5)

        text_button.icon_path = dest_path  # Adiciona a propriedade icon_path ao botão
        if button_id is None:
            button_id = self.button_counter
            self.button_counter += 1

        text_button.id = button_id
        text_button.link = link
        text_button.premium_link = premium_link
        text_button.standard_link = standard_link
        
        tooltip_text = f"ID: {text_button.id}\nLink: {link}"
        text_button.tooltip = ToolTip(text_button, tooltip_text)

        menu = tk.Menu(text_button, tearoff=0)
        menu.add_command(label="Editar script", command=lambda: self.edit_link(text_button))
        menu.add_command(label="Abrir pasta", command=lambda: self.open_button_folder(text_button))
        menu.add_command(label="Alterar ID", command=lambda: self.change_button_id(text_button))
        if premium_link is not None:
            menu.add_command(label="IP Premium", command=lambda: self.run_as_admin(premium_link))
        if standard_link is not None:
            menu.add_command(label="IP Standard", command=lambda: self.run_as_admin(standard_link))
        menu.add_command(label="Deletar servidor", command=lambda: self.delete_button(text_button))
        text_button.bind("<Button-3>", lambda event: menu.post(event.x_root, event.y_root))

        text_button.config(command=lambda: self.run_as_admin(text_button.link))

        self.buttons.append(text_button)
        self.reorder_buttons_by_id()
        self.update_button_widths()

    def refresh_button_to_tab2(self, icon_path, text, link, button_id, premium_link=None, standard_link=None):
        # Copia a imagem para a pasta "imagens" e gera um nome único apenas se ainda não foi copiada
        if not os.path.exists(icon_path):
            unique_name = str(uuid.uuid4()) + os.path.splitext(icon_path)[1]
            dest_path = os.path.join('imagens', unique_name)
            shutil.copy(icon_path, dest_path)
        else:
            dest_path = icon_path
        
        button_frame = tk.Frame(self.second_tab_button_frame)  # Cria um frame para conter a imagem e o botão de texto
        button_frame.pack(side=tk.TOP, padx=5, pady=5)

        icon_label = tk.Label(button_frame)  # Label para exibir a imagem
        with Image.open(dest_path) as img:
            img = img.resize((40, 40), Image.LANCZOS)
            icon = ImageTk.PhotoImage(img)

        icon_label.icon = icon
        icon_label.config(image=icon_label.icon)
        icon_label.pack(side=tk.LEFT)

        text_button = tk.Button(button_frame, text=text, justify="center", anchor="center")  # Botão para exibir o texto
        text_button.pack(side=tk.LEFT, padx=5, pady=5)

        text_button.icon_path = dest_path  # Adiciona a propriedade icon_path ao botão
        if button_id is None:
            button_id = self.button_counter
            self.button_counter += 1

        text_button.id = button_id
        text_button.link = link
        text_button.premium_link = premium_link
        text_button.standard_link = standard_link

        tooltip_text = f"ID: {text_button.id}\nLink: {link}"
        text_button.tooltip = ToolTip(text_button, tooltip_text)

        menu = tk.Menu(text_button, tearoff=0)
        menu.add_command(label="Editar script", command=lambda: self.edit_link(text_button))
        menu.add_command(label="Abrir pasta", command=lambda: self.open_button_folder(text_button))
        menu.add_command(label="Alterar ID", command=lambda: self.change_button_id(text_button))
        if premium_link is not None:
            menu.add_command(label="IP Premium", command=lambda: self.run_as_admin(premium_link))
        if standard_link is not None:
            menu.add_command(label="IP Standard", command=lambda: self.run_as_admin(standard_link))
        menu.add_command(label="Deletar servidor", command=lambda: self.delete_button(text_button))
        text_button.bind("<Button-3>", lambda event: menu.post(event.x_root, event.y_root))

        text_button.config(command=lambda: self.run_as_admin(text_button.link))

        self.buttons.append(text_button)
        self.reorder_buttons_by_id()
        self.update_button_widths()

#LOGICA PARA OS BOTÕES DA PARTE INFERIOR DAS ABAS 1 E 2.
    def open_folder(self, path):
        os.startfile(path)

    def finaliza_cmd(self):
        os.startfile(self.os_letter("Dropbox Compartilhado/AmazonWS/Auto Iniciar meus VPS/Scripts Locais/Finaliza_CMD.bat"))
    
    def open_useall(self):
        os.startfile(self.os_letter(r"Dropbox Compartilhado\AmazonWS\Oracle Ubuntu 22.04 Instance 3 ARM/xubuntu 22.04.rdp"))

    def load_buttons(self):
        if os.path.isfile("buttons.json"):
            with open("buttons.json", "r") as f:
                buttons_data = json.load(f)
                for button_data in buttons_data:
                    premium_link = button_data.get("premium_link")  # Adicione esta linha
                    standard_link = button_data.get("standard_link")  # Adicione esta linha

                    if button_data.get("tab") == 2:
                        self.refresh_button_to_tab2(button_data["icon_path"], button_data["text"], button_data["link"], button_data["id"], premium_link, standard_link)
                    else:
                        self.refresh_button(button_data["icon_path"], button_data["text"], button_data["link"], button_data["id"], premium_link, standard_link)  # Modifique esta linha

                self.reorder_buttons_by_id()  # Ordena os botões após carregá-los
                self.update_button_widths()  # Atualiza a largura dos botões após carregá-los

#LOGICA PARA SALVAR BOTÕES EM AMBAS AS ABAS 1 E 2.
    def save_buttons(self):
        # Lista para armazenar os dados dos botões a serem salvos
        buttons_data = []

        # Determinar o índice da aba atual
        current_tab_index = self.notebook.index(self.notebook.select())

        # Carregar dados existentes se o arquivo já existir
        if os.path.exists("buttons.json"):
            with open("buttons.json", "r") as f:
               buttons_data = json.load(f)

        # Lista para armazenar icon_path dos botões existentes no arquivo JSON
        existing_button_icon_paths = [button["icon_path"] for button in buttons_data]

        for button in self.buttons:
            if hasattr(button, 'icon_path'):
                # Verificar se o botão já está no arquivo JSON antes de adicioná-lo novamente
                if button.icon_path not in existing_button_icon_paths:
                    # Determinar o índice da aba para o novo botão
                    if current_tab_index == 1:  # Índice 1 representa a segunda aba
                        tab = 2
                    else:
                        tab = 1
                    # Criar dados do botão para adicionar à lista
                    button_data = {
                        "id": button.id,
                        "icon_path": button.icon_path,
                        "text": button.cget("text"),
                        "link": button.link,
                        "premium_link": button.premium_link,  # Adicione esta linha
                        "standard_link": button.standard_link,  # Adicione esta linha
                        "tab": tab
                    }
                    buttons_data.append(button_data)

        # Salvar os dados atualizados de botões no arquivo JSON
        with open("buttons.json", "w") as f:
            json.dump(buttons_data, f, indent=4)  # indent para formatação legível

#LOGICA PARA ADICIONAR BOTÕES A PRIMEIRA ABA.
    def add_new_button(self):
        dialog = AddButtonDialog(self.master, self.top)
        self.master.wait_window(dialog.top)
        if dialog.button_info:
            # Atribuir um novo ID único para o botão
            button_id = self.button_counter
            self.button_counter += 1
            
            # Adicionar o botão à segunda aba
            self.add_button(dialog.button_info['icon'], dialog.button_info['text'], dialog.button_info['link'],
                                    premium_link=dialog.button_info.get('premium_link'),
                                    standard_link=dialog.button_info.get('standard_link'),
                                    button_id=button_id)
            self.save_buttons()  # Salva os botões após adicionar um novo

    def add_button(self, icon_path, text, link, button_id, premium_link=None, standard_link=None):
        # Copia a imagem para a pasta "imagens" e gera um nome único
        unique_name = str(uuid.uuid4()) + os.path.splitext(icon_path)[1]
        dest_path = os.path.join('imagens', unique_name)
        shutil.copy(icon_path, dest_path)

        button_frame = tk.Frame(self.button_frame)  # Cria um frame para conter a imagem e o botão de texto
        button_frame.pack(side=tk.TOP, padx=5, pady=5)

        icon_label = tk.Label(button_frame)  # Label para exibir a imagem
        with Image.open(dest_path) as img:
            img = img.resize((40, 40), Image.LANCZOS)
            icon = ImageTk.PhotoImage(img)

        icon_label.icon = icon
        icon_label.config(image=icon_label.icon)
        icon_label.pack(side=tk.LEFT)

        text_button = tk.Button(button_frame, text=text, justify="center", anchor="center")  # Botão para exibir o texto
        text_button.pack(side=tk.LEFT, padx=5, pady=5)

        text_button.icon_path = dest_path  # Adiciona a propriedade icon_path ao botão
        if button_id is None:
            button_id = self.button_counter
            self.button_counter += 1

        text_button.id = button_id
        text_button.link = link
        text_button.premium_link = premium_link
        text_button.standard_link = standard_link

        tooltip_text = f"ID: {text_button.id}\nLink: {link}"
        text_button.tooltip = ToolTip(text_button, tooltip_text)

        menu = tk.Menu(text_button, tearoff=0)
        menu.add_command(label="Editar script", command=lambda: self.edit_link(text_button))
        menu.add_command(label="Abrir pasta", command=lambda: self.open_button_folder(text_button))
        menu.add_command(label="Alterar ID", command=lambda: self.change_button_id(text_button))
        if premium_link is not None:
            menu.add_command(label="IP Premium", command=lambda: self.run_as_admin(premium_link))
        if standard_link is not None:
            menu.add_command(label="IP Standard", command=lambda: self.run_as_admin(standard_link))
        menu.add_command(label="Deletar servidor", command=lambda: self.delete_button(text_button))
        
        text_button.bind("<Button-3>", lambda event: menu.post(event.x_root, event.y_root))

        text_button.config(command=lambda: self.run_as_admin(text_button.link))

        self.buttons.append(text_button)
        self.reorder_buttons_by_id()
        self.update_button_widths()

    def refresh_button(self, icon_path, text, link, button_id, premium_link=None, standard_link=None):
        # Copia a imagem para a pasta "imagens" e gera um nome único apenas se ainda não foi copiada
        if not os.path.exists(icon_path):
            unique_name = str(uuid.uuid4()) + os.path.splitext(icon_path)[1]
            dest_path = os.path.join('imagens', unique_name)
            shutil.copy(icon_path, dest_path)
        else:
            dest_path = icon_path
        
        button_frame = tk.Frame(self.button_frame)  # Cria um frame para conter a imagem e o botão de texto
        button_frame.pack(side=tk.TOP, padx=5, pady=5)

        icon_label = tk.Label(button_frame)  # Label para exibir a imagem
        with Image.open(dest_path) as img:
            img = img.resize((40, 40), Image.LANCZOS)
            icon = ImageTk.PhotoImage(img)

        icon_label.icon = icon
        icon_label.config(image=icon_label.icon)
        icon_label.pack(side=tk.LEFT)

        text_button = tk.Button(button_frame, text=text, justify="center", anchor="center")  # Botão para exibir o texto
        text_button.pack(side=tk.LEFT, padx=5, pady=5)

        text_button.icon_path = dest_path  # Adiciona a propriedade icon_path ao botão
        if button_id is None:
            button_id = self.button_counter
            self.button_counter += 1

        text_button.id = button_id
        text_button.link = link
        text_button.premium_link = premium_link
        text_button.standard_link = standard_link

        tooltip_text = f"ID: {text_button.id}\nLink: {link}"
        text_button.tooltip = ToolTip(text_button, tooltip_text)

        menu = tk.Menu(text_button, tearoff=0)
        menu.add_command(label="Editar script", command=lambda: self.edit_link(text_button))
        menu.add_command(label="Abrir pasta", command=lambda: self.open_button_folder(text_button))
        menu.add_command(label="Alterar ID", command=lambda: self.change_button_id(text_button))        
        if premium_link is not None:
            menu.add_command(label="IP Premium", command=lambda: self.run_as_admin(premium_link))
        if standard_link is not None:
            menu.add_command(label="IP Standard", command=lambda: self.run_as_admin(standard_link))
        menu.add_command(label="Deletar servidor", command=lambda: self.delete_button(text_button))
            
        text_button.bind("<Button-3>", lambda event: menu.post(event.x_root, event.y_root))
        
        text_button.config(command=lambda: self.run_as_admin(text_button.link))

        self.buttons.append(text_button)
        self.reorder_buttons_by_id()
        self.update_button_widths()

#LOGICA PARA ATUALIZAR LARGURA, EDITAR LINKS, ABRIR PASTAS, DELETAR E ATUALIZAR BOTÕES DAS ABAS 1 E 2.
    def update_button_widths(self):
        if self.buttons:  # Verifica se a lista de botões não está vazia
            max_chars = max(len(button.cget("text")) for button in self.buttons)
            avg_char_width = 1  # Um valor aproximado da largura média de um caractere
            max_width = max_chars * avg_char_width + 3  # Adiciona um valor extra para garantir espaço suficiente
            for button in self.buttons:
                button.config(width=max_width)

    def edit_link(self, button):
        subprocess.Popen(['notepad', button.link])

    def open_button_folder(self, button):
        os.startfile(os.path.dirname(button.link))

    def open_config_dialog(self):
        dialog = ConfigDialog(self.master, self.color_map, self.top)
        self.master.wait_window(dialog.top)
        if dialog.updated_color_map:
            self.color_map = dialog.updated_color_map
            self.save_color_map()

    def delete_button(self, button):
        # Remove a imagem associada ao botão
        if os.path.exists(button.icon_path):
            os.remove(button.icon_path)

        # Encontre o frame associado ao botão
        for widget in button.master.winfo_children():
            widget.destroy()
        button.master.destroy()
    
        # Remova o botão da lista de botões
        self.buttons.remove(button)
    
        # Atualiza a largura dos botões
        self.update_button_widths()
    
       # Salva os botões atualizados
        self.resave_buttons()

    def resave_buttons(self): #Função de salvar exclusiva para delete_buttons
        # Lista para armazenar os dados dos botões a serem salvos
        buttons_data = []

        # Determinar o índice da aba atual
        current_tab_index = self.notebook.index(self.notebook.select())

        # Carregar dados existentes se o arquivo já existir
        if os.path.exists("buttons.json"):
            with open("buttons.json", "r") as f:
                buttons_data = json.load(f)

        # Lista para armazenar icon_path dos botões existentes no arquivo JSON
        existing_button_icon_paths = [button["icon_path"] for button in buttons_data]

        # Lista para armazenar icon_path dos botões atuais na interface
        current_button_icon_paths = [button.icon_path for button in self.buttons if hasattr(button, 'icon_path')]

        # Remover botões deletados do JSON
        buttons_data = [button for button in buttons_data if button["icon_path"] in current_button_icon_paths]

        for button in self.buttons:
            if hasattr(button, 'icon_path'):
                # Verificar se o botão já está no arquivo JSON antes de adicioná-lo novamente
                if button.icon_path not in existing_button_icon_paths:
                    # Determinar o índice da aba para o novo botão
                    if current_tab_index == 1:  # Índice 1 representa a segunda aba
                        tab = 2
                    else:
                        tab = 1
                    # Criar dados do botão para adicionar à lista
                    button_data = {
                        "id": button.id,
                        "icon_path": button.icon_path,
                        "text": button.cget("text"),
                        "link": button.link,
                        "premium_link": button.premium_link,  # Adicione esta linha
                        "standard_link": button.standard_link,  # Adicione esta linha
                        "tab": tab
                    }
                    buttons_data.append(button_data)

        # Salvar os dados atualizados de botões no arquivo JSON
        with open("buttons.json", "w") as f:
            json.dump(buttons_data, f, indent=4)  # indent para formatação legível

    def atualiza_all_buttons(self):
        # Itera sobre todos os botões e seus frames
        for button in self.buttons:
            button_frame = button.master
            # Destroi todos os widgets dentro do frame
            for widget in button_frame.winfo_children():
                widget.destroy()
            # Destroi o próprio frame
            button_frame.destroy()

        # Limpa a lista de botões
        self.buttons.clear()
    
        # Atualiza a largura dos botões
        self.update_button_widths()
    
        # Salva os botões atualizados
        self.load_buttons()

# METODO PARA DESLIGAR OS VPS
    def poweroff_vps_vpn(self):
        if hasattr(self, 'ssh_vps_vpn_client') and self.ssh_vps_vpn_client is not None:
            try:
                # Executa o comando sudo poweroff via SSH
                self.ssh_vps_vpn_client.exec_command("sudo poweroff")
            except Exception as e:
                print(f"Erro ao tentar desligar o VPN Client: {e}")
                pass

    def poweroff_vps_jogo(self):
        if hasattr(self, 'ssh_vps_jogo_client') and self.ssh_vps_jogo_client is not None:
            try:
                # Executa o comando sudo poweroff via SSH
                self.ssh_vps_jogo_client.exec_command("sudo poweroff")
            except Exception as e:
                print(f"Erro ao tentar desligar o Jogo Client: {e}")
                pass


#LOGICA PARA FUNÇÃO QUE EXECUTA OS LINKS DOS BOTÕES ADICIONADOS NAS ABAS 1 E 2.
    def run_as_admin(self, file_path):
        # Verifica se o arquivo é um .bat
        if not file_path.lower().endswith('.bat'):
            # Executa o arquivo normalmente sem abrir a janela de saída
            subprocess.Popen(shlex.split(f'"{file_path}"'), shell=True)
            return
        
        # Nova janela para mostrar a saída do script
        output_window = tk.Toplevel(self.master)
        output_window.title("Visualizador de Scripts")

        # Adiciona a lógica para salvar a posição da janela quando ela for fechada
        output_window.protocol("WM_DELETE_WINDOW", lambda: self.save_output_position(output_window) or output_window.destroy())

        # Carregar a posição salva
        self.load_output_position(output_window)
    
        # Frames para dividir a tela horizontalmente
        top_frame = tk.Frame(output_window)
        top_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    
        bottom_frame = tk.Frame(output_window)
        bottom_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # TextAreas para as saídas
        colored_text_area = scrolledtext.ScrolledText(top_frame, wrap=tk.WORD, width=100, height=15, state=tk.DISABLED, bg="black", fg="lightgray")
        colored_text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        colored_text_area.tag_config('inactivity', foreground='red')  # Por exemplo, cor vermelha

        uncolored_text_area = scrolledtext.ScrolledText(bottom_frame, wrap=tk.WORD, width=100, height=15, state=tk.DISABLED, bg="black", fg="lightgray")
        uncolored_text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        uncolored_text_area.tag_config('inactivity', foreground='red')  # Por exemplo, cor vermelha

        # Definindo tags de cores dinamicamente
        for value, color in self.color_map.items():
            colored_text_area.tag_config(value, foreground=color)

        # Botão para fechar a janela e executar o script de finalização
        def close_window_and_finalize():
            self.save_output_position(output_window)
            output_window.destroy()
            self.finaliza_cmd()

        close_button = tk.Button(output_window, text="Fechar", command=close_window_and_finalize)
        close_button.pack(side=tk.BOTTOM, padx=10, pady=10)

        # Arquivo temporário para redirecionar a saída do processo
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file_path = temp_file.name
        temp_file.close()

        # Executa o script e redireciona a saída para o arquivo temporário
        command = f'"{file_path}" > "{temp_file_path}" 2>&1'
        process = subprocess.Popen(shlex.split(command), shell=True)

        def read_temp_file(file_path, colored_widget, uncolored_widget):
            last_position = 0
            inactivity_timeout = 20000  # Tempo em milissegundos (20 segundos) para considerar inatividade
            inactivity_start = None

            while True:
                with open(file_path, 'r') as f:
                    f.seek(last_position)
                    new_text = f.read()
                    last_position = f.tell()
                    if new_text:
                        colored_widget.config(state=tk.NORMAL)
                        uncolored_widget.config(state=tk.NORMAL)

                        for line in new_text.splitlines():
                            tag_found = False
                            if "INICIO DO SCRIPT" in line:
                                self.script_finished = True
                                self.update_general_status()

                            if "PROCESSO CONCLUIDO" in line:
                                self.start_monitoring_delay()

                            if "DESLIGAMENTO CONCLUIDO" in line:
                                self.verificar_vm = False

                            if "DESLIGAR VPS VPN" in line:
                                self.poweroff_vps_vpn()

                            if "DESLIGAR VPS JOGO" in line:
                                self.poweroff_vps_jogo()

                            # Verifica se a linha começa com "Conectando" e atualizando status da conexão com o servidor correspondente.
                            if line.startswith("Conectando"):
                                connection_target = line[len("Conectando"):].strip()
                                with open("conection_status.txt", "w") as connection_file:
                                    connection_file.write(f"Conectando a {connection_target}\n")
                                    connection_file.write(f"Conectado a {connection_target}\n")
                    
                            for value, color in self.color_map.items():
                                if line.startswith(value):
                                    colored_widget.insert(tk.END, line + '\n', value)
                                    tag_found = True
                                    break
                            if not tag_found:
                                uncolored_widget.insert(tk.END, line + '\n')

                        colored_widget.config(state=tk.DISABLED)
                        uncolored_widget.config(state=tk.DISABLED)
                        colored_widget.see(tk.END)
                        uncolored_widget.see(tk.END)

                        inactivity_start = None  # Reinicia o tempo de inatividade
                    else:
                        if inactivity_start is None:
                            inactivity_start = time.time()  # Marca o início da inatividade
                        elif (time.time() - inactivity_start) * 1000 > inactivity_timeout:
                            colored_widget.config(state=tk.NORMAL)
                            colored_widget.insert(tk.END, "\nLoop terminou devido à inatividade.\n", 'inactivity')
                            colored_widget.config(state=tk.DISABLED)
                            colored_widget.see(tk.END)

                            uncolored_widget.config(state=tk.NORMAL)
                            uncolored_widget.insert(tk.END, "\nLoop terminou devido à inatividade.\n", 'inactivity')
                            uncolored_widget.config(state=tk.DISABLED)
                            uncolored_widget.see(tk.END)
                
                            break  # Sai do loop após o tempo de inatividade

                colored_widget.update_idletasks()
                uncolored_widget.update_idletasks()
                colored_widget.after(2)  # Espera 2ms antes de verificar novamente
                uncolored_widget.after(2)  # Espera 2ms antes de verificar novamente

            # Remover o arquivo temporário após a leitura completa
            os.remove(file_path)

        # Cria um thread para leitura assíncrona do arquivo temporário
        threading.Thread(target=read_temp_file, args=(temp_file_path, colored_text_area, uncolored_text_area), daemon=True).start()

    def append_colored_text(self, text_widget, text):
        for line in text.splitlines():
            tag = None
            for value in self.color_map.keys():
                if line.startswith(value):
                    tag = value
                    break
            
            if tag:
                text_widget.insert(tk.END, line + '\n', tag)
            else:
                text_widget.insert(tk.END, line + '\n')

    def load_output_position(self, window):
        if os.path.isfile("output_position.json"):
            with open("output_position.json", "r") as f:
                position = json.load(f)
                window.geometry("+{}+{}".format(position["x"], position["y"]))

    def save_output_position(self, window):
        position = {
            "x": window.winfo_x(),
            "y": window.winfo_y()
        }
        with open("output_position.json", "w") as f:
            json.dump(position, f)

    def on_close_output(self, window):
        self.save_output_position(window)
        window.destroy()

#LOGICA PARA MUDAR ID DOS BOTÕES DE ABAS 1 E 2.
    def change_button_id(self, button):
        new_id = simpledialog.askinteger("Alterar ID", "Digite o novo ID para o botão:")
        if new_id is not None:
            old_id = button.id
            button.id = new_id
            tooltip_text = f"ID: {button.id}\nLink: {button.link}"
            button.tooltip.update_text(tooltip_text)
            messagebox.showinfo("ID Alterado", f"ID do botão '{button.cget('text')}' alterado de {old_id} para {new_id}.")
            #self.sort_buttons()  # Ordena os botões após alterar o ID
            self.reresave_buttons()  # Salva os botões após alterar a ordem
            self.reorder_buttons_by_id()  # Ordena os botões após alterar o ID
            self.atualiza_all_buttons()

    def reresave_buttons(self): #Função de salvar exclusiva para função change_button_id
        # Lista para armazenar os dados dos botões a serem salvos
        buttons_data = []

        # Determinar o índice da aba atual
        current_tab_index = self.notebook.index(self.notebook.select())

        # Carregar dados existentes se o arquivo já existir
        if os.path.exists("buttons.json"):
            with open("buttons.json", "r") as f:
                buttons_data = json.load(f)

        # Lista para armazenar icon_path dos botões existentes no arquivo JSON
        existing_button_icon_paths = [button["icon_path"] for button in buttons_data]

        for button in self.buttons:
            if hasattr(button, 'icon_path'):
                # Verificar se o botão já está no arquivo JSON antes de adicioná-lo novamente
                if button.icon_path not in existing_button_icon_paths:
                    # Determinar o índice da aba para o novo botão
                    if current_tab_index == 1:  # Índice 1 representa a segunda aba
                        tab = 2
                    else:
                        tab = 1
                    # Criar dados do botão para adicionar à lista
                    button_data = {
                        "id": button.id,
                        "icon_path": button.icon_path,
                        "text": button.cget("text"),
                        "link": button.link,
                        "premium_link": button.premium_link,  # Adicione esta linha
                        "standard_link": button.standard_link,  # Adicione esta linha
                        "tab": tab
                    }
                    buttons_data.append(button_data)
                else:
                    # Atualizar dados do botão no arquivo JSON se ele já existir
                    for bd in buttons_data:
                        if bd["icon_path"] == button.icon_path:
                            bd["id"] = button.id
                            bd["text"] = button.cget("text")
                            bd["link"] = button.link
                            #bd["premium_link"] = button.premium_link
                            #bd["standard_link"] = button.standard_link

        # Salvar os dados atualizados de botões no arquivo JSON
        with open("buttons.json", "w") as f:
            json.dump(buttons_data, f, indent=4)  # indent para formatação legível

    def reorder_buttons_by_id(self, file_path="buttons.json"):
        try:
            # Abrir o arquivo JSON e carregar os dados existentes
            with open(file_path, "r") as f:
                buttons_data = json.load(f)
            
            # Ordenar os dados com base no campo 'id'
            buttons_data_sorted = sorted(buttons_data, key=lambda x: x['id'])

            # Escrever os dados ordenados de volta no arquivo JSON
            with open(file_path, "w") as f:
                json.dump(buttons_data_sorted, f, indent=4)  # indent para formatação legível

            #print(f"Arquivo '{file_path}' foi reordenado com sucesso pela chave 'id'.")

        except Exception as e:
            print(f"Erro ao reordenar arquivo '{file_path}': {e}")

    def sort_buttons(self):
        # Ordena a lista de botões com base no atributo 'id'
        self.buttons.sort(key=lambda button: button.id)
        
        # Reorganiza visualmente os botões na interface
        for button in self.buttons:
            button.pack_forget()  # Remove o botão da interface gráfica
            button.pack(side=tk.LEFT, padx=5, pady=5)  # Reinsere o botão ordenadamente

#JANELA DE CONFIGURAÇÃO DE CORES.
class ConfigDialog:
    def __init__(self, master, color_map, top):
        self.master = master
        self.top = tk.Toplevel(master)
        self.load_window_position()
        self.top.title("Configurações de Cores")
        # Bloqueia a interação com a janela master
        self.top.grab_set()

        # Define a janela como ativa
        self.top.focus_set()
        self.color_map = self.load_color_map()
        self.updated_color_map = None

        self.max_height = 400  

        # Frame principal para conter o scrollable_frame e os botões
        self.main_frame = tk.Frame(self.top, borderwidth=2, relief="ridge")
        self.main_frame.pack(fill="both", expand=True)

        # Canvas e scrollbar
        self.canvas = tk.Canvas(self.main_frame)
        self.scrollbar = tk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Adicionando conteúdo ao scrollable_frame
        self.colors_frame = tk.Frame(self.scrollable_frame)
        self.colors_frame.pack(padx=10, pady=10)

        self.entries = []

        for i, (value, color) in enumerate(self.color_map.items()):
            self.add_color_entry(i, value, color)

        self.new_value_entry = tk.Entry(self.colors_frame)
        self.new_value_entry.grid(row=len(self.entries), column=0, padx=5, pady=5)
        
        self.new_color_canvas = tk.Canvas(self.colors_frame, width=20, height=20, bg="white")
        self.new_color_canvas.grid(row=len(self.entries), column=1, padx=5, pady=5)
        
        tk.Button(self.colors_frame, text="Escolher Cor", command=self.choose_new_color).grid(row=len(self.entries), column=2, padx=5, pady=5)

        # Botões na parte inferior da janela
        button_frame = tk.Frame(self.top)
        button_frame.pack(side="bottom", pady=10)

        tk.Button(button_frame, text="Adicionar", command=self.add_new_value_and_reopen).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="Cancelar", command=self.cancel).pack(side=tk.LEFT, padx=10)

        self.new_color = None
        self.top.protocol("WM_DELETE_WINDOW", self.on_close)

        self.update_window_size()

        # Configurando eventos de rolagem do mouse
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        # Ajuste a visualização para mostrar o conteúdo no final
        self.canvas.yview_moveto(1.0)

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(-1 * int(event.delta/120), "units")

    def add_new_value_and_reopen(self):
        new_value = self.new_value_entry.get()
        new_color = self.new_color_canvas["bg"]
        if new_value and new_color != "white":
            self.add_color_entry(len(self.entries), new_value, new_color)
            self.new_value_entry.delete(0, tk.END)
            self.new_color_canvas.config(bg="white")
            self.save_and_reopen()
        else:
            messagebox.showwarning("Erro", "Por favor, preencha o campo 'Novo Valor' e escolha uma cor.")

    def save_and_reopen(self):
        self.save()
        self.top.destroy()
        ConfigDialog(self.master, self.updated_color_map, self.top)

    def load_window_position(self):
        if os.path.isfile("configdialog_position.json"):
            with open("configdialog_position.json", "r") as f:
                position = json.load(f)
                self.top.geometry("+{}+{}".format(position["x"], position["y"]))

    def save_window_position(self):
        position = {
            "x": self.top.winfo_x(),
            "y": self.top.winfo_y()
        }
        with open("configdialog_position.json", "w") as f:
            json.dump(position, f)

    def load_color_map(self):
        try:
            with open('color_map.json', 'r') as f:
                color_map = json.load(f)
        except FileNotFoundError:
            color_map = {}
        return color_map

    def add_color_entry(self, row, value, color):
        key_entry = tk.Entry(self.colors_frame)
        key_entry.grid(row=row, column=0, padx=5, pady=5)
        key_entry.insert(0, value)
        key_entry.row = row

        color_canvas = tk.Canvas(self.colors_frame, width=20, height=20, bg=color)
        color_canvas.grid(row=row, column=1, padx=5, pady=5)
        color_canvas.row = row
        
        choose_button = tk.Button(self.colors_frame, text="Escolher Cor", command=lambda e=color_canvas: self.choose_color(e))
        choose_button.grid(row=row, column=2, padx=5, pady=5)
        choose_button.row = row
        
        delete_button = tk.Button(self.colors_frame, text="Deletar", command=lambda: self.delete_value(row))
        delete_button.grid(row=row, column=3, padx=5, pady=5)
        delete_button.row = row
        
        self.entries.append((key_entry, color_canvas, choose_button, delete_button))
        self.update_window_size()

    def choose_color(self, canvas):
        color_code = colorchooser.askcolor(title="Escolher Cor")[1]
        if color_code:
            canvas.config(bg=color_code)

    def choose_new_color(self):
        color_code = colorchooser.askcolor(title="Escolher Cor")[1]
        if color_code:
            self.new_color_canvas.config(bg=color_code)

    def delete_value(self, row):
        self.entries = [(key_entry, color_canvas, choose_button, delete_button) for key_entry, color_canvas, choose_button, delete_button in self.entries if key_entry.row != row]
        
        for widget in self.colors_frame.grid_slaves():
            if hasattr(widget, 'row') and widget.row == row:
                widget.grid_forget()

        for i, (key_entry, color_canvas, choose_button, delete_button) in enumerate(self.entries):
            key_entry.grid(row=i, column=0, padx=5, pady=5)
            color_canvas.grid(row=i, column=1, padx=5, pady=5)
            choose_button.grid(row=i, column=2, padx=5, pady=5)
            delete_button.grid(row=i, column=3, padx=5, pady=5)
            key_entry.row = i
            color_canvas.row = i
            choose_button.row = i
            delete_button.row = i

        self.new_value_entry.grid(row=len(self.entries), column=0, padx=5, pady=5)
        self.new_color_canvas.grid(row=len(self.entries), column=1, padx=5, pady=5)
        tk.Button(self.colors_frame, text="Escolher Cor", command=self.choose_new_color).grid(row=len(self.entries), column=2, padx=5, pady=5)
        
        self.update_window_size()

    def save(self):
        self.updated_color_map = {key_entry.get(): color_canvas["bg"] for key_entry, color_canvas, _, _ in self.entries}
        self.write_to_file()

    def write_to_file(self):
        try:
            with open('color_map.json', 'w') as f:
                json.dump(self.updated_color_map, f, indent=4)
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível salvar o arquivo: {e}")

    def on_close(self):
        self.top.grab_release()
        self.save()
        self.save_window_position()
        self.top.destroy()

    def cancel(self):
        self.top.grab_release()
        self.top.destroy()

    def update_window_size(self):
        self.top.update_idletasks()
        current_height = self.scrollable_frame.winfo_height()
        if current_height > self.max_height:
            self.canvas.config(height=self.max_height)
        else:
            self.canvas.config(height=current_height)

#JANELA DE CONFIGURAÇÕES E GERENCIADOR DE ARQUIVOS.
class OMRManagerDialog:
    def __init__(self, master, ButtonManager):
        self.config_file = 'config.ini'  # Nome do arquivo de configuração fixo
        self.config = configparser.ConfigParser()  # Inicializa o configparser
        top = self.top = tk.Toplevel(master)
        self.master = master
        self.ButtonManager = ButtonManager  # Armazena a instância de ButtonManager
        self.load_window_position()
        self.top.title("Configurações do Gerenciador de VPS")

        # Bloqueia a interação com a janela master
        self.top.grab_set()

        # Define a janela como ativa
        self.top.focus_set()
        
        # Inicialização das abas
        self.tabs = ttk.Notebook(self.top)
        self.tabs.pack(expand=1, fill='both')

        # Primeira aba (conteúdo original)
        aba1 = ttk.Frame(self.tabs)
        self.tabs.add(aba1, text="Gerenciador de Arquivos")

        # Frame para os botões e textos descritivos
        button_frame = tk.Frame(aba1, borderwidth=1, relief=tk.RIDGE)
        button_frame.pack(side="left", padx=10, pady=10, anchor='w', fill=tk.BOTH)

        # Primeiro texto descritivo e botão
        tk.Label(button_frame, text="Seleciona arquivos .vdi antigos do OMR para mover:").pack(side=tk.TOP, anchor='w')
        tk.Button(button_frame, text="Mover Arquivos Antigos", command=self.select_files).pack(side=tk.TOP, anchor='w', padx=5, pady=5)

        # Espaço entre o primeiro botão e o segundo texto
        tk.Label(button_frame).pack(side=tk.TOP, pady=6)  # Espaço de 6 pixels entre os widgets

        # Segundo texto descritivo e botão
        tk.Label(button_frame, text="Copia, renomeia, compacta e move arquivos .vdi do OMR:").pack(side=tk.TOP, anchor='w')
        tk.Label(button_frame, text="Para ser usado ao atualizar ambos OMR.").pack(side=tk.TOP, anchor='w')
        tk.Button(button_frame, text="Executar processos para OpenMPTCP e OCI", command=self.perform_management_operations).pack(side=tk.TOP, anchor='w', padx=5, pady=5)

        # Espaço entre os botões
        tk.Label(button_frame).pack(side=tk.TOP, pady=6)  # Espaço de 6 pixels entre os widgets

        # Terceiro texto descritivo e botão
        tk.Label(button_frame, text="Extrai arquivo, renomeia e copia para OMR OCI:").pack(side=tk.TOP, anchor='w')
        tk.Label(button_frame, text="Para ser usado apenas para atualizar OMR OCI").pack(side=tk.TOP, anchor='w')
        tk.Button(button_frame, text="Executar processos para OCI", command=self.copy_to_oci).pack(side=tk.TOP, anchor='w', padx=5, pady=5)

        # Frame para os botões e textos descritivos à direita
        button_frame_right = tk.Frame(aba1, borderwidth=1, relief=tk.RIDGE)
        button_frame_right.pack(side="top", padx=10, pady=10, anchor='e', fill=tk.BOTH)

        # Primeiro botão
        tk.Label(button_frame_right, text="Edita script de alteração de UUID:").pack(side=tk.TOP, anchor='w')
        tk.Button(button_frame_right, text="Editar script", command=self.edit_uuid).pack(side=tk.TOP, anchor='w', padx=5, pady=5)

        # Espaço entre o primeiro botão e o segundo texto
        tk.Label(button_frame_right).pack(side=tk.TOP, pady=6)  # Espaço de 6 pixels entre os widgets

        # Segundo botão
        tk.Label(button_frame_right, text="Backup das Máquinas Virtuais:").pack(side=tk.TOP, anchor='w')
        tk.Button(button_frame_right, text="Executar backup", command=self.backup_virtualbox).pack(side=tk.TOP, anchor='w', padx=5, pady=5)

        # Espaço entre o segundo botão e o terceiro texto
        tk.Label(button_frame_right).pack(side=tk.TOP, pady=6)  # Espaço de 6 pixels entre os widgets

        # Terceiro botão
        tk.Label(button_frame_right, text="Editar arquivo de ajuda:").pack(side=tk.TOP, anchor='w')
        tk.Button(button_frame_right, text="Editar arquivo", command=self.editar_arquivo_ajuda).pack(side=tk.TOP, anchor='w', padx=5, pady=5)

        # Espaço entre o terceiro botão e o novo campo de entrada
        tk.Label(button_frame_right).pack(side=tk.TOP, pady=6)  # Espaço de 6 pixels entre os widgets

        # Novo campo de entrada para o URL
        self.url_label = tk.Label(button_frame_right, text="URL para o teste de provedores:")
        self.url_label.pack(side=tk.TOP, anchor='w')
        
        self.url_entry = tk.Entry(button_frame_right, width=50)
        self.url_entry.pack(side=tk.TOP, anchor='w', padx=5, pady=5)
        
        # Botão para salvar o novo URL
        self.save_url_button = tk.Button(button_frame_right, text="Salvar URL", command=self.save_provedor_url)
        self.save_url_button.pack(side=tk.TOP, anchor='w', padx=5, pady=5)

        # Carrega as configurações gerais
        self.load_provedor_url()

        # Botões na parte inferior da janela
        button_frame_bottom = tk.Frame(aba1)
        button_frame_bottom.pack(side="bottom", pady=10)

        # Segunda aba (Configurações de Ping)
        aba2 = ttk.Frame(self.tabs)
        self.tabs.add(aba2, text="Configurações de Ping")

        # Carregar a configuração do config.ini
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')

        # Inicializa a configuração de 'execute_initial_test'
        self.execute_initial_test_active = self.config.getboolean('general', 'execute_initial_test', fallback=True)

        # Frame com borda
        frame = tk.Frame(aba2, bd=2, borderwidth=1, relief=tk.RAISED)
        frame.pack(padx=10, pady=10, fill=tk.BOTH)

        # Carregar endereços
        self.load_addresses()

        # Labels VPS VPN
        tk.Label(frame, text="Endereço VPS VPN:").grid(row=0, column=0, sticky=tk.W)
        self.vps_vpn_entry = tk.Entry(frame, width=30)
        self.vps_vpn_entry.grid(row=0, column=1, padx=5, pady=5)
        self.vps_vpn_entry.insert(0, self.url_to_ping_vps_vpn or '')

        # Labels VPS VPN1
        tk.Label(frame, text="Endereço VPS VPN 1:").grid(row=0, column=2, sticky=tk.W)
        self.vps_vpn_1_entry = tk.Entry(frame, width=30)
        self.vps_vpn_1_entry.grid(row=0, column=3, padx=5, pady=5)
        self.vps_vpn_1_entry.insert(0, self.url_to_ping_vps_vpn_1 or '')

        # Labels VPS JOGO
        tk.Label(frame, text="Endereço VPS JOGO:").grid(row=1, column=0, sticky=tk.W)
        self.vps_jogo_entry = tk.Entry(frame, width=30)
        self.vps_jogo_entry.grid(row=1, column=1, padx=5, pady=5)
        self.vps_jogo_entry.insert(0, self.url_to_ping_vps_jogo or '')

        # Labels VPS JOGO1
        tk.Label(frame, text="Endereço VPS JOGO 1:").grid(row=1, column=2, sticky=tk.W)
        self.vps_jogo_1_entry = tk.Entry(frame, width=30)
        self.vps_jogo_1_entry.grid(row=1, column=3, padx=5, pady=5)
        self.vps_jogo_1_entry.insert(0, self.url_to_ping_vps_jogo_1 or '')

        # Labels OMR VPN
        tk.Label(frame, text="Endereço OMR VPN:").grid(row=2, column=0, sticky=tk.W)
        self.omr_vpn_entry = tk.Entry(frame, width=30)
        self.omr_vpn_entry.grid(row=2, column=1, padx=5, pady=5)
        self.omr_vpn_entry.insert(0, self.url_to_ping_omr_vpn or '')

        # Labels OMR JOGO
        tk.Label(frame, text="Endereço OMR JOGO:").grid(row=3, column=0, sticky=tk.W)
        self.omr_jogo_entry = tk.Entry(frame, width=30)
        self.omr_jogo_entry.grid(row=3, column=1, padx=5, pady=5)
        self.omr_jogo_entry.insert(0, self.url_to_ping_omr_jogo or '')

        # Botão para alterar o estado de execute_initial_test
        self.toggle_initial_test_button = tk.Button(
            frame, 
            text="Ligar/Desligar teste de ping", 
            command=self.toggle_and_save_execute_initial_test  # Agora o botão também salva e envia para ButtonManager
        )
        self.toggle_initial_test_button.grid(row=4, column=0, padx=5, pady=5)

        # Label para mostrar o estado de execute_initial_test
        self.execute_test_status_label = tk.Label(frame, text="")
        self.execute_test_status_label.grid(row=4, column=1, padx=5, pady=5)
        self.update_execute_test_status_label()

        # Rótulo de texto logo abaixo dos frames
        tk.Label(frame, text="Liga ou desliga o teste de ping nos IPs do OMR VPN/JOGO enquanto estiver com status conectado.", anchor=tk.W).grid(row=5, column=0, columnspan=5, pady=0, sticky=tk.W)

        save_button = tk.Button(frame, text="Salvar", command=self.save_addresses)
        save_button.grid(row=6, column=0, columnspan=4, pady=10)

        # Terceira aba Configurações de VMs.
        aba3 = ttk.Frame(self.tabs)
        self.tabs.add(aba3, text="Configurações de VMs")

        # Frame para configurações de VMs na aba 3
        frame_vm_config = tk.Frame(aba3, borderwidth=1, relief=tk.RAISED)
        frame_vm_config.pack(padx=10, pady=10, fill=tk.BOTH)

        tk.Label(frame_vm_config, text="Nome da VM VPN:").grid(row=0, column=0, sticky=tk.W)
        self.vm_vpn_name_entry = tk.Entry(frame_vm_config, width=30)
        self.vm_vpn_name_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(frame_vm_config, text="Nome da VM JOGO:").grid(row=1, column=0, sticky=tk.W)
        self.vm_jogo_name_entry = tk.Entry(frame_vm_config, width=30)
        self.vm_jogo_name_entry.grid(row=1, column=1, padx=5, pady=5)

        save_button = tk.Button(frame_vm_config, text="Salvar", command=self.save_vm_names)
        save_button.grid(row=2, column=0, columnspan=2, pady=10)

        # Botões para Ligar e Desligar o monitoramento
        start_monitoring_button = tk.Button(frame_vm_config, text="Ligar Monitoramento", command=self.start_monitoring)
        start_monitoring_button.grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)

        stop_monitoring_button = tk.Button(frame_vm_config, text="Desligar Monitoramento", command=self.stop_monitoring)
        stop_monitoring_button.grid(row=4, column=1, padx=5, pady=5, sticky=tk.E)

        # Label para mostrar o status do monitoramento
        self.monitoring_status_label = tk.Label(frame_vm_config, text="Monitoramento: Desligado", fg="red")
        self.monitoring_status_label.grid(row=3, column=0, columnspan=2, pady=10)

        # Carregar nomes das VMs ao inicializar
        self.load_vm_names()

        # Verifica o estado do monitoramento das VMs
        self.update_monitoring_status()

        # Quarta aba (Configurações de Usuário e Senha)
        aba4 = ttk.Frame(self.tabs)
        self.tabs.add(aba4, text="Configurações de SSH")

        # Frame principal para configurações de usuário na aba 4
        frame_user_config = tk.Frame(aba4, borderwidth=1, relief=tk.RAISED)
        frame_user_config.pack(padx=10, pady=10, fill=tk.BOTH)

        # Frame OMR VPN
        frame_omr_vpn = tk.Frame(frame_user_config, borderwidth=1, relief=tk.RAISED)
        frame_omr_vpn.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)

        tk.Label(frame_omr_vpn, text="Host OMR VPN:").grid(row=0, column=0, sticky=tk.W)
        self.host_vpn_entry = tk.Entry(frame_omr_vpn, width=30)
        self.host_vpn_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        self.port_vpn_entry = tk.Entry(frame_omr_vpn, width=7)
        self.port_vpn_entry.grid(row=0, column=2, padx=5, pady=5, sticky=tk.E)

        tk.Label(frame_omr_vpn, text="Usuário OMR VPN:").grid(row=1, column=0, sticky=tk.W)
        self.user_vpn_entry = tk.Entry(frame_omr_vpn, width=30)
        self.user_vpn_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(frame_omr_vpn, text="Senha OMR VPN:").grid(row=2, column=0, sticky=tk.W)
        self.password_vpn_entry = tk.Entry(frame_omr_vpn, show='*', width=30)
        self.password_vpn_entry.grid(row=2, column=1, padx=5, pady=5)

        # Frame OMR JOGO
        frame_omr_jogo = tk.Frame(frame_user_config, borderwidth=1, relief=tk.RAISED)
        frame_omr_jogo.grid(row=0, column=3, padx=5, pady=5, sticky=tk.W)

        tk.Label(frame_omr_jogo, text="Host OMR JOGO:").grid(row=0, column=0, sticky=tk.W)
        self.host_jogo_entry = tk.Entry(frame_omr_jogo, width=30)
        self.host_jogo_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        self.port_jogo_entry = tk.Entry(frame_omr_jogo, width=7)
        self.port_jogo_entry.grid(row=0, column=2, padx=5, pady=5, sticky=tk.E)

        tk.Label(frame_omr_jogo, text="Usuário OMR JOGO:").grid(row=1, column=0, sticky=tk.W)
        self.user_jogo_entry = tk.Entry(frame_omr_jogo, width=30)
        self.user_jogo_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(frame_omr_jogo, text="Senha OMR JOGO:").grid(row=2, column=0, sticky=tk.W)
        self.password_jogo_entry = tk.Entry(frame_omr_jogo, show='*', width=30)
        self.password_jogo_entry.grid(row=2, column=1, padx=5, pady=5)

        # Frame VPS VPN
        frame_vps_vpn = tk.Frame(frame_user_config, borderwidth=1, relief=tk.RAISED)
        frame_vps_vpn.grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)

        tk.Label(frame_vps_vpn, text="Host VPS VPN:").grid(row=0, column=0, sticky=tk.W)
        self.host_vps_vpn_entry = tk.Entry(frame_vps_vpn, width=30)
        self.host_vps_vpn_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        self.port_vps_vpn_entry = tk.Entry(frame_vps_vpn, width=7)
        self.port_vps_vpn_entry.grid(row=0, column=2, padx=5, pady=5, sticky=tk.E)

        tk.Label(frame_vps_vpn, text="Usuário VPS VPN:").grid(row=1, column=0, sticky=tk.W)
        self.user_vps_vpn_entry = tk.Entry(frame_vps_vpn, width=30)
        self.user_vps_vpn_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(frame_vps_vpn, text="Senha VPS VPN:").grid(row=2, column=0, sticky=tk.W)
        self.password_vps_vpn_entry = tk.Entry(frame_vps_vpn, show='*', width=30)
        self.password_vps_vpn_entry.grid(row=2, column=1, padx=5, pady=5)

        # Frame VPS JOGO
        frame_vps_jogo = tk.Frame(frame_user_config, borderwidth=1, relief=tk.RAISED)
        frame_vps_jogo.grid(row=3, column=3, padx=5, pady=5, sticky=tk.W)

        tk.Label(frame_vps_jogo, text="Host VPS JOGO:").grid(row=0, column=0, sticky=tk.W)
        self.host_vps_jogo_entry = tk.Entry(frame_vps_jogo, width=30)
        self.host_vps_jogo_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        self.port_vps_jogo_entry = tk.Entry(frame_vps_jogo, width=7)
        self.port_vps_jogo_entry.grid(row=0, column=2, padx=5, pady=5, sticky=tk.E)

        tk.Label(frame_vps_jogo, text="Usuário VPS JOGO:").grid(row=1, column=0, sticky=tk.W)
        self.user_vps_jogo_entry = tk.Entry(frame_vps_jogo, width=30)
        self.user_vps_jogo_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(frame_vps_jogo, text="Senha VPS JOGO:").grid(row=2, column=0, sticky=tk.W)
        self.password_vps_jogo_entry = tk.Entry(frame_vps_jogo, show='*', width=30)
        self.password_vps_jogo_entry.grid(row=2, column=1, padx=5, pady=5)

        # Rótulo de texto logo abaixo dos frames
        tk.Label(frame_user_config, text="Os arquivos das chaves privadas devem ser salvos na pasta 'ssh_keys' na raiz do programa.", anchor=tk.W).grid(row=4, column=0, columnspan=5, pady=0, sticky=tk.W)

        # Botão para abrir a pasta 'ssh_keys'
        open_folder_button = tk.Button(frame_user_config, text="Abrir Pasta 'ssh_keys'", command=self.open_ssh_keys_folder)
        open_folder_button.grid(row=5, column=0, columnspan=2, pady=10, sticky=tk.W)

        # Rótulo de texto acima do botão alinhado à esquerda
        tk.Label(frame_user_config, text="", anchor=tk.W).grid(row=6, column=0, columnspan=5, pady=20, sticky=tk.W)
        tk.Label(frame_user_config, text="Marcar esta opção irá criar um usuario e senha no OMR de acordo com as configurações definidas acima.", anchor=tk.W).grid(row=8, column=0, columnspan=5, pady=0, sticky=tk.W)

        # Adiciona uma caixa de seleção para criar usuário SSH
        self.criar_usuario_ssh_var = tk.BooleanVar(value=self.ButtonManager.criar_usuario_ssh)
        criar_usuario_ssh_checkbox = tk.Checkbutton(frame_user_config, text="Criar usuário SSH automaticamente",
                                            variable=self.criar_usuario_ssh_var, command=self.toggle_criar_usuario_ssh)
        criar_usuario_ssh_checkbox.grid(row=9, column=0, columnspan=2, pady=10)

        save_button = tk.Button(frame_user_config, text="Salvar", command=self.save_user_credentials)
        save_button.grid(row=11, column=0, columnspan=2, pady=10)

        # Carregar informações do usuário ao inicializar
        self.load_user_credentials()

        # Adiciona a quinta aba (Configurações de Proxy)
        aba5 = ttk.Frame(self.tabs)
        self.tabs.add(aba5, text="Configurações de Proxy")

        # Frame principal para configurações de Proxy na aba 5
        frame_ssh_bind = tk.Frame(aba5, borderwidth=1, relief=tk.RAISED)
        frame_ssh_bind.pack(padx=10, pady=10, fill=tk.BOTH)

        # Frame SSH VPS VPN Bind
        frame_vps_vpn_bind = tk.Frame(frame_ssh_bind, borderwidth=1, relief=tk.RAISED)
        frame_vps_vpn_bind.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)

        tk.Label(frame_vps_vpn_bind, text="Host via VPS VPN:").grid(row=0, column=0, sticky=tk.W)
        self.host_vps_vpn_bind_entry = tk.Entry(frame_vps_vpn_bind, width=30)
        self.host_vps_vpn_bind_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        self.port_vps_vpn_bind_entry = tk.Entry(frame_vps_vpn_bind, width=7)
        self.port_vps_vpn_bind_entry.grid(row=0, column=2, padx=5, pady=5, sticky=tk.E)

        tk.Label(frame_vps_vpn_bind, text="Usuário:").grid(row=1, column=0, sticky=tk.W)
        self.user_vps_vpn_bind_entry = tk.Entry(frame_vps_vpn_bind, width=30)
        self.user_vps_vpn_bind_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(frame_vps_vpn_bind, text="Senha:").grid(row=2, column=0, sticky=tk.W)
        self.password_vps_vpn_bind_entry = tk.Entry(frame_vps_vpn_bind, show='*', width=30)
        self.password_vps_vpn_bind_entry.grid(row=2, column=1, padx=5, pady=5)

        tk.Label(frame_vps_vpn_bind, text="Porta Local:").grid(row=3, column=0, sticky=tk.W)
        self.port_local_vps_vpn_bind_entry = tk.Entry(frame_vps_vpn_bind, width=7)
        self.port_local_vps_vpn_bind_entry.grid(row=3, column=1, padx=5, pady=5)

        # Frame SSH VPS JOGO Bind
        frame_vps_jogo_bind = tk.Frame(frame_ssh_bind, borderwidth=1, relief=tk.RAISED)
        frame_vps_jogo_bind.grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)

        tk.Label(frame_vps_jogo_bind, text="Host via VPS JOGO:").grid(row=0, column=0, sticky=tk.W)
        self.host_vps_jogo_bind_entry = tk.Entry(frame_vps_jogo_bind, width=30)
        self.host_vps_jogo_bind_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        self.port_vps_jogo_bind_entry = tk.Entry(frame_vps_jogo_bind, width=7)
        self.port_vps_jogo_bind_entry.grid(row=0, column=2, padx=5, pady=5, sticky=tk.E)

        tk.Label(frame_vps_jogo_bind, text="Usuário:").grid(row=1, column=0, sticky=tk.W)
        self.user_vps_jogo_bind_entry = tk.Entry(frame_vps_jogo_bind, width=30)
        self.user_vps_jogo_bind_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(frame_vps_jogo_bind, text="Senha:").grid(row=2, column=0, sticky=tk.W)
        self.password_vps_jogo_bind_entry = tk.Entry(frame_vps_jogo_bind, show='*', width=30)
        self.password_vps_jogo_bind_entry.grid(row=2, column=1, padx=5, pady=5)

        tk.Label(frame_vps_jogo_bind, text="Porta Local:").grid(row=3, column=0, sticky=tk.W)
        self.port_local_vps_jogo_bind_entry = tk.Entry(frame_vps_jogo_bind, width=7)
        self.port_local_vps_jogo_bind_entry.grid(row=3, column=1, padx=5, pady=5)

        # Rótulo de texto logo abaixo dos frames
        tk.Label(frame_ssh_bind, text="Configure aqui seu host SSH que será conectado através dos túneis MPTCP. Se informado uma porta local, também será criado um proxy SOCKS5 para servir de túnel SSH para TCP.", anchor=tk.W, wraplength=800, justify=tk.LEFT).grid(row=1, column=0, columnspan=5, pady=0, sticky=tk.W)
        # Rótulo de texto logo abaixo dos frames
        tk.Label(frame_ssh_bind, text="As chaves privadas devem ser salvas na pasta 'ssh_keys' acessivel na tela de Configurações de SSH.", anchor=tk.W, wraplength=800, justify=tk.LEFT).grid(row=2, column=0, columnspan=5, pady=0, sticky=tk.W)

        # Rótulo de texto acima do botão alinhado à esquerda
        #tk.Label(frame_ssh_bind, text="", anchor=tk.W).grid(row=1, column=1, columnspan=5, pady=20, sticky=tk.W)
        #tk.Label(frame_ssh_bind, text="Marcar esta opção irá criar um usuario e senha no OMR de acordo com as configurações definidas acima.", anchor=tk.W).grid(row=2, column=0, columnspan=5, pady=0, sticky=tk.W)

        # Botão para salvar as configurações
        save_button = tk.Button(frame_ssh_bind, text="Salvar", command=self.save_bind_credentials)
        save_button.grid(row=3, column=0, columnspan=2, pady=10)

        # Carregar informações ao inicializar
        self.load_bind_credentials()

        self.top.protocol("WM_DELETE_WINDOW", self.on_close)

# METODO DA ABA DE CONFIGURAÇÃO DE PROXYS SOCKS5 E TUNEL SSH NA QUINTA ABA.
    def load_bind_credentials(self):
        config = configparser.ConfigParser()
        config.read('config.ini')

        # Carregar as informações para VPS VPN Bind
        self.host_vps_vpn_bind_entry.insert(0, config['ssh_vps_vpn_bind'].get('host', ''))
        self.port_vps_vpn_bind_entry.insert(0, config['ssh_vps_vpn_bind'].get('port', ''))
        self.user_vps_vpn_bind_entry.insert(0, config['ssh_vps_vpn_bind'].get('username', ''))
        self.password_vps_vpn_bind_entry.insert(0, config['ssh_vps_vpn_bind'].get('password', ''))
        self.port_local_vps_vpn_bind_entry.insert(0, config['ssh_vps_vpn_bind'].get('port_local', ''))

        # Carregar as informações para VPS JOGO Bind
        self.host_vps_jogo_bind_entry.insert(0, config['ssh_vps_jogo_bind'].get('host', ''))
        self.port_vps_jogo_bind_entry.insert(0, config['ssh_vps_jogo_bind'].get('port', ''))
        self.user_vps_jogo_bind_entry.insert(0, config['ssh_vps_jogo_bind'].get('username', ''))
        self.password_vps_jogo_bind_entry.insert(0, config['ssh_vps_jogo_bind'].get('password', ''))
        self.port_local_vps_jogo_bind_entry.insert(0, config['ssh_vps_jogo_bind'].get('port_local', ''))

    def save_bind_credentials(self):
        config = configparser.ConfigParser()
        config.read('config.ini')

        # Salvar as informações para VPS VPN Bind
        config['ssh_vps_vpn_bind'] = {
            'host': self.host_vps_vpn_bind_entry.get(),
            'port': self.port_vps_vpn_bind_entry.get(),
            'username': self.user_vps_vpn_bind_entry.get(),
            'port_local': self.port_local_vps_vpn_bind_entry.get(),
            'password': self.password_vps_vpn_bind_entry.get()
        }

        # Salvar as informações para VPS JOGO Bind
        config['ssh_vps_jogo_bind'] = {
            'host': self.host_vps_jogo_bind_entry.get(),
            'port': self.port_vps_jogo_bind_entry.get(),
            'username': self.user_vps_jogo_bind_entry.get(),
            'port_local': self.port_local_vps_jogo_bind_entry.get(),
            'password': self.password_vps_jogo_bind_entry.get()
        }

        with open('config.ini', 'w') as configfile:
            config.write(configfile)

# METODO PARA SALVAR USUARIO E SENHA PARA CONEXÃO SSH COM OMR VPS VPN/JOGO NA QUARTA ABA
    def open_ssh_keys_folder(self):
        # Define o caminho da pasta 'ssh_keys'
        path = os.path.join(os.getcwd(), 'ssh_keys')
        
        # Tenta abrir a pasta usando o explorador de arquivos padrão
        try:
            os.startfile(path)
        except FileNotFoundError:
            print("A pasta 'ssh_keys' não foi encontrada.")
        except Exception as e:
            print(f"Erro ao tentar abrir a pasta: {e}")

    def toggle_criar_usuario_ssh(self):
        """Alterna o valor de criar_usuario_ssh e salva no arquivo de configuração."""
        self.ButtonManager.criar_usuario_ssh = self.criar_usuario_ssh_var.get()
        self.ButtonManager.save_general_config()

    # Carregar informações do usuário da seção apropriada
    def load_user_credentials(self):
        config = configparser.ConfigParser()
        config.read('config.ini')

        # Limpa as entradas atuais
        self.user_vpn_entry.delete(0, tk.END)
        self.password_vpn_entry.delete(0, tk.END)
        self.user_jogo_entry.delete(0, tk.END)
        self.password_jogo_entry.delete(0, tk.END)
        self.host_vpn_entry.delete(0, tk.END)
        self.host_jogo_entry.delete(0, tk.END)
        self.port_vpn_entry.delete(0, tk.END)
        self.port_jogo_entry.delete(0, tk.END)
        self.user_vps_vpn_entry.delete(0, tk.END)
        self.password_vps_vpn_entry.delete(0, tk.END)
        self.host_vps_vpn_entry.delete(0, tk.END)
        self.port_vps_vpn_entry.delete(0, tk.END)
        self.user_vps_jogo_entry.delete(0, tk.END)
        self.password_vps_jogo_entry.delete(0, tk.END)
        self.host_vps_jogo_entry.delete(0, tk.END)
        self.port_vps_jogo_entry.delete(0, tk.END)

        # Carrega as informações do arquivo ini
        if 'ssh_vpn' in config:
            self.host_vpn_entry.insert(0, config['ssh_vpn'].get('host', ''))
            self.user_vpn_entry.insert(0, config['ssh_vpn'].get('username', ''))
            self.password_vpn_entry.insert(0, config['ssh_vpn'].get('password', ''))
            self.port_vpn_entry.insert(0, config['ssh_vpn'].get('port', ''))

        if 'ssh_jogo' in config:
            self.host_jogo_entry.insert(0, config['ssh_jogo'].get('host', ''))
            self.user_jogo_entry.insert(0, config['ssh_jogo'].get('username', ''))
            self.password_jogo_entry.insert(0, config['ssh_jogo'].get('password', ''))
            self.port_jogo_entry.insert(0, config['ssh_jogo'].get('port', ''))

        if 'ssh_vps_vpn' in config:
            self.host_vps_vpn_entry.insert(0, config['ssh_vps_vpn'].get('host', ''))
            self.user_vps_vpn_entry.insert(0, config['ssh_vps_vpn'].get('username', ''))
            self.password_vps_vpn_entry.insert(0, config['ssh_vps_vpn'].get('password', ''))
            self.port_vps_vpn_entry.insert(0, config['ssh_vps_vpn'].get('port', ''))

        if 'ssh_vps_jogo' in config:
            self.host_vps_jogo_entry.insert(0, config['ssh_vps_jogo'].get('host', ''))
            self.user_vps_jogo_entry.insert(0, config['ssh_vps_jogo'].get('username', ''))
            self.password_vps_jogo_entry.insert(0, config['ssh_vps_jogo'].get('password', ''))
            self.port_vps_jogo_entry.insert(0, config['ssh_vps_jogo'].get('port', ''))

    def save_user_credentials(self):
        config = configparser.ConfigParser()
        config.read('config.ini')

        # Cria as seções se não existirem
        if 'ssh_vpn' not in config:
            config.add_section('ssh_vpn')
        if 'ssh_jogo' not in config:
            config.add_section('ssh_jogo')
        if 'ssh_vps_vpn' not in config:
            config.add_section('ssh_vps_vpn')
        if 'ssh_vps_jogo' not in config:
            config.add_section('ssh_vps_jogo')

        # Salva as informações no arquivo ini
        config['ssh_vpn']['host'] = self.host_vpn_entry.get()
        config['ssh_vpn']['username'] = self.user_vpn_entry.get()
        config['ssh_vpn']['password'] = self.password_vpn_entry.get()
        config['ssh_vpn']['port'] = self.port_vpn_entry.get()

        config['ssh_jogo']['host'] = self.host_jogo_entry.get()
        config['ssh_jogo']['username'] = self.user_jogo_entry.get()
        config['ssh_jogo']['password'] = self.password_jogo_entry.get()
        config['ssh_jogo']['port'] = self.port_jogo_entry.get()

        config['ssh_vps_vpn']['host'] = self.host_vps_vpn_entry.get()
        config['ssh_vps_vpn']['username'] = self.user_vps_vpn_entry.get()
        config['ssh_vps_vpn']['password'] = self.password_vps_vpn_entry.get()
        config['ssh_vps_vpn']['port'] = self.port_vps_vpn_entry.get()

        config['ssh_vps_jogo']['host'] = self.host_vps_jogo_entry.get()
        config['ssh_vps_jogo']['username'] = self.user_vps_jogo_entry.get()
        config['ssh_vps_jogo']['password'] = self.password_vps_jogo_entry.get()
        config['ssh_vps_jogo']['port'] = self.port_vps_jogo_entry.get()

        # Escreve as configurações no arquivo
        with open('config.ini', 'w') as configfile:
            config.write(configfile)

        messagebox.showinfo("Salvar Configurações", "Configurações salvas com sucesso!")

        # Recarrega as configurações na instância de ButtonManager
        self.ButtonManager.load_ssh_configurations()

#METODO PARA SALVAR NOME DAS VMS NA TERCEIRA ABA
    def save_vm_names(self):
        vm_vpn_name = self.vm_vpn_name_entry.get().strip()
        vm_jogo_name = self.vm_jogo_name_entry.get().strip()

        if vm_vpn_name and vm_jogo_name:
            vm_names = {
                'vm_vpn_name': vm_vpn_name,
                'vm_jogo_name': vm_jogo_name
            }
            with open("vm_config.json", 'w') as file:
                json.dump(vm_names, file, indent=4)
            messagebox.showinfo("Salvar", "Nome de VMs salvos com sucesso!")
        else:
            messagebox.showinfo("Erro", "Por favor, insira todos os nomes das VMs.")

    def load_vm_names(self):
        try:
            with open("vm_config.json", 'r') as file:
                vm_names = json.load(file)
                self.vm_vpn_name_entry.delete(0, tk.END)
                self.vm_vpn_name_entry.insert(0, vm_names.get('vm_vpn_name', ''))
                self.vm_jogo_name_entry.delete(0, tk.END)
                self.vm_jogo_name_entry.insert(0, vm_names.get('vm_jogo_name', ''))
        except FileNotFoundError:
            # Arquivo não encontrado, deixar os campos vazios
            self.vm_vpn_name_entry.delete(0, tk.END)
            self.vm_jogo_name_entry.delete(0, tk.END)
        except json.JSONDecodeError:
            # Arquivo JSON inválido, deixar os campos vazios
            self.vm_vpn_name_entry.delete(0, tk.END)
            self.vm_jogo_name_entry.delete(0, tk.END)

    def start_monitoring(self):
        self.ButtonManager.verificar_vm = True  # Habilita o monitoramento
        self.ButtonManager.update_vm_status()   # Inicia o monitoramento
        self.update_monitoring_status()

    def stop_monitoring(self):
        self.ButtonManager.verificar_vm = False  # Desabilita o monitoramento
        self.update_monitoring_status()

    def update_monitoring_status(self):
        # Atualiza o texto do Label com base no status de monitoramento
        if self.ButtonManager.verificar_vm:
            self.monitoring_status_label.config(text="Monitoramento: Ligado", fg="green")
        else:
            self.monitoring_status_label.config(text="Monitoramento: Desligado", fg="red")

# MÉTODOS PARA A SEGUNDA ABA (Configurações de Ping)
    def toggle_and_save_execute_initial_test(self):
        # Alterna o estado da variável execute_initial_test_active
        self.execute_initial_test_active = not self.execute_initial_test_active
        self.update_execute_test_status_label()

        # Salva a configuração no arquivo INI
        self.config.set('general', 'execute_initial_test', str(self.execute_initial_test_active))
        with open('config.ini', 'w') as configfile:
            self.config.write(configfile)
        print("Configurações salvas!")

        # Passar o valor de execute_initial_test para a classe ButtonManager
        self.ButtonManager.set_execute_initial_test(self.execute_initial_test_active)

    def update_execute_test_status_label(self):
        # Atualiza o texto da label de status
        status_text = "Ligado" if self.execute_initial_test_active else "Desligado"
        self.execute_test_status_label.config(text=f"Teste de Ping: {status_text}")

    def load_addresses(self):
        try:
            with open('addresses.json', 'r') as f:
                addresses = json.load(f)
                self.url_to_ping_vps_jogo = addresses.get("vps_jogo")
                self.url_to_ping_vps_vpn = addresses.get("vps_vpn")
                self.url_to_ping_omr_vpn = addresses.get("omr_vpn")
                self.url_to_ping_omr_jogo = addresses.get("omr_jogo")
                self.url_to_ping_vps_vpn_1 = addresses.get("vps_vpn_1")
                self.url_to_ping_vps_jogo_1 = addresses.get("vps_jogo_1")
        except (FileNotFoundError, json.JSONDecodeError):
            self.url_to_ping_vps_jogo = None
            self.url_to_ping_vps_vpn = None
            self.url_to_ping_omr_vpn = None
            self.url_to_ping_omr_jogo = None
            self.url_to_ping_vps_vpn_1 = None
            self.url_to_ping_vps_jogo_1 = None

    def save_addresses(self):
        addresses = {
            "vps_vpn": self.vps_vpn_entry.get(),
            "vps_jogo": self.vps_jogo_entry.get(),
            "omr_vpn": self.omr_vpn_entry.get(),
            "omr_jogo": self.omr_jogo_entry.get(),
            "vps_vpn_1": self.vps_vpn_1_entry.get(),
            "vps_jogo_1": self.vps_jogo_1_entry.get()
        }
        with open("addresses.json", "w") as f:
            json.dump(addresses, f)
        # Exibir uma mensagem de sucesso
        messagebox.showinfo("Salvar", "Endereços salvos com sucesso!")


#FUNÇÃO PARA GERAR LINKS SEM PRECISAR ADICIONAR A LETRA DE UNIDADE.
    def get_drive_letter(self):
        """Retorna a letra da unidade onde o script está sendo executado."""
        if getattr(sys, 'frozen', False):  # Verifica se o código está congelado/compilado
            script_path = os.path.abspath(sys.executable)
        else:
            script_path = os.path.abspath(__file__)
        drive_letter = os.path.splitdrive(script_path)[0]
        return drive_letter

    def os_letter(self, relative_path):
        """Constrói o caminho absoluto a partir de um caminho relativo."""
        drive_letter = self.get_drive_letter()
        # Se o caminho relativo já inclui uma unidade (letra de drive), não substituímos
        if os.path.splitdrive(relative_path)[0]:
            return os.path.abspath(relative_path)
        else:
            # Garantir que a barra invertida seja adicionada após a letra da unidade
            return os.path.join(drive_letter + os.sep, relative_path)

#FUNÇÕES DA PRIMEIRA ABA
    def load_provedor_url(self):
        """Carrega o URL do provedor de teste do arquivo .ini e preenche o campo de entrada."""
        self.config.read(self.config_file)
        
        # Carregar o URL do provedor de teste
        self.test_provedor_url = self.config.get('general', 'test_provedor_url', fallback="")

        # Preenche o campo de entrada com o URL carregado
        self.url_entry.delete(0, tk.END)  # Limpa o campo de entrada
        self.url_entry.insert(0, self.test_provedor_url)  # Insere o URL carregado

    def save_provedor_url(self):
        """Salva o URL do provedor de teste no arquivo de configuração."""
        new_url = self.url_entry.get()
        if not self.config.has_section('general'):
            self.config.add_section('general')
        
        # Atualiza o URL no arquivo de configuração
        self.config.set('general', 'test_provedor_url', new_url)
        
        # Salva as alterações no arquivo de configuração
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

        print(f"Novo URL salvo: {new_url}")

    def editar_arquivo_ajuda(self):
        relative_path = r"Dropbox Compartilhado\AmazonWS\Auto Iniciar meus VPS\pitao\Ajuda.hnd"
        absolute_path = self.os_letter(relative_path)
        if os.path.exists(absolute_path):
            ctypes.windll.shell32.ShellExecuteW(None, "open", absolute_path, None, None, 1)
        else:
            print("Arquivo de ajuda não encontrado.")

    def select_files(self):
        initial_dir = r"J:\Maquinas Virtuais\Virtual Box Machines"
        files = filedialog.askopenfilenames(initialdir=initial_dir, title="Selecionar arquivos", filetypes=(("All files", "*.rar;*.vdi;*.zip"),))
        if files:
            self.move_files(files)

    def move_files(self, files):
        destination_dir = filedialog.askdirectory(title="Selecionar pasta de destino")
        if destination_dir:
            for file in files:
                filename = os.path.basename(file)
                destination_path = os.path.join(destination_dir, filename)
                try:
                    os.rename(file, destination_path)
                except Exception as e:
                    print(f"Erro ao mover {file} para {destination_path}: {e}")

    def edit_uuid(self):
        bat_file_path = r"J:\Maquinas Virtuais\Virtual Box Machines\OpenMPTCP\mudar_uuid.bat"
        subprocess.Popen(['notepad.exe', bat_file_path])

    def perform_management_operations(self):
        success_message = "Todas as operações foram concluídas com sucesso."
        # Passos conforme descrito
        for file in filedialog.askopenfilenames(initialdir=r"J:\Maquinas Virtuais\Virtual Box Machines\OpenMPTCP", title="Selecionar arquivo .vdi", filetypes=(("VDI files", "*.vdi"),)):
            try:
                # 1. Criar cópia do arquivo no mesmo diretório
                dir_path = os.path.dirname(file)
                base_name = os.path.basename(file)
                copy_name = os.path.join(dir_path, f"Copy_of_{base_name}")
                shutil.copy(file, copy_name)

                # 2. Executar o bat J:\Maquinas Virtuais\Virtual Box Machines\OpenMPTCP\mudar_uuid.bat
                bat_file = r"J:\Maquinas Virtuais\Virtual Box Machines\OpenMPTCP\mudar_uuid.bat"
                subprocess.run([bat_file], shell=True)

                # 3. Comprimir o arquivo selecionado inicialmente com data YYMMDD
                current_date = datetime.now().strftime("%y-%m-%d")
                compressed_name = filedialog.asksaveasfilename(initialdir=dir_path, title="Comprimir arquivo", initialfile=f"OpenMPTCP {current_date}.zip", filetypes=(("Zip files", "*.zip"),))
                if compressed_name:
                    shutil.make_archive(compressed_name[:-4], 'zip', dir_path, base_name)

                # 4. Renomear o arquivo selecionado inicialmente com data YYMMDD
                new_name = filedialog.asksaveasfilename(initialdir=dir_path, title="Renomear arquivo OpenMPTCP", initialfile=f"OpenMPTCP {current_date}.vdi", filetypes=(("VDI files", "*.vdi"),))
                if new_name:
                    os.rename(file, new_name)

                # 5. Solicitar novo nome para a cópia do arquivo com data YYMMDD
                new_copy_name = filedialog.asksaveasfilename(initialdir=dir_path, title="Renomear arquivo OCI", initialfile=f"OCI {current_date}.vdi", filetypes=(("VDI files", "*.vdi"),))
                if new_copy_name:
                    os.rename(copy_name, new_copy_name)

                # 6. Mover arquivo cópia para pasta J:\Maquinas Virtuais\Virtual Box Machines\OpenMPTCP_OCI
                destination_folder = r"J:\Maquinas Virtuais\Virtual Box Machines\OpenMPTCP_OCI"
                shutil.move(new_copy_name, os.path.join(destination_folder, os.path.basename(new_copy_name)))

                # Mostra mensagem de sucesso após concluir todas as operações
                messagebox.showinfo("Operações Concluídas", success_message)

            except Exception as e:
                print(f"Erro ao executar operações de gerenciamento: {e}")

    def copy_to_oci(self):
        try:
            # Passo 1: Selecionar arquivo .zip
            zip_file = filedialog.askopenfilename(initialdir=r"J:\Maquinas Virtuais\Virtual Box Machines\OpenMPTCP", title="Selecionar arquivo .zip", filetypes=(("Zip files", "*.zip"),))
            if not zip_file:
                return  # Se o usuário cancelar a seleção, sair da função

            # Passo 2: Extrair arquivo .zip no mesmo diretório
            dir_path = os.path.dirname(zip_file)
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(dir_path)

            # Identificar o nome do arquivo extraído
            extracted_files = zip_ref.namelist()
            if len(extracted_files) != 1:
                raise ValueError("O arquivo .zip deve conter exatamente um arquivo para este processo.")

            extracted_file = os.path.join(dir_path, extracted_files[0])

            # Passo 3: Executar o bat J:\Maquinas Virtuais\Virtual Box Machines\OpenMPTCP\mudar_uuid.bat
            bat_file = r"J:\Maquinas Virtuais\Virtual Box Machines\OpenMPTCP\mudar_uuid.bat"
            subprocess.run([bat_file], shell=True)

            # Passo 4: Permitir que o usuário escolha um novo nome para o arquivo extraído
            current_date = datetime.now().strftime("%y-%m-%d")
            new_name = filedialog.asksaveasfilename(initialdir=dir_path, title="Renomear arquivo extraído", initialfile=f"OCI {current_date}.vdi", filetypes=(("VDI files", "*.vdi"),))
            if not new_name:
                raise ValueError("Nome de arquivo inválido ou operação cancelada pelo usuário.")

            os.rename(extracted_file, new_name)

            # Passo 5: Mover arquivo extraído para pasta J:\Maquinas Virtuais\Virtual Box Machines\OpenMPTCP_OCI
            destination_folder = r"J:\Maquinas Virtuais\Virtual Box Machines\OpenMPTCP_OCI"
            shutil.move(new_name, os.path.join(destination_folder, os.path.basename(new_name)))

            # Mostrar mensagem de sucesso
            messagebox.showinfo("Operações Concluídas", "Operações de extração e gerenciamento concluídas com sucesso.")

        except Exception as e:
            print(f"Erro ao executar operações de extração e gerenciamento: {e}")

    def backup_virtualbox(self):
        try:
            # Passo 1: Compactar os arquivos .vbox em um arquivo zip
            current_date = datetime.now().strftime("%y-%m-%d")
            source_files = [
                r"J:\Maquinas Virtuais\Virtual Box Machines\OpenMPTCP_OCI\OpenMPTCP_OCI.vbox",
                r"J:\Maquinas Virtuais\Virtual Box Machines\OpenMPTCP\OpenMPTCP.vbox"
            ]
            zip_filename = f"BackupOMR {current_date}.zip"

            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                for file in source_files:
                    zipf.write(file, os.path.basename(file))

            # Passo 2: Mover o arquivo zip para a pasta específica
            current_dir = os.getcwd()  # Diretório atual onde o executável está sendo executado
            destination_folder = os.path.join(current_dir, "Backup VMs VirtualBox")
            os.makedirs(destination_folder, exist_ok=True)  # Cria o diretório se ele não existir
            shutil.move(zip_filename, os.path.join(destination_folder, zip_filename))

            # Mostrar mensagem de sucesso
            messagebox.showinfo("Operações Concluídas", "Arquivos compactados e movidos com sucesso.")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao executar operações: {e}")

    def save(self):
        self.top.grab_release()
        self.save_window_position()
        self.top.destroy()

    def load_window_position(self):
        if os.path.isfile("OMRManagerDialog_position.json"):
            with open("OMRManagerDialog_position.json", "r") as f:
                position = json.load(f)
                self.top.geometry("+{}+{}".format(position["x"], position["y"]))

    def save_window_position(self):
        position = {
            "x": self.top.winfo_x(),
            "y": self.top.winfo_y()
        }
        with open("OMRManagerDialog_position.json", "w") as f:
            json.dump(position, f)

    def on_close(self):
        self.top.grab_release()
        self.save_window_position()
        self.top.destroy()

#JANELA PARA ADICIONAR SERVIDOR/OMR AS ABAS 1 E 2.
class AddButtonDialog:
    def __init__(self, parent, top):
        self.top = tk.Toplevel(parent)
        self.load_window_position()
        self.top.title("Adicionar Servidor")

        # Bloqueia a interação com a janela master
        self.top.grab_set()

        # Definir a janela como transient para a janela parent
        self.top.transient(parent)

        # Define a janela como ativa
        self.top.focus_set()

        self.icon_path = tk.StringVar()
        self.text = tk.StringVar()
        self.link = tk.StringVar()
        self.premium_link = tk.StringVar()
        self.standard_link = tk.StringVar()

        # Frame com borda para conter todo o conteúdo
        self.main_frame = tk.Frame(self.top, borderwidth=2, relief="raised")
        self.main_frame.pack(padx=10, pady=10, fill="both", expand=True)

        tk.Label(self.main_frame, text="Selecionar Icone:").grid(row=0, column=0, padx=5, pady=5)
        tk.Entry(self.main_frame, textvariable=self.icon_path).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(self.main_frame, text="Selecionar", command=self.select_icon).grid(row=0, column=2, padx=5, pady=5)

        tk.Label(self.main_frame, text="Texto do botão:").grid(row=1, column=0, padx=5, pady=5)
        tk.Entry(self.main_frame, textvariable=self.text).grid(row=1, column=1, padx=5, pady=5)

        tk.Label(self.main_frame, text="Link:").grid(row=2, column=0, padx=5, pady=5)
        tk.Entry(self.main_frame, textvariable=self.link).grid(row=2, column=1, padx=5, pady=5)
        tk.Button(self.main_frame, text="Selecionar Arquivo", command=self.select_file).grid(row=2, column=2, padx=5, pady=5)

        tk.Label(self.main_frame, text="IP Premium:").grid(row=3, column=0, padx=5, pady=5)
        tk.Entry(self.main_frame, textvariable=self.premium_link).grid(row=3, column=1, padx=5, pady=5)
        tk.Button(self.main_frame, text="Selecionar Arquivo", command=self.select_premium_file).grid(row=3, column=2, padx=5, pady=5)

        tk.Label(self.main_frame, text="IP Standard:").grid(row=4, column=0, padx=5, pady=5)
        tk.Entry(self.main_frame, textvariable=self.standard_link).grid(row=4, column=1, padx=5, pady=5)
        tk.Button(self.main_frame, text="Selecionar Arquivo", command=self.select_standard_file).grid(row=4, column=2, padx=5, pady=5)

        tk.Button(self.main_frame, text="Adicionar", command=self.add_button).grid(row=5, columnspan=3, padx=5, pady=5)

        self.button_info = None
        self.top.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_window_position(self):
        if os.path.isfile("addButtondialog_position.json"):
            with open("addButtondialog_position.json", "r") as f:
                position = json.load(f)
                self.top.geometry("+{}+{}".format(position["x"], position["y"]))

    def save_window_position(self):
        position = {
            "x": self.top.winfo_x(),
            "y": self.top.winfo_y()
        }
        with open("addButtondialog_position.json", "w") as f:
            json.dump(position, f)

    def on_close(self):
        self.top.grab_release()
        self.save_window_position()
        self.top.destroy()

    def select_icon(self):
        self.hide_dialog()
        file_path = filedialog.askopenfilename(filetypes=[("Imagens", "*.png;*.jpg;*.gif")])
        self.icon_path.set(file_path)
        self.show_dialog()

    def select_file(self):
        self.hide_dialog()
        file_path = filedialog.askopenfilename()
        self.link.set(file_path)
        self.show_dialog()

    def select_premium_file(self):
        self.hide_dialog()
        file_path = filedialog.askopenfilename()
        self.premium_link.set(file_path)
        self.show_dialog()

    def select_standard_file(self):
        self.hide_dialog()
        file_path = filedialog.askopenfilename()
        self.standard_link.set(file_path)
        self.show_dialog()

    def hide_dialog(self):
        self.top.withdraw()

    def show_dialog(self):
        self.top.deiconify()
        self.top.grab_set()
        self.top.focus_set()

    def add_button(self):
        if self.icon_path.get() and self.text.get() and self.link.get():
            self.button_info = {
                'icon': self.icon_path.get(),
                'text': self.text.get(),
                'link': self.link.get(),
                'premium_link': self.premium_link.get() if self.premium_link.get() else None,
                'standard_link': self.standard_link.get() if self.standard_link.get() else None
            }
            self.top.destroy()
        else:
            messagebox.showerror("Erro", "Preencha todos os campos obrigatórios!")

#JANELA SOBRE
class about:
    def __init__(self, master):
        top = self.top = tk.Toplevel(master)
        self.master = master
        self.load_window_position()
        self.top.title("Sobre")
        self.top.geometry("540x495")

        # Bloqueia a interação com a janela master
        self.top.grab_set()

        # Define a janela como ativa
        self.top.focus_set()

        # Texto centralizado no topo da janela
        tk.Label(self.top, text="_______________PROJETO TEMER_______________", font=("Helvetica", 16)).pack(side="top", pady=10)

        # Carregar e exibir a imagem
        img_path = os.path.join("Sobre", "vempiro.jpg")  # Substitua pelo nome do arquivo de sua imagem
        if os.path.isfile(img_path):
            img = Image.open(img_path)
            img = ImageTk.PhotoImage(img)
            tk.Label(self.top, image=img).pack(side="top", pady=10)
            # Manter a referência da imagem para evitar coleta de lixo
            self.img = img
        
        # Frame para os botões e textos descritivos
        button_frame = tk.Frame(self.top, borderwidth=1, relief=tk.RIDGE, width=500, height=170, bg="white")
        button_frame.pack(side="top", padx=10, pady=1, anchor='n')
        button_frame.pack_propagate(False)

        # Adicionando imagens aos textos
        self.add_text_with_image(button_frame, "Versão: Beta 74.5 | 2024 - 2024", "icone1.png")
        self.add_text_with_image(button_frame, "Edição e criação: VempirE", "icone2.png")
        self.add_text_with_image(button_frame, "Código: Mano GPT", "icone3.png")
        self.add_text_with_image(button_frame, "Auxilio não remunerado: Mije", "pepox.png")
        self.add_text_with_image(button_frame, "Liferuler: CAOS", "chora.png")
        self.add_text_with_image(button_frame, "Gerente e Ouvinte: Naminha Pixu", "mimo.png")

    def add_text_with_image(self, parent, text, image_path):
        frame = tk.Frame(parent, bg="white")
        frame.pack(side=tk.TOP, anchor='w')

        tk.Label(frame, text=text, bg="white").pack(side=tk.LEFT)

        if os.path.isfile(os.path.join("Sobre", image_path)):
            img = Image.open(os.path.join("Sobre", image_path))
            img = ImageTk.PhotoImage(img)
            label_img = tk.Label(frame, image=img)
            label_img.image = img
            label_img.pack(side=tk.LEFT, padx=5)

        # Botões na parte inferior da janela
        button_frame_bottom = tk.Frame(self.top)
        button_frame_bottom.pack(side="bottom", pady=10)
        #tk.Button(button_frame_bottom, text="Cancelar", command=self.save).pack(side=tk.LEFT, padx=10)

        self.top.protocol("WM_DELETE_WINDOW", self.on_close)

    def save(self):
        self.top.grab_release()
        self.save_window_position()
        self.top.destroy()

    def load_window_position(self):
        if os.path.isfile("about_position.json"):
            with open("about_position.json", "r") as f:
                position = json.load(f)
                self.top.geometry("+{}+{}".format(position["x"], position["y"]))

    def save_window_position(self):
        position = {
            "x": self.top.winfo_x(),
            "y": self.top.winfo_y()
        }
        with open("about_position.json", "w") as f:
            json.dump(position, f)

    def on_close(self):
        self.top.grab_release()
        self.save_window_position()
        self.top.destroy()

#LOGICA PARA FUNCIONAÇÃO DAS TOOLTIPS.
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tooltip, text=self.text, justify="left",
                         background="#ffffe0", relief="solid", borderwidth=1)
        label.pack(ipadx=1)

    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

    def update_text(self, text):
        self.text = text

def main():
    root = tk.Tk()
    root.title("Gerenciador de VPS")
    root.configure(bg="white")

    manager = ButtonManager(root)

    root.mainloop()

if __name__ == "__main__":
    main()
