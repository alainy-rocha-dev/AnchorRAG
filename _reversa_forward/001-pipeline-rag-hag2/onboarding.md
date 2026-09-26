# Onboarding: Implementação inicial do Projeto HAG 2 (Pipeline RAG)

> Feature: `001-pipeline-rag-hag2`
> Data: `2026-09-22`
> Público: Engenheiro(a) de IA / Dev Backend testando a feature pela primeira vez

## 1. Pré-requisitos

- **Python 3.11+** (recomendado 3.11 ou 3.12)
- **Git**
- **Opcional:** [Ollama](https://ollama.ai/) instalado para modelos locais (embeddings + LLM)
- **Opcional:** Chave API OpenAI (`OPENAI_API_KEY` no ambiente) para modelos cloud

## 2. Instalação rápida (dev)

```bash
# Clone e entre no diretório
git clone <repo-url>
cd hag-rag

# Crie venv e instale em modo editável
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Verifique instalação
hag-rag --help
```

## 3. Configuração

Copie o arquivo de exemplo e ajuste:

```bash
cp config.example.yaml config.yaml
# Edite config.yaml com seu editor
```

**`config.yaml` mínimo para começar (local com Ollama):**

```yaml
embedding:
  provider: "ollama"
  model: "nomic-embed-text"
  # dimensions: 768  # auto-detectado

llm:
  provider: "ollama"
  model: "llama3.1:8b"
  temperature: 0.0
  timeout: 5.0

chunking:
  chunk_size: 1000
  chunk_overlap: 200
  chunk_unit: "chars"  # ou "tokens"

vector_store:
  path: "./data/hag_rag.db"  # SQLite file

logging:
  level: "INFO"
  format: "json"
```

**Para OpenAI (cloud):**

```yaml
embedding:
  provider: "openai"
  model: "text-embedding-3-small"
  api_key: "${OPENAI_API_KEY}"  # lê do env

llm:
  provider: "openai"
  model: "gpt-4o-mini"
  api_key: "${OPENAI_API_KEY}"
  temperature: 0.0
```

## 4. Preparar documentos de teste

```bash
# Crie pasta de docs e coloque PDFs
mkdir -p ./docs
cp /caminho/para/seus/pdfs/*.pdf ./docs/

# Ou use PDFs de exemplo (download automático)
hag-rag download-samples --out ./docs
```

## 5. Primeira ingestão (indexar PDFs)

```bash
# Indexa todos os PDFs em ./docs
hag-rag ingest ./docs

# Saída esperada:
# 📄 Processando: manual_tecnico.pdf (15 páginas)
# ✂️  Chunking: 47 chunks gerados (chars, size=1000, overlap=200)
# 🔮 Gerando embeddings... [47/47]
# 💾 Salvando no vector store...
# ✅ Concluído em 12.3s — 47 chunks indexados
```

**Opções úteis:**

```bash
# Apenas um arquivo
hag-rag ingest ./docs/manual.pdf

# Forçar reindexar (ignora hash)
hag-rag ingest ./docs --force

# Config customizado inline
hag-rag ingest ./docs --chunk-size 500 --chunk-overlap 100 --chunk-unit tokens
```

## 6. Primeira consulta

```bash
# Consulta simples
hag-rag query "Como configurar o parâmetro de timeout?"

# Saída esperada:
# 🔍 Buscando top-3...
# 📊 Scores: [0.87, 0.72, 0.65]
# 🤖 Sintetizando com gpt-4o-mini...
#
# 💬 Resposta:
# O parâmetro de timeout é configurado na seção [network] do arquivo config.yaml
# com o nome 'timeout_seconds' [1]. O valor padrão é 30 segundos [2].
#
# 📚 Fontes:
# [1] manual_tecnico.pdf - Pág. 12 - score: 0.87
# [2] manual_tecnico.pdf - Pág. 13 - score: 0.72
#
# ⏱️ Latência total: 1.23s
```

**Opções úteis:**

```bash
# Mais resultados
hag-rag query "Como configurar..." --top-k 5

# Ajustar threshold de similaridade
hag-rag query "..." --threshold 0.50

# Modelo LLM diferente (se configurado)
hag-rag query "..." --llm-model llama3.1:8b

# Output JSON (para integração)
hag-rag query "..." --format json
```

## 7. Avaliação (eval)

```bash
# Roda suite de avaliação com gold set embutido
hag-rag eval

# Saída:
# 📊 Recall@3: 87.5%
# 📊 MRR: 0.78
# ⏱️ Latência P95: 1.45s
# 🎯 Alucinação: 0/20 (0%)
# 📝 Citação coverage: 100%
```

## 8. Estrutura do projeto (para navegar no código)

```
hag-rag/
├── pyproject.toml           # Config projeto, deps, entry-points
├── config.example.yaml      # Template de config
├── config.yaml              # Sua config local (gitignored)
├── data/                    # SQLite DB (gitignored)
│   └── hag_rag.db
├── docs/                    # PDFs de entrada (gitignored)
├── src/
│   └── hag_rag/
│       ├── __init__.py
│       ├── cli.py           # Typer commands: ingest, query, eval
│       ├── config.py        # Pydantic Settings
│       ├── domain/
│       │   ├── models.py    # Document, Chunk, QueryResult, configs
│       │   └── exceptions.py
│       ├── ingestion/
│       │   ├── parser.py    # pdfplumber + pypdf fallback
│       │   ├── sanitizer.py
│       │   └── chunker.py   # Fixed-size + overlap (chars/tokens)
│       ├── embeddings/
│       │   ├── base.py      # EmbeddingProvider (ABC)
│       │   ├── openai.py
│       │   ├── ollama.py
│       │   └── huggingface.py
│       ├── vector_store/
│       │   ├── base.py      # VectorStore (ABC)
│       │   └── sqlite_vec.py # SQLite + sqlite-vec implementation
│       ├── synthesis/
│       │   ├── prompt.py    # System prompt com ancoragem estrita
│       │   └── synthesizer.py # RAGSynthesizer
│       └── evaluation/
│           ├── gold_set.py  # Queries + expected chunks
│           └── metrics.py   # Recall@k, MRR, latency
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│       └── sample.pdf
└── README.md                # Com matemática de cosseno + comparativo embeddings
```

## 9. Comandos úteis de desenvolvimento

```bash
# Testes
pytest                    # Todos
pytest -k "unit"         # Apenas unitários
pytest -k "integration"  # Apenas integração
pytest --cov=hag_rag     # Com coverage

# Lint/Typecheck
ruff check src/          # Lint rápido
ruff format src/         # Auto-format
mypy src/                # Type checking

# Build
pip build                # Gera dist/

# Reset completo (limpa DB e reindexa)
rm -rf data/hag_rag.db
hag-rag ingest ./docs --force
```

## 10. Troubleshooting comum

| Problema | Causa provável | Solução |
|----------|----------------|---------|
| `sqlite-vec` falha ao instalar | Rust toolchain ausente (Windows) | `pip install sqlite-vec --no-binary sqlite-vec` ou instalar Rust via `rustup` |
| `ModuleNotFoundError: tiktoken` | Dependency missing | `pip install tiktoken` |
| Embeddings muito lentos | Modelo grande local sem GPU | Usar `nomic-embed-text` (768 dims) ou `bge-small` (384 dims) |
| Latência > 2s | LLM local lento / rede | Reduzir `max_tokens`, usar modelo menor, ou `--llm-model phi3:mini` |
| "Não encontrei informações" | Threshold muito alto / docs não indexados | Baixar `--threshold 0.30` ou reindexar com `--force` |
| Citação `[1]` não aparece | Bug no synthesizer | Verificar logs `DEBUG`; issue no tracker |

## 11. Próximos passos após validar

1. **Adicionar seus PDFs reais** em `./docs` e reindexar
2. **Testar modelos diferentes** editando `config.yaml` (comparativo no README)
3. **Customizar prompt** em `src/hag_rag/synthesis/prompt.py` para seu domínio
4. **Rodar eval completo** e documentar métricas no portfólio
5. **Opcional:** Expor como API FastAPI (`hag-rag serve` — futuro)

## 12. Suporte

- **Issues:** GitHub Issues do repositório
- **Docs:** README.md (matemática, comparativo, arquitetura)
- **Logs:** `hag-rag query "..." --verbose` para debug detalhado