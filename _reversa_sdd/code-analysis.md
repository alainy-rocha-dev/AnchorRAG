# Análise de Código: HAG RAG (Projeto HAG 2)

> Gerado pelo Reversa Archaeologist em 2026-09-22
> Nível de documentação: **essencial**
> Módulos analisados: 1/10 (config)

---

## 1. Módulo `config` — Configuração Centralizada (Pydantic Settings)

### 1.1 Visão Geral
Arquivo: `src/hag_rag/config.py` (137 linhas)
Responsabilidade: Configuração tipada, validada e hierárquica via Pydantic Settings v2, com suporte a YAML, variáveis de ambiente aninhadas e resolução de API keys.

### 1.2 Classes de Configuração (Estrutura de Dados)

| Classe | Campos Principais | Validações | Prefixo Env |
|--------|------------------|------------|-------------|
| `EmbeddingConfig` | provider, model, dimensions, batch_size, api_key_env, base_url | dimensions > 0 | `EMBEDDING_` |
| `LLMConfig` | provider, model, temperature, max_tokens, timeout, api_key_env, base_url | 0 ≤ temperature ≤ 2 | `LLM_` |
| `ChunkingConfig` | chunk_size, chunk_overlap, chunk_unit, min_chunk_size | chunk_overlap < chunk_size | `CHUNKING_` |
| `VectorStoreConfig` | type, path, embedding_dimensions | — | `VECTOR_STORE_` |
| `LoggingConfig` | level, format, output, include_request_id | — | `LOGGING_` |
| `QueryLogConfig` | enabled, path | — | `QUERY_LOG_` |
| `AppConfig` | embedding, llm, chunking, vector_store, logging, query_log | — | (raiz + `__`) |

### 1.3 Fluxos de Controle e Algoritmos

#### `AppConfig.from_yaml(path)` — Carregamento YAML
```python
@classmethod
def from_yaml(cls, path: str | Path) -> "AppConfig":
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return cls(**data)
```
- **Entrada**: caminho para arquivo YAML
- **Processamento**: `yaml.safe_load` + instância direta via `cls(**data)`
- **Saída**: `AppConfig` validado
- **Tratamento de erro**: `FileNotFoundError`, `yaml.YAMLError` propagam (não capturados)

#### `AppConfig.resolve_api_keys()` — Resolução de Secrets
```python
def resolve_api_keys(self) -> "AppConfig":
    import os
    def resolve(env_var: str) -> Optional[str]:
        return os.getenv(env_var)
    config_dict = self.model_dump()
    for section in ["embedding", "llm"]:
        env_key = config_dict[section].get("api_key_env")
        if env_key:
            config_dict[section]["api_key"] = resolve(env_key)
    return self.model_validate(config_dict)
```
- **Algoritmo**: Itera sobre seções `embedding` e `llm`, lê `api_key_env`, busca no `os.environ`, injeta `api_key` no dict, revalida
- **Padrão**: Immutable — retorna nova instância validada
- **Segurança**: Não loga valores; apenas injeta em memória

### 1.4 Validações de Domínio (field_validator)

| Validador | Classe | Regra | Confiança |
|-----------|--------|-------|-----------|
| `validate_dimensions` | `EmbeddingConfig` | `dimensions > 0` | 🟢 CONFIRMADO |
| `validate_temperature` | `LLMConfig` | `0 ≤ temperature ≤ 2` | 🟢 CONFIRMADO |
| `validate_overlap` | `ChunkingConfig` | `chunk_overlap < chunk_size` | 🟢 CONFIRMADO |

> Usa `field_validator` com `mode="after"` (padrão Pydantic v2). Validação cross-field no `chunk_overlap` via `info.data`.

### 1.5 Constantes e Enums de Domínio

| Enum/Constante | Valores | Uso |
|----------------|---------|-----|
| `Literal["openai", "ollama", "huggingface"]` | 3 provedores embedding | `EmbeddingConfig.provider` |
| `Literal["openai", "ollama", "anthropic"]` | 3 provedores LLM | `LLMConfig.provider` |
| `Literal["chars", "tokens"]` | 2 unidades chunking | `ChunkingConfig.chunk_unit` |
| `Literal["sqlite_vec"]` | 1 tipo vector store | `VectorStoreConfig.type` |
| `Literal["DEBUG", "INFO", "WARNING", "ERROR"]` | 4 níveis log | `LoggingConfig.level` |
| `Literal["json", "text"]` | 2 formatos log | `LoggingConfig.format` |

