import json
import logging
import base64
import traceback
from dotenv import load_dotenv
from utils.telegram_handler import process_telegram_update

# Carregar variáveis de ambiente do arquivo .env
try:
    load_dotenv()
    logging.info("Variáveis de ambiente carregadas do arquivo .env")
except Exception as e:
    logging.error(f"Erro ao carregar variáveis de ambiente: {e}")

# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Flag global para evitar processar o mesmo evento duas vezes
processed_updates = set()

def lambda_handler(event, context):
    """
    Função principal que processa as requisições do webhook do Telegram
    Versão ultra-simplificada para devolver resposta imediata ao API Gateway
    """
    # Log mínimo do evento
    logger.info("Webhook recebido")
    
    try:
        # Se houver corpo no evento, processa a mensagem
        if 'body' in event:
            body = event['body']
            is_base64_encoded = event.get('isBase64Encoded', False)
            
            # Se for base64, decodifica o corpo
            if is_base64_encoded:
                try:
                    body = base64.b64decode(body).decode('utf-8')
                except Exception as e:
                    logger.error(f"Erro ao decodificar corpo base64: {e}")
                    return {'statusCode': 200, 'body': json.dumps({'status': 'ok'})}
            
            # Tenta converter o corpo para JSON e processar
            try:
                update = json.loads(body)
                
                # Verificar se este update já foi processado (evitar duplicação)
                update_id = update.get('update_id', 0)
                
                # Considera como teste se o update_id for 123456789
                is_test = isinstance(update_id, int) and update_id == 123456789
                
                if is_test or update_id not in processed_updates:
                    # Adiciona ao conjunto de updates processados (exceto testes)
                    if not is_test and update_id > 0:
                        processed_updates.add(update_id)
                        # Limitar o tamanho do conjunto para evitar vazamento de memória
                        if len(processed_updates) > 1000:
                            processed_updates.clear()
                    
                    # Processar o update e retornar resposta imediatamente
                    return process_telegram_update(update)
                else:
                    logger.info(f"Update {update_id} já foi processado anteriormente, ignorando")
                    return {'statusCode': 200, 'body': json.dumps({'status': 'already_processed'})}
                
            except json.JSONDecodeError as e:
                logger.error(f"Erro ao fazer parse do JSON: {e}")
                return {'statusCode': 200, 'body': json.dumps({'status': 'invalid_json'})}
            except Exception as e:
                logger.error(f"Erro ao processar update: {e}")
                logger.error(traceback.format_exc())
                return {'statusCode': 200, 'body': json.dumps({'status': 'error'})}
        else:
            logger.warning("Evento sem corpo")
            return {'statusCode': 200, 'body': json.dumps({'status': 'no_body'})}
    except Exception as e:
        logger.error(f"Erro não tratado: {e}")
        logger.error(traceback.format_exc())
        return {'statusCode': 200, 'body': json.dumps({'status': 'error'})}