"""Provedor de embedding HuggingFace via sentence-transformers."""

from __future__ import annotations
from typing import List, Optional
import logging

from anchor_rag.embeddings.base import EmbeddingProvider, EmbeddingConfig

logger = logging.getLogger(__name__)


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """Provedor de embeddings via sentence-transformers (local)."""

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self._model = None
        self._dimensions = config.dimensions

    def _load_model(self):
        """Carrega o modelo sob demanda."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise RuntimeError(
                    "sentence-transformers não instalado. Instale com: pip install sentence-transformers"
                )
            logger.info(f"Carregando modelo HuggingFace: {self.config.model}")
            self._model = SentenceTransformer(self.config.model)
            # Atualiza dimensões reais do modelo
            self._dimensions = self._model.get_sentence_embedding_dimension()

    @property
    def dimensions(self) -> int:
        if self._model is None:
            return self._dimensions
        return self._model.get_sentence_embedding_dimension()

    async def embed(self, text: str) -> List[float]:
        """Gera embedding para um texto único."""
        self._load_model()
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Gera embeddings em lote com encoding otimizado."""
        if not texts:
            return []

        self._load_model()
        embeddings = self._model.encode(
            texts,
            batch_size=self.config.batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        result = embeddings.tolist()
        self._validate_dimensions(result)
        return result

    async def health_check(self) -> bool:
        """Verifica se o modelo carrega corretamente."""
        try:
            self._load_model()
            await self.embed("health check")
            return True
        except Exception as e:
            logger.warning(f"HuggingFace health check falhou: {e}")
            return False