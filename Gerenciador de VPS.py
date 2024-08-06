import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, scrolledtext, colorchooser, ttk
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
from datetime import datetime
from PIL import Image, ImageTk

class ButtonManager:
    def __init__(self, master):
        self.master = master
        self.script_finished = False  # Inicializa a variável de controle para o término do script
        self.omr_restarted = False  # Variável de estado para rastrear se o omr jogo já foi reiniciado
        self.buttons = []
        self.button_frame = None
        self.second_tab_button_frame = None
        self.button_counter = 1  # Inicializa o contador de botões
        self.load_window_position()
        self.create_widgets()
        self.load_buttons()
        self.load_color_map()  # Carrega o mapeamento de cores
        self.top = None
        # Cria menu
        self.create_menu_button()
        self.url_to_ping_vps_jogo = None
        self.url_to_ping_vps_vpn = None
        self.load_addresses()
        # Bind the notebook's tab change event to the method
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
            
    # Cria um botão de menu no canto superior esquerdo
    def create_menu_button(self):
        menu_bar = tk.Menu(self.master)
        self.master.config(menu=menu_bar)

        # Menu de Configurações
        config_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Configurações", menu=config_menu)
        config_menu.add_command(label="Configurações e Gerenciador de Arquivos", command=self.open_omr_manager)
        config_menu.add_command(label="Configurações de Cores", command=self.open_color_config)
        config_menu.add_command(label="Configuração de Endereços", command=self.options_address)
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
        dialog = OMRManagerDialog(self.master)
        self.master.wait_window(dialog.top)

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

    def on_close(self):
        self.save_window_position()
        self.save_color_map()  # Salva o mapeamento de cores
        self.master.destroy()

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
        # Função para abrir o arquivo específico do VPS JOGO
        relative_path = r"Dropbox Compartilhado\AmazonWS\Google Debian 5.4 Instance 3\OpenMPTCP.tlp"  # Substitua pelo caminho relativo do seu arquivo
        filepath = self.os_letter(relative_path)
        if os.path.exists(filepath):
            subprocess.Popen(['start', '', filepath], shell=True)  # Abre o arquivo no sistema operacional padrão
        else:
            print(f"Arquivo não encontrado: {filepath}")

    def abrir_arquivo_vps_vpn(self):
        # Função para abrir o arquivo específico do VPS VPN
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
            self.executar_comandos()

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
        btn_vps_vpn = tk.Button(frame_vps_vpn, text=" VPS  VPN: ", bg='lightgray', justify=tk.CENTER, command=self.abrir_arquivo_vps_vpn).pack(side=tk.LEFT)
        self.status_label_vps_vpn = tk.Label(frame_vps_vpn, text="Aguarde...", bg='lightgray', justify=tk.CENTER)
        self.status_label_vps_vpn.pack(side=tk.LEFT)

        # Label e valor para VPS JOGO
        frame_vps_jogo = tk.Frame(self.top_frame, bg='lightgray')
        frame_vps_jogo.grid(row=0, column=2, padx=5, pady=5, sticky=tk.E+tk.W)
        btn_vps_jogo = tk.Button(frame_vps_jogo, text=" VPS  JOGO: ", bg='lightgray', justify=tk.CENTER, command=self.abrir_arquivo_vps_jogo).pack(side=tk.LEFT)
        self.status_label_vps_jogo = tk.Label(frame_vps_jogo, text="Aguarde...", bg='lightgray', justify=tk.CENTER)
        self.status_label_vps_jogo.pack(side=tk.LEFT)

        # Label (aparência de botão) para OMR VPN
        frame_omr_vpn = tk.Frame(self.top_frame, bg='lightgray')
        frame_omr_vpn.grid(row=1, column=1, padx=5, pady=5, sticky=tk.E+tk.W)
        btn_omr_vpn = tk.Button(frame_omr_vpn, text="OMR VPN:", bg='lightgray', justify=tk.CENTER, command=self.open_OMR_VPN)
        btn_omr_vpn.pack(side=tk.LEFT)
        self.status_label_omr_vpn = tk.Label(frame_omr_vpn, text="Aguarde...", bg='lightgray', fg='black', justify=tk.CENTER)
        self.status_label_omr_vpn.pack(side=tk.LEFT)

        # Label (aparência de botão) para OMR JOGO
        frame_omr_jogo = tk.Frame(self.top_frame, bg='lightgray')
        frame_omr_jogo.grid(row=1, column=2, padx=5, pady=5, sticky=tk.E+tk.W)
        btn_omr_jogo = tk.Button(frame_omr_jogo, text="OMR JOGO:", bg='lightgray', justify=tk.CENTER, command=self.open_OMR_JOGO)
        btn_omr_jogo.pack(side=tk.LEFT)
        self.status_label_omr_jogo = tk.Label(frame_omr_jogo, text="Aguarde...", bg='lightgray', fg='black', justify=tk.CENTER)
        self.status_label_omr_jogo.pack(side=tk.LEFT)

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
        self.button_frame = tk.Frame(self.tab1)
        self.button_frame.pack(side=tk.TOP)

        self.bottom_frame = tk.Frame(self.tab1)
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
        self.second_tab_button_frame = tk.Frame(self.tab2)
        self.second_tab_button_frame.pack(side=tk.TOP, padx=5, pady=5)

        self.bottom_frame2 = tk.Frame(self.tab2)
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
        self.frame_topo = tk.Frame(self.tab3, borderwidth=2, relief=tk.RAISED)
        self.frame_topo.pack(pady=0, fill=tk.X)

        self.frame_geral = tk.Frame(self.tab3, borderwidth=2, relief=tk.SUNKEN)
        self.frame_geral.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.label_topo = tk.Label(self.frame_topo, text="SCHEDULER E CC", font=("Arial", 16))
        self.label_topo.pack()

        self.frame_vps = tk.Frame(self.frame_geral, borderwidth=2, relief=tk.RAISED)
        self.frame_vps.pack(pady=10)

        self.frame_omr = tk.Frame(self.frame_geral, borderwidth=2, relief=tk.RAISED)
        self.frame_omr.pack(pady=10)

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

        # Frame inferior com borda e botões
        self.frame_inferior_scheduler = tk.Frame(self.tab3, borderwidth=2, relief=tk.RAISED)
        self.frame_inferior_scheduler.pack(pady=10, fill=tk.X, side=tk.BOTTOM)

        # Botão para reiniciar o omr-tracker VPN
        self.botao_reiniciar_vpn_scheduler = tk.Button(self.frame_inferior_scheduler, text="Reiniciar omr-tracker VPN", command=self.reiniciar_omr_tracker_vpn)
        self.botao_reiniciar_vpn_scheduler.pack(side=tk.LEFT, padx=10, pady=5)

        # Botão para reiniciar o omr-tracker JOGO
        self.botao_reiniciar_jogo_scheduler = tk.Button(self.frame_inferior_scheduler, text="Reiniciar omr-tracker JOGO", command=self.reiniciar_omr_tracker_jogo)
        self.botao_reiniciar_jogo_scheduler.pack(side=tk.LEFT, padx=10, pady=5)

        # Cria o frame para o rodapé da janela
        self.footer_frame = tk.Frame(self.master, bg='lightgray', borderwidth=1, relief=tk.RAISED)
        self.footer_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Adiciona o label de versão ao rodapé
        self.version_label = tk.Label(self.footer_frame, text="Projeto Temer - ©VempirE_GhosT - Versão: beta 62", bg='lightgray', fg='black')
        self.version_label.pack(side=tk.LEFT, padx=0, pady=0)

    def executar_comando(self, comando):
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


    def atualizar_label(self, label_scheduler, label_cc, comando_scheduler, comando_cc):
        resultado_scheduler = self.executar_comando(comando_scheduler)
        resultado_cc = self.executar_comando(comando_cc)
    
        # Trunca os resultados se necessário
        resultado_scheduler_truncado = self.truncar_texto(resultado_scheduler)
        resultado_cc_truncado = self.truncar_texto(resultado_cc)
    
        # Atualiza as labels usando self.master
        self.master.after(0, lambda: label_scheduler.config(text=f"Scheduler: {resultado_scheduler_truncado}"))
        self.master.after(0, lambda: label_cc.config(text=f"CC: {resultado_cc_truncado}"))

    def executar_comandos(self):
        # Define os comandos a serem executados
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
                ["start", "/B", "sexec", "-profile=J:\\Dropbox Compartilhado\\AmazonWS\\Oracle Ubuntu 22.04 Instance 2\\OpenMPTCP_Router.tlp", "--", "cat", "/proc/sys/net/mptcp/mptcp_scheduler"],
                ["start", "/B", "sexec", "-profile=J:\\Dropbox Compartilhado\\AmazonWS\\Oracle Ubuntu 22.04 Instance 2\\OpenMPTCP_Router.tlp", "--", "cat", "/proc/sys/net/ipv4/tcp_congestion_control"]
            ),
            (self.label_omr_jogo_scheduler, self.label_omr_jogo_cc): (
                ["start", "/B", "sexec", "-profile=J:\\Dropbox Compartilhado\\AmazonWS\\Google Debian 5.4 Instance 3\\OpenMPTCP_Router.tlp", "--", "cat", "/proc/sys/net/mptcp/mptcp_scheduler"],
                ["start", "/B", "sexec", "-profile=J:\\Dropbox Compartilhado\\AmazonWS\\Google Debian 5.4 Instance 3\\OpenMPTCP_Router.tlp", "--", "cat", "/proc/sys/net/ipv4/tcp_congestion_control"]
            ),
        }

        def processar_comandos():
            for (label_scheduler, label_cc), (comando_scheduler, comando_cc) in comandos.items():
                self.atualizar_label(label_scheduler, label_cc, comando_scheduler, comando_cc)

        # Executar os comandos em uma thread separada para não bloquear a interface
        threading.Thread(target=processar_comandos).start()

    def reiniciar_omr_tracker_vpn(self):
        subprocess.Popen(["start", "/B", "sexec", "-profile=J:\\Dropbox Compartilhado\\AmazonWS\\Oracle Ubuntu 22.04 Instance 2\\OpenMPTCP_Router.tlp", "--", "/etc/init.d/omr-tracker", "restart"], shell=True)

    def reiniciar_omr_tracker_jogo(self):
        subprocess.Popen(["start", "/B", "sexec", "-profile=J:\\Dropbox Compartilhado\\AmazonWS\\Google Debian 5.4 Instance 3\\OpenMPTCP_Router.tlp", "--", "/etc/init.d/omr-tracker", "restart"], shell=True)


    def start_pinging_threads(self):
        interval = 2  # Define o intervalo de 2 segundos para os pings
        threading.Thread(target=self.ping_forever_direto, args=(self.url_to_ping_vps_vpn, self.update_status_vps_vpn), daemon=True).start()
        threading.Thread(target=self.ping_forever_direto, args=(self.url_to_ping_vps_jogo, self.update_status_vps_jogo), daemon=True).start()
        threading.Thread(target=self.ping_forever_omr_vpn, args=(self.url_to_ping_omr_vpn, self.update_status_omr_vpn), daemon=True).start()
        threading.Thread(target=self.ping_forever_omr_jogo, args=(self.url_to_ping_omr_jogo, self.update_status_omr_jogo), daemon=True).start()

    def load_addresses(self):
        try:
            with open('addresses.json', 'r') as f:
                addresses = json.load(f)
                self.url_to_ping_vps_jogo = addresses.get("vps_jogo")
                self.url_to_ping_vps_vpn = addresses.get("vps_vpn")
                self.url_to_ping_omr_vpn = addresses.get("omr_vpn")
                self.url_to_ping_omr_jogo = addresses.get("omr_jogo")
        except (FileNotFoundError, json.JSONDecodeError):
            self.url_to_ping_vps_jogo = None
            self.url_to_ping_vps_vpn = None
            self.url_to_ping_omr_vpn = None
            self.url_to_ping_omr_jogo = None

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
            if not self.omr_restarted:  # Verifica se o omr jogo já foi reiniciado
                self.omr_restarted = True  # Define como True para garantir execução única
                time.sleep(5)  # Aguarda 5 segundos
                subprocess.Popen(["start", "/B", "sexec", "-profile=J:\\Dropbox Compartilhado\\AmazonWS\\Google Debian 5.4 Instance 3\\OpenMPTCP_Router.tlp", "--", "/etc/init.d/omr-tracker", "restart"], shell=True)
            return f"ON ({response_time} ms)", "green"
        except (socket.timeout, socket.error):
            return "OFF", "blue"

    def ping_forever_omr_vpn(self, url, update_func, interval=1):
        while True:
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
        while True:
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
        while True:
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
                self.general_status_label.config(text="Conectando", bg="yellow", fg="black")
            else:
                self.general_status_frame.config(bg="red")
                self.general_status_label.config(text="Desconectado", bg="red", fg="black")
        elif any("ON" in status for status in statuses):
            if all("ON" in status for status in statuses):
                self.general_status_frame.config(bg="green")
                self.general_status_label.config(text="Conectado", bg="green", fg="black")
                self.script_finished = False
            else:
                self.general_status_frame.config(bg="yellow")
                self.general_status_label.config(text="Conectando", bg="yellow", fg="black")
                self.script_finished = False
        else:
            self.general_status_frame.config(bg="red")
            self.general_status_label.config(text="Desconectado", bg="red", fg="black")
            self.script_finished = False

        # Verifica se o script terminou e atualiza o status para "Conectando" se necessário
        if self.script_finished:
            self.general_status_frame.config(bg="yellow")
            self.general_status_label.config(text="Conectando", bg="yellow", fg="black")

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
        icon_label.icon = tk.PhotoImage(file=dest_path)
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
        icon_label.icon = tk.PhotoImage(file=dest_path)
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
        icon_label.icon = tk.PhotoImage(file=dest_path)
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
        icon_label.icon = tk.PhotoImage(file=dest_path)
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

    def run_as_admin(self, file_path):
        # Verifica se o arquivo é um .bat
        if not file_path.lower().endswith('.bat'):
            # Executa o arquivo normalmente sem abrir a janela de saída
            subprocess.Popen(shlex.split(f'"{file_path}"'), shell=True)
            return
        
        # Nova janela para mostrar a saída do script
        output_window = tk.Toplevel(self.master)
        output_window.title("Visualizador de Scripts")
    
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

