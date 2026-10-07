"""Módulo de ingestão de documentos."""

from anchor_rag.ingestion.parser import PDFParser, create_parser, PdfPlumberParser, PyPDFParser
from anchor_rag.ingestion.chunker import Chunker, ChunkingResult
from anchor_rag.ingestion.structured_chunker import StructuredChunker, LegalChunker, StructuredChunk
from anchor_rag.ingestion.pipeline import IngestionPipeline, IngestConfig

__all__ = [
    "PDFParser",
    "create_parser",
    "PdfPlumberParser",
    "PyPDFParser",
    "Chunker",
    "ChunkingResult",
    "StructuredChunker",
    "LegalChunker",
    "StructuredChunk",
    "IngestionPipeline",
    "IngestConfig",
]