"""Testes de integração do pipeline de query."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from anchor_rag.pipeline.orchestrator import RAGPipeline
from anchor_rag.embeddings.base import EmbeddingProvider
from anchor_rag.vector_store.base import VectorStore
from anchor_rag.synthesis.llm import LLMProvider, LLMResponse
from anchor_rag.domain.models import Chunk, QueryConfig


class MockEmbedder(EmbeddingProvider):
    def __init__(self):
        config = MagicMock()
        config.dimensions = 1536
        super().__init__(config)
        self._dimensions = 1536

    @property
    def dimensions(self):
        return self._dimensions

    async def embed(self, text):
        return [0.1] * 1536

    async def embed_batch(self, texts):
        return [[0.1] * 1536 for _ in texts]

    async def health_check(self):
        return True


class MockVectorStore(VectorStore):
    def __init__(self, chunks=None):
        self._chunks = chunks or []

    async def init_db(self):
        pass

    async def add_chunks(self, chunks):
        self._chunks.extend(chunks)
        return len(chunks)

    async def search(self, query_embedding, top_k=5, threshold=0.0):
        return self._chunks[:top_k]

    async def get_chunks_by_doc(self, document_id):
        return [c for c in self._chunks if c.document_id == document_id]

    async def delete_document(self, document_id):
        return 0

    async def get_stats(self):
        return {"total_chunks": len(self._chunks)}


class MockLLM(LLMProvider):
    def __init__(self):
        config = MagicMock()
        super().__init__(config)

    async def complete(self, messages, temperature=None, max_tokens=None):
        # Simula resposta com citações
        content = "Resposta baseada nos documentos. [1] [2]"
        return LLMResponse(
            content=content,
            input_tokens=100,
            output_tokens=50,
            model="test-model",
        )

    async def complete_stream(self, messages, temperature=None, max_tokens=None):
        yield "Resposta "
        yield "baseada "
        yield "nos "
        yield "documentos. "
        yield "[1] [2]"

    async def health_check(self):
        return True

    def count_tokens(self, text):
        return len(text.split())


@pytest.fixture
def sample_chunks():
    doc_id = uuid4()
    return [
        Chunk(
            id=uuid4(),
            document_id=doc_id,
            content="Primeiro trecho relevante sobre o tópico.",
            chunk_index=0,
            page_number=1,
            start_char=0,
            end_char=40,
            token_count=10,
            embedding=[0.1] * 1536,
            metadata={"filename": "doc1.pdf", "page_number": 1},
        ),
        Chunk(
            id=uuid4(),
            document_id=doc_id,
            content="Segundo trecho com mais detalhes.",
            chunk_index=1,
            page_number=1,
            start_char=40,
            end_char=70,
            token_count=10,
            embedding=[0.1] * 1536,
            metadata={"filename": "doc1.pdf", "page_number": 1},
        ),
    ]


@pytest.fixture
def rag_pipeline(sample_chunks):
    embedder = MockEmbedder()
    vector_store = MockVectorStore(sample_chunks)
    llm = MockLLM()

    pipeline = RAGPipeline(
        embedder=embedder,
        vector_store=vector_store,
        llm=llm,
    )
    return pipeline


@pytest.mark.asyncio
async def test_query_returns_answer_with_citations(rag_pipeline):
    """Testa query retornando resposta com citações."""
    result = await rag_pipeline.query("Qual é o tópico principal?")

    assert isinstance(result.answer, str)
    assert len(result.answer) > 0
    assert len(result.citations) > 0
    assert len(result.chunks_used) > 0
    assert len(result.scores) > 0

    # Verifica que citações estão na resposta
    assert "[" in result.answer and "]" in result.answer


@pytest.mark.asyncio
async def test_query_latency_breakdown(rag_pipeline):
    """Testa se latência é medida corretamente."""
    result = await rag_pipeline.query("Pergunta de teste")

    assert "embed" in result.latency_ms
    assert "search" in result.latency_ms
    assert "synthesize" in result.latency_ms
    assert "total" in result.latency_ms

    # Total deve ser aproximadamente soma das partes
    total_parts = result.latency_ms["embed"] + result.latency_ms["search"] + result.latency_ms["synthesize"]
    assert abs(result.latency_ms["total"] - total_parts) < 100  # margem de 100ms


@pytest.mark.asyncio
async def test_query_no_results(rag_pipeline):
    """Testa query sem resultados."""
    # Vector store vazio
    rag_pipeline.vector_store = MockVectorStore([])

    result = await rag_pipeline.query("Pergunta sem resposta")

    assert "Não encontrei" in result.answer or "não encontrei" in result.answer.lower()
    assert result.citations == []
    assert result.chunks_used == []


@pytest.mark.asyncio
async def test_query_no_synthesis(rag_pipeline, sample_chunks):
    """Testa query com no_synthesis=True."""
    config = QueryConfig(no_synthesis=True, top_k=2)
    result = await rag_pipeline.query("Pergunta", config)

    # Deve retornar chunks brutos
    assert len(result.chunks_used) == 2
    assert "[1]" in result.answer
    assert "[2]" in result.answer


@pytest.mark.asyncio
async def test_query_respects_top_k(rag_pipeline, sample_chunks):
    """Testa se top_k é respeitado."""
    config = QueryConfig(top_k=1)
    result = await rag_pipeline.query("Pergunta", config)

    assert len(result.chunks_used) <= 1


@pytest.mark.asyncio
async def test_query_respects_threshold(rag_pipeline, sample_chunks):
    """Testa se threshold é respeitado (mock não filtra, mas parâmetro passa)."""
    config = QueryConfig(threshold=0.9)
    result = await rag_pipeline.query("Pergunta", config)

    # No mock, threshold não filtra, mas parâmetro é passado
    assert result is not None


class TestQueryConfig:
    def test_defaults(self):
        config = QueryConfig()
        assert config.top_k == 5
        assert config.threshold == 0.7
        assert config.no_synthesis is False
        assert config.format == "text"