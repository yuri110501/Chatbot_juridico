import os
import json
import boto3
from langchain_chroma import Chroma
from langchain_aws import BedrockEmbeddings
from langchain.schema import Document
from utils import pdf_loader
import logging
import traceback


# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Obter variáveis do ambiente da função Lambda
EMBEDDING_BUCKET_NAME = os.environ.get("EMBEDDING_BUCKET_NAME")
CHROMA_DB_DIR = os.environ.get("CHROMA_DB_DIR", "/tmp/chroma_db")

# Modelos do Bedrock a serem usados
EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
TEXT_MODEL_ID = "amazon.titan-text-express-v1"

# Cliente inicializado de forma preguiçosa
_bedrock_client = None
_embeddings = None

# Configuração do S3
s3 = boto3.client('s3')
EMBEDDINGS_KEY = os.environ.get('EMBEDDINGS_KEY', 'embeddings/chroma_db')

def get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client(
            "bedrock-runtime", 
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        )
    return _bedrock_client

def get_embeddings():
    """Retorna o modelo de embeddings para uso com o ChromaDB"""
    global _embeddings
    if _embeddings is None:
        _embeddings = BedrockEmbeddings(client=get_bedrock_client(), model_id=EMBEDDING_MODEL_ID)
    return _embeddings

def get_text_model_id():
    """Retorna o ID do modelo de texto do Bedrock para geração de texto"""
    return TEXT_MODEL_ID

def get_bedrock_embeddings():
    """Configura o cliente de embeddings do Bedrock"""
    logger.info("Configurando cliente BedrockEmbeddings")
    try:
        # Usa o modelo Titan para embeddings via Bedrock
        bedrock_embeddings = BedrockEmbeddings(
            model_id="amazon.titan-embed-text-v1",
            region_name=os.environ.get('AWS_REGION', 'us-east-1')
        )
        logger.info("Cliente BedrockEmbeddings configurado com sucesso")
        return bedrock_embeddings
    except Exception as e:
        logger.error(f"Erro ao configurar BedrockEmbeddings: {e}")
        logger.error(traceback.format_exc())
        raise

def load_existing_embeddings():
    """Carrega embeddings existentes, otimizado para Lambda"""
    try:
        logger.info(f"Tentando carregar embeddings do S3: {EMBEDDING_BUCKET_NAME}")
        
        # Verificar se o diretório existe e criar se necessário
        os.makedirs(CHROMA_DB_DIR, exist_ok=True)
        logger.info(f"Diretório para embeddings: {CHROMA_DB_DIR}")
        
        # Define os arquivos necessários para o ChromaDB
        chroma_files = [
            "chroma.sqlite3"  # Arquivo principal do banco de dados
        ]
        
        all_files_exist = True
        
        for file in chroma_files:
            s3_key = f"{EMBEDDINGS_KEY}/{file}"
            local_path = os.path.join(CHROMA_DB_DIR, file)
            
            try:
                # Verificar se o arquivo existe no S3
                s3.head_object(Bucket=EMBEDDING_BUCKET_NAME, Key=s3_key)
                logger.info(f"Arquivo {s3_key} encontrado no S3")
                
                # Baixar o arquivo
                logger.info(f"Baixando arquivo {s3_key} para {local_path}")
                s3.download_file(EMBEDDING_BUCKET_NAME, s3_key, local_path)
                logger.info(f"Arquivo {file} baixado com sucesso")
                
                if not (os.path.exists(local_path) and os.path.getsize(local_path) > 0):
                    logger.error(f"Arquivo {file} baixado está vazio ou não existe")
                    all_files_exist = False
                    break
                    
            except Exception as e:
                logger.error(f"Erro ao verificar/baixar arquivo {file}: {e}")
                logger.error(traceback.format_exc())
                all_files_exist = False
                break
        
        if all_files_exist:
            try:
                # Carrega o ChromaDB do diretório
                logger.info(f"Carregando ChromaDB de {CHROMA_DB_DIR}")
                db = Chroma(
                    collection_name="juridico_collection", 
                    embedding_function=get_embeddings(), 
                    persist_directory=CHROMA_DB_DIR
                )
                logger.info("ChromaDB carregado com sucesso")
                return db
            except Exception as e:
                logger.error(f"Erro ao carregar ChromaDB: {e}")
                logger.error(traceback.format_exc())
        
        logger.warning("Nenhum embedding válido encontrado")
        return None
            
    except Exception as e:
        logger.error(f"Erro não esperado ao carregar embeddings: {e}")
        logger.error(traceback.format_exc())
        return None

def dividir_texto(texto, max_tokens=800):
    """Divide o texto em chunks para processamento"""
    words = texto.split()
    chunks, current_chunk = [], []
    current_length = 0
    
    for word in words:
        word_length = len(word.split())
        if current_length + word_length <= max_tokens:
            current_chunk.append(word)
            current_length += word_length
        else:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_length = word_length
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks

