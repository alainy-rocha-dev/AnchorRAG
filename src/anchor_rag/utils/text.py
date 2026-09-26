"""Utilitários de texto: sanitização, contagem, hash."""

import hashlib
import re
import unicodedata
from typing import List
import tiktoken


def sha256_hash(content: bytes) -> str:
    """Calcula SHA256 hex do conteúdo."""
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: str) -> str:
    """Calcula SHA256 hex de um arquivo."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sanitize_text(text: str) -> str:
    """Remove caracteres de controle e normaliza hifenização."""
    if not text:
        return ""

    # Remove caracteres de controle (exceto \n, \t)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

    # Normaliza unicode (NFKC)
    text = unicodedata.normalize("NFKC", text)

    # Fix hifenização: remove hífen + quebra de linha
    text = re.sub(r"-\n(\w)", r"\1", text)

    # Colapsa múltiplas quebras de linha
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove espaços trailing em cada linha
    text = "\n".join(line.rstrip() for line in text.splitlines())

    return text.strip()


def count_chars(text: str) -> int:
    """Conta caracteres no texto."""
    return len(text)


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Conta tokens usando tiktoken."""
    try:
        encoding = tiktoken.get_encoding(model)
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def chunk_by_tokens(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    model: str = "cl100k_base",
) -> List[str]:
    """Divide texto em chunks por tokens com overlap."""
    try:
        encoding = tiktoken.get_encoding(model)
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens = encoding.encode(text)
    if not tokens:
        return []

    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(encoding.decode(chunk_tokens))
        if end == len(tokens):
            break
        start = end - chunk_overlap
        if start < 0:
            start = 0
    return chunks


def chunk_by_chars(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[str]:
    """Divide texto em chunks por caracteres com overlap."""
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - chunk_overlap
        if start < 0:
            start = 0
    return chunks


def generate_uuid() -> str:
    """Gera UUID v4 como string."""
    import uuid
    return str(uuid.uuid4())


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Trunca texto preservando palavras."""
    if len(text) <= max_length:
        return text
    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(" ")
    if last_space > max_length * 0.8:
        truncated = truncated[:last_space]
    return truncated + suffix