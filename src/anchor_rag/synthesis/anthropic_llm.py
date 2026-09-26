"""Provedor LLM Anthropic via SDK."""

from __future__ import annotations
from typing import List, Optional, AsyncGenerator
import logging

from anchor_rag.synthesis.llm import LLMProvider, LLMConfig, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicLLMProvider(LLMProvider):
    """Provedor LLM via Anthropic SDK."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            import anthropic
        except ImportError:
            raise RuntimeError(
                "anthropic não instalado. Instale com: pip install anthropic"
            )
        self._client = anthropic.AsyncAnthropic(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
        )

    async def complete(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Completa chat sem streaming."""
        # Converte mensagens para formato Anthropic (system prompt separado)
        system_prompt = ""
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                anthropic_messages.append({"role": msg["role"], "content": msg["content"]})

        response = await self._client.messages.create(
            model=self.config.model,
            system=system_prompt if system_prompt else None,
            messages=anthropic_messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
        )

        return LLMResponse(
            content=response.content[0].text if response.content else "",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
            finish_reason=response.stop_reason,
        )

    async def complete_stream(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """Completa com streaming."""
        system_prompt = ""
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                anthropic_messages.append({"role": msg["role"], "content": msg["content"]})

        stream = await self._client.messages.create(
            model=self.config.model,
            system=system_prompt if system_prompt else None,
            messages=anthropic_messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.type == "content_block_delta" and chunk.delta.type == "text_delta":
                yield chunk.delta.text

    async def health_check(self) -> bool:
        """Verifica saúde."""
        try:
            await self.complete(
                [{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return True
        except Exception as e:
            logger.warning(f"Anthropic health check falhou: {e}")
            return False

    def count_tokens(self, text: str) -> int:
        """Contagem aproximada via Anthropic tokenizer."""
        try:
            count = self._client.count_tokens(text)
            return count
        except Exception:
            # Fallback aproximado
            return max(1, len(text) // 4)