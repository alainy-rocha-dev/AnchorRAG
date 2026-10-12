"""Carregamento do corpus de normas com IDs estáveis."""

import hashlib
import json
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from anchor_rag.embeddings.base import EmbeddingProvider
from anchor_rag.ingestion.corpus_loader import (
    CorpusMismatchError,
    check_corpus,
    chunk_uuid,
    document_uuid,
    ingest_corpus,
    read_corpus,
)
from anchor_rag.vector_store.sqlite_vec import SQLiteVecStore

DIMS = 8


def _vetor(texto: str):
    """Embedding determinístico a partir do texto (sem rede)."""
    d = hashlib.sha256(texto.encode("utf-8")).digest()
    return [b / 255.0 + 0.01 for b in d[:DIMS]]


class FakeEmbedder(EmbeddingProvider):
    def __init__(self):
        super().__init__(MagicMock())
        self.chamadas = 0

    @property
    def dimensions(self):
        return DIMS

    async def embed(self, text):
        return _vetor(text)

    async def embed_batch(self, texts):
        self.chamadas += 1
        return [_vetor(t) for t in texts]

    async def health_check(self):
        return True


REGISTROS = [
    {"chunk_id": "res_cmn_4893:art1", "norma": "res_cmn_4893", "artigo": "1", "texto": "Art. 1º Política de segurança cibernética.", "fonte": "u1"},
    {"chunk_id": "res_cmn_4893:art2", "norma": "res_cmn_4893", "artigo": "2", "texto": "Art. 2º Plano de resposta a incidentes.", "fonte": "u1"},
    {"chunk_id": "res_bcb_85:art1", "norma": "res_bcb_85", "artigo": "1", "texto": "Art. 1º Instituições de pagamento e nuvem.", "fonte": "u2"},
]


def _escrever(path, registros):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in registros) + "\n", encoding="utf-8")


@pytest.fixture
def corpus(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _escrever(p, REGISTROS)
    return p


@pytest_asyncio.fixture
async def store(tmp_path):
    s = SQLiteVecStore(str(tmp_path / "bcb.db"), embedding_dimensions=DIMS)
    yield s
    await s.close()


def test_chunk_uuid_estavel_e_distinto():
    assert chunk_uuid("res_cmn_4893:art3") == chunk_uuid("res_cmn_4893:art3")
    assert chunk_uuid("res_cmn_4893:art3") != chunk_uuid("res_cmn_4893:art3-A")
    assert chunk_uuid("res_cmn_4893") != document_uuid("res_cmn_4893")
    # valor fixo: se mudar, todas as bases carregadas ficam inválidas
    assert str(chunk_uuid("res_cmn_4893:art3")) == str(chunk_uuid("res_cmn_4893:art3"))


def test_read_corpus_rejeita_duplicado(tmp_path):
    p = tmp_path / "c.jsonl"
    _escrever(p, REGISTROS + [REGISTROS[0]])
    with pytest.raises(ValueError, match="duplicado"):
        read_corpus(p)


def test_read_corpus_rejeita_campo_ausente(tmp_path):
    p = tmp_path / "c.jsonl"
    _escrever(p, [{"chunk_id": "x:art1", "norma": "x"}])
    with pytest.raises(ValueError, match="texto"):
        read_corpus(p)


@pytest.mark.asyncio
async def test_carrega_chunks_e_documentos(corpus, store):
    r = await ingest_corpus(corpus, store, FakeEmbedder(), embedding_model="fake")

    assert (r.total, r.inseridos, r.pulados, r.normas) == (3, 3, 0, 2)
    stats = await store.get_stats()
    assert stats["total_chunks"] == 3
    assert stats["total_documents"] == 2

    conn = store._get_conn()
    hashes = [row["content_hash"] for row in conn.execute("SELECT content_hash FROM documents")]
    assert all(len(h) == 64 for h in hashes)
    assert len(set(hashes)) == 2


@pytest.mark.asyncio
async def test_busca_devolve_uuid_estavel_e_chunk_id(corpus, store):
    await ingest_corpus(corpus, store, FakeEmbedder(), embedding_model="fake")

    alvo = REGISTROS[1]
    res = await store.search_with_scores(_vetor(alvo["texto"]), top_k=1, threshold=0.0)

    chunk, score = res[0]
    assert chunk.id == chunk_uuid(alvo["chunk_id"])
    assert chunk.document_id == document_uuid(alvo["norma"])
    assert chunk.metadata["chunk_id"] == alvo["chunk_id"]
    assert score == pytest.approx(1.0, abs=1e-5)


@pytest.mark.asyncio
async def test_recarga_e_idempotente(corpus, store):
    await ingest_corpus(corpus, store, FakeEmbedder(), embedding_model="fake")
    emb = FakeEmbedder()
    r = await ingest_corpus(corpus, store, emb, embedding_model="fake")

    assert (r.inseridos, r.pulados) == (0, 3)
    assert emb.chamadas == 0
    assert (await store.get_stats())["total_chunks"] == 3


@pytest.mark.asyncio
async def test_retoma_carga_interrompida(corpus, store, tmp_path):
    parcial = tmp_path / "parcial.jsonl"
    _escrever(parcial, REGISTROS[:1])
    # simula carga anterior incompleta: chunk presente, mas sem registro de corpus
    await store.init_db()
    await ingest_corpus(parcial, store, FakeEmbedder(), embedding_model="fake")
    conn = store._get_conn()
    conn.execute("DELETE FROM store_meta")
    conn.commit()

    r = await ingest_corpus(corpus, store, FakeEmbedder(), embedding_model="fake")
    assert (r.inseridos, r.pulados) == (2, 1)


@pytest.mark.asyncio
async def test_recusa_corpus_diferente(corpus, store, tmp_path):
    await ingest_corpus(corpus, store, FakeEmbedder(), embedding_model="fake")
    outro = tmp_path / "outro.jsonl"
    _escrever(outro, REGISTROS[:2])

    with pytest.raises(CorpusMismatchError, match="outro corpus"):
        await ingest_corpus(outro, store, FakeEmbedder(), embedding_model="fake")


@pytest.mark.asyncio
async def test_recusa_modelo_diferente(corpus, store):
    await ingest_corpus(corpus, store, FakeEmbedder(), embedding_model="fake")
    with pytest.raises(CorpusMismatchError, match="embedding"):
        await ingest_corpus(corpus, store, FakeEmbedder(), embedding_model="outro")


@pytest.mark.asyncio
async def test_check_corpus(corpus, store, tmp_path):
    await store.init_db()
    assert "ingest-chunks" in await check_corpus(store, corpus)

    await ingest_corpus(corpus, store, FakeEmbedder(), embedding_model="fake")
    assert await check_corpus(store, corpus) is None

    _escrever(corpus, REGISTROS[:2])
    assert "outro corpus" in await check_corpus(store, corpus)
