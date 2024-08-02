import tkinter as tk
import subprocess
import os
import json
import threading

class SchedulerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Scheduler e CC")

        # Carregar a posição da janela se disponível
        self.load_window_position()

        # Frame centralizado e alinhado ao topo (movido para fora do frame_geral)
        self.frame_topo = tk.Frame(root, borderwidth=2, relief=tk.RAISED)
        self.frame_topo.pack(pady=0, fill=tk.X)

        # Frame geral
        self.frame_geral = tk.Frame(root, borderwidth=2, relief=tk.SUNKEN)
        self.frame_geral.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Label SCHEDULER e CC
        self.label_topo = tk.Label(self.frame_topo, text="SCHEDULER E CC", font=("Arial", 16))
        self.label_topo.pack()

        # Frame para labels VPS VPN e VPS JOGO
        self.frame_vps = tk.Frame(self.frame_geral, borderwidth=2, relief=tk.RAISED)
        self.frame_vps.pack(pady=10)

        # Frame para labels OMR VPN e OMR JOGO
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
        self.frame_inferior = tk.Frame(root, borderwidth=2, relief=tk.RAISED)
        self.frame_inferior.pack(pady=0, fill=tk.X, side=tk.BOTTOM)

        # Botão para Reiniciar omr-tracker VPN
        self.botao_reiniciar_vpn = tk.Button(self.frame_inferior, text="Reiniciar omr-tracker VPN", command=self.reiniciar_omr_tracker_vpn)
        self.botao_reiniciar_vpn.grid(row=0, column=0, padx=10, pady=5, sticky='w')

        # Botão para Reiniciar omr-tracker JOGO
        self.botao_reiniciar_jogo = tk.Button(self.frame_inferior, text="Reiniciar omr-tracker JOGO", command=self.reiniciar_omr_tracker_jogo)
        self.botao_reiniciar_jogo.grid(row=0, column=1, padx=10, pady=5, sticky='w')

        # Adiciona o label de versão dentro do frame_inferior, alinhado à esquerda e com tamanho de fonte configurável
        self.label_versao = tk.Label(self.frame_inferior, text="Projeto Pastilha - ©VempirE_GhosT - Versão: beta 2.1", font=("Arial", 7))
        self.label_versao.grid(row=1, column=0, columnspan=2, sticky='w', pady=(0, 0))

        # Define o evento de fechamento para salvar a posição da janela
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Iniciar a execução dos comandos em uma thread separada
        self.executar_comandos()

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
        
        self.root.after(0, lambda: label_scheduler.config(text=f"Scheduler: {resultado_scheduler_truncado}"))
        self.root.after(0, lambda: label_cc.config(text=f"CC: {resultado_cc_truncado}"))

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

    def save_window_position(self):
        position = {
            "x": self.root.winfo_x(),
            "y": self.root.winfo_y()
        }
        with open("scheduler_e_cc_position.json", "w") as f:
            json.dump(position, f)

    def load_window_position(self):
        if os.path.isfile("scheduler_e_cc_position.json"):
            with open("scheduler_e_cc_position.json", "r") as f:
                position = json.load(f)
                self.root.geometry("+{}+{}".format(position["x"], position["y"]))

    def on_close(self):
        self.save_window_position()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    root.configure(bg="white")
    app = SchedulerApp(root)
    root.mainloop()
