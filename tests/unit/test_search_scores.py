"""Scores reais de similaridade: do SQLiteVecStore até o QueryResult."""

import math
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio

from anchor_rag.domain.models import QueryConfig
from anchor_rag.embeddings.base import EmbeddingProvider
from anchor_rag.pipeline.orchestrator import RAGPipeline
from anchor_rag.synthesis.llm import LLMProvider, LLMResponse
from anchor_rag.vector_store.base import Chunk, VectorStore
from anchor_rag.vector_store.sqlite_vec import SQLiteVecStore


def _chunk(content, embedding, doc_id):
    return Chunk(
        id=uuid4(),
        document_id=doc_id,
        content=content,
        chunk_index=0,
        page_number=None,
        start_char=0,
        end_char=len(content),
        token_count=None,
        embedding=embedding,
        metadata={},
    )


def _cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


@pytest_asyncio.fixture
async def store(tmp_path):
    s = SQLiteVecStore(str(tmp_path / "t.db"), embedding_dimensions=3)
    await s.init_db()
    doc = uuid4()
    await s.add_chunks([
        _chunk("igual", [1.0, 0.0, 0.0], doc),
        _chunk("parecido", [1.0, 1.0, 0.0], doc),
        _chunk("ortogonal", [0.0, 0.0, 1.0], doc),
    ])
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_sqlite_search_with_scores_devolve_similaridade_de_cosseno(store):
    q = [1.0, 0.0, 0.0]
    res = await store.search_with_scores(q, top_k=3, threshold=0.0)

    assert [c.content for c, _ in res] == ["igual", "parecido", "ortogonal"]
    scores = [s for _, s in res]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == pytest.approx(1.0, abs=1e-5)
    assert scores[1] == pytest.approx(_cos(q, [1.0, 1.0, 0.0]), abs=1e-5)
    assert scores[2] == pytest.approx(0.0, abs=1e-5)


@pytest.mark.asyncio
async def test_sqlite_search_continua_devolvendo_so_chunks(store):
    res = await store.search([1.0, 0.0, 0.0], top_k=2, threshold=0.0)
    assert [c.content for c in res] == ["igual", "parecido"]


@pytest.mark.asyncio
async def test_sqlite_threshold_filtra_por_score(store):
    res = await store.search_with_scores([1.0, 0.0, 0.0], top_k=3, threshold=0.5)
    assert [c.content for c, _ in res] == ["igual", "parecido"]


class _Embedder(EmbeddingProvider):
    def __init__(self):
        cfg = MagicMock()
        cfg.dimensions = 3
        super().__init__(cfg)

    @property
    def dimensions(self):
        return 3

    async def embed(self, text):
        return [1.0, 0.0, 0.0]

    async def embed_batch(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]

    async def health_check(self):
        return True


class _LLM(LLMProvider):
    def __init__(self):
        super().__init__(MagicMock())

    async def complete(self, messages, temperature=None, max_tokens=None):
        return LLMResponse(content="Resposta. [1] [2]", input_tokens=1, output_tokens=1, model="m")

    async def complete_stream(self, messages, temperature=None, max_tokens=None):
        yield "Resposta. [1] [2]"

    async def health_check(self):
        return True

    def count_tokens(self, text):
        return 1


@pytest.mark.asyncio
async def test_query_usa_scores_reais_do_store(store):
    pipeline = RAGPipeline(embedder=_Embedder(), vector_store=store, llm=_LLM())

    result = await pipeline.query("pergunta", QueryConfig(top_k=2, threshold=0.0, no_synthesis=True))

    assert result.scores[0] == pytest.approx(1.0, abs=1e-5)
    assert result.scores[1] == pytest.approx(_cos([1, 0, 0], [1, 1, 0]), abs=1e-5)
    assert result.scores != [1.0, 1.0]


class _StoreSemScore(VectorStore):
    """Store antigo, que só implementa search(): deve continuar funcionando."""

    def __init__(self, chunks):
        self._chunks = chunks

    async def init_db(self):
        pass

    async def add_chunks(self, chunks):
        return 0

    async def search(self, query_embedding, top_k=5, threshold=0.0):
        return self._chunks[:top_k]

    async def get_chunks_by_doc(self, document_id):
        return []

    async def delete_document(self, document_id):
        return 0

    async def get_stats(self):
        return {}

    async def document_exists_by_hash(self, content_hash):
        return False


@pytest.mark.asyncio
async def test_store_sem_score_usa_fallback_com_aviso(caplog):
    doc = uuid4()
    s = _StoreSemScore([_chunk("a", None, doc), _chunk("b", None, doc)])

    with caplog.at_level("WARNING"):
        res = await s.search_with_scores([0.0], top_k=2)

    assert [sc for _, sc in res] == [1.0, 1.0]
    assert "não implementa search_with_scores" in caplog.text
