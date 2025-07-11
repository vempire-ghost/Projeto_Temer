import tkinter as tk
from tkinter import messagebox
import socket
import json
import threading
import time
import pystray
from PIL import Image, ImageDraw
import sys
import configparser
import os
import winreg  # Adicionado para manipulação do registro do Windows
import requests
from packaging import version
from datetime import datetime
from datetime import timezone
import logging

# Determina o caminho base para arquivos do aplicativo
if getattr(sys, 'frozen', False):
    # Se o aplicativo estiver congelado (compilado)
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

# Cria um diretório para logs se não existir
log_dir = os.path.join(application_path, 'logs')
os.makedirs(log_dir, exist_ok=True)

# Configuração do caminho do arquivo de log
log_file = os.path.join(log_dir, 'atualizador.log')

# Configuração básica do logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# Altera o diretório de trabalho para o local do aplicativo
os.chdir(application_path)

# Função para retornar a versão
def get_version():
    return "Beta 3.3"

class ClientApp:
    def __init__(self):
        # Verificar e atualizar arquivos antes de qualquer inicialização
        self.verificar_e_atualizar_arquivos()
        self.root = tk.Tk()
        self.root.title("Cliente do Projeto Temer")
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        
        # Inicializa as variáveis antes de carregar a configuração
        self.server_ip = tk.StringVar()
        self.server_port = tk.IntVar()
        self.connected = False
        self.server_status = False
        self.tray_icon = None
        self.auto_reconnect = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10000
        self.reconnect_delay = 5  # segundos
        self.update_thread = None
        self.running = True
        self.notify_provider_changes = tk.BooleanVar(value=False)  # Valor padrão True (ativado)
        self.control_proxifier = tk.BooleanVar(value=False)
        
        # Variáveis para os checkboxes
        self.start_with_windows = tk.BooleanVar()
        self.start_minimized = tk.BooleanVar()
        
        # Carrega configurações do arquivo .ini
        self.config = configparser.ConfigParser()
        self.config_file = 'cliente_config.ini'
        self.load_config()
        
        # Define os valores das variáveis após carregar a configuração
        self.server_ip.set(self.config.get('DEFAULT', 'host', fallback="192.168.2.21"))
        self.server_port.set(self.config.getint('DEFAULT', 'port', fallback=5000))
        self.start_with_windows.set(self.config.getboolean('DEFAULT', 'start_with_windows', fallback=False))
        self.start_minimized.set(self.config.getboolean('DEFAULT', 'start_minimized', fallback=False))
        
        # Configura inicialização com Windows
        self.configure_start_with_windows()
        
        self.connected = False
        self.server_status = False
        self.tray_icon = None
        
        self.setup_ui()
        self.create_tray_icon()
        self.update_thread = None
        self.running = True
        
        # Configura o gerenciamento da posição da janela
        self.setup_window_position()

        # Inicia tentativa de conexão automática
        self.root.after(1000, self.auto_connect)
        
        # Se configurado para iniciar minimizado
        if self.start_minimized.get():
            self.root.withdraw()  # Esconde a janela imediatamente

