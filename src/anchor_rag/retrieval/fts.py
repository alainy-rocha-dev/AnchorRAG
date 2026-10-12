"""FTS5 (BM25) full-text search para SQLite."""

from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID
import json
import re
import sqlite3
import logging
from pathlib import Path

from anchor_rag.vector_store.base import VectorStore, Chunk

logger = logging.getLogger(__name__)

# Versão do esquema/tokenizador do índice. Mudou -> ensure_fts() recria e reindexa.
# v2: 'unicode61 remove_diacritics 2' (o 'porter' anterior é um stemmer de INGLÊS).
FTS_VERSION = "2"

# Palavras sem valor de busca: artigos, preposições, pronomes e interrogativos.
STOPWORDS_PT = frozenset("""
a o as os um uma uns umas de da do das dos em na no nas nos por pela pelo pelas pelos
para pra com sem sob sobre entre ate apos ao aos e ou mas nem que se ja nao sim
eu tu ele ela nos vos eles elas me te lhe lhes meu minha seu sua seus suas nosso nossa
este esta estes estas esse essa esses essas isto isso aquele aquela aquilo
qual quais quando onde como quanto quanta quantos quantas quem porque pois
ser estar ter haver sao foi era sera seria tem tinha deve devem pode podem ha
mais menos muito muita muitos muitas outro outra outros outras mesmo mesma todo toda todos todas
cada qualquer quaisquer algum alguma alguns algumas nenhum nenhuma
""".split())


