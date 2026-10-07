"""Comando CLI: eval."""

from __future__ import annotations
from typing import Optional, List
from pathlib import Path
import asyncio
import json
import uuid
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from anchor_rag.pipeline.orchestrator import RAGPipeline, EvalMetrics
from anchor_rag.config import AppConfig
from anchor_rag.evaluation.drift import DriftDetector
from anchor_rag.evaluation.cost import CostEstimator, create_cost_estimator_from_config
from anchor_rag.evaluation.comparative import ComparativeEvaluator, create_comparative_evaluator_from_config

console = Console()


def eval_command(
    config_path: Optional[Path],
    output_format: str,
    verbose: bool,
    dataset: Optional[Path] = None,
    k: int = 5,
    # Agentic evaluation flags
    agentic: bool = False,
    judge: Optional[str] = None,
    compare: Optional[str] = None,
    drift_check: bool = False,
    baseline: Optional[Path] = None,
    output: Optional[Path] = None,
):
    """
    Executa comando de avaliação do pipeline RAG.

    Args:
        config_path: Caminho opcional para config.yaml.
        output_format: "text" para saída formatada, "json" para JSON.
        verbose: Se True, exibe configuração ativa.
        dataset: Caminho opcional para dataset YAML de avaliação (eval_dataset_bacen.yaml).
        k: Valor de k para recall@k (default 5).
        agentic: Ativa modo agentic (LLM-as-judge + métricas RAGAS-like).
        judge: Provedor judge: 'openai', 'ollama', 'anthropic' (default: config).
        compare: Lista CSV de provedores para comparative eval: 'openai,ollama'.
        drift_check: Modo drift detection (requer --baseline).
        baseline: Arquivo JSON baseline para drift check.
        output: Arquivo de saída (JSON/Markdown).
    """
    asyncio.run(_eval_async(
        config_path, output_format, verbose, dataset, k,
        agentic, judge, compare, drift_check, baseline, output
    ))


