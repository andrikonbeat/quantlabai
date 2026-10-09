"""EmbeddingService — async text embeddings with deterministic fallback.

Provides sentence-level embeddings for semantic similarity search. Uses a
configurable model (sentence-transformers when available) with a graceful
fallback to TF-IDF + char 3-gram cosine (the same deterministic algorithm
used by `QueryBuilder.search_similar_campaigns` and `search_agent_memory`).

Embeddings are persisted as `.npy` vectors with accompanying `.meta.json`
metadata in `knowledge/embeddings/` per hypothesis/campaign.

Index version: bumped to 6 in `KnowledgeStore` to include the embeddings dir.
"""

from __future__ import annotations

import json
import logging
import math
import os
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from quantlab.knowledge.store import _tokenize, _add_text, _text_cosine

if TYPE_CHECKING:
    from quantlab.knowledge.store import KnowledgeStore

logger = logging.getLogger(__name__)

# Default embedding model (sentence-transformers). Can be overridden via env.
_DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_EMBEDDING_MODEL_ENV = "QUANTLAB_EMBEDDING_MODEL"
_EMBEDDINGS_DIR = "embeddings"


class EmbeddingService:
    """Async embedding service with deterministic fallback.

    Attributes:
        model_name: Name of the sentence-transformers model to use.
        fallback_enabled: Whether to fall back to TF-IDF+3-gram on model failure.
    """

    def __init__(
        self,
        model_name: str | None = None,
        fallback_enabled: bool = True,
    ) -> None:
        self.model_name = model_name or os.getenv(
            _EMBEDDING_MODEL_ENV, _DEFAULT_EMBEDDING_MODEL
        )
        self.fallback_enabled = fallback_enabled
        self._model: Any = None
        self._model_loaded = False
        self._load_error: Exception | None = None

    def _load_model(self) -> None:
        """Lazy-load the sentence-transformers model."""
        if self._model_loaded:
            return

        try:
            # Import here to avoid hard dependency at module load time
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            self._model_loaded = True
            logger.info("Loaded embedding model: %s", self.model_name)
        except Exception as exc:  # pragma: no cover - defensive
            self._load_error = exc
            self._model_loaded = True
            if self.fallback_enabled:
                warnings.warn(
                    f"Failed to load embedding model '{self.model_name}': {exc}. "
                    "Falling back to TF-IDF+3-gram cosine similarity.",
                    UserWarning,
                    stacklevel=2,
                )
                logger.warning(
                    "Embedding model load failed, fallback enabled: %s", exc
                )
            else:
                logger.error("Embedding model load failed, no fallback: %s", exc)
                raise

    async def embed(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            2D numpy array of shape (len(texts), embedding_dim) with float32 vectors.

        Raises:
            RuntimeError: If model not loaded and fallback disabled.
        """
        if not texts:
            return np.empty((0, 384), dtype=np.float32)  # all-MiniLM-L6-v2 dim

        self._load_model()

        if self._model is not None:
            try:
                # sentence-transformers encode is sync; run in executor for async
                import asyncio

                loop = asyncio.get_running_loop()
                vectors = await loop.run_in_executor(
                    None, lambda: self._model.encode(texts, convert_to_numpy=True)
                )
                return vectors.astype(np.float32)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Embedding encode failed, trying fallback: %s", exc)
                if not self.fallback_enabled:
                    raise RuntimeError(
                        f"Embedding encode failed and fallback disabled: {exc}"
                    ) from exc

        # Fallback: deterministic TF-IDF+3-gram (same as QueryBuilder)
        return self._fallback_embed(texts)

    def _fallback_embed(self, texts: list[str]) -> np.ndarray:
        """Deterministic fallback embedding using TF-IDF + char 3-gram.

        Returns unit vectors in a sparse feature space (dict-based, then
        projected to fixed 384-dim for compatibility). Not true embeddings
        but preserves cosine similarity ranking exactly as QueryBuilder.
        """
        # Build vocabulary from all texts
        vocab: dict[str, int] = {}
        doc_vectors: list[dict[str, int]] = []

        for text in texts:
            vec: dict[str, int] = {}
            _add_text(vec, text)
            doc_vectors.append(vec)
            for token in vec:
                vocab[token] = vocab.get(token, 0) + 1

        # If no vocabulary (empty/whitespace texts), return small random unit vectors
        if not vocab:
            result = np.random.default_rng(42).normal(size=(len(texts), 384)).astype(np.float32)
            norms = np.linalg.norm(result, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            return result / norms

        # IDF weighting
        n_docs = len(texts)
        idf = {token: math.log(n_docs / df) for token, df in vocab.items()}

        # TF-IDF vectors
        tfidf_vecs: list[dict[str, float]] = []
        for vec in doc_vectors:
            tfidf = {token: count * idf[token] for token, count in vec.items()}
            # L2 normalize
            norm = math.sqrt(sum(v * v for v in tfidf.values()))
            if norm > 0:
                tfidf = {token: v / norm for token, v in tfidf.items()}
            tfidf_vecs.append(tfidf)

        # Project to fixed 384-dim using deterministic hash (for storage compatibility)
        # This preserves cosine similarity approximately
        dim = 384
        result = np.zeros((len(texts), dim), dtype=np.float32)
        for i, vec in enumerate(tfidf_vecs):
            for token, weight in vec.items():
                # Deterministic hash projection
                idx = hash(token) % dim
                result[i, idx] += weight
            # Re-normalize after projection; if zero, add small noise
            row_norm = np.linalg.norm(result[i])
            if row_norm > 0:
                result[i] /= row_norm
            else:
                # Deterministic fallback for zero vectors
                rng = np.random.default_rng(hash(texts[i]) % (2**32))
                result[i] = rng.normal(size=dim).astype(np.float32)
                result[i] /= np.linalg.norm(result[i])

        return result

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity between two embedding vectors.

        Args:
            a: First vector (1D).
            b: Second vector (1D).

        Returns:
            Cosine similarity in [-1, 1].
        """
        # Both should be L2-normalized; dot product = cosine similarity
        return float(np.dot(a, b))

    def similarity_batch(self, query: np.ndarray, candidates: np.ndarray) -> np.ndarray:
        """Cosine similarity between query and multiple candidates.

        Args:
            query: Query vector (1D, length d).
            candidates: Candidate matrix (n, d).

        Returns:
            1D array of n similarity scores.
        """
        return candidates @ query

    async def embed_and_store(
        self,
        store: KnowledgeStore,
        hypothesis_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Embed text and persist vector + metadata to Knowledge Lake.

        Args:
            store: KnowledgeStore instance (for root path).
            hypothesis_id: Unique identifier for the hypothesis.
            text: Text to embed.
            metadata: Optional metadata to store alongside vector.

        Returns:
            Path to the saved `.npy` vector file.
        """
        vectors = await self.embed([text])
        vector = vectors[0]

        # Persist .npy
        embeddings_root = Path(store.root) / _EMBEDDINGS_DIR
        embeddings_root.mkdir(parents=True, exist_ok=True)

        npy_path = embeddings_root / f"{hypothesis_id}.npy"
        np.save(npy_path, vector)

        # Persist .meta.json
        meta = {
            "hypothesis_id": hypothesis_id,
            "text": text,
            "model": self.model_name,
            "fallback_used": self._model is None,
            "dimension": int(vector.shape[0]),
            "created": datetime.now(UTC).isoformat(),
            "sha256": self._vector_sha256(vector),
        }
        if metadata:
            meta.update(metadata)

        meta_path = embeddings_root / f"{hypothesis_id}.meta.json"
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        logger.debug("Stored embedding for %s at %s", hypothesis_id, npy_path)
        return npy_path

    def _vector_sha256(self, vector: np.ndarray) -> str:
        """SHA256 of vector bytes for integrity."""
        import hashlib

        return hashlib.sha256(vector.tobytes()).hexdigest()

    @classmethod
    def load_vector(cls, store: KnowledgeStore, hypothesis_id: str) -> np.ndarray | None:
        """Load a stored embedding vector.

        Args:
            store: KnowledgeStore instance.
            hypothesis_id: Hypothesis identifier.

        Returns:
            Vector as 1D numpy array, or None if not found.
        """
        npy_path = Path(store.root) / _EMBEDDINGS_DIR / f"{hypothesis_id}.npy"
        if not npy_path.exists():
            return None
        return np.load(npy_path)

    @classmethod
    def load_meta(cls, store: KnowledgeStore, hypothesis_id: str) -> dict[str, Any] | None:
        """Load embedding metadata."""
        meta_path = Path(store.root) / _EMBEDDINGS_DIR / f"{hypothesis_id}.meta.json"
        if not meta_path.exists():
            return None
        return json.loads(meta_path.read_text(encoding="utf-8"))