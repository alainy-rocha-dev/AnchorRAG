"""ABC base para Vector Store."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from dataclasses import dataclass


@dataclass
class Chunk:
    """Chunk armazenado no vector store."""

    id: UUID
    document_id: UUID
    content: str
    chunk_index: int
    page_number: Optional[int]
    start_char: int
    end_char: int
    token_count: Optional[int]
    embedding: Optional[List[float]]
    metadata: dict


class VectorStore(ABC):
    """Interface base para armazenamento vetorial."""

    @abstractmethod
    async def init_db(self) -> None:
        """Inicializa o banco de dados (cria tabelas, índices)."""
        pass

    @abstractmethod
    async def add_chunks(self, chunks: List[Chunk]) -> int:
        """
        Adiciona chunks ao store.
        Retorna número de chunks inseridos.
        """
        pass

    @abstractmethod
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> List[Chunk]:
        """
        Busca por similaridade de cosseno.
        Retorna chunks ordenados por score (maior primeiro).
        """
        pass

    @abstractmethod
    async def get_chunks_by_doc(self, document_id: UUID) -> List[Chunk]:
        """Recupera todos os chunks de um documento."""
        pass

    @abstractmethod
    async def delete_document(self, document_id: UUID) -> int:
        """Remove todos os chunks de um documento. Retorna count removido."""
        pass

    @abstractmethod
    async def get_stats(self) -> dict:
        """Estatísticas do store: total_chunks, total_documents, etc."""
        pass

    @abstractmethod
    async def document_exists_by_hash(self, content_hash: str) -> bool:
        """Verifica se já existe um documento com o content_hash dado."""
        pass