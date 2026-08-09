"""Archiver tests (campaign-archive spec, REQ-33).

Covers the archive agent contract:

- Live Guardian + portfolio data → maintenance plan with next review date
  7 days from archive, refresh triggers, replacement criteria (drawdown >
  10%), cost budget, and account statistics over the demo window.
- DEGRADING strategy → replacement runbook with portfolio candidates,
  expected improvement and risk assessment; human-confirmed gate listed.
- No Guardian data → default review intervals + missing-live-data warning.
- Parameter matrix confidence < 0.3 flags a parameter refresh trigger.
- Artifacts (plan, runbook, stats envelope) are persisted under the
  KnowledgeStore ``maintenance/`` and ``campaign-phases/`` directories.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import yaml

from quantlab.agents.archiver import (
    DEFAULT_NEXT_CYCLE_BUDGET,
    REPLACEMENT_DRAWDOWN_THRESHOLD,
    Archiver,
    ArchiveResult,
    ReplacementCandidate,
    ReplacementRunbook,
    refresh_triggers,
    review_cycle_days,
)
from quantlab.guardian.models import PortfolioState, StrategyState
from quantlab.readers.models import EquityPoint


def _equity_points() -> list[EquityPoint]:
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        EquityPoint(timestamp=ts, equity=1000.0),
        EquityPoint(timestamp=ts.replace(hour=1), equity=1100.0),
        EquityPoint(timestamp=ts.replace(hour=2), equity=1050.0),
    ]


class TestReviewCycleDays:
    def test_live_data_uses_7_day_cycle(self) -> None:
        assert review_cycle_days(has_live_data=True) == 7

    def test_no_live_data_uses_default_cycle(self) -> None:
        assert review_cycle_days(has_live_data=False) == 30


class TestRefreshTriggers:
    def test_low_confidence_parameter_is_flagged(self) -> None:
        matrix = [
            {"tab": "MoneyManagement", "parameter": "sl_atr", "value": 2.0,
             "rationale": "volatility", "confidence": 0.2},
            {"tab": "MoneyManagement", "parameter": "pt_atr", "value": 3.0,
             "rationale": "volatility", "confidence": 0.9},
        ]
        triggers = refresh_triggers(matrix)
        assert [t["parameter"] for t in triggers] == ["sl_atr"]
        assert triggers[0]["reason"] == "confidence below 0.3"

    def test_no_matrix_yields_default_trigger(self) -> None:
        triggers = refresh_triggers(None)
        assert len(triggers) == 1
        assert triggers[0]["parameter"] == "all"


class TestArchiveMaintenancePlan:
    async def test_live_data_builds_7_day_plan_with_stats(self, tmp_path) -> None:
        archiver = Archiver()
        portfolio_data = {
            "knowledge_root": tmp_path,
            "equity_points": _equity_points(),
            "portfolio_candidates": ["s2", "s3"],
            "deployed_strategy_id": "s1",
            "strategy_state": StrategyState.ACTIVE,
            "next_cycle_budget": 250.0,
        }

        result = await archiver.archive(
            "campaign-a", PortfolioState.NORMAL, portfolio_data
        )

        assert isinstance(result, ArchiveResult)
        # Next review date is 7 days from archive (live data present).
        assert result.plan.review_cycle_days == 7
        assert result.plan.campaign_id == "campaign-a"
        assert result.plan.live_strategy_ids == ["s1"]
        # Account statistics computed over the demo window.
        assert result.stats["end_equity"] == 1050.0
        assert result.stats["pnl"] == 50.0
        assert result.stats["max_drawdown"] == pytest.approx((1100 - 1050) / 1100)
        # Plan notes carry the spec-required maintenance content.
        notes = yaml.safe_load(result.plan.notes)
        assert notes["next_review_days"] == 7
        assert any("drawdown > 10%" in c for c in notes["replacement_criteria"])
        assert notes["cost_budget"] == 250.0
        assert notes["refresh_triggers"]
        # Not degrading → maintain, no candidates.
        assert result.runbook.recommendation == "MAINTAIN"
        assert result.runbook.candidates == []
        assert result.warnings == []

    async def test_degrading_strategy_produces_replacement_runbook(self, tmp_path) -> None:
        archiver = Archiver()
        portfolio_data = {
            "knowledge_root": tmp_path,
            "equity_points": _equity_points(),
            "portfolio_candidates": ["s2", "s3", "s1"],
            "deployed_strategy_id": "s1",
            "strategy_state": StrategyState.DEGRADING,
            "candidate_metrics": {
                "s2": {"sharpe": 1.8, "max_drawdown": 0.05},
                "s3": {"sharpe": 1.2, "max_drawdown": 0.09},
            },
        }

        result = await archiver.archive(
            "campaign-a", PortfolioState.DEFENSIVE, portfolio_data
        )

        runbook: ReplacementRunbook = result.runbook
        assert runbook.recommendation == "REPLACE"
        # Deployed strategy excluded; candidates come from the portfolio.
        assert [c.strategy_id for c in runbook.candidates] == ["s2", "s3"]
        assert all(isinstance(c, ReplacementCandidate) for c in runbook.candidates)
        # Each candidate carries expected improvement and risk assessment.
        assert runbook.candidates[0].expected_improvement
        assert runbook.candidates[0].risk
        assert runbook.drawdown_threshold == REPLACEMENT_DRAWDOWN_THRESHOLD
        # Replacement must be human-confirmed before archive.
        assert "HUMAN_APPROVE_ARCHIVE" in runbook.required_confirmations
        assert result.plan.replacement_candidates == ["s2", "s3"]

    async def test_no_guardian_data_defaults_intervals_with_warning(self, tmp_path) -> None:
        archiver = Archiver()
        result = await archiver.archive(
            "campaign-b", None, {"knowledge_root": tmp_path}
        )

        assert result.plan.review_cycle_days == 30
        assert any("missing live data" in w for w in result.warnings)
        assert result.runbook.recommendation == "MAINTAIN"
        assert result.stats["start_equity"] == 0.0


class TestArchivePersistence:
    async def test_artifacts_written_to_knowledge_store_dirs(self, tmp_path) -> None:
        archiver = Archiver()
        portfolio_data = {
            "knowledge_root": tmp_path,
            "equity_points": _equity_points(),
            "portfolio_candidates": ["s2"],
            "deployed_strategy_id": "s1",
            "strategy_state": StrategyState.DEGRADING,
        }

        result = await archiver.archive("campaign-c", None, portfolio_data)

        assert result.artifacts, "archiver wrote no artifacts"
        plan_path = tmp_path / "maintenance" / "campaign-c.yaml"
        runbook_path = tmp_path / "maintenance" / "campaign-c.runbook.yaml"
        stats_path = tmp_path / "campaign-phases" / "campaign-c_archive.yaml"
        assert plan_path.is_file()
        assert runbook_path.is_file()
        assert stats_path.is_file()
        # Persisted runbook is parseable and complete.
        persisted = yaml.safe_load(runbook_path.read_text(encoding="utf-8"))
        assert persisted["recommendation"] == "REPLACE"
        assert persisted["candidates"] == ["s2"]
        # Stats envelope embeds the account statistics.
        stats = yaml.safe_load(stats_path.read_text(encoding="utf-8"))
        assert stats["status"] == "archived"
        assert stats["stats"]["end_equity"] == 1050.0
