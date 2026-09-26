"""Provedor LLM Ollama via HTTP /api/chat."""

from __future__ import annotations
from typing import List, Optional, AsyncGenerator
import logging
import httpx
import json

from anchor_rag.synthesis.llm import LLMProvider, LLMConfig, LLMResponse

logger = logging.getLogger(__name__)


class OllamaLLMProvider(LLMProvider):
    """Provedor LLM via Ollama HTTP API."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=config.timeout,
        )

    async def complete(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Completa chat sem streaming."""
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature or self.config.temperature,
                "num_predict": max_tokens or self.config.max_tokens,
            },
        }
        response = await self._client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        message = data.get("message", {})
        return LLMResponse(
            content=message.get("content", ""),
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            model=data.get("model", self.config.model),
            finish_reason=data.get("done_reason"),
        )

    async def complete_stream(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """Completa com streaming via Server-Sent Events."""
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature or self.config.temperature,
                "num_predict": max_tokens or self.config.max_tokens,
            },
        }
        async with self._client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                    except json.JSONDecodeError:
                        continue

    async def health_check(self) -> bool:
        """Verifica se Ollama está respondendo."""
        try:
            response = await self._client.get("/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama LLM health check falhou: {e}")
            return False

    def count_tokens(self, text: str) -> int:
        """Contagem aproximada (Ollama não expõe tokenizer)."""
        # Aproximação: ~1 token por 4 chars em inglês, ~1 por 2-3 em português
        return max(1, len(text) // 3)

    async def close(self):
        """Fecha cliente HTTP."""
        await self._client.aclose()