# FUNÇÃO PARA DOWNLOAD E ATUALIZAÇÃO DO PROGRAMA.
    def verificar_e_atualizar_arquivos(self):
        arquivos_necessarios = {
            "server_status_desligado.png": ("vempire-ghost/Projeto_Temer", "server_status_desligado.png"),
            "server_status_ligado.png": ("vempire-ghost/Projeto_Temer", "server_status_ligado.png"),
            "server_status_operacional.png": ("vempire-ghost/Projeto_Temer", "server_status_operacional.png"),
            "cliente_temer.exe": ("vempire-ghost/Projeto_Temer", "dist/cliente_temer.exe")
        }
        
        executavel_atualizado = False
        
        def get_github_file_last_modified(repo, path):
            api_url = f"https://api.github.com/repos/{repo}/commits?path={path}&page=1&per_page=1"
            try:
                response = requests.get(api_url, timeout=10)
                if response.status_code == 200:
                    commits = response.json()
                    if commits:
                        last_modified = commits[0]['commit']['committer']['date']
                        return datetime.strptime(last_modified, '%Y-%m-%dT%H:%M:%SZ')
                else:
                    logging.warning(f"Falha ao acessar API GitHub para {path}. Status code: {response.status_code}")
            except Exception as e:
                logging.error(f"Erro ao acessar API GitHub para {path}: {str(e)}", exc_info=True)
            return None
        
        for arquivo, (repo, path) in arquivos_necessarios.items():
            precisa_baixar = False
            download_url = f"https://raw.githubusercontent.com/{repo}/main/{path}"
            
            if not os.path.exists(arquivo):
                precisa_baixar = True
                logging.info(f"Arquivo {arquivo} não encontrado localmente. Iniciando download...")
            else:
                try:
                    if arquivo == "cliente_temer.exe":
                        # Verificação robusta para o executável
                        data_remota = get_github_file_last_modified(repo, path)
                        
                        if data_remota:
                            data_local = datetime.fromtimestamp(os.path.getmtime(arquivo)).astimezone(timezone.utc)
                            data_remota = data_remota.replace(tzinfo=timezone.utc)
                            
                            if data_remota > data_local:
                                precisa_baixar = True
                                logging.info(f"Executável desatualizado. GitHub: {data_remota}, Local: {data_local}")
                            else:
                                logging.debug(f"Executável atualizado. GitHub: {data_remota}, Local: {data_local}")
                        else:
                            # Fallback para verificação por tamanho
                            response = requests.head(download_url, timeout=10)
                            if response.status_code == 200:
                                tamanho_remoto = int(response.headers.get('Content-Length', 0))
                                tamanho_local = os.path.getsize(arquivo)
                                if tamanho_remoto != tamanho_local:
                                    precisa_baixar = True
                                    logging.info(f"Executável com tamanho diferente. Remoto: {tamanho_remoto} bytes, Local: {tamanho_local} bytes")
                    else:
                        # Verificação simplificada para imagens
                        response = requests.head(download_url, timeout=10)
                        if response.status_code == 200:
                            tamanho_remoto = int(response.headers.get('Content-Length', 0))
                            tamanho_local = os.path.getsize(arquivo)
                            if tamanho_remoto != tamanho_local:
                                precisa_baixar = True
                                logging.info(f"Imagem {arquivo} com tamanho diferente. Remoto: {tamanho_remoto} bytes, Local: {tamanho_local} bytes")
                        else:
                            logging.warning(f"Falha ao verificar imagem {arquivo}. Status code: {response.status_code}")
                except Exception as e:
                    logging.error(f"Erro ao verificar {arquivo}: {str(e)}", exc_info=True)
                    continue
            
            if precisa_baixar:
                try:
                    logging.info(f"Iniciando download do arquivo {arquivo}...")
                    response = requests.get(download_url, timeout=30)
                    if response.status_code == 200:
                        if arquivo == "cliente_temer.exe":
                            # Nome temporário para o novo executável
                            temp_name = "cliente_temer_new.exe"
                            with open(temp_name, 'wb') as f:
                                f.write(response.content)
                            
                            # Cria script de atualização para Windows
                            if os.name == 'nt':
                                with open("update.bat", "w") as f:
                                    f.write(f"""
    @echo off
    echo [ATUALIZADOR] Encerrando aplicativo...
    taskkill /f /im cliente_temer.exe >nul 2>&1
    timeout /t 2 >nul

    echo [ATUALIZADOR] Atualizando executável...
    move /y "cliente_temer_new.exe" "cliente_temer.exe" >nul
    timeout /t 2 >nul

    echo [ATUALIZADOR] Criando script de inicialização...
    (
        echo @echo off
        echo cd /d "%~dp0"
        echo "cliente_temer.exe"
        echo del "%%~f0"
        echo taskkill /F /IM cmd.exe
        echo exit
    ) > iniciar.bat

    echo [ATUALIZADOR] Iniciando nova versão...
    start "" /B cmd /c "cd /d %~dp0 && cliente_temer.exe"
    timeout /t 2 >nul
    taskkill /F /IM cmd.exe
    exit
    """)
                                # Executa o script de atualização
                                os.startfile("update.bat")
                                executavel_atualizado = True
                                logging.warning("ATENÇÃO: Executável atualizado. O aplicativo será reiniciado automaticamente.")
                                sys.exit(0)
                            else:
                                # Script para Linux/Mac
                                with open("update.sh", "w") as f:
                                    f.write(f"""#!/bin/bash
    echo "[ATUALIZADOR] Aguardando encerramento do aplicativo..."
    sleep 2
    pkill -f cliente_temer
    echo "[ATUALIZADOR] Atualizando executável..."
    mv -f "{temp_name}" "cliente_temer"
    chmod +x "cliente_temer"
    echo "[ATUALIZADOR] Iniciando nova versão..."
    ./cliente_temer &
    rm -f update.sh
    exit
    """)
                                os.chmod("update.sh", 0o755)
                                os.system("./update.sh &")
                                sys.exit(0)
                        else:
                            # Para arquivos que não são o executável principal
                            with open(arquivo, 'wb') as f:
                                f.write(response.content)
                            logging.info(f"Download do arquivo {arquivo} concluído com sucesso")
                    else:
                        logging.error(f"Falha no download de {arquivo}. Status code: {response.status_code}")
                except Exception as e:
                    logging.error(f"Erro durante o download de {arquivo}: {str(e)}", exc_info=True)
        
        return executavel_atualizado

# FUNÇÃO PARA INICIAR COM O WINDOWS
    def configure_start_with_windows(self):
        """Configura ou remove a entrada no registro para iniciar com o Windows"""
        key = winreg.HKEY_CURRENT_USER
        subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "ClientApp"
        app_path = os.path.abspath(sys.argv[0])
        
        try:
            with winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE) as registry_key:
                if self.start_with_windows.get():
                    winreg.SetValueEx(registry_key, app_name, 0, winreg.REG_SZ, app_path)
                else:
                    try:
                        winreg.DeleteValue(registry_key, app_name)
                    except WindowsError:
                        pass  # A chave não existe, não há problema
        except WindowsError as e:
            print(f"Erro ao acessar o registro do Windows: {e}")

