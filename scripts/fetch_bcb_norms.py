#!/usr/bin/env python3
"""
Script para baixar e normalizar normas do Banco Central do Brasil (BCB).

Fonte: https://www.bcb.gov.br/estabilidadefinanceira/buscanormas
- Resoluções CMN (Conselho Monetário Nacional)
- Resoluções BCB (Banco Central)
- Circulares, Cartas Circulares, Comunicados

Uso:
    python scripts/fetch_bcb_norms.py --output-dir data/bcb_norms --max-norms 50
    python scripts/fetch_bcb_norms.py --resume --output-dir data/bcb_norms
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import aiofiles
import aiohttp
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.bcb.gov.br"
SEARCH_URL = f"{BASE_URL}/estabilidadefinanceira/buscanormas"

NORM_TYPES = {
    "resolucao_cmn": "Resolução CMN",
    "resolucao_bcb": "Resolução BCB",
    "circular": "Circular",
    "carta_circular": "Carta Circular",
    "comunicado": "Comunicado",
}

@dataclass
class NormMetadata:
    """Metadados de uma norma do BCB."""
    id: str
    tipo: str
    numero: str
    ano: int
    data_publicacao: str
    titulo: str
    ementa: str
    url_pdf: str
    url_html: str
    arquivo_local: Optional[str] = None
    content_hash: Optional[str] = None
    downloaded_at: Optional[str] = None
    tamanho_bytes: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def filename(self) -> str:
        safe_titulo = re.sub(r'[^\w\s-]', '', self.titulo)[:80]
        safe_titulo = re.sub(r'\s+', '_', safe_titulo)
        return f"{self.tipo}_{self.numero}_{self.ano}_{safe_titulo}.pdf"

    @property
    def json_filename(self) -> str:
        return self.filename.replace(".pdf", ".json")


async def fetch_page(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """Baixa uma página HTML."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                return await resp.text()
            logger.warning(f"HTTP {resp.status} para {url}")
    except Exception as e:
        logger.error(f"Erro ao baixar {url}: {e}")
    return None


