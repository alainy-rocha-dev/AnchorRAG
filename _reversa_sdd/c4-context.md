# C4 — Contexto: HAG RAG

> Diagrama C4 Nível 1 — Contexto do Sistema
> Gerado pelo Reversa Architect em 2026-09-22

```mermaid
C4Context
title Diagrama de Contexto — HAG RAG (Projeto HAG 2)

Person(user, "Usuário / Desenvolvedor", "Opera via CLI `hag-rag`: ingest PDFs, queries RAG, eval pipeline")
Person(devops, "DevOps / Infra", "Gerencia configuração (YAML), secrets (.env), monitora logs/DB")

System_Boundary(hag_rag, "HAG RAG") {
    System(cli, "CLI (hag-rag)", "Typer + Rich", "Comandos: ingest, query, eval — output table/JSON/Markdown")
    System(pipeline, "RAG Pipeline", "Python async", "Orquestra ingestão (parse→chunk→embed→store) e query (embed→search→synthesize)")
    SystemDb(db, "SQLite + sqlite-vec", "sqlite3 + vec0 extension", "Documents, Chunks, Embeddings (virtual table), Query Log")
}

System_Ext(openai, "OpenAI API", "SaaS", "Embeddings: text-embedding-3-small/large • LLM: gpt-4o-mini")
System_Ext(ollama, "Ollama (Local)", "HTTP localhost:11434", "Embeddings: nomic-embed-text, mxbai-embed-large • LLM: llama3, mistral, etc.")
System_Ext(hf, "HuggingFace (Local)", "Python: sentence-transformers", "Embeddings: BGE, E5, Arctic, etc. — execução 100% local")
System_Ext(anthropic, "Anthropic API", "SaaS", "LLM: claude-3-haiku/sonnet/opus")
System_Ext(pdf_libs, "PDF Libraries", "Python packages", "pdfplumber (texto+tabelas) • PyPDF (fallback leve)")

Rel(user, cli, "Executa comandos", "stdin / stdout / stderr")
Rel(devops, cli, "Fornece configuração", "config.yaml + .env")
Rel(cli, pipeline, "Invoca operações", "Injeção de dependência / async Python")
Rel(pipeline, db, "Persiste e busca", "sqlite3 + sqlite-vec (ACID, WAL)")
Rel(pipeline, openai, "Consome APIs", "HTTPS/REST (Bearer token)")
Rel(pipeline, ollama, "Consome APIs locais", "HTTP/REST + SSE (sem auth)")
Rel(pipeline, hf, "Executa localmente", "Python import (sentence-transformers)")
Rel(pipeline, anthropic, "Consome API", "HTTPS/REST (Bearer token)")
Rel(pipeline, pdf_libs, "Parseia PDFs", "Python import")
```

---

## Legenda

| Elemento | Descrição |
|----------|-----------|
| **Person** | Ator humano (usuário final, DevOps) |
| **System** | Aplicação de software (CLI, Pipeline) |
| **SystemDb** | Armazenamento de dados (SQLite + sqlite-vec) |
| **System_Ext** | Sistema externo (APIs, bibliotecas) |
| **Rel** | Relacionamento com protocolo/tecnologia |

---

## Narrativa

O **HAG RAG** é um sistema **local-first** de *Retrieval-Augmented Generation* operado primariamente via **CLI**. O usuário (desenvolvedor/analista) ingere documentos PDF, que são parseados, chunkados, embeddados e armazenados em um banco **SQLite com extensão vetorial nativa (sqlite-vec)**. Queries são transformadas em embeddings, buscadas por similaridade de cosseno no banco, e sintetizadas por um **LLM** com **ancoragem estrita** e **citações numéricas**.

O sistema suporta **três modos de operação** para embeddings e LLM:
- **Cloud (OpenAI, Anthropic)** — melhor qualidade, custo por token, requer API key
- **Local (Ollama)** — privacidade total, roda em localhost:11434, modelos abertos
- **Local Offline (HuggingFace)** — 100% offline, `sentence-transformers`, apenas embeddings

A configuração é **declarativa** via YAML + variáveis de ambiente (`.env`), com resolução segura de secrets. Observabilidade nativa via **JSON logging com request_id** e **query_log table** com latência por etapa.