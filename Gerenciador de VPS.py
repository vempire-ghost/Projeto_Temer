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
import winreg
import queue
import paramiko
import configparser
from datetime import datetime
from PIL import Image, ImageTk
# Configuração básica do logging para salvar em dois arquivos diferentes
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')

# Criando o Formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')

# Logger principal
logger_main = logging.getLogger('main_logger')
main_handler = logging.FileHandler('app.log')
main_handler.setLevel(logging.INFO)
main_handler.setFormatter(formatter)  # Aplicando o Formatter
logger_main.addHandler(main_handler)

# Logger secundário para o run_test_command
logger_test_command = logging.getLogger('test_command_logger')
test_command_handler = logging.FileHandler('test_command.log')
test_command_handler.setLevel(logging.INFO)
test_command_handler.setFormatter(formatter)  # Aplicando o Formatter
logger_test_command.addHandler(test_command_handler)

class ButtonManager:
    def __init__(self, master):
        self.master = master
        self.script_finished = False  # Inicializa a variável de controle para o término do script
        self.monitor_xray = False # Variável para rastrear o estado do monitoramento do Xray JOGO
        self.botao_monitorar_xray = True  # Variável para rastrear o estado do botão monitoramento do Xray JOGO
        self.verificar_vm = True  # Variável que controla a verificação das VMs
        self.ping_forever = True # Variavel para ligar/desligar testes de ping.
        self.criar_usuario_ssh = True # Variavel para definir se cria ou não o usuario ssh no OMR
        self.connection_established = threading.Event()  # Evento para sinalizar conexão estabelecida
        self.stop_event = threading.Event()
        self.thread = None
        self.buttons = []
        self.button_frame = None
        self.second_tab_button_frame = None
        self.button_counter = 1  # Inicializa o contador de botões
        self.load_window_position()

        self.clear_log_file('app.log')  # Limpa o arquivo de log ao iniciar o programa
        self.clear_log_file('test_command.log')  # Limpa o arquivo de log ao iniciar o programa

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
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)
        
        # Inicia as threads de ping se os endereços estiverem configurados
        if (self.url_to_ping_vps_jogo and self.url_to_ping_vps_vpn and 
            self.url_to_ping_omr_vpn and self.url_to_ping_omr_jogo):
            self.start_pinging_threads()
        else:
            messagebox.showinfo("Info", "Por favor, configure todos os endereços de ping nas opções.")
        
        # Configura o tratamento para fechar a janela
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        # Cria a pasta de imagens se não existir
        if not os.path.exists('imagens'):
            os.makedirs('imagens')

        # Cria a pasta de chaves ssh se não existir
        if not os.path.exists('ssh_keys'):
            os.makedirs('ssh_keys')

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

        self.config.add_section('ssh_vps_vpn')
        self.config.set('ssh_vps_vpn', 'host', '')
        self.config.set('ssh_vps_vpn', 'username', '')
        self.config.set('ssh_vps_vpn', 'password', '')
        self.config.set('ssh_vps_vpn', 'port', '')

        # Adiciona a seção 'ssh_jogo'
        self.config.add_section('ssh_vps_jogo')
        self.config.set('ssh_vps_jogo', 'host', '')
        self.config.set('ssh_vps_jogo', 'username', '')
        self.config.set('ssh_vps_jogo', 'password', '')
        self.config.set('ssh_vps_jogo', 'port', '')

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
        self.load_general_config()  # Carrega as configurações gerais

        print("Configurações de SSH recarregadas com sucesso.")

# FUNÇÃO PARA VERIFICA INSTALAÇÃO DE PROGRAMAS NECESSARIOS PARA O FUNCIONAMENTO DO SISTEMA
    def check_software_installation(self):
        """Verifica se o Bitvise e o VirtualBox estão instalados no sistema."""
        bitvise_installed = self.is_program_installed("BvSsh.exe")
        virtualbox_installed = self.is_program_installed("VirtualBox.exe", check_registry=True)
        
        if not bitvise_installed or not virtualbox_installed:
            missing_programs = []
            if not bitvise_installed:
                missing_programs.append("Bitvise")
            if not virtualbox_installed:
                missing_programs.append("VirtualBox")
            
            # Exibe a mensagem com opção para fechar o programa
            msg = f"Os seguintes programas não estão instalados: {', '.join(missing_programs)}. Por favor, instale-os para continuar."
            if messagebox.askokcancel("Programas faltando", msg, icon="warning"):
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
    def on_close(self):
        self.master.after(100, self.prepare_for_closing)  # Agendar a execução de prepare_for_closing após 100 ms

    def prepare_for_closing(self):
        # Criar e exibir a tela de alerta
        #self.show_closing_alert()

        # Colocar aqui toda chamada de encerramento de threads que estiverem sendo executadas de forma initerrupta e qualquer função a ser chamada no encerramento do programa.
        # Sinaliza para as threads que devem encerrar
        self.stop_event.set()
        self.close_ssh_connection()
        self.stop_pinging_threads()
        self.stop_verificar_vm()
        self.save_window_position()
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
        self.master.destroy()

