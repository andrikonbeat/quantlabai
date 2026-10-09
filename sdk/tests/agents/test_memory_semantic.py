"""Tests for semantic + calibration retrieval in AgentMemoryManager (T9 4.3)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from quantlab.agents.memory import AgentMemoryManager


def _seed(root: Path) -> None:
    import yaml

    base = root / "agent-memory" / "research" / "camp-1"
    base.mkdir(parents=True, exist_ok=True)
    (base / "memory.yaml").write_text(
        yaml.safe_dump(
            [
                {"decision": "prefer trend setups on EURUSD", "tags": ["trend"]},
                {"decision": "avoid illiquid exotic pairs", "tags": ["risk"]},
            ]
        ),
        encoding="utf-8",
    )


class _FakeEmbeddings:
    """Deterministic similarities: trend-decision scores 0.9, other 0.1."""

    async def embed(self, texts: list[str]) -> np.ndarray:
        vecs = []
        for text in texts:
            if "trend" in text:
                vecs.append([1.0, 0.0])
            else:
                vecs.append([0.0, 1.0])
        return np.array(vecs, dtype=np.float32)

    def similarity_batch(self, query: np.ndarray, candidates: np.ndarray) -> np.ndarray:
        return candidates @ query


class TestSemanticRetrieval:
    def test_defaults_preserve_behavior(self, tmp_path: Path) -> None:
        import asyncio

        _seed(tmp_path)
        mgr = AgentMemoryManager(knowledge_root=tmp_path)
        result = asyncio.run(mgr.query_cross_agent("EURUSD"))
        decisions = result["research"]
        assert len(decisions) == 1
        assert "similarity" not in decisions[0]
        assert "calibration" not in decisions[0]

    def test_semantic_query_ranks_and_scores(self, tmp_path: Path) -> None:
        import asyncio

        _seed(tmp_path)
        mgr = AgentMemoryManager(knowledge_root=tmp_path)
        with patch(
            "quantlab.knowledge.embedding_service.EmbeddingService",
            return_value=_FakeEmbeddings(),
        ):
            result = asyncio.run(
                mgr.query_cross_agent("", semantic_query="trend setups")
            )
        decisions = result["research"]
        assert len(decisions) == 2
        # Ranked by similarity desc
        assert decisions[0]["tags"] == ["trend"]
        assert decisions[0]["similarity"] == pytest.approx(1.0)
        assert decisions[1]["similarity"] == pytest.approx(0.0)

    def test_semantic_failure_falls_back_to_text_order(self, tmp_path: Path) -> None:
        import asyncio

        _seed(tmp_path)
        mgr = AgentMemoryManager(knowledge_root=tmp_path)

        class _Broken:
            async def embed(self, texts: list[str]):
                raise RuntimeError("embeddings down")

        with patch(
            "quantlab.knowledge.embedding_service.EmbeddingService",
            return_value=_Broken(),
        ):
            result = asyncio.run(
                mgr.query_cross_agent("", semantic_query="trend")
            )
        assert len(result["research"]) == 2  # no crash, text order kept

    def test_tag_stats_attached(self, tmp_path: Path) -> None:
        import asyncio

        _seed(tmp_path)
        mgr = AgentMemoryManager(knowledge_root=tmp_path)
        result = asyncio.run(
            mgr.query_cross_agent(
                "",
                tag_stats={"trend": {"avg_sharpe": 1.8, "sample_count": 4}},
            )
        )
        by_tag = {tuple(d.get("tags", [])): d for d in result["research"]}
        assert by_tag[("trend",)]["calibration"] == {
            "trend": {"avg_sharpe": 1.8, "sample_count": 4}
        }
        assert "calibration" not in by_tag[("risk",)]
