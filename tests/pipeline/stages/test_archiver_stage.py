"""ArchiverStage tests (tasks 3.4 / 4.7, REQ-33/REQ-26).

The stage adapts :class:`Archiver` to the pipeline ``Stage`` ABC: it reads
``guardian_state`` from the pipeline artifacts (produced by ``guardian_evaluate``),
composes the portfolio data from context, runs the injectable archiver, and
publishes ``archive_result``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from quantlab.agents.archiver import ArchiveResult, Archiver
from quantlab.guardian.models import PortfolioState
from quantlab.knowledge.models import MaintenancePlan
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.archiver_stage import ArchiverStage
from quantlab.readers.models import EquityPoint


def _archive_result() -> ArchiveResult:
    return ArchiveResult(
        campaign_id="c1",
        plan=MaintenancePlan(campaign_id="c1", review_cycle_days=7),
        runbook=None,  # type: ignore[arg-type]  # not exercised here
        stats={"end_equity": 1050.0, "pnl": 50.0, "max_drawdown": 0.0, "start_equity": 1000.0},
    )


class TestArchiverStageContract:
    def test_name_and_io_contract(self) -> None:
        assert ArchiverStage.name == "archiver"
        assert ArchiverStage.requires == ["guardian_state"]
        assert ArchiverStage.provides == ["archive_result"]


class TestArchiverStageExecute:
    async def test_execute_runs_injected_archiver_and_publishes_result(self) -> None:
        result = _archive_result()
        archiver = AsyncMock(Archiver)
        archiver.archive = AsyncMock(return_value=result)
        stage = ArchiverStage(archiver=archiver)

        points = [
            EquityPoint(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), equity=1000.0),
        ]
        ctx = PipelineContext(
            config={"campaign_id": "c1", "deployed_strategy_id": "s1", "knowledge_root": "/tmp/kb"},
            artifacts={
                "guardian_state": PortfolioState.DEFENSIVE,
                "equity_points": points,
                "portfolio_candidates": ["s2"],
                "parameter_matrix": [{"parameter": "sl_atr", "confidence": 0.2}],
            },
        )

        output = await stage.execute(ctx)

        assert output["archive_result"] is result
        assert ctx.artifacts["archive_result"] is result
        archiver.archive.assert_awaited_once()
        campaign_id, guardian_state, portfolio_data = archiver.archive.await_args.args
        assert campaign_id == "c1"
        assert guardian_state == PortfolioState.DEFENSIVE
        assert portfolio_data["deployed_strategy_id"] == "s1"
        assert portfolio_data["portfolio_candidates"] == ["s2"]
        assert portfolio_data["equity_points"] == points
        assert portfolio_data["knowledge_root"] == "/tmp/kb"
        assert portfolio_data["parameter_matrix"][0]["parameter"] == "sl_atr"

    async def test_defaults_when_context_is_sparse(self) -> None:
        result = _archive_result()
        archiver = AsyncMock(Archiver)
        archiver.archive = AsyncMock(return_value=result)
        stage = ArchiverStage(archiver=archiver)

        ctx = PipelineContext(config={}, artifacts={"guardian_state": PortfolioState.NORMAL})

        await stage.execute(ctx)

        campaign_id, guardian_state, portfolio_data = archiver.archive.await_args.args
        assert campaign_id == "campaign"
        assert guardian_state == PortfolioState.NORMAL
        assert portfolio_data["deployed_strategy_id"] == ""
        assert portfolio_data["portfolio_candidates"] == []
