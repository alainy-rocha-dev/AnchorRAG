"""Exceções customizadas do domínio."""

from typing import Optional


class HAGRAGException(Exception):
    """Exceção base do AnchorRAG."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class InvalidDocumentException(HAGRAGException):
    """Documento inválido ou corrompido."""

    pass


class EmbeddingGenerationException(HAGRAGException):
    """Erro na geração de embeddings."""

    pass


class VectorStoreException(HAGRAGException):
    """Erro no vector store."""

    pass


class SynthesisException(HAGRAGException):
    """Erro na síntese da resposta."""

    pass


class ConfigurationException(HAGRAGException):
    """Erro de configuração."""

    pass


class ProviderNotAvailableException(HAGRAGException):
    """Provedor não disponível."""

    pass