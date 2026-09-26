"""Provedor LLM OpenAI com streaming e token counting."""

from __future__ import annotations
from typing import List, Optional, AsyncGenerator
import logging
import tiktoken

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from anchor_rag.synthesis.llm import LLMProvider, LLMConfig, LLMResponse

logger = logging.getLogger(__name__)


class OpenAILLMProvider(LLMProvider):
    """Provedor LLM OpenAI com streaming e contagem de tokens."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=0,
        )
        try:
            self._encoding = tiktoken.encoding_for_model(config.model)
        except Exception:
            self._encoding = tiktoken.get_encoding("cl100k_base")

    @retry(
        wait=wait_exponential_jitter(initial=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def complete(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Completa chat sem streaming."""
        response = await self._client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
        )
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            model=response.model,
            finish_reason=choice.finish_reason,
        )

    @retry(
        wait=wait_exponential_jitter(initial=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def complete_stream(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """Completa com streaming."""
        stream = await self._client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def health_check(self) -> bool:
        """Verifica saúde com uma completion simples."""
        try:
            await self.complete([{"role": "user", "content": "ping"}], max_tokens=5)
            return True
        except Exception as e:
            logger.warning(f"OpenAI LLM health check falhou: {e}")
            return False

    def count_tokens(self, text: str) -> int:
        """Conta tokens usando tiktoken."""
        return len(self._encoding.encode(text))

    def count_message_tokens(self, messages: List[dict]) -> int:
        """Conta tokens de uma lista de mensagens (aproximado)."""
        total = 0
        for msg in messages:
            total += 4  # overhead por mensagem
            for key, value in msg.items():
                total += len(self._encoding.encode(str(value)))
        total += 2  # overhead final
        return total