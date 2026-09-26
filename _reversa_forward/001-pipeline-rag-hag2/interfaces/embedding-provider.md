# Interface: EmbeddingProvider (Abstração Python)

> Feature: `001-pipeline-rag-hag2`
> Tipo: Interface interna (Python ABC)
> Data: `2026-09-22`

## 1. Propósito

Abstração para geração de embeddings vetoriais. Permite trocar provedor (OpenAI, Ollama, HuggingFace local) sem alterar o pipeline de ingestão/busca.

## 2. Contrato (ABC)

```python
# src/hag_rag/embeddings/base.py

from abc import ABC, abstractmethod
from typing import List, Sequence
from pydantic import BaseModel

class EmbeddingConfig(BaseModel):
    model: str
    dimensions: int | None = None  # Auto-detectado se None
    batch_size: int = 100
    timeout: float = 30.0
    max_retries: int = 3
    retry_backoff: float = 1.0  # Base para backoff exponencial

class EmbeddingProvider(ABC):
    """Interface para provedores de embeddings."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._dimensions: int | None = None

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identificador único do provedor (ex.: 'openai', 'ollama', 'huggingface')."""
        ...

    @property
    def dimensions(self) -> int:
        """Dimensão do vetor de embedding. Cacheado após primeira chamada."""
        if self._dimensions is None:
            self._dimensions = self._detect_dimensions()
        return self._dimensions

    @abstractmethod
    def _detect_dimensions(self) -> int:
        """Descobre dimensão do modelo (uma chamada de teste ou metadata)."""
        ...

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Gera embedding para um único texto."""
        ...

    @abstractmethod
    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        """Gera embeddings para múltiplos textos (otimizado para batch)."""
        ...

    def validate_dimensions(self, expected: int) -> None:
        """Valida se dimensão do modelo corresponde ao esperado."""
        actual = self.dimensions
        if actual != expected:
            raise ValueError(
                f"Dimensão do modelo {self.provider_name}/{self.config.model} "
                f"({actual}) não corresponde ao esperado ({expected})"
            )

    def health_check(self) -> bool:
        """Verifica se provedor está acessível."""
        try:
            self.embed("health check")
            return True
        except Exception:
            return False
```

## 3. Implementações previstas

### 3.1 OpenAI (`OpenAIEmbeddingProvider`)

```python
# src/hag_rag/embeddings/openai.py

from openai import OpenAI
from .base import EmbeddingProvider, EmbeddingConfig

class OpenAIEmbeddingProvider(EmbeddingProvider):
    provider_name = "openai"

    def __init__(self, config: EmbeddingConfig, api_key: str | None = None):
        super().__init__(config)
        self.client = OpenAI(api_key=api_key)

    def _detect_dimensions(self) -> int:
        # text-embedding-3-small = 1536, text-embedding-3-large = 3072
        # text-embedding-ada-002 = 1536
        known = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return known.get(self.config.model, 1536)

    def embed(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        # OpenAI API aceita batch nativo
        response = self.client.embeddings.create(
            model=self.config.model,
            input=list(texts),
            dimensions=self.config.dimensions,  # None = default do modelo
        )
        return [d.embedding for d in response.data]
```

### 3.2 Ollama (`OllamaEmbeddingProvider`)

```python
# src/hag_rag/embeddings/ollama.py

import httpx
from .base import EmbeddingProvider, EmbeddingConfig

class OllamaEmbeddingProvider(EmbeddingProvider):
    provider_name = "ollama"

    def __init__(self, config: EmbeddingConfig, base_url: str = "http://localhost:11434"):
        super().__init__(config)
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=config.timeout)

    def _detect_dimensions(self) -> int:
        # Modelos conhecidos
        known = {
            "nomic-embed-text": 768,
            "nomic-embed-text-v1.5": 768,
            "mxbai-embed-large": 1024,
            "bge-m3": 1024,
            "all-minilm": 384,
        }
        # Tenta via API se não conhecido
        for name, dim in known.items():
            if name in self.config.model.lower():
                return dim
        # Fallback: uma chamada real
        return len(self.embed("dimension detection"))

    def embed(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        # Ollama /api/embed aceita array
        response = self.client.post(
            f"{self.base_url}/api/embed",
            json={"model": self.config.model, "input": list(texts)},
        )
        response.raise_for_status()
        return response.json()["embeddings"]
```

### 3.3 HuggingFace Local (`HuggingFaceEmbeddingProvider`)

```python
# src/hag_rag/embeddings/huggingface.py

from sentence_transformers import SentenceTransformer
from .base import EmbeddingProvider, EmbeddingConfig

class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    provider_name = "huggingface"

    def __init__(self, config: EmbeddingConfig, device: str | None = None):
        super().__init__(config)
        self.model = SentenceTransformer(config.model, device=device)

    def _detect_dimensions(self) -> int:
        return self.model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        embeddings = self.model.encode(
            list(texts),
            batch_size=self.config.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return embeddings.tolist()
```

## 4. Factory / Registry

```python
# src/hag_rag/embeddings/__init__.py

from .base import EmbeddingProvider, EmbeddingConfig
from .openai import OpenAIEmbeddingProvider
from .ollama import OllamaEmbeddingProvider
from .huggingface import HuggingFaceEmbeddingProvider

_PROVIDERS = {
    "openai": OpenAIEmbeddingProvider,
    "ollama": OllamaEmbeddingProvider,
    "huggingface": HuggingFaceEmbeddingProvider,
}

def create_embedding_provider(
    provider: str,
    config: EmbeddingConfig,
    **kwargs
) -> EmbeddingProvider:
    if provider not in _PROVIDERS:
        raise ValueError(f"Provedor de embedding desconhecido: {provider}. "
                         f"Disponíveis: {list(_PROVIDERS.keys())}")
    return _PROVIDERS[provider](config, **kwargs)

def list_providers() -> List[str]:
    return list(_PROVIDERS.keys())
```

## 5. Uso no pipeline

```python
# Ingestão
provider = create_embedding_provider("ollama", EmbeddingConfig(model="nomic-embed-text"))
chunks = chunker.chunk(document_text)
embeddings = provider.embed_batch([c.text for c in chunks])
for chunk, emb in zip(chunks, embeddings):
    chunk.embedding = emb
vector_store.add_chunks(chunks)

# Busca
query_emb = provider.embed(user_question)
results = vector_store.search(query_emb, top_k=3)
```

## 6. Requisitos não-funcionais

| Requisito | Detalhe |
|-----------|---------|
| **Retry** | 3 tentativas com backoff exponencial (1s, 2s, 4s) para falhas transitórias |
| **Timeout** | 30s default por chamada (configurável) |
| **Batch** | `embed_batch` obrigatório para eficiência na ingestão |
| **Dimensões** | Auto-detectadas; validação no `validate_dimensions()` |
| **Thread-safety** | Implementações devem ser thread-safe (stateless ou connection pool) |
| **Logging** | Log nível INFO: "Embedding batch: N texts, M ms" |