# FUNÇÃO PARA ENCONTRAR A LETRA DA UNIDADE ONDE O PROGRAMA SE ENCONTRA E UTILIZAR NAS FUNÇÕES DO MESMO.
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

    def on_tab_change(self, event):
        # Obtemos a aba selecionada
        current_tab = self.notebook.select()
    
        if self.notebook.tab(current_tab, "text") == "Scheduler":
            # Executa os comandos apenas quando a aba Scheduler é selecionada
            self.executar_comandos_scheduler()

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
        self.status_label_vps_vpn = tk.Label(frame_vps_vpn, text="Aguarde...", bg='lightgray', justify=tk.CENTER)
        self.status_label_vps_vpn.pack(side=tk.LEFT)

        # Label e valor para VPS JOGO
        frame_vps_jogo = tk.Frame(self.top_frame, bg='lightgray')
        frame_vps_jogo.grid(row=0, column=2, padx=5, pady=5, sticky=tk.E+tk.W)
        btn_vps_jogo = tk.Button(frame_vps_jogo, text=" VPS  JOGO: ", bg='lightgray', justify=tk.CENTER, command=self.abrir_arquivo_vps_jogo, width=9, height=1).pack(side=tk.LEFT)
        self.status_label_vps_jogo = tk.Label(frame_vps_jogo, text="Aguarde...", bg='lightgray', justify=tk.CENTER)
        self.status_label_vps_jogo.pack(side=tk.LEFT)

        # Label (aparência de botão) para OMR VPN
        frame_omr_vpn = tk.Frame(self.top_frame, bg='lightgray')
        frame_omr_vpn.grid(row=1, column=1, padx=5, pady=5, sticky=tk.E+tk.W)
        btn_omr_vpn = tk.Button(frame_omr_vpn, text="OMR VPN:", bg='lightgray', justify=tk.CENTER, command=self.open_OMR_VPN, width=9, height=1)
        btn_omr_vpn.pack(side=tk.LEFT)
        self.status_label_omr_vpn = tk.Label(frame_omr_vpn, text="Aguarde...", bg='lightgray', fg='black', justify=tk.CENTER)
        self.status_label_omr_vpn.pack(side=tk.LEFT)

        # Label (aparência de botão) para OMR JOGO
        frame_omr_jogo = tk.Frame(self.top_frame, bg='lightgray')
        frame_omr_jogo.grid(row=1, column=2, padx=5, pady=5, sticky=tk.E+tk.W)
        btn_omr_jogo = tk.Button(frame_omr_jogo, text="OMR JOGO:", bg='lightgray', justify=tk.CENTER, command=self.open_OMR_JOGO, width=9, height=1)
        btn_omr_jogo.pack(side=tk.LEFT)
        self.status_label_omr_jogo = tk.Label(frame_omr_jogo, text="Aguarde...", bg='lightgray', fg='black', justify=tk.CENTER)
        self.status_label_omr_jogo.pack(side=tk.LEFT)

        # Frame para VM VPN com fundo lightgray
        frame_vm_vpn = tk.Frame(self.top_frame, bg='lightgray')
        frame_vm_vpn.grid(row=2, column=1, padx=5, pady=5, sticky=tk.E+tk.W)
        self.label_vm_vpn = tk.Button(frame_vm_vpn, text="VM VPN:", bg='lightgray', justify=tk.CENTER, borderwidth=2, relief=tk.RAISED, command=self.show_vm_vpn_menu, width=9, height=1)
        self.label_vm_vpn.pack(side=tk.LEFT)
        self.value_vm_vpn = tk.Label(frame_vm_vpn, text="Aguarde...", bg='lightgray', justify=tk.CENTER)
        self.value_vm_vpn.pack(side=tk.LEFT)

        # Frame para VM JOGO com fundo lightgray
        frame_vm_jogo = tk.Frame(self.top_frame, bg='lightgray')
        frame_vm_jogo.grid(row=2, column=2, padx=5, pady=5, sticky=tk.E+tk.W)
        self.label_vm_jogo = tk.Button(frame_vm_jogo, text="VM JOGO:", bg='lightgray', justify=tk.CENTER, borderwidth=2, relief=tk.RAISED, command=self.show_vm_jogo_menu, width=9, height=1)
        self.label_vm_jogo.pack(side=tk.LEFT)
        self.value_vm_jogo = tk.Label(frame_vm_jogo, text="Aguarde...", bg='lightgray', justify=tk.CENTER)
        self.value_vm_jogo.pack(side=tk.LEFT)

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
        self.unifique_status.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)

        # Botão para Claro
        self.claro_status = tk.Button(self.status_frame, text="CLARO: Offline", bg='red', fg='black', justify=tk.CENTER, borderwidth=1, relief=tk.SOLID, command=self.test_claro)
        self.claro_status.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        # Botão para Coopera
        self.coopera_status = tk.Button(self.status_frame, text="COOPERA: Offline", bg='red', fg='black', justify=tk.CENTER, borderwidth=1, relief=tk.SOLID, command=self.test_coopera)
        self.coopera_status.grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)

        # Inicia a atualização do status das conexões SSH com atraso
        self.master.after(1000, lambda: threading.Thread(target=self.establish_ssh_vpn_connection).start())
        self.master.after(2000, lambda: threading.Thread(target=self.establish_ssh_jogo_connection).start())
        self.master.after(3000, lambda: threading.Thread(target=self.establish_ssh_vps_vpn_connection).start())
        self.master.after(4000, lambda: threading.Thread(target=self.establish_ssh_vps_jogo_connection).start())


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
        self.label_vps_vpn = tk.Label(self.frame_vps_vpn, text="VPS VPN:")
        self.label_vps_vpn.pack(anchor=tk.W)
        self.label_vps_vpn_scheduler = tk.Label(self.frame_vps_vpn, text="Scheduler: Aguarde...")
        self.label_vps_vpn_scheduler.pack(anchor=tk.W)
        self.label_vps_vpn_cc = tk.Label(self.frame_vps_vpn, text="CC: Aguarde...")
        self.label_vps_vpn_cc.pack(anchor=tk.W)

        # Labels e resultados para VPS JOGO
        self.frame_vps_jogo = tk.Frame(self.frame_vps, borderwidth=1, relief=tk.SOLID)
        self.frame_vps_jogo.grid(row=0, column=1, padx=10, pady=5, sticky=tk.W)
        self.label_vps_jogo = tk.Label(self.frame_vps_jogo, text="VPS JOGO:")
        self.label_vps_jogo.pack(anchor=tk.W)
        self.label_vps_jogo_scheduler = tk.Label(self.frame_vps_jogo, text="Scheduler: Aguarde...")
        self.label_vps_jogo_scheduler.pack(anchor=tk.W)
        self.label_vps_jogo_cc = tk.Label(self.frame_vps_jogo, text="CC: Aguarde...")
        self.label_vps_jogo_cc.pack(anchor=tk.W)

        # Labels e resultados para OMR VPN
        self.frame_omr_vpn = tk.Frame(self.frame_omr, borderwidth=1, relief=tk.SOLID)
        self.frame_omr_vpn.grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        self.label_omr_vpn = tk.Label(self.frame_omr_vpn, text="OMR VPN:")
        self.label_omr_vpn.pack(anchor=tk.W)
        self.label_omr_vpn_scheduler = tk.Label(self.frame_omr_vpn, text="Scheduler: Aguarde...")
        self.label_omr_vpn_scheduler.pack(anchor=tk.W)
        self.label_omr_vpn_cc = tk.Label(self.frame_omr_vpn, text="CC: Aguarde...")
        self.label_omr_vpn_cc.pack(anchor=tk.W)

        # Labels e resultados para OMR JOGO
        self.frame_omr_jogo = tk.Frame(self.frame_omr, borderwidth=1, relief=tk.SOLID)
        self.frame_omr_jogo.grid(row=0, column=1, padx=10, pady=5, sticky=tk.W)
        self.label_omr_jogo = tk.Label(self.frame_omr_jogo, text="OMR JOGO:")
        self.label_omr_jogo.pack(anchor=tk.W)
        self.label_omr_jogo_scheduler = tk.Label(self.frame_omr_jogo, text="Scheduler: Aguarde...")
        self.label_omr_jogo_scheduler.pack(anchor=tk.W)
        self.label_omr_jogo_cc = tk.Label(self.frame_omr_jogo, text="CC: Aguarde...")
        self.label_omr_jogo_cc.pack(anchor=tk.W)

        # Botão para reiniciar o omr-tracker VPN
        self.botao_atualizar_scheduler = tk.Button(self.frame_atualizar, text="Atualizar Scheduler e CC", command=self.atualizar_scheduler)
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
        self.botao_reiniciar_vpn_scheduler = tk.Button(self.frame_inferior_scheduler, text="Reiniciar Glorytun VPN", command=self.reiniciar_glorytun_vpn)
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
        self.version_label = tk.Label(self.footer_frame, text="Projeto Temer - ©VempirE_GhosT - Versão: beta 68", bg='lightgray', fg='black')
        self.version_label.pack(side=tk.LEFT, padx=0, pady=0)

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

    def establish_ssh_connection(self, connection_type):
        """Estabelece e mantém uma conexão SSH persistente com tentativas de reconexão contínuas."""
        max_retries = 50000
        retry_delay = 5
        attempt = 0

        while not self.stop_event.is_set():
            # Recarregar configurações antes de tentar conectar
            self.load_ssh_configurations()

            # Seleciona a configuração com base no tipo de conexão
            if connection_type == 'vpn':
                config = self.ssh_vpn_config
            elif connection_type == 'jogo':
                config = self.ssh_jogo_config
            elif connection_type == 'vps_vpn':
               config = self.ssh_vps_vpn_config
            elif connection_type == 'vps_jogo':
                config = self.ssh_vps_jogo_config
            else:
                logger_test_command.error("Tipo de conexão inválido.")
                return

            # Obter a porta da configuração (definir um valor padrão caso não esteja presente)
            port = int(config.get('port', 22))  # Por padrão, usa a porta 22 se não estiver definida

            # Adicionando o teste de conexão na porta definida usando socket
            try:
                socket_info = socket.getaddrinfo(config['host'], port, socket.AF_INET, socket.SOCK_STREAM)
                conn = socket.create_connection(socket_info[0][4], timeout=2)
                conn.close()
                logger_test_command.info(f"Conexão TCP na porta {port} com {config['host']} bem-sucedida.")
            except (socket.timeout, socket.error) as e:
                logger_test_command.warning(f"Falha na conexão TCP na porta {port} com {config['host']}: {e}. Tentando novamente em {retry_delay} segundos...")
                attempt += 1
                if attempt < max_retries:
                    if self.stop_event.wait(retry_delay):
                        break
                    continue  # Tenta novamente após o tempo de espera
                else:
                    logger_test_command.error("Número máximo de tentativas de conexão atingido devido à falha na porta {port}.")
                    self.connection_established.set()  # Marca a conexão como falhada
                    self.update_all_statuses_offline()  # Atualiza o status de todas as conexões para offline
                    break

            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            key_dir = os.path.join(os.path.dirname(__file__), 'ssh_keys')
            key_files = [os.path.join(key_dir, f) for f in os.listdir(key_dir) if os.path.isfile(os.path.join(key_dir, f))]

            try:
                # Tenta se conectar
                ssh_client.connect(
                    config['host'],
                    port=port,  # Usa a porta carregada do arquivo ini
                    username=config['username'],
                    password=config['password'],
                    key_filename=key_files,  # Usa todos os arquivos de chave encontrados
                    look_for_keys=False,
                    allow_agent=False
                )

                if connection_type == 'vpn':
                    self.ssh_vpn_client = ssh_client
                    # Inicia a atualização das labels após a conexão VPN ser estabelecida
                    if hasattr(self, 'update_status_labels'):
                        self.master.after(1000, self.update_status_labels)
                        # Marca a conexão como estabelecida
                        self.connection_established.set()
                    logger_test_command.info("Conexão SSH (vpn) estabelecida com sucesso iniciando teste das conexões.")
                elif connection_type == 'jogo':
                    self.ssh_jogo_client = ssh_client
                    logger_test_command.info("Conexão SSH (jogo) estabelecida com sucesso.")
                elif connection_type == 'vps_vpn':
                    self.ssh_vps_vpn_client = ssh_client
                    logger_test_command.info("Conexão SSH (vps_vpn) estabelecida com sucesso.")
                elif connection_type == 'vps_jogo':
                    self.ssh_vps_jogo_client = ssh_client
                    logger_test_command.info("Conexão SSH (vps_jogo) estabelecida com sucesso.")

                # Aguarda até que a conexão seja interrompida ou o programa seja fechado
                while not self.stop_event.is_set():
                    try:
                        # Realiza uma operação simples para verificar a conexão
                        ssh_client.exec_command('echo test')
                        # Usa wait com timeout para permitir a verificação do evento de parada
                        if self.stop_event.wait(5):  # Espera 5 segundos ou até o evento ser setado
                            break
                    except Exception as e:
                        # Se uma exceção for lançada, significa que a conexão foi perdida
                        logger_test_command.error(f"Conexão SSH ({connection_type}) perdida: {e}")
                        ssh_client.close()
                        if connection_type == 'vpn':
                            self.connection_established.clear()  # Limpa o sinal de conexão estabelecida (somente para VPN)
                            self.update_all_statuses_offline()  # Atualiza o status de todas as conexões para offline (somente para VPN)
                            break  # Sai do loop para evitar looping infinito ao perder a conexão VPN
                        else:
                            break  # Sai do loop para tentar reconectar a conexão de jogo

            except paramiko.AuthenticationException as e:
                logger_test_command.error(f"Erro de autenticação ao estabelecer conexão SSH ({connection_type}): {e}")

                if self.criar_usuario_ssh:
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
                else:
                    logger_test_command.info("A opção Criar usuário SSH automaticamente não está marcada, marque a opção ou crie o usuário manualmente e reinicie o programa.")
                    break  # Sair do loop de tentativa de conexão

            except paramiko.SSHException as e:
                # Captura erros específicos relacionados ao banner SSH
                if "banner" in str(e).lower():
                    logger_test_command.error(f"Erro de porta SSH ao estabelecer conexão ({connection_type}): {e}")
                    logger_test_command.error("Verifique a configuração da porta SSH nas configurações e corrija o problema.")
                    break  # Sai do loop de tentativa de conexão

            except Exception as e:
                logger_test_command.error(f"Erro ao estabelecer conexão SSH ({connection_type}): {e}")
                attempt += 1
                if attempt < max_retries:
                    logger_test_command.info(f"Tentando novamente em {retry_delay} segundos...")
                    if self.stop_event.wait(retry_delay):
                        break
                else:
                    logger_test_command.error("Número máximo de tentativas de conexão atingido.")
                    if connection_type == 'vpn':
                        self.connection_established.set()  # Marca a conexão como falhada (somente para VPN)
                        self.update_all_statuses_offline()  # Atualiza o status de todas as conexões para offline (somente para VPN)
                    break  # Sai do loop de tentativa de conexão

    def close_ssh_connection(self):
        """Fecha todas as conexões SSH abertas."""
        if hasattr(self, 'ssh_vpn_client') and self.ssh_vpn_client is not None:
            self.ssh_vpn_client.close()
            logger_test_command.info("Conexão SSH (vpn) fechada.")
            self.ssh_vpn_client = None

        if hasattr(self, 'ssh_jogo_client') and self.ssh_jogo_client is not None:
            self.ssh_jogo_client.close()
            logger_test_command.info("Conexão SSH (jogo) fechada.")
            self.ssh_jogo_client = None

        """Fecha a conexão SSH aberta para VPS VPN."""
        if hasattr(self, 'ssh_vps_vpn_client') and self.ssh_vps_vpn_client is not None:
            self.ssh_vps_vpn_client.close()
            logger_test_command.info("Conexão SSH (vps_vpn) fechada.")
            self.ssh_vps_vpn_client = None

        """Fecha a conexão SSH aberta para VPS Jogo."""
        if hasattr(self, 'ssh_vps_jogo_client') and self.ssh_vps_jogo_client is not None:
            self.ssh_vps_jogo_client.close()
            logger_test_command.info("Conexão SSH (vps_jogo) fechada.")
            self.ssh_vps_jogo_client = None

