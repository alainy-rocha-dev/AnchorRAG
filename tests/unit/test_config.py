"""Testes unitários para config.py."""

import pytest
import os
import tempfile
from pathlib import Path
from anchor_rag.config import (
    EmbeddingConfig,
    LLMConfig,
    ChunkingConfig,
    VectorStoreConfig,
    LoggingConfig,
    QueryLogConfig,
    AppConfig,
)


class TestEmbeddingConfig:
    def test_defaults(self):
        config = EmbeddingConfig()
        assert config.provider == "openai"
        assert config.model == "text-embedding-3-small"
        assert config.dimensions == 1536

    def test_custom_values(self):
        config = EmbeddingConfig(provider="ollama", model="nomic-embed-text", dimensions=768)
        assert config.provider == "ollama"
        assert config.dimensions == 768

    def test_invalid_dimensions(self):
        with pytest.raises(ValueError):
            EmbeddingConfig(dimensions=0)


class TestLLMConfig:
    def test_defaults(self):
        config = LLMConfig()
        assert config.provider == "openai"
        assert config.model == "gpt-4o-mini"
        assert config.temperature == 0.1

    def test_temperature_validation(self):
        with pytest.raises(ValueError):
            LLMConfig(temperature=2.5)
        with pytest.raises(ValueError):
            LLMConfig(temperature=-0.1)

    def test_valid_temperature_range(self):
        config = LLMConfig(temperature=0.0)
        assert config.temperature == 0.0
        config = LLMConfig(temperature=2.0)
        assert config.temperature == 2.0


class TestChunkingConfig:
    def test_defaults(self):
        config = ChunkingConfig()
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
        assert config.chunk_unit == "tokens"

    def test_overlap_validation(self):
        with pytest.raises(ValueError):
            ChunkingConfig(chunk_size=100, chunk_overlap=100)
        with pytest.raises(ValueError):
            ChunkingConfig(chunk_size=100, chunk_overlap=150)

    def test_valid_overlap(self):
        config = ChunkingConfig(chunk_size=512, chunk_overlap=50)
        assert config.chunk_overlap == 50


class TestVectorStoreConfig:
    def test_defaults(self):
        config = VectorStoreConfig()
        assert config.type == "sqlite_vec"
        assert config.path == "./data/anchor_rag.db"
        assert config.embedding_dimensions == 1536


class TestAppConfig:
    def test_from_yaml(self, tmp_path):
        yaml_content = """
embedding:
  provider: "ollama"
  model: "nomic-embed-text"
  dimensions: 768
llm:
  provider: "ollama"
  model: "llama3.1:8b"
chunking:
  chunk_size: 256
vector_store:
  embedding_dimensions: 768
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(yaml_content)

        config = AppConfig.from_yaml(config_file)
        assert config.embedding.provider == "ollama"
        assert config.embedding.dimensions == 768
        assert config.llm.model == "llama3.1:8b"
        assert config.chunking.chunk_size == 256

    def test_resolve_api_keys(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")

        config = AppConfig(
            embedding=EmbeddingConfig(api_key_env="OPENAI_API_KEY"),
            llm=LLMConfig(api_key_env="ANTHROPIC_API_KEY"),
        )
        resolved = config.resolve_api_keys()
        assert resolved.embedding.api_key == "test-key-123"
        assert resolved.llm.api_key == "anthropic-key"

    def test_cross_config_valid_dimensions_match(self):
        config = AppConfig(
            embedding=EmbeddingConfig(dimensions=768),
            vector_store=VectorStoreConfig(embedding_dimensions=768),
        )
        assert config.embedding.dimensions == 768
        assert config.vector_store.embedding_dimensions == 768

    def test_cross_config_invalid_dimensions_mismatch(self):
        with pytest.raises(ValueError, match="embedding.dimensions \\(1536\\) != vector_store.embedding_dimensions \\(768\\)"):
            AppConfig(
                embedding=EmbeddingConfig(dimensions=1536),
                vector_store=VectorStoreConfig(embedding_dimensions=768),
            )

    def test_cross_config_from_yaml_valid(self, tmp_path):
        yaml_content = """
embedding:
  dimensions: 768
vector_store:
  embedding_dimensions: 768
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(yaml_content)
        config = AppConfig.from_yaml(config_file)
        assert config.embedding.dimensions == 768

    def test_cross_config_from_yaml_invalid(self, tmp_path):
        yaml_content = """
embedding:
  dimensions: 1536
vector_store:
  embedding_dimensions: 768
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(yaml_content)
        with pytest.raises(ValueError, match="embedding.dimensions \\(1536\\) != vector_store.embedding_dimensions \\(768\\)"):
            AppConfig.from_yaml(config_file)