class OMRManagerDialog:
    def __init__(self, master):
        top = self.top = tk.Toplevel(master)
        self.master = master
        self.load_window_position()
        self.top.title("Configurações e Gerenciador de Arquivos")
        #self.top.geometry("800x800")

        # Bloqueia a interação com a janela master
        self.top.grab_set()

        # Define a janela como ativa
        self.top.focus_set()
        
        # Frame para os botões e textos descritivos
        button_frame = tk.Frame(self.top, borderwidth=1, relief=tk.RIDGE)
        button_frame.pack(side="left", padx=10, pady=10, anchor='w')

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

        # Frame para os botões e textos descritivos a direita
        button_frame_right = tk.Frame(self.top, borderwidth=1, relief=tk.RIDGE)
        button_frame_right.pack(side="top", padx=10, pady=10, anchor='w')

        #Primeiro botão
        tk.Label(button_frame_right, text="Edita scritp de alteração de UUID:").pack(side=tk.TOP, anchor='w')
        tk.Button(button_frame_right, text="Editar script", command=self.edit_uuid).pack(side=tk.TOP, anchor='w', padx=5, pady=5)

        # Espaço entre o primeiro botão e o segundo texto
        tk.Label(button_frame_right).pack(side=tk.TOP, pady=6)  # Espaço de 6 pixels entre os widgets

        #Segundo botão
        tk.Label(button_frame_right, text="Backup das Maquinas Virtuais:").pack(side=tk.TOP, anchor='w')
        tk.Button(button_frame_right, text="Executar backup", command=self.backup_virtualbox).pack(side=tk.TOP, anchor='w', padx=5, pady=5)

        # Espaço entre o segundo botão e o terceiro texto
        tk.Label(button_frame_right).pack(side=tk.TOP, pady=6)  # Espaço de 6 pixels entre os widgets

        #Terceiro botão
        tk.Label(button_frame_right, text="Editar arquivo de ajuda:").pack(side=tk.TOP, anchor='w')
        tk.Button(button_frame_right, text="Editar arquivo", command=self.editar_arquivo_ajuda).pack(side=tk.TOP, anchor='w', padx=5, pady=5)

        # Botões na parte inferior da janela
        button_frame_bottom = tk.Frame(self.top)
        button_frame_bottom.pack(side="bottom", pady=10)
        #tk.Button(button_frame_bottom, text="Cancelar", command=self.save).pack(side=tk.LEFT, padx=10)

        self.top.protocol("WM_DELETE_WINDOW", self.on_close)

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

