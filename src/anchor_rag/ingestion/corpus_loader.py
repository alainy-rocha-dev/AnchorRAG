"""Carrega o corpus de normas (corpus/chunks.jsonl) no vector store.

Cada chunk do corpus vira um chunk no store com UUID estável, derivado do chunk_id
legível ("res_cmn_4893:art3"). Assim o dataset de avaliação, que referencia chunk_ids,
casa com os resultados da busca em qualquer máquina e em qualquer reingestão.

A base guarda o hash do chunks.jsonl e o modelo de embedding usados. Se o corpus ou o
modelo mudarem, o carregamento recusa a base existente em vez de misturar versões.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional
from uuid import UUID, uuid5

from anchor_rag.embeddings.base import EmbeddingProvider
from anchor_rag.vector_store.base import Chunk
from anchor_rag.vector_store.sqlite_vec import SQLiteVecStore

logger = logging.getLogger(__name__)

# Namespace fixo: mudar este valor muda todos os UUIDs e invalida bases já carregadas.
NAMESPACE_ANCHOR = UUID("71fb638f-92d7-46df-8f65-a0db1f7d1f98")

META_CORPUS_HASH = "corpus_hash"
META_EMBEDDING_MODEL = "embedding_model"
META_EMBEDDING_DIMS = "embedding_dimensions"

CAMPOS_OBRIGATORIOS = ("chunk_id", "norma", "texto")


class CorpusMismatchError(RuntimeError):
    """A base foi carregada com outro corpus ou outro modelo de embedding."""


def chunk_uuid(chunk_id: str) -> UUID:
    """UUID estável de um chunk do corpus (ex.: 'res_cmn_4893:art3')."""
    return uuid5(NAMESPACE_ANCHOR, f"chunk:{chunk_id}")


def document_uuid(norma: str) -> UUID:
    """UUID estável de uma norma (ex.: 'res_cmn_4893')."""
    return uuid5(NAMESPACE_ANCHOR, f"norma:{norma}")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 16), b""):
            h.update(bloco)
    return h.hexdigest()


def read_corpus(path: Path) -> List[dict]:
    """Lê o chunks.jsonl e valida campos obrigatórios e chunk_ids únicos."""
    registros: List[dict] = []
    vistos: set = set()
    with open(path, encoding="utf-8") as f:
        for n, linha in enumerate(f, 1):
            if not linha.strip():
                continue
            r = json.loads(linha)
            faltam = [c for c in CAMPOS_OBRIGATORIOS if not r.get(c)]
            if faltam:
                raise ValueError(f"{path}:{n}: campos ausentes: {', '.join(faltam)}")
            if r["chunk_id"] in vistos:
                raise ValueError(f"{path}:{n}: chunk_id duplicado: {r['chunk_id']}")
            vistos.add(r["chunk_id"])
            registros.append(r)
    return registros


async def check_corpus(store: SQLiteVecStore, corpus_path: Path) -> Optional[str]:
    """Confere se a base foi carregada com este corpus. Devolve um aviso, ou None se ok."""
    gravado = await store.get_meta(META_CORPUS_HASH)
    if gravado is None:
        return "a base não tem registro de corpus carregado (rode ingest-chunks)"
    atual = file_sha256(corpus_path)
    if gravado != atual:
        return (f"a base foi carregada com outro corpus (hash {gravado[:12]}), "
                f"mas {corpus_path} tem hash {atual[:12]}; recarregue numa base nova")
    return None


@dataclass
class IngestCorpusResult:
    total: int
    inseridos: int
    pulados: int
    normas: int
    corpus_hash: str


async def ingest_corpus(
    corpus_path: Path,
    store: SQLiteVecStore,
    embedder: EmbeddingProvider,
    embedding_model: str,
    batch_size: int = 32,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> IngestCorpusResult:
    """Carrega o corpus no store. Idempotente: chunks já presentes são pulados."""
    corpus_path = Path(corpus_path)
    await store.init_db()

    corpus_hash = file_sha256(corpus_path)
    hash_gravado = await store.get_meta(META_CORPUS_HASH)
    if hash_gravado and hash_gravado != corpus_hash:
        raise CorpusMismatchError(
            f"a base {store.db_path} foi carregada com outro corpus (hash {hash_gravado[:12]}); "
            f"o arquivo atual tem hash {corpus_hash[:12]}. Use uma base nova (--db)."
        )
    modelo_gravado = await store.get_meta(META_EMBEDDING_MODEL)
    if modelo_gravado and modelo_gravado != embedding_model:
        raise CorpusMismatchError(
            f"a base {store.db_path} usa o embedding '{modelo_gravado}', não '{embedding_model}'. "
            "Use uma base nova (--db)."
        )

    registros = read_corpus(corpus_path)

    # Documentos: um por norma, com hash real do conteúdo
    por_norma: Dict[str, List[dict]] = {}
    for r in registros:
        por_norma.setdefault(r["norma"], []).append(r)
    for norma, itens in por_norma.items():
        conteudo = "\n".join(i["texto"] for i in itens)
        await store.upsert_document(
            document_id=document_uuid(norma),
            path=str(corpus_path),
            filename=norma,
            content_hash=hashlib.sha256(conteudo.encode("utf-8")).hexdigest(),
            metadata={"norma": norma, "fonte": itens[0].get("fonte"), "n_chunks": len(itens)},
        )

    indice_na_norma = {}
    for itens in por_norma.values():
        for i, r in enumerate(itens):
            indice_na_norma[r["chunk_id"]] = i

    ids = [str(chunk_uuid(r["chunk_id"])) for r in registros]
    existentes = await store.existing_chunk_ids(ids)
    pendentes = [r for r, cid in zip(registros, ids) if cid not in existentes]

    inseridos = 0
    for i in range(0, len(pendentes), batch_size):
        lote = pendentes[i:i + batch_size]
        embeddings = await embedder.embed_batch([r["texto"] for r in lote])
        chunks = [
            Chunk(
                id=chunk_uuid(r["chunk_id"]),
                document_id=document_uuid(r["norma"]),
                content=r["texto"],
                chunk_index=indice_na_norma[r["chunk_id"]],
                page_number=None,
                start_char=0,
                end_char=len(r["texto"]),
                token_count=None,
                embedding=emb,
                metadata={
                    "chunk_id": r["chunk_id"],
                    "norma": r["norma"],
                    "artigo": r.get("artigo"),
                    "fonte": r.get("fonte"),
                },
            )
            for r, emb in zip(lote, embeddings)
        ]
        inseridos += await store.add_chunks(chunks)
        if on_progress:
            on_progress(min(i + batch_size, len(pendentes)), len(pendentes))

    # Só registra o corpus depois de tudo carregado: uma carga interrompida pode ser retomada.
    await store.set_meta(META_CORPUS_HASH, corpus_hash)
    await store.set_meta(META_EMBEDDING_MODEL, embedding_model)
    await store.set_meta(META_EMBEDDING_DIMS, str(store.embedding_dimensions))

    return IngestCorpusResult(
        total=len(registros),
        inseridos=inseridos,
        pulados=len(registros) - len(pendentes),
        normas=len(por_norma),
        corpus_hash=corpus_hash,
    )
