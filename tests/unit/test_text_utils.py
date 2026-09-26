"""Testes unitários para text.py."""

import pytest
from anchor_rag.utils.text import (
    sha256_hash,
    sha256_file,
    sanitize_text,
    count_chars,
    count_tokens,
    chunk_by_tokens,
    chunk_by_chars,
    generate_uuid,
    truncate_text,
)


class TestHash:
    def test_sha256_hash(self):
        content = b"hello world"
        result = sha256_hash(content)
        assert len(result) == 64
        assert result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

    def test_sha256_file(self, tmp_path):
        file_path = tmp_path / "test.txt"
        file_path.write_bytes(b"test content")
        result = sha256_file(str(file_path))
        assert len(result) == 64


class TestSanitizeText:
    def test_remove_control_chars(self):
        text = "hello\x00world\x01test"
        result = sanitize_text(text)
        assert "\x00" not in result
        assert "\x01" not in result
        assert result == "helloworldtest"

    def test_preserve_newline_tab(self):
        text = "hello\nworld\ttest"
        result = sanitize_text(text)
        assert "\n" in result
        assert "\t" in result

    def test_fix_hyphenation(self):
        text = "hyphen-\nated word"
        result = sanitize_text(text)
        assert result == "hyphenated word"

    def test_collapse_multiple_newlines(self):
        text = "line1\n\n\n\nline2"
        result = sanitize_text(text)
        assert result == "line1\n\nline2"

    def test_strip_trailing_spaces(self):
        text = "line1   \nline2\t\nline3"
        result = sanitize_text(text)
        assert not any(line.endswith(" ") for line in result.splitlines())


class TestCounting:
    def test_count_chars(self):
        assert count_chars("hello") == 5
        assert count_chars("") == 0

    def test_count_tokens(self):
        text = "hello world"
        tokens = count_tokens(text)
        assert tokens > 0
        assert isinstance(tokens, int)


class TestChunking:
    def test_chunk_by_chars_basic(self):
        text = "abcdefghijklmnopqrstuvwxyz"
        chunks = chunk_by_chars(text, chunk_size=10, chunk_overlap=2)
        assert len(chunks) > 1
        assert all(len(c) <= 10 for c in chunks)

    def test_chunk_by_chars_overlap(self):
        text = "abcdefghij"
        chunks = chunk_by_chars(text, chunk_size=5, chunk_overlap=1)
        assert chunks[0] == "abcde"
        assert chunks[1] == "efghi"

    def test_chunk_by_tokens_basic(self):
        text = "This is a test sentence for chunking by tokens."
        chunks = chunk_by_tokens(text, chunk_size=10, chunk_overlap=2)
        assert len(chunks) >= 1

    def test_chunk_empty_text(self):
        assert chunk_by_chars("", 10, 2) == []
        assert chunk_by_tokens("", 10, 2) == []


class TestUUID:
    def test_generate_uuid_format(self):
        uuid_str = generate_uuid()
        assert len(uuid_str) == 36
        assert uuid_str.count("-") == 4


class TestTruncate:
    def test_truncate_short(self):
        text = "short"
        assert truncate_text(text, 20) == "short"

    def test_truncate_long(self):
        text = "This is a very long text that should be truncated"
        result = truncate_text(text, 20)
        assert len(result) <= 20
        assert result.endswith("...")

    def test_truncate_preserves_words(self):
        text = "This is a sentence with words"
        result = truncate_text(text, 15)
        assert not result.rstrip("...").endswith(" ")