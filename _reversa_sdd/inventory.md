# Inventário do Projeto: AnchorRAG

> Gerado pelo Reversa Scout em 2026-09-30
> Nível de documentação: **essencial**

---

## 1. Visão Geral

**AnchorRAG** é um pipeline RAG (Retrieval-Augmented Generation) local-first para ingestão de PDFs, geração de embeddings multi-provedor, busca vetorial com SQLite + sqlite-vec e síntese com ancoragem estrita, citações e defesa few-shot contra prompt injection.

| Aspecto | Detalhe |
|---------|---------|
| **Nome do pacote** | `anchor-rag` |
| **Versão** | `0.1.0` |
| **Python** | `>=3.11` |
| **Licença** | MIT |
| **Entry point CLI** | `anchor-rag` (Typer) |
| **Gerenciador de pacotes** | pip / uv (pyproject.toml + uv.lock) |

---

## 2. Estrutura de Diretórios

```
C:\rag\
├── .agents/                 # Skills do Reversa
├── .claude/                 # Configuração Claude
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI
├── .reversa/                # Estado e artefatos do Reversa
│   ├── context/
│   │   └── surface.json     # Este arquivo (surface)
│   ├── state.json           # Estado do pipeline
│   └── ...
├── docs/
│   └── embedding-benchmark.md
├── scripts/
│   └── benchmark_embeddings.py
├── src/
│   └── anchor_rag/          # Package principal
│       ├── __init__.py
│       ├── cli.py           # Entry point Typer (ingest, query, eval)
│       ├── cli_eval.py      # Comando eval
│       ├── cli_ingest.py    # Comando ingest
│       ├── cli_query.py     # Comando query
│       ├── config.py        # Pydantic Settings (YAML + env + secrets)
│       ├── logging.py       # JSON logging + request_id (contextvar)
│       ├── domain/          # Modelos + exceções
│       │   ├── __init__.py
│       │   ├── models.py    # Document, Chunk, QueryResult, configs
│       │   └── exceptions.py
│       ├── ingestion/       # Parser + Chunker + Pipeline
│       │   ├── __init__.py
│       │   ├── parser.py    # PDFParser ABC + pdfplumber/PyPDF
│       │   ├── chunker.py   # Tokens/chars, overlap, metadados
│       │   └── pipeline.py  # IngestionPipeline (orquestra)
│       ├── embeddings/      # Strategy: OpenAI/Ollama/HF
│       │   ├── __init__.py  # Factory + registry
│       │   ├── base.py      # EmbeddingProvider ABC
│       │   ├── openai.py    # OpenAIEmbeddingProvider (retry 3x)
│       │   ├── ollama.py    # OllamaEmbeddingProvider (HTTP /api/embed)
│       │   └── huggingface.py
│       ├── vector_store/    # SQLite + sqlite-vec
│       │   ├── __init__.py  # Factory
│       │   ├── base.py      # VectorStore ABC
│       │   └── sqlite_vec.py
│       ├── synthesis/       # LLM + Prompt + Synthesizer
│       │   ├── __init__.py  # Factory + registry
│       │   ├── llm.py       # LLMProvider ABC
│       │   ├── openai_llm.py
│       │   ├── ollama_llm.py
│       │   ├── anthropic_llm.py
│       │   ├── prompt.py    # Ancoragem estrita + few-shot
│       │   └── synthesizer.py
│       └── pipeline/
│           └── orchestrator.py  # RAGPipeline (ingest/query/eval)
├── tests/
│   ├── fixtures/            # Textos sintéticos + eval_dataset_bacen.yaml
│   ├── unit/                # 9 arquivos (text, models, config, contratos)
│   └── integration/         # 5 arquivos (ingestion, query, e2e, prompt_injection)
├── _reversa_sdd/            # Artefatos da extração reversa
├── _reversa_forward/        # Features do ciclo forward
│   ├── 001-pipeline-rag-hag2/
│   └── 002-rag-evaluation-hardening/
├── _reversa_docs/           # Mini-site docs
├── pyproject.toml           # PEP 621 config + deps
├── config.example.yaml      # Template de configuração
├── uv.lock                  # Lockfile uv
├── README.md                # Documentação completa
├── AGENTS.md                # Instruções do Reversa
├── CLAUDE.md                # Config Claude
└── LINKEDIN_POST.md
```

