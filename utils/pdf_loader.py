import os
import logging
from langchain_community.document_loaders import PyPDFLoader
from utils import s3_bucket_handler

# Configuração de logging
logger = logging.getLogger()

# Obter variáveis do ambiente da função Lambda
PDF_BUCKET_NAME = os.environ.get("PDF_BUCKET_NAME")
PDF_FOLDER = os.environ.get("PDF_FOLDER", "dataset/juridicos/")
LOCAL_FOLDER = os.environ.get("LOCAL_FOLDER", "/tmp/pdfs")

def processar_pdfs():
    """Processa PDFs e extrai texto, otimizado para Lambda"""
    # Garante que o diretório local existe no /tmp do Lambda
    lambda_tmp_folder = os.path.join("/tmp", "pdf_cache")
    try:
        os.makedirs(lambda_tmp_folder, exist_ok=True)
        logger.info(f"Diretório para PDFs criado: {lambda_tmp_folder}")
    except Exception as e:
        logger.error(f"Erro ao criar diretório para PDFs: {e}")
        # Tenta um caminho alternativo se falhar
        lambda_tmp_folder = "/tmp"
    
    try:
        # Tenta buscar PDFs do S3
        pdf_files = s3_bucket_handler.list_s3_files(PDF_BUCKET_NAME, PDF_FOLDER)
        logger.info(f"Encontrados {len(pdf_files)} arquivos no bucket {PDF_BUCKET_NAME}")
        
        if not pdf_files:
            # Fallback para arquivos locais se não encontrar no S3
            local_dataset = os.path.join(os.getcwd(), "dataset")
            if os.path.exists(local_dataset):
                pdf_files = []
                for root, dirs, files in os.walk(local_dataset):
                    for file in files:
                        if file.lower().endswith('.pdf'):
                            pdf_files.append(os.path.join(root, file))
                logger.info(f"Usando {len(pdf_files)} arquivos do diretório local dataset")
    except Exception as e:
        logger.error(f"Erro ao listar arquivos: {e}")
        pdf_files = []
    
    # Retorna dicionário vazio se não houver arquivos
    if not pdf_files:
        logger.warning("Nenhum arquivo PDF encontrado para processar")
        return {}
    
    extracted_text = {}
    
    # Limite o número de PDFs processados por invocação em ambiente Lambda
    # para evitar timeout ou uso excessivo de memória
    max_pdfs_per_invocation = 5
    pdf_files = pdf_files[:max_pdfs_per_invocation]
    
    for pdf_key in pdf_files:
        try:
            # Extrai apenas o nome base do arquivo
            filename = os.path.basename(pdf_key)
            local_pdf_path = os.path.join(lambda_tmp_folder, filename)
            
            logger.info(f"Processando: {pdf_key}")
            
            # Verifica se está processando um arquivo S3 ou local
            if pdf_key.startswith('/'):  # Arquivo local
                if os.path.exists(pdf_key):
                    loader = PyPDFLoader(pdf_key)
                else:
                    logger.warning(f"Arquivo local não encontrado: {pdf_key}")
                    continue
            else:  # Arquivo S3
                try:
                    s3_bucket_handler.download_from_s3(PDF_BUCKET_NAME, pdf_key, local_pdf_path)
                    loader = PyPDFLoader(local_pdf_path)
                except Exception as s3_err:
                    logger.error(f"Erro ao baixar do S3 {pdf_key}: {s3_err}")
                    continue
            
            pages = loader.load()
            extracted_text[pdf_key] = "\n".join([page.page_content for page in pages])
            logger.info(f"PDF processado: {filename}")
            
            # Limpa o arquivo temporário após processamento para economizar espaço
            if os.path.exists(local_pdf_path) and not pdf_key.startswith('/'):
                try:
                    os.remove(local_pdf_path)
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Erro ao processar PDF {pdf_key}: {e}")
            continue

    logger.info(f"Total de {len(extracted_text)} documentos processados")
    return extracted_text