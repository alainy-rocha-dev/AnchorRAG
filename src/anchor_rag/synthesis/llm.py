"""ABC e configuração base para provedores de LLM."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional, AsyncGenerator
from pydantic import BaseModel
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuração do provedor de LLM."""

    provider: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 2048
    timeout: int = 30
    api_key: Optional[str] = None
    base_url: Optional[str] = None


@dataclass
class LLMResponse:
    """Resposta do LLM."""

    content: str
    input_tokens: int
    output_tokens: int
    model: str
    finish_reason: Optional[str] = None


class LLMProvider(ABC):
    """Interface base para provedores de LLM."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def complete(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Completa uma conversa (non-streaming)."""
        pass

    @abstractmethod
    async def complete_stream(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """Completa com streaming."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica se o provedor está saudável."""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Conta tokens no texto."""
        pass