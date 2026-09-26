"""Testes unitários para modelos Pydantic."""

import pytest
from uuid import UUID
from datetime import datetime
from anchor_rag.domain.models import (
    Document,
    Chunk,
    QueryResult,
    IngestConfig,
    QueryConfig,
    ChunkUnit,
)
from pydantic import ValidationError


class TestDocument:
    def test_document_creation(self):
        doc = Document(
            path="/test/doc.pdf",
            filename="doc.pdf",
            content_hash="a" * 64,
            page_count=3,
        )
        assert isinstance(doc.id, UUID)
        assert doc.path == "/test/doc.pdf"
        assert doc.page_count == 3
        assert isinstance(doc.created_at, datetime)

    def test_document_invalid_hash(self):
        with pytest.raises(ValidationError):
            Document(
                path="/test/doc.pdf",
                filename="doc.pdf",
                content_hash="invalid",
                page_count=1,
            )

    def test_document_hash_case_insensitive(self):
        doc = Document(
            path="/test/doc.pdf",
            filename="doc.pdf",
            content_hash="A" * 64,
            page_count=1,
        )
        assert doc.content_hash == "a" * 64


class TestChunk:
    def test_chunk_creation(self):
        doc_id = UUID("12345678-1234-5678-1234-567812345678")
        chunk = Chunk(
            document_id=doc_id,
            content="Test chunk content",
            chunk_index=0,
            page_number=1,
            start_char=0,
            end_char=18,
        )
        assert isinstance(chunk.id, UUID)
        assert chunk.document_id == doc_id
        assert chunk.chunk_index == 0

    def test_chunk_negative_index_fails(self):
        doc_id = UUID("12345678-1234-5678-1234-567812345678")
        with pytest.raises(ValidationError):
            Chunk(
                document_id=doc_id,
                content="test",
                chunk_index=-1,
                start_char=0,
                end_char=4,
            )


class TestQueryResult:
    def test_query_result_defaults(self):
        result = QueryResult(answer="Test answer")
        assert result.answer == "Test answer"
        assert result.citations == []
        assert result.chunks_used == []
        assert result.scores == []
        assert result.latency_ms == {}


class TestIngestConfig:
    def test_ingest_config_defaults(self):
        config = IngestConfig()
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
        assert config.chunk_unit == ChunkUnit.TOKENS
        assert config.parser == "pdfplumber"
        assert config.force_reingest is False
        assert config.recursive is False


class TestQueryConfig:
    def test_query_config_defaults(self):
        config = QueryConfig()
        assert config.top_k == 5
        assert config.threshold == 0.7
        assert config.no_synthesis is False
        assert config.format == "text"