"""Provedor de embedding OpenAI com retry e batch nativo."""

from __future__ import annotations
from typing import List, Optional
import asyncio
import logging

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from anchor_rag.embeddings.base import EmbeddingProvider, EmbeddingConfig

logger = logging.getLogger(__name__)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Provedor de embeddings OpenAI com retry exponencial e batch nativo."""

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self._client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=0,  # Handle retries manually with tenacity
        )
        # Auto-detect dimensions se não especificado
        if config.dimensions == 1536 and "large" in config.model:
            self._dimensions = 3072
        elif config.dimensions == 1536 and "3-small" in config.model:
            self._dimensions = 1536
        else:
            self._dimensions = config.dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @retry(
        wait=wait_exponential_jitter(initial=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def embed(self, text: str) -> List[float]:
        """Gera embedding para um texto único."""
        response = await self._client.embeddings.create(
            model=self.config.model,
            input=text,
            encoding_format="float",
        )
        return response.data[0].embedding

    @retry(
        wait=wait_exponential_jitter(initial=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Gera embeddings em lote usando API nativa de batch."""
        if not texts:
            return []

        # Processa em lotes se exceder batch_size
        batch_size = self.config.batch_size
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = await self._client.embeddings.create(
                model=self.config.model,
                input=batch,
                encoding_format="float",
            )
            batch_embeddings = [d.embedding for d in response.data]
            all_embeddings.extend(batch_embeddings)

        self._validate_dimensions(all_embeddings)
        return all_embeddings

    async def health_check(self) -> bool:
        """Verifica saúde fazendo uma embedding de teste."""
        try:
            await self.embed("health check")
            return True
        except Exception as e:
            logger.warning(f"OpenAI health check falhou: {e}")
            return False