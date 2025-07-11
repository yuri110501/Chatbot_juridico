import os
import boto3
import time
import logging

# Configurar logging
logger = logging.getLogger()

_s3_client = None

def get_s3_client():
    """Obtém ou inicializa cliente S3 com retry em caso de erro"""
    global _s3_client
    
    if _s3_client is not None:
        return _s3_client
        
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            _s3_client = boto3.client(
                "s3",
                region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
            )
            # Testa a conexão (chamada leve apenas para validar credenciais)
            _s3_client.list_buckets()
            logger.info("Conexão S3 estabelecida")
            return _s3_client
        except Exception as e:
            logger.error(f"Erro na tentativa {attempt+1} de conectar ao S3: {e}")
            if attempt < max_attempts - 1:
                wait_time = 2 ** attempt  # Backoff exponencial
                time.sleep(wait_time)
            else:
                logger.error("Falha ao conectar ao S3 após várias tentativas")
                raise
    
    return None

def list_s3_files(bucket_name, prefix):
    """Lista arquivos no bucket S3 com retry e tratamento de erros"""
    s3 = get_s3_client()
    if not s3:
        logger.error("Cliente S3 não disponível")
        return []
        
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            files = [obj["Key"] for obj in response.get("Contents", [])]
            logger.info(f"Listados {len(files)} arquivos de {bucket_name}/{prefix}")
            return files
        except Exception as e:
            logger.error(f"Erro na tentativa {attempt+1} de listar arquivos S3: {e}")
            if attempt < max_attempts - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"Falha ao listar arquivos do bucket {bucket_name}")
                return []

def download_from_s3(bucket_name, s3_key, local_path):
    """Baixa um arquivo do S3 com retry e tratamento de erros"""
    s3 = get_s3_client()
    if not s3:
        logger.error("Cliente S3 não disponível")
        raise Exception("Cliente S3 não inicializado")
        
    # Cria o diretório local se não existir
    os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            logger.info(f"Baixando {s3_key} para {local_path}")
            s3.download_file(bucket_name, s3_key, local_path)
            
            # Verifica se o arquivo foi baixado corretamente
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                logger.info(f"Download concluído: {local_path} ({os.path.getsize(local_path)} bytes)")
                return True
            else:
                raise Exception("Arquivo baixado está vazio ou não existe")
                
        except Exception as e:
            logger.error(f"Erro na tentativa {attempt+1} de baixar arquivo: {e}")
            if attempt < max_attempts - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"Falha ao baixar {s3_key} após várias tentativas")
                raise

def upload_to_s3(local_path, bucket_name, s3_key):
    """Envia um arquivo para o S3 com retry e tratamento de erros"""
    s3 = get_s3_client()
    if not s3:
        logger.error("Cliente S3 não disponível")
        raise Exception("Cliente S3 não inicializado")
        
    if not os.path.exists(local_path):
        logger.error(f"Arquivo local não existe: {local_path}")
        raise FileNotFoundError(f"Arquivo não encontrado: {local_path}")
        
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            logger.info(f"Enviando {local_path} para {bucket_name}/{s3_key}")
            s3.upload_file(local_path, bucket_name, s3_key)
            
            # Verifica se o upload foi bem-sucedido
            try:
                response = s3.head_object(Bucket=bucket_name, Key=s3_key)
                s3_size = response.get('ContentLength', 0)
                logger.info(f"Upload concluído: {s3_key} ({s3_size} bytes)")
                return True
            except:
                raise Exception("Não foi possível verificar o arquivo após upload")
                
        except Exception as e:
            logger.error(f"Erro na tentativa {attempt+1} de enviar arquivo: {e}")
            if attempt < max_attempts - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"Falha ao enviar {local_path} após várias tentativas")
                raise

def check_bucket_exists(bucket_name):   
    """Verifica se um bucket existe e o cria se necessário"""
    s3 = get_s3_client()
    if not s3:
        logger.error("Cliente S3 não disponível")
        return False
        
    try:
        s3.head_bucket(Bucket=bucket_name)
        logger.info(f"Bucket {bucket_name} existe")
        return True
    except:
        try:
            logger.info(f"Criando bucket {bucket_name}...")
            s3.create_bucket(Bucket=bucket_name)
            logger.info(f"Bucket {bucket_name} criado com sucesso")
            return True
        except Exception as e:
            logger.error(f"Erro ao criar bucket {bucket_name}: {e}")
            return False