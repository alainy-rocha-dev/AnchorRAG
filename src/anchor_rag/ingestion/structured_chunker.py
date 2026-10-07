"""Chunker estruturado para documentos normativos (artigos, incisos, parágrafos)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
from uuid import UUID, uuid4
import re
import tiktoken

from anchor_rag.utils.text import sanitize_text, count_tokens
from anchor_rag.domain.models import Chunk, ChunkUnit


@dataclass
class StructuredChunk:
    """Chunk com estrutura normativa preservada."""
    tipo: str           # "artigo", "paragrafo", "inciso", "alinea", "pagina"
    numero: str         # número do artigo/inciso/etc
    titulo: str         # "Art. 5", "§ 2", "Inciso III", "Alínea a"
    conteudo: str       # texto completo do chunk
    pagina: Optional[int]
    subitems: List[dict]  # itens aninhados
    metadata: dict      # metadados extras (norma, vigência, etc)


@dataclass
class ChunkingResult:
    """Resultado do chunking."""
    chunks: List[Chunk]
    total_chunks: int
    total_tokens: int


class StructuredChunker:
    """
    Chunker que preserva estrutura de normas jurídicas.
    
    Extrai: Art. X, § Y, Inciso Z, Alínea W
    Cria chunks por artigo (com seus incisos/parágrafos aninhados).
    Fallback: chunking por página se estrutura não detectada.
    """
    
    # Padrões regex para estrutura normativa brasileira
    ARTIGO_RE = re.compile(r"^Art\.\s*(\d+)([ºª])?\s*[.-]?\s*(.*)$", re.IGNORECASE | re.MULTILINE)
    PARAGRAFO_RE = re.compile(r"^§\s*(\d+)([ºª])?\s*[.-]?\s*(.*)$", re.IGNORECASE | re.MULTILINE)
    INCISO_RE = re.compile(r"^(?:Inc|Inciso)\s+([IVXLCM\d]+)\s*[.-]?\s*(.*)$", re.IGNORECASE | re.MULTILINE)
    ALINEA_RE = re.compile(r"^([a-z])\)\s+(.*)$", re.MULTILINE)
    
    # Padrões alternativos
    ARTIGO_ALT_RE = re.compile(r"^Artigo\s+(\d+)\s*[.-]?\s*(.*)$", re.IGNORECASE | re.MULTILINE)
    PARAGRAFO_UNICO_RE = re.compile(r"^Parágrafo\s+único\s*[.-]?\s*(.*)$", re.IGNORECASE | re.MULTILINE)
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        chunk_unit: ChunkUnit = ChunkUnit.TOKENS,
        encoding_name: str = "cl100k_base",
        norma_id: Optional[str] = None,
        ano: Optional[int] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunk_unit = chunk_unit
        self.encoding_name = encoding_name
        self.norma_id = norma_id
        self.ano = ano
        
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
        """Faz chunking estruturado de um documento normativo."""
        sanitized = sanitize_text(full_text)
        
        # 1. Tenta extrair estrutura
        structured_chunks = self._extract_structure(sanitized, page_texts)
        
        # 2. Se não encontrou estrutura, fallback para chunking por página
        if not structured_chunks and page_texts:
            structured_chunks = self._chunk_by_page(page_texts)
        elif not structured_chunks:
            # Último recurso: chunking por tokens tradicional
            return self._fallback_token_chunking(document_id, sanitized, page_texts)
        
        # 3. Converte para Chunks do domínio
        chunks = self._to_domain_chunks(document_id, structured_chunks)
        
        total_tokens = sum(c.token_count or 0 for c in chunks)
        return ChunkingResult(chunks=chunks, total_chunks=len(chunks), total_tokens=total_tokens)
    
    def _extract_structure(
        self,
        text: str,
        page_texts: Optional[List[str]] = None,
    ) -> List[StructuredChunk]:
        """Extrai estrutura hierárquica: Artigo → Parágrafo/Inciso → Alínea."""
        chunks = []
        
        # Mapeia posição no texto para página
        page_map = self._build_page_map(page_texts) if page_texts else None
        
        # Encontra todos os artigos
        artigo_matches = list(self.ARTIGO_RE.finditer(text))
        if not artigo_matches:
            artigo_matches = list(self.ARTIGO_ALT_RE.finditer(text))
        
        if not artigo_matches:
            return []  # Sem estrutura detectada
        
        for i, art_match in enumerate(artigo_matches):
            art_num = art_match.group(1)
            art_title = f"Art. {art_num}"
            art_start = art_match.start()
            art_end = artigo_matches[i + 1].start() if i + 1 < len(artigo_matches) else len(text)
            art_text = text[art_start:art_end].strip()
            
            # Extrai parágrafos e incisos dentro do artigo
            subitems = []
            sub_chunks = []
            
            # Parágrafos
            for par_match in self.PARAGRAFO_RE.finditer(art_text):
                subitems.append({
                    "tipo": "paragrafo",
                    "numero": par_match.group(1),
                    "texto": par_match.group(0).strip(),
                })
            for par_match in self.PARAGRAFO_UNICO_RE.finditer(art_text):
                subitems.append({
                    "tipo": "paragrafo",
                    "numero": "único",
                    "texto": par_match.group(0).strip(),
                })
            
            # Incisos
            for inc_match in self.INCISO_RE.finditer(art_text):
                subitems.append({
                    "tipo": "inciso",
                    "numero": inc_match.group(1),
                    "texto": inc_match.group(0).strip(),
                })
            
            # Alíneas (dentro de incisos)
            for ali_match in self.ALINEA_RE.finditer(art_text):
                subitems.append({
                    "tipo": "alinea",
                    "letra": ali_match.group(1),
                    "texto": ali_match.group(0).strip(),
                })
            
            # Ordena subitems por posição no texto
            subitems.sort(key=lambda x: art_text.find(x["texto"]))
            
            # Constrói conteúdo do artigo (inclui subitems)
            conteudo = art_match.group(0).strip()
            if art_match.group(3):
                conteudo += " " + art_match.group(3).strip()
            
            # Adiciona textos dos subitems ao conteúdo
            for sub in subitems:
                conteudo += "\n" + sub["texto"]
            
            pagina = self._find_page(art_start, page_map) if page_map else None
            
            chunks.append(StructuredChunk(
                tipo="artigo",
                numero=art_num,
                titulo=art_title,
                conteudo=conteudo,
                pagina=pagina,
                subitems=subitems,
                metadata={
                    "norma": self.norma_id,
                    "ano": self.ano,
                    "artigo": art_num,
                },
            ))
        
        return chunks
    
    def _chunk_by_page(self, page_texts: List[str]) -> List[StructuredChunk]:
        """Fallback: chunk por página."""
        chunks = []
        for i, page_text in enumerate(page_texts, 1):
            if not page_text.strip():
                continue
            chunks.append(StructuredChunk(
                tipo="pagina",
                numero=str(i),
                titulo=f"Página {i}",
                conteudo=page_text.strip(),
                pagina=i,
                subitems=[],
                metadata={"norma": self.norma_id, "ano": self.ano},
            ))
        return chunks
    
    def _fallback_token_chunking(
        self,
        document_id: UUID,
        text: str,
        page_texts: Optional[List[str]] = None,
    ) -> ChunkingResult:
        """Fallback para chunking por tokens tradicional."""
        from anchor_rag.ingestion.chunker import Chunker
        fallback = Chunker(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            chunk_unit=self.chunk_unit,
            encoding_name=self.encoding_name,
        )
        return fallback.chunk_document(document_id, text, page_texts)
    
    def _build_page_map(self, page_texts: List[str]) -> List[Tuple[int, int]]:
        """Constrói mapa de offset → página."""
        page_map = []
        accumulated = 0
        for page_text in page_texts:
            start = accumulated
            end = accumulated + len(page_text)
            page_map.append((start, end))
            accumulated = end
        return page_map
    
    def _find_page(self, offset: int, page_map: List[Tuple[int, int]]) -> Optional[int]:
        """Encontra página para um offset."""
        for i, (start, end) in enumerate(page_map, 1):
            if start <= offset < end:
                return i
        return len(page_map) if page_map else None
    
    def _to_domain_chunks(
        self,
        document_id: UUID,
        structured: List[StructuredChunk],
    ) -> List[Chunk]:
        """Converte StructuredChunk para Chunk do domínio."""
        chunks = []
        
        for idx, schunk in enumerate(structured):
            token_count = count_tokens(schunk.conteudo, self.encoding_name)
            
            # Se chunk muito grande, subdivide mantendo metadados
            if token_count > self.chunk_size * 1.5:
                sub_chunks = self._split_large_chunk(schunk, token_count)
                for sub_idx, sub_chunk in enumerate(sub_chunks):
                    chunks.append(self._create_chunk(
                        document_id, idx * 100 + sub_idx, sub_chunk, schunk
                    ))
            else:
                chunks.append(self._create_chunk(document_id, idx, schunk.conteudo, schunk))
        
        return chunks
    
    def _split_large_chunk(
        self,
        schunk: StructuredChunk,
        token_count: int,
    ) -> List[str]:
        """Divide chunk grande mantendo estrutura."""
        from anchor_rag.utils.text import chunk_by_tokens
        return chunk_by_tokens(
            schunk.conteudo,
            self.chunk_size,
            self.chunk_overlap,
            model=self.encoding_name,
        )
    
    def _create_chunk(
        self,
        document_id: UUID,
        chunk_index: int,
        content: str,
        schunk: StructuredChunk,
    ) -> Chunk:
        token_count = count_tokens(content, self.encoding_name)
        
        return Chunk(
            id=uuid4(),
            document_id=document_id,
            content=content,
            chunk_index=chunk_index,
            page_number=schunk.pagina,
            start_char=0,  # Não rastreado no estruturado
            end_char=len(content),
            token_count=token_count,
            embedding=None,
            metadata={
                **schunk.metadata,
                "chunk_tipo": schunk.tipo,
                "chunk_numero": schunk.numero,
                "chunk_titulo": schunk.titulo,
                "subitems": schunk.subitems,
            },
        )


class LegalChunker(StructuredChunker):
    """Alias semântico para chunker jurídico."""
    pass