async def download_pdf(session: aiohttp.ClientSession, url: str, dest: Path) -> Optional[dict]:
    """Baixa um PDF e retorna metadados."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            if resp.status != 200:
                logger.warning(f"HTTP {resp.status} para PDF {url}")
                return None
            
            content = await resp.read()
            dest.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(dest, "wb") as f:
                await f.write(content)
            
            content_hash = hashlib.sha256(content).hexdigest()
            return {
                "path": str(dest),
                "hash": content_hash,
                "size": len(content),
            }
    except Exception as e:
        logger.error(f"Erro ao baixar PDF {url}: {e}")
    return None


def parse_norm_list(html: str, base_url: str) -> list[NormMetadata]:
    """Parseia a lista de normas da página de busca."""
    soup = BeautifulSoup(html, "html.parser")
    norms = []
    
    # A estrutura exata depende do HTML do BCB - adaptar conforme necessário
    # Procura por tabelas ou listas de normas
    for row in soup.select("table tr, .norma-item, .resultado-item"):
        try:
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            
            # Extrai informações básicas - ajustar seletores conforme HTML real
            tipo_elem = cells[0].get_text(strip=True)
            numero_elem = cells[1].get_text(strip=True)
            titulo_elem = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            
            # Tenta extrair link do PDF
            pdf_link = None
            for link in row.find_all("a", href=True):
                href = link["href"]
                if ".pdf" in href.lower():
                    pdf_link = urljoin(base_url, href)
                    break
            
            if not pdf_link:
                continue
            
            # Parseia tipo e número
            tipo_match = re.search(r"(Resolução|Circular|Carta Circular|Comunicado)\s+(CMN|BCB)?", tipo_elem, re.IGNORECASE)
            if not tipo_match:
                continue
            
            tipo_raw = tipo_match.group(1).lower()
            orgao = tipo_match.group(2) or ""
            
            if "resolução" in tipo_raw:
                tipo = "resolucao_cmn" if "cmn" in orgao.lower() else "resolucao_bcb"
            elif "circular" in tipo_raw and "carta" in tipo_raw:
                tipo = "carta_circular"
            elif "circular" in tipo_raw:
                tipo = "circular"
            else:
                tipo = "comunicado"
            
            numero_match = re.search(r"(\d+)[/\-](\d{4})", numero_elem)
            if not numero_match:
                continue
            numero, ano = numero_match.groups()
            
            # Ementa (pode estar em célula separada ou tooltip)
            ementa = cells[3].get_text(strip=True) if len(cells) > 3 else ""
            
            norm = NormMetadata(
                id=f"{tipo}_{numero}_{ano}",
                tipo=tipo,
                numero=numero,
                ano=int(ano),
                data_publicacao="",  # Preencher se disponível
                titulo=titulo_elem,
                ementa=ementa,
                url_pdf=pdf_link,
                url_html="",
            )
            norms.append(norm)
            
        except Exception as e:
            logger.debug(f"Erro ao parsear linha: {e}")
            continue
    
    return norms


async def search_norms(
    session: aiohttp.ClientSession,
    tipo: str = "",
    ano: int = 0,
    palavra_chave: str = "",
    pagina: int = 1,
) -> str:
    """Faz busca na página de normas do BCB."""
    params = {"pagina": pagina}
    if tipo:
        params["tipo"] = tipo
    if ano:
        params["ano"] = ano
    if palavra_chave:
        params["palavraChave"] = palavra_chave
    
    # A URL real de busca pode ser diferente - ajustar conforme BCB
    search_url = f"{SEARCH_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    return await fetch_page(session, search_url) or ""


async def fetch_all_norms(
    output_dir: Path,
    max_norms: int = 50,
    resume: bool = False,
    anos: Optional[list[int]] = None,
    tipos: Optional[list[str]] = None,
) -> list[NormMetadata]:
    """Baixa todas as normas conforme filtros."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    metadata_file = output_dir / "norms_metadata.json"
    existing_norms = {}
    
    if resume and metadata_file.exists():
        async with aiofiles.open(metadata_file, "r", encoding="utf-8") as f:
            data = json.loads(await f.read())
            for n in data:
                existing_norms[n["id"]] = NormMetadata(**n)
        logger.info(f"Retomando: {len(existing_norms)} normas já baixadas")
    
    connector = aiohttp.TCPConnector(limit=5)
    timeout = aiohttp.ClientTimeout(total=60)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        all_norms = []
        
        # Anos padrão: últimos 5 anos
        if anos is None:
            current_year = datetime.now().year
            anos = list(range(current_year - 4, current_year + 1))
        
        if tipos is None:
            tipos = list(NORM_TYPES.keys())
        
        for ano in anos:
            for tipo in tipos:
                if len(all_norms) >= max_norms:
                    break
                
                logger.info(f"Buscando {NORM_TYPES.get(tipo, tipo)} de {ano}...")
                page = 1
                while len(all_norms) < max_norms:
                    html = await search_norms(session, tipo=tipo, ano=ano, pagina=page)
                    if not html:
                        break
                    
                    norms = parse_norm_list(html, BASE_URL)
                    if not norms:
                        break
                    
                    for norm in norms:
                        if norm.id in existing_norms:
                            all_norms.append(existing_norms[norm.id])
                            continue
                        if len(all_norms) >= max_norms:
                            break
                        all_norms.append(norm)
                    
                    page += 1
                    await asyncio.sleep(0.5)  # Rate limiting
        
        # Baixa PDFs
        logger.info(f"Baixando {len(all_norms)} PDFs...")
        semaphore = asyncio.Semaphore(3)
        
        async def download_one(norm: NormMetadata) -> NormMetadata:
            async with semaphore:
                if norm.arquivo_local and Path(norm.arquivo_local).exists():
                    return norm
                
                dest = output_dir / "pdfs" / norm.filename
                result = await download_pdf(session, norm.url_pdf, dest)
                if result:
                    norm.arquivo_local = result["path"]
                    norm.content_hash = result["hash"]
                    norm.tamanho_bytes = result["size"]
                    norm.downloaded_at = datetime.now().isoformat()
                    logger.info(f"  ✓ {norm.filename} ({result['size']} bytes)")
                else:
                    logger.warning(f"  ✗ Falha: {norm.id}")
                await asyncio.sleep(0.3)
                return norm
        
        all_norms = await asyncio.gather(*[download_one(n) for n in all_norms])
        
        # Salva metadados
        async with aiofiles.open(metadata_file, "w", encoding="utf-8") as f:
            await f.write(json.dumps([n.to_dict() for n in all_norms], ensure_ascii=False, indent=2))
        
        logger.info(f"Metadados salvos em {metadata_file}")
        return all_norms