---

## 3. Módulos Identificados (11 módulos)

| Módulo | Arquivos | Responsabilidade |
|--------|----------|------------------|
| `config` | `config.py` | Pydantic Settings v2: YAML + env vars aninhadas + resolução de API keys |
| `domain` | `models.py`, `exceptions.py` | Document, Chunk, QueryResult, IngestConfig, QueryConfig, ChunkUnit enum, hierarquia de exceções |
| `utils.text` | `text.py` | SHA256, sanitize (control chars, NFKC, hyphen fix), tiktoken chunking, UUID |
| `logging` | `logging.py` | JSON logging, RequestIdFilter (contextvar), CustomJsonFormatter |
| `ingestion` | `parser.py`, `chunker.py`, `pipeline.py` | PDFParser (pdfplumber/PyPDF), Chunker (tokens/chars), IngestionPipeline |
| `embeddings` | `base.py`, `openai.py`, `ollama.py`, `huggingface.py`, `__init__.py` | Strategy Pattern: 3 provedores + factory/registry |
| `vector_store` | `base.py`, `sqlite_vec.py`, `__init__.py` | VectorStore ABC, SQLiteVecStore (sqlite-vec virtual table), factory |
| `synthesis` | `llm.py`, `openai_llm.py`, `ollama_llm.py`, `anthropic_llm.py`, `prompt.py`, `synthesizer.py`, `__init__.py` | LLMProvider ABC, 3 provedores, prompt ancoragem estrita, RAGSynthesizer |
| `pipeline` | `orchestrator.py` | RAGPipeline: wiring completo (ingest, query, eval) |
| `cli` | `cli.py`, `cli_ingest.py`, `cli_query.py`, `cli_eval.py` | Typer app: comandos ingest/query/eval |
| `tests` | `unit/`, `integration/`, `fixtures/` | Contratos ABC, integração pipeline, e2e, adversarial |

---

## 4. Dependências Principais

### Core (dependencies)
| Pacote | Versão | Uso |
|--------|--------|-----|
| `pdfplumber` | >=0.11.0 | Parser PDF rico (tabelas) |
| `pypdf` | >=5.0.0 | Parser PDF leve (fallback) |
| `tiktoken` | >=0.7.0 | Contagem tokens + chunking |
| `numpy` | >=1.26.0 | Arrays numéricos (embeddings) |
| `sqlite-vec` | >=0.1.6 | Extensão SQLite para busca vetorial |
| `httpx` | >=0.27.0 | HTTP async (Ollama, APIs) |
| `typer` | >=0.12.0 | CLI framework |
| `pydantic` | >=2.8.0 | Validação + Settings |
| `pydantic-settings` | >=2.4.0 | Config via YAML/env |
| `pyyaml` | >=6.0.1 | Parse YAML config |
| `tenacity` | >=8.0.0 | Retry exponencial (OpenAI) |

### Opcionais (optional-dependencies)
| Extra | Pacotes | Uso |
|-------|---------|-----|
| `openai` | `openai>=1.35.0` | OpenAIEmbeddingProvider, OpenAILLMProvider |
| `ollama` | (nenhum) | OllamaEmbeddingProvider, OllamaLLMProvider |
| `huggingface` | `sentence-transformers>=3.0.0`, `torch>=2.3.0` | HuggingFaceEmbeddingProvider |
| `anthropic` | `anthropic>=0.30.0` | AnthropicLLMProvider |

