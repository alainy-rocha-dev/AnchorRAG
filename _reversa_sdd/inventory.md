# Inventário do Projeto: HAG RAG (Projeto HAG 2)

> Gerado pelo Reversa Scout em 2026-09-22
> Projeto: rag
> Pasta raiz: `C:\rag`

---

## 1. Estrutura de Pastas (excluindo internos)

```
rag/
├── .github/
│   └── workflows/
│       └── ci.yml                    # GitHub Actions CI
├── .reversa/                         # Configuração e estado do Reversa (interno)
├── _reversa_forward/                 # Features do ciclo forward (interno)
├── _reversa_sdd/                     # Especificações geradas (interno)
├── .agents/                          # Skills do Reversa (interno)
├── .claude/                          # Skills do Reversa (interno)
├── src/
│   └── hag_rag/
│       ├── __init__.py               # Package root, version 0.1.0
│       ├── cli.py                    # CLI principal (Typer)
│       ├── cli_eval.py               # Comando eval
│       ├── cli_ingest.py             # Comando ingest
│       ├── cli_query.py              # Comando query
│       ├── config.py                 # Configuração Pydantic Settings
│       ├── logging.py                # Logging estruturado JSON
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── models.py             # Document, Chunk, QueryResult, configs
│       │   └── exceptions.py         # Exceções customizadas
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── parser.py             # PDFParser + PdfPlumberParser + PyPDFParser
│       │   ├── chunker.py            # Chunker tokens/chars + overlap
│       │   └── pipeline.py           # IngestionPipeline orquestrador
│       ├── embeddings/
│       │   ├── __init__.py           # Factory create_embedding_provider
│       │   ├── base.py               # EmbeddingProvider ABC
│       │   ├── openai.py             # OpenAIEmbeddingProvider
│       │   ├── ollama.py             # OllamaEmbeddingProvider
│       │   └── huggingface.py        # HuggingFaceEmbeddingProvider
│       ├── vector_store/
│       │   ├── __init__.py           # Factory create_vector_store
│       │   ├── base.py               # VectorStore ABC
│       │   └── sqlite_vec.py         # SQLiteVecStore (sqlite-vec)
│       ├── synthesis/
│       │   ├── __init__.py           # Factory create_llm_provider
│       │   ├── llm.py                # LLMProvider ABC + config/response
│       │   ├── openai_llm.py         # OpenAILLMProvider
│       │   ├── ollama_llm.py         # OllamaLLMProvider
│       │   ├── anthropic_llm.py      # AnthropicLLMProvider
│       │   ├── prompt.py             # Ancoragem estrita + few-shot defense
│       │   └── synthesizer.py        # RAGSynthesizer + citações [N]
│       ├── pipeline/
│       │   ├── __init__.py
│       │   └── orchestrator.py       # RAGPipeline (ingest/query/eval)
│       └── utils/
│           ├── __init__.py
│           └── text.py               # Hash, sanitize, tokens, chunking
├── tests/
│   ├── fixtures/
│   │   ├── sample_text.txt
│   │   ├── table_text.txt
│   │   └── corrupted_text.txt
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_embedding_provider_contract.py
│   │   ├── test_llm_provider_contract.py
│   │   ├── test_models.py
│   │   ├── test_text_utils.py
│   │   └── test_vector_store_contract.py
│   └── integration/
│       ├── test_e2e.py
│       ├── test_ingestion_pipeline.py
│       ├── test_prompt_injection.py
│       └── test_query_pipeline.py
├── AGENTS.md                         # Instruções para agentes
├── CLAUDE.md                         # Instruções para Claude
├── config.example.yaml               # Template de configuração
├── pyproject.toml                    # Configuração do projeto (PEP 621)
├── README.md                         # Documentação completa
├── Relatorio_Portfolio_Agentes_IA.pdf # Relatório de referência
└── WhatsApp Image 2026-09-21 at 16.36.10 (1).jpeg # Imagem de referência
```

---

## 2. Linguagens e Contagem de Arquivos

