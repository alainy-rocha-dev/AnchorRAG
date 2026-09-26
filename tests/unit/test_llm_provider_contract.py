"""Testes de contrato para LLMProvider ABC."""

import pytest
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Resposta do LLM."""

    content: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMProvider(ABC):
    """Contrato para provedores de LLM."""

    @abstractmethod
    async def complete(
        self,
        messages: List[dict],
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Completa o chat."""

    @abstractmethod
    async def complete_stream(
        self,
        messages: List[dict],
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ):
        """Completa com streaming."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica saúde do provedor."""

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Conta tokens."""


class MockLLMProvider(LLMProvider):
    """Mock implementation para testes."""

    def __init__(self, healthy: bool = True):
        self._healthy = healthy
        self.complete_calls = []
        self.stream_calls = []

    async def complete(
        self,
        messages: List[dict],
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        self.complete_calls.append({"messages": messages, "temperature": temperature, "max_tokens": max_tokens})
        return LLMResponse(
            content="Mock response",
            input_tokens=10,
            output_tokens=5,
            model="mock-model",
        )

    async def complete_stream(
        self,
        messages: List[dict],
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ):
        self.stream_calls.append({"messages": messages})
        yield "Mock "
        yield "streaming "
        yield "response"

    async def health_check(self) -> bool:
        return self._healthy

    def count_tokens(self, text: str) -> int:
        return len(text.split())


class TestLLMProviderContract:
    """Testes do contrato LLMProvider."""

    @pytest.fixture
    def provider(self):
        return MockLLMProvider()

    @pytest.mark.asyncio
    async def test_complete_returns_response(self, provider):
        messages = [{"role": "user", "content": "Hello"}]
        response = await provider.complete(messages)
        assert isinstance(response, LLMResponse)
        assert response.content == "Mock response"
        assert response.input_tokens > 0
        assert response.output_tokens > 0

    @pytest.mark.asyncio
    async def test_complete_with_params(self, provider):
        messages = [{"role": "user", "content": "Test"}]
        response = await provider.complete(messages, temperature=0.5, max_tokens=100)
        assert response is not None
        call = provider.complete_calls[-1]
        assert call["temperature"] == 0.5
        assert call["max_tokens"] == 100

    @pytest.mark.asyncio
    async def test_complete_stream_yields_chunks(self, provider):
        messages = [{"role": "user", "content": "Stream test"}]
        chunks = []
        async for chunk in provider.complete_stream(messages):
            chunks.append(chunk)
        assert len(chunks) == 3
        assert "".join(chunks) == "Mock streaming response"

    @pytest.mark.asyncio
    async def test_health_check(self, provider):
        result = await provider.health_check()
        assert isinstance(result, bool)
        assert result is True

    def test_count_tokens(self, provider):
        count = provider.count_tokens("hello world")
        assert count == 2


class TestLLMProviderUnhealthy:
    @pytest.fixture
    def unhealthy_provider(self):
        return MockLLMProvider(healthy=False)

    @pytest.mark.asyncio
    async def test_health_check_false(self, unhealthy_provider):
        result = await unhealthy_provider.health_check()
        assert result is False