def extract_text_from_pdf(pdf_path: Path) -> tuple[str, list[dict]]:
    """Extrai texto estruturado do PDF (artigos, incisos, parágrafos)."""
    import pdfplumber
    
    full_text = []
    structure = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            full_text.append(text)
            
            # Tenta identificar estrutura: Art. X, § Y, Inciso Z
            lines = text.split("\n")
            for line_num, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # Padrões de estrutura normativa
                art_match = re.match(r"Art\.\s*(\d+)([ºª])?", line, re.IGNORECASE)
                paragrafo_match = re.match(r"§\s*(\d+)([ºª])?", line)
                inciso_match = re.match(r"(Inc|Inciso)\s+([IVXLCM\d]+)", line, re.IGNORECASE)
                alinea_match = re.match(r"([a-z])\)", line)
                
                if art_match:
                    structure.append({
                        "tipo": "artigo",
                        "numero": art_match.group(1),
                        "texto": line,
                        "pagina": page_num,
                        "linha": line_num,
                    })
                elif paragrafo_match:
                    structure.append({
                        "tipo": "paragrafo",
                        "numero": paragrafo_match.group(1),
                        "texto": line,
                        "pagina": page_num,
                        "linha": line_num,
                    })
                elif inciso_match:
                    structure.append({
                        "tipo": "inciso",
                        "numero": inciso_match.group(2),
                        "texto": line,
                        "pagina": page_num,
                        "linha": line_num,
                    })
                elif alinea_match and structure and structure[-1]["tipo"] == "inciso":
                    structure.append({
                        "tipo": "alinea",
                        "letra": alinea_match.group(1),
                        "texto": line,
                        "pagina": page_num,
                        "linha": line_num,
                    })
    
    return "\n\n".join(full_text), structure


async def process_norms_for_rag(norms: list[NormMetadata], output_dir: Path) -> list[dict]:
    """Processa normas baixadas para formato pronto para RAG (chunking por artigo)."""
    output_dir = Path(output_dir)
    processed_dir = output_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    processed = []
    
    for norm in norms:
        if not norm.arquivo_local or not Path(norm.arquivo_local).exists():
            continue
        
        pdf_path = Path(norm.arquivo_local)
        full_text, structure = extract_text_from_pdf(pdf_path)
        
        # Cria chunks por artigo/inciso
        chunks = []
        current_artigo = None
        
        for item in structure:
            if item["tipo"] == "artigo":
                if current_artigo:
                    chunks.append(current_artigo)
                current_artigo = {
                    "tipo": "artigo",
                    "artigo": item["numero"],
                    "titulo": f"Art. {item['numero']}",
                    "conteudo": item["texto"],
                    "pagina": item["pagina"],
                    "subitems": [],
                }
            elif item["tipo"] in ("paragrafo", "inciso", "alinea") and current_artigo:
                current_artigo["conteudo"] += "\n" + item["texto"]
                current_artigo["subitems"].append(item)
        
        if current_artigo:
            chunks.append(current_artigo)
        
        # Se não encontrou estrutura, fallback: chunk por página
        if not chunks:
            with open(pdf_path, "rb") as f:
                import pdfplumber
                with pdfplumber.open(f) as pdf:
                    for page_num, page in enumerate(pdf.pages, 1):
                        text = page.extract_text() or ""
                        if text.strip():
                            chunks.append({
                                "tipo": "pagina",
                                "pagina": page_num,
                                "titulo": f"Página {page_num}",
                                "conteudo": text,
                                "subitems": [],
                            })
        
        # Salva chunks estruturados
        norm_data = {
            "metadata": norm.to_dict(),
            "full_text": full_text,
            "structure": structure,
            "chunks": chunks,
            "processed_at": datetime.now().isoformat(),
        }
        
        json_path = processed_dir / norm.json_filename
        async with aiofiles.open(json_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(norm_data, ensure_ascii=False, indent=2))
        
        processed.append(norm_data)
        logger.info(f"Processado: {norm.id} → {len(chunks)} chunks estruturados")
    
    return processed


async def main():
    parser = argparse.ArgumentParser(description="Baixa e processa normas do BCB")
    parser.add_argument("--output-dir", default="data/bcb_norms", help="Diretório de saída")
    parser.add_argument("--max-norms", type=int, default=50, help="Máximo de normas para baixar")
    parser.add_argument("--resume", action="store_true", help="Retomar download anterior")
    parser.add_argument("--anos", nargs="+", type=int, help="Anos específicos (ex: 2022 2023 2024)")
    parser.add_argument("--tipos", nargs="+", choices=list(NORM_TYPES.keys()), help="Tipos de norma")
    parser.add_argument("--process-only", action="store_true", help="Apenas processa PDFs já baixados")
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    
    if args.process_only:
        metadata_file = output_dir / "norms_metadata.json"
        if not metadata_file.exists():
            logger.error("Arquivo de metadados não encontrado. Rode sem --process-only primeiro.")
            return 1
        async with aiofiles.open(metadata_file, "r", encoding="utf-8") as f:
            data = json.loads(await f.read())
        norms = [NormMetadata(**n) for n in data]
        await process_norms_for_rag(norms, output_dir)
        return 0
    
    norms = await fetch_all_norms(
        output_dir,
        max_norms=args.max_norms,
        resume=args.resume,
        anos=args.anos,
        tipos=args.tipos,
    )
    
    if norms:
        await process_norms_for_rag(norms, output_dir)
        logger.info(f"Concluído: {len(norms)} normas processadas em {output_dir}/processed")
    else:
        logger.warning("Nenhuma norma baixada")
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))