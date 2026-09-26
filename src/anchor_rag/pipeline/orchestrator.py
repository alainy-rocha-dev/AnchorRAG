"""Orquestrador do pipeline RAG completo: ingest + query + eval."""

from __future__ import annotations
from typing import List, Optional
from pathlib import Path
import logging
import time

from anchor_rag.config import AppConfig
from anchor_rag.ingestion.parser import PDFParser, create_parser
from anchor_rag.ingestion.chunker import Chunker
from anchor_rag.ingestion.pipeline import IngestionPipeline, IngestConfig
from anchor_rag.embeddings.base import EmbeddingProvider
from anchor_rag.embeddings import create_embedding_provider
from anchor_rag.vector_store.base import VectorStore
from anchor_rag.vector_store import create_vector_store
from anchor_rag.synthesis.llm import LLMProvider
from anchor_rag.synthesis import create_llm_provider
from anchor_rag.synthesis.synthesizer import RAGSynthesizer, SynthesizerConfig
from anchor_rag.domain.models import Document, Chunk, QueryResult, QueryConfig, IngestConfig as DomainIngestConfig

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Pipeline RAG completo: ingestão, query e avaliação."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        parser: Optional[PDFParser] = None,
        chunker: Optional[Chunker] = None,
        embedder: Optional[EmbeddingProvider] = None,
        vector_store: Optional[VectorStore] = None,
        llm: Optional[LLMProvider] = None,
        synthesizer: Optional[RAGSynthesizer] = None,
    ):
        self.config = config or AppConfig()
        self.parser = parser or create_parser(self.config.chunking.parser)
        self.chunker = chunker or Chunker(
            chunk_size=self.config.chunking.chunk_size,
            chunk_overlap=self.config.chunking.chunk_overlap,
            chunk_unit=self.config.chunking.chunk_unit,
        )
        self.embedder = embedder or create_embedding_provider(self.config.embedding)
        self.vector_store = vector_store or create_vector_store(
            "sqlite_vec",
            db_path=self.config.vector_store.path,
            embedding_dimensions=self.config.vector_store.embedding_dimensions,
        )
        self.llm = llm or create_llm_provider(self.config.llm)
        self.synthesizer = synthesizer or RAGSynthesizer(self.llm)

        self.ingestion_pipeline = IngestionPipeline(
            parser=self.parser,
            chunker=self.chunker,
            embedder=self.embedder,
            vector_store=self.vector_store,
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RAGPipeline":
        """Cria pipeline a partir de arquivo YAML."""
        config = AppConfig.from_yaml(path).resolve_api_keys()
        return cls(config=config)

    async def initialize(self):
        """Inicializa componentes (db, conexões)."""
        await self.vector_store.init_db()
        logger.info("RAGPipeline inicializado")

    async def ingest(
        self,
        paths: List[str | Path],
        ingest_config: Optional[DomainIngestConfig] = None,
    ) -> List[Document]:
        """Ingere documentos."""
        cfg = ingest_config or DomainIngestConfig()
        results = await self.ingestion_pipeline.ingest(paths)
        return [r.document for r in results]

    async def ingest_directory(
        self,
        directory: str | Path,
        recursive: bool = False,
        pattern: str = "*.pdf",
    ) -> List[Document]:
        """Ingere todos os PDFs de um diretório."""
        results = await self.ingestion_pipeline.ingest_directory(directory, recursive, pattern)
        return [r.document for r in results]

    async def query(
        self,
        question: str,
        query_config: Optional[QueryConfig] = None,
    ) -> QueryResult:
        """Executa query RAG completa: embed -> search -> synthesize."""
        cfg = query_config or QueryConfig()

        # 1. Embedding da query
        import time
        embed_start = time.perf_counter()
        query_embedding = await self.embedder.embed(question)
        embed_latency = (time.perf_counter() - embed_start) * 1000

        # 2. Busca vetorial
        search_start = time.perf_counter()
        search_results = await self.vector_store.search(
            query_embedding=query_embedding,
            top_k=cfg.top_k,
            threshold=cfg.threshold,
        )
        search_latency = (time.perf_counter() - search_start) * 1000

        if not search_results:
            return QueryResult(
                answer="Não encontrei informações relevantes nos documentos para responder a essa pergunta.",
                citations=[],
                chunks_used=[],
                scores=[],
                latency_ms={"embed": embed_latency, "search": search_latency, "total": embed_latency + search_latency},
            )

        # Extrai chunks e scores
        chunks = search_results
        scores = [1.0] * len(chunks)  # scores viriam do vector store idealmente

        # 3. Síntese (se não desabilitado)
        if cfg.no_synthesis:
            return QueryResult(
                answer="\n\n".join(f"[{i+1}] {c.content}" for i, c in enumerate(chunks)),
                citations=[{"index": i+1} for i in range(len(chunks))],
                chunks_used=chunks,
                scores=scores,
                latency_ms={"embed": embed_latency, "search": search_latency, "total": embed_latency + search_latency},
            )

        # Configura sintetizador
        synth_config = SynthesizerConfig(
            max_chunks=cfg.top_k,
            min_score_threshold=cfg.threshold,
        )

        # Override LLM se especificado
        if cfg.llm_provider or cfg.llm_model:
            # Criaria novo LLM provider - simplificado por enquanto
            pass

        synth_start = time.perf_counter()
        result = await self.synthesizer.synthesize(
            query=question,
            chunks=chunks,
            scores=scores,
            config=synth_config,
        )
        synth_latency = (time.perf_counter() - synth_start) * 1000

        # Atualiza latências
        result.latency_ms.update({
            "embed": embed_latency,
            "search": search_latency,
            "synthesize": synth_latency,
            "total": embed_latency + search_latency + synth_latency,
        })

        return result

    async def eval(self) -> dict:
        """Executa avaliação básica (placeholder para métricas futuras)."""
        stats = await self.vector_store.get_stats()
        return {
            "vector_store_stats": stats,
            "embedding_provider": self.config.embedding.provider,
            "llm_provider": self.config.llm.provider,
            "chunking": {
                "size": self.config.chunking.chunk_size,
                "overlap": self.config.chunking.chunk_overlap,
                "unit": self.config.chunking.chunk_unit.value,
            },
        }

    async def close(self):
        """Fecha conexões."""
        if hasattr(self.embedder, "close"):
            await self.embedder.close()
        if hasattr(self.llm, "close"):
            await self.llm.close()
        if hasattr(self.vector_store, "close"):
            await self.vector_store.close()
        logger.info("RAGPipeline fechado")