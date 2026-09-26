"""Testes de contrato para EmbeddingProvider ABC."""

import pytest
from abc import ABC, abstractmethod
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock


class EmbeddingProvider(ABC):
    """Contrato para provedores de embedding."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Dimensão dos embeddings."""

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Gera embedding para um texto."""

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Gera embeddings em lote."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica se o provedor está saudável."""


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock implementation para testes."""

    def __init__(self, dims: int = 1536, healthy: bool = True):
        self._dimensions = dims
        self._healthy = healthy
        self.embed_calls = []
        self.embed_batch_calls = []

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, text: str) -> List[float]:
        self.embed_calls.append(text)
        return [0.1] * self._dimensions

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        self.embed_batch_calls.append(texts)
        return [[0.1] * self._dimensions for _ in texts]

    async def health_check(self) -> bool:
        return self._healthy


class TestEmbeddingProviderContract:
    """Testes do contrato EmbeddingProvider."""

    @pytest.fixture
    def provider(self):
        return MockEmbeddingProvider()

    @pytest.mark.asyncio
    async def test_embed_returns_correct_dimensions(self, provider):
        result = await provider.embed("test text")
        assert len(result) == provider.dimensions
        assert all(isinstance(x, float) for x in result)

    @pytest.mark.asyncio
    async def test_embed_batch_returns_correct_shape(self, provider):
        texts = ["text 1", "text 2", "text 3"]
        results = await provider.embed_batch(texts)
        assert len(results) == 3
        assert all(len(r) == provider.dimensions for r in results)

    @pytest.mark.asyncio
    async def test_embed_batch_empty_list(self, provider):
        results = await provider.embed_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_health_check_returns_bool(self, provider):
        result = await provider.health_check()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_embed_called_with_correct_text(self, provider):
        await provider.embed("specific text")
        assert "specific text" in provider.embed_calls

    @pytest.mark.asyncio
    async def test_embed_batch_called_with_list(self, provider):
        texts = ["a", "b"]
        await provider.embed_batch(texts)
        assert provider.embed_batch_calls[-1] == texts


class TestEmbeddingProviderUnhealthy:
    """Testes com provedor não saudável."""

    @pytest.fixture
    def unhealthy_provider(self):
        return MockEmbeddingProvider(healthy=False)

    @pytest.mark.asyncio
    async def test_health_check_false(self, unhealthy_provider):
        result = await unhealthy_provider.health_check()
        assert result is False