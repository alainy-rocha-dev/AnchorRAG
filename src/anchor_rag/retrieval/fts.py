"""FTS5 (BM25) full-text search para SQLite."""

from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID
import sqlite3
import logging
from pathlib import Path

from anchor_rag.vector_store.base import VectorStore, Chunk

logger = logging.getLogger(__name__)


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
                tokenize='porter unicode61'
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
        fts_query = self._build_fts_query(query)
        
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
            JOIN chunks c ON c.id = chunks_fts.chunk_id
            WHERE {' AND '.join(where_clauses)}
            ORDER BY bm25_score ASC
            LIMIT ?
        """
        params.append(top_k)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            # BM25: menor = melhor. Converte para score 0-1 (inverso)
            bm25_raw = row["bm25_score"]
            score = 1.0 / (1.0 + bm25_raw) if bm25_raw > 0 else 1.0

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

    def _build_fts_query(self, query: str) -> str:
        """Constrói query FTS5 com operadores booleanos e prefixos."""
        # Escapa caracteres especiais FTS5
        escaped = query.replace('"', '""').replace("'", "''")
        
        # Divide em termos e adiciona prefixo * para busca parcial
        terms = escaped.split()
        if not terms:
            return '""'
        
        # Usa NEAR para proximidade e OR entre termos principais
        if len(terms) == 1:
            return f'"{terms[0]}"*'
        
        # Combina: frase exata OU termos individuais com prefixo
        phrase = f'"{escaped}"'
        prefixed = " OR ".join(f'"{t}"*' for t in terms)
        return f"({phrase}) OR ({prefixed})"

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


import json  # noqa: E402