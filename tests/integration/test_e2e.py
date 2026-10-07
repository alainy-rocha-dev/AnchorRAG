"""Testes end-to-end do pipeline RAG completo."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import tempfile
import os

from anchor_rag.pipeline.orchestrator import RAGPipeline
from anchor_rag.embeddings.base import EmbeddingProvider
from anchor_rag.vector_store.base import VectorStore
from anchor_rag.synthesis.llm import LLMProvider, LLMResponse
from anchor_rag.ingestion.parser import PDFParser, ParsedPage
from anchor_rag.ingestion.chunker import Chunker
from anchor_rag.domain.models import Chunk, QueryConfig, IngestConfig


class MockParser(PDFParser):
    def parse(self, path):
        return [
            ParsedPage(page_number=1, text="O projeto HAG 2 é um pipeline RAG para ingestão de documentos.", tables=[]),
            ParsedPage(page_number=2, text="Ele usa sqlite-vec para busca vetorial e suporta múltiplos provedores de embedding.", tables=[]),
            ParsedPage(page_number=3, text="A síntese usa ancoragem estrita para evitar alucinações.", tables=[]),
        ]

    def get_page_count(self, path):
        return 3


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
        # Embedding determinístico baseado no texto
        hash_val = hash(text) % 1000
        return [float(hash_val) / 1000.0] * 1536

    async def embed_batch(self, texts):
        return [await self.embed(t) for t in texts]

    async def health_check(self):
        return True


class MockVectorStore(VectorStore):
    def __init__(self):
        self.chunks = []
        self.hashes = set()

    async def init_db(self):
        pass

    async def add_chunks(self, chunks):
        self.chunks.extend(chunks)
        return len(chunks)

    async def search(self, query_embedding, top_k=5, threshold=0.0):
        # Retorna todos os chunks se query_embedding não vazio
        if query_embedding:
            return self.chunks[:top_k]
        return []

    async def get_chunks_by_doc(self, document_id):
        return [c for c in self.chunks if c.document_id == document_id]

    async def delete_document(self, document_id):
        return 0

    async def get_stats(self):
        return {"total_chunks": len(self.chunks)}

    async def document_exists_by_hash(self, content_hash):
        return content_hash in self.hashes


class MockLLM(LLMProvider):
    def __init__(self):
        config = MagicMock()
        super().__init__(config)

    async def complete(self, messages, temperature=None, max_tokens=None):
        # Extrai mensagens
        system_msg = next((m for m in messages if m["role"] == "system"), {})
        user_msg = next((m for m in reversed(messages) if m["role"] == "user"), {})
        content = system_msg.get("content", "")
        user_text = user_msg.get("content", "")

        if "França" in user_text or "capital" in user_text:
            return LLMResponse(
                content="Não encontrei essa informação nos documentos fornecidos.",
                input_tokens=100,
                output_tokens=20,
                model="test-model",
            )
        elif "HAG 2" in content and "pipeline RAG" in content:
            return LLMResponse(
                content="O HAG 2 é um pipeline RAG para ingestão de documentos. [1]",
                input_tokens=200,
                output_tokens=30,
                model="test-model",
            )
        elif "sqlite-vec" in content:
            return LLMResponse(
                content="Ele usa sqlite-vec para busca vetorial. [2]",
                input_tokens=200,
                output_tokens=30,
                model="test-model",
            )
        elif "ancoragem estrita" in content:
            return LLMResponse(
                content="A síntese usa ancoragem estrita para evitar alucinações. [3]",
                input_tokens=200,
                output_tokens=30,
                model="test-model",
            )
        return LLMResponse(
            content="Não encontrei essa informação nos documentos fornecidos.",
            input_tokens=100,
            output_tokens=20,
            model="test-model",
        )

    async def complete_stream(self, messages, temperature=None, max_tokens=None):
        yield "Resposta "
        yield "simulada."

    async def health_check(self):
        return True

    def count_tokens(self, text):
        return len(text.split())


@pytest.fixture
def e2e_pipeline():
    """Pipeline completo com mocks."""
    parser = MockParser()
    chunker = Chunker(chunk_size=200, chunk_overlap=50, chunk_unit="chars")
    embedder = MockEmbedder()
    vector_store = MockVectorStore()
    llm = MockLLM()

    pipeline = RAGPipeline(
        parser=parser,
        chunker=chunker,
        embedder=embedder,
        vector_store=vector_store,
        llm=llm,
    )
    return pipeline


@pytest.mark.asyncio
async def test_e2e_ingest_then_query(e2e_pipeline, tmp_path):
    """Teste E2E: ingere documento e faz query."""
    # Cria arquivo PDF fake
    pdf_file = tmp_path / "hag2.pdf"
    pdf_file.write_bytes(b"fake pdf content")

    # 1. Ingestão
    documents = await e2e_pipeline.ingest([str(pdf_file)])
    assert len(documents) == 1
    assert documents[0].page_count == 3

    # Verifica se chunks foram armazenados
    stats = await e2e_pipeline.vector_store.get_stats()
    assert stats["total_chunks"] > 0

    # 2. Query sobre o conteúdo ingerido
    result = await e2e_pipeline.query("O que é o HAG 2?")

    # 3. Verifica resposta
    assert "pipeline RAG" in result.answer or "HAG 2" in result.answer
    assert len(result.citations) > 0
    assert result.latency_ms["total"] > 0


@pytest.mark.asyncio
async def test_e2e_multiple_queries(e2e_pipeline, tmp_path):
    """Teste E2E: múltiplas queries após ingestão."""
    pdf_file = tmp_path / "hag2.pdf"
    pdf_file.write_bytes(b"fake pdf content")

    await e2e_pipeline.ingest([str(pdf_file)])

    queries = [
        "O que é o HAG 2?",
        "Qual banco vetorial ele usa?",
        "Como evita alucinações?",
    ]

    for query in queries:
        result = await e2e_pipeline.query(query)
        assert len(result.answer) > 0
        assert result.latency_ms["total"] < 2000  # < 2 segundos (mock é instantâneo)


@pytest.mark.asyncio
async def test_e2e_query_nonexistent_topic(e2e_pipeline, tmp_path):
    """Teste E2E: query sobre tema não nos documentos."""
    pdf_file = tmp_path / "hag2.pdf"
    pdf_file.write_bytes(b"fake pdf content")

    await e2e_pipeline.ingest([str(pdf_file)])

    result = await e2e_pipeline.query("Qual a capital da França?")

    assert "Não encontrei" in result.answer or "não encontrei" in result.answer.lower()
    assert result.citations == []


@pytest.mark.asyncio
async def test_e2e_latency_under_2s(e2e_pipeline, tmp_path):
    """Teste E2E: latência total < 2s."""
    pdf_file = tmp_path / "hag2.pdf"
    pdf_file.write_bytes(b"fake pdf content")

    await e2e_pipeline.ingest([str(pdf_file)])

    import time
    start = time.perf_counter()
    result = await e2e_pipeline.query("O que é HAG 2?")
    elapsed = (time.perf_counter() - start) * 1000

    # Em mock é instantâneo, mas testa se métrica está presente
    assert result.latency_ms["total"] < 2000
    assert elapsed < 2000


@pytest.mark.asyncio
async def test_e2e_directory_ingest(e2e_pipeline, tmp_path):
    """Teste E2E: ingestão de diretório."""
    (tmp_path / "doc1.pdf").write_bytes(b"content 1")
    (tmp_path / "doc2.pdf").write_bytes(b"content 2")

    documents = await e2e_pipeline.ingest_directory(tmp_path)
    assert len(documents) == 2


class TestE2EWithRealComponents:
    """Testes que usariam componentes reais (marcados como slow/integration)."""

    @pytest.mark.skip(reason="Requer chaves de API e serviços rodando")
    @pytest.mark.asyncio
    async def test_e2e_real_openai(self):
        """Teste com OpenAI real - pular em CI normal."""
        pass

    @pytest.mark.skip(reason="Requer Ollama rodando localmente")
    @pytest.mark.asyncio
    async def test_e2e_real_ollama(self):
        """Teste com Ollama real."""
        pass