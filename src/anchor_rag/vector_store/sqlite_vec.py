"""Implementação do Vector Store usando SQLite com sqlite-vec."""

from __future__ import annotations
from typing import List, Optional
from uuid import UUID
import sqlite3
import sqlite_vec
import numpy as np
import json
import logging
from pathlib import Path

from anchor_rag.vector_store.base import VectorStore, Chunk

logger = logging.getLogger(__name__)


class SQLiteVecStore(VectorStore):
    """Vector Store usando SQLite com extensão sqlite-vec."""

    def __init__(self, db_path: str, embedding_dimensions: int = 1536):
        self.db_path = Path(db_path)
        self.embedding_dimensions = embedding_dimensions
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        """Obtém conexão, criando se necessário."""
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    async def init_db(self) -> None:
        """Cria tabelas e índices necessários."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Tabela de documentos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                filename TEXT NOT NULL,
                content_hash TEXT NOT NULL UNIQUE,
                page_count INTEGER,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabela de chunks com virtual table para vetores
        cursor.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(
                embedding float[{self.embedding_dimensions}]
            )
        """)

        # Tabela de metadados dos chunks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                content TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                page_number INTEGER,
                start_char INTEGER,
                end_char INTEGER,
                token_count INTEGER,
                metadata TEXT,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        """)

        # Índices
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash)
        """)

        # Tabela de query log (opcional)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS query_log (
                id TEXT PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                question TEXT NOT NULL,
                answer TEXT,
                top_k INTEGER,
                threshold REAL,
                chunks_retrieved INTEGER,
                citations_count INTEGER,
                latency_embed_ms REAL,
                latency_search_ms REAL,
                latency_synthesize_ms REAL,
                latency_total_ms REAL,
                llm_provider TEXT,
                llm_model TEXT,
                success BOOLEAN DEFAULT 1,
                error_message TEXT
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_log_timestamp ON query_log(timestamp)
        """)

        conn.commit()
        logger.info(f"SQLiteVecStore inicializado: {self.db_path}")

    def _serialize_embedding(self, embedding: List[float]) -> bytes:
        """Serializa embedding para blob sqlite-vec."""
        arr = np.array(embedding, dtype=np.float32)
        return arr.tobytes()

    def _deserialize_embedding(self, blob: bytes) -> List[float]:
        """Deserializa embedding do blob."""
        arr = np.frombuffer(blob, dtype=np.float32)
        return arr.tolist()

    async def add_chunks(self, chunks: List[Chunk]) -> int:
        """Adiciona chunks com embeddings."""
        if not chunks:
            return 0

        conn = self._get_conn()
        cursor = conn.cursor()

        inserted = 0
        for chunk in chunks:
            try:
                # Insere documento se não existe (upsert simples)
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO documents (id, path, filename, content_hash, page_count, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(chunk.document_id),
                        "",  # path será preenchido pelo pipeline
                        "",  # filename será preenchido pelo pipeline
                        "",  # content_hash será preenchido pelo pipeline
                        0,
                        "{}",
                    ),
                )

                # Insere chunk metadata
                cursor.execute(
                    """
                    INSERT INTO chunks (id, document_id, content, chunk_index, page_number,
                                       start_char, end_char, token_count, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(chunk.id),
                        str(chunk.document_id),
                        chunk.content,
                        chunk.chunk_index,
                        chunk.page_number,
                        chunk.start_char,
                        chunk.end_char,
                        chunk.token_count,
                        json.dumps(chunk.metadata),
                    ),
                )

                # Insere embedding na virtual table
                if chunk.embedding:
                    emb_blob = self._serialize_embedding(chunk.embedding)
                    cursor.execute(
                        "INSERT INTO chunks_vec (rowid, embedding) VALUES (?, ?)",
                        (str(chunk.id), emb_blob),
                    )

                inserted += 1

            except sqlite3.IntegrityError as e:
                logger.warning(f"Chunk duplicado ignorado: {chunk.id} - {e}")
            except Exception as e:
                logger.error(f"Erro ao inserir chunk {chunk.id}: {e}")
                raise

        conn.commit()
        logger.info(f"Inseridos {inserted} chunks no SQLiteVecStore")
        return inserted

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> List[Chunk]:
        """Busca por similaridade de cosseno usando sqlite-vec."""
        conn = self._get_conn()
        cursor = conn.cursor()

        query_blob = self._serialize_embedding(query_embedding)

        # Busca na virtual table - sqlite-vec retorna distance (L2) por padrão
        # Para cosseno, usamos: 1 - (distance^2 / 2) para vetores normalizados
        cursor.execute(
            """
            SELECT
                c.id, c.document_id, c.content, c.chunk_index, c.page_number,
                c.start_char, c.end_char, c.token_count, c.metadata,
                vec_distance_cosine(chunks_vec.embedding, ?) as distance
            FROM chunks c
            JOIN chunks_vec ON c.id = chunks_vec.rowid
            WHERE distance <= ?
            ORDER BY distance ASC
            LIMIT ?
            """,
            (query_blob, 1.0 - threshold, top_k),
        )

        rows = cursor.fetchall()
        results = []
        for row in rows:
            # Converte distance L2 para score de cosseno (1 - distance para vetores normalizados)
            distance = row["distance"]
            score = 1.0 - distance

            chunk = Chunk(
                id=UUID(row["id"]),
                document_id=UUID(row["document_id"]),
                content=row["content"],
                chunk_index=row["chunk_index"],
                page_number=row["page_number"],
                start_char=row["start_char"],
                end_char=row["end_char"],
                token_count=row["token_count"],
                embedding=None,  # Não retornamos embedding na busca
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )
            results.append((chunk, score))

        # Ordena por score decrescente
        results.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in results]

    async def get_chunks_by_doc(self, document_id: UUID) -> List[Chunk]:
        """Recupera todos os chunks de um documento."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, document_id, content, chunk_index, page_number,
                   start_char, end_char, token_count, metadata
            FROM chunks
            WHERE document_id = ?
            ORDER BY chunk_index
            """,
            (str(document_id),),
        )

        rows = cursor.fetchall()
        return [
            Chunk(
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
            for row in rows
        ]

    async def delete_document(self, document_id: UUID) -> int:
        """Remove documento e seus chunks (CASCADE)."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Primeiro pega os IDs dos chunks para remover da virtual table
        cursor.execute(
            "SELECT id FROM chunks WHERE document_id = ?",
            (str(document_id),),
        )
        chunk_ids = [row["id"] for row in cursor.fetchall()]

        # Remove da virtual table
        if chunk_ids:
            placeholders = ",".join("?" * len(chunk_ids))
            cursor.execute(
                f"DELETE FROM chunks_vec WHERE rowid IN ({placeholders})",
                chunk_ids,
            )

        # Remove chunks (CASCADE remove documento se não houver mais chunks)
        cursor.execute(
            "DELETE FROM chunks WHERE document_id = ?",
            (str(document_id),),
        )

        # Remove documento se órfão
        cursor.execute(
            "DELETE FROM documents WHERE id = ? AND NOT EXISTS (SELECT 1 FROM chunks WHERE document_id = ?)",
            (str(document_id), str(document_id)),
        )

        conn.commit()
        return len(chunk_ids)

    async def get_stats(self) -> dict:
        """Estatísticas do store."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM chunks")
        total_chunks = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM documents")
        total_documents = cursor.fetchone()["count"]

        return {
            "total_chunks": total_chunks,
            "total_documents": total_documents,
            "embedding_dimensions": self.embedding_dimensions,
            "db_path": str(self.db_path),
        }

    async def close(self):
        """Fecha conexão."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # Query Log methods
    async def log_query(
        self,
        query_id: str,
        question: str,
        answer: str,
        top_k: int,
        threshold: float,
        chunks_retrieved: int,
        citations_count: int,
        latency: dict,
        llm_provider: str,
        llm_model: str,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Registra query no log (se habilitado)."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO query_log (
                id, question, answer, top_k, threshold, chunks_retrieved,
                citations_count, latency_embed_ms, latency_search_ms,
                latency_synthesize_ms, latency_total_ms, llm_provider,
                llm_model, success, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query_id,
                question,
                answer,
                top_k,
                threshold,
                chunks_retrieved,
                citations_count,
                latency.get("embed", 0),
                latency.get("search", 0),
                latency.get("synthesize", 0),
                latency.get("total", 0),
                llm_provider,
                llm_model,
                success,
                error_message,
            ),
        )
        conn.commit()

    async def get_query_logs(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[dict]:
        """Recupera logs de queries."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM query_log
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_query_stats(self) -> dict:
        """Estatísticas do query log."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM query_log")
        total = cursor.fetchone()["total"]

        cursor.execute("SELECT AVG(latency_total_ms) as avg_latency FROM query_log WHERE success = 1")
        avg_latency = cursor.fetchone()["avg_latency"] or 0

        cursor.execute("SELECT COUNT(*) as failed FROM query_log WHERE success = 0")
        failed = cursor.fetchone()["failed"]

        return {
            "total_queries": total,
            "avg_latency_ms": round(avg_latency, 2),
            "failed_queries": failed,
        }