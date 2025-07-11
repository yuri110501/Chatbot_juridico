# 🤖 Chatbot Jurídico com RAG

![Status](https://img.shields.io/badge/Status-Online-brightgreen)
![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![AWS](https://img.shields.io/badge/AWS-Cloud-orange?logo=amazon-aws)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Database-009688)
![LangChain](https://img.shields.io/badge/LangChain-Framework-2E68C0)

---

## 🚀 Sobre o Projeto

Esse projeto é um chatbot jurídico inteligente, feito pra responder perguntas sobre documentos jurídicos usando RAG (Retrieval-Augmented Generation) e IA generativa. Ele integra AWS, ChromaDB, LangChain e Telegram pra entregar respostas rápidas e precisas, direto no seu chat.

---

## 🏗️ Como Funciona?

1. **Recebe perguntas pelo Telegram**
2. **Busca e processa documentos jurídicos (PDFs)**
3. **Gera embeddings e indexa tudo com ChromaDB**
4. **Usa AWS Bedrock pra gerar respostas baseadas nos documentos**
5. **Entrega a resposta no chat, de forma clara e rápida**

---

## 🛠️ Tecnologias Usadas

- **Python 3.12**
- **AWS Lambda, S3, Bedrock, API Gateway, EC2**
- **ChromaDB**
- **LangChain**
- **Telegram Bot**
- **NLTK, Requests, Boto3, pypdf**

---

## 📦 Estrutura do Projeto
```bash
chatbot-juridico-rag/
 ┣ dataset/           # PDFs jurídicos
 ┣ libs/              # Camadas e libs customizadas
 ┣ utils/             # Scripts utilitários (RAG, Telegram, S3, Embeddings, PDF)
 ┣ lambda_function.py # Handler principal do Lambda
 ┣ lambda_initialize.py # Setup e inicialização
 ┣ requirements.txt   # Dependências
 ┗ README.md
```

---

## ⚙️ Funcionalidades
- Consulta automática de documentos jurídicos
- Respostas geradas por IA com contexto real dos documentos
- Pipeline completo: PDF → Embedding → Indexação → Resposta
- Integração total com AWS e Telegram
- Fácil de escalar e adaptar pra outros domínios

---

## 🖥️ Como Usar

1. **Configure as variáveis de ambiente AWS e Telegram**
2. **Suba os PDFs na pasta `dataset/` ou no S3**
3. **Rode o `lambda_initialize.py` pra preparar tudo**
4. **Implemente o webhook do Telegram apontando pro Lambda**
5. **Mande perguntas no Telegram e receba respostas inteligentes!**

---

## 📑 Exemplo de Arquitetura

// Aqui você pode colocar um diagrama ou imagem da arquitetura, se quiser

---

## 📋 Requisitos

```bash
# Instale as dependências
pip install -r requirements.txt
```

---

## 💡 Diferenciais
- Código limpo, comentado só onde precisa (em português e de boa)
- Pronto pra cloud, serverless e fácil de manter
- Modular: cada parte (PDF, embedding, RAG, Telegram) é independente
- Fácil de customizar pra outros tipos de documento

---

## 👤 Autor

- Yuri Gabriel

