"""Integration tests for CritiqueAndRefineSynthesizer."""

from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List
from uuid import uuid4

from anchor_rag.domain.models import Chunk, QueryConfig, QueryResult
from anchor_rag.evaluation.critique_refine import CritiqueAndRefineSynthesizer, CritiqueAndRefineResult
from anchor_rag.evaluation.evaluator import EvaluatorProvider
from anchor_rag.synthesis.synthesizer import RAGSynthesizer


class MockEvaluator(EvaluatorProvider):
    """Mock evaluator para testes."""

    def __init__(self, scores_sequence: List[dict]):
        super().__init__(model="mock")
        self.scores_sequence = scores_sequence
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return "mock"

    async def eval_faithfulness(self, query: str, context: List[str], answer: str) -> float:
        return self._get_score("faithfulness")

    async def eval_answer_relevancy(self, query: str, answer: str) -> float:
        return self._get_score("answer_relevancy")

    async def eval_context_precision(self, query: str, context: List[str], answer: str) -> float:
        return self._get_score("context_precision")

    async def eval_context_recall(self, query: str, context: List[str], answer: str) -> float:
        return self._get_score("context_recall")

    def _get_score(self, metric: str) -> float:
        if self.call_count < len(self.scores_sequence):
            return self.scores_sequence[self.call_count].get(metric, 0.5)
        return 0.5

    async def health_check(self) -> bool:
        return True

    async def evaluate_all(self, query: str, context: List[str], answer: str) -> dict:
        self.call_count += 1
        return await super().evaluate_all(query, context, answer)


class MockSynthesizer(RAGSynthesizer):
    """Mock synthesizer para testes."""

    def __init__(self, answers: List[str]):
        super().__init__(llm_provider=None)
        self.answers = answers
        self.call_count = 0

    async def synthesize(self, query: str, chunks: List[Chunk], scores: List[float], config=None) -> QueryResult:
        answer = self.answers[self.call_count] if self.call_count < len(self.answers) else "Default answer"
        self.call_count += 1
        return QueryResult(
            answer=answer,
            citations=[{"chunk_id": str(c.id)} for c in chunks[:2]],
            chunks_used=chunks,
            scores=scores,
            latency_ms={},
            metadata={},
        )

    async def generate(self, prompt: str, temperature: float = 0.1, max_tokens: int = 1024) -> str:
        """Mock generate para critique/refine."""
        if "crítico" in prompt.lower() or "critique" in prompt.lower():
            return "A resposta anterior continha informação não suportada pelo contexto. Deve citar apenas o que está nos documentos."
        return "Resposta melhorada baseada no contexto fornecido. [1]"


@pytest.fixture
def sample_chunks():
    """Cria chunks de exemplo."""
    return [
        Chunk(
            id=uuid4(),
            document_id=uuid4(),
            content="A taxa Selic atual é 13,75% ao ano, definida pelo Copom.",
            chunk_index=0,
            start_char=0,
            end_char=50,
            token_count=20,
        ),
        Chunk(
            id=uuid4(),
            document_id=uuid4(),
            content="O Comitê de Política Monetária manteve a taxa inalterada em agosto de 2024.",
            chunk_index=1,
            start_char=50,
            end_char=120,
            token_count=25,
        ),
    ]


@pytest.fixture
def query_config():
    return QueryConfig(top_k=5, threshold=0.7)


