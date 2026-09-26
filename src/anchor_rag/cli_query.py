"""Comando CLI: query."""

from __future__ import annotations
from typing import Optional
from pathlib import Path
import asyncio
import json
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from anchor_rag.pipeline.orchestrator import RAGPipeline
from anchor_rag.config import AppConfig
from anchor_rag.domain.models import QueryConfig

console = Console()


def query_command(
    question: str,
    top_k: int,
    threshold: float,
    llm_provider: Optional[str],
    llm_model: Optional[str],
    temperature: Optional[float],
    no_synthesis: bool,
    output_format: str,
    config_path: Optional[Path],
    verbose: bool,
):
    """Executa comando de query."""
    asyncio.run(_query_async(
        question, top_k, threshold, llm_provider, llm_model,
        temperature, no_synthesis, output_format, config_path, verbose
    ))


async def _query_async(
    question: str,
    top_k: int,
    threshold: float,
    llm_provider: Optional[str],
    llm_model: Optional[str],
    temperature: Optional[float],
    no_synthesis: bool,
    output_format: str,
    config_path: Optional[Path],
    verbose: bool,
):
    # Carrega config
    if config_path:
        config = AppConfig.from_yaml(config_path).resolve_api_keys()
    else:
        config = AppConfig().resolve_api_keys()

    # Override LLM se especificado
    if llm_provider:
        config.llm.provider = llm_provider
    if llm_model:
        config.llm.model = llm_model
    if temperature is not None:
        config.llm.temperature = temperature

    # Cria pipeline
    pipeline = RAGPipeline(config=config)
    await pipeline.initialize()

    try:
        query_config = QueryConfig(
            top_k=top_k,
            threshold=threshold,
            llm_provider=llm_provider,
            llm_model=llm_model,
            temperature=temperature,
            no_synthesis=no_synthesis,
            format=output_format,
        )

        if verbose:
            console.print(f"[blue]Query: {question}[/blue]")
            console.print(f"[dim]top_k={top_k}, threshold={threshold}, synthesis={'off' if no_synthesis else 'on'}[/dim]")

        result = await pipeline.query(question, query_config)

        if output_format == "json":
            output = {
                "question": question,
                "answer": result.answer,
                "citations": result.citations,
                "chunks_used": len(result.chunks_used),
                "scores": result.scores,
                "latency_ms": result.latency_ms,
                "metadata": result.metadata,
            }
            console.print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            # Formato texto rico
            if no_synthesis:
                console.print(Panel(result.answer, title="Chunks Recuperados", border_style="blue"))
            else:
                console.print(Panel(Markdown(result.answer), title="Resposta", border_style="green"))

            # Latência
            if verbose:
                lat_table = Table(title="Latência (ms)", show_header=False)
                lat_table.add_column("Etapa", style="cyan")
                lat_table.add_column("Tempo", justify="right", style="yellow")
                for stage, ms in result.latency_ms.items():
                    lat_table.add_row(stage, f"{ms:.1f}")
                console.print(lat_table)

            # Citações
            if result.citations:
                cite_table = Table(title="Citações", show_header=True)
                cite_table.add_column("#", justify="right")
                cite_table.add_column("Score", justify="right")
                cite_table.add_column("Fonte")
                for i, cite in enumerate(result.citations):
                    idx = cite.get("index", i + 1)
                    score = result.scores[i] if i < len(result.scores) else 0
                    chunk = result.chunks_used[i] if i < len(result.chunks_used) else None
                    source = ""
                    if chunk:
                        source = chunk.metadata.get("filename", "desconhecido")
                        if chunk.metadata.get("page_number"):
                            source += f" p.{chunk.metadata['page_number']}"
                    cite_table.add_row(str(idx), f"{score:.3f}", source)
                console.print(cite_table)

    finally:
        await pipeline.close()