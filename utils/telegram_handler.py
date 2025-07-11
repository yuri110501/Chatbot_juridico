import json
import logging
import os
import traceback
import requests
import threading
from functools import wraps
import time
from utils.rag_handler import consulta_rag

# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuração do bot
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

# Configuração de timeout para evitar problemas com o webhook
PROCESSING_TIMEOUT = int(os.environ.get('PROCESSING_TIMEOUT', '15'))  # 15 segundos por padrão

def timeout_handler(seconds):
    """
    Decorator para limitar o tempo de execução de uma função
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = [None]
            error = [None]
            
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    error[0] = e
                    
            thread = threading.Thread(target=target)
            thread.daemon = True
            
            try:
                thread.start()
                thread.join(seconds)
                if thread.is_alive():
                    raise TimeoutError(f"A função {func.__name__} ultrapassou o timeout de {seconds} segundos")
                if error[0]:
                    raise error[0]
                return result[0]
            except TimeoutError as e:
                logger.error(f"Timeout na execução: {e}")
                return {"statusCode": 504, "body": json.dumps({"message": str(e)})}
            
        return wrapper
    return decorator

def send_message(chat_id, text):
    """
    Envia uma mensagem para um chat específico do Telegram.
    """
    logger.info(f"Enviando mensagem para chat {chat_id}")
    url = f"{TELEGRAM_API}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    # Logging detalhado para debug
    logger.info(f"URL da API: {url}")
    logger.info(f"Token do bot: {TOKEN[:5]}...{TOKEN[-5:] if TOKEN and len(TOKEN) > 10 else 'indefinido'}")
    logger.info(f"Dados a serem enviados: {json.dumps(data)}")
    
    try:
        logger.info("Enviando requisição para API do Telegram...")
        response = requests.post(url, json=data)
        logger.info(f"Resposta do Telegram: {response.status_code} - {response.text}")
        
        if response.status_code != 200:
            logger.error(f"Erro na resposta do Telegram: {response.status_code}")
            logger.error(f"Detalhes: {response.text}")
            
            # Verificar se o token é válido
            try:
                logger.info("Verificando token com getMe...")
                me_url = f"https://api.telegram.org/bot{TOKEN}/getMe"
                me_response = requests.get(me_url)
                logger.info(f"Resposta getMe: {me_response.status_code} - {me_response.text}")
            except Exception as e:
                logger.error(f"Erro ao verificar token: {e}")
        
        return response.json()
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {e}")
        logger.error(traceback.format_exc())
        return {"ok": False, "error": str(e)}

def send_message_plain(chat_id, text):
    """
    Envia uma mensagem para um chat específico do Telegram sem formatação Markdown.
    """
    logger.info(f"Enviando mensagem simples para chat {chat_id}")
    url = f"{TELEGRAM_API}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text
        # Sem parse_mode para enviar texto simples
    }
    
    # Logging detalhado para debug
    logger.info(f"URL da API: {url}")
    logger.info(f"Token do bot: {TOKEN[:5]}...{TOKEN[-5:] if TOKEN and len(TOKEN) > 10 else 'indefinido'}")
    
    try:
        logger.info("Enviando requisição para API do Telegram...")
        response = requests.post(url, json=data)
        logger.info(f"Resposta do Telegram: {response.status_code} - {response.text}")
        
        if response.status_code != 200:
            logger.error(f"Erro na resposta do Telegram: {response.status_code}")
            logger.error(f"Detalhes: {response.text}")
        
        return response.json()
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {e}")
        logger.error(traceback.format_exc())
        return {"ok": False, "error": str(e)}

def handle_start_command(chat_id):
    """
    Processa o comando /start
    """
    logger.info(f"Processando comando /start para chat {chat_id}")
    welcome_message = (
        "👋 Bem-vindo ao BOT AWS lambda RAG\n\n"
        "Estou pronto para responder suas perguntas sobre documentos. "
        "Basta enviar sua pergunta e eu usarei tecnologia RAG "
        "(Retrieval-Augmented Generation) para encontrar a melhor resposta.\n\n"
        "Comandos disponíveis:\n"
        "• /start - Mostra esta mensagem de boas-vindas\n"
        "• /ajuda - Exibe informações de ajuda\n\n"
        "Digite sua pergunta a qualquer momento!"
    )
    return send_message_plain(chat_id, welcome_message)

def handle_help_command(chat_id):
    """
    Processa o comando /ajuda
    """
    logger.info(f"Processando comando /ajuda para chat {chat_id}")
    help_message = (
        "🔍 Ajuda do BOT AWS lambda RAG\n\n"
        "Este bot usa RAG (Retrieval-Augmented Generation) para responder suas perguntas "
        "com base nos documentos armazenados.\n\n"
        "Como usar:\n"
        "• Faça uma pergunta sobre o conteúdo dos documentos\n"
        "• O bot irá procurar nos documentos e gerar uma resposta relevante\n\n"
        "Comandos:\n"
        "• /start - Reinicia o bot\n"
        "• /ajuda - Mostra esta mensagem de ajuda"
    )
    return send_message_plain(chat_id, help_message)

def handle_debug_command(chat_id):
    """
    Processa o comando /debug para verificar a configuração do bot
    """
    logger.info(f"Processando comando /debug para chat {chat_id}")
    
    try:
        token = os.environ.get('TELEGRAM_BOT_TOKEN', 'Não definido')
        
        # Mascarar parte do token por segurança
        if token != 'Não definido' and len(token) > 10:
            masked_token = token[:5] + '*****' + token[-5:]
        else:
            masked_token = token
            
        # Verificar buckets S3
        pdf_bucket = os.environ.get('PDF_BUCKET_NAME', 'Não definido')
        embedding_bucket = os.environ.get('EMBEDDING_BUCKET_NAME', 'Não definido')
        
        # Tentar verificar status do bot
        try:
            bot_status = "Verificando..."
            url = f"{TELEGRAM_API}/getMe"
            response = requests.get(url)
            if response.status_code == 200 and response.json().get('ok'):
                bot_info = response.json().get('result', {})
                bot_name = bot_info.get('first_name', 'Desconhecido')
                bot_username = bot_info.get('username', 'Desconhecido')
                bot_status = f"✅ Conectado ({bot_name} @{bot_username})"
            else:
                error = response.json().get('description', 'Erro desconhecido')
                bot_status = f"❌ Erro: {error}"
        except Exception as e:
            bot_status = f"❌ Erro de conexão: {str(e)}"
        
        # Usar texto simples em vez de Markdown para evitar problemas de formatação
        debug_message = (
            "🔧 Informações de Debug\n\n"
            f"Status do Bot: {bot_status}\n\n"
            f"Token: {masked_token}\n"
            f"API URL: (omitida por segurança)\n\n"
            f"Buckets S3:\n"
            f"- PDF: {pdf_bucket}\n"
            f"- Embeddings: {embedding_bucket}\n\n"
            f"Variáveis de Ambiente:\n"
            f"- AWS_DEFAULT_REGION: {os.environ.get('AWS_DEFAULT_REGION', 'Não definido')}\n"
            f"- CHROMA_DB_DIR: {os.environ.get('CHROMA_DB_DIR', '/tmp/chroma_db')}\n"
        )
        
        # Enviar com parse_mode None para evitar problemas de formatação
        return send_message_plain(chat_id, debug_message)
    except Exception as e:
        logger.error(f"Erro ao processar comando /debug: {e}")
        logger.error(traceback.format_exc())
        return send_message_plain(chat_id, f"Erro ao processar comando /debug: {str(e)}")

def handle_message(chat_id, text):
    """
    Processa mensagens normais
    """
    logger.info(f"Iniciando processamento RAG para chat {chat_id}: '{text}'")
    
    try:
        # Inicia o processamento RAG com timeout
        start_time = time.time()
        
        # Consulta o sistema RAG para obter resposta
        logger.info(f"Consultando RAG para: '{text}'")
        rag_response = consulta_rag(text)
        
        duration = time.time() - start_time
        logger.info(f"Consulta RAG concluída em {duration:.2f} segundos")
        
        # Verifica o status da resposta
        status_code = rag_response.get('statusCode', 500)
        
        if status_code == 200:
            # Extrai a resposta do corpo
            response_body = json.loads(rag_response['body'])
            response_text = response_body.get('response', 'Não foi possível obter uma resposta.')
            response_time = response_body.get('duration', '')
            
            # Adiciona informação sobre tempo de processamento
            if response_time:
                response_text += f"\n\n⏱️ Tempo de processamento: {response_time}"
            
            logger.info(f"Enviando resposta ao usuário: {response_text[:100]}...")
            return send_message_plain(chat_id, response_text)
        elif status_code == 504:
            # Trata o caso de timeout
            timeout_message = "⏱️ A consulta demorou muito tempo para ser processada. Por favor, tente uma pergunta mais simples ou tente novamente mais tarde."
            logger.warning("Timeout na consulta RAG")
            return send_message_plain(chat_id, timeout_message)
        else:
            # Trata erros da consulta RAG
            error_body = json.loads(rag_response['body'])
            error_message = error_body.get('message', 'Ocorreu um erro ao processar sua consulta.')
            logger.error(f"Erro na consulta RAG: {error_message}")
            
            user_message = "😔 "
            
            if status_code == 400:
                user_message += "Os embeddings dos documentos ainda não foram inicializados.\n\n"
                user_message += "Por favor, aguarde enquanto o administrador do sistema executa a função `initialize-embeddings` para gerar os embeddings necessários."
            elif status_code == 404:
                user_message += "Não encontrei informações relevantes para sua pergunta na base de conhecimento disponível."
            else:
                user_message += "Ocorreu um erro interno. Por favor, tente novamente mais tarde."
            
            return send_message_plain(chat_id, user_message)
            
    except TimeoutError:
        logger.error("Timeout ao processar mensagem")
        timeout_message = "⏱️ A consulta demorou muito tempo para ser processada. Por favor, tente uma pergunta mais simples ou tente novamente mais tarde."
        return send_message_plain(chat_id, timeout_message)
    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {e}")
        logger.error(traceback.format_exc())
        error_message = "😔 Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente mais tarde."
        return send_message_plain(chat_id, error_message)

def process_telegram_update(update):
    """
    Processa uma atualização do Telegram de forma totalmente síncrona
    """
    logger.info(f"Processando update: {json.dumps(update)}")
    
    try:
        # Verifica se é uma mensagem
        if 'message' not in update:
            logger.warning("Update não contém mensagem")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Formato de update inválido: não contém mensagem'})
            }
        
        message = update['message']
        
        # Verifica se tem chat_id
        if 'chat' not in message or 'id' not in message['chat']:
            logger.warning("Mensagem não contém chat_id")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Formato de mensagem inválido: não contém chat_id'})
            }
        
        chat_id = message['chat']['id']
        logger.info(f"Chat ID: {chat_id}")
        
        # Verifica se há texto na mensagem
        if 'text' not in message:
            # Mensagem sem texto (pode ser foto, vídeo, etc.)
            logger.warning("Mensagem não contém texto")
            send_message_plain(chat_id, "Atualmente, só consigo processar mensagens de texto. Por favor, envie sua pergunta como texto.")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Mensagem sem texto processada'})
            }
            
        text = message['text']
        logger.info(f"Texto da mensagem: {text}")
        
        # Inicia o processamento com base no tipo de mensagem
        if text.startswith('/'):
            # Processamento síncrono para comandos
            if text == '/start':
                logger.info("Comando /start detectado")
                handle_start_command(chat_id)
            elif text == '/ajuda' or text == '/help':
                logger.info("Comando /ajuda detectado")
                handle_help_command(chat_id)
            elif text == '/debug':
                logger.info("Comando /debug detectado")
                handle_debug_command(chat_id)
            else:
                logger.warning(f"Comando desconhecido: {text}")
                send_message_plain(chat_id, "Comando não reconhecido. Use /ajuda para ver os comandos disponíveis.")
        else:
            # Para mensagens normais, envia resposta imediata e processa completamente antes de retornar
            logger.info("Processando como mensagem normal de forma síncrona")
            typing_message = "🔍 Estou processando sua pergunta. Aguarde alguns instantes..."
            send_message_plain(chat_id, typing_message)
            
            # Versão síncrona - processa completamente antes de retornar
            try:
                # Processa diretamente a mensagem (sem threads)
                handle_message(chat_id, text)
            except Exception as e:
                logger.error(f"Erro ao processar mensagem: {e}")
                logger.error(traceback.format_exc())
                error_message = "😔 Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente mais tarde."
                send_message_plain(chat_id, error_message)
        
        # Sempre retorna 200 para o webhook
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Mensagem recebida e processada'})
        }
        
    except Exception as e:
        logger.error(f"Erro ao processar update do Telegram: {e}")
        logger.error(traceback.format_exc())
        return {
            'statusCode': 200,
            'body': json.dumps({'message': f'Erro interno ao processar update: {str(e)}'})
        }

def handle_message_with_retry(chat_id, text, max_retries=1):
    """
    Processa uma mensagem normal com tentativas de retry em caso de falha
    """
    for attempt in range(max_retries + 1):
        try:
            result = handle_message(chat_id, text)
            # Se chegou aqui, o processamento teve sucesso
            return result
        except Exception as e:
            logger.error(f"Erro na tentativa {attempt+1} de processar mensagem: {e}")
            logger.error(traceback.format_exc())
            
            if attempt < max_retries:
                # Espera antes de tentar novamente (backoff exponencial)
                wait_time = 2 ** attempt
                logger.info(f"Aguardando {wait_time}s antes de tentar novamente...")
                time.sleep(wait_time)
            else:
                # Última tentativa falhou, envia mensagem de erro
                error_message = "😔 Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente mais tarde."
                send_message_plain(chat_id, error_message)
                return None 