"""ABC e configuração base para provedores de embedding."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field
from dataclasses import dataclass


@dataclass
class EmbeddingConfig:
    """Configuração do provedor de embedding."""

    provider: str = "openai"
    model: str = "text-embedding-3-small"
    dimensions: int = 1536
    batch_size: int = 100
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3


class EmbeddingProvider(ABC):
    """Interface base para provedores de embedding."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Dimensão dos embeddings gerados."""
        pass

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Gera embedding para um único texto."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Gera embeddings para múltiplos textos em lote."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica se o provedor está saudável."""
        pass

    def _validate_dimensions(self, embeddings: List[List[float]]) -> None:
        """Valida se todos os embeddings têm a dimensão correta."""
        for i, emb in enumerate(embeddings):
            if len(emb) != self.dimensions:
                raise ValueError(
                    f"Embedding {i} tem dimensão {len(emb)}, esperado {self.dimensions}"
                )