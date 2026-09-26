"""Configuração da aplicação usando Pydantic Settings."""

from pathlib import Path
from typing import Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmbeddingConfig(BaseSettings):
    """Configuração do provedor de embedding."""

    provider: Literal["openai", "ollama", "huggingface"] = "openai"
    model: str = "text-embedding-3-small"
    dimensions: int = 1536
    batch_size: int = 100
    timeout: int = 30
    max_retries: int = 3
    api_key_env: str = "OPENAI_API_KEY"
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    model_config = SettingsConfigDict(env_prefix="EMBEDDING_", extra="ignore")

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("dimensions deve ser maior que zero")
        return v


class LLMConfig(BaseSettings):
    """Configuração do provedor de LLM."""

    provider: Literal["openai", "ollama", "anthropic"] = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 2048
    timeout: int = 30
    api_key_env: str = "OPENAI_API_KEY"
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    model_config = SettingsConfigDict(env_prefix="LLM_", extra="ignore")

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0 <= v <= 2:
            raise ValueError("temperature deve estar entre 0 e 2")
        return v


class ChunkingConfig(BaseSettings):
    """Configuração de chunking."""

    chunk_size: int = 512
    chunk_overlap: int = 50
    chunk_unit: Literal["chars", "tokens"] = "tokens"
    min_chunk_size: int = 50
    parser: Literal["pdfplumber", "pypdf"] = "pdfplumber"

    model_config = SettingsConfigDict(env_prefix="CHUNKING_", extra="ignore")

    @field_validator("chunk_overlap")
    @classmethod
    def validate_overlap(cls, v: int, info) -> int:
        chunk_size = info.data.get("chunk_size", 512)
        if v >= chunk_size:
            raise ValueError("chunk_overlap deve ser menor que chunk_size")
        return v


class VectorStoreConfig(BaseSettings):
    """Configuração do vector store."""

    type: Literal["sqlite_vec"] = "sqlite_vec"
    path: str = "./data/anchor_rag.db"
    embedding_dimensions: int = 1536

    model_config = SettingsConfigDict(env_prefix="VECTOR_STORE_", extra="ignore")


class LoggingConfig(BaseSettings):
    """Configuração de logging."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    format: Literal["json", "text"] = "json"
    output: str = "stdout"
    include_request_id: bool = True

    model_config = SettingsConfigDict(env_prefix="LOGGING_", extra="ignore")


class QueryLogConfig(BaseSettings):
    """Configuração de log de queries."""

    enabled: bool = False
    path: str = "./data/query_log.db"

    model_config = SettingsConfigDict(env_prefix="QUERY_LOG_", extra="ignore")


class AppConfig(BaseSettings):
    """Configuração principal da aplicação."""

    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    query_log: QueryLogConfig = Field(default_factory=QueryLogConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AppConfig":
        """Carrega configuração a partir de arquivo YAML."""
        import yaml

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)

    def resolve_api_keys(self) -> "AppConfig":
        """Resolve variáveis de ambiente para chaves de API."""
        import os

        def resolve(env_var: str) -> Optional[str]:
            return os.getenv(env_var)

        config_dict = self.model_dump()
        for section in ["embedding", "llm"]:
            env_key = config_dict[section].get("api_key_env")
            if env_key:
                config_dict[section]["api_key"] = resolve(env_key)
        return self.model_validate(config_dict)