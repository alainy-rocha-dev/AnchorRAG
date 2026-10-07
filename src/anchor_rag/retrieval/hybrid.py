"""Busca híbrida: fusão RRF de vetorial + FTS5 (BM25)."""

from __future__ import annotations

from typing import List, Tuple, Optional, Callable, Awaitable
from uuid import UUID
import logging

from anchor_rag.vector_store.base import VectorStore, Chunk
from anchor_rag.retrieval.fts import FTS5Store

logger = logging.getLogger(__name__)


# Type aliases
VectorSearchFn = Callable[[List[float], int, float], Awaitable[List[Chunk]]]
FTSSearchFn = Callable[[str, int, Optional[str], Optional[str]], Awaitable[List[Tuple[Chunk, float]]]]


def rrf_fusion(
    rankings: List[List[UUID]],
    k: int = 60,
) -> List[Tuple[UUID, float]]:
    """
    Reciprocal Rank Fusion (RRF).
    
    Args:
        rankings: Lista de rankings, cada um é lista de chunk_ids ordenados (melhor primeiro)
        k: Constante de suavização (padrão 60)
    
    Returns:
        Lista de (chunk_id, score_rrf) ordenada por score decrescente.
    """
    scores: dict[UUID, float] = {}
    
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


class HybridRetriever:
    """
    Recuperador híbrido: vetorial + FTS5 (BM25) + RRF + Reranker opcional.
    
    Fluxo:
    1. Busca vetorial (top_k * 2)
    2. Busca FTS5/BM25 (top_k * 2)
    3. Fusão RRF
    4. Reranker opcional (cross-encoder)
    5. Retorna top_k final
    """

    def __init__(
        self,
        vector_store: VectorStore,
        fts_store: FTS5Store,
        embedder: Callable[[str], Awaitable[List[float]]],
        reranker: Optional[Callable[[str, List[Chunk]], Awaitable[List[Tuple[Chunk, float]]]]] = None,
        top_k: int = 10,
        vector_weight: float = 1.0,  # mantido para compat, RRF não usa pesos
        fts_weight: float = 1.0,
    ):
        self.vector_store = vector_store
        self.fts_store = fts_store
        self.embedder = embedder
        self.reranker = reranker
        self.top_k = top_k
        self.vector_weight = vector_weight
        self.fts_weight = fts_weight

    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        threshold: float = 0.0,
        norma_filter: Optional[str] = None,
        artigo_filter: Optional[str] = None,
        use_reranker: bool = True,
    ) -> List[Chunk]:
        """
        Executa busca híbrida completa.
        
        Args:
            query: Pergunta do usuário
            top_k: Número final de resultados (default: self.top_k)
            threshold: Threshold mínimo de similaridade vetorial
            norma_filter: Filtrar por norma específica
            artigo_filter: Filtrar por artigo específico
            use_reranker: Se True e reranker configurado, aplica rerank
        
        Returns:
            Lista de Chunks ordenados por relevância final.
        """
        k = top_k or self.top_k
        expanded_k = k * 3  # Busca mais para fusão ter material
        
        # 1. Busca vetorial
        query_embedding = await self.embedder(query)
        vector_results = await self.vector_store.search(
            query_embedding=query_embedding,
            top_k=expanded_k,
            threshold=threshold,
        )
        vector_ids = [c.id for c in vector_results]
        logger.debug(f"Vetorial: {len(vector_results)} resultados")
        
        # 2. Busca FTS5 (BM25)
        fts_results = await self.fts_store.search(
            query=query,
            top_k=expanded_k,
            norma_filter=norma_filter,
            artigo_filter=artigo_filter,
        )
        fts_ids = [c.id for c, _ in fts_results]
        logger.debug(f"FTS5: {len(fts_results)} resultados")
        
        # 3. Fusão RRF
        fused = rrf_fusion([vector_ids, fts_ids])
        fused_ids = [cid for cid, _ in fused[:k * 2]]  # Pega top 2k para rerank
        
        # Reconstrói objetos Chunk completos a partir dos IDs fundidos
        # Prioriza resultados que apareceram em ambos
        id_to_chunk = {}
        for c in vector_results:
            id_to_chunk[c.id] = c
        for c, _ in fts_results:
            if c.id not in id_to_chunk:
                id_to_chunk[c.id] = c
        
        fused_chunks = [id_to_chunk[cid] for cid in fused_ids if cid in id_to_chunk]
        
        # 4. Reranker opcional
        if use_reranker and self.reranker and fused_chunks:
            reranked = await self.reranker(query, fused_chunks)
            fused_chunks = [c for c, _ in reranked[:k]]
            logger.debug(f"Reranker: {len(fused_chunks)} resultados finais")
        else:
            fused_chunks = fused_chunks[:k]
        
        return fused_chunks

    async def retrieve_vector_only(
        self,
        query: str,
        top_k: Optional[int] = None,
        threshold: float = 0.0,
    ) -> List[Chunk]:
        """Apenas busca vetorial (para ablação)."""
        k = top_k or self.top_k
        query_embedding = await self.embedder(query)
        return await self.vector_store.search(query_embedding, k, threshold)

    async def retrieve_fts_only(
        self,
        query: str,
        top_k: Optional[int] = None,
        norma_filter: Optional[str] = None,
        artigo_filter: Optional[str] = None,
    ) -> List[Chunk]:
        """Apenas busca FTS5/BM25 (para ablação)."""
        k = top_k or self.top_k
        results = await self.fts_store.search(query, k, norma_filter, artigo_filter)
        return [c for c, _ in results]