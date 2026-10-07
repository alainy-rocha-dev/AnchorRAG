"""Integration tests for ComparativeEvaluator."""

from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import yaml

from anchor_rag.evaluation.comparative import ComparativeEvaluator, ComparativeReport
from anchor_rag.evaluation.evaluator import EvaluatorProvider


class MockEvaluator(EvaluatorProvider):
    """Mock evaluator com scores controlados."""

    def __init__(self, provider_name: str, scores: dict):
        super().__init__(model=f"mock-{provider_name}")
        self._provider_name = provider_name
        self.fixed_scores = scores
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def eval_faithfulness(self, query: str, context: List[str], answer: str) -> float:
        return self.fixed_scores.get("faithfulness", 0.7)

    async def eval_answer_relevancy(self, query: str, answer: str) -> float:
        return self.fixed_scores.get("answer_relevancy", 0.7)

    async def eval_context_precision(self, query: str, context: List[str], answer: str) -> float:
        return self.fixed_scores.get("context_precision", 0.7)

    async def eval_context_recall(self, query: str, context: List[str], answer: str) -> float:
        return self.fixed_scores.get("context_recall", 0.7)

    async def health_check(self) -> bool:
        return True


class MockPipeline:
    """Mock pipeline para testes comparativos."""

    def __init__(self, provider_name: str, scores: dict):
        self.provider_name = provider_name
        self.scores = scores
        self.query_count = 0

    async def query(self, question: str, query_config=None):
        from anchor_rag.domain.models import QueryResult, Chunk
        from uuid import uuid4

        self.query_count += 1
        return QueryResult(
            answer=f"Resposta de {self.provider_name} para: {question}",
            citations=[{"chunk_id": str(uuid4())}],
            chunks_used=[Chunk(
                id=uuid4(),
                document_id=uuid4(),
                content=f"Contexto para {question}",
                chunk_index=0,
                start_char=0,
                end_char=30,
                token_count=10,
            )],
            scores=[self.scores.get("faithfulness", 0.7)],
            latency_ms={"total": 100},
            metadata={},
        )


