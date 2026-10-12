"""Busca textual (FTS5/BM25) em português e recuperação híbrida com RRF."""

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from anchor_rag.embeddings.base import EmbeddingProvider
from anchor_rag.evaluation.dataset_v1 import evaluate_v1, load_v1
from anchor_rag.ingestion.corpus_loader import ingest_corpus
from anchor_rag.retrieval.fts import FTS5Store, build_fts_query
from anchor_rag.retrieval.hybrid import HybridRetriever
from anchor_rag.vector_store.sqlite_vec import SQLiteVecStore

DIMS = 8

CORPUS = [
    {"chunk_id": "n:art1", "norma": "n", "artigo": "1", "texto": "Art. 1 Esta Resolução dispõe sobre a política de segurança cibernética."},
    {"chunk_id": "n:art2", "norma": "n", "artigo": "2", "texto": "Art. 2 A política deve passar por revisão anual pela diretoria."},
    {"chunk_id": "n:art3", "norma": "n", "artigo": "3", "texto": "Art. 3 Os procedimentos de análise podem ser realizados de forma centralizada no conglomerado."},
    {"chunk_id": "n:art4", "norma": "n", "artigo": "4", "texto": "Art. 4 O novo pedido de adesão só cabe após sessenta meses da exclusão."},
]


def _vetor(texto):
    d = hashlib.sha256(texto.encode("utf-8")).digest()
    return [b / 255.0 + 0.01 for b in d[:DIMS]]


class Embedder(EmbeddingProvider):
    def __init__(self, mapa=None):
        super().__init__(MagicMock())
        self.mapa = mapa or {}

    @property
    def dimensions(self):
        return DIMS

    async def embed(self, text):
        return _vetor(self.mapa.get(text, text))

    async def embed_batch(self, texts):
        return [_vetor(t) for t in texts]

    async def health_check(self):
        return True


@pytest_asyncio.fixture
async def base(tmp_path):
    corpus = tmp_path / "chunks.jsonl"
    corpus.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in CORPUS), encoding="utf-8")
    db = str(tmp_path / "b.db")
    store = SQLiteVecStore(db, embedding_dimensions=DIMS)
    await ingest_corpus(corpus, store, Embedder(), embedding_model="fake")
    fts = FTS5Store(db)
    await fts.ensure_fts()
    yield store, fts
    await fts.close()
    await store.close()


def _ids(res):
    return [c.metadata["chunk_id"] for c, _ in res]


def test_query_tira_stopwords_e_acentos():
    q = build_fts_query("Qual é o prazo de revisão da política?")
    assert q == '"prazo"* OR "revisao"* OR "politic"*'


def test_query_usa_radical_e_mantem_numeros():
    q = build_fts_query("centralizada após 60 meses")
    assert '"central"*' in q
    assert '"60"' in q


def test_query_vazia_devolve_none():
    assert build_fts_query("o que é?") is None


@pytest.mark.asyncio
async def test_fts_ignora_acento_e_flexao(base):
    _, fts = base
    res = await fts.search("revisao anual", top_k=2)
    assert _ids(res)[0] == "n:art2"

    res = await fts.search("centralizar a análise", top_k=2)
    assert _ids(res)[0] == "n:art3"


@pytest.mark.asyncio
async def test_fts_score_positivo_e_decrescente(base):
    _, fts = base
    res = await fts.search("política revisão anual", top_k=4)
    scores = [s for _, s in res]
    assert all(s > 0 for s in scores)
    assert scores == sorted(scores, reverse=True)
    assert len(set(scores)) > 1  # antes todos saíam 1.0


@pytest.mark.asyncio
async def test_fts_sem_termo_util_devolve_vazio(base):
    _, fts = base
    assert await fts.search("o que é?", top_k=3) == []


@pytest.mark.asyncio
async def test_ensure_fts_idempotente_e_recria_versao_antiga(base):
    store, fts = base
    assert await fts.ensure_fts() is False

    conn = fts._get_conn()
    conn.execute("UPDATE store_meta SET value = '1' WHERE key = 'fts_version'")
    conn.commit()
    assert await fts.ensure_fts() is True
    assert _ids(await fts.search("sessenta meses", top_k=1)) == ["n:art4"]


@pytest.mark.asyncio
async def test_modos_de_recuperacao(base):
    store, fts = base
    pergunta = "Quando cabe novo pedido de adesão após a exclusão?"
    # o embedder "acha" o art1 (errado); o BM25 acha o art4 (certo)
    r = HybridRetriever(vector_store=store, fts_store=fts, embedder=Embedder({pergunta: CORPUS[0]["texto"]}).embed)

    assert _ids(await r.retrieve_with_scores(pergunta, 1, mode="vector")) == ["n:art1"]
    assert _ids(await r.retrieve_with_scores(pergunta, 1, mode="fts")) == ["n:art4"]
    hibrido = _ids(await r.retrieve_with_scores(pergunta, 2, mode="hybrid"))
    assert set(hibrido) == {"n:art1", "n:art4"}

    with pytest.raises(ValueError):
        await r.retrieve_with_scores(pergunta, 1, mode="outro")


@pytest.mark.asyncio
async def test_rrf_prioriza_quem_aparece_nas_duas_buscas(base):
    store, fts = base
    pergunta = "revisão anual da política"
    r = HybridRetriever(vector_store=store, fts_store=fts, embedder=Embedder({pergunta: CORPUS[1]["texto"]}).embed)
    res = await r.retrieve_with_scores(pergunta, 3, mode="hybrid")
    assert _ids(res)[0] == "n:art2"
    assert [s for _, s in res] == sorted([s for _, s in res], reverse=True)


@pytest.mark.asyncio
async def test_avaliacao_usa_o_recuperador_do_pipeline(base, tmp_path):
    store, fts = base
    item = {"id": "x", "pergunta": "sessenta meses após exclusão", "categoria": "respondivel",
            "chunk_ids_relevantes": ["n:art4"], "resposta_ouro": "60 meses"}
    p = tmp_path / "v.jsonl"
    p.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
    r = HybridRetriever(vector_store=store, fts_store=fts, embedder=Embedder().embed)

    async def recuperar(q, k):
        return await r.retrieve_with_scores(q, k, mode="fts")

    pipeline = SimpleNamespace(embedder=None, vector_store=None, retrieve=recuperar, synthesizer=None)
    rs = await evaluate_v1(pipeline, load_v1(p), k=2, sintetizar=False)
    assert rs[0].erro is None
    assert rs[0].recuperados[0] == "n:art4" and rs[0].hit
