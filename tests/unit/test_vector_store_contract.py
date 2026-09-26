"""Testes de contrato para VectorStore ABC."""

import pytest
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass
class Chunk:
    """Chunk para testes."""

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
    """Contrato para vector stores."""

    @abstractmethod
    async def init_db(self) -> None:
        """Inicializa o banco."""

    @abstractmethod
    async def add_chunks(self, chunks: List[Chunk]) -> int:
        """Adiciona chunks. Retorna count."""

    @abstractmethod
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> List[Chunk]:
        """Busca similaridade."""

    @abstractmethod
    async def get_chunks_by_doc(self, document_id: UUID) -> List[Chunk]:
        """Recupera chunks de um documento."""

    @abstractmethod
    async def delete_document(self, document_id: UUID) -> int:
        """Remove documento. Retorna count removido."""

    @abstractmethod
    async def get_stats(self) -> dict:
        """Estatísticas do store."""


class MockVectorStore(VectorStore):
    """Mock implementation."""

    def __init__(self):
        self.chunks: List[Chunk] = []
        self.init_called = False

    async def init_db(self) -> None:
        self.init_called = True

    async def add_chunks(self, chunks: List[Chunk]) -> int:
        self.chunks.extend(chunks)
        return len(chunks)

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> List[Chunk]:
        return self.chunks[:top_k]

    async def get_chunks_by_doc(self, document_id: UUID) -> List[Chunk]:
        return [c for c in self.chunks if c.document_id == document_id]

    async def delete_document(self, document_id: UUID) -> int:
        initial = len(self.chunks)
        self.chunks = [c for c in self.chunks if c.document_id != document_id]
        return initial - len(self.chunks)

    async def get_stats(self) -> dict:
        return {"total_chunks": len(self.chunks), "total_documents": len(set(c.document_id for c in self.chunks))}


class TestVectorStoreContract:
    """Testes do contrato VectorStore."""

    @pytest.fixture
    def store(self):
        return MockVectorStore()

    @pytest.fixture
    def sample_chunks(self):
        doc_id = uuid4()
        return [
            Chunk(
                id=uuid4(),
                document_id=doc_id,
                content=f"Chunk {i}",
                chunk_index=i,
                page_number=1,
                start_char=i * 10,
                end_char=(i + 1) * 10,
                token_count=5,
                embedding=[0.1] * 1536,
                metadata={},
            )
            for i in range(3)
        ]

    @pytest.mark.asyncio
    async def test_init_db(self, store):
        await store.init_db()
        assert store.init_called is True

    @pytest.mark.asyncio
    async def test_add_chunks_returns_count(self, store, sample_chunks):
        count = await store.add_chunks(sample_chunks)
        assert count == 3
        assert len(store.chunks) == 3

    @pytest.mark.asyncio
    async def test_search_returns_top_k(self, store, sample_chunks):
        await store.add_chunks(sample_chunks)
        results = await store.search([0.1] * 1536, top_k=2)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_chunks_by_doc(self, store, sample_chunks):
        await store.add_chunks(sample_chunks)
        doc_id = sample_chunks[0].document_id
        results = await store.get_chunks_by_doc(doc_id)
        assert len(results) == 3
        assert all(c.document_id == doc_id for c in results)

    @pytest.mark.asyncio
    async def test_delete_document(self, store, sample_chunks):
        await store.add_chunks(sample_chunks)
        doc_id = sample_chunks[0].document_id
        count = await store.delete_document(doc_id)
        assert count == 3
        assert len(store.chunks) == 0

    @pytest.mark.asyncio
    async def test_get_stats(self, store, sample_chunks):
        await store.add_chunks(sample_chunks)
        stats = await store.get_stats()
        assert stats["total_chunks"] == 3
        assert stats["total_documents"] == 1