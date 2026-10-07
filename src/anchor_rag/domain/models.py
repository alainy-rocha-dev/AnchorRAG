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


class IngestResult(BaseModel):
    """Resultado da ingestão de um documento."""

    document: Optional[Document] = None
    chunks: List[Chunk] = Field(default_factory=list)
    stats: Optional[Any] = None
    skipped: bool = False
    skip_reason: Optional[str] = None


class EvalMetrics(BaseModel):
    """Métricas de avaliação RAG (estendido para agentic)."""

    recall_at_k: float
    mrr: float
    hallucination_rate: float
    citation_coverage: float
    total_queries: int
    successful_queries: int
    # NOVOS (agentic):
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    # Por query (opcional, para relatório detalhado)
    per_query: List[Dict[str, Any]] = Field(default_factory=list)


class ComparativeMetrics(BaseModel):
    """Resultado de comparação estatística entre provedores."""

    provider_a: str
    provider_b: str
    metric: str
    mean_a: float
    mean_b: float
    mean_diff: float
    p_value: float
    ci_95_lower: float
    ci_95_upper: float
    significant: bool  # p < 0.05


class DriftResult(BaseModel):
    """Resultado de detecção de drift."""

    has_drift: bool
    metric_diffs: Dict[str, float]  # relative diff (current - baseline) / baseline
    threshold: float
    baseline_metrics: Dict[str, float]
    current_metrics: Dict[str, float]
    exit_code: int  # 0=ok, 1=drift, 2=error


class CostEstimate(BaseModel):
    """Estimativa de custo de avaliação."""

    total_tokens_input: int
    total_tokens_output: int
    estimated_cost_usd: float
    per_query: List[Dict[str, Any]]
    budget_exceeded: bool