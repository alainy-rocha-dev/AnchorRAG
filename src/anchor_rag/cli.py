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


@app.command("ingest-chunks")
def ingest_chunks(
    corpus: Path = typer.Argument(
        Path("corpus/chunks.jsonl"), help="Arquivo chunks.jsonl gerado por eval/build_dataset.py ingest",
        exists=True, readable=True,
    ),
    db: Path = typer.Option(Path("data/bcb.db"), "--db", help="Base SQLite de destino (separada dos PDFs)"),
    embedding_provider: Optional[str] = typer.Option(None, "--embedding-provider", help="Override: openai, ollama, huggingface"),
    embedding_model: Optional[str] = typer.Option(None, "--embedding-model", help="Override do modelo (ex.: bge-m3)"),
    batch_size: int = typer.Option(32, "--batch-size", help="Chunks por chamada de embedding"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Arquivo de configuração"),
):
    """Carrega o corpus de normas (chunks.jsonl) numa base vetorial, com IDs estáveis."""
    import asyncio
    from anchor_rag.embeddings import create_embedding_provider
    from anchor_rag.ingestion.corpus_loader import CorpusMismatchError, ingest_corpus
    from anchor_rag.vector_store.sqlite_vec import SQLiteVecStore

    cfg = AppConfig.from_yaml(config).resolve_api_keys() if config else AppConfig()
    if embedding_provider:
        cfg.embedding.provider = embedding_provider
    if embedding_model:
        cfg.embedding.model = embedding_model
    # A primeira chamada pode carregar o modelo na GPU; 30 s costuma ser pouco.
    cfg.embedding.timeout = max(cfg.embedding.timeout, 120)

    async def run():
        embedder = create_embedding_provider(cfg.embedding)
        store = SQLiteVecStore(str(db), embedding_dimensions=embedder.dimensions)

        def progresso(feitos: int, total: int):
            typer.echo(f"  embeddings: {feitos}/{total}")

        try:
            r = await ingest_corpus(
                corpus, store, embedder, embedding_model=cfg.embedding.model,
                batch_size=batch_size, on_progress=progresso,
            )
        finally:
            await store.close()
            fechar = getattr(embedder, "close", None)
            if fechar:
                await fechar()
        return r

    typer.echo(f"Corpus: {corpus}  ->  base: {db}  (embedding {cfg.embedding.provider}:{cfg.embedding.model})")
    try:
        r = asyncio.run(run())
    except CorpusMismatchError as e:
        typer.echo(f"ERRO: {e}", err=True)
        raise typer.Exit(code=1)
    typer.echo(
        f"OK: {r.total} chunks de {r.normas} normas; {r.inseridos} inseridos, "
        f"{r.pulados} já existiam. Hash do corpus: {r.corpus_hash[:12]}"
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
    dataset: Optional[Path] = typer.Option(
        None, "--dataset", "-d", help="Caminho para dataset YAML de avaliação", exists=True, readable=True
    ),
    k: int = typer.Option(5, "--k", help="Valor de k para recall@k"),
):
    """Avalia o pipeline (estatísticas, health checks, métricas com dataset)."""
    eval_command(
        config_path=config,
        output_format=format,
        verbose=verbose,
        dataset=dataset,
        k=k,
    )


if __name__ == "__main__":
    app()