class open_options_address:
    def __init__(self, master):
        top = self.top = tk.Toplevel(master)
        self.master = master
        self.load_window_position()
        self.top.title("Configurações de Ping")
        self.load_addresses()
        #self.top.geometry("250x250")

        # Bloqueia a interação com a janela master
        self.top.grab_set()

        # Define a janela como ativa
        self.top.focus_set()

        # Define o evento de fechamento para salvar a posição da janela
        self.top.protocol("WM_DELETE_WINDOW", self.on_close)

        # Frame com borda
        frame = tk.Frame(self.top, bd=2, relief=tk.RAISED)
        frame.pack(padx=10, pady=10)

        # Labels e Entries dentro do frame
        tk.Label(frame, text="Endereço VPS VPN:").grid(row=0, column=0, sticky=tk.W)
        vps_vpn_entry = tk.Entry(frame, width=30)  # Aumente o valor de width conforme necessário
        vps_vpn_entry.grid(row=0, column=1, padx=5, pady=5)
        vps_vpn_entry.insert(0, self.url_to_ping_vps_vpn or '')
        
        tk.Label(frame, text="Endereço VPS Jogo:").grid(row=1, column=0, sticky=tk.W)
        vps_jogo_entry = tk.Entry(frame, width=30)  # Aumente o valor de width conforme necessário
        vps_jogo_entry.grid(row=1, column=1, padx=5, pady=5)
        vps_jogo_entry.insert(0, self.url_to_ping_vps_jogo or '')

        tk.Label(frame, text="Endereço OMR VPN:").grid(row=2, column=0, sticky=tk.W)
        omr_vpn_entry = tk.Entry(frame, width=30)
        omr_vpn_entry.grid(row=2, column=1, padx=5, pady=5)
        omr_vpn_entry.insert(0, self.url_to_ping_omr_vpn or '')

        tk.Label(frame, text="Endereço OMR Jogo:").grid(row=3, column=0, sticky=tk.W)
        omr_jogo_entry = tk.Entry(frame, width=30)
        omr_jogo_entry.grid(row=3, column=1, padx=5, pady=5)
        omr_jogo_entry.insert(0, self.url_to_ping_omr_jogo or '')

        save_button = tk.Button(frame, text="Salvar", command=lambda: self.save_addresses(
            vps_jogo_entry.get(), vps_vpn_entry.get(), omr_vpn_entry.get(), omr_jogo_entry.get()))
        save_button.grid(row=4, column=0, columnspan=2, pady=10)

    def save_addresses(self, vps_jogo, vps_vpn, omr_vpn, omr_jogo):
        self.url_to_ping_vps_jogo = vps_jogo
        self.url_to_ping_vps_vpn = vps_vpn
        self.url_to_ping_omr_vpn = omr_vpn
        self.url_to_ping_omr_jogo = omr_jogo
        addresses = {
            "vps_jogo": vps_jogo,
            "vps_vpn": vps_vpn,
            "omr_vpn": omr_vpn,
            "omr_jogo": omr_jogo
        }
        with open('addresses.json', 'w') as f:
            json.dump(addresses, f)
        # messagebox.showinfo("Info", "Endereços salvos com sucesso!")

    def load_addresses(self):
        try:
            with open('addresses.json', 'r') as f:
                addresses = json.load(f)
                self.url_to_ping_vps_jogo = addresses.get("vps_jogo")
                self.url_to_ping_vps_vpn = addresses.get("vps_vpn")
                self.url_to_ping_omr_vpn = addresses.get("omr_vpn")
                self.url_to_ping_omr_jogo = addresses.get("omr_jogo")
        except (FileNotFoundError, json.JSONDecodeError):
            self.url_to_ping_vps_jogo = None
            self.url_to_ping_vps_vpn = None
            self.url_to_ping_omr_vpn = None
            self.url_to_ping_omr_jogo = None

    def save(self):
        self.top.grab_release()
        self.save_window_position()
        self.top.destroy()

    def load_window_position(self):
        if os.path.isfile("open_options_address.json"):
            with open("open_options_address.json", "r") as f:
                position = json.load(f)
                self.top.geometry("+{}+{}".format(position["x"], position["y"]))

    def save_window_position(self):
        position = {
            "x": self.top.winfo_x(),
            "y": self.top.winfo_y()
        }
        with open("open_options_address.json", "w") as f:
            json.dump(position, f)

    def on_close(self):
        self.top.grab_release()
        #self.save_addresses(self.url_to_ping_vps_jogo, self.url_to_ping_vps_vpn)
        self.save_window_position()
        self.top.destroy()

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
        self.add_text_with_image(button_frame, "Versão: Beta 62", "icone1.png")
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