def criar_embeddings():
    """Gera embeddings para documentos jurídicos usando ChromaDB"""
    logger.info("Iniciando criação de embeddings com ChromaDB...")
    
    try:
        # Extrair texto dos PDFs
        extracted_text = pdf_loader.processar_pdfs()
        if not extracted_text:
            logger.warning("Nenhum texto extraído dos PDFs.")
            return {"statusCode": 400, "body": json.dumps({"message": "Nenhum texto extraído"})}
        
        logger.info(f"Textos extraídos de {len(extracted_text)} documentos.")
        
        # Garantir que o diretório existe
        os.makedirs(CHROMA_DB_DIR, exist_ok=True)
        logger.info(f"Diretório para embeddings: {CHROMA_DB_DIR}")
        
        try:
            # Criar ChromaDB
            logger.info("Configurando embeddings com Bedrock...")
            embedding_function = get_embeddings()
            
            logger.info("Criando ChromaDB...")
            vector_store = Chroma(
                collection_name="juridico_collection", 
                embedding_function=embedding_function, 
                persist_directory=CHROMA_DB_DIR
            )
            
            total_chunks = 0
            
            # Processar cada documento
            for key, text in extracted_text.items():
                logger.info(f"Processando documento: {key}")
                chunks = dividir_texto(text, max_tokens=800)
                logger.info(f" - Dividido em {len(chunks)} partes")
                
                docs = [Document(page_content=part, metadata={"source": key, "chunk": i}) for i, part in enumerate(chunks)]
                total_chunks += len(docs)
                
                logger.info(f" - Adicionando {len(docs)} documentos ao ChromaDB")
                vector_store.add_documents(docs)
                logger.info(f" - Documentos adicionados com sucesso")
            
            # O ChromaDB já armazena automaticamente os dados no diretório especificado
            # quando configurado com persist_directory
            logger.info("O ChromaDB já está persistindo automaticamente os dados no diretório especificado")
            logger.info(f"Total de {total_chunks} partes de documentos processadas")
            
            # Upload para S3
            try:
                logger.info(f"Fazendo upload dos arquivos para S3 ({EMBEDDING_BUCKET_NAME})...")
                
                # Verifica se o bucket está definido
                if not EMBEDDING_BUCKET_NAME:
                    logger.error("EMBEDDING_BUCKET_NAME não está definido nas variáveis de ambiente")
                    return {
                        "statusCode": 200, 
                        "body": json.dumps({
                            "message": f"Embeddings criados com sucesso localmente, mas EMBEDDING_BUCKET_NAME não está definido para upload."
                        })
                    }
                
                # Lista os arquivos no diretório ChromaDB
                files_to_upload = []
                for root, dirs, files in os.walk(CHROMA_DB_DIR):
                    for file in files:
                        if file.endswith('.sqlite3'):
                            local_path = os.path.join(root, file)
                            rel_path = os.path.relpath(local_path, CHROMA_DB_DIR)
                            files_to_upload.append((local_path, rel_path))
                
                logger.info(f"Encontrados {len(files_to_upload)} arquivos para upload")
                
                # Faz upload de cada arquivo
                for local_path, rel_path in files_to_upload:
                    s3_key = f"{EMBEDDINGS_KEY}/{rel_path}"
                    logger.info(f"Enviando arquivo {local_path} para S3:{s3_key}...")
                    s3.upload_file(local_path, EMBEDDING_BUCKET_NAME, s3_key)
                    logger.info(f"Arquivo enviado com sucesso")
                
                return {
                    "statusCode": 200, 
                    "body": json.dumps({
                        "message": f"Embeddings criados e salvos com sucesso. Total de {total_chunks} chunks processados."
                    })
                }
                
            except Exception as e:
                logger.error(f"Erro ao fazer upload para S3: {e}")
                logger.error(traceback.format_exc())
                
                # Ainda retornamos sucesso, já que os embeddings foram criados localmente
                return {
                    "statusCode": 200, 
                    "body": json.dumps({
                        "message": "Embeddings criados localmente, mas não puderam ser enviados para S3."
                    })
                }
                
        except Exception as e:
            logger.error(f"Erro ao criar ChromaDB: {e}")
            logger.error(traceback.format_exc())
            return {
                "statusCode": 500, 
                "body": json.dumps({
                    "message": f"Erro ao criar ChromaDB: {str(e)}"
                })
            }
            
    except Exception as e:
        logger.error(f"Erro não tratado ao criar embeddings: {e}")
        logger.error(traceback.format_exc())
        return {
            "statusCode": 500, 
            "body": json.dumps({
                "message": f"Erro interno ao criar embeddings: {str(e)}"
            })
        }