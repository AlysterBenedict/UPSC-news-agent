"""
UPSC Daily Digest — Embedding Client Service
==============================================
Local sentence-transformers for embedding and similarity.
"""

from __future__ import annotations

import numpy as np
from typing import Optional

from app.utils.logging_app import get_logger

log = get_logger(__name__)


class EmbeddingClient:
    """Local embedding client using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy-load the model on first use."""
        if self._model is None:
            log.info("loading_embedding_model", model=self.model_name)
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            log.info("embedding_model_loaded", model=self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts, returning (N, D) array."""
        if not texts:
            return np.array([])
        embeddings = self.model.encode(
            texts,
            show_progress_bar=False,
            batch_size=64,
            normalize_embeddings=True,
        )
        return np.array(embeddings)

    def cosine_similarity_matrix(self, embeddings: np.ndarray) -> np.ndarray:
        """Compute pairwise cosine similarity matrix.

        Since embeddings are already L2-normalized, dot product = cosine similarity.
        """
        return embeddings @ embeddings.T

    def find_similar(
        self, query_embedding: np.ndarray, corpus_embeddings: np.ndarray, top_k: int = 5
    ) -> list[tuple[int, float]]:
        """Find top-k most similar items from corpus."""
        similarities = corpus_embeddings @ query_embedding.T
        similarities = similarities.flatten()
        top_indices = np.argsort(similarities)[::-1][:top_k]
        return [(int(idx), float(similarities[idx])) for idx in top_indices]