# FUNÇÃO PARA SALVAR E CARREGAR TAMANHO E POSIÇÃO DA JANELA.
    def setup_window_position(self):
        """Configura a posição da janela com base nas configurações salvas"""
        # Carrega a posição salva ou usa valores padrão
        window_x = self.config.getint('WINDOW', 'x', fallback=100)
        window_y = self.config.getint('WINDOW', 'y', fallback=100)
        window_width = self.config.getint('WINDOW', 'width', fallback=400)
        window_height = self.config.getint('WINDOW', 'height', fallback=300)
        
        # Define a geometria da janela
        self.root.geometry(f"{window_width}x{window_height}+{window_x}+{window_y}")
        
        # Vincula o evento de movimento para salvar a posição
        self.root.bind('<Configure>', self.save_window_position)
    
    def save_window_position(self, event=None):
        """Salva a posição e tamanho atual da janela"""
        if event and event.widget == self.root:
            # Verifica se a janela não está minimizada
            if not self.root.state() == 'iconic':
                # Obtém a geometria atual
                geometry = self.root.geometry()
                parts = geometry.split('+')
                
                if len(parts) == 3:
                    # Extrai dimensões e posição
                    dimensions = parts[0].split('x')
                    if len(dimensions) == 2:
                        width, height = dimensions
                        x, y = parts[1], parts[2]
                        
                        # Atualiza as configurações
                        self.config['WINDOW'] = {
                            'x': x,
                            'y': y,
                            'width': width,
                            'height': height
                        }
# FUNÇÕES PARA CARREGAR E SALVAR OPÇÕES DO PROGRAMA.                        
    def load_config(self):
        """Carrega as configurações do arquivo .ini ou cria um novo com valores padrão"""
        if not os.path.exists(self.config_file):
            # Cria configuração padrão se o arquivo não existir
            self.config['DEFAULT'] = {
                'host': '192.168.2.21',
                'port': '5000',
                'start_with_windows': 'False',
                'start_minimized': 'False',
                'notify_provider_changes': 'False'  # Adicionado
            }
            self.config['WINDOW'] = {
                'x': '100',
                'y': '100',
                'width': '400',
                'height': '300'
            }
            with open(self.config_file, 'w') as configfile:
                self.config.write(configfile)
        else:
            self.config.read(self.config_file)
            # Carrega a configuração de notificação
            self.notify_provider_changes.set(self.config.getboolean('DEFAULT', 'notify_provider_changes', fallback=False))
            self.control_proxifier.set(self.config.getboolean('DEFAULT', 'control_proxifier', fallback=False)) 
    
    def save_config(self):
        """Salva as configurações atuais no arquivo .ini"""
        if hasattr(self, 'server_ip') and hasattr(self, 'server_port'):
            self.config['DEFAULT'] = {
                'host': self.server_ip.get(),
                'port': str(self.server_port.get()),
                'start_with_windows': str(self.start_with_windows.get()),
                'start_minimized': str(self.start_minimized.get()),
                'notify_provider_changes': str(self.notify_provider_changes.get()),
                'control_proxifier': str(self.control_proxifier.get())  # Adicione esta linha
            }
            
            # Salva também a posição atual da janela
            if hasattr(self, 'root'):
                geometry = self.root.geometry()
                parts = geometry.split('+')
                if len(parts) == 3:
                    dimensions = parts[0].split('x')
                    if len(dimensions) == 2:
                        width, height = dimensions
                        x, y = parts[1], parts[2]
                        self.config['WINDOW'] = {
                            'x': x,
                            'y': y,
                            'width': width,
                            'height': height
                        }
            
            with open(self.config_file, 'w') as configfile:
                self.config.write(configfile)
            
            # Configura inicialização com Windows
            self.configure_start_with_windows()
            
            #messagebox.showinfo("Sucesso", "Configurações salvas com sucesso!")

