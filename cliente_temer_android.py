"""
App Android para Projeto Temer - Versão Simplificada
Funcionalidades:
- Conectar/Desconectar ao servidor
- Exibir status do servidor e provedores
- Botões para reiniciar VPS
- Opções de desligar servidor no menu
- Versão 4.02
"""

import kivy
kivy.require('2.3.0')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.properties import ListProperty, BooleanProperty
from kivy.uix.popup import Popup

import socket
import json
import threading
import time
from datetime import datetime

# Configuração da janela para Android
#Window.size = (350, 600)
Window.clearcolor = (0.92, 0.94, 0.96, 1)

class RoundedButton(Button):
    """Botão com cantos arredondados simples"""
    
    def __init__(self, **kwargs):
        # Extrai a cor personalizada antes de chamar super()
        self._bg_color = kwargs.pop('bg_color', [0.3, 0.6, 0.9, 1])
        self._disabled_color = kwargs.pop('disabled_color', [0.7, 0.7, 0.7, 1])
        
        super().__init__(**kwargs)
        
        # Configurações para botão sem fundo nativo
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)  # Transparente
        self.color = (1, 1, 1, 1)
        self.font_size = '14sp'
        self.bold = True
        
        # Monitora mudanças no estado disabled
        self.bind(disabled=self._on_disabled_changed)
        
        # Adiciona canvas personalizado
        self.bind(pos=self._update_canvas, size=self._update_canvas)
        Clock.schedule_once(lambda dt: self._update_canvas(), 0.1)
    
    def _on_disabled_changed(self, instance, value):
        """Atualiza o canvas quando o estado disabled muda"""
        self._update_canvas()
    
    def _update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            # Fundo arredondado
            if not self.disabled:
                Color(*self._bg_color)
            else:
                Color(*self._disabled_color)
            RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[20]
            )

class FramedLabel(Label):
    """Label com frame arredondado"""
    
    def __init__(self, **kwargs):
        # Extrai a cor do frame antes de chamar super()
        self._frame_color = kwargs.pop('frame_color', [0.8, 0.2, 0.2, 0.3])
        
        super().__init__(**kwargs)
        
        self.halign = 'center'
        self.valign = 'middle'
        self.bind(size=self.setter('text_size'))
        self.bind(pos=self._update_canvas, size=self._update_canvas)
        Clock.schedule_once(lambda dt: self._update_canvas(), 0.1)
    
    def _update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            # Fundo branco
            Color(1, 1, 1, 1)
            RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[12]
            )
            
            # Borda colorida
            Color(*self._frame_color)
            Line(
                rounded_rectangle=(self.pos[0], self.pos[1], 
                                 self.size[0], self.size[1], 12),
                width=1.5
            )