### 1.6 Configuração Pydantic Settings (model_config)

```python
# Classes filhas (EmbeddingConfig, LLMConfig, etc.)
model_config = SettingsConfigDict(env_prefix="PREFIXO_", extra="ignore")

# AppConfig (raiz)
model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    env_nested_delimiter="__",  # ex: EMBEDDING__MODEL
    extra="ignore",
)
```
- **Herança**: Configurações filhas usam prefixo próprio; `AppConfig` agrega via `Field(default_factory=...)`
- **Delimiter aninhado**: `__` permite `EMBEDDING__MODEL=text-embedding-3-large` no `.env`
- **Extra ignore**: Ignora chaves desconhecidas no YAML/env (resiliente a evolução)

### 1.7 Dicionário de Dados (Resumo — doc_level=essencial)

| Entidade | Campo | Tipo | Obrigatório | Default | Validação |
|----------|-------|------|-------------|---------|-----------|
| `EmbeddingConfig` | provider | str | Sim | "openai" | ∈ {openai,ollama,huggingface} |
| | model | str | Sim | "text-embedding-3-small" | — |
| | dimensions | int | Sim | 1536 | > 0 |
| | batch_size | int | Sim | 100 | — |
| | api_key_env | str | Sim | "OPENAI_API_KEY" | — |
| | base_url | str? | Não | None | — |
| `LLMConfig` | provider | str | Sim | "openai" | ∈ {openai,ollama,anthropic} |
| | model | str | Sim | "gpt-4o-mini" | — |
| | temperature | float | Sim | 0.1 | [0, 2] |
| | max_tokens | int | Sim | 2048 | — |
| | timeout | int | Sim | 30 | — |
| | api_key_env | str | Sim | "OPENAI_API_KEY" | — |
| | base_url | str? | Não | None | — |
| `ChunkingConfig` | chunk_size | int | Sim | 512 | — |
| | chunk_overlap | int | Sim | 50 | < chunk_size |
| | chunk_unit | str | Sim | "tokens" | ∈ {chars, tokens} |
| | min_chunk_size | int | Sim | 50 | — |
| `VectorStoreConfig` | type | str | Sim | "sqlite_vec" | = "sqlite_vec" |
| | path | str | Sim | "./data/hag_rag.db" | — |
| | embedding_dimensions | int | Sim | 1536 | — |
| `LoggingConfig` | level | str | Sim | "INFO" | ∈ {DEBUG,INFO,WARNING,ERROR} |
| | format | str | Sim | "json" | ∈ {json,text} |
| | output | str | Sim | "stdout" | — |
| | include_request_id | bool | Sim | True | — |
| `QueryLogConfig` | enabled | bool | Sim | False | — |
| | path | str | Sim | "./data/query_log.db" | — |
| `AppConfig` | embedding | EmbeddingConfig | Sim | factory | — |
| | llm | LLMConfig | Sim | factory | — |
| | chunking | ChunkingConfig | Sim | factory | — |
| | vector_store | VectorStoreConfig | Sim | factory | — |
| | logging | LoggingConfig | Sim | factory | — |
| | query_log | QueryLogConfig | Sim | factory | — |

### 1.8 Integração com YAML Exemplo (`config.example.yaml`)

```yaml
embedding:
  provider: "openai"
  model: "text-embedding-3-small"
  dimensions: 1536
  batch_size: 100
  api_key_env: "OPENAI_API_KEY"
llm:
  provider: "openai"
  model: "gpt-4o-mini"
  temperature: 0.1
  max_tokens: 2048
chunking:
  chunk_size: 512
  chunk_overlap: 50
  chunk_unit: "tokens"
vector_store:
  type: "sqlite_vec"
  path: "./data/hag_rag.db"
  embedding_dimensions: 1536
logging:
  level: "INFO"
  format: "json"
  output: "stdout"
query_log:
  enabled: false
```

### 1.9 Pontos de Atenção / Lacunas