def _sem_acento(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def build_fts_query(query: str, prefix_len: int = 7) -> Optional[str]:
    """Monta a consulta FTS5: termos relevantes, cada um como radical com prefixo, unidos por OR.

    Sem stemmer de português no FTS5, o radical com '*' aproxima flexões
    ("centralizar", "centralizada", "centralização" -> "central"*). Stopwords saem para não
    casar com quase todo trecho. O BM25 dá peso maior a quem casa termos mais raros.
    Devolve None se não sobrar termo.
    """
    termos = re.findall(r"\w+", _sem_acento(query))
    vistos, partes = set(), []
    for t in termos:
        if t in STOPWORDS_PT:
            continue
        if not t.isdigit() and len(t) < 3:
            continue
        raiz = t if (t.isdigit() or len(t) <= prefix_len) else t[:prefix_len]
        if raiz in vistos:
            continue
        vistos.add(raiz)
        partes.append(f'"{raiz}"' if t.isdigit() else f'"{raiz}"*')
    return " OR ".join(partes) if partes else None


class FTS5Store:
    """Busca full-text usando SQLite FTS5 (BM25 nativo)."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    async def init_fts(self) -> None:
        """Cria tabela FTS5 e triggers para sincronismo com chunks."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Tabela FTS5 com conteúdo sincronizado
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                content,
                document_id UNINDEXED,
                chunk_id UNINDEXED,
                chunk_index UNINDEXED,
                page_number UNINDEXED,
                norma UNINDEXED,
                artigo UNINDEXED,
                tokenize='unicode61 remove_diacritics 2'
            )
        """)

        # Triggers para manter FTS sincronizado com tabela chunks
        # Nota: chunks table agora tem rowid (inteiro) como PK e id (TEXT) como UUID
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                INSERT INTO chunks_fts(rowid, content, document_id, chunk_id, chunk_index, page_number, norma, artigo)
                VALUES (new.rowid, new.content, new.document_id, new.id, new.chunk_index, new.page_number,
                        json_extract(new.metadata, '$.norma'), json_extract(new.metadata, '$.artigo'));
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, content, document_id, chunk_id, chunk_index, page_number, norma, artigo)
                VALUES ('delete', old.rowid, old.content, old.document_id, old.id, old.chunk_index, old.page_number,
                        json_extract(old.metadata, '$.norma'), json_extract(old.metadata, '$.artigo'));
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, content, document_id, chunk_id, chunk_index, page_number, norma, artigo)
                VALUES ('delete', old.rowid, old.content, old.document_id, old.id, old.chunk_index, old.page_number,
                        json_extract(old.metadata, '$.norma'), json_extract(old.metadata, '$.artigo'));
                INSERT INTO chunks_fts(rowid, content, document_id, chunk_id, chunk_index, page_number, norma, artigo)
                VALUES (new.rowid, new.content, new.document_id, new.id, new.chunk_index, new.page_number,
                        json_extract(new.metadata, '$.norma'), json_extract(new.metadata, '$.artigo'));
            END
        """)

        conn.commit()
        logger.info("FTS5 inicializado com triggers de sincronismo")

    async def ensure_fts(self) -> bool:
        """Garante índice FTS na versão atual; recria e reindexa se faltar ou estiver velho.

        Devolve True se (re)construiu o índice.
        """
        conn = self._get_conn()
        conn.execute("CREATE TABLE IF NOT EXISTS store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        row = conn.execute("SELECT value FROM store_meta WHERE key = 'fts_version'").fetchone()
        existe = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='chunks_fts'"
        ).fetchone()
        if existe and row and row["value"] == FTS_VERSION:
            return False
        for trig in ("chunks_ai", "chunks_ad", "chunks_au"):
            conn.execute(f"DROP TRIGGER IF EXISTS {trig}")
        conn.execute("DROP TABLE IF EXISTS chunks_fts")
        conn.commit()
        await self.init_fts()
        n = await self.rebuild_fts()
        conn.execute(
            "INSERT INTO store_meta (key, value) VALUES ('fts_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (FTS_VERSION,),
        )
        conn.commit()
        logger.info(f"Índice FTS v{FTS_VERSION} construído: {n} chunks")
        return True

    async def search(
        self,
        query: str,
        top_k: int = 10,
        norma_filter: Optional[str] = None,
        artigo_filter: Optional[str] = None,
    ) -> List[Tuple[Chunk, float]]:
        """
        Busca BM25 via FTS5.
        
        Returns:
            Lista de (Chunk, score_bm25) ordenada por score decrescente.
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # Monta query FTS5
        fts_query = build_fts_query(query)
        if fts_query is None:
            return []

        where_clauses = ["chunks_fts MATCH ?"]
        params: List = [fts_query]
        
        if norma_filter:
            where_clauses.append("norma = ?")
            params.append(norma_filter)
        if artigo_filter:
            where_clauses.append("artigo = ?")
            params.append(artigo_filter)

        sql = f"""
            SELECT
                c.id, c.document_id, c.content, c.chunk_index, c.page_number,
                c.start_char, c.end_char, c.token_count, c.metadata,
                bm25(chunks_fts) as bm25_score
            FROM chunks_fts
            JOIN chunks c ON c.rowid = chunks_fts.rowid
            WHERE {' AND '.join(where_clauses)}
            ORDER BY bm25_score ASC
            LIMIT ?
        """
        params.append(top_k)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            # bm25() do FTS5 é negativo (mais negativo = mais relevante); o score é o oposto.
            # Antes: 1/(1+raw) só para raw > 0, que nunca ocorre -> todo score saía 1.0.
            score = -row["bm25_score"]

            chunk = Chunk(
                id=UUID(row["id"]),
                document_id=UUID(row["document_id"]),
                content=row["content"],
                chunk_index=row["chunk_index"],
                page_number=row["page_number"],
                start_char=row["start_char"],
                end_char=row["end_char"],
                token_count=row["token_count"],
                embedding=None,
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )
            results.append((chunk, score))

        return results

    def _build_fts_query(self, query: str) -> Optional[str]:
        """Compatibilidade: use build_fts_query()."""
        return build_fts_query(query)

    async def rebuild_fts(self) -> int:
        """Reconstrói índice FTS5 a partir da tabela chunks (útil na primeira vez)."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM chunks_fts")
        
        cursor.execute("""
            INSERT INTO chunks_fts(rowid, content, document_id, chunk_id, chunk_index, page_number, norma, artigo)
            SELECT
                rowid, content, document_id, id, chunk_index, page_number,
                json_extract(metadata, '$.norma'),
                json_extract(metadata, '$.artigo')
            FROM chunks
        """
        )
        
        count = cursor.rowcount
        conn.commit()
        logger.info(f"FTS5 reconstruído: {count} chunks indexados")
        return count

    async def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
