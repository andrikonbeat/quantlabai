"""Tests for KnowledgeLakeFeedbackWriter."""

from __future__ import annotations

import asyncio
from pathlib import Path

from quantlab.agents.feedback_writer import KnowledgeLakeFeedbackWriter
from quantlab.knowledge.models import HypothesisFeedbackRecord


def test_write_feedback_appends_to_metadata(tmp_path: Path) -> None:
    writer = KnowledgeLakeFeedbackWriter(lake_root=tmp_path)
    record = HypothesisFeedbackRecord(
        campaign_id="camp-001",
        hypothesis_id="h1",
        feedback_type="positive",
        notes="Good performance",
    )
    asyncio.run(writer.write_feedback(record))

    metadata_path = tmp_path / "structured" / "camp-001" / "metadata.yaml"
    assert metadata_path.exists()
    content = metadata_path.read_text()
    assert "feedback:" in content


def test_auto_adjust_defaults_to_false(tmp_path: Path) -> None:
    writer = KnowledgeLakeFeedbackWriter(lake_root=tmp_path)
    assert writer.auto_adjust is False
