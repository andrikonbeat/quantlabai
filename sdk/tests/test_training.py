"""WU6 training export + semantic retrieval tests (REQ-106, REQ-107, REQ-501).

Covers the training-ready side of the knowledge lake:

- REQ-106: ``export_training_jsonl`` writes curated JSONL to ``datasets/``,
  restricted to verified campaigns, deduplicated by config hash, and
  privacy-scrubbed per REQ-107 (deny-list-clean, campaign IDs SHA-256 hashed).
- REQ-501: ``KnowledgeStore.find_similar_campaigns`` ranks campaigns by a
  pragmatic deterministic text embedding (TF-style token + char n-gram cosine
  similarity over campaign text) when no dense ``.npy`` vectors exist.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from quantlab.knowledge.conformance import assert_conformance
from quantlab.knowledge.privacy import hash_campaign_id
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


def seed_lake(root: Path) -> None:
    """Seed a small lake: one verified campaign, one unverified campaign."""
    # campaign-1: verified (success decision present).
    write_memory(
        root,
        "research-director",
        "campaign-1",
        [
            decision(),
            decision(
                status="failed",
                executive_summary="Dispatch failed: data gaps",
                risks=["missing M1 data"],
                phase="dispatch",
                timestamp="2026-01-02T00:00:00+00:00",
                config={"stop_loss": "ATR", "market": "EURUSD", "extra": True},
            ),
        ],
    )
    # campaign-2: only failed decisions -> NOT verified, excluded by curation.
    write_memory(
        root,
        "research-director",
        "campaign-2",
        [
            decision(
                status="failed",
                executive_summary="Never reached a verified outcome",
                risks=["all failed"],
                timestamp="2026-01-03T00:00:00+00:00",
            )
        ],
    )


def export_records(root: Path) -> list[dict]:
    """Run the export against a seeded lake and parse every JSONL line."""
    from quantlab.knowledge.training import export_training_jsonl

    path, count = export_training_jsonl(root)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == count
    return [json.loads(line) for line in lines]


# ──────────────────────────────────────────────────────────────────────────────
# REQ-106: curated JSONL training export
# ──────────────────────────────────────────────────────────────────────────────


class TestTrainingExport:
    """REQ-106 scenarios: curated JSONL export to datasets/."""

    def test_export_writes_curated_jsonl_to_datasets(self, tmp_path: Path) -> None:
        seed_lake(tmp_path)
        path, count = __import__(
            "quantlab.knowledge.training", fromlist=["export_training_jsonl"]
        ).export_training_jsonl(tmp_path)
        assert path.parent.name == "datasets"
        assert path.exists()
        # campaign-1 has 2 decisions; campaign-2 is not verified.
        assert count == 2
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert len(records) == 2

    def test_export_dedupes_by_config_hash(self, tmp_path: Path) -> None:
        # Two records with the SAME config hash -> one exported line.
        write_memory(
            tmp_path,
            "research-director",
            "campaign-1",
            [
                decision(timestamp="2026-01-01T00:00:00+00:00"),
                decision(timestamp="2026-01-02T00:00:00+00:00"),
            ],
        )
        records = export_records(tmp_path)
        assert len(records) == 1  # same config -> deduped

    def test_export_keeps_distinct_configs(self, tmp_path: Path) -> None:
        write_memory(
            tmp_path,
            "research-director",
            "campaign-1",
            [
                decision(timestamp="2026-01-01T00:00:00+00:00"),
                decision(
                    timestamp="2026-01-02T00:00:00+00:00",
                    config={"stop_loss": "BB", "market": "GBPUSD"},
                ),
            ],
        )
        records = export_records(tmp_path)
        assert len(records) == 2  # different configs -> both kept

    def test_export_hashes_campaign_ids_and_deny_list_clean(self, tmp_path: Path) -> None:
        from quantlab.knowledge.privacy import PrivacyScrubber

        write_memory(
            tmp_path,
            "research-director",
            "campaign-1",
            [
                decision(
                    config={"stop_loss": "ATR", "sqx_license": "FUTLABF255"},
                )
            ],
        )
        records = export_records(tmp_path)
        assert len(records) == 1
        record = records[0]
        # REQ-107: campaign ID appears as its SHA-256 hash, not the raw ID.
        assert record["campaign_id"] == hash_campaign_id("campaign-1")
        assert record["campaign_id"] != "campaign-1"
        # License code scrubbed out of the export.
        assert "FUTLABF255" not in json.dumps(record)
        # Every exported line is deny-list-clean under export rules.
        assert PrivacyScrubber().is_deny_list_clean(record, export=True)

    def test_export_includes_hashed_record_id(self, tmp_path: Path) -> None:
        write_memory(tmp_path, "research-director", "campaign-1", [decision()])
        records = export_records(tmp_path)
        assert "id" in records[0]
        # The ID is a stable SHA-256 hex digest, not the raw campaign/phase.
        assert len(records[0]["id"]) == 64
        assert records[0]["id"] != "campaign-1"

    def test_export_empty_lake_no_error(self, tmp_path: Path) -> None:
        from quantlab.knowledge.training import export_training_jsonl

        path, count = export_training_jsonl(tmp_path)
        assert count == 0
        assert not path.exists()  # nothing to export -> no file written

    def test_export_conforms_to_training_exporter_layout(self, tmp_path: Path) -> None:
        seed_lake(tmp_path)
        from quantlab.knowledge.training import export_training_jsonl

        path, _ = export_training_jsonl(tmp_path)
        assert_conformance("training_exporter", str(path.relative_to(tmp_path)))


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