# FUNÇÃO PARA CRIAR A INTERFACE DO PROGRAMA.    
    def setup_ui(self):
        """Configura a interface do usuário"""
        # Frame principal com borda
        main_frame = tk.Frame(self.root, bd=2, relief=tk.GROOVE, padx=5, pady=5)
        main_frame.pack(padx=10, pady=(10, 0), fill=tk.BOTH, expand=True)
        
        # Frame para o conteúdo
        content_frame = tk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Entrada de IP
        tk.Label(content_frame, text="IP do Servidor:").grid(row=0, column=0, sticky="w", pady=(0, 5))
        tk.Entry(content_frame, textvariable=self.server_ip).grid(row=0, column=1, pady=(0, 5))
        
        # Entrada de Porta
        tk.Label(content_frame, text="Porta:").grid(row=1, column=0, sticky="w", pady=(0, 5))
        tk.Entry(content_frame, textvariable=self.server_port).grid(row=1, column=1, pady=(0, 5))
        
        # Checkboxes
        tk.Checkbutton(content_frame, text="Iniciar com Windows", variable=self.start_with_windows).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(0, 5))
        tk.Checkbutton(content_frame, text="Iniciar minimizado", variable=self.start_minimized).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(0, 5))
        # Novo checkbox para notificações
        tk.Checkbutton(content_frame, text="Notificar mudanças nos provedores", variable=self.notify_provider_changes).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(0, 10))

        tk.Checkbutton(content_frame, text="Controlar Proxifier automaticamente", 
                      variable=self.control_proxifier).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(0, 10))
        
        # Botões
        btn_frame = tk.Frame(content_frame)
        btn_frame.grid(row=6, columnspan=2, pady=(0, 10))
        
        tk.Button(btn_frame, text="Conectar", command=self.auto_connect).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Desconectar", command=self.disconnect).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Salvar Config", command=self.save_config).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Sair", command=self.quit_app).pack(side=tk.RIGHT, padx=5)
        
        # Status
        self.status_label = tk.Label(content_frame, text="Status: Desconectado", fg="red")
        self.status_label.grid(row=7, columnspan=2, pady=(0, 5))
        
        # Frame para status dos provedores
        self.providers_frame = tk.Frame(content_frame)
        self.providers_frame.grid(row=8, columnspan=2, pady=(5, 10), sticky="ew")
        
        # Labels para status dos provedores
        self.coopera_label = tk.Label(self.providers_frame, text="Coopera: Offline", fg="red")
        self.coopera_label.pack(side=tk.LEFT, padx=5)
        
        self.claro_label = tk.Label(self.providers_frame, text="Claro: Offline", fg="red")
        self.claro_label.pack(side=tk.LEFT, padx=5)
        
        self.unifique_label = tk.Label(self.providers_frame, text="Unifique: Offline", fg="red")
        self.unifique_label.pack(side=tk.LEFT, padx=5)
        
        # Cria o frame para o rodapé da janela
        self.footer_frame = tk.Frame(self.root, bg='lightgray', borderwidth=1, relief=tk.RAISED)
        self.footer_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Adiciona o label de versão ao rodapé
        self.version_label = tk.Label(self.footer_frame, text=f"Projeto Xandão - ©VempirE_GhosT - Versão: {get_version()}", bg='lightgray', fg='black')
        self.version_label.pack(side=tk.LEFT, padx=0, pady=0)

        # Se estiver minimizado, garante que a janela não será mostrada
        if not self.start_minimized.get():
            self.root.deiconify()  # Mostra a janela apenas se não for para iniciar minimizado