@pytest.fixture
def sample_dataset():
    """Cria dataset YAML temporário para testes."""
    data = {
        "eval_cases": [
            {
                "id": "q1",
                "question": "Qual a taxa Selic?",
                "expected_chunks": ["chunk1"],
                "expected_answer_contains": "13,75%",
                "metadata": {},
            },
            {
                "id": "q2",
                "question": "O que é o Copom?",
                "expected_chunks": ["chunk2"],
                "expected_answer_contains": "Comitê de Política Monetária",
                "metadata": {},
            },
            {
                "id": "q3",
                "question": "Qual a inflação atual?",
                "expected_chunks": ["chunk3"],
                "expected_answer_contains": "4,62%",
                "metadata": {},
            },
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(data, f)
        return Path(f.name)


class TestComparativeEvaluator:
    """Testes de integração para ComparativeEvaluator."""

    @pytest.mark.asyncio
    async def test_compare_two_providers(self, sample_dataset):
        """Deve comparar dois provedores e gerar estatísticas."""
        # Mock do judge evaluator
        mock_judge = MockEvaluator("openai", {
            "faithfulness": 0.8,
            "answer_relevancy": 0.75,
            "context_precision": 0.7,
            "context_recall": 0.8,
        })

        # Mock do create_evaluator_provider para retornar nosso judge
        with patch("anchor_rag.evaluation.comparative.create_evaluator_provider") as mock_factory:
            mock_factory.return_value = mock_judge

            # Mock do PipelineOrchestrator
            with patch("anchor_rag.evaluation.comparative.PipelineOrchestrator") as mock_pipeline_class:
                # Cria mock pipelines para cada provedor
                def create_mock_pipeline(config):
                    provider = config.llm.provider
                    scores = {
                        "openai": {"faithfulness": 0.85, "answer_relevancy": 0.82, "context_precision": 0.78, "context_recall": 0.81},
                        "ollama": {"faithfulness": 0.72, "answer_relevancy": 0.68, "context_precision": 0.65, "context_recall": 0.70},
                    }
                    mock_pipe = MockPipeline(provider, scores.get(provider, {}))
                    mock_pipe.initialize = AsyncMock()
                    mock_pipe.query = AsyncMock(side_effect=mock_pipe.query)
                    mock_pipe.close = AsyncMock()
                    return mock_pipe

                mock_pipeline_class.side_effect = create_mock_pipeline

                # Cria evaluator comparativo
                evaluator = ComparativeEvaluator(
                    judge_provider="openai",
                    judge_model="gpt-4o-mini",
                )

                # Executa comparação
                report = await evaluator.compare(
                    providers=["openai", "ollama"],
                    dataset_path=sample_dataset,
                    top_k=5,
                    threshold=0.7,
                )

                # Verificações
                assert isinstance(report, ComparativeReport)
                assert report.providers == ["openai", "ollama"]
                assert report.total_queries == 3
                assert len(report.metrics) > 0

                # Deve ter métricas para cada par de provedores × 4 métricas
                # 1 par × 4 métricas = 4 ComparativeMetrics
                assert len(report.metrics) == 4

                # Verifica estrutura das métricas
                for metric in report.metrics:
                    assert metric.provider_a in ["openai", "ollama"]
                    assert metric.provider_b in ["openai", "ollama"]
                    assert metric.metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
                    assert 0 <= metric.p_value <= 1
                    assert metric.ci_95_lower <= metric.ci_95_upper
                    assert isinstance(metric.significant, bool)

                # Verifica tabela summary
                assert "Comparative Evaluation" in report.summary_table
                assert "openai" in report.summary_table
                assert "ollama" in report.summary_table

    @pytest.mark.asyncio
    async def test_compare_three_providers(self, sample_dataset):
        """Deve comparar três provedores (3 pares × 4 métricas = 12 ComparativeMetrics)."""
        mock_judge = MockEvaluator("openai", {
            "faithfulness": 0.8, "answer_relevancy": 0.75, "context_precision": 0.7, "context_recall": 0.8,
        })

        with patch("anchor_rag.evaluation.comparative.create_evaluator_provider") as mock_factory:
            mock_factory.return_value = mock_judge

            with patch("anchor_rag.evaluation.comparative.PipelineOrchestrator") as mock_pipeline_class:
                def create_mock_pipeline(config):
                    provider = config.llm.provider
                    scores = {
                        "openai": {"faithfulness": 0.85, "answer_relevancy": 0.82, "context_precision": 0.78, "context_recall": 0.81},
                        "ollama": {"faithfulness": 0.72, "answer_relevancy": 0.68, "context_precision": 0.65, "context_recall": 0.70},
                        "anthropic": {"faithfulness": 0.88, "answer_relevancy": 0.85, "context_precision": 0.82, "context_recall": 0.84},
                    }
                    mock_pipe = MockPipeline(provider, scores.get(provider, {}))
                    mock_pipe.initialize = AsyncMock()
                    mock_pipe.query = AsyncMock(side_effect=mock_pipe.query)
                    mock_pipe.close = AsyncMock()
                    return mock_pipe

                mock_pipeline_class.side_effect = create_mock_pipeline

                evaluator = ComparativeEvaluator(judge_provider="openai")
                report = await evaluator.compare(
                    providers=["openai", "ollama", "anthropic"],
                    dataset_path=sample_dataset,
                    top_k=5,
                )

                # 3 provedores = 3 pares (openai-ollama, openai-anthropic, ollama-anthropic) × 4 métricas = 12
                assert len(report.metrics) == 12

    @pytest.mark.asyncio
    async def test_p_value_significance(self, sample_dataset):
        """Deve marcar significância estatística corretamente (p < 0.05)."""
        # Cenário: diferença grande = p-value baixo = significativo
        mock_judge = MockEvaluator("openai", {
            "faithfulness": 0.9, "answer_relevancy": 0.9, "context_precision": 0.9, "context_recall": 0.9,
        })

        with patch("anchor_rag.evaluation.comparative.create_evaluator_provider") as mock_factory:
            mock_factory.return_value = mock_judge

            with patch("anchor_rag.evaluation.comparative.PipelineOrchestrator") as mock_pipeline_class:
                def create_mock_pipeline(config):
                    provider = config.llm.provider
                    # openai muito melhor que ollama
                    scores = {
                        "openai": {"faithfulness": 0.95, "answer_relevancy": 0.92, "context_precision": 0.90, "context_recall": 0.93},
                        "ollama": {"faithfulness": 0.60, "answer_relevancy": 0.55, "context_precision": 0.50, "context_recall": 0.58},
                    }
                    mock_pipe = MockPipeline(provider, scores.get(provider, {}))
                    mock_pipe.initialize = AsyncMock()
                    mock_pipe.query = AsyncMock(side_effect=mock_pipe.query)
                    mock_pipe.close = AsyncMock()
                    return mock_pipe

                mock_pipeline_class.side_effect = create_mock_pipeline

                evaluator = ComparativeEvaluator(judge_provider="openai")
                report = await evaluator.compare(
                    providers=["openai", "ollama"],
                    dataset_path=sample_dataset,
                    top_k=5,
                )

                # Pelo menos faithfulness deve ser significativo (diferença grande)
                faith_metric = next(m for m in report.metrics if m.metric == "faithfulness")
                assert faith_metric.p_value < 0.05
                assert faith_metric.significant is True
                assert faith_metric.mean_diff > 0  # openai > ollama

    @pytest.mark.asyncio
    async def test_bootstrap_ci(self, sample_dataset):
        """Deve gerar IC 95% via bootstrap."""
        mock_judge = MockEvaluator("openai", {
            "faithfulness": 0.8, "answer_relevancy": 0.75, "context_precision": 0.7, "context_recall": 0.8,
        })

        with patch("anchor_rag.evaluation.comparative.create_evaluator_provider") as mock_factory:
            mock_factory.return_value = mock_judge

            with patch("anchor_rag.evaluation.comparative.PipelineOrchestrator") as mock_pipeline_class:
                def create_mock_pipeline(config):
                    provider = config.llm.provider
                    scores = {
                        "openai": {"faithfulness": 0.85, "answer_relevancy": 0.82, "context_precision": 0.78, "context_recall": 0.81},
                        "ollama": {"faithfulness": 0.72, "answer_relevancy": 0.68, "context_precision": 0.65, "context_recall": 0.70},
                    }
                    mock_pipe = MockPipeline(provider, scores.get(provider, {}))
                    mock_pipe.initialize = AsyncMock()
                    mock_pipe.query = AsyncMock(side_effect=mock_pipe.query)
                    mock_pipe.close = AsyncMock()
                    return mock_pipe

                mock_pipeline_class.side_effect = create_mock_pipeline

                evaluator = ComparativeEvaluator(judge_provider="openai")
                report = await evaluator.compare(
                    providers=["openai", "ollama"],
                    dataset_path=sample_dataset,
                    top_k=5,
                )

                # Verifica IC 95% presente
                for metric in report.metrics:
                    assert hasattr(metric, "ci_95_lower")
                    assert hasattr(metric, "ci_95_upper")
                    assert metric.ci_95_lower <= metric.mean_diff <= metric.ci_95_upper

    @pytest.mark.asyncio
    async def test_summary_table_format(self, sample_dataset):
        """Tabela summary deve ter formato Markdown válido."""
        mock_judge = MockEvaluator("openai", {
            "faithfulness": 0.8, "answer_relevancy": 0.75, "context_precision": 0.7, "context_recall": 0.8,
        })

        with patch("anchor_rag.evaluation.comparative.create_evaluator_provider") as mock_factory:
            mock_factory.return_value = mock_judge

            with patch("anchor_rag.evaluation.comparative.PipelineOrchestrator") as mock_pipeline_class:
                def create_mock_pipeline(config):
                    provider = config.llm.provider
                    scores = {
                        "openai": {"faithfulness": 0.85, "answer_relevancy": 0.82, "context_precision": 0.78, "context_recall": 0.81},
                        "ollama": {"faithfulness": 0.72, "answer_relevancy": 0.68, "context_precision": 0.65, "context_recall": 0.70},
                    }
                    mock_pipe = MockPipeline(provider, scores.get(provider, {}))
                    mock_pipe.initialize = AsyncMock()
                    mock_pipe.query = AsyncMock(side_effect=mock_pipe.query)
                    mock_pipe.close = AsyncMock()
                    return mock_pipe

                mock_pipeline_class.side_effect = create_mock_pipeline

                evaluator = ComparativeEvaluator(judge_provider="openai")
                report = await evaluator.compare(
                    providers=["openai", "ollama"],
                    dataset_path=sample_dataset,
                    top_k=5,
                )

                # Verifica formato Markdown table
                lines = report.summary_table.split("\n")
                assert lines[0].startswith("Comparative Evaluation")
                # Header row
                assert "| Metric |" in lines[2]
                assert "|---|" in lines[3]  # Separator
                # Data rows
                assert "Faithful." in report.summary_table
                assert "Relevancy" in report.summary_table
                assert "Precision" in report.summary_table
                assert "Recall" in report.summary_table