# LOGICA PARA TESTAR ESTADO DAS CONEXÕES A INTERNET.
    # Funções para os botões de teste
    def test_unifique(self):
        """Executa o teste para a conexão UNIFIQUE usando a conexão SSH VPN."""
        if not hasattr(self, 'ssh_vpn_client') or self.ssh_vpn_client is None:
            logger_test_command.error("Conexão SSH VPN não está estabelecida para o teste UNIFIQUE.")
            return

        threading.Thread(target=self.check_interface_status, args=('eth2', self.unifique_status, 'UNIFIQUE', self.ssh_vpn_client)).start()

    def test_claro(self):
        """Executa o teste para a conexão CLARO usando a conexão SSH VPN."""
        if not hasattr(self, 'ssh_vpn_client') or self.ssh_vpn_client is None:
            logger_test_command.error("Conexão SSH VPN não está estabelecida para o teste CLARO.")
            return

        threading.Thread(target=self.check_interface_status, args=('eth4', self.claro_status, 'CLARO', self.ssh_vpn_client)).start()

    def test_coopera(self):
        """Executa o teste para a conexão COOPERA usando a conexão SSH VPN."""
        if not hasattr(self, 'ssh_vpn_client') or self.ssh_vpn_client is None:
            logger_test_command.error("Conexão SSH VPN não está estabelecida para o teste COOPERA.")
            return

        threading.Thread(target=self.check_interface_status, args=('eth5', self.coopera_status, 'COOPERA', self.ssh_vpn_client)).start()

    def run_test_command(self, ssh_client, interface, output_queue, test_name):
        """Executa um comando utilizando a conexão SSH estabelecida."""
        if ssh_client is None:
            logger_test_command.error(f"{test_name}: Conexão SSH não está estabelecida.")
            output_queue.put(None)
            return

        command = f'curl --interface {interface} ipinfo.io'
        logger_test_command.info(f"Testando conexão com {test_name} na {interface}: {command}")

        try:
            stdin, stdout, stderr = ssh_client.exec_command(command)
            output = stdout.read().decode()
            logger_test_command.info(f"Teste de conexão com {test_name}: {output}")
            output_queue.put(output)
        except Exception as e:
            logger_test_command.error(f"{test_name}: Erro ao executar comando: {e}")
            output_queue.put(None)

    def update_all_statuses_offline(self):
        """Atualiza o status de todas as conexões para offline."""
        self.unifique_status.config(text="UNIFIQUE: Offline", bg='red')
        self.claro_status.config(text="CLARO: Offline", bg='red')
        self.coopera_status.config(text="COOPERA: Offline", bg='red')

    def update_status_labels(self):
        """Atualiza os labels a cada 30 segundos, se a conexão SSH estiver estabelecida."""
        # Verifica se a conexão SSH ainda está estabelecida
        if self.connection_established.is_set():
            self.check_status()  # Chama o método para atualizar o status
            self.master.after(30000, self.update_status_labels)  # Chama update_status_labels novamente após 30 segundos
        else:
            logger_test_command.info("Conexão SSH perdida. Parando a checagem das conexões.")
            self.update_all_statuses_offline()  # Atualiza o status de todas as conexões para offline

    def check_interface_status(self, interface, button, name, ssh_client):
        output_queue = queue.Queue()

        # Executa o comando em uma thread
        threading.Thread(target=self.run_test_command, args=(ssh_client, interface, output_queue, name)).start()

        def thread_function():
            try:
                output = output_queue.get()  # Espera até receber o output
                if output is None:
                    logger_test_command.error(f"Erro: A saída do comando é None.")
                    self.master.after(0, lambda: button.config(text=f"{name}: Offline", bg='red'))
                    return

                if name.lower() in output.lower():
                    self.master.after(0, lambda: button.config(text=f"{name}: Online", bg='green'))
                else:
                    self.master.after(0, lambda: button.config(text=f"{name}: Offline", bg='red'))
            except Exception as e:
                logger_test_command.error(f"Erro ao verificar status: {e}")

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
        menu.add_command(label="Desligar", command=lambda: self.run_command("acpipowerbutton", vm_name))
        menu.add_command(label="Forçar Desligamento", command=lambda: self.run_command("poweroff", vm_name))
        menu.add_command(label="Ligar", command=lambda: self.run_command("startvm", vm_name))
        menu.post(self.master.winfo_pointerx(), self.master.winfo_pointery())

    def run_command(self, action, vm_name):
        commands = {
            "acpipowerbutton": f'"C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe" controlvm "{vm_name}" acpipowerbutton',
            "poweroff": f'"C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe" controlvm "{vm_name}" poweroff',
            "startvm": f'"C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe" startvm "{vm_name}" --type headless'
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
        # Definir o tamanho da janela
        log_window.geometry("877x656")  # Largura de 600 pixels e altura de 400 pixels

        # Carregar a posição salva
        self.load_log_position(log_window)

        # Cria um notebook (abas)
        notebook = ttk.Notebook(log_window)
        notebook.pack(expand=1, fill='both')

        # Aba 1: Logs principais
        # Configuração do widget de rolagem
        log_frame_main = tk.Frame(notebook)
        log_text_main = scrolledtext.ScrolledText(log_frame_main, wrap=tk.WORD, state=tk.NORMAL)
        log_text_main.pack(expand=1, fill=tk.BOTH)
        notebook.add(log_frame_main, text='Monitoramento do OMR')

        # Aba 2: Logs do Test Command
        # Configuração do widget de rolagem
        log_frame_test = tk.Frame(notebook)
        log_text_test = scrolledtext.ScrolledText(log_frame_test, wrap=tk.WORD, state=tk.NORMAL)
        log_text_test.pack(expand=1, fill=tk.BOTH)
        notebook.add(log_frame_test, text='Logs das Conexões')

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

            # Agendar a próxima atualização
            self.update_logs_id = log_window.after(1, update_logs)

        # Função para parar o scroll automático
        def stop_auto_scroll():
            self.auto_scroll = False
            if self.update_logs_id:
                log_window.after_cancel(self.update_logs_id)

        # Função para continuar o scroll automático
        def start_auto_scroll():
            self.auto_scroll = True
            update_logs()  # Atualiza imediatamente e reinicia o loop

        # Botões para pausar e retomar o scroll automático
        button_frame = tk.Frame(log_window)
        button_frame.pack(fill=tk.X, pady=5)
    
        stop_button = tk.Button(button_frame, text="Parar Scroll", command=stop_auto_scroll)
        stop_button.pack(side=tk.LEFT, padx=5)
    
        start_button = tk.Button(button_frame, text="Continuar Scroll", command=start_auto_scroll)
        start_button.pack(side=tk.LEFT, padx=5)

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
        def test_connection(ip, port, timeout):
            try:
                socket_info = socket.getaddrinfo(ip, port, socket.AF_INET, socket.SOCK_STREAM)
                conn = socket.create_connection(socket_info[0][4], timeout=timeout)
                conn.close()
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

        # Teste de conexão ao host fornecido na porta 80
        logger_main.info(f"Verificando conexão com o host {host} na porta {port}...")
        if test_connection(host, port, timeout):
            logger_main.info(f"Conexão com o host {host} bem-sucedida.")
            return "ON", "green"
        else:
            logger_main.error(f"Falha na conexão com o host {host}.")
            return "OFF", "blue"

    def ping_xray_jogo(self, host, port=65222, timeout=1):
        def test_connection(ip, port, timeout):
            try:
                socket_info = socket.getaddrinfo(ip, port, socket.AF_INET, socket.SOCK_STREAM)
                conn = socket.create_connection(socket_info[0][4], timeout=timeout)
                conn.close()
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

        # Teste de conexão ao host fornecido na porta 65222
        logger_main.info(f"Verificando conexão com o host {host} na porta {port}...")
        try:
            start_time = time.time()
            socket_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
            conn = socket.create_connection(socket_info[0][4], timeout=timeout)
            conn.sendall(b'PING')
            response = conn.recv(1024)
            conn.close()
            end_time = time.time()
            response_time = int((end_time - start_time) * 1000 / 2)  # Converte para milissegundos e arredonda para inteiro

            if response:
                logger_main.info(f"Conexão com o host {host} bem-sucedida. Tempo de resposta: {response_time} ms")
                return f"ON ({response_time} ms)", "green"
            else:
                logger_main.warning(f"Falha na conexão com o host {host} (sem resposta).")
                return "OFF", "blue"
        except (socket.timeout, socket.error):
            logger_main.error(f"Falha na conexão com o host {host} (exceção).")
            return "OFF", "blue"

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
            # Agendar a execução do restante da função após 20 segundos
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
    def executar_comando_scheduler(self, comando):
        try:
            resultado = subprocess.run(comando, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if resultado.returncode != 0:
                return f"Erro: {resultado.stderr.strip()}"
            return resultado.stdout.strip()
        except Exception as e:
            return f"Erro: {str(e)}"

    def truncar_texto(self, texto, limite=12):
        """Retorna 'Indisponível' se o texto exceder o limite, caso contrário retorna o texto."""
        if len(texto) > limite:
            return "Indisponível"
        return texto


    def atualizar_label_scheduler(self, label_scheduler, label_cc, comando_scheduler, comando_cc):
        resultado_scheduler = self.executar_comando_scheduler(comando_scheduler)
        resultado_cc = self.executar_comando_scheduler(comando_cc)
    
        # Trunca os resultados se necessário
        resultado_scheduler_truncado = self.truncar_texto(resultado_scheduler)
        resultado_cc_truncado = self.truncar_texto(resultado_cc)
    
        # Atualiza as labels usando self.master
        self.master.after(0, lambda: label_scheduler.config(text=f"Scheduler: {resultado_scheduler_truncado}"))
        self.master.after(0, lambda: label_cc.config(text=f"CC: {resultado_cc_truncado}"))

    def executar_comandos_scheduler(self):
       # Define os comandos a serem executados e as funções de execução SSH associadas
        comandos = {
            (self.label_vps_vpn_scheduler, self.label_vps_vpn_cc): (
                ["start", "/B", "sexec", "-profile=J:\\Dropbox Compartilhado\\AmazonWS\\Oracle Ubuntu 22.04 Instance 2\\OpenMPTCP.tlp", "--", "cat", "/proc/sys/net/mptcp/mptcp_scheduler"],
                ["start", "/B", "sexec", "-profile=J:\\Dropbox Compartilhado\\AmazonWS\\Oracle Ubuntu 22.04 Instance 2\\OpenMPTCP.tlp", "--", "cat", "/proc/sys/net/ipv4/tcp_congestion_control"]
            ),
            (self.label_vps_jogo_scheduler, self.label_vps_jogo_cc): (
                ["start", "/B", "sexec", "-profile=J:\\Dropbox Compartilhado\\AmazonWS\\Google Debian 5.4 Instance 3\\OpenMPTCP.tlp", "--", "cat", "/proc/sys/net/mptcp/mptcp_scheduler"],
                ["start", "/B", "sexec", "-profile=J:\\Dropbox Compartilhado\\AmazonWS\\Google Debian 5.4 Instance 3\\OpenMPTCP.tlp", "--", "cat", "/proc/sys/net/ipv4/tcp_congestion_control"]
            ),
            (self.label_omr_vpn_scheduler, self.label_omr_vpn_cc): (
                ["ssh", "-o", "StrictHostKeyChecking=no", "root@192.168.101.1", "cat", "/proc/sys/net/mptcp/mptcp_scheduler"],
                ["ssh", "-o", "StrictHostKeyChecking=no", "root@192.168.101.1", "cat", "/proc/sys/net/ipv4/tcp_congestion_control"]
            ),
            (self.label_omr_jogo_scheduler, self.label_omr_jogo_cc): (
                ["ssh", "-o", "StrictHostKeyChecking=no", "root@192.168.100.1", "cat", "/proc/sys/net/mptcp/mptcp_scheduler"],
                ["ssh", "-o", "StrictHostKeyChecking=no", "root@192.168.100.1", "cat", "/proc/sys/net/ipv4/tcp_congestion_control"]
            ),
        }

        def processar_comandos():
            for (label_scheduler, label_cc), (comando_scheduler, comando_cc) in comandos.items():
                self.atualizar_label_scheduler(label_scheduler, label_cc, comando_scheduler, comando_cc)

        # Executar os comandos em uma thread separada para não bloquear a interface
        threading.Thread(target=processar_comandos).start()

    def atualizar_scheduler(self):
        # Finaliza o processo sexec.exe
        os.system('taskkill /f /im sexec.exe /t')

        # Aguarda 5 segundos
        time.sleep(5)

        # Executa os comandos do scheduler
        self.executar_comandos_scheduler()

#LOGICA PARA BOTÕES DE REINICIAR GLORYTUN E XRAY NA 3° ABA.
    def reiniciar_glorytun_vpn(self):
        """Reinicia o serviço Glorytun através da conexão SSH já estabelecida."""
        if hasattr(self, 'ssh_vpn_client') and self.ssh_vpn_client is not None:
            try:
                self.ssh_vpn_client.exec_command("/etc/init.d/glorytun restart")
            except Exception:
                pass

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
                if hasattr(self, 'ssh_jogo_client') and self.ssh_jogo_client is not None:
                    try:
                        self.ssh_jogo_client.exec_command("/etc/init.d/xray restart")
                    except Exception:
                        pass

        confirmar_reiniciar()

#LOGICA PARA MONITORAMENTO DE VPS E OMR, E ATUALIZAR AS DEVIDAS LABELS NO TOPO DA JANELA PRINCIPAL DA APLICAÇÃO.
    # Inicia o looping de monitoramento de ping.
    def start_pinging_threads(self):
        interval = 2  # Define o intervalo de 2 segundos para os pings
        threading.Thread(target=self.ping_forever_direto, args=(self.url_to_ping_vps_vpn, self.update_status_vps_vpn), daemon=True).start()
        threading.Thread(target=self.ping_forever_direto, args=(self.url_to_ping_vps_jogo, self.update_status_vps_jogo), daemon=True).start()
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
                socket_info = socket.getaddrinfo(ip, port, socket.AF_INET, socket.SOCK_STREAM)
                conn = socket.create_connection(socket_info[0][4], timeout=timeout)
                conn.close()
                return True
            except (socket.timeout, socket.error):
                return False

        # Teste inicial de conexão ao endereço 192.168.101.1 na porta 80
        if not test_connection('192.168.101.1', 80, timeout):
            return "OFF", "red"

        # Teste de conexão ao host fornecido na porta 80
        try:
            start_time = time.time()
            socket_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
            socket.create_connection(socket_info[0][4], timeout=timeout).close()
            end_time = time.time()
            response_time = int((end_time - start_time) * 1000)  # Converte para milissegundos e arredonda para inteiro
            return f"ON ({response_time} ms)", "green"
        except (socket.timeout, socket.error):
            return "OFF", "blue"

    def ping_forever_omr_vpn(self, url, update_func, interval=1):
        while self.ping_forever:
            status, color = self.ping_omr_vpn(url)
            update_func(status, color)
            time.sleep(interval)

    def ping_omr_jogo(self, host, port=65222, timeout=1):
        def test_connection(ip, port, timeout):
            try:
                socket_info = socket.getaddrinfo(ip, port, socket.AF_INET, socket.SOCK_STREAM)
                conn = socket.create_connection(socket_info[0][4], timeout=timeout)
                conn.close()
                return True
            except (socket.timeout, socket.error):
                return False

        # Teste inicial de conexão ao endereço 192.168.100.1 na porta 80
        if not test_connection('192.168.100.1', 80, timeout):
            return "OFF", "red"

        # Teste de conexão ao host fornecido na porta 65222
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
            response_time = int((end_time - start_time) * 1000 / 2)  # Converte para milissegundos e arredonda para inteiro

            # Verifica se a resposta é válida
            if response:
                return f"ON ({response_time} ms)", "green"
            else:
                return "OFF", "blue"
        except (socket.timeout, socket.error):
            return "OFF", "blue"

    def ping_forever_omr_jogo(self, url, update_func, interval=1):
        while self.ping_forever:
            status, color = self.ping_omr_jogo(url)
            update_func(status, color)
            time.sleep(interval)

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

    def ping_forever_direto(self, url, update_func, interval=1):
        while self.ping_forever:
            status, color = self.ping_direto(url)
            update_func(status, color)
            time.sleep(interval)

    def update_status_vps_jogo(self, status, color):
        self.status_label_vps_jogo.config(text=status, fg=color)
        self.update_general_status()

    def update_status_vps_vpn(self, status, color):
        self.status_label_vps_vpn.config(text=status, fg=color)
        self.update_general_status()

    def update_status_omr_vpn(self, status, color):
        self.status_label_omr_vpn.config(text=status, fg=color)
        self.update_general_status()

    def update_status_omr_jogo(self, status, color):
        self.status_label_omr_jogo.config(text=status, fg=color)
        self.update_general_status()

    def update_general_status(self):
        statuses = [
            self.status_label_vps_vpn.cget("text"),
            self.status_label_vps_jogo.cget("text"),
            self.status_label_omr_vpn.cget("text"),
            self.status_label_omr_jogo.cget("text")
        ]
        if all("OFF" in status for status in statuses):
            if self.script_finished:
                self.general_status_frame.config(bg="yellow")
                self.general_status_label.config(bg="yellow")
                self.display_connection_status("Conectando")  # Atualiza para "Conectando"
            else:
                self.general_status_frame.config(bg="red")
                self.general_status_label.config(text="Desconectado", bg="red", fg="black")
        elif any("ON" in status for status in statuses):
            if all("ON" in status for status in statuses):
                self.general_status_frame.config(bg="green")
                self.general_status_label.config(bg="green")
                self.script_finished = False
                self.display_connection_status("Conectado")  # Atualiza para "Conectado"
            else:
                self.general_status_frame.config(bg="yellow")
                self.general_status_label.config(bg="yellow")
                self.script_finished = False
                self.display_connection_status("Conectando")  # Atualiza para "Conectando"
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

        # Botões na parte inferior da janela
        button_frame_bottom = tk.Frame(aba1)
        button_frame_bottom.pack(side="bottom", pady=10)

        # Segunda aba (Configurações de Ping)
        aba2 = ttk.Frame(self.tabs)
        self.tabs.add(aba2, text="Configurações de Ping")

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

        save_button = tk.Button(frame, text="Salvar", command=self.save_addresses)
        save_button.grid(row=4, column=0, columnspan=4, pady=10)

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

        self.top.protocol("WM_DELETE_WINDOW", self.on_close)

# METODO PARA SALVAR USUARIO E SENHA PARA CONEXÃO SSH COM OMR
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
        self.add_text_with_image(button_frame, "Versão: Beta 68 | 2024 - 2024", "icone1.png")
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
