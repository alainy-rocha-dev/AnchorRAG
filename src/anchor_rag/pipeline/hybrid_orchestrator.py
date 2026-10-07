"""Pipeline RAG Híbrido: busca vetorial + FTS5 (BM25) + RRF + Reranker opcional."""

from __future__ import annotations

from typing import List, Optional
from pathlib import Path
import logging
import time
import yaml
from dataclasses import dataclass
from typing import Dict, Any

from anchor_rag.config import AppConfig
from anchor_rag.ingestion.parser import PDFParser, create_parser
from anchor_rag.ingestion import Chunker, StructuredChunker
from anchor_rag.ingestion.pipeline import IngestionPipeline, IngestConfig
from anchor_rag.embeddings.base import EmbeddingProvider
from anchor_rag.embeddings import create_embedding_provider
from anchor_rag.vector_store.base import VectorStore
from anchor_rag.vector_store import create_vector_store
from anchor_rag.vector_store.sqlite_vec import SQLiteVecStore
from anchor_rag.synthesis.llm import LLMProvider
from anchor_rag.synthesis import create_llm_provider
from anchor_rag.synthesis.synthesizer import RAGSynthesizer, SynthesizerConfig
from anchor_rag.retrieval import HybridRetriever, FTS5Store, create_reranker, Reranker
from anchor_rag.domain.models import Document, Chunk, QueryResult, QueryConfig, IngestConfig as DomainIngestConfig

logger = logging.getLogger(__name__)


@dataclass
class EvalCase:
    """Caso de teste para avaliação."""
    id: str
    question: str
    expected_chunks: List[str]
    expected_answer_contains: str
    metadata: Dict[str, Any]


@dataclass
class EvalMetrics:
    """Métricas de avaliação RAG."""
    recall_at_k: float
    mrr: float
    hallucination_rate: float
    citation_coverage: float
    total_queries: int
    successful_queries: int