# FUNÇÃO PARA LOCALIZAR E INICIAR O PROXIFIER.
    def find_proxifier_path(self):
        """Busca abrangente no registro do Windows por qualquer entrada que aponte para proxifier.exe"""
        try:
            # 1. Primeiro verifica nos locais padrão de aplicativos (mais rápido)
            standard_locations = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Proxifier.exe"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\Proxifier.exe"),
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths\Proxifier.exe")
            ]

            for root, subkey in standard_locations:
                try:
                    with winreg.OpenKey(root, subkey) as key:
                        path = winreg.QueryValue(key, None)
                        if path and os.path.exists(path):
                            return os.path.abspath(path)
                except WindowsError:
                    continue

            # 2. Busca recursiva por menções a proxifier.exe no registro
            registry_roots = [
                winreg.HKEY_LOCAL_MACHINE,
                winreg.HKEY_CURRENT_USER,
                winreg.HKEY_CLASSES_ROOT
            ]

            search_keys = [
                r"SOFTWARE",
                r"SOFTWARE\WOW6432Node",
                r"Microsoft\Windows\CurrentVersion\Uninstall",
                r"Classes\Applications"
            ]

            def search_registry(root, key_path, depth=0):
                if depth > 5:  # Limita a profundidade da busca
                    return None
                
                try:
                    with winreg.OpenKey(root, key_path) as key:
                        for i in range(0, winreg.QueryInfoKey(key)[0]):
                            subkey_name = winreg.EnumKey(key, i)
                            full_path = f"{key_path}\\{subkey_name}" if key_path else subkey_name
                            
                            # Verifica valores na chave atual
                            try:
                                with winreg.OpenKey(root, full_path) as subkey:
                                    for j in range(0, winreg.QueryInfoKey(subkey)[1]):
                                        name, value, _ = winreg.EnumValue(subkey, j)
                                        if isinstance(value, str) and "proxifier.exe" in value.lower():
                                            # Tenta extrair um caminho válido
                                            path = self.extract_path_from_string(value)
                                            if path and os.path.exists(path):
                                                return os.path.abspath(path)
                            except WindowsError:
                                pass
                            
                            # Busca recursiva
                            result = search_registry(root, full_path, depth + 1)
                            if result:
                                return result
                except WindowsError:
                    pass
                return None

            for root in registry_roots:
                for key in search_keys:
                    path = search_registry(root, key)
                    if path:
                        return path

            # 3. Verifica locais comuns de instalação
            common_paths = [
                r"C:\Program Files\Proxifier\Proxifier.exe",
                r"C:\Program Files (x86)\Proxifier\Proxifier.exe",
                r"C:\Program Files\Proxifier PE\Proxifier.exe",
                r"C:\Program Files (x86)\Proxifier PE\Proxifier.exe",
                os.path.expandvars(r"%ProgramFiles%\Proxifier\Proxifier.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Proxifier\Proxifier.exe"),
                os.path.expandvars(r"%ProgramFiles%\Proxifier PE\Proxifier.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Proxifier PE\Proxifier.exe"),
                os.path.expandvars(r"%LocalAppData%\Programs\Proxifier\Proxifier.exe")
            ]

            for path in common_paths:
                if os.path.exists(path):
                    return os.path.abspath(path)

            # 4. Tenta encontrar no PATH do sistema
            import shutil
            path = shutil.which("Proxifier.exe")
            if path:
                return os.path.abspath(path)

        except Exception as e:
            logging.error(f"Erro ao tentar localizar o Proxifier: {str(e)}")
        
        return None

    def extract_path_from_string(self, s):
        """Extrai um caminho de arquivo válido de uma string que contenha 'proxifier.exe'"""
        patterns = [
            r'"[^"]*proxifier\.exe"',  # Caminhos entre aspas
            r'\b[a-z]:\\[^"]*proxifier\.exe\b',  # Caminhos sem aspas
            r'\\[^"]*proxifier\.exe\b'  # Caminhos de rede
        ]
        
        import re
        for pattern in patterns:
            match = re.search(pattern, s, re.IGNORECASE)
            if match:
                path = match.group(0).strip('"')
                if os.path.exists(path):
                    return path
                # Tenta encontrar o executável no caminho pai
                dir_path = os.path.dirname(path)
                if os.path.exists(dir_path):
                    for file in os.listdir(dir_path):
                        if file.lower() == "proxifier.exe":
                            return os.path.join(dir_path, file)
        return None

    def start_proxifier(self):
        """Inicia o Proxifier se não estiver rodando"""
        try:
            # Primeiro verifica se já está rodando
            if self.is_proxifier_running():
                logging.info("Proxifier já está em execução")
                return True

            # Localiza o executável
            proxifier_path = self.find_proxifier_path()
            
            if not proxifier_path:
                logging.error("Não foi possível localizar o Proxifier no sistema")
                return False

            # Inicia o Proxifier
            os.system(f'start "" "{proxifier_path}"')
            logging.info(f"Proxifier iniciado com sucesso a partir de: {proxifier_path}")
            return True
            
        except Exception as e:
            logging.error(f"Erro ao iniciar Proxifier: {str(e)}")
            return False

    def is_proxifier_running(self):
        """Verifica se o Proxifier já está em execução"""
        try:
            # Usa tasklist para verificar se o processo está rodando
            output = os.popen('tasklist /FI "IMAGENAME eq Proxifier.exe"').read()
            return "Proxifier.exe" in output
        except Exception as e:
            logging.error(f"Erro ao verificar se Proxifier está rodando: {str(e)}")
            return False

    def stop_proxifier(self):
        """Encerra o Proxifier se estiver rodando"""
        try:
            os.system('taskkill /f /im proxifier.exe >nul 2>&1')
            logging.info("Proxifier encerrado com sucesso")
        except Exception as e:
            logging.error(f"Erro ao encerrar Proxifier: {str(e)}")

    def check_and_control_proxifier(self):
        """Verifica o status e controla o Proxifier conforme necessário"""
        if not self.control_proxifier.get():
            return
            
        if self.server_status:  # Se estiver operacional
            self.start_proxifier()
        else:
            self.stop_proxifier()

