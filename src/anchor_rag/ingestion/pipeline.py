"""Pipeline de ingestão: orquestra parser -> sanitize -> chunker -> embeddings -> vector_store."""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Callable, Awaitable
from uuid import UUID, uuid4
import asyncio
import logging
import time

from anchor_rag.domain.models import Document, Chunk, IngestConfig
from anchor_rag.domain.exceptions import InvalidDocumentException, EmbeddingGenerationException, VectorStoreException
from anchor_rag.ingestion.parser import PDFParser, ParsedPage, create_parser
from anchor_rag.ingestion.chunker import Chunker, ChunkingResult
from anchor_rag.embeddings.base import EmbeddingProvider
from anchor_rag.vector_store.base import VectorStore
from anchor_rag.utils.text import sha256_file, sanitize_text

logger = logging.getLogger(__name__)


@dataclass
class IngestionStats:
    """Estatísticas da ingestão."""

    documents_processed: int = 0
    documents_skipped: int = 0
    chunks_created: int = 0
    chunks_embedded: int = 0
    chunks_stored: int = 0
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class IngestionResult:
    """Resultado da ingestão de um documento."""

    document: Document
    chunks: List[Chunk]
    stats: IngestionStats


class IngestionPipeline:
    """Orquestra o pipeline completo de ingestão."""

    def __init__(
        self,
        parser: PDFParser,
        chunker: Chunker,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
        config: Optional[IngestConfig] = None,
    ):
        self.parser = parser
        self.chunker = chunker
        self.embedder = embedder
        self.vector_store = vector_store
        self.config = config or IngestConfig()

    async def ingest(self, file_paths: List[str | Path]) -> List[IngestionResult]:
        """Ingere múltiplos arquivos."""
        await self.vector_store.init_db()
        results = []
        overall_stats = IngestionStats()
        start_time = time.perf_counter()

        for path in file_paths:
            try:
                result = await self._ingest_single(Path(path))
                results.append(result)
                overall_stats.documents_processed += 1
                overall_stats.chunks_created += result.stats.chunks_created
                overall_stats.chunks_embedded += result.stats.chunks_embedded
                overall_stats.chunks_stored += result.stats.chunks_stored
                overall_stats.errors.extend(result.stats.errors)
            except Exception as e:
                logger.error(f"Erro ao ingerir {path}: {e}")
                overall_stats.documents_skipped += 1
                overall_stats.errors.append(f"{path}: {e}")

        overall_stats.duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"Ingestão concluída: {overall_stats}")
        return results

    async def _ingest_single(self, path: Path) -> IngestionResult:
        """Ingere um único arquivo."""
        stats = IngestionStats()
        doc_start = time.perf_counter()

        # 1. Hash do arquivo para dedup
        content_hash = sha256_file(str(path))

        # Verificar se já existe (buscar por hash nos metadados)
        # Nota: implementação simplificada - em produção usar índice de hash

        # 2. Parse PDF
        pages = self.parser.parse(path)
        full_text = "\n\n".join(p.text for p in pages)
        page_texts = [p.text for p in pages]

        # 3. Sanitização
        sanitized_text = sanitize_text(full_text)

        # 4. Chunking
        document_id = uuid4()
        chunk_result: ChunkingResult = self.chunker.chunk_document(
            document_id=document_id,
            full_text=sanitized_text,
            page_texts=page_texts,
        )
        stats.chunks_created = chunk_result.total_chunks

        # 5. Embeddings (batch)
        chunks = chunk_result.chunks
        if chunks:
            texts = [c.content for c in chunks]
            try:
                embeddings = await self.embedder.embed_batch(texts)
                for chunk, embedding in zip(chunks, embeddings):
                    chunk.embedding = embedding
                stats.chunks_embedded = len(chunks)
            except Exception as e:
                logger.error(f"Erro ao gerar embeddings: {e}")
                raise EmbeddingGenerationException(f"Falha ao gerar embeddings: {e}")

        # 6. Vector Store
        try:
            stored = await self.vector_store.add_chunks(chunks)
            stats.chunks_stored = stored
        except Exception as e:
            logger.error(f"Erro ao armazenar no vector store: {e}")
            raise VectorStoreException(f"Falha ao armazenar chunks: {e}")

        # 7. Criar Document
        document = Document(
            id=document_id,
            path=str(path),
            filename=path.name,
            content_hash=content_hash,
            page_count=len(pages),
            metadata={"parser": type(self.parser).__name__},
        )

        stats.duration_ms = (time.perf_counter() - doc_start) * 1000
        return IngestionResult(document=document, chunks=chunks, stats=stats)

    async def ingest_directory(
        self,
        directory: str | Path,
        recursive: bool = False,
        pattern: str = "*.pdf",
    ) -> List[IngestionResult]:
        """Ingere todos os PDFs de um diretório."""
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            raise InvalidDocumentException(f"Diretório não encontrado: {directory}")

        if recursive:
            files = list(path.rglob(pattern))
        else:
            files = list(path.glob(pattern))

        logger.info(f"Encontrados {len(files)} arquivos em {directory}")
        return await self.ingest(files)