import json
import logging
import os
import traceback
from utils import embedding_handler
from utils import s3_bucket_handler
from utils import pdf_loader
from utils import rag_handler

# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def initialize_s3_buckets():
    """Inicializa os buckets S3 necessários para o projeto"""
    logger.info("Inicializando buckets S3...")
    
    # Obter nomes dos buckets das variáveis de ambiente
    pdf_bucket = os.environ.get("PDF_BUCKET_NAME")
    embedding_bucket = os.environ.get("EMBEDDING_BUCKET_NAME")
    
    status = {}
    
    # Verificar e criar buckets se necessário
    if pdf_bucket:
        status["pdf_bucket"] = s3_bucket_handler.check_bucket_exists(pdf_bucket)
        logger.info(f"Bucket PDF ({pdf_bucket}): {'✅' if status['pdf_bucket'] else '❌'}")
    
    if embedding_bucket:
        status["embedding_bucket"] = s3_bucket_handler.check_bucket_exists(embedding_bucket)
        logger.info(f"Bucket Embeddings ({embedding_bucket}): {'✅' if status['embedding_bucket'] else '❌'}")
    
    return status

def process_pdf_documents():
    """Processa os documentos PDF e extrai o texto"""
    logger.info("Processando documentos PDF...")
    
    try:
        extracted_text = pdf_loader.processar_pdfs()
        num_docs = len(extracted_text)
        logger.info(f"Processados {num_docs} documentos PDF")
        return {"status": True, "num_documents": num_docs}
    except Exception as e:
        logger.error(f"Erro ao processar PDFs: {e}")
        logger.error(traceback.format_exc())
        return {"status": False, "error": str(e)}

def generate_embeddings():
    """Gera os embeddings para os documentos processados"""
    logger.info("Gerando embeddings...")
    
    try:
        resultado = embedding_handler.criar_embeddings()
        if resultado["statusCode"] == 200:
            logger.info("Embeddings gerados com sucesso")
            return {"status": True, "message": json.loads(resultado["body"])["message"]}
        else:
            logger.error(f"Erro ao gerar embeddings: {resultado}")
            return {"status": False, "error": json.loads(resultado["body"])["message"]}
    except Exception as e:
        logger.error(f"Erro ao gerar embeddings: {e}")
        logger.error(traceback.format_exc())
        return {"status": False, "error": str(e)}

def test_rag_system():
    """Testa o sistema RAG com uma consulta simples"""
    logger.info("Testando sistema RAG...")
    
    try:
        test_query = "O que é um recurso especial?"
        resultado = rag_handler.consulta_rag(test_query)
        
        if resultado["statusCode"] == 200:
            logger.info("Sistema RAG funcionando corretamente")
            return {"status": True, "message": "Sistema RAG operacional"}
        else:
            logger.warning(f"Sistema RAG retornou status {resultado['statusCode']}")
            return {"status": False, "error": json.loads(resultado["body"])["message"]}
    except Exception as e:
        logger.error(f"Erro ao testar sistema RAG: {e}")
        logger.error(traceback.format_exc())
        return {"status": False, "error": str(e)}

def lambda_handler(event, context):
    """
    Função Lambda para inicializar todo o sistema
    
    Este handler executa todas as etapas necessárias para configurar o sistema:
    1. Inicializa buckets S3
    2. Processa documentos PDF
    3. Gera embeddings
    4. Testa o sistema RAG
    """
    logger.info("Iniciando inicialização completa do sistema")
    
    results = {
        "s3_buckets": None,
        "pdf_processing": None,
        "embeddings": None,
        "rag_test": None
    }
    
    try:
        # Etapa 1: Inicializar buckets S3
        results["s3_buckets"] = initialize_s3_buckets()
        
        # Etapa 2: Processar documentos PDF
        results["pdf_processing"] = process_pdf_documents()
        
        # Etapa 3: Gerar embeddings
        results["embeddings"] = generate_embeddings()
        
        # Etapa 4: Testar sistema RAG
        if results["embeddings"]["status"]:
            results["rag_test"] = test_rag_system()
        
        # Verificar status geral
        all_success = all([
            results["s3_buckets"].get("pdf_bucket", False) if "pdf_bucket" in results["s3_buckets"] else True,
            results["s3_buckets"].get("embedding_bucket", False) if "embedding_bucket" in results["s3_buckets"] else True,
            results["pdf_processing"]["status"] if results["pdf_processing"] else False,
            results["embeddings"]["status"] if results["embeddings"] else False,
            results["rag_test"]["status"] if results["rag_test"] else False
        ])
        
        status_code = 200 if all_success else 500
        
        return {
            'statusCode': status_code,
            'body': json.dumps({
                'message': 'Inicialização do sistema concluída' if all_success else 'Inicialização do sistema com erros',
                'results': results
            })
        }
            
    except Exception as e:
        logger.error(f"Erro durante a inicialização completa: {e}")
        logger.error(traceback.format_exc())
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Erro interno ao inicializar o sistema',
                'error': str(e),
                'results': results
            })
        } 