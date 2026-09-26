"""Parsers de PDF: protocol + implementações pdfplumber e PyPDF."""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ParsedPage:
    """Página extraída do PDF."""

    page_number: int
    text: str
    tables: List[List[List[str]]]


class PDFParser(ABC):
    """Protocolo para parsers de PDF."""

    @abstractmethod
    def parse(self, path: str | Path) -> List[ParsedPage]:
        """Extrai texto e tabelas de todas as páginas."""
        pass

    @abstractmethod
    def get_page_count(self, path: str | Path) -> int:
        """Retorna número de páginas sem extrair conteúdo."""
        pass


class PdfPlumberParser(PDFParser):
    """Parser usando pdfplumber (melhor para tabelas)."""

    def __init__(self, extract_tables: bool = True):
        self.extract_tables = extract_tables

    def parse(self, path: str | Path) -> List[ParsedPage]:
        import pdfplumber

        pages = []
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                tables = []
                if self.extract_tables:
                    extracted_tables = page.extract_tables()
                    if extracted_tables:
                        for table in extracted_tables:
                            if table:
                                tables.append(table)
                pages.append(ParsedPage(page_number=i, text=text, tables=tables))
        logger.info(f"PdfPlumberParser: extraiu {len(pages)} páginas de {path}")
        return pages

    def get_page_count(self, path: str | Path) -> int:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return len(pdf.pages)


class PyPDFParser(PDFParser):
    """Parser usando PyPDF (fallback leve)."""

    def parse(self, path: str | Path) -> List[ParsedPage]:
        from pypdf import PdfReader

        pages = []
        reader = PdfReader(path)
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append(ParsedPage(page_number=i, text=text, tables=[]))
        logger.info(f"PyPDFParser: extraiu {len(pages)} páginas de {path}")
        return pages

    def get_page_count(self, path: str | Path) -> int:
        from pypdf import PdfReader

        reader = PdfReader(path)
        return len(reader.pages)


def create_parser(parser_type: str = "pdfplumber") -> PDFParser:
    """Factory para criar parser."""
    if parser_type == "pdfplumber":
        return PdfPlumberParser()
    elif parser_type == "pypdf":
        return PyPDFParser()
    else:
        raise ValueError(f"Parser desconhecido: {parser_type}. Use 'pdfplumber' ou 'pypdf'")