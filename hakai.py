import time
import subprocess
import sys

class GerenciadorDeProcesso:
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
            
            # Opcional: se você ainda quiser registrar o sucesso em um arquivo de log
            with open('hakai.log', 'a') as f:
                 f.write("Processo 'Gerenciador de VPS.exe' finalizado com sucesso.\n")
            
        except subprocess.CalledProcessError:
            # Opcional: registrar erro em um arquivo de log
            with open('hakai.log', 'a') as f:
                 f.write("Falha ao tentar finalizar o processo.\n")
            pass

if __name__ == "__main__":
    gerenciador = GerenciadorDeProcesso()
    time.sleep(4)
    gerenciador.suicidar_temer()
