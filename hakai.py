import time
import subprocess
import sys
import os

class GerenciadorDeProcesso:
    def __init__(self):
        # Cria a pasta Logs se ela não existir
        self.log_dir = 'Logs'
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def suicidar_temer(self):
        try:
            # Usando CREATE_NO_WINDOW para executar silenciosamente
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            subprocess.run(
                ['taskkill', '/IM', 'Gerenciador de VPS.exe', '/F'],
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Registra o sucesso no arquivo de log dentro da pasta Logs
            log_path = os.path.join(self.log_dir, 'hakai.log')
            with open(log_path, 'a') as f:
                f.write("Processo 'Gerenciador de VPS.exe' finalizado com sucesso.\n")
            
        except subprocess.CalledProcessError:
            # Registra o erro no arquivo de log dentro da pasta Logs
            log_path = os.path.join(self.log_dir, 'hakai.log')
            with open(log_path, 'a') as f:
                f.write("Falha ao tentar finalizar o processo.\n")
            pass

if __name__ == "__main__":
    gerenciador = GerenciadorDeProcesso()
    time.sleep(4)
    gerenciador.suicidar_temer()
