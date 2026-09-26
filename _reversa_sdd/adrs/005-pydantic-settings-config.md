# ADR 005: Configuração Hierárquica com Pydantic Settings v2 (YAML + Env + API Keys)

**Data**: 2026-09-22
**Status**: Aceito
**Contexto**: O sistema precisa de configuração tipada, validada, hierárquica, com suporte a arquivo YAML, variáveis de ambiente aninhadas e resolução segura de secrets (API keys).

## Decisão

Usar **Pydantic Settings v2** (`BaseSettings`) com:
- Classes aninhadas por domínio (`EmbeddingConfig`, `LLMConfig`, `ChunkingConfig`, etc.)
- `model_config = SettingsConfigDict(env_prefix="PREFIX_", extra="ignore")` por classe
- `AppConfig` agrega todas via `Field(default_factory=...)`
- Delimiter aninhado `__` (`env_nested_delimiter="__"`) → `EMBEDDING__MODEL=text-embedding-3-large`
- `resolve_api_keys()`: injeta `api_key` lendo `api_key_env` do `os.environ`
- `from_yaml(cls, path)`: carrega YAML → `cls(**data)` → validação automática

## Estrutura

```python
class EmbeddingConfig(BaseSettings):
    provider: Literal["openai","ollama","huggingface"] = "openai"
    model: str = "text-embedding-3-small"
    dimensions: int = 1536
    batch_size: int = 100
    api_key_env: str = "OPENAI_API_KEY"  # nome da env var
    base_url: Optional[str] = None
    model_config = SettingsConfigDict(env_prefix="EMBEDDING_", extra="ignore")
    @field_validator("dimensions") ...

class AppConfig(BaseSettings):
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    query_log: QueryLogConfig = Field(default_factory=QueryLogConfig)
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8",
        env_nested_delimiter="__", extra="ignore"
    )
    
    @classmethod
    def from_yaml(cls, path): ...
    def resolve_api_keys(self) -> "AppConfig": ...
```

## Alternativas Consideradas

| Opção | Prós | Contras |
|-------|------|---------|
| **Pydantic Settings v2** (escolhido) | Type hints, validação automática, YAML + env unificados, nested delimiter, extra=ignore, imutável (retorna nova instância) | Curva de aprendizado v1→v2, `BaseSettings` mudou para `pydantic-settings` pkg |
| **python-dotenv + dataclasses** | Simples, zero dep extra | Sem validação, sem type coercion, manual nested env |
| **Hydra/OmegaConf** | Poderoso, overrides CLI, configs compostos | Dependência pesada, overkill para CLI tool |
| **TOML only** (`pyproject.toml`) | Padrão Python, legível | Sem env vars, sem validação runtime, sem secrets resolution |
| **Argparse + manual merge** | Controle total | Boilerplate enorme, error-prone, sem validação |

## Consequências

### Positivas
- **Single source of truth**: YAML para defaults/compartilhado, `.env` para secrets, env vars para overrides CI/CD
- **Validação antecipada**: Erro na inicialização, não em runtime profundo (ex: `temperature > 2` falha no `AppConfig()`)
- **Type safety**: IDE autocomplete, mypy happy, `Literal` restringe valores
- **Imutabilidade**: `resolve_api_keys()` retorna `model_validate(config_dict)` — nova instância
- **Extensibilidade**: `extra="ignore"` permite novos campos no YAML sem quebrar versões antigas
- **Documentação viva**: Classes = schema; `model_dump()` → dict para logging/debug

### Negativas
- **Duplicação de config**: `EmbeddingConfig` em `domain/models.py` (runtime) + `config.py` (infra) — campos similares, propósitos diferentes
- **`api_key` não tipada no Settings**: Injetada dinamicamente em `resolve_api_keys()`; não aparece no schema YAML
- **`base_url` sem validação URL**: Aceita string inválida; erro só no HTTP client
- **`vector_store.type` Literal com 1 valor**: Preparado para futuro mas sem uso atual

## Mitigações

- Separar claramente: `domain/models.py` = `IngestConfig`/`QueryConfig` (parâmetros de execução); `config.py` = `AppConfig` (infraestrutura)
- `resolve_api_keys()` chamado explicitamente no CLI (`AppConfig().resolve_api_keys()`)
- Validação de URL pode ser adicionada via `@field_validator("base_url")` se necessário
- `vector_store.type` mantido como `Literal["sqlite_vec"]` para type safety

---

## Consequências Detalhadas (doc_level=detalhado)

### Precedência de Configuração (maior → menor prioridade)

1. **Env vars diretas** (`EMBEDDING__MODEL=...`) — override total
2. **`.env` file** (`OPENAI_API_KEY=sk-...`) — secrets
3. **YAML file** (`--config config.yaml`) — config compartilhada versionada
4. **Defaults no código** (`= "openai"`) — fallback

```bash
# Exemplo precedência
# config.yaml: embedding.model = "text-embedding-3-small"
# .env: EMBEDDING__MODEL = "text-embedding-3-large"
# Resultado: model = "text-embedding-3-large" (env var vence)
```

### Exemplo YAML Completo (`config.example.yaml`)

```yaml
embedding:
  provider: "openai"
  model: "text-embedding-3-small"
  dimensions: 1536
  batch_size: 100
  api_key_env: "OPENAI_API_KEY"
  base_url: null
llm:
  provider: "openai"
  model: "gpt-4o-mini"
  temperature: 0.1
  max_tokens: 2048
  timeout: 30
  api_key_env: "OPENAI_API_KEY"
  base_url: null
chunking:
  chunk_size: 512
  chunk_overlap: 50
  chunk_unit: "tokens"
  min_chunk_size: 50
vector_store:
  type: "sqlite_vec"
  path: "./data/hag_rag.db"
  embedding_dimensions: 1536
logging:
  level: "INFO"
  format: "json"
  output: "stdout"
  include_request_id: true
query_log:
  enabled: false
  path: "./data/query_log.db"
```

### Uso no CLI

```python
# cli_ingest.py / cli_query.py / cli_eval.py
if config_path:
    config = AppConfig.from_yaml(config_path).resolve_api_keys()
else:
    config = AppConfig().resolve_api_keys()

# Override CLI args têm precedência final
if chunk_size: config.chunking.chunk_size = chunk_size
```

### Validadores Cross-Field

```python
# ChunkingConfig
@field_validator("chunk_overlap")
def validate_overlap(cls, v, info):
    chunk_size = info.data.get("chunk_size", 512)
    if v >= chunk_size:
        raise ValueError("chunk_overlap deve ser menor que chunk_size")
```

### Lacunas Identificadas (🔴)

1. **`embedding.dimensions` ≠ `vector_store.embedding_dimensions`** — sem validação cross-section; erro só em runtime (`_validate_dimensions` no provider ou `CREATE VIRTUAL TABLE` no store)
2. **`api_key_env` aponta para var inexistente** — `resolve_api_keys` injeta `None` silenciosamente; provedor falha depois no `health_check`
3. **`base_url` formato não validado** — pode ser `"not-a-url"`; erro no `AsyncOpenAI`/`httpx`

### Evolução Futura
- Adicionar `model_config = SettingsConfigDict(validate_assignment=True)` para catch mutations
- Validador cross-section no `AppConfig`: `@model_validator(mode="after")` checar `embedding.dimensions == vector_store.embedding_dimensions`
- `base_url` com `@field_validator` usando `HttpUrl` (pydantic v2)
- `api_key_env` obrigatório + validação de existência em `resolve_api_keys` (warn se não encontrado)