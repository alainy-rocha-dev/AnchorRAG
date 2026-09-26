"""Factory para Vector Stores."""

from __future__ import annotations
from typing import List, Type
import logging

from anchor_rag.vector_store.base import VectorStore
from anchor_rag.vector_store.sqlite_vec import SQLiteVecStore

logger = logging.getLogger(__name__)

# Registry
_STORES: dict[str, Type[VectorStore]] = {
    "sqlite_vec": SQLiteVecStore,
}


def register_store(name: str, store_class: Type[VectorStore]) -> None:
    """Registra um novo vector store."""
    _STORES[name.lower()] = store_class
    logger.info(f"Vector store registrado: {name}")


def list_stores() -> List[str]:
    """Lista stores disponíveis."""
    return list(_STORES.keys())


def create_vector_store(
    store_type: str = "sqlite_vec",
    **kwargs,
) -> VectorStore:
    """Factory para criar vector store."""
    store_type = store_type.lower()
    if store_type not in _STORES:
        available = ", ".join(_STORES.keys())
        raise ValueError(f"Store '{store_type}' não suportado. Disponíveis: {available}")

    store_class = _STORES[store_type]
    logger.info(f"Criando vector store: {store_type}")
    return store_class(**kwargs)


# Auto-detect: tenta sqlite-vec, cai para fallback se não disponível
async def auto_create_vector_store(**kwargs) -> VectorStore:
    """Cria store com auto-detecção de sqlite-vec."""
    try:
        import sqlite_vec  # noqa: F401
        return create_vector_store("sqlite_vec", **kwargs)
    except ImportError:
        logger.warning("sqlite-vec não disponível, usando fallback (não implementado)")
        raise RuntimeError("sqlite-vec é necessário. Instale com: pip install sqlite-vec")