| Item | Severidade | Observação |
|------|------------|------------|
| `resolve_api_keys` não valida se env var existe | 🟡 INFERIDO | Retorna `None` silenciosamente se env var não definida; provedor falhará depois no `health_check` |
| `base_url` opcional mas não validado formato URL | 🟡 INFERIDO | Pode aceitar string inválida; erro só em runtime do HTTP client |
| `vector_store.type` fixo em `sqlite_vec` | 🟡 INFERIDO | Literal com 1 valor; preparado para expansão futura |
| Falta validação `embedding_dimensions` == `dimensions` do provider | 🔴 LACUNA | Inconsistência detectada apenas em runtime (vector store vs embedding) |

---

## 2. Módulo `domain` — Modelos de Domínio e Exceções

> Análise consolidada dos arquivos `src/hag_rag/domain/models.py` (89 linhas) e `src/hag_rag/domain/exceptions.py` (53 linhas).

### 2.1 Entidades Principais

#### `Document` — Documento Ingerido
- **Campos**: `id` (UUIDv4), `path`, `filename`, `content_hash` (SHA256 hex 64 chars), `page_count`, `metadata` (dict), `created_at` (datetime UTC)
- **Validação**: `content_hash` deve ter 64 chars hex → normalizado para lowercase
- **Confiança**: 🟢 CONFIRMADO

#### `Chunk` — Trecho de Texto com Metadados
- **Campos**: `id` (UUIDv4), `document_id` (FK), `content`, `chunk_index` (≥0), `page_number` (opcional), `start_char`, `end_char`, `token_count` (opcional), `embedding` (opcional List[float]), `metadata` (dict)
- **Validação**: `chunk_index` não negativo
- **Rastreabilidade**: `document_id` + `chunk_index` + `page_number` + offsets permitem reconstrução exata
- **Confiança**: 🟢 CONFIRMADO

#### `QueryResult` — Resultado da Query RAG
- **Campos**: `answer`, `citations` (List[Dict]), `chunks_used` (List[Chunk]), `scores` (List[float]), `latency_ms` (Dict[str,float]), `metadata` (dict)
- **Latency breakdown**: `embed`, `search`, `synthesize`, `total` (ms)
- **Confiança**: 🟢 CONFIRMADO

#### `IngestConfig` / `QueryConfig` — Configs de Runtime
- Separam configuração de execução (tamanho chunk, parser, top_k, threshold) da configuração de infraestrutura (`AppConfig`)
- **Confiança**: 🟢 CONFIRMADO

### 2.2 Enum `ChunkUnit`
```python
class ChunkUnit(str, Enum):
    CHARS = "chars"
    TOKENS = "tokens"
```
- Usado em `ChunkingConfig.chunk_unit` e `IngestConfig.chunk_unit`
- **Confiança**: 🟢 CONFIRMADO

### 2.3 Hierarquia de Exceções
```
HAGRAGException (base)
├── InvalidDocumentException      # PDF corrompido/vazio
├── EmbeddingGenerationException  # Falha API embedding
├── VectorStoreException          # Erro SQLite/sqlite-vec
├── SynthesisException            # Erro LLM/síntese
├── ConfigurationException        # Config inválida
└── ProviderNotAvailableException # Provedor indisponível
```
- **Base**: Armazena `message` + `details` (dict) → `__str__` inclui details
- **Uso**: Capturadas no pipeline de ingestão e query para logging estruturado
- **Confiança**: 🟢 CONFIRMADO

---

## 3. Módulo `utils.text` — Utilitários de Texto

> Arquivo: `src/hag_rag/utils/text.py` (162 linhas)

### 3.1 Funções Principais

| Função | Assinatura | Algoritmo | Confiança |
|--------|------------|-----------|-----------|
| `sha256_hash` | `(content: bytes) -> str` | `hashlib.sha256().hexdigest()` | 🟢 |
| `sha256_file` | `(path: str) -> str` | Stream 8KB chunks | 🟢 |
| `sanitize_text` | `(text: str) -> str` | Regex + NFKC + hyphen fix | 🟢 |
| `count_chars` | `(text: str) -> int` | `len(text)` | 🟢 |
| `count_tokens` | `(text: str, model="cl100k_base") -> int` | `tiktoken.get_encoding().encode()` | 🟢 |
| `chunk_by_tokens` | `(text, chunk_size, chunk_overlap, model) -> List[str]` | tiktoken encode/decode com overlap | 🟢 |
| `chunk_by_chars` | `(text, chunk_size, chunk_overlap) -> List[str]` | Slicing com overlap | 🟢 |
| `generate_uuid` | `() -> str` | `uuid.uuid4()` | 🟢 |
| `truncate_text` | `(text, max_length, suffix="...") -> str` | Preserva palavras | 🟢 |

