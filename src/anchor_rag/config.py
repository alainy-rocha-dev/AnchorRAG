"""Configuração da aplicação usando Pydantic Settings."""

from pathlib import Path
from typing import Literal, Optional
from pydantic import Field, field_validator, model_validator
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
    structured: bool = False  # Chunking estruturado por artigo/inciso (normas jurídicas)

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


class RetrievalConfig(BaseSettings):
    """Configuração de retrieval híbrido."""

    mode: Literal["vector", "hybrid", "fts_only"] = "hybrid"
    reranker_provider: Optional[Literal["huggingface", "ollama", "cohere"]] = None
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_batch_size: int = 32

    model_config = SettingsConfigDict(env_prefix="RETRIEVAL_", extra="ignore")


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


class EvaluationConfig(BaseSettings):
    """Configuração de avaliação agentic (LLM-as-judge)."""

    judge_provider: Literal["openai", "ollama", "anthropic"] = "openai"
    judge_model: str = "gpt-4o-mini"
    judge_temperature: float = 0.0
    judge_max_tokens: int = 1024
    thresholds: dict[str, float] = Field(default_factory=lambda: {
        "faithfulness": 0.7,
        "answer_relevancy": 0.7,
        "context_precision": 0.7,
        "context_recall": 0.7,
    })
    max_refine_iterations: int = 2
    cost_budget_usd: float = 0.50
    pricing_table: dict[str, dict[str, float]] = Field(default_factory=dict)

    model_config = SettingsConfigDict(env_prefix="EVALUATION_", extra="ignore")

    @field_validator("judge_temperature")
    @classmethod
    def validate_judge_temperature(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("judge_temperature deve estar entre 0 e 1")
        return v

    @field_validator("max_refine_iterations")
    @classmethod
    def validate_max_refine(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("max_refine_iterations deve estar entre 1 e 5")
        return v

    @field_validator("cost_budget_usd")
    @classmethod
    def validate_budget(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("cost_budget_usd deve ser maior que zero")
        return v


class AppConfig(BaseSettings):
    """Configuração principal da aplicação."""

    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    query_log: QueryLogConfig = Field(default_factory=QueryLogConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)

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

    @property
    def retrieval_mode(self) -> str:
        return self.retrieval.mode

    @property
    def reranker_provider(self) -> Optional[str]:
        return self.retrieval.reranker_provider

    @property
    def reranker_model(self) -> str:
        return self.retrieval.reranker_model

    @model_validator(mode="after")
    def validate_embedding_dimensions(self) -> "AppConfig":
        """
        Valida consistência entre dimensions do embedding e vector store.

        Executa no modelo validado (mode="after"), garantindo que ambos
        os sub-configs já estão instanciados. Impede erro silencioso em runtime
        quando embedding.dimensions != vector_store.embedding_dimensions,
        que causaria falha na criação da virtual table sqlite-vec.

        Raises:
            ValueError: Se dimensions divergirem, com mensagem acionável.
        """
        emb_dims = self.embedding.dimensions
        vs_dims = self.vector_store.embedding_dimensions
        if emb_dims != vs_dims:
            raise ValueError(
                f"embedding.dimensions ({emb_dims}) != vector_store.embedding_dimensions ({vs_dims}). "
                f"Ajuste config.yaml para que ambos tenham o mesmo valor."
            )
        return self