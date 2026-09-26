# Dependências do Projeto: HAG RAG

> Gerado pelo Reversa Scout em 2026-09-22
> Fonte: `pyproject.toml` + análise de imports

---

## 1. Dependências Core (Obrigatórias)

| Pacote | Versão Mínima | Versão Atual (lock) | Propósito | Categoria |
|--------|---------------|---------------------|-----------|-----------|
| `pdfplumber` | >=0.11.0 | - | Parsing PDF com extração de tabelas | PDF Processing |
| `pypdf` | >=5.0.0 | - | Parsing PDF fallback (leve) | PDF Processing |
| `tiktoken` | >=0.7.0 | - | Tokenização OpenAI (cl100k_base) | NLP/Tokenization |
| `numpy` | >=1.26.0 | - | Operações vetoriais, busca cosseno | Math/Vector |
| `sqlite-vec` | >=0.1.6 | - | Extensão vetorial SQLite (virtual table) | Database/Vector |
| `httpx` | >=0.27.0 | - | Cliente HTTP assíncrono (Ollama, APIs) | HTTP Client |
| `typer` | >=0.12.0 | - | Framework CLI moderno | CLI |
| `pydantic` | >=2.8.0 | - | Validação de dados, models | Validation |
| `pydantic-settings` | >=2.4.0 | - | Configuração por env/YAML | Configuration |
| `pyyaml` | >=6.0.1 | - | Parse YAML config files | Configuration |

---

## 2. Dependências Opcionais (Extras)

| Extra | Pacotes | Versão Mínima | Propósito |
|-------|---------|---------------|-----------|
| `openai` | `openai` | >=1.35.0 | Provider OpenAI (embeddings + LLM) |
| `ollama` | *(nenhum)* | - | Provider Ollama via HTTP nativo |
| `huggingface` | `sentence-transformers` | >=3.0.0 | Provider HF local (embeddings) |
| | `torch` | >=2.3.0 | Backend PyTorch para sentence-transformers |
| `anthropic` | `anthropic` | >=0.30.0 | Provider Anthropic (LLM) |

---

## 3. Dependências de Desenvolvimento

| Pacote | Versão Mínima | Propósito |
|--------|---------------|-----------|
| `pytest` | >=8.2.0 | Test runner |
| `pytest-asyncio` | >=0.23.0 | Testes async |
| `pytest-cov` | >=5.0.0 | Coverage report |
| `ruff` | >=0.5.0 | Lint + format (substitui flake8, black, isort) |
| `mypy` | >=1.10.0 | Type checking strict |

---

## 4. Análise de Imports por Módulo

### `src/hag_rag/config.py`
```python
pydantic, pydantic_settings, yaml, pathlib, typing
```

### `src/hag_rag/domain/models.py`
```python
pydantic, enum, typing, uuid, datetime
```

### `src/hag_rag/domain/exceptions.py`
```python
typing  # apenas stdlib
```

### `src/hag_rag/utils/text.py`
```python
hashlib, re, unicodedata, tiktoken, uuid, typing
```

### `src/hag_rag/ingestion/parser.py`
```python
pdfplumber, pypdf, abc, dataclasses, pathlib, typing, logging
```

### `src/hag_rag/ingestion/chunker.py`
```python
tiktoken, dataclasses, typing, uuid
# imports locais: hag_rag.utils.text, hag_rag.domain.models
```

### `src/hag_rag/ingestion/pipeline.py`
```python
asyncio, dataclasses, pathlib, typing, uuid, time, logging
# imports locais: hag_rag.domain, hag_rag.ingestion, hag_rag.embeddings, hag_rag.vector_store
```

### `src/hag_rag/embeddings/base.py`
```python
abc, typing, pydantic, dataclasses
```

### `src/hag_rag/embeddings/openai.py`
```python
openai, tenacity, typing, logging
# imports locais: hag_rag.embeddings.base
```

### `src/hag_rag/embeddings/ollama.py`
```python
httpx, typing, logging
# imports locais: hag_rag.embeddings.base
```

### `src/hag_rag/embeddings/huggingface.py`
```python
sentence_transformers, typing, logging
# imports locais: hag_rag.embeddings.base
```

### `src/hag_rag/embeddings/__init__.py`
```python
typing, logging
# imports locais: .base, .openai, .ollama, .huggingface
```

### `src/hag_rag/vector_store/base.py`
```python
abc, typing, dataclasses, uuid
```

### `src/hag_rag/vector_store/sqlite_vec.py`
```python
sqlite3, sqlite_vec, numpy, json, logging, pathlib, typing, uuid
# imports locais: hag_rag.vector_store.base
```

### `src/hag_rag/vector_store/__init__.py`
```python
typing, logging
# imports locais: .base, .sqlite_vec
```

### `src/hag_rag/synthesis/llm.py`
```python
abc, typing, pydantic, dataclasses
```

### `src/hag_rag/synthesis/openai_llm.py`
```python
openai, tenacity, tiktoken, typing, logging
# imports locais: hag_rag.synthesis.llm
```

### `src/hag_rag/synthesis/ollama_llm.py`
```python
httpx, json, typing, logging
# imports locais: hag_rag.synthesis.llm
```

### `src/hag_rag/synthesis/anthropic_llm.py`
```python
anthropic, typing, logging
# imports locais: hag_rag.synthesis.llm
```

