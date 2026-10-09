"""Tests for feedback ingestion into the index pipeline (T9 task 4.4)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml

from quantlab.agents.feedback_writer import KnowledgeLakeFeedbackWriter
from quantlab.knowledge.models import HypothesisFeedbackRecord


def _record() -> HypothesisFeedbackRecord:
    return HypothesisFeedbackRecord(
        campaign_id="camp-1", hypothesis_id="h1", feedback_type="pass",
        notes="archived", source="gate",
    )


class TestFeedbackIngestion:
    def test_write_refreshes_index(self, tmp_path: Path) -> None:
        import asyncio

        writer = KnowledgeLakeFeedbackWriter(lake_root=tmp_path)
        asyncio.run(writer.write_feedback(_record()))

        index_path = tmp_path / "index.yaml"
        assert index_path.exists()
        index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
        assert "structured/camp-1/metadata.yaml" in index["directories"]["structured"]

    def test_reindex_false_skips(self, tmp_path: Path) -> None:
        import asyncio

        writer = KnowledgeLakeFeedbackWriter(lake_root=tmp_path)
        asyncio.run(writer.write_feedback(_record(), reindex=False))

        assert (tmp_path / "structured" / "camp-1" / "metadata.yaml").exists()
        assert not (tmp_path / "index.yaml").exists()

    def test_reindex_failure_never_breaks_write(self, tmp_path: Path) -> None:
        import asyncio

        writer = KnowledgeLakeFeedbackWriter(lake_root=tmp_path)
        with patch(
            "quantlab.knowledge.store.KnowledgeStore.rebuild_index",
            side_effect=RuntimeError("index down"),
        ):
            asyncio.run(writer.write_feedback(_record()))  # must not raise

        data = yaml.safe_load(
            (tmp_path / "structured" / "camp-1" / "metadata.yaml").read_text(
                encoding="utf-8"
            )
        )
        assert len(data["feedback"]) == 1
