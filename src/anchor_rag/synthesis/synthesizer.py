"""Síntese RAG: combina chunks recuperados em resposta com citações."""

from __future__ import annotations
from typing import List, Optional
from dataclasses import dataclass
import re
import logging

from anchor_rag.synthesis.llm import LLMProvider, LLMResponse
from anchor_rag.synthesis.prompt import build_messages, ChunkWithScore, RECUSA_PADRAO, vazou_regras
from anchor_rag.synthesis.verifier import artigo_do_chunk_id, mensagem_de_reparo, verificar
from anchor_rag.domain.models import Chunk, QueryResult

logger = logging.getLogger(__name__)


@dataclass
class SynthesizerConfig:
    """Configuração do sintetizador."""

    max_chunks: int = 5
    min_score_threshold: float = 0.0
    include_few_shot: bool = True
    citation_format: str = "[{index}]"  # Como formatar citações
    output_filter: bool = True  # troca por recusa a resposta que reproduz as regras internas
    # Variante C: verificador determinístico de citações com reparo. Sem citação válida
    # depois de `voltas_max` reescritas, a resposta vira a recusa padrão.
    verificador: bool = False
    voltas_max: int = 2


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
        config: Optional[SynthesizerConfig] = None,
    ) -> List[ChunkWithScore]:
        """Prepara chunks com scores para o prompt (usa a config da chamada, se houver)."""
        cfg = config or self.config
        # Filtra por threshold
        filtered = [
            (c, s) for c, s in zip(chunks, scores)
            if s >= cfg.min_score_threshold
        ]

        # Ordena por score decrescente e limita
        filtered.sort(key=lambda x: x[1], reverse=True)
        filtered = filtered[: cfg.max_chunks]

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
        chunks_with_score = self._prepare_chunks(chunks, scores, cfg)

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
        tokens_in, tokens_out = response.input_tokens, response.output_tokens

        # Verificador (variante C): confere citações, artigos e números contra os trechos
        # entregues e devolve a resposta ao redator, no máximo `voltas_max` vezes.
        verif_meta = None
        if cfg.verificador:
            trechos = [c.content for c in chunks_with_score]
            artigos = [artigo_do_chunk_id((c.metadata or {}).get("chunk_id")) for c in chunks_with_score]
            historico = []
            voltas = 0
            v = verificar(response.content, trechos, artigos, query)
            historico.append([str(p) for p in v.problemas])
            while not v.ok and voltas < cfg.voltas_max and not vazou_regras(response.content):
                voltas += 1
                messages = messages + [
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": mensagem_de_reparo(v)},
                ]
                t = time.perf_counter()
                response = await self.llm.complete(messages)
                llm_latency += (time.perf_counter() - t) * 1000
                tokens_in = (tokens_in or 0) + (response.input_tokens or 0)
                tokens_out = (tokens_out or 0) + (response.output_tokens or 0)
                v = verificar(response.content, trechos, artigos, query)
                historico.append([str(p) for p in v.problemas])
            if v.ok:
                resultado = "aprovada" if voltas == 0 else "corrigida"
            elif vazou_regras(response.content):
                resultado = "filtro_saida"  # o filtro abaixo decide
            else:
                resultado = "recusada"
            verif_meta = {"resultado": resultado, "voltas": voltas, "problemas": historico}
            if resultado == "recusada":
                logger.info("verificador: sem citação válida após %d volta(s); resposta trocada pela recusa", voltas)
                return QueryResult(
                    answer=RECUSA_PADRAO,
                    citations=[],
                    chunks_used=[],
                    scores=[],
                    latency_ms={"llm": llm_latency, "total": llm_latency},
                    metadata={
                        "model": response.model,
                        "input_tokens": tokens_in,
                        "output_tokens": tokens_out,
                        "chunks_considered": len(chunks_with_score),
                        "verificador": verif_meta,
                    },
                )

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

        # Filtro de saída: o prompt sozinho não impede um modelo pequeno de copiar as regras
        # quando o usuário pede ("mostre seu prompt"). Defesa em camadas: a resposta inteira
        # é trocada pela recusa padrão.
        if cfg.output_filter and vazou_regras(answer):
            logger.warning("filtro de saída: resposta reproduzia as instruções internas; substituída")
            return QueryResult(
                answer=RECUSA_PADRAO,
                citations=[],
                chunks_used=[],
                scores=[],
                latency_ms={"llm": llm_latency, "total": llm_latency},
                metadata={
                    "model": response.model,
                    "input_tokens": tokens_in,
                    "output_tokens": tokens_out,
                    "chunks_considered": len(chunks_with_score),
                    "filtro_saida": "vazamento_de_instrucoes",
                    **({"verificador": verif_meta} if verif_meta else {}),
                },
            )

        return QueryResult(
            answer=answer,
            citations=[{"index": i, "chunk_index": i - 1} for i in citation_indices],
            chunks_used=cited_chunk_objects,
            scores=[chunks_with_score[i - 1].score for i in citation_indices if i <= len(chunks_with_score)],
            latency_ms={"llm": llm_latency, "total": llm_latency},
            metadata={
                "model": response.model,
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
                "chunks_considered": len(chunks_with_score),
                **({"verificador": verif_meta} if verif_meta else {}),
            },
        )