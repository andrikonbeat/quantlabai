"""Tests for the campaign archive phase — REQ-33 (+ REQ-38 archive gate).

Verifies the archive phase produces a maintenance/replacement plan, account
statistics over the demo window, and an artifact bundle; that a DEGRADING
strategy (Guardian report) triggers a replacement recommendation from the
campaign portfolio (REQ-33 scenario 2); and that the HUMAN_APPROVE_ARCHIVE
gate holds the plan for human confirmation — denial returns the campaign to
maintenance and a no-callback / fallback outcome is never treated as
approval (REQ-38 scenario 3, fail-closed).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from quantlab.gates.models import GateDecision, GateDecisionAction
from quantlab.guardian.feedback import FeedbackSignals, record
from quantlab.guardian.models import StrategyState
from quantlab.phase4.campaign_archive import (
    AccountStats,
    ArchiveBundle,
    ArchivePhase,
    MaintenancePlan,
    account_stats,
    build_plan,
)
from quantlab.readers.models import EquityPoint


def _curve(values: list[float]) -> list[EquityPoint]:
    return [
        EquityPoint(timestamp=datetime.now(timezone.utc), equity=v)
        for v in values
    ]


class TestAccountStats:
    """REQ-33: account statistics over the demo window."""

    def test_stats_computed_over_window(self) -> None:
        """GIVEN an equity curve over the demo window
        WHEN account_stats runs
        THEN equity, drawdown and P&L are computed (REQ-33 scenario 1).
        """
        stats = account_stats(
            _curve([100.0, 90.0, 95.0, 88.0]),
            start_equity=100.0,
        )

        assert isinstance(stats, AccountStats)
        assert stats.start_equity == 100.0
        assert stats.end_equity == 88.0
        assert stats.pnl == pytest.approx(-12.0)
        assert stats.max_drawdown == pytest.approx(0.12)  # 88 vs peak 100

    def test_stats_default_start_is_first_point(self) -> None:
        """GIVEN no explicit start equity
        WHEN account_stats runs
        THEN the first equity point anchors the window start.
        """
        stats = account_stats(_curve([1000.0, 1050.0, 1030.0]))

        assert stats.start_equity == 1000.0
        assert stats.end_equity == 1030.0
        assert stats.pnl == pytest.approx(30.0)

    def test_stats_empty_curve_is_zeroed(self) -> None:
        """GIVEN no equity data at all
        WHEN account_stats runs
        THEN a zeroed statistics block is produced (no crash).
        """
        stats = account_stats([], start_equity=100.0)

        assert stats.start_equity == 100.0
        assert stats.end_equity == 100.0
        assert stats.pnl == 0.0
        assert stats.max_drawdown == 0.0


class TestBuildPlan:
    """REQ-33 scenario 2: DEGRADING strategy triggers replacement."""

    def test_degrading_strategy_recommends_replacement(self) -> None:
        """GIVEN Guardian reports the deployed strategy DEGRADING
        WHEN the archive plan is composed
        THEN it recommends replacement from the campaign portfolio.
        """
        plan = build_plan(
            campaign_id="camp-arch",
            deployed_strategy_id="strat-a",
            strategy_state=StrategyState.DEGRADING,
            portfolio_candidates=["strat-a", "strat-b", "strat-c"],
        )

        assert isinstance(plan, MaintenancePlan)
        assert plan.recommendation == "REPLACE"
        assert "DEGRADING" in plan.reason
        candidates = {c.strategy_id for c in plan.candidates}
        assert candidates == {"strat-b", "strat-c"}  # deployed excluded

    def test_healthy_strategy_maintains(self) -> None:
        """GIVEN an ACTIVE deployed strategy
        WHEN the archive plan is composed
        THEN the plan recommends maintenance (no candidates).
        """
        plan = build_plan(
            campaign_id="camp-ok",
            deployed_strategy_id="strat-a",
            strategy_state=StrategyState.ACTIVE,
            portfolio_candidates=["strat-a", "strat-b"],
        )

        assert plan.recommendation == "MAINTAIN"
        assert plan.candidates == []

    def test_feedback_degradation_drives_replacement(self) -> None:
        """GIVEN a healthy state but a degrading feedback record
        WHEN the archive plan is composed
        THEN the feedback signal drives replacement (REQ-34 → REQ-33).
        """
        feedback = record(
            "camp-fb",
            FeedbackSignals(degradation=True, drawdown=0.14),
        )
        plan = build_plan(
            campaign_id="camp-fb",
            deployed_strategy_id="strat-a",
            strategy_state=StrategyState.ACTIVE,
            portfolio_candidates=["strat-a", "strat-b"],
            feedback=feedback,
        )

        assert plan.recommendation == "REPLACE"
        assert [c.strategy_id for c in plan.candidates] == ["strat-b"]


class TestArchivePhaseGate:
    """REQ-38 scenario 3: HUMAN_APPROVE_ARCHIVE holds the plan."""

    @staticmethod
    def _phase(gate_fn: Any | None = None) -> ArchivePhase:
        return ArchivePhase(gate_fn=gate_fn)

    @staticmethod
    def _ctx() -> dict[str, Any]:
        return {
            "gate_id": "HUMAN_APPROVE_ARCHIVE",
            "campaign_id": "camp-arch",
            "stage_name": "archive_phase",
        }

    @pytest.mark.asyncio
    async def test_approval_finalizes_archive_bundle(self) -> None:
        """GIVEN a completed demo window and a human approval
        WHEN the archive phase runs
        THEN the plan and stats are written and the bundle is archived
        (REQ-33 scenario 1).
        """
        async def approve(ctx: dict[str, Any]) -> GateDecision:
            assert ctx["gate_id"] == "HUMAN_APPROVE_ARCHIVE"
            return GateDecision(
                gate_id="HUMAN_APPROVE_ARCHIVE",
                action=GateDecisionAction.APPROVE,
                reason="archive ok",
                decided_by="human",
            )

        phase = self._phase(gate_fn=approve)
        bundle = await phase.run(
            "camp-arch",
            strategy_state=StrategyState.ACTIVE,
            portfolio_candidates=["strat-a", "strat-b"],
            equity_points=_curve([100.0, 95.0, 105.0]),
            artifacts=["bundle/strategies.csv", "bundle/plan.md"],
        )

        assert isinstance(bundle, ArchiveBundle)
        assert bundle.status == "ARCHIVED"
        assert bundle.plan.recommendation == "MAINTAIN"
        assert bundle.stats.end_equity == pytest.approx(105.0)
        assert len(bundle.artifacts) == 2
        assert bundle.archived_at is not None

    @pytest.mark.asyncio
    async def test_denial_returns_to_maintenance(self) -> None:
        """GIVEN a human denial of the archive
        WHEN the archive phase runs
        THEN no archive is finalized — the campaign returns to maintenance.
        """
        async def deny(ctx: dict[str, Any]) -> GateDecision:
            return GateDecision(
                gate_id="HUMAN_APPROVE_ARCHIVE",
                action=GateDecisionAction.REJECT,
                reason="keep running",
                decided_by="human",
            )

        phase = self._phase(gate_fn=deny)
        bundle = await phase.run(
            "camp-arch",
            strategy_state=StrategyState.ACTIVE,
            equity_points=_curve([100.0, 95.0]),
            artifacts=["bundle/strategies.csv"],
        )

        assert bundle.status == "DENIED"
        assert bundle.artifacts == []
        assert bundle.archived_at is None

    @pytest.mark.asyncio
    async def test_no_callback_fails_closed(self) -> None:
        """GIVEN autonomous mode with no archive callback
        WHEN the archive phase runs
        THEN the HOLD fallback applies and the archive never finalizes.
        """
        phase = self._phase(gate_fn=None)
        bundle = await phase.run(
            "camp-arch",
            strategy_state=StrategyState.DEGRADING,
            portfolio_candidates=["strat-a", "strat-b"],
            equity_points=_curve([100.0, 85.0]),
        )

        assert bundle.status == "DENIED"
        assert bundle.decision_action != GateDecisionAction.APPROVE.value

    @pytest.mark.asyncio
    async def test_fallback_hold_is_not_approval(self) -> None:
        """GIVEN a HOLD/FALLBACK gate outcome
        WHEN the archive phase consumes it
        THEN it is NOT treated as approval — explicit APPROVE is required
        (PR-4 finding: GateDecision.is_approved() returns True for FALLBACK).
        """
        async def fallback_hold(ctx: dict[str, Any]) -> GateDecision:
            return GateDecision(
                gate_id="HUMAN_APPROVE_ARCHIVE",
                action=GateDecisionAction.FALLBACK,
                reason="HOLD fallback",
                decided_by="system",
            )

        phase = self._phase(gate_fn=fallback_hold)
        bundle = await phase.run("camp-arch", equity_points=_curve([100.0]))

        assert bundle.status == "DENIED"
        assert bundle.decision_action == GateDecisionAction.FALLBACK.value

    @pytest.mark.asyncio
    async def test_archive_bundle_serializable_for_audit(self) -> None:
        """GIVEN an archived bundle
        WHEN to_dict() runs
        THEN it is a JSON-safe audit record.
        """
        async def approve(ctx: dict[str, Any]) -> GateDecision:
            return GateDecision(
                gate_id="HUMAN_APPROVE_ARCHIVE",
                action=GateDecisionAction.APPROVE,
                reason="ok",
                decided_by="human",
            )

        phase = self._phase(gate_fn=approve)
        bundle = await phase.run(
            "camp-arch",
            strategy_state=StrategyState.DEGRADING,
            portfolio_candidates=["strat-a", "strat-b"],
            equity_points=_curve([100.0, 88.0]),
            artifacts=["bundle/plan.md"],
        )
        import json

        payload = bundle.to_dict()
        json.dumps(payload)  # must not raise

        assert payload["status"] == "ARCHIVED"
        assert payload["plan"]["recommendation"] == "REPLACE"
        assert payload["stats"]["end_equity"] == pytest.approx(88.0)
