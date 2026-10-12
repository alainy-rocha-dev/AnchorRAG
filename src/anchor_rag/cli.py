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


def _familia(modelo: str) -> str:
    """'ollama:qwen2.5:7b' -> 'qwen'; 'llama3.1:8b' -> 'llama'; 'gpt-4o-mini' -> 'gpt'."""
    import re
    nome = (modelo or "").lower()
    if nome.count(":") >= 1 and nome.split(":", 1)[0] in ("ollama", "openai", "anthropic"):
        nome = nome.split(":", 1)[1]
    m = re.match(r"[a-z]+", nome)
    return m.group(0) if m else nome


def _carregar_contexto_juiz(dataset: Path, corpus: Path):
    import json
    from anchor_rag.evaluation.judge import Contexto
    ouro = {}
    with open(dataset, encoding="utf-8") as f:
        for linha in f:
            if linha.strip():
                x = json.loads(linha)
                ouro[x["id"]] = x.get("resposta_ouro")
    textos = {}
    with open(corpus, encoding="utf-8") as f:
        for linha in f:
            if linha.strip():
                x = json.loads(linha)
                textos[x["chunk_id"]] = x["texto"]
    return Contexto(ouro_por_id=ouro, texto_por_chunk=textos)


@app.command("judge-v1")
def judge_v1(
    relatorio: Path = typer.Argument(..., help="Relatório JSON do eval-v1 (com síntese)", exists=True, readable=True),
    dataset: Path = typer.Option(Path("eval/datasets/v1.jsonl"), "--dataset", exists=True, readable=True),
    corpus: Path = typer.Option(Path("corpus/chunks.jsonl"), "--corpus", exists=True, readable=True),
    judge_provider: str = typer.Option("ollama", "--judge-provider"),
    judge_model: str = typer.Option("llama3.1:8b", "--judge-model"),
    permitir_mesma_familia: bool = typer.Option(False, "--permitir-mesma-familia",
                                                help="Aceita juiz da mesma família do modelo avaliado"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Julga só os N primeiros itens (teste rápido)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
):
    """Julga as respostas de um relatório do eval-v1 com um LLM juiz (vereditos categóricos)."""
    import asyncio
    import json
    from datetime import datetime
    from anchor_rag.evaluation.dataset_v1 import file_sha256
    from anchor_rag.evaluation.judge import formatar_resumo, julgar_relatorio, resumo_juiz
    from anchor_rag.synthesis import create_llm_provider

    rel = json.loads(relatorio.read_text(encoding="utf-8"))
    if not rel.get("sintetizou"):
        typer.echo("ERRO: o relatório não tem respostas (foi gerado com --no-synthesis).", err=True)
        raise typer.Exit(code=1)
    if rel.get("dataset_sha256") != file_sha256(dataset):
        typer.echo("ERRO: o dataset mudou desde o relatório; as respostas-ouro podem não corresponder.", err=True)
        raise typer.Exit(code=1)
    fam_avaliado, fam_juiz = _familia(rel.get("llm") or ""), _familia(judge_model)
    if fam_avaliado == fam_juiz and not permitir_mesma_familia:
        typer.echo(f"ERRO: juiz ({judge_model}) e modelo avaliado ({rel.get('llm')}) são da mesma família "
                   f"'{fam_juiz}'. Use outro juiz ou --permitir-mesma-familia.", err=True)
        raise typer.Exit(code=1)

    cfg = AppConfig.from_yaml(config).resolve_api_keys() if config else AppConfig()
    cfg.llm.provider = judge_provider
    cfg.llm.model = judge_model
    cfg.llm.temperature = 0.0
    cfg.llm.timeout = max(cfg.llm.timeout, 180)
    ctx = _carregar_contexto_juiz(dataset, corpus)

    alvo = dict(rel)
    if limit:
        alvo["itens"] = rel["itens"][:limit]

    def progresso(n, total, item):
        vs = ", ".join(f"{d}={v['veredito']}" for d, v in item.get("juiz", {}).items()) or "-"
        typer.echo(f"  [{n}/{total}] {item['subtipo']:<14} {item['id']}  {vs}")

    async def run():
        llm = create_llm_provider(cfg.llm)
        try:
            return await julgar_relatorio(llm, alvo, ctx, on_item=progresso)
        finally:
            fechar = getattr(getattr(llm, "_client", None), "aclose", None)
            if fechar:
                await fechar()

    typer.echo(f"Juiz {judge_provider}:{judge_model} sobre {relatorio.name} ({len(alvo['itens'])} itens)")
    itens = asyncio.run(run())
    resumo = resumo_juiz(itens)
    alvo["juiz"] = {
        "modelo": f"{judge_provider}:{judge_model}",
        "data": datetime.now().isoformat(timespec="seconds"),
        "resumo": resumo,
    }
    destino = relatorio.with_name(relatorio.stem + ("_juiz_parcial" if limit else "_juiz") + ".json")
    destino.write_text(json.dumps(alvo, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo("")
    typer.echo(formatar_resumo(resumo))
    typer.echo(f"\nRelatório: {destino}")


@app.command("judge-review")
def judge_review(
    relatorio_juiz: Path = typer.Argument(..., help="Relatório gerado pelo judge-v1", exists=True, readable=True),
    dataset: Path = typer.Option(Path("eval/datasets/v1.jsonl"), "--dataset", exists=True, readable=True),
    corpus: Path = typer.Option(Path("corpus/chunks.jsonl"), "--corpus", exists=True, readable=True),
    n_exatidao: int = typer.Option(12, "--n-exatidao"),
    n_premissa: int = typer.Option(6, "--n-premissa"),
    n_fidelidade: int = typer.Option(12, "--n-fidelidade"),
    seed: int = typer.Option(7, "--seed"),
):
    """Você julga uma amostra sem ver o juiz; no fim, concordância (% e kappa) por dimensão."""
    import json
    import sys
    from anchor_rag.evaluation.judge import VEREDITOS, amostra_estratificada, concordancia

    if not sys.stdin.isatty():
        typer.echo("ERRO: a revisão exige uma pessoa no terminal.", err=True)
        raise typer.Exit(code=1)

    rel = json.loads(relatorio_juiz.read_text(encoding="utf-8"))
    ctx = _carregar_contexto_juiz(dataset, corpus)
    amostra = amostra_estratificada(
        rel["itens"], {"exatidao": n_exatidao, "premissa": n_premissa, "fidelidade": n_fidelidade}, seed=seed)

    rotulos_path = relatorio_juiz.with_name(relatorio_juiz.stem + "_humano.jsonl")
    feitos = {}
    if rotulos_path.exists():
        for linha in rotulos_path.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                r = json.loads(linha)
                feitos[(r["id"], r["dimensao"])] = r

    pendentes = [(it, d) for it, d in amostra if (it["id"], d) not in feitos]
    typer.echo(f"{len(amostra)} itens na amostra; {len(feitos)} já rotulados; {len(pendentes)} pendentes.")
    typer.echo("Você NÃO verá o veredito do juiz. Digite o número do seu veredito, s=pular, q=sair.\n")

    with open(rotulos_path, "a", encoding="utf-8") as saida:
        for k, (it, dim) in enumerate(pendentes, 1):
            opcoes = VEREDITOS[dim]
            typer.echo("=" * 78)
            typer.echo(f"[{k}/{len(pendentes)}] {dim.upper()}  ({it['subtipo']}, id={it['id']})\n")
            typer.echo(f"PERGUNTA: {it['pergunta']}\n")
            if dim in ("exatidao", "premissa"):
                rotulo = "CORREÇÃO ESPERADA" if dim == "premissa" else "RESPOSTA DE REFERÊNCIA"
                typer.echo(f"{rotulo}: {ctx.ouro_por_id.get(it['id'])}\n")
            if dim == "fidelidade":
                for i, cid in enumerate(it.get("recuperados") or [], 1):
                    typer.echo(f"--- trecho [{i}] {cid} ---\n{ctx.texto_por_chunk.get(cid, '')}\n")
            typer.echo(f"RESPOSTA AVALIADA:\n{it['resposta']}\n")
            if dim == "fidelidade":
                typer.echo("Pergunta: a resposta traz alguma informação factual que NÃO está nos trechos?")
            menu = "  ".join(f"{i}={v}" for i, v in enumerate(opcoes, 1))
            while True:
                r = input(f"{menu}  s=pular  q=sair > ").strip().lower()
                if r in ("q", "s") or (r.isdigit() and 1 <= int(r) <= len(opcoes)):
                    break
            if r == "q":
                break
            if r == "s":
                continue
            reg = {"id": it["id"], "dimensao": dim, "humano": opcoes[int(r) - 1],
                   "juiz": it["juiz"][dim]["veredito"]}
            saida.write(json.dumps(reg, ensure_ascii=False) + "\n")
            saida.flush()
            feitos[(it["id"], dim)] = reg

    conc = concordancia(list(feitos.values()))
    typer.echo("\nConcordância juiz x humano:")
    for dim, m in conc.items():
        typer.echo(f"  {dim:<11} n={m['n']:<3} acordo={m['acordo']:.2f}  kappa={m['kappa']}")
    destino = relatorio_juiz.with_name(relatorio_juiz.stem + "_concordancia.json")
    destino.write_text(json.dumps(conc, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"Rótulos: {rotulos_path}\nConcordância: {destino}")


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