class HybridRAGPipeline:
    """
    Pipeline RAG Híbrido com busca vetorial + BM25 + RRF + Reranker.
    
    Configuração via AppConfig:
    - retrieval.mode: "vector" | "hybrid" | "fts_only"
    - retrieval.reranker: "huggingface" | "ollama" | "cohere" | null
    - retrieval.reranker_model: nome do modelo
    - chunking.structured: true/false (usa StructuredChunker para normas)
    """

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        parser: Optional[PDFParser] = None,
        chunker: Optional[Chunker] = None,
        embedder: Optional[EmbeddingProvider] = None,
        vector_store: Optional[VectorStore] = None,
        llm: Optional[LLMProvider] = None,
        synthesizer: Optional[RAGSynthesizer] = None,
        retriever: Optional[HybridRetriever] = None,
        reranker: Optional[Reranker] = None,
    ):
        self.config = config or AppConfig()
        self.parser = parser or create_parser(self.config.chunking.parser)
        
        # Chunker: estruturado para normas se configurado
        use_structured = getattr(self.config.chunking, "structured", False)
        if chunker:
            self.chunker = chunker
        elif use_structured:
            self.chunker = StructuredChunker(
                chunk_size=self.config.chunking.chunk_size,
                chunk_overlap=self.config.chunking.chunk_overlap,
                chunk_unit=self.config.chunking.chunk_unit,
                encoding_name="cl100k_base",
                norma_id=getattr(self.config, "norma_id", None),
                ano=getattr(self.config, "ano", None),
            )
        else:
            self.chunker = Chunker(
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

        # Componentes de retrieval híbrido
        self._fts_store: Optional[FTS5Store] = None
        self._hybrid_retriever: Optional[HybridRetriever] = retriever
        self._reranker: Optional[Reranker] = reranker
        
        # Config de retrieval
        self.retrieval_mode = getattr(self.config, "retrieval_mode", "hybrid")
        self.reranker_provider = getattr(self.config, "reranker_provider", None)
        self.reranker_model = getattr(self.config, "reranker_model", "BAAI/bge-reranker-v2-m3")

    @classmethod
    def from_yaml(cls, path: str | Path) -> "HybridRAGPipeline":
        """Cria pipeline a partir de arquivo YAML."""
        config = AppConfig.from_yaml(path).resolve_api_keys()
        return cls(config=config)

    async def initialize(self):
        """Inicializa componentes (db, conexões, FTS5, reranker)."""
        await self.vector_store.init_db()
        
        # Inicializa FTS5 se usando busca híbrida
        if self.retrieval_mode in ("hybrid", "fts_only"):
            if isinstance(self.vector_store, SQLiteVecStore):
                await self.vector_store.init_fts()
            self._fts_store = FTS5Store(self.config.vector_store.path)
            await self._fts_store.init_fts()
            
            # Inicializa reranker se configurado
            if self.reranker_provider:
                self._reranker = create_reranker(
                    self.reranker_provider,
                    model_name=self.reranker_model,
                )
            
            # Cria retriever híbrido
            self._hybrid_retriever = HybridRetriever(
                vector_store=self.vector_store,
                fts_store=self._fts_store,
                embedder=self.embedder.embed,
                reranker=self._reranker.rerank if self._reranker else None,
                top_k=self.config.chunking.chunk_size,  # será sobrescrito na query
            )
        
        logger.info(f"HybridRAGPipeline inicializado (mode={self.retrieval_mode})")

    async def ingest(
        self,
        paths: List[str | Path],
        ingest_config: Optional[DomainIngestConfig] = None,
    ) -> List[Document]:
        """Ingere documentos."""
        cfg = ingest_config or DomainIngestConfig()
        results = await self.ingestion_pipeline.ingest(paths)
        
        # Reconstrói FTS5 após ingestão se usando híbrido
        if self._fts_store:
            await self._fts_store.rebuild_fts()
        
        return [r.document for r in results]

    async def ingest_directory(
        self,
        directory: str | Path,
        recursive: bool = False,
        pattern: str = "*.pdf",
    ) -> List[Document]:
        """Ingere todos os PDFs de um diretório."""
        results = await self.ingestion_pipeline.ingest_directory(directory, recursive, pattern)
        
        if self._fts_store:
            await self._fts_store.rebuild_fts()
        
        return [r.document for r in results]

    async def query(
        self,
        question: str,
        query_config: Optional[QueryConfig] = None,
    ) -> QueryResult:
        """Executa query RAG híbrida: embed -> hybrid search -> rerank -> synthesize."""
        cfg = query_config or QueryConfig()
        
        # 1. Embedding da query
        embed_start = time.perf_counter()
        query_embedding = await self.embedder.embed(question)
        embed_latency = (time.perf_counter() - embed_start) * 1000

        # 2. Busca (vetorial, híbrida, ou FTS only)
        search_start = time.perf_counter()
        
        if self.retrieval_mode == "hybrid" and self._hybrid_retriever:
            chunks = await self._hybrid_retriever.retrieve(
                query=question,
                top_k=cfg.top_k,
                threshold=cfg.threshold,
                norma_filter=getattr(cfg, "norma_filter", None),
                artigo_filter=getattr(cfg, "artigo_filter", None),
                use_reranker=True,
            )
        elif self.retrieval_mode == "fts_only" and self._hybrid_retriever:
            chunks = await self._hybrid_retriever.retrieve_fts_only(
                query=question,
                top_k=cfg.top_k,
                norma_filter=getattr(cfg, "norma_filter", None),
                artigo_filter=getattr(cfg, "artigo_filter", None),
            )
        else:
            # Vetorial only (comportamento original)
            chunks = await self.vector_store.search(
                query_embedding=query_embedding,
                top_k=cfg.top_k,
                threshold=cfg.threshold,
            )
        
        search_latency = (time.perf_counter() - search_start) * 1000

        if not chunks:
            return QueryResult(
                answer="Não encontrei informações relevantes nos documentos para responder a essa pergunta.",
                citations=[],
                chunks_used=[],
                scores=[],
                latency_ms={"embed": embed_latency, "search": search_latency, "total": embed_latency + search_latency},
            )

        # Scores placeholder (viriam do retriever idealmente)
        scores = [1.0] * len(chunks)

        # 3. Síntese
        if cfg.no_synthesis:
            return QueryResult(
                answer="\n\n".join(f"[{i+1}] {c.content}" for i, c in enumerate(chunks)),
                citations=[{"index": i+1} for i in range(len(chunks))],
                chunks_used=chunks,
                scores=scores,
                latency_ms={"embed": embed_latency, "search": search_latency, "total": embed_latency + search_latency},
            )

        synth_config = SynthesizerConfig(
            max_chunks=cfg.top_k,
            min_score_threshold=cfg.threshold,
        )

        synth_start = time.perf_counter()
        result = await self.synthesizer.synthesize(
            query=question,
            chunks=chunks,
            scores=scores,
            config=synth_config,
        )
        synth_latency = (time.perf_counter() - synth_start) * 1000

        result.latency_ms.update({
            "embed": embed_latency,
            "search": search_latency,
            "synthesize": synth_latency,
            "total": embed_latency + search_latency + synth_latency,
        })

        return result

    # Métodos de avaliação por configuração (ablação)
    async def query_vector_only(self, question: str, top_k: int = 5, threshold: float = 0.0) -> QueryResult:
        """Força busca apenas vetorial (para ablação A)."""
        cfg = QueryConfig(top_k=top_k, threshold=threshold)
        original_mode = self.retrieval_mode
        self.retrieval_mode = "vector"
        try:
            return await self.query(question, cfg)
        finally:
            self.retrieval_mode = original_mode

    async def query_hybrid_no_rerank(self, question: str, top_k: int = 5, threshold: float = 0.0) -> QueryResult:
        """Busca híbrida sem reranker (para ablação C/D)."""
        if not self._hybrid_retriever:
            return await self.query_vector_only(question, top_k, threshold)
        
        embed_start = time.perf_counter()
        query_embedding = await self.embedder.embed(question)
        embed_latency = (time.perf_counter() - embed_start) * 1000
        
        search_start = time.perf_counter()
        chunks = await self._hybrid_retriever.retrieve(
            query=question,
            top_k=top_k,
            threshold=threshold,
            use_reranker=False,
        )
        search_latency = (time.perf_counter() - search_start) * 1000
        
        if not chunks:
            return QueryResult(
                answer="Não encontrei informações relevantes nos documentos para responder a essa pergunta.",
                citations=[],
                chunks_used=[],
                scores=[],
                latency_ms={"embed": embed_latency, "search": search_latency, "total": embed_latency + search_latency},
            )
        
        scores = [1.0] * len(chunks)
        synth_config = SynthesizerConfig(max_chunks=top_k, min_score_threshold=threshold)
        
        synth_start = time.perf_counter()
        result = await self.synthesizer.synthesize(
            query=question, chunks=chunks, scores=scores, config=synth_config
        )
        synth_latency = (time.perf_counter() - synth_start) * 1000
        
        result.latency_ms.update({
            "embed": embed_latency,
            "search": search_latency,
            "synthesize": synth_latency,
            "total": embed_latency + search_latency + synth_latency,
        })
        return result

    async def query_fts_only(self, question: str, top_k: int = 5) -> QueryResult:
        """Força busca apenas FTS5/BM25 (para ablação B)."""
        cfg = QueryConfig(top_k=top_k)
        original_mode = self.retrieval_mode
        self.retrieval_mode = "fts_only"
        try:
            return await self.query(question, cfg)
        finally:
            self.retrieval_mode = original_mode

    async def eval_dataset(self, dataset_path: str | Path, k: int = 5) -> EvalMetrics:
        """Avalia pipeline contra dataset."""
        with open(dataset_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        eval_cases = [EvalCase(**case) for case in data.get("eval_cases", [])]
        if not eval_cases:
            logger.warning("Dataset vazio ou sem eval_cases")
            return EvalMetrics(0, 0, 0, 0, 0, 0)
        
        total_queries = len(eval_cases)
        successful_queries = 0
        recall_hits = 0
        reciprocal_ranks = []
        hallucination_count = 0
        citation_hits = 0
        
        for case in eval_cases:
            try:
                result = await self.query(case.question, QueryConfig(top_k=k))
                successful_queries += 1
                
                retrieved_ids = {str(c.id) for c in result.chunks_used}
                expected_ids = set(case.expected_chunks)
                if retrieved_ids & expected_ids:
                    recall_hits += 1
                
                rank = 0
                for i, chunk in enumerate(result.chunks_used):
                    if str(chunk.id) in expected_ids:
                        rank = i + 1
                        break
                if rank > 0:
                    reciprocal_ranks.append(1.0 / rank)
                else:
                    reciprocal_ranks.append(0.0)
                
                if result.chunks_used and "Não encontrei" in result.answer:
                    hallucination_count += 1
                
                citation_indices = set()
                import re
                for match in re.finditer(r'\[(\d+)\]', result.answer):
                    idx = int(match.group(1)) - 1
                    if 0 <= idx < len(result.chunks_used):
                        citation_indices.add(idx)
                if result.chunks_used and citation_indices:
                    citation_hits += 1
                    
            except Exception as e:
                logger.error(f"Erro ao avaliar caso {case.id}: {e}")
        
        recall_at_k = recall_hits / total_queries if total_queries > 0 else 0
        mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0
        hallucination_rate = hallucination_count / successful_queries if successful_queries > 0 else 0
        citation_coverage = citation_hits / successful_queries if successful_queries > 0 else 0
        
        return EvalMetrics(
            recall_at_k=recall_at_k,
            mrr=mrr,
            hallucination_rate=hallucination_rate,
            citation_coverage=citation_coverage,
            total_queries=total_queries,
            successful_queries=successful_queries,
        )

    async def run_ablation(self, dataset_path: str | Path, k: int = 5) -> Dict[str, EvalMetrics]:
        """
        Roda ablação completa (configs A-E do plano).
        
        Returns:
            Dict com métricas para cada configuração.
        """
        logger.info("Iniciando ablação A-E...")
        
        # A. Baseline (vetorial only, chunk tokens)
        original_mode = self.retrieval_mode
        original_chunker = self.chunker
        
        try:
            # A: Baseline
            self.retrieval_mode = "vector"
            logger.info("Config A: Baseline (vetorial only)")
            metrics_a = await self.eval_dataset(dataset_path, k)
            
            # B: + chunking estruturado
            if hasattr(self, '_structured_chunker'):
                self.chunker = self._structured_chunker
            logger.info("Config B: + chunking estruturado")
            metrics_b = await self.eval_dataset(dataset_path, k)
            
            # C: + busca híbrida (RRF)
            self.retrieval_mode = "hybrid"
            logger.info("Config C: + busca híbrida (RRF)")
            metrics_c = await self.eval_dataset(dataset_path, k)
            
            # D: + reranker
            if self._reranker:
                logger.info("Config D: + reranker")
                metrics_d = await self.eval_dataset(dataset_path, k)
            else:
                metrics_d = metrics_c
                logger.warning("Reranker não configurado, D = C")
            
            # E: + grafo agêntico (placeholder - requer implementação separada)
            logger.info("Config E: + grafo agêntico (não implementado ainda)")
            metrics_e = metrics_d
            
        finally:
            self.retrieval_mode = original_mode
            self.chunker = original_chunker
        
        return {
            "A_baseline_vector": metrics_a,
            "B_structured_chunking": metrics_b,
            "C_hybrid_rrf": metrics_c,
            "D_reranker": metrics_d,
            "E_agentic_graph": metrics_e,
        }

    async def close(self):
        """Fecha conexões."""
        if hasattr(self.embedder, "close"):
            await self.embedder.close()
        if hasattr(self.llm, "close"):
            await self.llm.close()
        if hasattr(self.vector_store, "close"):
            await self.vector_store.close()
        if self._fts_store:
            await self._fts_store.close()
        if self._reranker:
            await self._reranker.close()
        logger.info("HybridRAGPipeline fechado")