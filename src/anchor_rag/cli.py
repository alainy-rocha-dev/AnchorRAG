"""CLI principal do AnchorRAG usando Typer."""

from __future__ import annotations
import typer
from typing import Optional, List
from pathlib import Path

from anchor_rag.pipeline.orchestrator import RAGPipeline
from anchor_rag.config import AppConfig
from anchor_rag.cli_ingest import ingest_command
from anchor_rag.cli_query import query_command
from anchor_rag.cli_eval import eval_command

app = typer.Typer(
    name="anchor-rag",
    help="AnchorRAG - Engine RAG de Alta Precisão com Ancoragem Estrita, Citações e SQLite-Vec",
    add_completion=False,
)


@app.callback()
def main(
    config: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="Caminho para arquivo de configuração YAML",
        exists=True,
        readable=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Output detalhado",
    ),
):
    """
    AnchorRAG - Pipeline de Ingestão, Embedding, Busca Vetorial e Síntese com Citações.
    """
    # Config é passado via contexto para subcomandos
    pass


@app.command()
def ingest(
    paths: List[Path] = typer.Argument(..., help="Arquivos ou diretórios para ingerir"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Buscar recursivamente em diretórios"),
    force: bool = typer.Option(False, "--force", "-f", help="Forçar re-ingestão (ignorar cache)"),
    chunk_size: Optional[int] = typer.Option(None, "--chunk-size", help="Tamanho do chunk (override config)"),
    chunk_overlap: Optional[int] = typer.Option(None, "--chunk-overlap", help="Overlap do chunk (override config)"),
    parser: str = typer.Option("pdfplumber", "--parser", help="Parser PDF: pdfplumber ou pypdf"),
    format: str = typer.Option("text", "--format", help="Formato de saída: text ou json"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Arquivo de configuração"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Output detalhado"),
):
    """Ingere documentos PDF no pipeline."""
    ingest_command(
        paths=paths,
        recursive=recursive,
        force=force,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        parser=parser,
        output_format=format,
        config_path=config,
        verbose=verbose,
    )


@app.command()
def query(
    question: str = typer.Argument(..., help="Pergunta para o sistema RAG"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Número de chunks a recuperar"),
    threshold: float = typer.Option(0.7, "--threshold", "-t", help="Threshold de similaridade (0-1)"),
    llm_provider: Optional[str] = typer.Option(None, "--llm-provider", help="Provedor LLM: openai, ollama, anthropic"),
    llm_model: Optional[str] = typer.Option(None, "--llm-model", help="Modelo LLM específico"),
    temperature: Optional[float] = typer.Option(None, "--temperature", help="Temperatura do LLM"),
    no_synthesis: bool = typer.Option(False, "--no-synthesis", help="Retornar apenas chunks sem síntese"),
    format: str = typer.Option("text", "--format", help="Formato de saída: text ou json"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Arquivo de configuração"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Output detalhado"),
):
    """Faz uma query no pipeline RAG."""
    query_command(
        question=question,
        top_k=top_k,
        threshold=threshold,
        llm_provider=llm_provider,
        llm_model=llm_model,
        temperature=temperature,
        no_synthesis=no_synthesis,
        output_format=format,
        config_path=config,
        verbose=verbose,
    )


@app.command()
def eval(
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Arquivo de configuração"),
    format: str = typer.Option("text", "--format", help="Formato de saída: text ou json"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Output detalhado"),
):
    """Avalia o pipeline (estatísticas, health checks)."""
    eval_command(
        config_path=config,
        output_format=format,
        verbose=verbose,
    )


if __name__ == "__main__":
    app()