| Linguagem | Arquivos | Linhas (estimado) | % do código |
|-----------|----------|-------------------|-------------|
| Python    | 42       | ~6.500            | 95%         |
| YAML      | 1        | ~60               | 1%          |
| TOML      | 1        | ~75               | 1%          |
| Markdown  | 3        | ~400              | 3%          |
| **Total** | **47**   | **~7.000**        | **100%**    |

> Contagem exclui: `.reversa/`, `_reversa_sdd/`, `_reversa_forward/`, `.agents/`, `.claude/`

---

## 3. Módulos Identificados (src/hag_rag/)

| Módulo | Arquivos | Responsabilidade |
|--------|----------|------------------|
| `hag_rag` (root) | 1 | Package entry, version |
| `hag_rag.config` | 1 | Configuração centralizada (Pydantic Settings) |
| `hag_rag.logging` | 1 | Logging JSON estruturado + request_id |
| `hag_rag.domain` | 2 | Modelos de domínio + exceções |
| `hag_rag.utils` | 1 | Utilitários de texto (hash, sanitize, chunking, tokens) |
| `hag_rag.ingestion` | 3 | Parser PDF, Chunker, Pipeline de ingestão |
| `hag_rag.embeddings` | 5 | ABC + 3 provedores (OpenAI, Ollama, HF) + factory |
| `hag_rag.vector_store` | 3 | ABC + SQLiteVecStore + factory |
| `hag_rag.synthesis` | 6 | ABC + 3 provedores LLM + prompt + synthesizer |
| `hag_rag.pipeline` | 1 | Orquestrador RAGPipeline |
| **CLI** | 4 | Typer app + comandos (ingest, query, eval) |
| **Total** | **31** | |

---

## 4. Pontos de Entrada

| Tipo | Arquivo/Caminho | Descrição |
|------|-----------------|-----------|
| **CLI Principal** | `src/hag_rag/cli.py` | Typer app: `hag-rag ingest|query|eval` |
| **Configuração** | `config.example.yaml` | Template YAML com todas as seções |
| **Build/Install** | `pyproject.toml` | PEP 621, entry point `hag-rag = hag_rag.cli:app` |
| **CI/CD** | `.github/workflows/ci.yml` | Matrix Python 3.11/3.12, ruff, mypy, pytest, build |
| **Testes** | `pytest` | `tests/` unit + integration, fixtures |

---

## 5. Tecnologias e Frameworks Principais

| Categoria | Tecnologia | Versão/Detalhe |
|-----------|------------|----------------|
| **Linguagem** | Python | >=3.11 (3.11, 3.12 no CI) |
| **Configuração** | Pydantic Settings | v2.8+ |
| **CLI** | Typer | v0.12+ |
| **PDF Parsing** | pdfplumber | v0.11+ (primário, tabelas) |
| | PyPDF | v5.0+ (fallback) |
| **Tokenização** | tiktoken | v0.7+ (cl100k_base) |
| **Embeddings** | OpenAI API | text-embedding-3-small/large |
| | Ollama HTTP | /api/embed (local) |
| | sentence-transformers | all-MiniLM-L6-v2, bge-m3, etc. |
| **Vector Store** | sqlite-vec | v0.1.6+ (extensão SQLite) |
| **HTTP Client** | httpx | v0.27+ (async) |
| **LLM Providers** | OpenAI SDK | v1.35+ (streaming, tokens) |
| | Ollama HTTP | /api/chat (streaming SSE) |
| | Anthropic SDK | v0.30+ |
| **Testes** | pytest | v8.2+ (asyncio, cov) |
| **Lint/Format** | ruff | v0.5+ (check, format) |
| **Type Check** | mypy | v1.10+ (strict) |
| **Logging** | python-json-logger | JSON estruturado |

---

## 6. Dependências Críticas (pyproject.toml)

### Core (obrigatórias)
- `pdfplumber>=0.11.0` — Parsing PDF com tabelas
- `pypdf>=5.0.0` — Parsing PDF fallback
- `tiktoken>=0.7.0` — Contagem tokens OpenAI
- `numpy>=1.26.0` — Operações vetoriais (busca cosseno)
- `sqlite-vec>=0.1.6` — Extensão vetorial SQLite
- `httpx>=0.27.0` — Cliente HTTP async
- `typer>=0.12.0` — CLI framework
- `pydantic>=2.8.0` — Validação + Settings
- `pydantic-settings>=2.4.0` — Configuração por env/YAML
- `pyyaml>=6.0.1` — Parse YAML config

