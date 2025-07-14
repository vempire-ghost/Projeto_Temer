import os
import sys
import time
import argparse
import psutil
import logging
from subprocess import Popen

def configurar_log():
    logging.basicConfig(
        filename='atualizador.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def encerrar_processo(pid=None, nome_executavel=None):
    try:
        if pid:
            try:
                processo = psutil.Process(pid)
                processo.terminate()
                processo.wait(timeout=5)
            except psutil.NoSuchProcess:
                pass
        
        if nome_executavel:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'].lower() == nome_executavel.lower():
                    try:
                        p = psutil.Process(proc.info['pid'])
                        p.terminate()
                        p.wait(timeout=5)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        
        time.sleep(2)  # Espera para garantir que o processo foi encerrado
    except Exception as e:
        logging.error(f"Erro ao encerrar processo: {str(e)}")

def substituir_arquivo(original, novo):
    max_tentativas = 5
    tentativa = 0
    
    while tentativa < max_tentativas:
        try:
            if os.path.exists(original):
                os.remove(original)
            os.rename(novo, original)
            return True
        except Exception as e:
            tentativa += 1
            time.sleep(2)
            if tentativa == max_tentativas:
                logging.error(f"Falha ao substituir arquivo após {max_tentativas} tentativas: {str(e)}")
                return False

def main():
    configurar_log()
    logging.info("Iniciando atualizador")
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', required=True)
    parser.add_argument('--novo', required=True)
    parser.add_argument('--pid')
    args = parser.parse_args()
    
    # Encerra o processo principal
    encerrar_processo(pid=args.pid if args.pid else None, nome_executavel=args.original)
    
    # Substitui o arquivo
    if substituir_arquivo(args.original, args.novo):
        # Inicia o novo programa
        try:
            Popen([args.original], creationflags=0x00000008)  # CREATE_NO_WINDOW
        except Exception as e:
            logging.error(f"Erro ao iniciar aplicativo: {str(e)}")
    
    logging.info("Atualização concluída")

if __name__ == "__main__":
    main()
