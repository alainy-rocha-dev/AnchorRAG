"""Comando CLI: ingest."""

from __future__ import annotations
from typing import List, Optional
from pathlib import Path
import asyncio
import json
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from anchor_rag.pipeline.orchestrator import RAGPipeline
from anchor_rag.config import AppConfig
from anchor_rag.ingestion.parser import create_parser
from anchor_rag.ingestion.chunker import Chunker
from anchor_rag.domain.models import IngestConfig

console = Console()


def ingest_command(
    paths: List[Path],
    recursive: bool,
    force: bool,
    chunk_size: Optional[int],
    chunk_overlap: Optional[int],
    parser: str,
    output_format: str,
    config_path: Optional[Path],
    verbose: bool,
):
    """Executa comando de ingestão."""
    asyncio.run(_ingest_async(
        paths, recursive, force, chunk_size, chunk_overlap,
        parser, output_format, config_path, verbose
    ))


async def _ingest_async(
    paths: List[Path],
    recursive: bool,
    force: bool,
    chunk_size: Optional[int],
    chunk_overlap: Optional[int],
    parser_type: str,
    output_format: str,
    config_path: Optional[Path],
    verbose: bool,
):
    # Carrega config
    if config_path:
        config = AppConfig.from_yaml(config_path).resolve_api_keys()
    else:
        config = AppConfig().resolve_api_keys()

    # Override chunking se especificado
    if chunk_size:
        config.chunking.chunk_size = chunk_size
    if chunk_overlap:
        config.chunking.chunk_overlap = chunk_overlap

    # Cria pipeline
    parser_obj = create_parser(parser_type)
    chunker = Chunker(
        chunk_size=config.chunking.chunk_size,
        chunk_overlap=config.chunking.chunk_overlap,
        chunk_unit=config.chunking.chunk_unit,
    )

    pipeline = RAGPipeline(
        config=config,
        parser=parser_obj,
        chunker=chunker,
    )

    await pipeline.initialize()

    try:
        # Expande paths se diretórios
        all_files = []
        for path in paths:
            if path.is_dir():
                pattern = "**/*.pdf" if recursive else "*.pdf"
                files = list(path.glob(pattern))
                all_files.extend(files)
                if verbose:
                    console.print(f"[blue]Diretório {path}: {len(files)} arquivos PDF[/blue]")
            else:
                all_files.append(path)

        if not all_files:
            console.print("[yellow]Nenhum arquivo PDF encontrado[/yellow]")
            return

        if verbose:
            console.print(f"[green]Ingerindo {len(all_files)} arquivo(s)...[/green]")

        # Progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Ingerindo...", total=len(all_files))

            results = []
            for file_path in all_files:
                progress.update(task, description=f"Ingerindo {file_path.name}...")
                result = await pipeline.ingest([str(file_path)])
                results.extend(result)
                progress.advance(task)

        # Output resultados
        if output_format == "json":
            output = {
                "documents_processed": len(results),
                "total_chunks": sum(r.stats.chunks_created for r in results),
                "total_embedded": sum(r.stats.chunks_embedded for r in results),
                "total_stored": sum(r.stats.chunks_stored for r in results),
                "documents": [
                    {
                        "id": str(r.document.id),
                        "filename": r.document.filename,
                        "pages": r.document.page_count,
                        "chunks": r.stats.chunks_created,
                    }
                    for r in results
                ],
            }
            console.print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            table = Table(title="Resultado da Ingestão")
            table.add_column("Arquivo", style="cyan")
            table.add_column("Páginas", justify="right")
            table.add_column("Chunks", justify="right")
            table.add_column("Embeddings", justify="right")
            table.add_column("Armazenados", justify="right")

            for r in results:
                table.add_row(
                    r.document.filename,
                    str(r.document.page_count),
                    str(r.stats.chunks_created),
                    str(r.stats.chunks_embedded),
                    str(r.stats.chunks_stored),
                )

            console.print(table)
            console.print(f"\n[green]Total: {len(results)} documentos, {sum(r.stats.chunks_stored for r in results)} chunks armazenados[/green]")

    finally:
        await pipeline.close()