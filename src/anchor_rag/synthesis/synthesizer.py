"""Síntese RAG: combina chunks recuperados em resposta com citações."""

from __future__ import annotations
from typing import List, Optional
from dataclasses import dataclass
import re
import logging

from anchor_rag.synthesis.llm import LLMProvider, LLMResponse
from anchor_rag.synthesis.prompt import build_messages, ChunkWithScore
from anchor_rag.domain.models import Chunk, QueryResult

logger = logging.getLogger(__name__)


@dataclass
class SynthesizerConfig:
    """Configuração do sintetizador."""

    max_chunks: int = 5
    min_score_threshold: float = 0.0
    include_few_shot: bool = True
    citation_format: str = "[{index}]"  # Como formatar citações


class RAGSynthesizer:
    """Sintetiza resposta final a partir de chunks recuperados."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        config: Optional[SynthesizerConfig] = None,
    ):
        self.llm = llm_provider
        self.config = config or SynthesizerConfig()

    def _prepare_chunks(
        self,
        chunks: List[Chunk],
        scores: List[float],
    ) -> List[ChunkWithScore]:
        """Prepara chunks com scores para o prompt."""
        # Filtra por threshold
        filtered = [
            (c, s) for c, s in zip(chunks, scores)
            if s >= self.config.min_score_threshold
        ]

        # Ordena por score decrescente e limita
        filtered.sort(key=lambda x: x[1], reverse=True)
        filtered = filtered[: self.config.max_chunks]

        # Cria objetos com index 1-based para citações
        return [
            ChunkWithScore(
                content=c.content,
                score=s,
                metadata=c.metadata,
                index=i + 1,
                id=c.id,
                document_id=c.document_id,
            )
            for i, (c, s) in enumerate(filtered)
        ]

    def _extract_citations(self, answer: str, max_citation: int) -> List[int]:
        """Extrai números de citação da resposta."""
        # Procura padrões [1], [2], etc.
        pattern = r"\[(\d+)\]"
        matches = re.findall(pattern, answer)
        citations = []
        for m in matches:
            idx = int(m)
            if 1 <= idx <= max_citation and idx not in citations:
                citations.append(idx)
        return citations

    async def synthesize(
        self,
        query: str,
        chunks: List[Chunk],
        scores: List[float],
        config: Optional[SynthesizerConfig] = None,
    ) -> QueryResult:
        """Sintetiza resposta final."""
        cfg = config or self.config

        if not chunks:
            return QueryResult(
                answer="Não encontrei informações relevantes nos documentos para responder a essa pergunta.",
                citations=[],
                chunks_used=[],
                scores=[],
                latency_ms={},
            )

        # Prepara chunks para o prompt
        chunks_with_score = self._prepare_chunks(chunks, scores)

        # Constrói mensagens
        messages = build_messages(
            query=query,
            chunks=chunks_with_score,
            include_few_shot=cfg.include_few_shot,
        )

        # Chama LLM
        import time
        start = time.perf_counter()
        response: LLMResponse = await self.llm.complete(messages)
        llm_latency = (time.perf_counter() - start) * 1000

        # Extrai citações da resposta
        citation_indices = self._extract_citations(response.content, len(chunks_with_score))

        # Mapeia índices de volta para chunks originais
        cited_chunks = [chunks_with_score[i - 1] for i in citation_indices if i <= len(chunks_with_score)]
        from uuid import uuid4
        cited_chunk_objects = [
            Chunk(
                id=c.id or uuid4(),
                document_id=c.document_id or uuid4(),
                content=c.content,
                chunk_index=0,
                page_number=c.metadata.get("page_number"),
                start_char=0,
                end_char=len(c.content),
                token_count=None,
                embedding=None,
                metadata=c.metadata,
            )
            for c in cited_chunks
        ]

        # Formata citações na resposta se não estiverem presentes
        answer = response.content
        if citation_indices and not re.search(r"\[\d+\]", answer):
            # Adiciona citações no final se não houver
            citation_str = " ".join(cfg.citation_format.format(index=i) for i in citation_indices)
            answer = f"{answer} {citation_str}"

        return QueryResult(
            answer=answer,
            citations=[{"index": i, "chunk_index": i - 1} for i in citation_indices],
            chunks_used=cited_chunk_objects,
            scores=[chunks_with_score[i - 1].score for i in citation_indices if i <= len(chunks_with_score)],
            latency_ms={"llm": llm_latency, "total": llm_latency},
            metadata={
                "model": response.model,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "chunks_considered": len(chunks_with_score),
            },
        )