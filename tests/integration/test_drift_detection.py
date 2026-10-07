"""Integration tests for DriftDetector."""

from __future__ import annotations
import pytest
from pathlib import Path
import tempfile
import json
from datetime import datetime

from anchor_rag.evaluation.drift import DriftDetector, BaselineData


class TestDriftDetector:
    """Testes de integração para DriftDetector."""

    @pytest.fixture
    def baseline_path(self):
        """Cria baseline JSON temporário."""
        baseline = BaselineData(
            dataset_hash="abc123",
            config_hash="def456",
            metrics={
                "faithfulness": 0.85,
                "answer_relevancy": 0.82,
                "context_precision": 0.78,
                "context_recall": 0.80,
            },
            created_at=datetime.utcnow().isoformat() + "Z",
            eval_run_id="run-123",
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            baseline.to_json(Path(f.name))
            yield Path(f.name)

    def test_no_drift(self, baseline_path):
        """Deve retornar exit_code=0 quando não há drift."""
        detector = DriftDetector(threshold=0.10)

        current_metrics = {
            "faithfulness": 0.84,   # -1.2% (dentro do threshold)
            "answer_relevancy": 0.81,  # -1.2%
            "context_precision": 0.77,  # -1.3%
            "context_recall": 0.79,     # -1.2%
        }

        result = detector.check(current_metrics, baseline_path)

        assert result.has_drift is False
        assert result.exit_code == 0
        assert all(abs(diff) <= 0.10 for diff in result.metric_diffs.values())

    def test_drift_detected_faithfulness(self, baseline_path):
        """Deve detectar drift em faithfulness (>10% queda)."""
        detector = DriftDetector(threshold=0.10)

        current_metrics = {
            "faithfulness": 0.74,   # -12.9% (DRIFT!)
            "answer_relevancy": 0.81,
            "context_precision": 0.77,
            "context_recall": 0.79,
        }

        result = detector.check(current_metrics, baseline_path)

        assert result.has_drift is True
        assert result.exit_code == 1
        assert result.metric_diffs["faithfulness"] > 0.10
        assert result.metric_diffs["faithfulness"] == pytest.approx(0.129, rel=0.01)

    def test_drift_detected_multiple_metrics(self, baseline_path):
        """Deve detectar drift em múltiplas métricas."""
        detector = DriftDetector(threshold=0.10)

        current_metrics = {
            "faithfulness": 0.74,   # -12.9%
            "answer_relevancy": 0.72,   # -12.2%
            "context_precision": 0.70,  # -10.3%
            "context_recall": 0.78,     # -2.5%
        }

        result = detector.check(current_metrics, baseline_path)

        assert result.has_drift is True
        assert result.exit_code == 1
        assert result.metric_diffs["faithfulness"] > 0.10
        assert result.metric_diffs["answer_relevancy"] > 0.10
        assert result.metric_diffs["context_precision"] > 0.10
        assert result.metric_diffs["context_recall"] < 0.10

    def test_improvement_not_drift(self, baseline_path):
        """Melhoria nas métricas não deve ser drift."""
        detector = DriftDetector(threshold=0.10)

        current_metrics = {
            "faithfulness": 0.90,   # +5.9% (melhoria)
            "answer_relevancy": 0.85,   # +3.7%
            "context_precision": 0.80,  # +2.6%
            "context_recall": 0.82,     # +2.5%
        }

        result = detector.check(current_metrics, baseline_path)

        assert result.has_drift is False
        assert result.exit_code == 0
        # Diffs negativos = melhoria
        assert result.metric_diffs["faithfulness"] < 0

    def test_custom_threshold(self, baseline_path):
        """Deve respeitar threshold customizado."""
        # Com threshold 5%, a queda de 1.2% em faithfulness (0.85->0.84) NÃO é drift
        detector = DriftDetector(threshold=0.05)

        current_metrics = {
            "faithfulness": 0.84,   # -1.2%
            "answer_relevancy": 0.81,
            "context_precision": 0.77,
            "context_recall": 0.79,
        }

        result = detector.check(current_metrics, baseline_path, threshold=0.05)

        assert result.has_drift is False
        assert result.exit_code == 0
        assert result.threshold == 0.05

    def test_invalid_baseline_file(self):
        """Deve retornar exit_code=2 para baseline inválido."""
        detector = DriftDetector(threshold=0.10)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json")
            invalid_path = Path(f.name)

        current_metrics = {"faithfulness": 0.8, "answer_relevancy": 0.8, "context_precision": 0.8, "context_recall": 0.8}
        result = detector.check(current_metrics, invalid_path)

        assert result.has_drift is False
        assert result.exit_code == 2
        assert result.metric_diffs == {}

    def test_missing_baseline_file(self):
        """Deve retornar exit_code=2 para arquivo inexistente."""
        detector = DriftDetector(threshold=0.10)

        current_metrics = {"faithfulness": 0.8, "answer_relevancy": 0.8, "context_precision": 0.8, "context_recall": 0.8}
        result = detector.check(current_metrics, Path("/nonexistent/baseline.json"))

        assert result.has_drift is False
        assert result.exit_code == 2

    def test_create_baseline(self):
        """Deve criar baseline a partir de métricas atuais."""
        detector = DriftDetector(threshold=0.10)

        current_metrics = {
            "faithfulness": 0.88,
            "answer_relevancy": 0.85,
            "context_precision": 0.82,
            "context_recall": 0.84,
        }

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            dataset_path = Path(f.name)

        config_dict = {
            "embedding": {"provider": "openai", "model": "text-embedding-3-small"},
            "llm": {"provider": "openai", "model": "gpt-4o-mini"},
            "chunking": {"chunk_size": 512},
        }

        baseline = detector.create_baseline(
            metrics=current_metrics,
            dataset_path=dataset_path,
            config_dict=config_dict,
            eval_run_id="test-run-456",
            output_path=dataset_path.with_suffix(".json"),
        )

        assert baseline.dataset_hash is not None
        assert baseline.config_hash is not None
        assert baseline.metrics == current_metrics
        assert baseline.eval_run_id == "test-run-456"

        # Verifica se arquivo foi criado
        output_path = dataset_path.with_suffix(".json")
        assert output_path.exists()

        # Verifica se pode ser lido de volta
        loaded = BaselineData.from_json(output_path)
        assert loaded.metrics == current_metrics
        assert loaded.eval_run_id == "test-run-456"

    def test_baseline_dataset_hash_consistency(self):
        """Hash do dataset deve ser consistente."""
        detector = DriftDetector(threshold=0.10)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("eval_cases:\n  - id: q1\n    question: test\n")
            dataset_path = Path(f.name)

        hash1 = detector.compute_dataset_hash(dataset_path)
        hash2 = detector.compute_dataset_hash(dataset_path)

        assert hash1 == hash2
        assert len(hash1) == 16  # SHA256 truncado

    def test_baseline_config_hash_consistency(self):
        """Hash da config deve ser consistente."""
        detector = DriftDetector(threshold=0.10)

        config = {"embedding": {"provider": "openai"}, "llm": {"model": "gpt-4o-mini"}}

        hash1 = detector.compute_config_hash(config)
        hash2 = detector.compute_config_hash(config)

        assert hash1 == hash2
        assert len(hash1) == 16