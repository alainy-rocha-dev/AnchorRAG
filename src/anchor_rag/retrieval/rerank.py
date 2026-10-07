"""Interface e implementações de Reranker (cross-encoder)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
import logging
from dataclasses import dataclass

from anchor_rag.vector_store.base import Chunk

logger = logging.getLogger(__name__)


@dataclass
class RerankerConfig:
    """Configuração do reranker."""
    model_name: str = "BAAI/bge-reranker-v2-m3"
    batch_size: int = 32
    max_length: int = 512
    device: str = "auto"  # auto, cpu, cuda, mps


class Reranker(ABC):
    """Interface abstrata para rerankers cross-encoder."""
    
    @abstractmethod
    async def rerank(
        self,
        query: str,
        chunks: List[Chunk],
        top_k: Optional[int] = None,
    ) -> List[Tuple[Chunk, float]]:
        """
        Reordena chunks por relevância cross-encoder.
        
        Args:
            query: Pergunta original
            chunks: Lista de chunks candidatos
            top_k: Retornar apenas top_k (None = todos)
        
        Returns:
            Lista de (Chunk, score) ordenada por score decrescente.
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Libera recursos (modelo, conexões)."""
        pass


class HuggingFaceReranker(Reranker):
    """Reranker usando sentence-transformers CrossEncoder local."""
    
    def __init__(self, config: Optional[RerankerConfig] = None):
        self.config = config or RerankerConfig()
        self._model = None
        self._device = None
    
    def _load_model(self):
        """Carrega modelo lazily."""
        if self._model is not None:
            return
        
        from sentence_transformers import CrossEncoder
        import torch
        
        if self.config.device == "auto":
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self._device = self.config.device
        
        logger.info(f"Carregando reranker {self.config.model_name} em {self._device}")
        self._model = CrossEncoder(
            self.config.model_name,
            max_length=self.config.max_length,
            device=self._device,
        )
    
    async def rerank(
        self,
        query: str,
        chunks: List[Chunk],
        top_k: Optional[int] = None,
    ) -> List[Tuple[Chunk, float]]:
        if not chunks:
            return []
        
        self._load_model()
        
        # Prepara pares (query, chunk_content)
        pairs = [(query, chunk.content) for chunk in chunks]
        
        # Prediz scores em batch
        import asyncio
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(
            None,
            lambda: self._model.predict(pairs, batch_size=self.config.batch_size, show_progress_bar=False)
        )
        
        # Combina e ordena
        results = list(zip(chunks, scores.tolist()))
        results.sort(key=lambda x: x[1], reverse=True)
        
        if top_k:
            results = results[:top_k]
        
        return results
    
    async def close(self):
        self._model = None
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


class OllamaReranker(Reranker):
    """Reranker via Ollama (modelo local via HTTP)."""
    
    def __init__(
        self,
        model: str = "bge-reranker-v2-m3",
        base_url: str = "http://localhost:11434",
        batch_size: int = 32,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.batch_size = batch_size
        self._session = None
    
    async def _get_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60)
            )
        return self._session
    
    async def rerank(
        self,
        query: str,
        chunks: List[Chunk],
        top_k: Optional[int] = None,
    ) -> List[Tuple[Chunk, float]]:
        if not chunks:
            return []
        
        session = await self._get_session()
        
        # Ollama não tem endpoint nativo de rerank, simula com embeddings
        # Para cross-encoder real, usar HF local ou API dedicada
        logger.warning("OllamaReranker usa fallback de similaridade de embeddings; prefira HuggingFaceReranker")
        
        # Fallback: embedding da query + embeddings dos chunks -> cosseno
        from anchor_rag.embeddings.ollama import OllamaEmbeddingProvider
        from anchor_rag.config import EmbeddingConfig
        
        embedder = OllamaEmbeddingProvider(EmbeddingConfig(
            provider="ollama",
            model=self.model,
            base_url=self.base_url,
        ))
        
        query_emb = await embedder.embed(query)
        chunk_embs = await embedder.embed_batch([c.content for c in chunks])
        
        import numpy as np
        query_arr = np.array(query_emb, dtype=np.float32)
        query_arr = query_arr / (np.linalg.norm(query_arr) + 1e-8)
        
        results = []
        for chunk, emb in zip(chunks, chunk_embs):
            chunk_arr = np.array(emb, dtype=np.float32)
            chunk_arr = chunk_arr / (np.linalg.norm(chunk_arr) + 1e-8)
            score = float(np.dot(query_arr, chunk_arr))
            results.append((chunk, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        
        if top_k:
            results = results[:top_k]
        
        return results
    
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None


class CohereReranker(Reranker):
    """Reranker via API Cohere (rerank-english-v3.0, rerank-multilingual-v3.0)."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "rerank-multilingual-v3.0",
        base_url: str = "https://api.cohere.ai/v1",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._session = None
    
    async def _get_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=aiohttp.ClientTimeout(total=60),
            )
        return self._session
    
    async def rerank(
        self,
        query: str,
        chunks: List[Chunk],
        top_k: Optional[int] = None,
    ) -> List[Tuple[Chunk, float]]:
        if not chunks:
            return []
        
        session = await self._get_session()
        
        documents = [c.content for c in chunks]
        
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": top_k or len(documents),
            "return_documents": False,
        }
        
        async with session.post(f"{self.base_url}/rerank", json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.error(f"Cohere rerank error {resp.status}: {text}")
                raise RuntimeError(f"Cohere rerank failed: {text}")
            
            data = await resp.json()
        
        # Reconstrói na ordem original com scores
        results = []
        for item in data["results"]:
            idx = item["index"]
            score = item["relevance_score"]
            results.append((chunks[idx], score))
        
        return results
    
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None


def create_reranker(provider: str, **kwargs) -> Reranker:
    """Factory para criar reranker."""
    provider = provider.lower()
    
    if provider == "huggingface" or provider == "hf":
        return HuggingFaceReranker(RerankerConfig(**kwargs))
    elif provider == "ollama":
        return OllamaReranker(**kwargs)
    elif provider == "cohere":
        return CohereReranker(**kwargs)
    else:
        raise ValueError(f"Reranker provider desconhecido: {provider}")