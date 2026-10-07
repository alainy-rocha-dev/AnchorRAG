"""Orquestrador do pipeline RAG completo: ingest + query + eval."""

from __future__ import annotations
from typing import List, Optional
from pathlib import Path
import logging
import time
import yaml
import uuid
from dataclasses import dataclass
from typing import Dict, Any

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
from anchor_rag.evaluation.evaluator import EvaluatorProvider, create_evaluator_provider
from anchor_rag.evaluation.critique_refine import CritiqueAndRefineSynthesizer
from anchor_rag.evaluation.drift import DriftDetector
from anchor_rag.evaluation.cost import CostEstimator, create_cost_estimator_from_config

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
                "unit": self.config.chunking.chunk_unit,
            },
        }

    async def eval_dataset(self, dataset_path: str | Path, k: int = 5) -> EvalMetrics:
        """
        Avalia pipeline contra dataset de referência.
        
        Args:
            dataset_path: Caminho para arquivo YAML com casos de teste
            k: Valor de k para recall@k
            
        Returns:
            EvalMetrics com recall@k, MRR, taxa_alucinacao, cobertura_citacoes
        """
        # Carrega dataset
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
                
                # Recall@k: verifica se algum chunk esperado foi recuperado
                # Usa IDs dos chunks recuperados vs esperados
                retrieved_ids = {str(c.id) for c in result.chunks_used}
                expected_ids = set(case.expected_chunks)
                if retrieved_ids & expected_ids:
                    recall_hits += 1
                
                # MRR: primeiro chunk relevante na posição rank
                rank = 0
                for i, chunk in enumerate(result.chunks_used):
                    if str(chunk.id) in expected_ids:
                        rank = i + 1
                        break
                if rank > 0:
                    reciprocal_ranks.append(1.0 / rank)
                else:
                    reciprocal_ranks.append(0.0)
                
                # Alucinação: resposta contém informação não nos chunks
                # Heurística: se resposta diz "Não encontrei" mas chunks foram recuperados
                if result.chunks_used and "Não encontrei" in result.answer:
                    hallucination_count += 1
                # Heurística: resposta contém termo não presente nos chunks (simplificado)
                # Em produção, usar LLM judge ou comparação semântica
                
                # Cobertura de citações: citações na resposta correspondem a chunks usados
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

    async def eval_dataset_agentic(
        self,
        dataset_path: str | Path,
        k: int = 5,
        judge_provider: str = "openai",
        judge_model: str = "gpt-4o-mini",
    ) -> dict:
        """
        Avaliação agentic com LLM-as-judge (métricas RAGAS-like).

        Args:
            dataset_path: Caminho para arquivo YAML com casos de teste
            k: Valor de k para retrieval
            judge_provider: Provedor do judge ('openai', 'ollama', 'anthropic')
            judge_model: Modelo do judge

        Returns:
            Dict com métricas agentic agregadas + por query
        """
        # Carrega dataset
        with open(dataset_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        eval_cases = [EvalCase(**case) for case in data.get("eval_cases", [])]
        if not eval_cases:
            logger.warning("Dataset vazio ou sem eval_cases")
            return {
                "faithfulness_avg": 0.0,
                "answer_relevancy_avg": 0.0,
                "context_precision_avg": 0.0,
                "context_recall_avg": 0.0,
                "total_queries": 0,
                "successful_queries": 0,
                "per_query": [],
            }

        # Cria judge evaluator
        judge = create_evaluator_provider(
            judge_provider,
            model=judge_model,
            temperature=0.0,
            max_tokens=1024,
        )

        # Cria critique-refine synthesizer
        thresholds = {
            "faithfulness": 0.7,
            "answer_relevancy": 0.7,
            "context_precision": 0.7,
            "context_recall": 0.7,
        }
        critique_synthesizer = CritiqueAndRefineSynthesizer(
            synthesizer=self.synthesizer,
            evaluator=judge,
            thresholds=thresholds,
            max_iterations=2,
        )

        total_queries = len(eval_cases)
        successful_queries = 0

        # Acumuladores para médias
        faithfulness_sum = 0.0
        relevancy_sum = 0.0
        precision_sum = 0.0
        recall_sum = 0.0

        per_query_results = []

        for case in eval_cases:
            try:
                # Query com critique-and-refine
                query_config = QueryConfig(top_k=k)

                # 1. Embedding + Search
                embed_start = time.perf_counter()
                query_embedding = await self.embedder.embed(case.question)
                embed_latency = (time.perf_counter() - embed_start) * 1000

                search_start = time.perf_counter()
                search_results = await self.vector_store.search(
                    query_embedding=query_embedding,
                    top_k=query_config.top_k,
                    threshold=query_config.threshold,
                )
                search_latency = (time.perf_counter() - search_start) * 1000

                if not search_results:
                    # Sem resultados
                    per_query_results.append({
                        "query_id": case.id,
                        "query": case.question,
                        "faithfulness": 0.0,
                        "answer_relevancy": 0.0,
                        "context_precision": 0.0,
                        "context_recall": 0.0,
                        "answer": "Não encontrei informações relevantes.",
                        "chunks_retrieved": 0,
                    })
                    continue

                chunks = search_results

                # 2. Critique-and-Refine synthesis
                synth_start = time.perf_counter()
                query_result, refine_result = await critique_synthesizer.synthesize(
                    query=case.question,
                    chunks=chunks,
                    config=query_config,
                )
                synth_latency = (time.perf_counter() - synth_start) * 1000

                successful_queries += 1

                # 3. Avalia com judge (usa scores do trail final)
                final_scores = refine_result.final_scores
                faithfulness_sum += final_scores.get("faithfulness", 0)
                relevancy_sum += final_scores.get("answer_relevancy", 0)
                precision_sum += final_scores.get("context_precision", 0)
                recall_sum += final_scores.get("context_recall", 0)

                per_query_results.append({
                    "query_id": case.id,
                    "query": case.question,
                    "faithfulness": final_scores.get("faithfulness", 0),
                    "answer_relevancy": final_scores.get("answer_relevancy", 0),
                    "context_precision": final_scores.get("context_precision", 0),
                    "context_recall": final_scores.get("context_recall", 0),
                    "answer": refine_result.final_answer,
                    "citations": refine_result.final_citations,
                    "chunks_retrieved": len(chunks),
                    "iterations": refine_result.total_iterations,
                    "stopped_reason": refine_result.stopped_reason,
                    "trail": refine_result.trail,
                    "latency_ms": {
                        "embed": embed_latency,
                        "search": search_latency,
                        "synthesize": synth_latency,
                        "total": embed_latency + search_latency + synth_latency,
                    },
                })

            except Exception as e:
                logger.error(f"Erro ao avaliar caso agentic {case.id}: {e}")
                per_query_results.append({
                    "query_id": case.id,
                    "query": case.question,
                    "error": str(e),
                    "faithfulness": 0.0,
                    "answer_relevancy": 0.0,
                    "context_precision": 0.0,
                    "context_recall": 0.0,
                })

        # Calcula médias
        n = successful_queries if successful_queries > 0 else 1
        faithfulness_avg = faithfulness_sum / n
        answer_relevancy_avg = relevancy_sum / n
        context_precision_avg = precision_sum / n
        context_recall_avg = recall_sum / n

        # Calcula custo estimado
        cost_estimator = await create_cost_estimator_from_config(self.config)
        # Estimativa simplificada
        avg_tokens = {
            "judge_input_per_metric": 1500,
            "judge_output_per_metric": 100,
            "synthesis_input": 2000,
            "synthesis_output": 500,
        }
        cost_estimate = cost_estimator.estimate_eval_run_cost(
            judge_provider=judge_provider,
            judge_model=judge_model,
            synthesis_provider=self.config.llm.provider,
            synthesis_model=self.config.llm.model,
            num_queries=total_queries,
            avg_tokens_per_query=avg_tokens,
            max_refine_iterations=2,
        )

        return {
            "faithfulness_avg": round(faithfulness_avg, 4),
            "answer_relevancy_avg": round(answer_relevancy_avg, 4),
            "context_precision_avg": round(context_precision_avg, 4),
            "context_recall_avg": round(context_recall_avg, 4),
            "total_queries": total_queries,
            "successful_queries": successful_queries,
            "per_query": per_query_results,
            "cost_estimate": {
                "total_tokens_input": cost_estimate.total_tokens_input,
                "total_tokens_output": cost_estimate.total_tokens_output,
                "estimated_cost_usd": cost_estimate.estimated_cost_usd,
                "budget_exceeded": cost_estimate.budget_exceeded,
            },
            "thresholds_used": thresholds,
            "judge_provider": judge_provider,
            "judge_model": judge_model,
        }

    async def drift_check(
        self,
        dataset_path: str | Path,
        baseline_path: str | Path,
        k: int = 5,
        judge_provider: str = "openai",
        judge_model: str = "gpt-4o-mini",
    ) -> dict:
        """
        Executa drift detection: eval agentic atual vs baseline.

        Returns:
            Dict com has_drift, metric_diffs, exit_code
        """
        # Executa eval agentic atual
        current_result = await self.eval_dataset_agentic(
            dataset_path=dataset_path,
            k=k,
            judge_provider=judge_provider,
            judge_model=judge_model,
        )

        current_metrics = {
            "faithfulness": current_result["faithfulness_avg"],
            "answer_relevancy": current_result["answer_relevancy_avg"],
            "context_precision": current_result["context_precision_avg"],
            "context_recall": current_result["context_recall_avg"],
        }

        # Drift check
        detector = DriftDetector(threshold=0.10)
        drift_result = detector.check(current_metrics, Path(baseline_path))

        return {
            "has_drift": drift_result.has_drift,
            "metric_diffs": drift_result.metric_diffs,
            "threshold": drift_result.threshold,
            "baseline_metrics": drift_result.baseline_metrics,
            "current_metrics": drift_result.current_metrics,
            "exit_code": drift_result.exit_code,
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