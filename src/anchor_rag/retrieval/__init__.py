"""Módulo de recuperação híbrida (vetorial + FTS5 + Reranker)."""

from anchor_rag.retrieval.fts import FTS5Store
from anchor_rag.retrieval.hybrid import HybridRetriever, rrf_fusion
from anchor_rag.retrieval.rerank import (
    Reranker,
    RerankerConfig,
    HuggingFaceReranker,
    OllamaReranker,
    CohereReranker,
    create_reranker,
)

__all__ = [
    "FTS5Store",
    "HybridRetriever",
    "rrf_fusion",
    "Reranker",
    "RerankerConfig",
    "HuggingFaceReranker",
    "OllamaReranker",
    "CohereReranker",
    "create_reranker",
]