"""Modelos de domínio Pydantic."""

from enum import Enum
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator
from uuid import UUID, uuid4
from datetime import datetime


class ChunkUnit(str, Enum):
    """Unidade de medida para chunking."""

    CHARS = "chars"
    TOKENS = "tokens"


class Document(BaseModel):
    """Representa um documento ingerido."""

    id: UUID = Field(default_factory=uuid4)
    path: str
    filename: str
    content_hash: str
    page_count: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("content_hash")
    @classmethod
    def validate_hash(cls, v: str) -> str:
        if len(v) != 64:
            raise ValueError("content_hash deve ser SHA256 (64 caracteres hex)")
        return v.lower()


class Chunk(BaseModel):
    """Representa um chunk de texto com metadados."""

    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    content: str
    chunk_index: int
    page_number: Optional[int] = None
    start_char: int
    end_char: int
    token_count: Optional[int] = None
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("chunk_index")
    @classmethod
    def validate_index(cls, v: int) -> int:
        if v < 0:
            raise ValueError("chunk_index não pode ser negativo")
        return v


class QueryResult(BaseModel):
    """Resultado de uma query RAG."""

    answer: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    chunks_used: List[Chunk] = Field(default_factory=list)
    scores: List[float] = Field(default_factory=list)
    latency_ms: Dict[str, float] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestConfig(BaseModel):
    """Configuração para ingestão."""

    chunk_size: int = 512
    chunk_overlap: int = 50
    chunk_unit: ChunkUnit = ChunkUnit.TOKENS
    parser: Literal["pdfplumber", "pypdf"] = "pdfplumber"
    force_reingest: bool = False
    recursive: bool = False


class QueryConfig(BaseModel):
    """Configuração para query."""

    top_k: int = 5
    threshold: float = 0.7
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: Optional[float] = None
    no_synthesis: bool = False
    format: Literal["text", "json"] = "text"