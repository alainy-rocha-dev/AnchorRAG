"""Factory e registry para provedores de embedding."""

from __future__ import annotations
from typing import Dict, List, Type
import logging

from anchor_rag.embeddings.base import EmbeddingProvider, EmbeddingConfig
from anchor_rag.embeddings.openai import OpenAIEmbeddingProvider
from anchor_rag.embeddings.ollama import OllamaEmbeddingProvider
from anchor_rag.embeddings.huggingface import HuggingFaceEmbeddingProvider

logger = logging.getLogger(__name__)

# Registry de provedores disponíveis
_PROVIDERS: Dict[str, Type[EmbeddingProvider]] = {
    "openai": OpenAIEmbeddingProvider,
    "ollama": OllamaEmbeddingProvider,
    "huggingface": HuggingFaceEmbeddingProvider,
}


def register_provider(name: str, provider_class: Type[EmbeddingProvider]) -> None:
    """Registra um novo provedor customizado."""
    _PROVIDERS[name.lower()] = provider_class
    logger.info(f"Provedor de embedding registrado: {name}")


def list_providers() -> List[str]:
    """Lista nomes dos provedores disponíveis."""
    return list(_PROVIDERS.keys())


def create_embedding_provider(config: EmbeddingConfig) -> EmbeddingProvider:
    """Factory para criar provedor de embedding."""
    provider_name = config.provider.lower()
    if provider_name not in _PROVIDERS:
        available = ", ".join(_PROVIDERS.keys())
        raise ValueError(
            f"Provedor '{provider_name}' não suportado. Disponíveis: {available}"
        )

    provider_class = _PROVIDERS[provider_name]
    logger.info(f"Criando provedor de embedding: {provider_name} ({config.model})")
    return provider_class(config)


# Backwards compatibility
EmbeddingProviderType = EmbeddingProvider