# FUNÇÃO PARA CRIAR E CONTROLAR O ICONE DE TRAY.
    def get_tray_tooltip(self):
        """Retorna o texto completo para o tooltip do tray icon"""
        base_text = "Projeto Xandão"
        
        if not self.connected:
            return f"{base_text}\nStatus: Desligado"
        
        status_text = "Servidor: " + ("Operacional" if self.server_status else "Ligado")
        
        # Adiciona status dos provedores
        providers_text = []
        if hasattr(self, 'coopera_status'):
            providers_text.append(f"Coopera: {'Online' if self.coopera_status else 'Offline'}")
        if hasattr(self, 'claro_status'):
            providers_text.append(f"Claro: {'Online' if self.claro_status else 'Offline'}")
        if hasattr(self, 'unifique_status'):
            providers_text.append(f"Unifique: {'Online' if self.unifique_status else 'Offline'}")
        
        full_text = f"{base_text}\n{status_text}"
        if providers_text:
            full_text += "\n" + "\n".join(providers_text)
        
        return full_text

    def create_tray_icon(self):
        """Cria o ícone na bandeja do sistema"""
        # Cria imagens para os diferentes estados
        self.red_icon = self.create_icon_image("red")
        self.blue_icon = self.create_icon_image("blue")
        self.green_icon = self.create_icon_image("green")
        
        # Menu do tray icon (agora com a opção de desligamento)
        menu = (
            pystray.MenuItem("Abrir", self.restore_from_tray),
            pystray.MenuItem("Desligar Servidor", self.send_poweroff_command),
            pystray.MenuItem("Sair", self.quit_app)
        )
        
        self.tray_icon = pystray.Icon(
            "server_client",
            self.red_icon,
            self.get_tray_tooltip(),
            menu
        )
        
        # Inicia uma thread para o tray icon
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def create_icon_image(self, color):
        """Cria uma imagem para o tray icon com a imagem especificada"""
        try:
            if color == "red":
                image_path = "server_status_desligado.png"
            elif color == "blue":
                image_path = "server_status_ligado.png"
            elif color == "green":
                image_path = "server_status_operacional.png"
            else:
                # Fallback para uma imagem padrão se a cor não for reconhecida
                image_path = "server_status_desligado.png"
            
            # Carrega a imagem do arquivo
            image = Image.open(image_path).convert("RGBA")
            
            # Redimensiona para 64x64 se necessário (opcional)
            if image.size != (64, 64):
                image = image.resize((64, 64), Image.Resampling.LANCZOS)
                
            return image
        except Exception as e:
            print(f"Erro ao carregar imagem do ícone: {e}")
            # Fallback: cria um ícone sólido se a imagem não puder ser carregada
            width = 64
            height = 64
            image = Image.new('RGB', (width, height), (0, 0, 0, 0))
            dc = ImageDraw.Draw(image)
            
            if color == "red":
                dc.rectangle((0, 0, width, height), fill=(255, 0, 0))
            elif color == "blue":
                dc.rectangle((0, 0, width, height), fill=(0, 0, 255))
            elif color == "green":
                dc.rectangle((0, 0, width, height), fill=(0, 255, 0))
            
            return image

    def update_tray_icon(self):
        """Atualiza o ícone na bandeja com base no status"""
        if not self.connected or self.reconnect_attempts > 0:
            self.tray_icon.icon = self.red_icon
        elif self.server_status:
            self.tray_icon.icon = self.green_icon
        else:
            self.tray_icon.icon = self.blue_icon
        
        if hasattr(self.tray_icon, '_update_icon'):
            self.tray_icon._update_icon()

# FUNÇÃO PARA DESLIGAR O SERVIDOR REMOTO, VPS, OMR E O WINDOWS.
    def send_poweroff_command(self):
        """Envia comando de desligamento para o servidor após confirmação"""
        if not self.connected:
            messagebox.showwarning("Aviso", "Não conectado ao servidor")
            return
        
        # Janela de confirmação
        confirm = messagebox.askyesno(
            "Confirmar Desligamento",
            "Tem certeza que deseja desligar o servidor?\nEsta ação não pode ser desfeita.",
            icon='warning'
        )
        
        if not confirm:
            return  # Usuário cancelou a ação
        
        try:
            # Cria um socket temporário para enviar o comando
            self.notify_provider_changes = tk.BooleanVar(value=False)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3)
                s.connect((self.server_ip.get(), self.server_port.get()))
                
                # Envia o comando de desligamento
                request = json.dumps({'action': 'poweroff'})
                s.send(request.encode('utf-8'))
                
                # Aguarda resposta
                response = s.recv(1024)
                if response:
                    data = json.loads(response.decode('utf-8'))
                    if data.get('success', False):
                        messagebox.showinfo("Sucesso", "Comando de desligamento enviado com sucesso")
                    else:
                        messagebox.showerror("Erro", "Falha ao executar desligamento no servidor")
        
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao enviar comando: {str(e)}")

