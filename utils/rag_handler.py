import os
import json
import boto3
import re
import logging
from utils import embedding_handler
import traceback
import threading
import time
from functools import wraps

# Configuração de logging
logger = logging.getLogger()

# Inicialização preguiçosa dos clientes AWS
_s3_client = None
_bedrock_client = None
_chroma_db = None

# Configuração de timeout
RAG_TIMEOUT = int(os.environ.get('RAG_TIMEOUT', '10'))  # 10 segundos por padrão

def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        )
    return _s3_client

def get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client(
            "bedrock-runtime", 
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        )
    return _bedrock_client

def get_chroma_db():
    """Carrega o ChromaDB se não estiver já carregado"""
    global _chroma_db
    if _chroma_db is None:
        logger.info("Carregando ChromaDB (inicialização preguiçosa)")
        _chroma_db = embedding_handler.load_existing_embeddings()
        if _chroma_db:
            logger.info("ChromaDB carregado com sucesso")
        else:
            logger.error("Falha ao carregar ChromaDB")
    return _chroma_db

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

def refinar_texto(texto):
    """
    Refina o texto para torná-lo mais legível, conciso e informativo.
    """
    # Remove caracteres de formatação especiais e códigos de escape
    texto = re.sub(r'\\[a-z0-9]{1,5}', ' ', texto)
    
    # Remove símbolos estranhos e substitui por espaços
    texto = re.sub(r'[•\u2022\u25cf\u25cb\u25aa\u25a0]', '- ', texto)
    
    # Normaliza aspas e outros caracteres
    texto = texto.replace('\"', '"').replace('\"', '"').replace("\'", "'")
    
    # Remove referências legais específicas
    texto = re.sub(r'\(e-STJ Fl\.[0-9]+\)', '', texto)
    texto = re.sub(r'R\. BELA CINTRA, 772[^\n]+', '', texto)
    texto = re.sub(r'\([^)]*\d+\/\d+[^)]*\)', '', texto)  # Referências com números entre parênteses
    
    # Remove códigos e marcações de formatação
    texto = re.sub(r'TEL \([0-9 ]+\)[^\n]*', '', texto)
    texto = re.sub(r'[0-9]{7}\.[Vv][0-9]{3} [0-9]+\/[0-9]+', '', texto)
    texto = re.sub(r'Documento recebido eletronicamente da origem', '', texto)
    texto = re.sub(r'SV\/AO ALVES DE OLIVEIRA & SALLES VANNI SOCIEDADE DE ADVOGADOS', '', texto)
    
    # Remove cabeçalhos e rodapés
    texto = re.sub(r'Poder Judici[^\n]+TRIBUNAL[^\n]+', '', texto)
    texto = re.sub(r'RECURSO ESPECIAL[^\n]+', '', texto)
    texto = re.sub(r'RECURSO EXTRAORDIN[^\n]+', '', texto)
    texto = re.sub(r'AGRAVO[^\n]+', '', texto)
    texto = re.sub(r'HABEAS CORPUS[^\n]+', '', texto)
    
    # Remove números de páginas e marcações de documentos
    texto = re.sub(r'\b\d+\/\d+\b', '', texto)
    texto = re.sub(r'\bp\. \d+\b', '', texto)
    
    # Remove termos jurídicos repetitivos
    texto = re.sub(r'\bIn verbis\b:', '', texto)
    texto = re.sub(r'\bEMENTA\b', '', texto)
    texto = re.sub(r'\bRel(ator)?\b\.?(\sMini?s?t?[^\n.]*)?', '', texto)
    texto = re.sub(r'\bDJe\b[^,\n.]*', '', texto)
    
    # Remove padrões de citações
    texto = re.sub(r'\([^)]{1,5}\)', '', texto)  # Referências curtas entre parênteses
    texto = re.sub(r'\[[^\]]+\]', '', texto)     # Conteúdo entre colchetes
    
    # Remove datas e códigos de processo
    texto = re.sub(r'\b\d{2}\/\d{2}\/\d{4}\b', '', texto)
    texto = re.sub(r'\b\d{4}\.\d{2}\.\d{2}\.\d{6}\b', '', texto)
    
    # Remove iniciais e códigos de maiúsculas repetidas
    texto = re.sub(r'([A-Z]{2,}(\.|\s|\/)){2,}', '', texto)
    texto = re.sub(r'\b[A-Z]{2,}\b', '', texto)  # Siglas isoladas
    
    # Remove sentenças que começam com símbolos ou números
    linhas = texto.split('\n')
    linhas_filtradas = []
    for linha in linhas:
        if not re.match(r'^[\d\W]', linha.strip()):
            linhas_filtradas.append(linha)
    texto = '\n'.join(linhas_filtradas)
    
    # Remove mensagens de erro ou avisos
    texto = re.sub(r'Erro:[^\n]+', '', texto)
    texto = re.sub(r'Aviso:[^\n]+', '', texto)
    
    # Remove múltiplos espaços e pontuações repetidas
    texto = re.sub(r'\s+', ' ', texto)
    texto = re.sub(r'\.{2,}', '.', texto)
    texto = re.sub(r'\s+\.', '.', texto)
    texto = re.sub(r'\s+,', ',', texto)
    
    # Restaura quebras de linha
    texto = re.sub(r'(\. |\? |\! )', '\\1\n', texto)
    
    # Remove linhas em branco repetidas
    texto = re.sub(r'\n\s*\n+', '\n\n', texto)
    
    # Remove linhas muito curtas (menos de 20 caracteres)
    linhas = texto.split('\n')
    linhas_filtradas = []
    for linha in linhas:
        if len(linha.strip()) >= 20 or not linha.strip():
            linhas_filtradas.append(linha)
    texto = '\n'.join(linhas_filtradas)
    
    return texto.strip()

