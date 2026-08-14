"""WU6 semantic retrieval tests (REQ-501).

Covers the retrieval side of the knowledge lake:

- REQ-501: ``KnowledgeStore.find_similar_campaigns`` ranks campaigns by a
  pragmatic deterministic text embedding (TF-style token + char n-gram cosine
  similarity over campaign text) when no dense ``.npy`` vectors exist.

(The REQ-106/107 training-export tests were removed with the dead
``quantlab.knowledge.training`` module — see repo-organization PR 1.)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from quantlab.knowledge.store import KnowledgeStore


# ── Fixtures / helpers ────────────────────────────────────────────────────────


def write_memory(root: Path, agent: str, campaign: str, decisions: list[dict]) -> Path:
    """Write agent-memory YAML in the exact AgentMemoryManager format."""
    camp_dir = root / "agent-memory" / agent / campaign
    camp_dir.mkdir(parents=True, exist_ok=True)
    memory_file = camp_dir / "memory.yaml"
    memory_file.write_text(
        yaml.dump(decisions, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return memory_file


def decision(**overrides: object) -> dict:
    """A decision record with phase config (REQ-102) and envelope fields."""
    base: dict[str, object] = {
        "status": "success",
        "executive_summary": "Config validated with ATR stop loss",
        "artifacts": ["build_config"],
        "next_recommended": "review",
        "risks": ["overfit on EURUSD M15"],
        "phase": "config",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "config": {"stop_loss": "ATR", "market": "EURUSD"},
        "campaign_id": "campaign-1",
    }
    base.update(overrides)
    return base


# ──────────────────────────────────────────────────────────────────────────────
# REQ-501: find_similar_campaigns (deterministic text embedding)
# ──────────────────────────────────────────────────────────────────────────────


class TestFindSimilarCampaigns:
    """REQ-501: similar campaigns ranked by deterministic text similarity."""

    def _seed_text_lake(self, root: Path) -> None:
        """Three campaigns: A and B share breakout vocabulary, C is distinct."""
        write_memory(
            root, "research-director", "campaign-A",
            [decision(executive_summary="EURUSD H1 breakout with ATR trailing stop",
                      config={"market": "EURUSD", "timeframe": "H1"},
                      timestamp="2026-01-01T00:00:00+00:00")],
        )
        write_memory(
            root, "research-director", "campaign-B",
            [decision(executive_summary="EURUSD H1 breakout ATR trailing stop momentum",
                      config={"market": "EURUSD", "timeframe": "H1"},
                      timestamp="2026-01-02T00:00:00+00:00")],
        )
        write_memory(
            root, "research-director", "campaign-C",
            [decision(executive_summary="GBPUSD M15 mean reversion with RSI bollinger",
                      config={"market": "GBPUSD", "timeframe": "M15"},
                      timestamp="2026-01-03T00:00:00+00:00")],
        )

    def test_ranks_most_similar_campaign_first(self, tmp_path: Path) -> None:
        self._seed_text_lake(tmp_path)
        store = KnowledgeStore(tmp_path)
        matches = store.find_similar_campaigns("campaign-A", top_k=5)
        assert matches, "expected at least one similar campaign"
        # campaign-B shares the breakout vocabulary -> first.
        assert matches[0]["campaign_id"] == "campaign-B"
        assert matches[0]["similarity_score"] > 0.0

    def test_dissimilar_campaign_ranked_lower_or_excluded(self, tmp_path: Path) -> None:
        self._seed_text_lake(tmp_path)
        store = KnowledgeStore(tmp_path)
        matches = store.find_similar_campaigns("campaign-A", top_k=5)
        b_score = next(
            m["similarity_score"] for m in matches if m["campaign_id"] == "campaign-B"
        )
        c_scores = [m["similarity_score"] for m in matches if m["campaign_id"] == "campaign-C"]
        if c_scores:  # if C made the cut, it must rank below B
            assert b_score > c_scores[0]

    def test_empty_lake_returns_empty(self, tmp_path: Path) -> None:
        store = KnowledgeStore(tmp_path)
        assert store.find_similar_campaigns("campaign-A") == []

    def test_top_k_respected(self, tmp_path: Path) -> None:
        self._seed_text_lake(tmp_path)
        store = KnowledgeStore(tmp_path)
        matches = store.find_similar_campaigns("campaign-A", top_k=1)
        assert len(matches) == 1
        assert matches[0]["campaign_id"] == "campaign-B"

    def test_min_similarity_filters(self, tmp_path: Path) -> None:
        self._seed_text_lake(tmp_path)
        store = KnowledgeStore(tmp_path)
        # A very high threshold must filter every text-based match out.
        assert store.find_similar_campaigns("campaign-A", min_similarity=0.99) == []
