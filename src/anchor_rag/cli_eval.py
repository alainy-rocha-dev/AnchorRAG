"""Comando CLI: eval."""

from __future__ import annotations
from typing import Optional
from pathlib import Path
import asyncio
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from anchor_rag.pipeline.orchestrator import RAGPipeline
from anchor_rag.config import AppConfig

console = Console()


def eval_command(
    config_path: Optional[Path],
    output_format: str,
    verbose: bool,
):
    """Executa comando de avaliação."""
    asyncio.run(_eval_async(config_path, output_format, verbose))


async def _eval_async(
    config_path: Optional[Path],
    output_format: str,
    verbose: bool,
):
    # Carrega config
    if config_path:
        config = AppConfig.from_yaml(config_path).resolve_api_keys()
    else:
        config = AppConfig().resolve_api_keys()

    pipeline = RAGPipeline(config=config)
    await pipeline.initialize()

    try:
        if verbose:
            console.print("[blue]Executando avaliação do pipeline...[/blue]")

        # Health checks
        embed_health = await pipeline.embedder.health_check()
        llm_health = await pipeline.llm.health_check()
        vector_stats = await pipeline.vector_store.get_stats()

        eval_result = await pipeline.eval()

        # Combina resultados
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
            },
            "pipeline": eval_result,
        }

        if output_format == "json":
            console.print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            console.print(Panel("Avaliação do Pipeline AnchorRAG", style="bold blue"))

            # Health checks
            health_table = Table(title="Health Checks", show_header=True)
            health_table.add_column("Componente", style="cyan")
            health_table.add_column("Status", style="green")
            health_table.add_row("Embedding Provider", "✓ OK" if embed_health else "✗ FALHOU")
            health_table.add_row("LLM Provider", "✓ OK" if llm_health else "✗ FALHOU")
            console.print(health_table)

            # Vector store stats
            vs_table = Table(title="Vector Store", show_header=True)
            vs_table.add_column("Métrica", style="cyan")
            vs_table.add_column("Valor", style="yellow")
            for key, value in vector_stats.items():
                vs_table.add_row(key.replace("_", " ").title(), str(value))
            console.print(vs_table)

            # Config
            if verbose:
                config_table = Table(title="Configuração Ativa", show_header=True)
                config_table.add_column("Parâmetro", style="cyan")
                config_table.add_column("Valor", style="yellow")
                cfg = result["config"]
                for key, value in cfg.items():
                    config_table.add_row(key.replace("_", " ").title(), str(value))
                console.print(config_table)

    finally:
        await pipeline.close()