async def _eval_async(
    config_path: Optional[Path],
    output_format: str,
    verbose: bool,
    dataset: Optional[Path],
    k: int,
    agentic: bool = False,
    judge: Optional[str] = None,
    compare: Optional[str] = None,
    drift_check: bool = False,
    baseline: Optional[Path] = None,
    output: Optional[Path] = None,
):
    """
    Executa avaliação assíncrona do pipeline.

    Modos:
    - Básico: health checks + vector store stats (sem dataset)
    - Dataset: eval_dataset() com recall@k, MRR, etc.
    - Agentic: LLM-as-judge + métricas RAGAS-like (faithfulness, answer_relevancy, context_precision, context_recall)
    - Comparative: compara múltiplos provedores LLM com estatísticas (paired t-test, IC 95%)
    - Drift: compara métricas atuais vs baseline (exit code 0=ok, 1=drift, 2=erro)
    """
    # Carrega config
    if config_path:
        config = AppConfig.from_yaml(config_path).resolve_api_keys()
    else:
        config = AppConfig().resolve_api_keys()

    # Override judge provider se fornecido
    if judge:
        config.evaluation.judge_provider = judge

    pipeline = RAGPipeline(config=config)
    await pipeline.initialize()

    eval_run_id = str(uuid.uuid4())

    try:
        if verbose:
            console.print("[blue]Executando avaliação do pipeline...[/blue]")

        # Health checks
        embed_health = await pipeline.embedder.health_check()
        llm_health = await pipeline.llm.health_check()
        vector_stats = await pipeline.vector_store.get_stats()

        # Combina resultados base
        result = {
            "health_checks": {
                "embedding_provider": embed_health,
                "llm_provider": llm_health,
            },
            "vector_store": vector_stats,
            "config": {
                "embedding_provider": config.embedding.provider,
                "embedding_model": config.embedding.model,
                "embedding_dimensions": config.embedding.dimensions,
                "llm_provider": config.llm.provider,
                "llm_model": config.llm.model,
                "chunk_size": config.chunking.chunk_size,
                "chunk_overlap": config.chunking.chunk_overlap,
                "chunk_unit": config.chunking.chunk_unit.value,
                "judge_provider": config.evaluation.judge_provider,
                "judge_model": config.evaluation.judge_model,
            },
            "pipeline": {},
        }

        # === MODO DRIFT CHECK ===
        if drift_check:
            if not baseline:
                console.print("[red]Erro: --drift-check requer --baseline[/red]")
                return
            if not dataset:
                console.print("[red]Erro: --drift-check requer --dataset[/red]")
                return

            if verbose:
                console.print(f"[blue]Modo drift detection: baseline={baseline}[/blue]")

            # Executa eval agentic para obter métricas atuais
            agentic_result = await pipeline.eval_dataset_agentic(
                dataset_path=dataset,
                k=k,
                judge_provider=config.evaluation.judge_provider,
                judge_model=config.evaluation.judge_model,
            )

            # Extrai métricas agregadas
            current_metrics = {
                "faithfulness": agentic_result.get("faithfulness_avg", 0),
                "answer_relevancy": agentic_result.get("answer_relevancy_avg", 0),
                "context_precision": agentic_result.get("context_precision_avg", 0),
                "context_recall": agentic_result.get("context_recall_avg", 0),
            }

            # Drift check
            detector = DriftDetector(threshold=0.10)
            drift_result = detector.check(current_metrics, baseline)

            result["drift_check"] = {
                "has_drift": drift_result.has_drift,
                "metric_diffs": drift_result.metric_diffs,
                "threshold": drift_result.threshold,
                "baseline_metrics": drift_result.baseline_metrics,
                "current_metrics": drift_result.current_metrics,
                "exit_code": drift_result.exit_code,
            }

            # Output
            if output_format == "json":
                output_data = {"drift_check": result["drift_check"]}
                if output:
                    output.write_text(json.dumps(output_data, indent=2, ensure_ascii=False))
                else:
                    console.print(json.dumps(output_data, indent=2, ensure_ascii=False))
            else:
                if drift_result.has_drift:
                    console.print("[bold red]DRIFT DETECTED[/bold red]")
                    for metric, diff in drift_result.metric_diffs.items():
                        if diff > drift_result.threshold:
                            console.print(f"  {metric}: {diff:.2%} (baseline: {drift_result.baseline_metrics.get(metric, 0):.2f} → current: {drift_result.current_metrics.get(metric, 0):.2f})")
                else:
                    console.print("[bold green]OK - Sem drift detectado[/bold green]")

            # Exit code para CI/CD
            import sys
            sys.exit(drift_result.exit_code)

        # === MODO COMPARATIVE ===
        if compare:
            if not dataset:
                console.print("[red]Erro: --compare requer --dataset[/red]")
                return

            providers = [p.strip() for p in compare.split(",")]
            if verbose:
                console.print(f"[blue]Modo comparative: {providers}[/blue]")

            comparative_eval = await create_comparative_evaluator_from_config(config)
            report = await comparative_eval.compare(
                providers=providers,
                dataset_path=dataset,
                top_k=k,
                threshold=0.7,
                config_path=config_path,
            )

            result["comparative"] = {
                "providers": report.providers,
                "dataset": report.dataset_name,
                "total_queries": report.total_queries,
                "metrics": [m.__dict__ for m in report.metrics],
                "summary_table": report.summary_table,
            }

            if output_format == "json":
                output_data = {"comparative": result["comparative"]}
                if output:
                    output.write_text(json.dumps(output_data, indent=2, ensure_ascii=False))
                else:
                    console.print(json.dumps(output_data, indent=2, ensure_ascii=False))
            else:
                console.print(Panel("Comparative Evaluation", style="bold blue"))
                console.print(report.summary_table)

            return

        # === MODO AGENTIC (LLM-as-judge) ===
        if agentic:
            if not dataset:
                console.print("[red]Erro: --agentic requer --dataset[/red]")
                return

            if verbose:
                console.print(f"[blue]Modo agentic: judge={config.evaluation.judge_provider}[/blue]")

            agentic_result = await pipeline.eval_dataset_agentic(
                dataset_path=dataset,
                k=k,
                judge_provider=config.evaluation.judge_provider,
                judge_model=config.evaluation.judge_model,
            )

            result["pipeline"] = agentic_result
            result["agentic"] = True

        # === MODO DATASET PADRÃO ===
        elif dataset:
            if verbose:
                console.print(f"[blue]Carregando dataset: {dataset}[/blue]")
            metrics = await pipeline.eval_dataset(dataset, k=k)
            result["pipeline"] = _metrics_to_dict(metrics)

        # === MODO BÁSICO ===
        else:
            eval_result = await pipeline.eval()
            result["pipeline"] = eval_result

        # Adiciona custo se agentic
        if agentic and "per_query" in result["pipeline"]:
            cost_estimator = await create_cost_estimator_from_config(config)
            # O cost já vem no resultado do pipeline

        # Output
        if output_format == "json":
            if output:
                output.write_text(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                console.print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            _print_text_output(result, k, agentic)

    finally:
        await pipeline.close()


def _print_text_output(result: dict, k: int, agentic: bool):
    """Imprime saída formatada em texto."""
    console = Console()

    console.print(Panel("Avaliação do Pipeline AnchorRAG", style="bold blue"))

    # Health checks
    health_table = Table(title="Health Checks", show_header=True)
    health_table.add_column("Componente", style="cyan")
    health_table.add_column("Status", style="green")
    health_table.add_row("Embedding Provider", "✓ OK" if result["health_checks"]["embedding_provider"] else "✗ FALHOU")
    health_table.add_row("LLM Provider", "✓ OK" if result["health_checks"]["llm_provider"] else "✗ FALHOU")
    console.print(health_table)

    # Vector store stats
    vs_table = Table(title="Vector Store", show_header=True)
    vs_table.add_column("Métrica", style="cyan")
    vs_table.add_column("Valor", style="yellow")
    for key, value in result["vector_store"].items():
        vs_table.add_row(key.replace("_", " ").title(), str(value))
    console.print(vs_table)

    # Métricas
    pipeline = result["pipeline"]

    if agentic and "faithfulness_avg" in pipeline:
        # Métricas agentic
        metrics_table = Table(title=f"Métricas Agentic RAGAS-like (k={k})", show_header=True)
        metrics_table.add_column("Métrica", style="cyan")
        metrics_table.add_column("Valor", style="yellow")
        metrics_table.add_row("Faithfulness", f"{pipeline.get('faithfulness_avg', 0):.4f}")
        metrics_table.add_row("Answer Relevancy", f"{pipeline.get('answer_relevancy_avg', 0):.4f}")
        metrics_table.add_row("Context Precision", f"{pipeline.get('context_precision_avg', 0):.4f}")
        metrics_table.add_row("Context Recall", f"{pipeline.get('context_recall_avg', 0):.4f}")
        metrics_table.add_row("Total Queries", str(pipeline.get('total_queries', 0)))
        metrics_table.add_row("Successful", str(pipeline.get('successful_queries', 0)))
        console.print(metrics_table)

        # Resumo
        summary_text = Text()
        summary_text.append("Faithfulness: ", style="cyan")
        summary_text.append(f"{pipeline.get('faithfulness_avg', 0):.2%}", style="bold green")
        summary_text.append("  |  Answer Relevancy: ", style="cyan")
        summary_text.append(f"{pipeline.get('answer_relevancy_avg', 0):.2%}", style="bold green")
        summary_text.append("  |  Context Precision: ", style="cyan")
        summary_text.append(f"{pipeline.get('context_precision_avg', 0):.2%}", style="bold green")
        summary_text.append("  |  Context Recall: ", style="cyan")
        summary_text.append(f"{pipeline.get('context_recall_avg', 0):.2%}", style="bold green")
        console.print(Panel(summary_text, title="Resumo Agentic", style="bold"))

        # Custo se disponível
        if "total_estimated_cost_usd" in pipeline:
            cost_text = Text()
            cost_text.append(f"Custo estimado: ${pipeline['total_estimated_cost_usd']:.4f}", style="bold yellow")
            console.print(Panel(cost_text, title="Custo", style="yellow"))

    elif "recall_at_k" in pipeline:
        # Métricas padrão
        metrics_table = Table(title=f"Métricas de Avaliação (k={k})", show_header=True)
        metrics_table.add_column("Métrica", style="cyan")
        metrics_table.add_column("Valor", style="yellow")
        metrics_table.add_row("Recall@k", f"{pipeline['recall_at_k']:.4f}")
        metrics_table.add_row("MRR (Mean Reciprocal Rank)", f"{pipeline['mrr']:.4f}")
        metrics_table.add_row("Taxa de Alucinação", f"{pipeline['hallucination_rate']:.4f}")
        metrics_table.add_row("Cobertura de Citações", f"{pipeline['citation_coverage']:.4f}")
        metrics_table.add_row("Total de Queries", str(pipeline['total_queries']))
        metrics_table.add_row("Queries Bem-sucedidas", str(pipeline['successful_queries']))
        console.print(metrics_table)

        summary_text = Text()
        summary_text.append(f"Recall@{k}: ", style="cyan")
        summary_text.append(f"{pipeline['recall_at_k']:.2%}", style="bold green")
        summary_text.append("  |  MRR: ", style="cyan")
        summary_text.append(f"{pipeline['mrr']:.4f}", style="bold green")
        summary_text.append("  |  Alucinação: ", style="cyan")
        summary_text.append(f"{pipeline['hallucination_rate']:.2%}", style="bold red" if pipeline['hallucination_rate'] > 0 else "bold green")
        summary_text.append("  |  Citações: ", style="cyan")
        summary_text.append(f"{pipeline['citation_coverage']:.2%}", style="bold green")
        console.print(Panel(summary_text, title="Resumo", style="bold"))

    # Config
    if result.get("config") and any(k in result["config"] for k in ["judge_provider", "judge_model"]):
        config_table = Table(title="Configuração Avaliação", show_header=True)
        config_table.add_column("Parâmetro", style="cyan")
        config_table.add_column("Valor", style="yellow")
        for key, value in result["config"].items():
            if key in ["judge_provider", "judge_model"]:
                config_table.add_row(key.replace("_", " ").title(), str(value))
        console.print(config_table)


def _metrics_to_dict(metrics: EvalMetrics) -> dict:
    """
    Converte EvalMetrics dataclass para dict serializável (JSON/YAML).

    Mantém precisão de float para métricas (recall, MRR, etc.) e int para contadores.
    """
    return {
        "recall_at_k": metrics.recall_at_k,
        "mrr": metrics.mrr,
        "hallucination_rate": metrics.hallucination_rate,
        "citation_coverage": metrics.citation_coverage,
        "total_queries": metrics.total_queries,
        "successful_queries": metrics.successful_queries,
    }