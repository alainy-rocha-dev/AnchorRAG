# Interface: LLMProvider (Abstração Python)

> Feature: `001-pipeline-rag-hag2`
> Tipo: Interface interna (Python ABC)
> Data: `2026-09-22`

## 1. Propósito

Abstração para chamada a modelos de linguagem (LLM) para síntese da resposta RAG. Permite trocar provedor (OpenAI, Ollama, Anthropic) sem alterar o sintetizador.

## 2. Contrato (ABC)

```python
# src/hag_rag/synthesis/llm.py

from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel
from dataclasses import dataclass

class LLMConfig(BaseModel):
    model: str
    temperature: float = 0.0
    max_tokens: int = 1024
    timeout: float = 5.0
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0

@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    latency_ms: int = 0

class LLMProvider(ABC):
    """Interface para provedores de LLM."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identificador único (ex.: 'openai', 'ollama', 'anthropic')."""
        ...

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """Gera completão para o prompt dado."""
        ...

    @abstractmethod
    def complete_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        """Generator para streaming de tokens (futuro SSE)."""
        ...

    def health_check(self) -> bool:
        try:
            self.complete("ping", max_tokens=1)
            return True
        except Exception:
            return False
```

## 3. Implementações previstas

### 3.1 OpenAI (`OpenAILLMProvider`)

```python
# src/hag_rag/synthesis/openai_llm.py

from openai import OpenAI
from .llm import LLMProvider, LLMConfig, LLMResponse

class OpenAILLMProvider(LLMProvider):
    provider_name = "openai"

    def __init__(self, config: LLMConfig, api_key: str | None = None):
        super().__init__(config)
        self.client = OpenAI(api_key=api_key)

    def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        import time
        start = time.perf_counter()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature if temperature is not None else self.config.temperature,
            max_tokens=max_tokens if max_tokens is not None else self.config.max_tokens,
            top_p=self.config.top_p,
            frequency_penalty=self.config.frequency_penalty,
            presence_penalty=self.config.presence_penalty,
            timeout=timeout if timeout is not None else self.config.timeout,
        )

        latency_ms = int((time.perf_counter() - start) * 1000)
        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            text=choice.message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            model=response.model,
            latency_ms=latency_ms,
        )

    def complete_stream(self, prompt: str, system_prompt: str | None = None, **kwargs):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            stream=True,
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
```

### 3.2 Ollama (`OllamaLLMProvider`)

```python
# src/hag_rag/synthesis/ollama_llm.py

import httpx
import time
from .llm import LLMProvider, LLMConfig, LLMResponse

class OllamaLLMProvider(LLMProvider):
    provider_name = "ollama"

    def __init__(self, config: LLMConfig, base_url: str = "http://localhost:11434"):
        super().__init__(config)
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=config.timeout)

    def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        start = time.perf_counter()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.config.temperature,
                "num_predict": max_tokens if max_tokens is not None else self.config.max_tokens,
                "top_p": self.config.top_p,
            },
        }

        response = self.client.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=timeout if timeout is not None else self.config.timeout,
        )
        response.raise_for_status()
        data = response.json()

        latency_ms = int((time.perf_counter() - start) * 1000)

        return LLMResponse(
            text=data["message"]["content"],
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
            total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            model=data.get("model", self.config.model),
            latency_ms=latency_ms,
        )

    def complete_stream(self, prompt: str, system_prompt: str | None = None, **kwargs):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            },
        }

        with self.client.stream("POST", f"{self.base_url}/api/chat", json=payload, timeout=30.0) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    import json
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]
```

### 3.3 Anthropic (`AnthropicLLMProvider`)

```python
# src/hag_rag/synthesis/anthropic_llm.py

from anthropic import Anthropic
from .llm import LLMProvider, LLMConfig, LLMResponse

class AnthropicLLMProvider(LLMProvider):
    provider_name = "anthropic"

    def __init__(self, config: LLMConfig, api_key: str | None = None):
        super().__init__(config)
        self.client = Anthropic(api_key=api_key)

    def complete(self, prompt: str, system_prompt: str | None = None, **kwargs) -> LLMResponse:
        import time
        start = time.perf_counter()

        response = self.client.messages.create(
            model=self.config.model,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            top_p=self.config.top_p,
            timeout=kwargs.get("timeout", self.config.timeout),
        )

        latency_ms = int((time.perf_counter() - start) * 1000)

        return LLMResponse(
            text=response.content[0].text if response.content else "",
            prompt_tokens=response.usage.input_tokens if response.usage else 0,
            completion_tokens=response.usage.output_tokens if response.usage else 0,
            total_tokens=(response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0,
            model=response.model,
            latency_ms=latency_ms,
        )

    def complete_stream(self, prompt: str, system_prompt: str | None = None, **kwargs):
        with self.client.messages.stream(
            model=self.config.model,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
        ) as stream:
            for text in stream.text_stream:
                yield text
```

## 4. Factory / Registry

```python
# src/hag_rag/synthesis/__init__.py

from .llm import LLMProvider, LLMConfig
from .openai_llm import OpenAILLMProvider
from .ollama_llm import OllamaLLMProvider
from .anthropic_llm import AnthropicLLMProvider

_PROVIDERS = {
    "openai": OpenAILLMProvider,
    "ollama": OllamaLLMProvider,
    "anthropic": AnthropicLLMProvider,
}

def create_llm_provider(
    provider: str,
    config: LLMConfig,
    **kwargs
) -> LLMProvider:
    if provider not in _PROVIDERS:
        raise ValueError(f"Provedor LLM desconhecido: {provider}. "
                         f"Disponíveis: {list(_PROVIDERS.keys())}")
    return _PROVIDERS[provider](config, **kwargs)

def list_providers() -> List[str]:
    return list(_PROVIDERS.keys())
```

## 5. Uso no sintetizador RAG

```python
# src/hag_rag/synthesis/synthesizer.py

from .llm import LLMProvider, LLMConfig
from ..domain.models import Chunk, QueryResult

class RAGSynthesizer:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    def synthesize(
        self,
        query: str,
        chunks: List[Chunk],
        scores: List[float],
        config: LLMConfig,
    ) -> QueryResult:
        # 1. Build system prompt com ancoragem estrita
        system_prompt = self._build_system_prompt()

        # 2. Build user prompt com chunks numerados
        user_prompt = self._build_user_prompt(query, chunks, scores)

        # 3. Chamar LLM
        response = self.llm.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout,
        )

        # 4. Parse citations [N] -> mapear para chunks
        citations = self._extract_citations(response.text, chunks)

        return QueryResult(
            chunks=chunks,
            scores=scores,
            synthesis=response.text,
            citations=citations,
            latency_ms=response.latency_ms,  # Apenas LLM; total medido no orchestrator
            embedding_model="",  # Preenchido pelo orchestrator
            llm_model=self.llm.config.model,
        )
```

## 6. Requisitos não-funcionais

| Requisito | Detalhe |
|-----------|---------|
| **Timeout hard** | 5.0s default (configurável); encerra e retorna erro gracioso |
| **Temperatura** | 0.0 default (determinístico para RAG) |
| **Max tokens** | 1024 default; evitar truncamento de resposta |
| **System prompt** | Obrigatório — contém instruções de ancoragem estrita |
| **Token counting** | Retornar usage se provedor suportar (OpenAI, Anthropic, Ollama) |
| **Streaming** | `complete_stream` definido para futuro SSE (não usado no MVP) |
| **Logging** | Log INFO: "LLM call: model=X, tokens=Y, latency=Zms" |