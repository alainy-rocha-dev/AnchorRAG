"""Critique-and-Refine Synthesizer - Agentic self-improvement loop."""

from __future__ import annotations
from typing import List, Optional, Dict, Any, Tuple
import logging
from uuid import uuid4
from dataclasses import dataclass, field

from anchor_rag.domain.models import Chunk, QueryResult, QueryConfig
from anchor_rag.synthesis.synthesizer import RAGSynthesizer
from anchor_rag.evaluation.evaluator import EvaluatorProvider

logger = logging.getLogger(__name__)


@dataclass
class RefinementStep:
    """Uma etapa de refinamento no trail."""
    iteration: int
    answer: str
    citations: List[Dict[str, Any]]
    scores: Dict[str, float]
    critique: Optional[str] = None
    improved: bool = False


@dataclass
class CritiqueAndRefineResult:
    """Resultado completo do critique-and-refine."""
    final_answer: str
    final_citations: List[Dict[str, Any]]
    final_scores: Dict[str, float]
    trail: List[RefinementStep]
    total_iterations: int
    stopped_reason: str  # "threshold_met", "max_iterations", "no_improvement"


class CritiqueAndRefineSynthesizer:
    """Wrapper sobre RAGSynthesizer que implementa critique-and-refine.

    Fluxo:
    1. Gera resposta base com RAGSynthesizer
    2. Avalia com LLM-as-judge (4 métricas)
    3. Se qualquer score < threshold: gera critique → refina resposta
    4. Repete até max 2 iterações (total 3 chamadas LLM)
    5. Retorna melhor resposta + trail completo de scores
    """

    def __init__(
        self,
        synthesizer: RAGSynthesizer,
        evaluator: EvaluatorProvider,
        thresholds: Dict[str, float],
        max_iterations: int = 2,
    ):
        self.synthesizer = synthesizer
        self.evaluator = evaluator
        self.thresholds = thresholds
        self.max_iterations = max_iterations

    async def synthesize(
        self,
        query: str,
        chunks: List[Chunk],
        config: QueryConfig,
        request_id: Optional[str] = None,
    ) -> Tuple[QueryResult, CritiqueAndRefineResult]:
        """Executa síntese com critique-and-refine.

        Returns:
            Tuple de (QueryResult final, CritiqueAndRefineResult com trail)
        """
        if request_id is None:
            request_id = str(uuid4())

        # 1. Gera resposta base
        logger.info(f"[{request_id}] critique_refine: geração base")
        base_result = await self.synthesizer.synthesize(query, chunks, config)

        # 2. Avalia resposta base
        context_texts = [c.content for c in chunks]
        base_scores = await self.evaluator.evaluate_all(query, context_texts, base_result.answer)

        trail = [
            RefinementStep(
                iteration=0,
                answer=base_result.answer,
                citations=base_result.citations,
                scores=base_scores,
            )
        ]

        # Verifica se atende thresholds
        if self._meets_thresholds(base_scores):
            logger.info(f"[{request_id}] critique_refine: thresholds atendidos na base")
            return base_result, CritiqueAndRefineResult(
                final_answer=base_result.answer,
                final_citations=base_result.citations,
                final_scores=base_scores,
                trail=trail,
                total_iterations=1,
                stopped_reason="threshold_met",
            )

        # 3. Loop de refinamento
        current_answer = base_result.answer
        current_citations = base_result.citations

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"[{request_id}] critique_refine: iteração {iteration}")

            # Gera critique
            critique = await self._generate_critique(query, context_texts, current_answer, base_scores)
            if not critique:
                logger.warning(f"[{request_id}] critique_refine: critique vazio, parando")
                break

            # Refina resposta
            refined_result = await self._refine_answer(query, chunks, config, current_answer, critique)
            if not refined_result:
                logger.warning(f"[{request_id}] critique_refine: refinamento falhou, parando")
                break

            # Avalia resposta refinada
            refined_scores = await self.evaluator.evaluate_all(query, context_texts, refined_result.answer)

            trail.append(
                RefinementStep(
                    iteration=iteration,
                    answer=refined_result.answer,
                    citations=refined_result.citations,
                    scores=refined_scores,
                    critique=critique,
                    improved=self._is_improvement(base_scores, refined_scores),
                )
            )

            # Verifica se melhorou
            if self._is_improvement(base_scores, refined_scores):
                current_answer = refined_result.answer
                current_citations = refined_result.citations
                base_scores = refined_scores

                # Verifica se atende thresholds agora
                if self._meets_thresholds(refined_scores):
                    logger.info(f"[{request_id}] critique_refine: thresholds atendidos na iteração {iteration}")
                    return refined_result, CritiqueAndRefineResult(
                        final_answer=refined_result.answer,
                        final_citations=refined_result.citations,
                        final_scores=refined_scores,
                        trail=trail,
                        total_iterations=iteration + 1,
                        stopped_reason="threshold_met",
                    )
            else:
                logger.info(f"[{request_id}] critique_refine: sem melhoria na iteração {iteration}")
                break

        # Retorna melhor resultado (último com melhoria ou base)
        best_step = max(trail, key=lambda s: sum(s.scores.values()))
        logger.info(f"[{request_id}] critique_refine: finalizado após {len(trail)} iterações, melhor iteração={best_step.iteration}")

        return QueryResult(
            answer=best_step.answer,
            citations=best_step.citations,
            chunks_used=chunks,
            scores=[best_step.scores.get("faithfulness", 0)],
            latency_ms={},
            metadata={"critique_refine_trail": [self._step_to_dict(s) for s in trail]},
        ), CritiqueAndRefineResult(
            final_answer=best_step.answer,
            final_citations=best_step.citations,
            final_scores=best_step.scores,
            trail=trail,
            total_iterations=len(trail),
            stopped_reason="max_iterations" if len(trail) > self.max_iterations else "no_improvement",
        )

    def _meets_thresholds(self, scores: Dict[str, float]) -> bool:
        """Verifica se todos os scores atendem aos thresholds."""
        for metric, threshold in self.thresholds.items():
            if scores.get(metric, 0) < threshold:
                return False
        return True

    def _is_improvement(self, old_scores: Dict[str, float], new_scores: Dict[str, float]) -> bool:
        """Verifica se houve melhoria geral (média das métricas)."""
        old_avg = sum(old_scores.values()) / len(old_scores) if old_scores else 0
        new_avg = sum(new_scores.values()) / len(new_scores) if new_scores else 0
        return new_avg > old_avg + 0.01  # Margem mínima de 1%

    async def _generate_critique(
        self,
        query: str,
        context: List[str],
        answer: str,
        scores: Dict[str, float],
    ) -> Optional[str]:
        """Gera critique apontando problemas específicos."""
        # Identifica métricas abaixo do threshold
        weak_metrics = [m for m, s in scores.items() if s < self.thresholds.get(m, 0.7)]

        if not weak_metrics:
            return None

        context_str = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(context))

        critique_prompt = (
            "Você é um crítico especializado em avaliar respostas RAG. "
            "Analise a resposta abaixo e identifique problemas específicos "
            "relacionados às métricas fracas indicadas.\n\n"
            f"Pergunta: {query}\n\n"
            f"Contexto:\n{context_str}\n\n"
            f"Resposta atual: {answer}\n\n"
            f"Métricas fracas: {', '.join(weak_metrics)}\n"
            f"Scores atuais: {scores}\n\n"
            "Produza uma crítica CONSTRUTIVA e ESPECÍFICA (máx 200 palavras) "
            "apontando exatamente o que está errado e como melhorar. "
            "Foque em: hallucination, citações faltando, informação não suportada, "
            "resposta incompleta, ou contexto mal utilizado."
        )

        try:
            # Usa o mesmo LLM do sintetizador para critique
            critique_response = await self.synthesizer.llm_provider.generate(
                prompt=critique_prompt,
                temperature=0.3,  # Levemente criativo para critique
                max_tokens=512,
            )
            return critique_response.strip()
        except Exception as e:
            logger.error(f"Erro ao gerar critique: {e}")
            return None

    async def _refine_answer(
        self,
        query: str,
        chunks: List[Chunk],
        config: QueryConfig,
        previous_answer: str,
        critique: str,
    ) -> Optional[QueryResult]:
        """Refina a resposta incorporando o critique."""
        context_str = "\n\n".join(f"[{i+1}] {c.content}" for i, c in enumerate(chunks))

        refine_prompt = (
            "Você é um especialista em melhorar respostas RAG. "
            "Reescreva a resposta incorporando o critique fornecido.\n\n"
            f"Pergunta: {query}\n\n"
            f"Contexto:\n{context_str}\n\n"
            f"Resposta anterior: {previous_answer}\n\n"
            f"Crítica: {critique}\n\n"
            "REGRAS:\n"
            "1. Use APENAS informação do contexto acima\n"
            "2. Cite fontes com [número] correspondente ao contexto\n"
            "3. Se informação não está no contexto, diga 'Não encontrei essa informação nos documentos fornecidos'\n"
            "4. Seja conciso e direto\n"
            "5. Mantenha o mesmo formato de citação\n\n"
            "Resposta melhorada:"
        )

        try:
            refined_text = await self.synthesizer.llm_provider.generate(
                prompt=refine_prompt,
                temperature=0.1,  # Baixa temperatura para consistência
                max_tokens=config.llm_model is not None and 2048 or 1024,
            )

            # Extrai citações do texto refinado (reusa lógica do sintetizador)
            citations = self._extract_citations(refined_text, chunks)

            return QueryResult(
                answer=refined_text.strip(),
                citations=citations,
                chunks_used=chunks,
                scores=[],
                latency_ms={},
                metadata={},
            )
        except Exception as e:
            logger.error(f"Erro ao refinar resposta: {e}")
            return None

    def _extract_citations(self, text: str, chunks: List[Chunk]) -> List[Dict[str, Any]]:
        """Extrai citações do texto no formato [n]."""
        import re
        citations = []
        matches = re.findall(r'\[(\d+)\]', text)
        for match in matches:
            idx = int(match) - 1
            if 0 <= idx < len(chunks):
                chunk = chunks[idx]
                citations.append({
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "page_number": chunk.page_number,
                    "snippet": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                })
        return citations

    def _step_to_dict(self, step: RefinementStep) -> Dict[str, Any]:
        """Converte step para dict serializável."""
        return {
            "iteration": step.iteration,
            "answer_preview": step.answer[:200] + "..." if len(step.answer) > 200 else step.answer,
            "scores": step.scores,
            "critique": step.critique,
            "improved": step.improved,
        }