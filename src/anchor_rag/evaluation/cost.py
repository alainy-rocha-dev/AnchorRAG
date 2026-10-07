"""Cost Estimator - Calcula custo USD de avaliação baseado em tokens."""

from __future__ import annotations
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import logging

from anchor_rag.domain.models import CostEstimate

logger = logging.getLogger(__name__)


# Tabela de pricing padrão ($/1M tokens) - atualizar conforme necessário
DEFAULT_PRICING_TABLE: Dict[str, Dict[str, Dict[str, float]]] = {
    "openai": {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    },
    "anthropic": {
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
        "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
        "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    },
    "ollama": {},  # Local = custo 0 (hardware próprio)
}


@dataclass
class TokenUsage:
    """Uso de tokens por componente."""
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    component: str  # "judge", "synthesis", "embedding"


class CostEstimator:
    """Estima custo USD de runs de avaliação."""

    def __init__(
        self,
        pricing_table: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None,
        budget_usd: float = 0.50,
    ):
        self.pricing_table = pricing_table or DEFAULT_PRICING_TABLE
        self.budget_usd = budget_usd

    def get_model_price(self, provider: str, model: str) -> Dict[str, float]:
        """Obtém pricing para um modelo específico."""
        provider_pricing = self.pricing_table.get(provider, {})
        return provider_pricing.get(model, {"input": 0.0, "output": 0.0})

    def estimate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calcula custo estimado para uma chamada."""
        price = self.get_model_price(provider, model)
        cost = (input_tokens / 1_000_000) * price.get("input", 0) + \
               (output_tokens / 1_000_000) * price.get("output", 0)
        return round(cost, 6)

    def estimate_eval_run_cost(
        self,
        judge_provider: str,
        judge_model: str,
        synthesis_provider: str,
        synthesis_model: str,
        num_queries: int,
        avg_tokens_per_query: Dict[str, int],
        max_refine_iterations: int = 2,
    ) -> CostEstimate:
        """Estima custo total de um eval run.

        Args:
            judge_provider/model: Provedor/modelo do judge
            synthesis_provider/model: Provedor/modelo da síntese
            num_queries: Número de queries no dataset
            avg_tokens_per_query: Dict com chaves:
                - judge_input_per_metric: tokens de entrada por métrica do judge
                - judge_output_per_metric: tokens de saída por métrica do judge
                - synthesis_input: tokens de entrada da síntese
                - synthesis_output: tokens de saída da síntese
            max_refine_iterations: Máximo iterações de refine (padrão 2 = 3 chamadas total)

        Returns:
            CostEstimate com breakdown
        """
        # 4 métricas do judge por query
        judge_metrics = 4

        # Tokens do judge (4 métricas × queries × iterações)
        # Base: 1 iteração + refine_iterations
        total_judge_calls = num_queries * judge_metrics * (1 + max_refine_iterations)

        judge_input_per_call = avg_tokens_per_query.get("judge_input_per_metric", 1500)
        judge_output_per_call = avg_tokens_per_query.get("judge_output_per_metric", 100)

        judge_total_input = total_judge_calls * judge_input_per_call
        judge_total_output = total_judge_calls * judge_output_per_call

        judge_cost = self.estimate_cost(judge_provider, judge_model, judge_total_input, judge_total_output)

        # Tokens da síntese (1 + refine_iterations chamadas por query)
        total_synthesis_calls = num_queries * (1 + max_refine_iterations)

        synthesis_input_per_call = avg_tokens_per_query.get("synthesis_input", 2000)
        synthesis_output_per_call = avg_tokens_per_query.get("synthesis_output", 500)

        synthesis_total_input = total_synthesis_calls * synthesis_input_per_call
        synthesis_total_output = total_synthesis_calls * synthesis_output_per_call

        synthesis_cost = self.estimate_cost(synthesis_provider, synthesis_model, synthesis_total_input, synthesis_total_output)

        total_cost = judge_cost + synthesis_cost

        # Breakdown por query
        per_query = []
        for q in range(num_queries):
            q_cost = (judge_cost + synthesis_cost) / num_queries
            per_query.append({
                "query_index": q,
                "estimated_cost_usd": round(q_cost, 6),
                "judge_cost_usd": round(judge_cost / num_queries, 6),
                "synthesis_cost_usd": round(synthesis_cost / num_queries, 6),
            })

        return CostEstimate(
            total_tokens_input=judge_total_input + synthesis_total_input,
            total_tokens_output=judge_total_output + synthesis_total_output,
            estimated_cost_usd=round(total_cost, 6),
            per_query=per_query,
            budget_exceeded=total_cost > self.budget_usd,
        )

    def estimate_from_actual_usage(
        self,
        usage_log: List[TokenUsage],
    ) -> CostEstimate:
        """Calcula custo real a partir de log de uso de tokens."""
        total_input = 0
        total_output = 0
        total_cost = 0.0
        per_query = []

        # Agrupa por query_index se disponível
        from collections import defaultdict
        by_query = defaultdict(list)

        for usage in usage_log:
            key = usage.component  # Simplificado: agrupa por componente
            by_query[key].append(usage)

        for component, usages in by_query.items():
            comp_input = sum(u.input_tokens for u in usages)
            comp_output = sum(u.output_tokens for u in usages)
            comp_cost = sum(
                self.estimate_cost(u.provider, u.model, u.input_tokens, u.output_tokens)
                for u in usages
            )
            total_input += comp_input
            total_output += comp_output
            total_cost += comp_cost
            per_query.append({
                "component": component,
                "input_tokens": comp_input,
                "output_tokens": comp_output,
                "estimated_cost_usd": round(comp_cost, 6),
            })

        return CostEstimate(
            total_tokens_input=total_input,
            total_tokens_output=total_output,
            estimated_cost_usd=round(total_cost, 6),
            per_query=per_query,
            budget_exceeded=total_cost > self.budget_usd,
        )

    def check_budget(self, estimated_cost: float) -> Tuple[bool, str]:
        """Verifica se custo excede orçamento."""
        if estimated_cost > self.budget_usd:
            return False, f"Custo estimado ${estimated_cost:.4f} excede orçamento ${self.budget_usd:.2f}"
        return True, f"Custo estimado ${estimated_cost:.4f} dentro do orçamento ${self.budget_usd:.2f}"


async def create_cost_estimator_from_config(config) -> CostEstimator:
    """Factory a partir de AppConfig."""
    eval_config = config.evaluation
    pricing = eval_config.pricing_table if eval_config.pricing_table else DEFAULT_PRICING_TABLE
    return CostEstimator(
        pricing_table=pricing,
        budget_usd=eval_config.cost_budget_usd,
    )