# FUNÇÕES DE CONEXÃO E DESCONEXÃO DO PROGRAMA COM O SERVIDOR.    
    def auto_connect(self):
        """Tenta conectar automaticamente ao servidor"""
        try:
            if not self.connected and self.auto_reconnect:
                # Inicia uma thread para verificar o ping antes de conectar
                threading.Thread(target=self.ping_and_connect, daemon=True).start()
        except Exception as e:
            print(f"Erro em auto_connect: {e}")
            # Agenda nova tentativa
            self.root.after(5000, self.auto_connect)

    def ping_and_connect(self):
        """Verifica se o host responde antes de tentar conectar (Windows apenas)"""
        def silent_ping(host, port, timeout=2):
            """Testa conectividade usando socket TCP (mais confiável que ICMP no Windows)"""
            try:
                # Atualiza ícone para vermelho enquanto tenta conectar
                self.root.after(0, self.update_tray_icon)
                self.root.after(0, lambda: self.status_label.config(
                    text="Status: Desconectado", 
                    fg="red"))
                print(f"[DEBUG] Tentando conexão TCP com {host}:{port}...")
                # Cria um socket TCP
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(timeout)
                
                # Tenta conectar
                s.connect((host, port))
                s.close()
                print("[DEBUG] Conexão TCP bem-sucedida (host alcançável)")
                return True
            except socket.timeout:
                print("[DEBUG] Timeout na conexão TCP")
                return False
            except socket.error as e:
                print(f"[DEBUG] Erro na conexão TCP: {e}")
                return False
            except Exception as e:
                print(f"[DEBUG] Erro inesperado: {e}")
                return False

        print(f"[DEBUG] Iniciando ping_and_connect para {self.server_ip.get()}")
        while not self.connected and self.auto_reconnect:
            print(f"[DEBUG] Tentativa de conexão em: {time.strftime('%H:%M:%S')}")
            
            # Usa a porta do servidor para o teste (ou 80 se não definida)
            test_port = self.server_port.get() if hasattr(self, 'server_port') else 80
            
            if silent_ping(self.server_ip.get(), test_port):
                print("[DEBUG] Host alcançável! Tentando conectar...")
                self.connect()
                break
            
            print("[DEBUG] Host não alcançável. Aguardando 2 segundos...")
            time.sleep(2)
        
        if not self.connected and self.auto_reconnect:
            print("[DEBUG] Agendando nova tentativa em 5 segundos...")
            self.root.after(5000, self.auto_connect)

    def connect(self):
        """Conecta ao servidor (sem mostrar erros)"""
        if self.connected:
            return
            
        try:
            # Atualiza ícone para vermelho enquanto tenta conectar
            self.root.after(0, self.update_tray_icon)
            
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(3)
            self.socket.connect((self.server_ip.get(), self.server_port.get()))
            self.socket.settimeout(None)
            
            self.connected = True
            self.server_status = False
            self.reconnect_attempts = 0  # Reseta tentativas
            
            # Atualiza UI
            self.root.after(0, lambda: self.status_label.config(
                text="Status: Conectado", 
                fg="blue"))
            self.root.after(0, self.update_tray_icon)
            
            # Inicia thread de atualização
            self.running = True
            self.update_thread = threading.Thread(target=self.update_status_loop)
            self.update_thread.daemon = True
            self.update_thread.start()
            
        except Exception as e:
            print(f"Erro na conexão: {e}")
            # Atualiza ícone para vermelho
            self.root.after(0, self.update_tray_icon)
            
            if self.auto_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
                self.reconnect_attempts += 1
                self.root.after(0, lambda: self.status_label.config(
                    text=f"Status: Tentando reconectar ({self.reconnect_attempts}/{self.max_reconnect_attempts})", 
                    fg="orange"))
                
                time.sleep(self.reconnect_delay)
                # Chama ping_and_connect em vez de connect diretamente
                threading.Thread(target=self.ping_and_connect, daemon=True).start()
            else:
                self.root.after(0, lambda: self.status_label.config(
                    text="Status: Desconectado", 
                    fg="red"))
                self.root.after(10000, self.auto_connect)

    def handle_connection_lost(self):
        """Lida com perda de conexão"""
        self.disconnect(silent=True)
        
        # Atualiza todos os provedores para Offline
        self.root.after(0, lambda: self.update_providers_status(False, False, False))
        
        # Atualiza o status da interface
        self.root.after(0, lambda: self.status_label.config(
            text="Status: Desconectado", 
            fg="red"))
        
        # Atualiza o tray icon
        self.root.after(0, self.update_tray_icon)
        
        # Atualiza o tooltip do tray icon (que será atualizado pelo get_tray_tooltip)
        if hasattr(self, 'tray_icon'):
            self.tray_icon.title = self.get_tray_tooltip()
            if hasattr(self.tray_icon, '_update_icon'):
                self.tray_icon._update_icon()
        
        if self.auto_reconnect:
            self.auto_connect()

    def disconnect(self, silent=False):
        """Desconecta do servidor"""
        self.running = False
        
        try:
            if hasattr(self, 'socket'):
                self.socket.send(json.dumps({'action': 'disconnect'}).encode('utf-8'))
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
        except:
            pass
        
        self.connected = False
        self.server_status = False
        
        # Para o Proxifier se estiver configurado
        if self.control_proxifier.get():
            self.stop_proxifier()
        
        # Atualiza todos os provedores para Offline
        self.root.after(0, lambda: self.update_providers_status(False, False, False))
        
        if not silent:
            self.root.after(0, lambda: self.status_label.config(
                text="Status: Desconectado", 
                fg="red"))
            self.update_tray_icon()

    def handle_connection_lost(self):
        """Lida com perda de conexão"""
        self.disconnect(silent=True)
        if self.auto_reconnect:
            self.auto_connect()

