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
            from anchor_rag.retrieval.fts import FTS5Store
            fts = FTS5Store(str(db))
            if await fts.ensure_fts():
                typer.echo("  índice FTS construído")
            await fts.close()
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


@app.command("eval-v1")
def eval_v1(
    dataset: Path = typer.Option(Path("eval/datasets/v1.jsonl"), "--dataset", "-d", exists=True, readable=True),
    db: Path = typer.Option(Path("data/bcb.db"), "--db", help="Base carregada com ingest-chunks"),
    corpus: Path = typer.Option(Path("corpus/chunks.jsonl"), "--corpus", help="Corpus esperado na base (conferido por hash)"),
    k: int = typer.Option(5, "--k", help="Chunks recuperados por pergunta"),
    retrieval: str = typer.Option("hybrid", "--retrieval", help="hybrid (RRF vetorial + BM25, padrão), vector ou fts"),
    no_synthesis: bool = typer.Option(False, "--no-synthesis", help="Só recuperação (rápido, sem LLM)"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Avalia só os N primeiros itens (teste rápido)"),
    categoria: Optional[str] = typer.Option(None, "--categoria", help="Filtra por subtipo (ex.: injecao)"),
    embedding_provider: Optional[str] = typer.Option(None, "--embedding-provider"),
    embedding_model: Optional[str] = typer.Option(None, "--embedding-model"),
    llm_provider: Optional[str] = typer.Option(None, "--llm-provider", help="Provedor do LLM de síntese"),
    llm_model: Optional[str] = typer.Option(None, "--llm-model", help="Modelo do LLM de síntese"),
    out: Path = typer.Option(Path("eval/results"), "--out", help="Pasta do relatório JSON"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Arquivo de configuração"),
):
    """Avalia o pipeline com o dataset v1: métricas por categoria e relatório JSON."""
    import asyncio
    from datetime import datetime
    from anchor_rag.embeddings import create_embedding_provider
    from anchor_rag.evaluation.dataset_v1 import (
        V1Report, evaluate_v1, file_sha256, format_table, load_v1, summarize,
    )
    from anchor_rag.ingestion.corpus_loader import META_EMBEDDING_MODEL, check_corpus
    from anchor_rag.retrieval.fts import FTS5Store
    from anchor_rag.retrieval.hybrid import HybridRetriever
    from types import SimpleNamespace
    from anchor_rag.synthesis import create_llm_provider
    from anchor_rag.synthesis.synthesizer import RAGSynthesizer
    from anchor_rag.vector_store.sqlite_vec import SQLiteVecStore

    cfg = AppConfig.from_yaml(config).resolve_api_keys() if config else AppConfig()
    if embedding_provider:
        cfg.embedding.provider = embedding_provider
    if embedding_model:
        cfg.embedding.model = embedding_model
    if llm_provider:
        cfg.llm.provider = llm_provider
    if llm_model:
        cfg.llm.model = llm_model
    cfg.embedding.timeout = max(cfg.embedding.timeout, 120)
    cfg.llm.timeout = max(cfg.llm.timeout, 180)

    if not db.exists():
        typer.echo(f"ERRO: base {db} não existe; rode ingest-chunks antes.", err=True)
        raise typer.Exit(code=1)
    if retrieval not in ("vector", "fts", "hybrid"):
        typer.echo(f"ERRO: --retrieval deve ser vector, fts ou hybrid (recebido {retrieval!r})", err=True)
        raise typer.Exit(code=1)

    itens = load_v1(dataset)
    if categoria:
        itens = [i for i in itens if i.subtipo == categoria]
    if limit:
        itens = itens[:limit]

    async def run():
        embedder = create_embedding_provider(cfg.embedding)
        store = SQLiteVecStore(str(db), embedding_dimensions=embedder.dimensions)
        fts = FTS5Store(str(db))
        try:
            aviso = await check_corpus(store, corpus)
            if aviso:
                raise RuntimeError(f"base inconsistente: {aviso}")
            modelo_base = await store.get_meta(META_EMBEDDING_MODEL)
            if modelo_base != cfg.embedding.model:
                raise RuntimeError(
                    f"a base foi carregada com o embedding '{modelo_base}', "
                    f"mas a avaliação usaria '{cfg.embedding.model}' (use --embedding-model)"
                )
            if retrieval in ("fts", "hybrid") and await fts.ensure_fts():
                typer.echo("  índice FTS (re)construído")
            retriever = HybridRetriever(vector_store=store, fts_store=fts, embedder=embedder.embed)

            async def recuperar(pergunta, kk):
                return await retriever.retrieve_with_scores(pergunta, top_k=kk, mode=retrieval)

            # Só as peças que a avaliação usa: recuperação e (se houver síntese) o sintetizador.
            pipeline = SimpleNamespace(
                embedder=embedder,
                vector_store=store,
                retrieve=recuperar,
                synthesizer=None if no_synthesis else RAGSynthesizer(create_llm_provider(cfg.llm)),
            )

            def progresso(n, total, r):
                marca = "ERRO " + r.erro if r.erro else ("ok" if r.hit in (None, True) else "miss")
                typer.echo(f"  [{n}/{total}] {r.subtipo:<14} {r.id}  {marca}")

            return await evaluate_v1(pipeline, itens, k=k, sintetizar=not no_synthesis, on_item=progresso), await store.get_meta("corpus_hash")
        finally:
            await fts.close()
            await store.close()
            fechar = getattr(embedder, "close", None)
            if fechar:
                await fechar()

    inicio = datetime.now()
    typer.echo(f"Avaliando {len(itens)} itens  (k={k}, recuperação {retrieval}, embedding {cfg.embedding.model}, "
               f"{'sem síntese' if no_synthesis else 'LLM ' + cfg.llm.provider + ':' + cfg.llm.model})")
    try:
        resultados, corpus_hash = asyncio.run(run())
    except RuntimeError as e:
        typer.echo(f"ERRO: {e}", err=True)
        raise typer.Exit(code=1)

    resumo = summarize(resultados)
    relatorio = V1Report(
        dataset=str(dataset),
        dataset_sha256=file_sha256(dataset),
        corpus_sha256=corpus_hash,
        embedding_model=f"{cfg.embedding.provider}:{cfg.embedding.model}",
        llm=None if no_synthesis else f"{cfg.llm.provider}:{cfg.llm.model}",
        retrieval=retrieval,
        k=k,
        sintetizou=not no_synthesis,
        inicio=inicio.isoformat(timespec="seconds"),
        duracao_s=round((datetime.now() - inicio).total_seconds(), 1),
        resumo=resumo,
        itens=[r.__dict__ for r in resultados],
    )
    out.mkdir(parents=True, exist_ok=True)
    sufixo = f"_{retrieval}" + ("_retrieval" if no_synthesis else "")
    destino = out / f"v1_{inicio.strftime('%Y%m%d-%H%M%S')}{sufixo}.json"
    destino.write_text(relatorio.to_json(), encoding="utf-8")

    typer.echo("")
    typer.echo(format_table(resumo))
    typer.echo(f"\nRelatório: {destino}")


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