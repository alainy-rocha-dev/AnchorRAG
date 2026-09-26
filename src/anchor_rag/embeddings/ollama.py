"""Provedor de embedding Ollama via HTTP /api/embed."""

from __future__ import annotations
from typing import List, Optional
import logging
import httpx

from anchor_rag.embeddings.base import EmbeddingProvider, EmbeddingConfig

logger = logging.getLogger(__name__)

# Modelos conhecidos do Ollama e suas dimensões
OLLAMA_MODEL_DIMS = {
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
    "all-minilm": 384,
    "bge-m3": 1024,
    "snowflake-arctic-embed": 1024,
}


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Provedor de embeddings via Ollama HTTP API."""

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=config.timeout,
        )

        # Detecta dimensões do modelo
        model_key = config.model.lower().replace(":", "-")
        self._dimensions = OLLAMA_MODEL_DIMS.get(model_key, config.dimensions)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, text: str) -> List[float]:
        """Gera embedding para um texto único."""
        response = await self._post_embed([text])
        return response[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Gera embeddings em lote."""
        if not texts:
            return []
        return await self._post_embed(texts)

    async def _post_embed(self, texts: List[str]) -> List[List[float]]:
        payload = {"model": self.config.model, "input": texts}
        response = await self._client.post("/api/embed", json=payload)
        response.raise_for_status()
        data = response.json()
        embeddings = data.get("embeddings", [])
        self._validate_dimensions(embeddings)
        return embeddings

    async def health_check(self) -> bool:
        """Verifica se Ollama está respondendo."""
        try:
            response = await self._client.get("/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama health check falhou: {e}")
            return False

    async def close(self):
        """Fecha o cliente HTTP."""
        await self._client.aclose()