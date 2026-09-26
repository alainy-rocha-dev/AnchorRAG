# Data Delta: Implementação inicial do Projeto HAG 2 (Pipeline RAG)

> Feature: `001-pipeline-rag-hag2`
> Data: `2026-09-22`
> Tipo: Greenfield (modelo novo, sem legado para migrar)

## 1. Visão geral

Modelo de dados totalmente novo. Três entidades principais persistidas no SQLite (via `sqlite-vec`):
- **Document** — metadados do arquivo PDF ingerido
- **Chunk** — trechos de texto com embedding e metadados de rastreabilidade
- **QueryLog** — registro opcional de consultas para observabilidade/avaliação

## 2. Esquema SQLite (DDL)

```sql
-- Tabela de documentos ingeridos
CREATE TABLE documents (
    id              TEXT PRIMARY KEY,           -- UUIDv4
    file_path       TEXT NOT NULL,              -- Caminho original ou hash
    file_name       TEXT NOT NULL,              -- Nome do arquivo
    file_hash       TEXT NOT NULL,              -- SHA256 para dedup
    page_count      INTEGER NOT NULL,           -- Total de páginas
    chunk_count     INTEGER NOT NULL DEFAULT 0, -- Quantidade de chunks gerados
    ingested_at     TEXT NOT NULL,              -- ISO 8601 UTC
    meta_json       TEXT                        -- JSON extensível (author, title, etc.)
);

-- Índice para busca por hash (deduplicação)
CREATE UNIQUE INDEX idx_documents_hash ON documents(file_hash);

-- Tabela de chunks com extensão vetorial (sqlite-vec)
-- sqlite-vec cria uma tabela virtual para vetores; aqui schema lógico:
CREATE TABLE chunks (
    id              TEXT PRIMARY KEY,           -- UUIDv4
    document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,           -- Ordem no documento (0-based)
    text            TEXT NOT NULL,              -- Texto do chunk
    char_count      INTEGER NOT NULL,           -- Contagem de caracteres
    token_count     INTEGER,                    -- Contagem de tokens (se chunk_unit=tokens)
    page_start      INTEGER NOT NULL,           -- Página inicial (1-indexed)
    page_end        INTEGER NOT NULL,           -- Página final (1-indexed)
    char_offset_start INTEGER NOT NULL,         -- Offset inicial no texto original
    char_offset_end   INTEGER NOT NULL,         -- Offset final no texto original
    embedding       BLOB NOT NULL,              -- Vetor serializado (sqlite-vec armazena em tabela virtual)
    model_name      TEXT NOT NULL,              -- Nome do modelo de embedding usado
    model_dim       INTEGER NOT NULL,           -- Dimensão do vetor
    created_at      TEXT NOT NULL               -- ISO 8601 UTC
);

-- Índices para performance
CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_chunks_model ON chunks(model_name);

-- Tabela virtual para busca vetorial (sqlite-vec)
-- Criada via: vec0 virtual table usando chunks_embedding
-- Exemplo: CREATE VIRTUAL TABLE chunks_vec USING vec0(embedding FLOAT[1536]);
-- O schema exato depende da versão do sqlite-vec

-- Tabela de log de queries (opcional, observabilidade)
CREATE TABLE query_logs (
    id              TEXT PRIMARY KEY,           -- UUIDv4
    query_text      TEXT NOT NULL,
    top_k           INTEGER NOT NULL,
    chunk_ids       TEXT NOT NULL,              -- JSON array de chunk IDs retornados
    scores          TEXT NOT NULL,              -- JSON array de scores
    synthesis       TEXT,                       -- Resposta sintetizada (pode ser NULL se erro)
    latency_ms      INTEGER NOT NULL,           -- Latência total em ms
    model_embedding TEXT NOT NULL,              -- Modelo embedding usado
    model_llm       TEXT NOT NULL,              -- Modelo LLM usado
    created_at      TEXT NOT NULL               -- ISO 8601 UTC
);

CREATE INDEX idx_query_logs_created ON query_logs(created_at);
```

## 3. Entidades de domínio (Python/Pydantic)