### Dev
| Pacote | Versão | Uso |
|--------|--------|-----|
| `pytest` | >=8.2.0 | Test runner |
| `ruff` | >=0.5.0 | Lint/format |
| `mypy` | >=1.10.0 | Type checking strict |
| `pytest-asyncio` | >=0.23.0 | Async tests |
| `pytest-cov` | >=5.0.0 | Coverage |

---

## 5. Integrações Externas (4)

| Sistema | Protocolo | Autenticação | Uso |
|---------|-----------|--------------|-----|
| **OpenAI API** | HTTPS/REST | Bearer token (API Key) | Embeddings + LLM |
| **Ollama** | HTTP/REST (localhost:11434) | Nenhuma (local) | Embeddings + LLM locais |
| **HuggingFace** | Local (sentence-transformers) | Nenhuma | Embeddings locais |
| **Anthropic API** | HTTPS/REST | Bearer token (API Key) | LLM |

---

## 6. Banco de Dados

**SQLite + sqlite-vec** (virtual table `chunks_vec`)

- Tabelas: `documents`, `chunks`, `chunks_vec` (virtual), `query_log`
- Schema auto-criado via DDL em `SQLiteVecStore.init_db()`
- Busca cosseno nativa via `vec_distance_cosine()`
- Cascade delete: remover documento apaga chunks + rows na virtual table
- Query log opcional (`query_log.enabled`)

---

## 7. Testes

| Tipo | Arquivos | Cobertura |
|------|----------|-----------|
| **Unit** | 9 (`test_*.py`) | text_utils, models, config, embedding_provider_contract, llm_provider_contract, vector_store_contract |
| **Integration** | 5 (`test_*.py`) | ingestion_pipeline, query_pipeline, e2e, prompt_injection (10 ataques) |
| **Fixtures** | 3 textos + 1 YAML eval | sample.txt, table.txt, corrupted.txt, eval_dataset_bacen.yaml (22 casos) |
| **Total** | 19 arquivos | 93 passed, 2 skipped |

---

## 8. CI/CD

**GitHub Actions** (`.github/workflows/ci.yml`)
- Matrix: Python 3.11, 3.12
- Steps: ruff check, ruff format, mypy strict, pytest + coverage, build package, verify install

---

## 9. Configuração

**Arquivo**: `config.example.yaml` → copiar para `config.yaml`

Seções:
- `embedding`: provider, model, dimensions, batch_size, api_key_env, base_url
- `llm`: provider, model, temperature, max_tokens, timeout, api_key_env, base_url
- `chunking`: chunk_size (512), chunk_overlap (50), chunk_unit (tokens), min_chunk_size
- `vector_store`: type (sqlite_vec), path, embedding_dimensions
- `logging`: level, format (json/text), output, include_request_id
- `query_log`: enabled, path

Resolução de secrets: `AppConfig.resolve_api_keys()` lê `api_key_env` do `os.environ`

---

## 10. Pontos de Entrada

| Comando | Descrição |
|---------|-----------|
| `anchor-rag ingest <paths> [--recursive] [--force] [--parser pdfplumber|pypdf] [--chunk-size N] [--format text|json]` | Ingestão de PDFs |
| `anchor-rag query <question> [--top-k 5] [--threshold 0.7] [--llm-provider openai|ollama|anthropic] [--no-synthesis] [--format text|json]` | Query RAG |
| `anchor-rag eval [--config config.yaml] [--dataset bacen.yaml] [--k 5] [--format text|json]` | Avaliação (health checks + métricas com dataset) |

---

## 11. Documentação

- `README.md`: Arquitetura ASCII, matemática cosseno, tabela comparativa embeddings, quickstart, configuração, troubleshooting, estrutura, segurança, métricas
- `docs/embedding-benchmark.md`: Benchmark gerado (placeholder - provedores indisponíveis no ambiente)

---

## 12. Nível de Documentação

**essencial** — Artefatos principais (code-analysis, domain, architecture, specs SDD). Para documentação completa com C4, ERD, ADRs, OpenAPI e matrizes, use nível `completo` ou `detalhado`.