def generate_response_with_bedrock(query, context_text):
    """
    Gera uma resposta usando o Amazon Bedrock Titan Text
    """
    client = get_bedrock_client()
    model_id = embedding_handler.get_text_model_id()
    
    try:
        prompt = f"""
Você é um assistente jurídico especializado. Com base na consulta e no contexto abaixo, 
elabore uma resposta concisa e informativa. Utilize apenas as informações do contexto.
Se o contexto não contiver informações suficientes, explique isso brevemente.

CONSULTA: {query}

CONTEXTO:
{context_text}

RESPOSTA:
"""
        
        # Preparar request para o modelo Titan
        request_body = json.dumps({
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 800,
                "temperature": 0.2,
                "topP": 0.9,
                "stopSequences": []
            }
        })
        
        # Invocar modelo
        logger.info(f"Invocando modelo Bedrock: {model_id}")
        response = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=request_body
        )
        
        # Processar resposta
        response_body = json.loads(response.get("body").read())
        generated_text = response_body.get("results")[0].get("outputText", "")
        
        # Limpar resposta
        generated_text = generated_text.strip()
        
        # Remover prefixos comuns que o modelo pode gerar
        prefixes_to_remove = ["RESPOSTA:", "Resposta:"]
        for prefix in prefixes_to_remove:
            if generated_text.startswith(prefix):
                generated_text = generated_text[len(prefix):].strip()
        
        logger.info("Resposta gerada com sucesso via Bedrock")
        return generated_text
        
    except Exception as e:
        logger.error(f"Erro ao gerar resposta com Bedrock: {e}")
        # Fallback para método simples se falhar
        return None

def consulta_rag(query):
    """Realiza consulta RAG com Bedrock para geração de resposta"""
    logger.info(f"Iniciando consulta RAG para: '{query}'")
    start_time = time.time()
    
    try:
        logger.info("Tentando usar ChromaDB em cache...")
        chroma_db = get_chroma_db()
        
        if not chroma_db:
            logger.error("Embeddings não encontrados ou não puderam ser carregados")
            return {"statusCode": 400, "body": json.dumps({"message": "Embeddings não encontrados. Execute a função initialize-embeddings primeiro."})}

        # Limite de documentos reduzido para melhorar performance em Lambda
        logger.info("Executando busca de similaridade no ChromaDB...")
        search_start = time.time()
        
        # Reduza o número de documentos para melhorar o tempo de resposta
        docs = chroma_db.similarity_search(query, k=1)  # Reduzido para apenas 1 documento
        
        search_duration = time.time() - search_start
        logger.info(f"Busca concluída em {search_duration:.2f} segundos")
        
        if not docs:
            logger.info("Nenhum documento relevante encontrado na busca")
            return {"statusCode": 404, "body": json.dumps({"message": "Nenhuma informação relevante encontrada para a consulta."})}
        
        # Extrair e preparar texto do contexto - simplificado
        context_text = docs[0].page_content
        source = docs[0].metadata.get('source', 'Desconhecida')
        
        # Simplificado - apenas limitamos o tamanho sem refinamento
        context_text = context_text[:3000]  # Reduzido para evitar tokens excessivos
        
        # Gera resposta usando Bedrock
        logger.info("Gerando resposta com base no contexto recuperado...")
        
        # Prompt simplificado para resposta mais rápida
        prompt = f"""
Com base neste contexto jurídico, responda de forma direta e objetiva:

PERGUNTA: {query}

CONTEXTO:
{context_text}

RESPOSTA:"""
        
        client = get_bedrock_client()
        model_id = embedding_handler.get_text_model_id()
        
        # Preparar request com configurações simplificadas
        request_body = json.dumps({
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 400,  # Reduzido para respostas mais curtas e rápidas
                "temperature": 0.1,    # Reduzido para respostas mais determinísticas
                "topP": 0.9,
                "stopSequences": []
            }
        })
        
        # Invocar modelo
        logger.info(f"Invocando modelo Bedrock: {model_id}")
        response = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=request_body
        )
        
        # Processar resposta
        response_body = json.loads(response.get("body").read())
        generated_response = response_body.get("results")[0].get("outputText", "").strip()
        
        # Remover prefixos comuns
        prefixes_to_remove = ["RESPOSTA:", "Resposta:"]
        for prefix in prefixes_to_remove:
            if generated_response.startswith(prefix):
                generated_response = generated_response[len(prefix):].strip()
        
        # Adicionar fonte ao final
        generated_response += f"\n\nFonte: {source}"
        
        total_duration = time.time() - start_time
        logger.info(f"Consulta RAG concluída em {total_duration:.2f} segundos")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "response": generated_response,
                "duration": f"{total_duration:.2f} segundos"
            })
        }
        
    except TimeoutError as e:
        logger.error(f"Timeout na consulta RAG: {e}")
        return {
            "statusCode": 504,
            "body": json.dumps({
                "message": "A consulta demorou muito tempo para ser processada.",
                "error": str(e)
            })
        }
    except Exception as e:
        logger.error(f"Erro na consulta RAG: {e}")
        logger.error(traceback.format_exc())
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Erro ao processar a consulta.",
                "error": str(e)
            })
        }