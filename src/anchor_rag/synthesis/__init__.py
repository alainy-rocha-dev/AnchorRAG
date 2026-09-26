"""Factory e registry para provedores de LLM."""

from __future__ import annotations
from typing import Dict, List, Type
import logging

from anchor_rag.synthesis.llm import LLMProvider, LLMConfig
from anchor_rag.synthesis.openai_llm import OpenAILLMProvider
from anchor_rag.synthesis.ollama_llm import OllamaLLMProvider
from anchor_rag.synthesis.anthropic_llm import AnthropicLLMProvider

logger = logging.getLogger(__name__)

_PROVIDERS: Dict[str, Type[LLMProvider]] = {
    "openai": OpenAILLMProvider,
    "ollama": OllamaLLMProvider,
    "anthropic": AnthropicLLMProvider,
}


def register_provider(name: str, provider_class: Type[LLMProvider]) -> None:
    """Registra provedor customizado."""
    _PROVIDERS[name.lower()] = provider_class
    logger.info(f"Provedor LLM registrado: {name}")


def list_providers() -> List[str]:
    """Lista provedores disponíveis."""
    return list(_PROVIDERS.keys())


def create_llm_provider(config: LLMConfig) -> LLMProvider:
    """Factory para criar provedor LLM."""
    provider_name = config.provider.lower()
    if provider_name not in _PROVIDERS:
        available = ", ".join(_PROVIDERS.keys())
        raise ValueError(f"Provedor '{provider_name}' não suportado. Disponíveis: {available}")

    provider_class = _PROVIDERS[provider_name]
    logger.info(f"Criando provedor LLM: {provider_name} ({config.model})")
    return provider_class(config)