# FUNÇÃO PARA VERIFICAR O ESTADO DOS PROVEDORES NO SERVIDOR
    def update_status_loop(self):
        """Loop para verificar o status do servidor usando a conexão persistente"""
        while self.running and self.connected:
            try:
                # Envia requisição de status
                request = json.dumps({'action': 'get_status'})
                self.socket.send(request.encode('utf-8'))
                
                # Recebe resposta
                response = self.socket.recv(1024)
                if not response:  # Conexão fechada pelo servidor
                    raise ConnectionError("Conexão fechada pelo servidor")
                    
                data = json.loads(response.decode('utf-8'))
                
                if data.get('connected', False):
                    new_status = data.get('server_status', False)
                    if new_status != self.server_status:
                        self.server_status = new_status
                        self.root.after(0, self.update_status_ui)
                    
                    # Atualiza status dos provedores
                    self.root.after(0, lambda: self.update_providers_status(
                        data.get('coopera_online', False),
                        data.get('claro_online', False),
                        data.get('unifique_online', False)
                    ))
                
            except ConnectionResetError:
                self.root.after(0, self.handle_connection_lost)
                break
            except socket.timeout:
                # Timeout pode ocorrer se o servidor não responder
                continue  # Tenta novamente no próximo ciclo
            except Exception as e:
                print(f"Erro na thread de atualização: {e}")
                self.root.after(0, self.handle_connection_lost)
                break
                
            time.sleep(1)  # Verifica a cada 1 segundo

    def update_providers_status(self, coopera_status, claro_status, unifique_status):
        """Atualiza os status dos provedores na interface"""
        # Verifica mudanças nos status para notificação
        if hasattr(self, 'coopera_status') and coopera_status != self.coopera_status:
            self.show_provider_notification("Coopera", coopera_status)
        if hasattr(self, 'claro_status') and claro_status != self.claro_status:
            self.show_provider_notification("Claro", claro_status)
        if hasattr(self, 'unifique_status') and unifique_status != self.unifique_status:
            self.show_provider_notification("Unifique", unifique_status)
        
        # Armazena os status como atributos
        self.coopera_status = coopera_status
        self.claro_status = claro_status
        self.unifique_status = unifique_status
        
        # Coopera
        if coopera_status:
            self.coopera_label.config(text="Coopera: Online", fg="green")
        else:
            self.coopera_label.config(text="Coopera: Offline", fg="red")
        
        # Claro
        if claro_status:
            self.claro_label.config(text="Claro: Online", fg="green")
        else:
            self.claro_label.config(text="Claro: Offline", fg="red")
        
        # Unifique
        if unifique_status:
            self.unifique_label.config(text="Unifique: Online", fg="green")
        else:
            self.unifique_label.config(text="Unifique: Offline", fg="red")
        
        # Atualiza o tooltip do tray icon
        if hasattr(self, 'tray_icon'):
            self.tray_icon.title = self.get_tray_tooltip()
            if hasattr(self.tray_icon, '_update_icon'):
                self.tray_icon._update_icon()

    # Adicione este novo método para mostrar notificações
    def show_provider_notification(self, provider_name, is_online):
        """Mostra uma notificação quando o status de um provedor muda"""
        if not self.notify_provider_changes.get():
            return
            
        status = "Online" if is_online else "Offline"
        message = f"Provedor {provider_name} está agora {status}"
        
        if hasattr(self, 'tray_icon') and self.tray_icon:
            try:
                self.tray_icon.notify(message, "Alteração de Conexão")
            except Exception as e:
                print(f"Erro ao mostrar notificação: {e}")

    def update_status_ui(self):
        """Atualiza a interface do usuário"""
        if self.server_status:
            self.status_label.config(text="Status: Servidor Operacional", fg="green")
        else:
            self.status_label.config(text="Status: Conectado", fg="blue")
        
        self.update_tray_icon()
        self.check_and_control_proxifier()  # Adicione esta linha
        
        # Atualiza o tooltip do tray icon
        if hasattr(self, 'tray_icon'):
            self.tray_icon.title = self.get_tray_tooltip()
            if hasattr(self.tray_icon, '_update_icon'):
                self.tray_icon._update_icon()

# FUNÇÕES PARA MINIMIZAR E FECHAR O PROGRAMA.
    def minimize_to_tray(self):
        """Minimiza a janela para a bandeja"""
        self.root.withdraw()
    
    def restore_from_tray(self, item=None):
        """Restaura a janela da bandeja"""
        self.root.deiconify()
        self.root.after(0, self.root.lift)
    
    def quit_app(self):
        """Encerra o aplicativo completamente"""
        # Salva a posição atual da janela antes de sair
        self.save_window_position()
        self.save_config()
        self.notify_provider_changes = tk.BooleanVar(value=False)

        # Sinaliza para todas as threads pararem
        self.running = False
        
        # Desconecta se estiver conectado
        if self.connected:
            self.disconnect()
        
        # Para o ícone da bandeja se existir
        if hasattr(self, 'tray_icon') and self.tray_icon:
            try:
                self.tray_icon.stop()
            except:
                pass
        
        # Destroi a janela principal
        if hasattr(self, 'root'):
            try:
                self.root.destroy()
            except:
                pass
        
        # Encerra o processo completamente
        os._exit(0)
    
    def run(self):
        """Executa o aplicativo"""
        self.root.mainloop()

if __name__ == "__main__":
    app = ClientApp()
    app.run()
