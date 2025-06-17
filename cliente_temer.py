import tkinter as tk
from tkinter import messagebox
import socket
import json
import threading
import time
import pystray
from PIL import Image, ImageDraw
import sys

class ClientApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Cliente do Servidor")
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        
        self.server_ip = tk.StringVar(value="127.0.0.1")
        self.server_port = tk.IntVar(value=5000)
        self.connected = False
        self.server_status = False
        self.tray_icon = None
        
        self.setup_ui()
        self.create_tray_icon()
        self.update_thread = None
        self.running = True
        
    def setup_ui(self):
        """Configura a interface do usuário"""
        frame = tk.Frame(self.root, padx=10, pady=10)
        frame.pack()
        
        # Entrada de IP
        tk.Label(frame, text="IP do Servidor:").grid(row=0, column=0, sticky="w")
        tk.Entry(frame, textvariable=self.server_ip).grid(row=0, column=1)
        
        # Entrada de Porta
        tk.Label(frame, text="Porta:").grid(row=1, column=0, sticky="w")
        tk.Entry(frame, textvariable=self.server_port).grid(row=1, column=1)
        
        # Botões
        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=2, columnspan=2, pady=10)
        
        tk.Button(btn_frame, text="Conectar", command=self.connect).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Desconectar", command=self.disconnect).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Sair", command=self.quit_app).pack(side="right", padx=5)
        
        # Status
        self.status_label = tk.Label(frame, text="Status: Desconectado", fg="red")
        self.status_label.grid(row=3, columnspan=2, pady=5)
        
    def create_tray_icon(self):
        """Cria o ícone na bandeja do sistema"""
        # Cria imagens para os diferentes estados
        self.red_icon = self.create_icon_image("red")
        self.blue_icon = self.create_icon_image("blue")
        self.green_icon = self.create_icon_image("green")
        
        # Menu do tray icon
        menu = (
            pystray.MenuItem("Abrir", self.restore_from_tray),
            pystray.MenuItem("Sair", self.quit_app)
        )
        
        self.tray_icon = pystray.Icon(
            "server_client",
            self.red_icon,
            "Cliente do Servidor",
            menu
        )
        
        # Inicia uma thread para o tray icon
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
    
    def create_icon_image(self, color):
        """Cria uma imagem para o tray icon com a cor especificada"""
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
        if not self.connected:
            self.tray_icon.icon = self.red_icon
        elif self.server_status:
            self.tray_icon.icon = self.green_icon
        else:
            self.tray_icon.icon = self.blue_icon
        
        if hasattr(self.tray_icon, '_update_icon'):
            self.tray_icon._update_icon()
    
    def connect(self):
        """Conecta ao servidor"""
        if self.connected:
            return
            
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(3)  # Timeout de conexão de 3 segundos
            self.socket.connect((self.server_ip.get(), self.server_port.get()))
            self.socket.settimeout(None)  # Remove timeout após conexão estabelecida
            
            self.connected = True
            self.server_status = False
            self.status_label.config(text="Status: Conectado", fg="blue")
            
            # Inicia thread para atualizar status
            self.running = True
            self.update_thread = threading.Thread(target=self.update_status_loop)
            self.update_thread.daemon = True
            self.update_thread.start()
            
            self.update_tray_icon()
            messagebox.showinfo("Sucesso", "Conectado ao servidor com sucesso!")
        except socket.timeout:
            messagebox.showerror("Erro", "Tempo excedido ao tentar conectar")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao conectar: {str(e)}")

    def disconnect(self):
        """Desconecta do servidor de forma limpa"""
        if not self.connected:
            return
        
        # Sinaliza para a thread parar
        self.running = False
        
        try:
            # Envia um comando de desconexão ao servidor
            if hasattr(self, 'socket'):
                self.socket.send(json.dumps({'action': 'disconnect'}).encode('utf-8'))
        except:
            pass
        
        try:
            # Fecha o socket
            if hasattr(self, 'socket'):
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
        except:
            pass
        
        self.connected = False
        self.server_status = False
        self.status_label.config(text="Status: Desconectado", fg="red")
        self.update_tray_icon()

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

    def update_status_ui(self):
        """Atualiza a interface do usuário"""
        if self.server_status:
            self.status_label.config(text="Status: Servidor Ativo", fg="green")
        else:
            self.status_label.config(text="Status: Conectado", fg="blue")
        self.update_tray_icon()

    def handle_connection_lost(self):
        """Lida com perda de conexão"""
        self.disconnect()
        messagebox.showerror("Erro", "Conexão com o servidor foi perdida")
    
    def minimize_to_tray(self):
        """Minimiza a janela para a bandeja"""
        self.root.withdraw()
    
    def restore_from_tray(self, item=None):
        """Restaura a janela da bandeja"""
        self.root.deiconify()
        self.root.after(0, self.root.lift)
    
    def quit_app(self):
        """Encerra o aplicativo"""
        self.running = False
        if self.connected:
            self.disconnect()
        
        if self.tray_icon:
            self.tray_icon.stop()
        
        self.root.quit()
        sys.exit(0)
    
    def run(self):
        """Executa o aplicativo"""
        self.root.mainloop()

if __name__ == "__main__":
    app = ClientApp()
    app.run()
