# Dependências do Projeto: AnchorRAG

> Gerado pelo Reversa Scout em 2026-09-30
> Nível de documentação: **essencial**

---

## 1. Dependências Core (Produção)

| Pacote | Versão Mínima | Licença | Propósito | Local de Uso |
|--------|---------------|---------|-----------|--------------|
| `pdfplumber` | >=0.11.0 | MIT | Parser PDF rico (extração texto + tabelas) | `src/anchor_rag/ingestion/parser.py` |
| `pypdf` | >=5.0.0 | BSD-3 | Parser PDF leve (fallback) | `src/anchor_rag/ingestion/parser.py` |
| `tiktoken` | >=0.7.0 | MIT | Tokenização (cl100k_base) + contagem tokens | `src/anchor_rag/utils/text.py`, `src/anchor_rag/ingestion/chunker.py` |
| `numpy` | >=1.26.0 | BSD-3 | Arrays numéricos, serialização embeddings | `src/anchor_rag/vector_store/sqlite_vec.py`, `src/anchor_rag/embeddings/*.py` |
| `sqlite-vec` | >=0.1.6 | MIT | Extensão SQLite para busca vetorial nativa | `src/anchor_rag/vector_store/sqlite_vec.py` |
| `httpx` | >=0.27.0 | MIT | Cliente HTTP async (Ollama, APIs) | `src/anchor_rag/embeddings/ollama.py`, `src/anchor_rag/synthesis/ollama_llm.py` |
| `typer` | >=0.12.0 | MIT | Framework CLI (comandos, help, progress) | `src/anchor_rag/cli.py`, `cli_*.py` |
| `pydantic` | >=2.8.0 | MIT | Validação de dados, Settings, modelos | Todo o projeto |
| `pydantic-settings` | >=2.4.0 | MIT | Configuração via YAML + env vars aninhadas | `src/anchor_rag/config.py` |
| `pyyaml` | >=6.0.1 | MIT | Parse/serialize YAML config | `src/anchor_rag/config.py` |
| `tenacity` | >=8.0.0 | Apache-2.0 | Retry exponencial + jitter (OpenAI) | `src/anchor_rag/embeddings/openai.py` |

---

## 2. Dependências Opcionais (Extras)

| Extra | Pacotes | Versão Mínima | Propósito | Local de Uso |
|-------|---------|---------------|-----------|--------------|
| `openai` | `openai` | >=1.35.0 | SDK OpenAI (embeddings + chat) | `src/anchor_rag/embeddings/openai.py`, `src/anchor_rag/synthesis/openai_llm.py` |
| `ollama` | *(nenhum)* | — | HTTP direto para Ollama local | `src/anchor_rag/embeddings/ollama.py`, `src/anchor_rag/synthesis/ollama_llm.py` |
| `huggingface` | `sentence-transformers`, `torch` | >=3.0.0, >=2.3.0 | Embeddings locais via ST | `src/anchor_rag/embeddings/huggingface.py` |
| `anthropic` | `anthropic` | >=0.30.0 | SDK Anthropic (Claude) | `src/anchor_rag/synthesis/anthropic_llm.py` |

---

## 3. Dependências de Desenvolvimento

| Pacote | Versão Mínima | Propósito |
|--------|---------------|-----------|
| `pytest` | >=8.2.0 | Test runner |
| `ruff` | >=0.5.0 | Lint + format (substitui flake8/black/isort) |
| `mypy` | >=1.10.0 | Type checking strict mode |
| `pytest-asyncio` | >=0.23.0 | Suporte a testes async |
| `pytest-cov` | >=5.0.0 | Coverage report |

---

## 4. Configuração de Ferramentas (pyproject.toml)

### Ruff
```toml
[tool.ruff]
target-version = "py311"
line-length = 100
select = ["E", "F", "I", "UP", "W"]
ignore = ["E501"]
extend-ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### MyPy (strict mode)
```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
strict = true
exclude = ["tests/fixtures/"]
```

### Pytest
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
```

---

## 5. Lockfile

**uv.lock** presente — 599KB, gerado por `uv` (resolver rápido, determinístico)

---

## 6. Resumo por Categoria

| Categoria | Count | Exemplos |
|-----------|-------|----------|
| Core (prod) | 11 | pdfplumber, pypdf, tiktoken, numpy, sqlite-vec, httpx, typer, pydantic, pydantic-settings, pyyaml, tenacity |
| Opcionais (extras) | 4 grupos | openai, ollama, huggingface, anthropic |
| Dev | 5 | pytest, ruff, mypy, pytest-asyncio, pytest-cov |
| **Total** | **20+** | — |

---

## 7. Observações

- **Nenhuma dependência obsoleta ou vulnerável conhecida** (versões recentes)
- **Todas as deps core têm licença permissiva** (MIT, BSD-3, Apache-2.0)
- **Extras permitem instalação mínima**: `pip install anchor-rag` instala só core; `pip install "anchor-rag[openai,anthropic]"` adiciona provedores cloud
- **uv.lock garante reprodutibilidade** — usar `uv sync` em CI