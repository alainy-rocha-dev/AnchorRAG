"""Chunker: divide texto em chunks com metadados."""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID, uuid4
import tiktoken

from anchor_rag.utils.text import (
    sanitize_text,
    count_tokens,
    chunk_by_tokens,
    chunk_by_chars,
)
from anchor_rag.domain.models import Chunk, ChunkUnit


@dataclass
class ChunkingResult:
    """Resultado do chunking."""

    chunks: List[Chunk]
    total_chunks: int
    total_tokens: int


class Chunker:
    """Divide documentos em chunks com overlap e metadados completos."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        chunk_unit: ChunkUnit = ChunkUnit.TOKENS,
        encoding_name: str = "cl100k_base",
    ):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap deve ser menor que chunk_size")
        if chunk_size <= 0:
            raise ValueError("chunk_size deve ser maior que zero")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunk_unit = chunk_unit
        self.encoding_name = encoding_name

        try:
            self._encoding = tiktoken.get_encoding(encoding_name)
        except Exception:
            self._encoding = tiktoken.get_encoding("cl100k_base")

    def chunk_document(
        self,
        document_id: UUID,
        full_text: str,
        page_texts: Optional[List[str]] = None,
    ) -> ChunkingResult:
        """Faz chunking de um documento completo."""
        sanitized = sanitize_text(full_text)

        if self.chunk_unit == ChunkUnit.TOKENS:
            text_chunks = chunk_by_tokens(
                sanitized,
                self.chunk_size,
                self.chunk_overlap,
                model=self.encoding_name,
            )
        else:
            text_chunks = chunk_by_chars(sanitized, self.chunk_size, self.chunk_overlap)

        chunks = []
        char_offset = 0

        for idx, chunk_text in enumerate(text_chunks):
            token_count = count_tokens(chunk_text, self.encoding_name)

            # Estimar page_number se page_texts fornecido
            page_number = None
            if page_texts:
                page_number = self._estimate_page_number(chunk_text, page_texts, char_offset)

            start_char = char_offset
            end_char = char_offset + len(chunk_text)
            char_offset = end_char - self.chunk_overlap if idx < len(text_chunks) - 1 else end_char

            chunk = Chunk(
                id=uuid4(),
                document_id=document_id,
                content=chunk_text,
                chunk_index=idx,
                page_number=page_number,
                start_char=start_char,
                end_char=end_char,
                token_count=token_count,
                embedding=None,
                metadata={},
            )
            chunks.append(chunk)

        total_tokens = sum(c.token_count or 0 for c in chunks)
        return ChunkingResult(chunks=chunks, total_chunks=len(chunks), total_tokens=total_tokens)

    def _estimate_page_number(
        self, chunk_text: str, page_texts: List[str], char_offset: int
    ) -> Optional[int]:
        """Estima página baseada no offset no texto original."""
        accumulated = 0
        for i, page_text in enumerate(page_texts, start=1):
            accumulated += len(page_text)
            if accumulated > char_offset:
                return i
        return len(page_texts) if page_texts else None

    def chunk_text(self, text: str) -> List[str]:
        """Apenas divide texto, sem metadados."""
        sanitized = sanitize_text(text)
        if self.chunk_unit == ChunkUnit.TOKENS:
            return chunk_by_tokens(sanitized, self.chunk_size, self.chunk_overlap, self.encoding_name)
        return chunk_by_chars(sanitized, self.chunk_size, self.chunk_overlap)