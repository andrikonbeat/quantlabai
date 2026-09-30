"""Slice B: guardian feedback persistence — JSONL store and read API.

Spec requirement "Guardian Metrics Persistence":

- ``GuardianFeedbackStore.write()`` appends a valid ``GuardianMetricRecord``
  to an append-only JSONL file under ``guardian-feedback/``.
- ``GuardianFeedbackStore.query(campaign_id)`` reads the records back.
- ``TimeSeriesStore.query_guardian_metrics()`` exposes the same records through
  the knowledge store read API.

Design decision: JSONL, not SQLite — it matches the ``metrics.jsonl`` spec, is
append-safe, and needs no schema migration.

Strict TDD: written first — RED until Slice B lands.
"""

from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

import pytest

from quantlab.guardian.models import PortfolioState
from quantlab.knowledge.guardian_store import (
    GUARDIAN_FEEDBACK_DIR,
    METRICS_FILENAME,
    GuardianFeedbackStore,
    GuardianMetricRecord,
)
from quantlab.knowledge.store import TimeSeriesStore


def _record(campaign_id: str = "camp_001", **overrides) -> GuardianMetricRecord:
    """Build a valid metric record, overriding individual fields."""
    return GuardianMetricRecord(
        record_id=overrides.pop("record_id", uuid4()),
        campaign_id=campaign_id,
        timestamp=overrides.pop("timestamp", datetime(2026, 8, 20, 12, 0, 0)),
        guardian_name=overrides.pop("guardian_name", "risk"),
        score=overrides.pop("score", 0.42),
        portfolio_state=overrides.pop("portfolio_state", PortfolioState.DEFENSIVE),
        risk_metrics=overrides.pop("risk_metrics", {"drawdown": 0.12}),
        correlation_id=overrides.pop("correlation_id", None),
        source=overrides.pop("source", "evaluation"),
    )


@pytest.fixture
def store(tmp_path) -> GuardianFeedbackStore:
    """A feedback store rooted in a temporary knowledge directory."""
    return GuardianFeedbackStore(tmp_path)


class TestGuardianMetricRecord:
    """The persisted record model matches the design contract."""

    def test_record_fields_round_trip(self) -> None:
        record = _record()

        assert record.campaign_id == "camp_001"
        assert record.guardian_name == "risk"
        assert record.score == 0.42
        assert record.portfolio_state is PortfolioState.DEFENSIVE
        assert record.source == "evaluation"

    def test_score_may_be_absent(self) -> None:
        """A guardian that produced no score records ``None``, not a sentinel 0."""
        assert _record(score=None).score is None

    def test_risk_metrics_may_be_absent(self) -> None:
        assert _record(risk_metrics=None).risk_metrics is None

    def test_score_is_bounded_to_the_guardian_scale(self) -> None:
        with pytest.raises(ValueError):
            _record(score=1.5)

    def test_rejects_unknown_source(self) -> None:
        with pytest.raises(ValueError):
            _record(source="telepathy")

    def test_record_serialises_to_json_object(self) -> None:
        payload = json.loads(_record().model_dump_json())

        assert payload["portfolio_state"] == "DEFENSIVE"
        assert payload["source"] == "evaluation"
        assert payload["risk_metrics"] == {"drawdown": 0.12}

    def test_record_round_trips_through_json(self) -> None:
        record = _record()

        assert GuardianMetricRecord.model_validate_json(record.model_dump_json()) == record


