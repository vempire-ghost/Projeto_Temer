import os
import sys
import time
import argparse
import psutil
import logging
from subprocess import Popen

def configurar_log():
    """Configura o sistema de logging com arquivo e console"""
    # Cria diretório de logs se não existir
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Configuração detalhada do logging
    log_format = '%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s'
    log_file = os.path.join(log_dir, 'atualizador.log')
    
    # Configura root logger para arquivo e console
    logging.basicConfig(
        level=logging.DEBUG,
        format=log_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('atualizador')

class ArgumentParserWithLogging(argparse.ArgumentParser):
    """Subclasse de ArgumentParser que registra erros no log"""
    def error(self, message):
        logger = logging.getLogger('atualizador')
        logger.error(f"Erro nos argumentos: {message}")
        super().error(message)

def encerrar_processo(logger, pid=None, nome_executavel=None):
    """Encerra um processo pelo PID ou nome do executável"""
    logger.debug("Iniciando encerramento de processos")
    
    try:
        if pid:
            try:
                pid_int = int(pid)
                logger.debug(f"Tentando encerrar processo por PID: {pid_int}")
                processo = psutil.Process(pid_int)
                logger.info(f"Encerrando processo: {processo.name()} (PID: {pid_int})")
                processo.terminate()
                processo.wait(timeout=5)
                logger.info(f"Processo {pid_int} encerrado com sucesso")
            except psutil.NoSuchProcess:
                logger.warning(f"Processo com PID {pid} não encontrado")
            except ValueError:
                logger.error(f"PID inválido fornecido: {pid}")
        
        if nome_executavel:
            logger.debug(f"Buscando processos com nome: {nome_executavel}")
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'].lower() == nome_executavel.lower():
                    try:
                        p = psutil.Process(proc.info['pid'])
                        logger.info(f"Encerrando processo: {p.name()} (PID: {p.pid})")
                        p.terminate()
                        p.wait(timeout=5)
                        logger.info(f"Processo {p.name()} encerrado com sucesso")
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        logger.warning(f"Erro ao encerrar processo {proc.info['pid']}: {str(e)}")
        
        time.sleep(2)
        logger.debug("Espera concluída após encerramento de processos")
    except Exception as e:
        logger.error(f"Erro crítico ao encerrar processos: {str(e)}", exc_info=True)
        raise

def substituir_arquivo(logger, original, novo):
    """Substitui o arquivo original pelo novo"""
    logger.debug("Iniciando substituição de arquivo")
    max_tentativas = 5
    tentativa = 0
    
    while tentativa < max_tentativas:
        try:
            logger.debug(f"Tentativa {tentativa + 1} de {max_tentativas}")
            
            if os.path.exists(original):
                logger.info(f"Removendo arquivo original: {original}")
                os.remove(original)
                time.sleep(2)
            
            logger.info(f"Renomeando {novo} para {original}")
            os.rename(novo, original)
            logger.info("Substituição concluída com sucesso")
            return True
            
        except Exception as e:
            tentativa += 1
            logger.warning(f"Falha na tentativa {tentativa}: {str(e)}")
            time.sleep(2)
            
            if tentativa == max_tentativas:
                logger.error(f"Falha ao substituir arquivo após {max_tentativas} tentativas")
                return False

def main():
    """Função principal do atualizador"""
    # Configura logging antes de qualquer operação
    logger = configurar_log()
    
    try:
        logger.info("Iniciando processo de atualização")
        
        # Configura parser de argumentos personalizado
        parser = ArgumentParserWithLogging(
            description='Atualizador de aplicativos',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        parser.add_argument('--original', required=True, help='Nome do arquivo original')
        parser.add_argument('--novo', required=True, help='Nome do novo arquivo')
        parser.add_argument('--pid', help='PID do processo a ser encerrado')
        
        try:
            args = parser.parse_args()
            logger.debug(f"Argumentos recebidos: {vars(args)}")
        except SystemExit as e:
            # Captura detalhes adicionais do erro
            exc_info = sys.exc_info()
            if exc_info[1] and str(exc_info[1]):
                logger.error(f"Código de saída: {str(exc_info[1])}")
            raise
        
        # Fase 1: Encerra processo existente
        logger.info("Fase 1/3: Encerrando processo existente")
        encerrar_processo(logger, pid=args.pid if args.pid else None, nome_executavel=args.original)
        
        # Fase 2: Substitui arquivo
        logger.info("Fase 2/3: Substituindo arquivo")
        if substituir_arquivo(logger, args.original, args.novo):
            # Fase 3: Inicia nova versão
            logger.info("Fase 3/3: Iniciando nova versão")
            try:
                logger.debug(f"Iniciando processo: {args.original}")
                Popen([args.original], creationflags=0x00000008)  # CREATE_NO_WINDOW
                logger.info("Aplicativo iniciado com sucesso")
            except Exception as e:
                logger.error(f"Falha ao iniciar aplicativo: {str(e)}", exc_info=True)
        
        logger.info("Processo de atualização concluído com sucesso")
    except Exception as e:
        logger.exception("Falha crítica no processo de atualização")
        sys.exit(1)

if __name__ == "__main__":
    main()