class TemerAndroidApp(App):
    """Aplicativo principal Android"""
    
    def build(self):
        self.title = "Projeto Temer Android"
        self.server_ip = "192.168.2.21"
        self.server_port = 5000
        self.connected = False
        self.server_status = False
        
        # Status dos provedores
        self.coopera_status = False
        self.claro_status = False
        self.unifique_status = False
        
        # Status das VPS
        self.vps_vpn_status = False
        self.vps_jogo_status = False
        
        # Socket
        self.socket = None
        self.running = False
        self.update_thread = None
        
        # Layout principal
        self.main_layout = BoxLayout(orientation='vertical', padding=15, spacing=15)
        
        # Fundo
        with self.main_layout.canvas.before:
            Color(0.92, 0.94, 0.96, 1)
            self.rect = Rectangle(size=self.main_layout.size, pos=self.main_layout.pos)
        
        self.main_layout.bind(size=self._update_rect, pos=self._update_rect)
        
        # Cria a interface
        self._create_interface()
        
        # Inicia tentativa de conexão automática
        Clock.schedule_once(lambda dt: self.try_auto_connect(), 1)
        
        return self.main_layout
    
    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size
    
    def _create_interface(self):
        """Cria todos os elementos da interface"""
        
        # ========== CABEÇALHO ==========
        header = BoxLayout(size_hint=(1, 0.12))
        with header.canvas.before:
            Color(0.2, 0.5, 0.8, 1)
            Rectangle(pos=header.pos, size=header.size)
        
        title = Label(
            text="PROJETO TEMER",
            font_size='22sp',
            bold=True,
            color=(0.15, 0.15, 0.15, 1)
        )
        header.add_widget(title)
        self.main_layout.add_widget(header)
        
        # ========== CONEXÃO ==========
        conn_box = BoxLayout(size_hint=(1, 0.18), spacing=15)
        
        # IP
        ip_box = BoxLayout(orientation='vertical', size_hint=(0.6, 1))
        ip_box.add_widget(Label(text="IP do Servidor:", 
                               color=(0.3, 0.3, 0.3, 1), 
                               font_size='12sp',
                               size_hint=(1, 0.4)))
        self.ip_input = TextInput(
            text=self.server_ip,
            multiline=False,
            size_hint=(1, 0.6),
            background_color=(1, 1, 1, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=(12, 8),
            background_normal='',
            background_active=''
        )
        ip_box.add_widget(self.ip_input)
        conn_box.add_widget(ip_box)
        
        # Porta
        port_box = BoxLayout(orientation='vertical', size_hint=(0.4, 1))
        port_box.add_widget(Label(text="Porta:", 
                                 color=(0.3, 0.3, 0.3, 1), 
                                 font_size='12sp',
                                 size_hint=(1, 0.4)))
        self.port_input = TextInput(
            text=str(self.server_port),
            multiline=False,
            size_hint=(1, 0.6),
            background_color=(1, 1, 1, 1),
            foreground_color=(0.2, 0.2, 0.2, 1),
            padding=(12, 8),
            background_normal='',
            background_active=''
        )
        port_box.add_widget(self.port_input)
        conn_box.add_widget(port_box)
        
        self.main_layout.add_widget(conn_box)
        
        # ========== BOTÕES DE CONEXÃO ==========
        btn_box = BoxLayout(size_hint=(1, 0.12), spacing=15)
        
        # Botão CONECTAR
        self.connect_btn = RoundedButton(
            text="CONECTAR",
            bg_color=[0.3, 0.7, 0.3, 1],
            disabled_color=[0.5, 0.8, 0.5, 0.7],  # Verde mais claro quando desabilitado
            size_hint=(0.5, 1)
        )
        self.connect_btn.bind(on_press=self.connect_to_server)
        btn_box.add_widget(self.connect_btn)
        
        # Botão DESCONECTAR
        self.disconnect_btn = RoundedButton(
            text="DESCONECTAR",
            bg_color=[0.9, 0.3, 0.3, 1],
            disabled_color=[0.8, 0.5, 0.5, 0.7],  # Vermelho mais claro quando desabilitado
            size_hint=(0.5, 1)
        )
        self.disconnect_btn.disabled = True
        self.disconnect_btn.bind(on_press=self.disconnect_from_server)
        btn_box.add_widget(self.disconnect_btn)
        
        self.main_layout.add_widget(btn_box)
        
        # ========== STATUS PRINCIPAL ==========
        status_box = BoxLayout(orientation='vertical', 
                              size_hint=(1, 0.2), 
                              spacing=5,
                              padding=(0, 5))
        
        # Frame ao redor do status
        with status_box.canvas.before:
            Color(0.2, 0.5, 0.8, 0.15)
            RoundedRectangle(
                pos=(status_box.pos[0], status_box.pos[1]),
                size=status_box.size,
                radius=[12]
            )
        
        # Status do servidor
        self.status_label = Label(
            text="Status: DESCONECTADO",
            font_size='18sp',
            color=(0.9, 0.3, 0.3, 1),
            bold=True,
            size_hint=(1, 0.5)
        )
        status_box.add_widget(self.status_label)
        
        # Hora do servidor
        self.time_label = Label(
            text="Hora do servidor: --:--:--",
            font_size='14sp',
            color=(0.5, 0.5, 0.5, 1),
            size_hint=(1, 0.5)
        )
        status_box.add_widget(self.time_label)
        
        self.main_layout.add_widget(status_box)
        
        # ========== STATUS DOS PROVEDORES ==========
        prov_title = Label(
            text="STATUS DOS PROVEDORES",
            font_size='16sp',
            bold=True,
            color=(0.4, 0.4, 0.4, 1),
            size_hint=(1, 0.06)
        )
        self.main_layout.add_widget(prov_title)
        
        # Grid para provedores
        prov_grid = GridLayout(cols=3, size_hint=(1, 0.16), spacing=10, padding=(5, 5))
        
        # Frame ao redor do grid
        with prov_grid.canvas.before:
            Color(0.2, 0.5, 0.8, 0.15)
            RoundedRectangle(
                pos=(prov_grid.pos[0], prov_grid.pos[1]),
                size=prov_grid.size,
                radius=[12]
            )
        
        self.coopera_label = FramedLabel(text="Coopera: OFF", 
                                        color=(0.9, 0.3, 0.3, 1),
                                        font_size='14sp',
                                        frame_color=[0.9, 0.3, 0.3, 0.3])
        self.claro_label = FramedLabel(text="Claro: OFF", 
                                      color=(0.9, 0.3, 0.3, 1),
                                      font_size='14sp',
                                      frame_color=[0.9, 0.3, 0.3, 0.3])
        self.unifique_label = FramedLabel(text="Unifique: OFF", 
                                         color=(0.9, 0.3, 0.3, 1),
                                         font_size='14sp',
                                         frame_color=[0.9, 0.3, 0.3, 0.3])
        
        prov_grid.add_widget(self.coopera_label)
        prov_grid.add_widget(self.claro_label)
        prov_grid.add_widget(self.unifique_label)
        
        self.main_layout.add_widget(prov_grid)
        
        # ========== STATUS DAS VPS ==========
        vps_title = Label(
            text="STATUS DAS VPS",
            font_size='16sp',
            bold=True,
            color=(0.4, 0.4, 0.4, 1),
            size_hint=(1, 0.06)
        )
        self.main_layout.add_widget(vps_title)
        
        vps_grid = GridLayout(cols=2, size_hint=(1, 0.16), spacing=10, padding=(5, 5))
        
        # Frame ao redor do grid
        with vps_grid.canvas.before:
            Color(0.2, 0.5, 0.8, 0.15)
            RoundedRectangle(
                pos=(vps_grid.pos[0], vps_grid.pos[1]),
                size=vps_grid.size,
                radius=[12]
            )
        
        self.vps_vpn_label = FramedLabel(text="VPS VPN: OFF", 
                                        color=(0.9, 0.3, 0.3, 1),
                                        font_size='14sp',
                                        frame_color=[0.9, 0.3, 0.3, 0.3])
        self.vps_jogo_label = FramedLabel(text="VPS Jogo: OFF", 
                                         color=(0.9, 0.3, 0.3, 1),
                                         font_size='14sp',
                                         frame_color=[0.9, 0.3, 0.3, 0.3])
        
        vps_grid.add_widget(self.vps_vpn_label)
        vps_grid.add_widget(self.vps_jogo_label)
        
        self.main_layout.add_widget(vps_grid)
        
        # ========== BOTÕES DE REINÍCIO ==========
        reboot_title = Label(
            text="REINICIAR VPS",
            font_size='16sp',
            bold=True,
            color=(0.4, 0.4, 0.4, 1),
            size_hint=(1, 0.06)
        )
        self.main_layout.add_widget(reboot_title)
        
        reboot_grid = GridLayout(cols=2, size_hint=(1, 0.16), spacing=15)
        
        self.reboot_vpn_btn = RoundedButton(
            text="Reiniciar VPN",
            bg_color=[0.2, 0.6, 0.9, 1],
            disabled_color=[0.5, 0.7, 0.9, 0.7]  # Azul mais claro quando desabilitado
        )
        self.reboot_vpn_btn.disabled = True
        self.reboot_vpn_btn.bind(on_press=self.reboot_vps_vpn)
        
        self.reboot_jogo_btn = RoundedButton(
            text="Reiniciar Jogo",
            bg_color=[0.2, 0.6, 0.9, 1],
            disabled_color=[0.5, 0.7, 0.9, 0.7]  # Azul mais claro quando desabilitado
        )
        self.reboot_jogo_btn.disabled = True
        self.reboot_jogo_btn.bind(on_press=self.reboot_vps_jogo)
        
        reboot_grid.add_widget(self.reboot_vpn_btn)
        reboot_grid.add_widget(self.reboot_jogo_btn)
        
        self.main_layout.add_widget(reboot_grid)
        
        # ========== MENU DE DESLIGAMENTO ==========
        power_box = BoxLayout(size_hint=(1, 0.12), spacing=15)
        
        # Botão para menu de desligamento
        self.power_menu_btn = RoundedButton(
            text="OPÇÕES DE DESLIGAMENTO",
            bg_color=[0.9, 0.4, 0.4, 1],
            disabled_color=[0.9, 0.6, 0.6, 0.7]  # Vermelho mais claro quando desabilitado
        )
        self.power_menu_btn.disabled = True
        self.power_menu_btn.bind(on_press=self.show_power_menu)
        power_box.add_widget(self.power_menu_btn)
        
        self.main_layout.add_widget(power_box)
    
    def _update_label_color(self, label, online):
        """Atualiza cor do label baseado no status"""
        if online:
            label.color = (0.2, 0.8, 0.2, 1)  # Verde
            label.text = label.text.replace(": OFF", ": ON").replace(": Desconectado", ": Conectado")
            label._frame_color = [0.2, 0.8, 0.2, 0.3]  # Verde para o frame
        else:
            label.color = (0.9, 0.3, 0.3, 1)  # Vermelho
            label.text = label.text.replace(": ON", ": OFF").replace(": Conectado", ": Desconectado")
            label._frame_color = [0.9, 0.3, 0.3, 0.3]  # Vermelho para o frame
        
        # Atualiza o canvas do label
        label._update_canvas()
    
    # ========== FUNÇÕES DE CONEXÃO ==========
    
    def try_auto_connect(self):
        """Tenta conexão automática ao iniciar"""
        threading.Thread(target=self._auto_connect_thread, daemon=True).start()
    
    def _auto_connect_thread(self):
        """Thread para tentar conexão automática"""
        time.sleep(2)  # Aguarda app carregar
        Clock.schedule_once(lambda dt: self.connect_to_server(None))
    
    def connect_to_server(self, instance):
        """Conecta ao servidor"""
        try:
            # Atualiza valores dos inputs
            self.server_ip = self.ip_input.text
            self.server_port = int(self.port_input.text)
            
            # Cria socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)
            
            # Tenta conectar
            self.socket.connect((self.server_ip, self.server_port))
            self.socket.settimeout(None)
            
            self.connected = True
            self.running = True
            
            # Atualiza UI
            Clock.schedule_once(lambda dt: self._update_connection_ui(True))
            
            # Inicia thread de atualização
            self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
            self.update_thread.start()
            
            # Mostra mensagem
            self.show_popup("Sucesso", "Conectado ao servidor!")
            
        except Exception as e:
            self.connected = False
            Clock.schedule_once(lambda dt: self._update_connection_ui(False))
            self.show_popup("Erro", f"Falha na conexão: {str(e)}")
    
    def disconnect_from_server(self, instance):
        """Desconecta do servidor"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        
        self.connected = False
        self.server_status = False
        
        # Atualiza UI
        Clock.schedule_once(lambda dt: self._update_connection_ui(False))
        
        # Reseta status
        Clock.schedule_once(lambda dt: self._reset_status())
        
        self.show_popup("Info", "Desconectado do servidor")
    
    def _update_connection_ui(self, connected):
        """Atualiza UI baseado no estado de conexão"""
        if connected:
            self.status_label.text = "Status: CONECTADO"
            self.status_label.color = (0.2, 0.5, 0.8, 1)  # Azul
            
            # Botões CONECTAR/DESCONECTAR
            self.connect_btn.disabled = True
            self.disconnect_btn.disabled = False
            
            # Botões de reinício
            self.reboot_vpn_btn.disabled = False
            self.reboot_jogo_btn.disabled = False
            
            # Botão de desligamento
            self.power_menu_btn.disabled = False
            
        else:
            self.status_label.text = "Status: DESCONECTADO"
            self.status_label.color = (0.9, 0.3, 0.3, 1)  # Vermelho
            
            # Botões CONECTAR/DESCONECTAR
            self.connect_btn.disabled = False
            self.disconnect_btn.disabled = True
            
            # Botões de reinício
            self.reboot_vpn_btn.disabled = True
            self.reboot_jogo_btn.disabled = True
            
            # Botão de desligamento
            self.power_menu_btn.disabled = True
    
    def _reset_status(self):
        """Reseta todos os status para desconectado"""
        # Provedores
        self._update_label_color(self.coopera_label, False)
        self._update_label_color(self.claro_label, False)
        self._update_label_color(self.unifique_label, False)
        
        # VPS
        self._update_label_color(self.vps_vpn_label, False)
        self._update_label_color(self.vps_jogo_label, False)
        
        # Hora
        self.time_label.text = "Hora do servidor: --:--:--"
    
    def _update_loop(self):
        """Loop para atualizar status do servidor"""
        while self.running and self.connected:
            try:
                # Envia requisição de status
                request = json.dumps({'action': 'get_status'})
                self.socket.send(request.encode('utf-8'))
                
                # Recebe resposta
                response = self.socket.recv(1024)
                if not response:
                    raise ConnectionError("Conexão fechada")
                
                data = json.loads(response.decode('utf-8'))
                
                # Atualiza status na thread principal
                Clock.schedule_once(lambda dt: self._process_status_data(data))
                
            except Exception as e:
                print(f"Erro na atualização: {e}")
                if self.running:
                    Clock.schedule_once(lambda dt: self.disconnect_from_server(None))
                break
            
            time.sleep(2)  # Atualiza a cada 2 segundos
    
    def _process_status_data(self, data):
        """Processa dados recebidos do servidor"""
        if data.get('connected', False):
            # Status do servidor
            new_status = data.get('server_status', False)
            if new_status != self.server_status:
                self.server_status = new_status
                if new_status:
                    self.status_label.text = "Status: OPERACIONAL"
                    self.status_label.color = (0.2, 0.8, 0.2, 1)  # Verde
                else:
                    self.status_label.text = "Status: CONECTADO"
                    self.status_label.color = (0.2, 0.5, 0.8, 1)  # Azul
            
            # Hora do servidor
            server_time = data.get('system_time', '')
            if server_time:
                try:
                    dt = datetime.fromisoformat(server_time)
                    self.time_label.text = f"Hora do servidor: {dt.strftime('%H:%M:%S')}"
                except:
                    self.time_label.text = f"Hora: {server_time}"
            
            # Provedores
            coopera = data.get('coopera_online', False)
            claro = data.get('claro_online', False)
            unifique = data.get('unifique_online', False)
            
            if coopera != self.coopera_status:
                self.coopera_status = coopera
                self._update_label_color(self.coopera_label, coopera)
            
            if claro != self.claro_status:
                self.claro_status = claro
                self._update_label_color(self.claro_label, claro)
            
            if unifique != self.unifique_status:
                self.unifique_status = unifique
                self._update_label_color(self.unifique_label, unifique)
            
            # VPS
            vps_vpn = data.get('vps_vpn_conectado', False)
            vps_jogo = data.get('vps_jogo_conectado', False)
            
            if vps_vpn != self.vps_vpn_status:
                self.vps_vpn_status = vps_vpn
                self._update_label_color(self.vps_vpn_label, vps_vpn)
            
            if vps_jogo != self.vps_jogo_status:
                self.vps_jogo_status = vps_jogo
                self._update_label_color(self.vps_jogo_label, vps_jogo)
    
    # ========== FUNÇÕES DE REINÍCIO ==========
    
    def reboot_vps_vpn(self, instance):
        """Reinicia VPS VPN"""
        if not self.connected:
            self.show_popup("Aviso", "Não conectado ao servidor")
            return
        
        # Confirmação
        self.show_confirmation_popup(
            "Reiniciar VPS VPN",
            "Tem certeza que deseja reiniciar o VPS VPN?\nIsso pode causar interrupção temporária.",
            lambda: self._send_reboot_command('reiniciar_vps_vpn', "VPS VPN")
        )
    
    def reboot_vps_jogo(self, instance):
        """Reinicia VPS Jogo"""
        if not self.connected:
            self.show_popup("Aviso", "Não conectado ao servidor")
            return
        
        # Confirmação
        self.show_confirmation_popup(
            "Reiniciar VPS Jogo",
            "Tem certeza que deseja reiniciar o VPS Jogo?\nIsso pode causar interrupção temporária.",
            lambda: self._send_reboot_command('reiniciar_vps_jogo', "VPS Jogo")
        )
    
    def _send_reboot_command(self, action, vps_name):
        """Envia comando de reinício ao servidor"""
        try:
            # Cria socket temporário
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                s.connect((self.server_ip, self.server_port))
                
                # Envia comando
                request = json.dumps({'action': action})
                s.send(request.encode('utf-8'))
                
                # Recebe resposta
                response = s.recv(1024)
                if response:
                    data = json.loads(response.decode('utf-8'))
                    if data.get('success', False):
                        self.show_popup("Sucesso", f"Comando de reinício do {vps_name} enviado!")
                    else:
                        self.show_popup("Erro", f"Falha ao reiniciar {vps_name}")
        
        except socket.timeout:
            self.show_popup("Erro", "Timeout - Servidor não respondeu")
        except Exception as e:
            self.show_popup("Erro", f"Falha ao enviar comando: {str(e)}")
    
    # ========== FUNÇÕES DE DESLIGAMENTO ==========
    
    def show_power_menu(self, instance):
        """Mostra menu de opções de desligamento"""
        # Cria popup com opções
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        
        # Título
        title = Label(text="DESLIGAR SERVIDOR", 
                     font_size='18sp', 
                     bold=True,
                     color=(0.3, 0.3, 0.3, 1))
        content.add_widget(title)
        
        # Botão 1: Desligar servidor e VPS
        btn1 = RoundedButton(
            text="Desligar Servidor e VPS",
            bg_color=[0.9, 0.4, 0.4, 1],
            disabled_color=[0.9, 0.6, 0.6, 0.7],
            size_hint=(1, 0.3)
        )
        btn1.bind(on_press=lambda x: self.show_poweroff_confirmation(
            "Desligar Servidor e VPS",
            "Tem certeza que deseja desligar o servidor E os VPS?\nEsta ação NÃO pode ser desfeita!",
            'poweroff'
        ))
        content.add_widget(btn1)
        
        # Botão 2: Desligar apenas servidor
        btn2 = RoundedButton(
            text="Desligar Apenas Servidor",
            bg_color=[0.9, 0.6, 0.3, 1],
            disabled_color=[0.9, 0.8, 0.6, 0.7],
            size_hint=(1, 0.3)
        )
        btn2.bind(on_press=lambda x: self.show_poweroff_confirmation(
            "Desligar Apenas Servidor",
            "Tem certeza que deseja desligar apenas o servidor?\nOs VPS permanecerão ligados.",
            'poweroff2'
        ))
        content.add_widget(btn2)
        
        # Botão Cancelar
        btn_cancel = RoundedButton(
            text="Cancelar",
            bg_color=[0.6, 0.6, 0.6, 1],
            disabled_color=[0.8, 0.8, 0.8, 0.7],
            size_hint=(1, 0.3)
        )
        btn_cancel.bind(on_press=lambda x: self.poweroff_popup.dismiss())
        content.add_widget(btn_cancel)
        
        self.poweroff_popup = Popup(
            title='',
            content=content,
            size_hint=(0.8, 0.6),
            auto_dismiss=True,
            background_color=(0.95, 0.95, 0.95, 1)
        )
        
        self.poweroff_popup.open()
    
    def show_poweroff_confirmation(self, title, message, action):
        """Mostra confirmação para desligamento"""
        self.poweroff_popup.dismiss()  # Fecha menu anterior
        
        self.show_confirmation_popup(
            title,
            message,
            lambda: self._send_poweroff_command(action, title)
        )
    
    def _send_poweroff_command(self, action, title):
        """Envia comando de desligamento ao servidor"""
        if not self.connected:
            self.show_popup("Aviso", "Não conectado ao servidor")
            return
        
        # Verificação de segurança (igual ao Windows)
        if not self.server_ip.startswith('192.168.2'):
            self.show_popup("Segurança", "Mimo safado não pode desligar o servidor!")
            return
        
        try:
            # Cria socket temporário
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3)
                s.connect((self.server_ip, self.server_port))
                
                # Envia comando
                request = json.dumps({'action': action})
                s.send(request.encode('utf-8'))
                
                # Recebe resposta
                response = s.recv(1024)
                if response:
                    data = json.loads(response.decode('utf-8'))
                    if data.get('success', False):
                        self.show_popup("Sucesso", f"{title} enviado com sucesso!")
                        # Desconecta após desligar
                        Clock.schedule_once(lambda dt: self.disconnect_from_server(None), 2)
                    else:
                        self.show_popup("Erro", "Falha ao executar desligamento")
        
        except Exception as e:
            self.show_popup("Erro", f"Falha ao enviar comando: {str(e)}")
    
    # ========== UTILITÁRIOS DE UI ==========
    
    def show_popup(self, title, message):
        """Mostra um popup simples"""
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        content.add_widget(Label(text=message, 
                                halign='center',
                                color=(0.3, 0.3, 0.3, 1)))
        
        btn = RoundedButton(text="OK", 
                           bg_color=[0.2, 0.5, 0.8, 1], 
                           disabled_color=[0.5, 0.7, 0.9, 0.7],
                           size_hint=(1, 0.3))
        
        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.8, 0.4),
            background_color=(0.95, 0.95, 0.95, 1)
        )
        
        btn.bind(on_press=popup.dismiss)
        content.add_widget(btn)
        popup.open()
    
    def show_confirmation_popup(self, title, message, confirm_callback):
        """Mostra popup de confirmação"""
        content = BoxLayout(orientation='vertical', spacing=10, padding=20)
        content.add_widget(Label(text=message, 
                                halign='center',
                                color=(0.3, 0.3, 0.3, 1)))
        
        btn_box = BoxLayout(size_hint=(1, 0.4), spacing=10)
        
        btn_yes = RoundedButton(text="SIM", 
                               bg_color=[0.9, 0.3, 0.3, 1],
                               disabled_color=[0.9, 0.6, 0.6, 0.7])
        btn_no = RoundedButton(text="NÃO", 
                              bg_color=[0.6, 0.6, 0.6, 1],
                              disabled_color=[0.8, 0.8, 0.8, 0.7])
        
        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.8, 0.5),
            background_color=(0.95, 0.95, 0.95, 1)
        )
        
        def on_yes(instance):
            popup.dismiss()
            confirm_callback()
        
        btn_yes.bind(on_press=on_yes)
        btn_no.bind(on_press=popup.dismiss)
        
        btn_box.add_widget(btn_yes)
        btn_box.add_widget(btn_no)
        content.add_widget(btn_box)
        
        popup.open()
    
    # ========== CICLO DE VIDA DO APP ==========
    
    def on_stop(self):
        """Chamado quando o app é fechado"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass

# Executa o aplicativo
if __name__ == '__main__':
    TemerAndroidApp().run()
