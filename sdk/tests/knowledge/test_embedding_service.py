"""Tests for EmbeddingService."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from quantlab.knowledge.embedding_service import EmbeddingService
from quantlab.knowledge.store import KnowledgeStore


# Helper to mock sentence_transformers for tests that need it
def mock_sentence_transformers():
    """Context manager that mocks sentence_transformers import."""
    mock_module = MagicMock()
    mock_model = MagicMock()
    mock_model.encode.return_value = np.random.rand(1, 384).astype(np.float32)
    mock_module.SentenceTransformer.return_value = mock_model
    return patch.dict("sys.modules", {"sentence_transformers": mock_module})


class TestEmbeddingService:
    """Tests for EmbeddingService embedding generation and storage."""

    def test_initialization_default_model(self) -> None:
        """Service initializes with default model from env or constant."""
        with patch.dict(os.environ, {}, clear=True):
            svc = EmbeddingService()
            assert svc.model_name == "sentence-transformers/all-MiniLM-L6-v2"
            assert svc.fallback_enabled is True

    def test_initialization_custom_model(self) -> None:
        """Service accepts custom model name."""
        svc = EmbeddingService(model_name="custom/model", fallback_enabled=False)
        assert svc.model_name == "custom/model"
        assert svc.fallback_enabled is False

    def test_initialization_env_override(self) -> None:
        """QUANTLAB_EMBEDDING_MODEL env var overrides default."""
        with patch.dict(os.environ, {"QUANTLAB_EMBEDDING_MODEL": "env/model"}):
            svc = EmbeddingService()
            assert svc.model_name == "env/model"

    @pytest.mark.asyncio
    async def test_embed_empty_list(self) -> None:
        """Embedding empty list returns empty array with correct dim."""
        svc = EmbeddingService(fallback_enabled=True)
        result = await svc.embed([])
        assert isinstance(result, np.ndarray)
        assert result.shape == (0, 384)
        assert result.dtype == np.float32

    @pytest.mark.asyncio
    async def test_embed_fallback_deterministic(self) -> None:
        """Fallback produces deterministic vectors for same input."""
        svc = EmbeddingService(fallback_enabled=True)
        # Force fallback by not loading model
        svc._model_loaded = True
        svc._model = None

        texts = ["hello world", "foo bar baz"]
        v1 = await svc.embed(texts)
        v2 = await svc.embed(texts)

        assert np.allclose(v1, v2)
        assert v1.shape == (2, 384)
        assert v1.dtype == np.float32
        # Vectors should be L2 normalized
        norms = np.linalg.norm(v1, axis=1)
        assert np.allclose(norms, 1.0)

    @pytest.mark.asyncio
    async def test_embed_fallback_cosine_similarity(self) -> None:
        """Fallback preserves cosine similarity semantics."""
        svc = EmbeddingService(fallback_enabled=True)
        svc._model_loaded = True
        svc._model = None

        texts = ["mean reversion RSI strategy", "RSI oversold entry", "trend following MACD"]
        vectors = await svc.embed(texts)

        # Similar texts should have higher similarity
        sim_01 = svc.similarity(vectors[0], vectors[1])
        sim_02 = svc.similarity(vectors[0], vectors[2])

        assert sim_01 > sim_02  # RSI texts more similar to each other
        assert -1.0 <= sim_01 <= 1.0
        assert -1.0 <= sim_02 <= 1.0

    @pytest.mark.asyncio
    async def test_similarity_batch(self) -> None:
        """Batch similarity computes query vs candidates correctly."""
        svc = EmbeddingService(fallback_enabled=True)
        svc._model_loaded = True
        svc._model = None

        query_text = "RSI mean reversion"
        candidate_texts = [
            "RSI oversold strategy",
            "MACD trend following",
            "Bollinger bands breakout",
        ]

        query_vec = (await svc.embed([query_text]))[0]
        cand_vecs = await svc.embed(candidate_texts)

        sims = svc.similarity_batch(query_vec, cand_vecs)
        assert sims.shape == (3,)
        # Cosine similarity range is [-1, 1] for general vectors
        assert all(-1.0 <= s <= 1.0 for s in sims)

    @pytest.mark.asyncio
    async def test_embed_and_store(self) -> None:
        """Embed and store persists .npy and .meta.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=Path(tmpdir))
            store.initialize()

            svc = EmbeddingService(fallback_enabled=True)
            svc._model_loaded = True
            svc._model = None

            hypothesis_id = "hyp_test_001"
            text = "RSI(14) < 30 mean reversion entry"
            meta = {"tag": "mean_reversion", "confidence": 0.85}

            npy_path = await svc.embed_and_store(store, hypothesis_id, text, meta)

            # Check files exist
            assert npy_path.exists()
            assert npy_path.suffix == ".npy"

            meta_path = npy_path.with_suffix(".meta.json")
            assert meta_path.exists()

            # Load and verify vector
            vector = np.load(npy_path)
            assert vector.shape == (384,)
            assert np.isclose(np.linalg.norm(vector), 1.0)

            # Load and verify metadata
            with meta_path.open(encoding="utf-8") as f:
                loaded_meta = json.load(f)

            assert loaded_meta["hypothesis_id"] == hypothesis_id
            assert loaded_meta["text"] == text
            assert loaded_meta["tag"] == "mean_reversion"
            assert loaded_meta["confidence"] == 0.85
            assert loaded_meta["dimension"] == 384
            assert "sha256" in loaded_meta
            assert "created" in loaded_meta

    @pytest.mark.asyncio
    async def test_load_vector_and_meta(self) -> None:
        """Classmethods load_vector and load_meta work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=Path(tmpdir))
            store.initialize()

            svc = EmbeddingService(fallback_enabled=True)
            svc._model_loaded = True
            svc._model = None

            hypothesis_id = "hyp_load_test"
            await svc.embed_and_store(store, hypothesis_id, "test text")

            # Load via classmethods
            vector = EmbeddingService.load_vector(store, hypothesis_id)
            meta = EmbeddingService.load_meta(store, hypothesis_id)

            assert vector is not None
            assert vector.shape == (384,)
            assert meta is not None
            assert meta["hypothesis_id"] == hypothesis_id

            # Non-existent returns None
            assert EmbeddingService.load_vector(store, "nonexistent") is None
            assert EmbeddingService.load_meta(store, "nonexistent") is None

    @pytest.mark.asyncio
    async def test_fallback_disabled_raises(self) -> None:
        """When fallback disabled and model fails, raises RuntimeError."""
        with mock_sentence_transformers() as mock_st:
            # Make the model's encode raise an exception
            mock_st["sentence_transformers"].SentenceTransformer.return_value.encode.side_effect = RuntimeError("GPU OOM")

            svc = EmbeddingService(fallback_enabled=False)
            svc._model_loaded = True
            # Provide a mock model that will fail on encode
            svc._model = mock_st["sentence_transformers"].SentenceTransformer.return_value

            with pytest.raises(RuntimeError, match="Embedding encode failed"):
                await svc.embed(["test"])

    @pytest.mark.asyncio
    async def test_model_lazy_load_called_once(self) -> None:
        """Model loads lazily on first embed call."""
        with mock_sentence_transformers() as mock_st:
            svc = EmbeddingService(model_name="test/model", fallback_enabled=True)
            await svc.embed(["first"])
            await svc.embed(["second"])

            # Should only instantiate once
            assert mock_st["sentence_transformers"].SentenceTransformer.call_count == 1


class TestEmbeddingServiceIntegration:
    """Integration tests with KnowledgeStore index."""

    @pytest.mark.asyncio
    async def test_embeddings_index_in_store(self) -> None:
        """Embeddings are indexed in KnowledgeStore.read_index()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=Path(tmpdir))
            store.initialize()

            svc = EmbeddingService(fallback_enabled=True)
            svc._model_loaded = True
            svc._model = None

            # Store some embeddings
            for i in range(3):
                await svc.embed_and_store(store, f"hyp_{i}", f"text {i}")

            # Rebuild index
            store.rebuild_index()
            index = store.read_index()

            # Embeddings section should exist
            assert "embeddings" in index
            assert len(index["embeddings"]) == 3

            # Check metadata structure
            for rel, info in index["embeddings"].items():
                assert rel.endswith(".npy")
                assert "size" in info
                assert "sha256" in info
                assert "model" in info
                assert "dimension" in info
                assert info["dimension"] == 384
                assert "fallback_used" in info
                assert "created" in info
                assert "meta" in info