"""Drift Detector - Detecta degradação de métricas RAG ao longo do tempo."""

from __future__ import annotations
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import json
import logging
from pathlib import Path
import hashlib
import yaml

from anchor_rag.domain.models import DriftResult

logger = logging.getLogger(__name__)


@dataclass
class BaselineData:
    """Dados de baseline para comparação."""
    dataset_hash: str
    config_hash: str
    metrics: Dict[str, float]
    created_at: str
    eval_run_id: str

    @classmethod
    def from_json(cls, path: Path) -> "BaselineData":
        """Carrega baseline de arquivo JSON."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    def to_json(self, path: Path) -> None:
        """Salva baseline em arquivo JSON."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)


class DriftDetector:
    """Detecta drift comparando métricas atuais vs baseline.

    Baseline = hash(dataset) + hash(config) + métricas agregadas.
    Drift = queda relativa > threshold (default 10%).
    Exit codes: 0=ok, 1=drift, 2=erro.
    """

    def __init__(self, threshold: float = 0.10):
        self.threshold = threshold

    @staticmethod
    def compute_dataset_hash(dataset_path: Path) -> str:
        """Computa SHA256 do dataset (conteúdo YAML)."""
        content = dataset_path.read_bytes()
        return hashlib.sha256(content).hexdigest()[:16]

    @staticmethod
    def compute_config_hash(config_dict: Dict[str, Any]) -> str:
        """Computa SHA256 da config de avaliação relevante."""
        # Normaliza config (ordena chaves, remove campos voláteis)
        import copy
        normalized = copy.deepcopy(config_dict)
        # Remove campos que não afetam métricas
        normalized.pop("evaluation", None)  # O judge provider pode mudar
        # Serializa determinísticamente
        import json
        content = json.dumps(normalized, sort_keys=True).encode()
        return hashlib.sha256(content).hexdigest()[:16]

    def check(
        self,
        current_metrics: Dict[str, float],
        baseline_path: Path,
        threshold: Optional[float] = None,
    ) -> DriftResult:
        """Compara métricas atuais vs baseline.

        Args:
            current_metrics: Dict com faithfulness, answer_relevancy, context_precision, context_recall
            baseline_path: Path para arquivo JSON de baseline
            threshold: Override do threshold (default: self.threshold)

        Returns:
            DriftResult com has_drift, diffs, exit_code
        """
        thresh = threshold if threshold is not None else self.threshold

        try:
            baseline = BaselineData.from_json(baseline_path)
        except Exception as e:
            logger.error(f"Erro ao carregar baseline: {e}")
            return DriftResult(
                has_drift=False,
                metric_diffs={},
                threshold=thresh,
                baseline_metrics={},
                current_metrics=current_metrics,
                exit_code=2,
            )

        # Compara cada métrica
        metric_diffs = {}
        has_drift = False

        for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
            baseline_val = baseline.metrics.get(metric, 0.0)
            current_val = current_metrics.get(metric, 0.0)

            if baseline_val > 0:
                # Queda relativa: (baseline - current) / baseline
                relative_diff = (baseline_val - current_val) / baseline_val
            else:
                relative_diff = 0.0

            metric_diffs[metric] = round(relative_diff, 4)

            if relative_diff > thresh:
                has_drift = True
                logger.warning(f"Drift detectado em {metric}: {relative_diff:.2%} (threshold: {thresh:.2%})")

        exit_code = 1 if has_drift else 0

        return DriftResult(
            has_drift=has_drift,
            metric_diffs=metric_diffs,
            threshold=thresh,
            baseline_metrics=baseline.metrics,
            current_metrics=current_metrics,
            exit_code=exit_code,
        )

    def create_baseline(
        self,
        metrics: Dict[str, float],
        dataset_path: Path,
        config_dict: Dict[str, Any],
        eval_run_id: str,
        output_path: Path,
    ) -> BaselineData:
        """Cria novo baseline a partir de métricas atuais."""
        from datetime import datetime

        dataset_hash = self.compute_dataset_hash(dataset_path)
        config_hash = self.compute_config_hash(config_dict)

        baseline = BaselineData(
            dataset_hash=dataset_hash,
            config_hash=config_hash,
            metrics=metrics,
            created_at=datetime.utcnow().isoformat() + "Z",
            eval_run_id=eval_run_id,
        )

        baseline.to_json(output_path)
        logger.info(f"Baseline criado: {output_path} (dataset_hash={dataset_hash}, config_hash={config_hash})")

        return baseline


async def create_drift_detector_from_config(config) -> DriftDetector:
    """Factory a partir de AppConfig."""
    return DriftDetector(threshold=0.10)  # Configurável via eval_config no futuro