### 3.2 Algoritmo `sanitize_text` (Não-Trivial)
```python
def sanitize_text(text: str) -> str:
    # 1. Remove control chars (exceto \n, \t)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    # 2. Normalize unicode NFKC
    text = unicodedata.normalize("NFKC", text)
    # 3. Fix hifenização: "hyphen-\nated" → "hyphenated"
    text = re.sub(r"-\n(\w)", r"\1", text)
    # 4. Colapsa \n{3,} → \n\n
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 5. Strip trailing spaces por linha
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.strip()
```
- **Entrada**: Texto bruto extraído de PDF
- **Saída**: Texto limpo para chunking
- **Confiança**: 🟢 CONFIRMADO

### 3.3 Algoritmo `chunk_by_tokens` (Core do Chunking)
```python
def chunk_by_tokens(text, chunk_size, chunk_overlap, model):
    encoding = tiktoken.get_encoding(model)
    tokens = encoding.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunks.append(encoding.decode(tokens[start:end]))
        if end == len(tokens): break
        start = end - chunk_overlap
        if start < 0: start = 0
    return chunks
```
- **Complexidade**: O(n) tokens
- **Overlap exato**: Últimos `chunk_overlap` tokens do chunk anterior = primeiros do próximo
- **Edge case**: Texto vazio → lista vazia
- **Confiança**: 🟢 CONFIRMADO

---

## 4. Módulo `logging` — Logging Estruturado JSON

> Arquivo: `src/hag_rag/logging.py` (103 linhas)

### 4.1 Componentes

| Componente | Responsabilidade | Confiança |
|------------|------------------|-----------|
| `RequestIdFilter` | Injeta `request_id` (contextvar) nos records | 🟢 |
| `CustomJsonFormatter` | Formato JSON com timestamp, level, logger, request_id | 🟢 |
| `setup_logging` | Configura logger `hag_rag` com handler + formatter | 🟢 |
| `set_request_id` / `clear_request_id` / `LogContext` | Gerenciamento de request_id via contextvar | 🟢 |

### 4.2 Fluxo de Request ID
```python
# Context variable (thread/task-safe)
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

# Uso no CLI (ex: cli_query.py)
with LogContext():  # Gera UUID curto se não passado
    result = await pipeline.query(...)
```
- **Isolamento**: `contextvars` garante isolamento em asyncio
- **Formato JSON**: `{"timestamp": "...", "level": "INFO", "logger": "hag_rag.ingestion", "request_id": "a1b2c3d4", "message": "..."}`
- **Confiança**: 🟢 CONFIRMADO

---

## Resumo de Artefatos Gerados (Módulos 1-4)

| Módulo | Arquivos | Linhas | Principais Descobertas |
|--------|----------|--------|------------------------|
| `config` | 1 | 137 | 7 classes Settings, 3 validadores, YAML + env + API key resolution |
| `domain` | 2 | 142 | 4 modelos (Document, Chunk, QueryResult, configs), 6 exceções, 1 enum |
| `utils.text` | 1 | 162 | 9 funções (hash, sanitize, chunking tokens/chars, tokens counting) |
| `logging` | 1 | 103 | JSON logging, request_id contextvar, CustomJsonFormatter |

**Total até agora**: 5 arquivos, ~544 linhas analisadas

---

## Próximos Módulos (Pendentes)

1. `ingestion` — parser.py, chunker.py, pipeline.py
2. `embeddings` — base.py, openai.py, ollama.py, huggingface.py, __init__.py
3. `vector_store` — base.py, sqlite_vec.py, __init__.py
4. `synthesis` — llm.py, openai_llm.py, ollama_llm.py, anthropic_llm.py, prompt.py, synthesizer.py, __init__.py
5. `pipeline` — orchestrator.py
6. `cli` — cli.py, cli_ingest.py, cli_query.py, cli_eval.py