class TestGuardianFeedbackStoreWrite:
    """``write()`` appends, never rewrites."""

    def test_write_creates_the_jsonl_file(self, store: GuardianFeedbackStore) -> None:
        record = _record()

        store.write(record)

        metrics_file = store.root / GUARDIAN_FEEDBACK_DIR / "camp_001" / METRICS_FILENAME
        assert metrics_file.exists()
        assert metrics_file.read_text(encoding="utf-8").count("\n") == 1

    def test_write_uses_the_guardian_feedback_convention(self, tmp_path) -> None:
        """The store reuses the Knowledge Lake ``guardian-feedback/`` directory."""
        store = GuardianFeedbackStore(tmp_path)

        store.write(_record(campaign_id="camp_x"))

        assert (tmp_path / GUARDIAN_FEEDBACK_DIR / "camp_x").is_dir()
        assert GUARDIAN_FEEDBACK_DIR in store.path_for("camp_x").parts

    def test_write_appends_instead_of_truncating(self, store: GuardianFeedbackStore) -> None:
        store.write(_record(guardian_name="risk"))
        store.write(_record(guardian_name="market"))
        store.write(_record(guardian_name="capital"))

        metrics_file = store.path_for("camp_001")
        lines = metrics_file.read_text(encoding="utf-8").strip().splitlines()
        assert [json.loads(line)["guardian_name"] for line in lines] == [
            "risk",
            "market",
            "capital",
        ]

    def test_written_line_is_valid_json(self, store: GuardianFeedbackStore) -> None:
        record = _record()

        store.write(record)

        payload = json.loads(store.path_for("camp_001").read_text(encoding="utf-8"))
        assert payload["record_id"] == str(record.record_id)

    def test_campaigns_are_isolated(self, store: GuardianFeedbackStore) -> None:
        store.write(_record(campaign_id="camp_a"))
        store.write(_record(campaign_id="camp_b"))

        assert len(store.query("camp_a")) == 1
        assert len(store.query("camp_b")) == 1

    def test_write_rejects_campaign_id_with_path_traversal(self, store: GuardianFeedbackStore) -> None:
        """A campaign id must never escape the guardian-feedback root."""
        with pytest.raises(ValueError):
            store.write(_record(campaign_id="../../etc"))

    def test_repeated_writes_are_durable(self, tmp_path) -> None:
        """A second store instance sees the records written by the first."""
        GuardianFeedbackStore(tmp_path).write(_record())

        assert len(GuardianFeedbackStore(tmp_path).query("camp_001")) == 1


class TestGuardianFeedbackStoreQuery:
    """``query()`` reads records back in write order."""

    def test_query_returns_written_records(self, store: GuardianFeedbackStore) -> None:
        record = _record()
        store.write(record)

        results = store.query("camp_001")

        assert results == [record]

    def test_query_preserves_write_order(self, store: GuardianFeedbackStore) -> None:
        for index in range(3):
            store.write(_record(guardian_name=f"g{index}"))

        assert [r.guardian_name for r in store.query("camp_001")] == ["g0", "g1", "g2"]

    def test_query_unknown_campaign_is_empty(self, store: GuardianFeedbackStore) -> None:
        store.write(_record(campaign_id="camp_a"))

        assert store.query("camp_missing") == []

    def test_query_filters_by_guardian(self, store: GuardianFeedbackStore) -> None:
        store.write(_record(guardian_name="risk"))
        store.write(_record(guardian_name="market"))

        assert [r.guardian_name for r in store.query("camp_001", guardian_name="risk")] == [
            "risk"
        ]

    def test_query_filters_by_source(self, store: GuardianFeedbackStore) -> None:
        store.write(_record(source="evaluation"))
        store.write(_record(source="live_stream"))

        assert [r.source for r in store.query("camp_001", source="live_stream")] == [
            "live_stream"
        ]

    def test_query_skips_corrupt_lines(self, store: GuardianFeedbackStore) -> None:
        """One malformed line MUST NOT lose the whole campaign's history."""
        store.write(_record(guardian_name="risk"))
        with store.path_for("camp_001").open("a", encoding="utf-8") as handle:
            handle.write("{not json}\n")
        store.write(_record(guardian_name="market"))

        assert [r.guardian_name for r in store.query("camp_001")] == ["risk", "market"]


class TestTimeSeriesGuardianReadApi:
    """``TimeSeriesStore`` exposes the guardian records as the read API."""

    def test_query_guardian_metrics_reads_the_store(self, tmp_path) -> None:
        GuardianFeedbackStore(tmp_path).write(_record(guardian_name="risk"))

        results = TimeSeriesStore(str(tmp_path / "ts.db")).query_guardian_metrics(
            "camp_001", knowledge_root=tmp_path
        )

        assert len(results) == 1
        assert results[0]["guardian_name"] == "risk"
        assert results[0]["portfolio_state"] == "DEFENSIVE"

    def test_query_guardian_metrics_is_json_safe(self, tmp_path) -> None:
        GuardianFeedbackStore(tmp_path).write(_record())

        results = TimeSeriesStore(str(tmp_path / "ts.db")).query_guardian_metrics(
            "camp_001", knowledge_root=tmp_path
        )

        assert json.loads(json.dumps(results)) == results

    def test_query_guardian_metrics_unknown_campaign(self, tmp_path) -> None:
        results = TimeSeriesStore(str(tmp_path / "ts.db")).query_guardian_metrics(
            "camp_missing", knowledge_root=tmp_path
        )

        assert results == []
