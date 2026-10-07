"""Comparative Evaluator - Statistical comparison between LLM providers."""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import asyncio
import logging
from pathlib import Path
import yaml
import statistics

from anchor_rag.evaluation.evaluator import EvaluatorProvider, create_evaluator_provider
from anchor_rag.domain.models import ComparativeMetrics

logger = logging.getLogger(__name__)


@dataclass
class ComparativeReport:
    """Relatório de avaliação comparativa."""
    providers: List[str]
    dataset_name: str
    total_queries: int
    metrics: List[ComparativeMetrics]
    summary_table: str  # Markdown table


class ComparativeEvaluator:
    """Compara múltiplos provedores LLM na mesma avaliação.

    Executa avaliação completa (retrieval + synthesis + judge) para cada provedor
    nas mesmas queries, depois faz paired t-test e bootstrap IC 95%.
    """

    def __init__(
        self,
        judge_provider: str = "openai",
        judge_model: str = "gpt-4o-mini",
        judge_temperature: float = 0.0,
        judge_max_tokens: int = 1024,
        thresholds: Optional[Dict[str, float]] = None,
        max_refine_iterations: int = 2,
    ):
        self.judge_provider = judge_provider
        self.judge_model = judge_model
        self.judge_temperature = judge_temperature
        self.judge_max_tokens = judge_max_tokens
        self.thresholds = thresholds or {
            "faithfulness": 0.7,
            "answer_relevancy": 0.7,
            "context_precision": 0.7,
            "context_recall": 0.7,
        }
        self.max_refine_iterations = max_refine_iterations

        # Cria judge evaluator (separado dos provedores de síntese)
        self.judge = create_evaluator_provider(
            judge_provider,
            model=judge_model,
            temperature=judge_temperature,
            max_tokens=judge_max_tokens,
        )

    async def compare(
        self,
        providers: List[str],
        dataset_path: Path,
        top_k: int = 5,
        threshold: float = 0.7,
        config_path: Optional[Path] = None,
    ) -> ComparativeReport:
        """Compara provedores no mesmo dataset.

        Args:
            providers: Lista de provedores de síntese para comparar (ex: ['openai', 'ollama'])
            dataset_path: Path para dataset YAML de avaliação
            top_k: Número de chunks para retrieval
            threshold: Threshold de similaridade
            config_path: Path opcional para config.yaml

        Returns:
            ComparativeReport com estatísticas
        """
        # Carrega dataset
        dataset = self._load_dataset(dataset_path)

        # Para cada provedor, roda avaliação completa
        provider_results: Dict[str, List[Dict[str, float]]] = {}

        for provider_name in providers:
            logger.info(f"ComparativeEvaluator: avaliando {provider_name}")
            results = await self._eval_provider_on_dataset(
                provider_name, dataset, top_k, threshold, config_path
            )
            provider_results[provider_name] = results

        # Calcula estatísticas comparativas
        metrics = self._calculate_comparative_stats(providers, provider_results)

        # Gera tabela Markdown
        summary_table = self._generate_summary_table(providers, provider_results, metrics)

        return ComparativeReport(
            providers=providers,
            dataset_name=dataset_path.stem,
            total_queries=len(dataset),
            metrics=metrics,
            summary_table=summary_table,
        )

    def _load_dataset(self, path: Path) -> List[Dict[str, Any]]:
        """Carrega dataset de avaliação YAML."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("queries", [])

    async def _eval_provider_on_dataset(
        self,
        provider_name: str,
        dataset: List[Dict[str, Any]],
        top_k: int,
        threshold: float,
        config_path: Optional[Path],
    ) -> List[Dict[str, float]]:
        """Roda avaliação completa para um provedor."""
        from anchor_rag.config import AppConfig
        from anchor_rag.pipeline.orchestrator import PipelineOrchestrator
        from anchor_rag.evaluation.critique_refine import CritiqueAndRefineSynthesizer

        # Carrega config
        if config_path:
            config = AppConfig.from_yaml(config_path)
        else:
            config = AppConfig()

        # Override LLM provider para este run
        config.llm.provider = provider_name

        # Cria orchestrator
        orchestrator = PipelineOrchestrator(config)

        results = []
        for item in dataset:
            query = item["query"]
            expected_answer = item.get("expected_answer", "")

            # Executa pipeline completo (retrieval + synthesis)
            query_result = await orchestrator.query(
                query=query,
                top_k=top_k,
                threshold=threshold,
                llm_provider=provider_name,
            )

            # Avalia com judge
            context_texts = [c.content for c in query_result.chunks_used]
            scores = await self.judge.evaluate_all(query, context_texts, query_result.answer)

            result_dict = {
                "query": query,
                "expected_answer": expected_answer,
                "generated_answer": query_result.answer,
                **scores,
            }
            results.append(result_dict)

        return results

    def _calculate_comparative_stats(
        self,
        providers: List[str],
        provider_results: Dict[str, List[Dict[str, float]]],
    ) -> List[ComparativeMetrics]:
        """Calcula paired t-test e bootstrap IC 95% para cada par de provedores."""
        from scipy import stats
        import numpy as np

        metrics_names = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
        comparative_metrics = []

        # Para cada par de provedores
        for i in range(len(providers)):
            for j in range(i + 1, len(providers)):
                prov_a = providers[i]
                prov_b = providers[j]

                results_a = provider_results[prov_a]
                results_b = provider_results[prov_b]

                for metric in metrics_names:
                    values_a = [r[metric] for r in results_a]
                    values_b = [r[metric] for r in results_b]

                    # Paired t-test
                    t_stat, p_value = stats.ttest_rel(values_a, values_b)
                    mean_a = statistics.mean(values_a)
                    mean_b = statistics.mean(values_b)
                    mean_diff = mean_a - mean_b

                    # Bootstrap IC 95% (1000 resamples)
                    ci_lower, ci_upper = self._bootstrap_ci(values_a, values_b)

                    significant = p_value < 0.05

                    comparative_metrics.append(ComparativeMetrics(
                        provider_a=prov_a,
                        provider_b=prov_b,
                        metric=metric,
                        mean_a=round(mean_a, 4),
                        mean_b=round(mean_b, 4),
                        mean_diff=round(mean_diff, 4),
                        p_value=round(p_value, 4),
                        ci_95_lower=round(ci_lower, 4),
                        ci_95_upper=round(ci_upper, 4),
                        significant=significant,
                    ))

        return comparative_metrics

    def _bootstrap_ci(
        self,
        values_a: List[float],
        values_b: List[float],
        n_resamples: int = 1000,
        confidence: float = 0.95,
    ) -> Tuple[float, float]:
        """Bootstrap confidence interval para diferença de médias pareadas."""
        import numpy as np

        n = len(values_a)
        diffs = np.array(values_a) - np.array(values_b)

        bootstrap_diffs = []
        for _ in range(n_resamples):
            sample = np.random.choice(diffs, size=n, replace=True)
            bootstrap_diffs.append(np.mean(sample))

        alpha = (1 - confidence) / 2
        ci_lower = np.percentile(bootstrap_diffs, alpha * 100)
        ci_upper = np.percentile(bootstrap_diffs, (1 - alpha) * 100)

        return float(ci_lower), float(ci_upper)

    def _generate_summary_table(
        self,
        providers: List[str],
        provider_results: Dict[str, List[Dict[str, float]]],
        metrics: List[ComparativeMetrics],
    ) -> str:
        """Gera tabela Markdown resumo."""
        lines = []
        lines.append(f"Comparative Evaluation: {' vs '.join(providers)}")
        lines.append("")
        lines.append("| Metric | " + " | ".join(providers) + " | p-value | sig? | CI95 Low | CI95 Hi |")
        lines.append("|" + "|".join(["---"] * (len(providers) + 5)) + "|")

        metrics_names = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
        metric_labels = ["Faithful.", "Relevancy", "Precision", "Recall"]

        for metric, label in zip(metrics_names, metric_labels):
            row = [label]
            for prov in providers:
                vals = [r[metric] for r in provider_results[prov]]
                row.append(f"{statistics.mean(vals):.2f}")

            # Encontra metric comparativa para este metric
            comp = [m for m in metrics if m.metric == metric and m.provider_a == providers[0] and m.provider_b == providers[1]]
            if comp:
                c = comp[0]
                row.extend([
                    f"{c.p_value:.3f}",
                    "✓" if c.significant else "✗",
                    f"{c.ci_95_lower:.3f}",
                    f"{c.ci_95_upper:.3f}",
                ])
            else:
                row.extend(["-", "-", "-", "-"])

            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)


async def create_comparative_evaluator_from_config(config) -> ComparativeEvaluator:
    """Factory a partir de AppConfig."""
    eval_config = config.evaluation
    return ComparativeEvaluator(
        judge_provider=eval_config.judge_provider,
        judge_model=eval_config.judge_model,
        judge_temperature=eval_config.judge_temperature,
        judge_max_tokens=eval_config.judge_max_tokens,
        thresholds=eval_config.thresholds,
        max_refine_iterations=eval_config.max_refine_iterations,
    )