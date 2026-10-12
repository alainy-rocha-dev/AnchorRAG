"""ABC base para Vector Store."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
import logging
from uuid import UUID
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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

    async def search_with_scores(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> List[Tuple[Chunk, float]]:
        """
        Busca por similaridade e devolve pares (chunk, score), score maior primeiro.

        Implementação padrão para stores que não expõem o score (ex.: mocks de teste):
        usa search() e marca score 1.0, com aviso. Stores reais devem sobrescrever.
        """
        if not getattr(self, "_aviso_sem_score", False):
            logger.warning(
                "%s não implementa search_with_scores; usando score 1.0 para todos os chunks",
                type(self).__name__,
            )
            self._aviso_sem_score = True
        chunks = await self.search(query_embedding, top_k=top_k, threshold=threshold)
        return [(c, 1.0) for c in chunks]

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