```python
# src/hag_rag/domain/models.py

from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional, List
from enum import Enum

class ChunkUnit(str, Enum):
    CHARS = "chars"
    TOKENS = "tokens"

class Document(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    file_path: str
    file_name: str
    file_hash: str
    page_count: int
    chunk_count: int = 0
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    meta: dict = Field(default_factory=dict)

class Chunk(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    chunk_index: int
    text: str
    char_count: int
    token_count: Optional[int] = None
    page_start: int
    page_end: int
    char_offset_start: int
    char_offset_end: int
    embedding: List[float] = Field(default_factory=list)  # Preenchido após embedding
    model_name: str
    model_dim: int
    created_at: datetime = Field(default_factory=datetime.utcnow)

class QueryResult(BaseModel):
    chunks: List[Chunk]
    scores: List[float]  # Similaridade de cosseno 0.0-1.0
    synthesis: Optional[str] = None
    citations: List[dict] = Field(default_factory=list)  # [{"chunk_id": ..., "file": ..., "page": ..., "score": ...}]
    latency_ms: int
    embedding_model: str
    llm_model: str

class IngestConfig(BaseModel):
    chunk_size: int = 1000
    chunk_overlap: int = 200
    chunk_unit: ChunkUnit = ChunkUnit.CHARS
    embedding_model: str = "text-embedding-3-small"
    pdf_parser: str = "pdfplumber"  # ou "pypdf"

class QueryConfig(BaseModel):
    top_k: int = 3
    similarity_threshold: float = 0.40
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 1024
    llm_timeout: float = 5.0
```

## 4. Fluxo de dados (Data Flow)

```
INGESTÃO:
PDF file → pdfplumber → pages text → sanitize → chunker(chunk_size, overlap, unit)
    → Chunk[] (com metadados) → EmbeddingProvider.embed_batch() → Chunk[] (com embeddings)
    → VectorStore.add_chunks() → SQLite (documents + chunks + vec index)

CONSULTA:
Query text → EmbeddingProvider.embed() → query_vec
    → VectorStore.search(query_vec, top_k) → Chunk[] + scores
    → RAGSynthesizer.synthesize(query, chunks, scores) → QueryResult
    → (opcional) QueryLog.save()
```

## 5. Migrações

**Não aplicável** — greenfield. Primeira execução cria schema via `sqlite-vec` initialization script.

Futuro: se schema mudar, usar `alembic` ou scripts de migração versionados em `migrations/`.

## 6. Índices e performance

| Tabela | Índice | Propósito |
|--------|--------|-----------|
| `documents` | `idx_documents_hash` | Deduplicação por SHA256 |
| `chunks` | `idx_chunks_document` | Listar chunks de um documento |
| `chunks` | `idx_chunks_model` | Filtrar por modelo de embedding (reindex se mudar modelo) |
| `chunks_vec` | (interno sqlite-vec) | ANN/HNSW para busca vetorial |
| `query_logs` | `idx_query_logs_created` | Time-series analytics |

## 7. Estimativas de volume (MVP)

| Entidade | Estimativa | Tamanho aproximado |
|----------|------------|-------------------|
| Documents | 10-100 | ~1 KB cada |
| Chunks | 1.000-50.000 | ~2-5 KB cada (texto + embedding 1536*4B ≈ 6KB) |
| QueryLogs | 1.000-10.000 | ~500 B cada |
| **Total DB** | — | **~100-500 MB** (confortável para SQLite) |

## 8. Backup e recuperação

- SQLite single file → backup = copy file (`.backup` command ou `VACUUM INTO`)
- Point-in-time: não nativo; usar litestream ou replicação se necessário (futuro)
- Embeddings são derivados → regeneráveis a partir dos chunks textuais

## 9. Privacidade e compliance

- **Zero telemetria externa** por padrão (PRD: "privacidade do repositório local")
- Embeddings/LLM providers podem ser 100% locais (Ollama) — configuração no `IngestConfig`/`QueryConfig`
- `file_hash` permite dedup sem expor conteúdo
- `query_logs` opcional (pode ser desabilitado via config)