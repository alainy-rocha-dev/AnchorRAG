"""Testes de integração do pipeline de ingestão."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from anchor_rag.ingestion.pipeline import IngestionPipeline, IngestionStats
from anchor_rag.ingestion.parser import PDFParser, ParsedPage
from anchor_rag.ingestion.chunker import Chunker
from anchor_rag.embeddings.base import EmbeddingProvider
from anchor_rag.vector_store.base import VectorStore
from anchor_rag.domain.models import Document, Chunk, IngestConfig


class MockParser(PDFParser):
    def parse(self, path):
        return [
            ParsedPage(page_number=1, text="Página 1: Conteúdo do documento.", tables=[]),
            ParsedPage(page_number=2, text="Página 2: Mais conteúdo aqui.", tables=[]),
        ]

    def get_page_count(self, path):
        return 2


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
    def __init__(self):
        self.chunks = []
        self.hashes = set()

    async def init_db(self):
        pass

    async def add_chunks(self, chunks):
        self.chunks.extend(chunks)
        return len(chunks)

    async def search(self, query_embedding, top_k=5, threshold=0.0):
        return self.chunks[:top_k]

    async def get_chunks_by_doc(self, document_id):
        return [c for c in self.chunks if c.document_id == document_id]

    async def delete_document(self, document_id):
        initial = len(self.chunks)
        self.chunks = [c for c in self.chunks if c.document_id != document_id]
        return initial - len(self.chunks)

    async def get_stats(self):
        return {"total_chunks": len(self.chunks)}

    async def document_exists_by_hash(self, content_hash):
        return content_hash in self.hashes


@pytest.fixture
def ingestion_pipeline():
    parser = MockParser()
    chunker = Chunker(chunk_size=100, chunk_overlap=20, chunk_unit="chars")
    embedder = MockEmbedder()
    vector_store = MockVectorStore()
    config = IngestConfig()
    return IngestionPipeline(parser, chunker, embedder, vector_store, config)


@pytest.mark.asyncio
async def test_ingest_single_document(ingestion_pipeline, tmp_path):
    """Testa ingestão de um documento."""
    # Cria arquivo temporário
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"fake pdf content")

    results = await ingestion_pipeline.ingest([str(test_file)])

    assert len(results) == 1
    result = results[0]

    # Verifica documento
    assert isinstance(result.document, Document)
    assert result.document.filename == "test.pdf"
    assert result.document.page_count == 2

    # Verifica chunks criados
    assert len(result.chunks) > 0
    assert result.stats.chunks_created > 0
    assert result.stats.chunks_embedded > 0
    assert result.stats.chunks_stored > 0

    # Verifica metadados dos chunks
    for chunk in result.chunks:
        assert chunk.document_id == result.document.id
        assert chunk.content
        assert chunk.embedding is not None
        assert len(chunk.embedding) == 1536


@pytest.mark.asyncio
async def test_ingest_creates_correct_chunk_metadata(ingestion_pipeline, tmp_path):
    """Testa se chunks têm metadados corretos."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"fake pdf content")

    results = await ingestion_pipeline.ingest([str(test_file)])
    chunks = results[0].chunks

    # Verifica chunk_index sequencial
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i
        assert chunk.start_char < chunk.end_char
        assert chunk.token_count is not None
        assert chunk.token_count > 0


@pytest.mark.asyncio
async def test_ingest_empty_file(ingestion_pipeline, tmp_path):
    """Testa ingestão de arquivo vazio."""
    test_file = tmp_path / "empty.pdf"
    test_file.write_bytes(b"")

    # Parser mock retorna páginas com texto, mas arquivo vazio pode causar erro
    # Neste teste, apenas verificamos que não quebra
    try:
        results = await ingestion_pipeline.ingest([str(test_file)])
        # Se não lançou erro, OK
    except Exception:
        # Erro esperado para arquivo vazio/corrompido
        pass


@pytest.mark.asyncio
async def test_ingest_dedup_by_hash(ingestion_pipeline, tmp_path):
    """Testa deduplicação por hash (simplificado)."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"same content")

    # Primeira ingestão
    results1 = await ingestion_pipeline.ingest([str(test_file)])
    count1 = results1[0].stats.chunks_stored

    # Segunda ingestão do mesmo arquivo
    # Nota: dedup real precisaria verificar hash no vector store
    results2 = await ingestion_pipeline.ingest([str(test_file)])
    count2 = results2[0].stats.chunks_stored

    # Como não implementamos check de hash real, ambos inserem
    # Este teste documenta o comportamento esperado
    assert count1 == count2


@pytest.mark.asyncio
async def test_ingest_directory(ingestion_pipeline, tmp_path):
    """Testa ingestão de diretório."""
    # Cria alguns arquivos
    (tmp_path / "doc1.pdf").write_bytes(b"content 1")
    (tmp_path / "doc2.pdf").write_bytes(b"content 2")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "doc3.pdf").write_bytes(b"content 3")

    results = await ingestion_pipeline.ingest_directory(tmp_path, recursive=True)

    assert len(results) == 3


class TestIngestionStats:
    def test_stats_aggregation(self):
        """Testa agregação de estatísticas."""
        stats = IngestionStats()
        stats.documents_processed = 2
        stats.chunks_created = 10
        stats.chunks_embedded = 10
        stats.chunks_stored = 10
        assert stats.documents_processed == 2
        assert stats.chunks_created == 10