class TestCritiqueAndRefineSynthesizer:
    """Testes de integração para CritiqueAndRefineSynthesizer."""

    @pytest.mark.asyncio
    async def test_stops_at_threshold_met(self, sample_chunks, query_config):
        """Deve parar na primeira iteração se thresholds atendidos."""
        # Scores altos na primeira avaliação
        evaluator = MockEvaluator([
            {"faithfulness": 0.9, "answer_relevancy": 0.9, "context_precision": 0.9, "context_recall": 0.9},
        ])
        synthesizer = MockSynthesizer(["Resposta inicial fiel ao contexto. [1]"])

        critique_refine = CritiqueAndRefineSynthesizer(
            synthesizer=synthesizer,
            evaluator=evaluator,
            thresholds={"faithfulness": 0.7, "answer_relevancy": 0.7, "context_precision": 0.7, "context_recall": 0.7},
            max_iterations=2,
        )

        result, trail_result = await critique_refine.synthesize(
            query="Qual a taxa Selic?",
            chunks=sample_chunks,
            config=query_config,
        )

        # Deve ter apenas 1 iteração (base)
        assert trail_result.total_iterations == 1
        assert trail_result.stopped_reason == "threshold_met"
        assert len(trail_result.trail) == 1
        assert trail_result.trail[0].iteration == 0

    @pytest.mark.asyncio
    async def test_refines_once_then_meets_threshold(self, sample_chunks, query_config):
        """Deve refinar uma vez e depois atender thresholds."""
        # Primeira avaliação baixa, segunda alta
        evaluator = MockEvaluator([
            {"faithfulness": 0.5, "answer_relevancy": 0.6, "context_precision": 0.6, "context_recall": 0.5},  # base
            {"faithfulness": 0.85, "answer_relevancy": 0.85, "context_precision": 0.8, "context_recall": 0.8},  # refine 1
        ])
        synthesizer = MockSynthesizer([
            "Resposta inicial com hallucination: Selic é 10%.",  # base
            "Resposta corrigida: A taxa Selic é 13,75%. [1]",  # refine
        ])

        critique_refine = CritiqueAndRefineSynthesizer(
            synthesizer=synthesizer,
            evaluator=evaluator,
            thresholds={"faithfulness": 0.7, "answer_relevancy": 0.7, "context_precision": 0.7, "context_recall": 0.7},
            max_iterations=2,
        )

        result, trail_result = await critique_refine.synthesize(
            query="Qual a taxa Selic?",
            chunks=sample_chunks,
            config=query_config,
        )

        # Deve ter 2 iterações (base + 1 refine)
        assert trail_result.total_iterations == 2
        assert trail_result.stopped_reason == "threshold_met"
        assert len(trail_result.trail) == 2
        assert trail_result.trail[0].iteration == 0
        assert trail_result.trail[1].iteration == 1
        assert trail_result.trail[1].improved is True
        assert trail_result.trail[1].critique is not None

    @pytest.mark.asyncio
    async def test_max_iterations_limit(self, sample_chunks, query_config):
        """Deve respeitar max_iterations (2 refinamentos = 3 total)."""
        # Scores sempre baixos
        evaluator = MockEvaluator([
            {"faithfulness": 0.4, "answer_relevancy": 0.4, "context_precision": 0.4, "context_recall": 0.4},  # base
            {"faithfulness": 0.5, "answer_relevancy": 0.5, "context_precision": 0.5, "context_recall": 0.5},  # refine 1
            {"faithfulness": 0.6, "answer_relevancy": 0.6, "context_precision": 0.6, "context_recall": 0.6},  # refine 2
        ])
        synthesizer = MockSynthesizer([
            "Resposta 1",
            "Resposta 2",
            "Resposta 3",
        ])

        critique_refine = CritiqueAndRefineSynthesizer(
            synthesizer=synthesizer,
            evaluator=evaluator,
            thresholds={"faithfulness": 0.7, "answer_relevancy": 0.7, "context_precision": 0.7, "context_recall": 0.7},
            max_iterations=2,
        )

        result, trail_result = await critique_refine.synthesize(
            query="Qual a taxa Selic?",
            chunks=sample_chunks,
            config=query_config,
        )

        # Deve ter 3 iterações (base + 2 refinamentos = max)
        assert trail_result.total_iterations == 3
        assert trail_result.stopped_reason == "max_iterations"
        assert len(trail_result.trail) == 3

    @pytest.mark.asyncio
    async def test_trail_contains_scores(self, sample_chunks, query_config):
        """Trail deve conter scores de cada iteração."""
        evaluator = MockEvaluator([
            {"faithfulness": 0.6, "answer_relevancy": 0.7, "context_precision": 0.7, "context_recall": 0.6},
            {"faithfulness": 0.8, "answer_relevancy": 0.8, "context_precision": 0.8, "context_recall": 0.8},
        ])
        synthesizer = MockSynthesizer(["Resposta 1", "Resposta 2"])

        critique_refine = CritiqueAndRefineSynthesizer(
            synthesizer=synthesizer,
            evaluator=evaluator,
            thresholds={"faithfulness": 0.7, "answer_relevancy": 0.7, "context_precision": 0.7, "context_recall": 0.7},
            max_iterations=2,
        )

        result, trail_result = await critique_refine.synthesize(
            query="Qual a taxa Selic?",
            chunks=sample_chunks,
            config=query_config,
        )

        # Verifica trail
        assert len(trail_result.trail) == 2
        for step in trail_result.trail:
            assert "faithfulness" in step.scores
            assert "answer_relevancy" in step.scores
            assert "context_precision" in step.scores
            assert "context_recall" in step.scores
            assert 0 <= step.scores["faithfulness"] <= 1

    @pytest.mark.asyncio
    async def test_returns_best_result_not_last(self, sample_chunks, query_config):
        """Deve retornar o melhor resultado (maior soma de scores), não o último."""
        # Base: médio, Refine 1: melhor, Refine 2: pior
        evaluator = MockEvaluator([
            {"faithfulness": 0.6, "answer_relevancy": 0.6, "context_precision": 0.6, "context_recall": 0.6},  # base: sum=2.4
            {"faithfulness": 0.9, "answer_relevancy": 0.9, "context_precision": 0.9, "context_recall": 0.9},  # refine 1: sum=3.6 (MELHOR)
            {"faithfulness": 0.5, "answer_relevancy": 0.5, "context_precision": 0.5, "context_recall": 0.5},  # refine 2: sum=2.0
        ])
        synthesizer = MockSynthesizer(["Resposta base", "Resposta melhor", "Resposta pior"])

        critique_refine = CritiqueAndRefineSynthesizer(
            synthesizer=synthesizer,
            evaluator=evaluator,
            thresholds={"faithfulness": 0.7, "answer_relevancy": 0.7, "context_precision": 0.7, "context_recall": 0.7},
            max_iterations=2,
        )

        result, trail_result = await critique_refine.synthesize(
            query="Qual a taxa Selic?",
            chunks=sample_chunks,
            config=query_config,
        )

        # Deve retornar a resposta do refine 1 (melhor)
        assert "melhor" in result.answer.lower() or trail_result.final_scores["faithfulness"] == 0.9

    @pytest.mark.asyncio
    async def test_llm_calls_count(self, sample_chunks, query_config):
        """Total de chamadas LLM deve ser <= 3 (1 base + 2 refinamentos)."""
        evaluator = MockEvaluator([
            {"faithfulness": 0.4, "answer_relevancy": 0.4, "context_precision": 0.4, "context_recall": 0.4},
            {"faithfulness": 0.5, "answer_relevancy": 0.5, "context_precision": 0.5, "context_recall": 0.5},
            {"faithfulness": 0.6, "answer_relevancy": 0.6, "context_precision": 0.6, "context_recall": 0.6},
        ])
        synthesizer = MockSynthesizer(["R1", "R2", "R3"])

        critique_refine = CritiqueAndRefineSynthesizer(
            synthesizer=synthesizer,
            evaluator=evaluator,
            thresholds={"faithfulness": 0.7, "answer_relevancy": 0.7, "context_precision": 0.7, "context_recall": 0.7},
            max_iterations=2,
        )

        # Conta chamadas ao sintetizador
        initial_synthesize_calls = synthesizer.call_count

        await critique_refine.synthesize(
            query="Qual a taxa Selic?",
            chunks=sample_chunks,
            config=query_config,
        )

        # Deve chamar synthesize 3 vezes (base + 2 refinamentos)
        assert synthesizer.call_count - initial_synthesize_calls == 3

        # Judge chamado 3 vezes (1 por iteração × 4 métricas cada = 12 calls to evaluate_all, mas 3 iterações)
        assert evaluator.call_count == 3