### Opcionais (extras)
- `openai>=1.35.0` — Provider OpenAI
- `sentence-transformers>=3.0.0` + `torch>=2.3.0` — Provider HuggingFace
- `anthropic>=0.30.0` — Provider Anthropic
- Ollama — Sem dependência Python (HTTP apenas)

### Dev
- `pytest>=8.2.0`, `pytest-asyncio>=0.23.0`, `pytest-cov>=5.0.0`
- `ruff>=0.5.0` — Lint + format
- `mypy>=1.10.0` — Type checking strict

---

## 7. Cobertura de Testes

| Tipo | Arquivos | Framework |
|------|----------|-----------|
| **Unitários** | 6 | pytest |
| `test_config.py` | Config loading, validation, env vars |
| `test_models.py` | Pydantic models (Document, Chunk, QueryResult) |
| `test_text_utils.py` | Hash, sanitize, chunking, tokens |
| `test_embedding_provider_contract.py` | ABC EmbeddingProvider (mock) |
| `test_llm_provider_contract.py` | ABC LLMProvider (mock) |
| `test_vector_store_contract.py` | ABC VectorStore (mock) |
| **Integração** | 4 | pytest-asyncio |
| `test_ingestion_pipeline.py` | Parser → Chunker → Embeddings → VectorStore |
| `test_query_pipeline.py` | Embedding → Search → Synthesize |
| `test_e2e.py` | Ingest real → Query real → Valida resposta |
| `test_prompt_injection.py` | 10 prompts adversariais |
| **Fixtures** | 3 arquivos texto | Sintéticos para testes |

---

## 8. Banco de Dados (superficial)

| Arquivo | Tipo | Status |
|---------|------|--------|
| `src/hag_rag/vector_store/sqlite_vec.py` | DDL + Virtual Table `chunks_vec` | Implementado |
| `config.example.yaml` → `vector_store.path` | `./data/hag_rag.db` | Configurável |
| `query_log.enabled` | Tabela `query_log` opcional | Implementado (desabilitado por padrão) |

> Análise detalhada ficará a cargo do `reversa-data-master` se solicitado.

---

## 9. Sugestão de Organização das Specs

```json
{
  "granularity": "module",
  "rationale": "Estrutura top-level em src/hag_rag/ segue domínio funcional (config, domain, ingestion, embeddings, vector_store, synthesis, pipeline, utils, logging, cli)",
  "signals": [
    {
      "type": "top_level_domain_folders",
      "evidence": [
        "src/hag_rag/config.py",
        "src/hag_rag/domain/",
        "src/hag_rag/ingestion/",
        "src/hag_rag/embeddings/",
        "src/hag_rag/vector_store/",
        "src/hag_rag/synthesis/",
        "src/hag_rag/pipeline/",
        "src/hag_rag/utils/",
        "src/hag_rag/logging.py",
        "src/hag_rag/cli*.py"
      ]
    }
  ]
}
```

> **Heurística aplicada**: "Pastas top-level com nomes de domínio" — as pastas `ingestion/`, `embeddings/`, `vector_store/`, `synthesis/`, `pipeline/`, `domain/`, `utils/` são nomes de domínio funcional claros.

---

## 10. Resumo para Próximos Agentes

- **Projeto**: `rag` — Pipeline RAG completo (HAG 2)
- **Linguagem principal**: Python 3.11+
- **Framework principal**: Typer (CLI) + Pydantic (config) + sqlite-vec (vector store)
- **Módulos identificados**: 10 módulos funcionais + 4 CLI
- **Integrações externas**: OpenAI API, Ollama (local), Anthropic API, HuggingFace (local)
- **Banco de dados**: SQLite com sqlite-vec (presente, configurável)
- **Testes**: 10 arquivos (6 unit + 4 integration) com mocks ABC
- **Nível de documentação**: `completo` (conforme state.json)
- **Organização specs sugerida**: `module` (por domínio funcional)