### `src/hag_rag/synthesis/prompt.py`
```python
typing, dataclasses
```

### `src/hag_rag/synthesis/synthesizer.py`
```python
re, time, dataclasses, typing, logging
# imports locais: hag_rag.synthesis.llm, hag_rag.synthesis.prompt, hag_rag.domain.models
```

### `src/hag_rag/synthesis/__init__.py`
```python
typing, logging
# imports locais: .llm, .openai_llm, .ollama_llm, .anthropic_llm
```

### `src/hag_rag/pipeline/orchestrator.py`
```python
typing, pathlib, logging, time
# imports locais: hag_rag.config, hag_rag.ingestion, hag_rag.embeddings, hag_rag.vector_store, hag_rag.synthesis
```

### `src/hag_rag/logging.py`
```python
logging, json, sys, uuid, contextvars, typing, datetime
# python-json-logger (via extra ou import opcional)
```

### `src/hag_rag/cli.py`
```python
typer, typing, pathlib
# imports locais: .cli_ingest, .cli_query, .cli_eval
```

### `src/hag_rag/cli_ingest.py`
```python
typer, asyncio, pathlib, rich, typing
# imports locais: hag_rag.pipeline, hag_rag.config, hag_rag.ingestion, hag_rag.domain
```

### `src/hag_rag/cli_query.py`
```python
typer, asyncio, pathlib, rich, typing
# imports locais: hag_rag.pipeline, hag_rag.config, hag_rag.domain
```

### `src/hag_rag/cli_eval.py`
```python
typer, asyncio, pathlib, rich, typing, json
# imports locais: hag_rag.pipeline, hag_rag.config
```

---

## 5. Mapa de Dependências Internas (Módulos)

```
hag_rag (root)
├── config          ← Pydantic Settings (base)
├── domain          ← Models + Exceptions (base)
│   ├── models.py
│   └── exceptions.py
├── utils           ← Text utilities (base)
│   └── text.py
├── logging         ← Structured logging (base)
│   └── logging.py
├── ingestion       ← Depende: domain, utils
│   ├── parser.py
│   ├── chunker.py
│   └── pipeline.py  ← Depende: embeddings, vector_store
├── embeddings      ← Depende: domain (config)
│   ├── base.py
│   ├── openai.py
│   ├── ollama.py
│   ├── huggingface.py
│   └── __init__.py  ← Factory
├── vector_store    ← Depende: domain
│   ├── base.py
│   ├── sqlite_vec.py
│   └── __init__.py  ← Factory
├── synthesis       ← Depende: domain
│   ├── llm.py
│   ├── openai_llm.py
│   ├── ollama_llm.py
│   ├── anthropic_llm.py
│   ├── prompt.py
│   ├── synthesizer.py
│   └── __init__.py  ← Factory
├── pipeline        ← Depende: ingestion, embeddings, vector_store, synthesis
│   └── orchestrator.py
└── cli*            ← Depende: pipeline, config, domain
    ├── cli.py
    ├── cli_ingest.py
    ├── cli_query.py
    └── cli_eval.py
```

---

## 6. Dependências Externas (Serviços)

| Serviço | Tipo | Configuração | Uso |
|---------|------|--------------|-----|
| **OpenAI API** | Cloud (pago) | `OPENAI_API_KEY` env | Embeddings (text-embedding-3-*), LLM (gpt-4o-mini) |
| **Ollama** | Local (gratuito) | `base_url` (default localhost:11434) | Embeddings (nomic-embed-text), LLM (llama3.1:8b) |
| **Anthropic API** | Cloud (pago) | `ANTHROPIC_API_KEY` env | LLM (claude-3-haiku) |
| **HuggingFace** | Local (gratuito) | Modelos via `sentence-transformers` | Embeddings (all-MiniLM-L6-v2, bge-m3) |

---

## 7. Versões de Python Suportadas

| Versão | Status | CI Matrix |
|--------|--------|-----------|
| 3.11 | ✅ Suportado | ✅ Testado |
| 3.12 | ✅ Suportado | ✅ Testado |
| 3.13+ | ❓ Não testado | ❌ Não no CI |

> `requires-python = ">=3.11"` no pyproject.toml

---

## 8. Observações de Compatibilidade

1. **sqlite-vec** requer SQLite com extensões habilitadas (`enable_load_extension`). Funciona em Linux/macOS/Windows (via wheels).

2. **sentence-transformers** + **torch** são pesados (~1GB+). Instalados apenas com extra `huggingface`.

3. **OpenAI SDK v1.x** usa interface nova (`AsyncOpenAI`, `chat.completions.create`). Incompatível com v0.x.

4. **Pydantic v2** usa `model_config` e `field_validator` (v1 usava `Config` class e `validator`).

5. **Typer** usa `Annotated` + `typer.Option` para CLI rico.

6. **ruff** configura `target-version = "py311"` — código pode usar `typing.Self`, `tomllib` (3.11+), `Exception.add_note()` (3.11+).

---

## 9. Lock File (Referência)

> Não há `uv.lock` ou `poetry.lock` — projeto usa `pip` + `pyproject.toml` direto.
> Para gerar lock: `pip compile pyproject.toml -o requirements.lock` (com `pip-tools`) ou `uv pip compile`.