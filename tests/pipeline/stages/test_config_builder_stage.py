"""ConfigBuilderStage — Gap 9 (T4): the stage must write the CFX it announces.

The stage sits on the CFX build path, so its observable contract is the file
it produces and the ``cfx_path`` it hands downstream:

- the stage completes with ``status == "success"``;
- a readable ``.cfx`` archive exists at ``artifacts["cfx_path"]``, inside the
  configured output directory and named after the exploration id;
- the archive is a real ZIP holding at least one entry (not an empty file);
- ``artifacts["project_name"]`` carries the exploration id.
"""

from __future__ import annotations

import asyncio
import zipfile
from pathlib import Path

from quantlab.exploration.models import BrokerCostSnapshot, ExplorationDecision
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.config_builder_stage import (
    ConfigBuilderConfig,
    ConfigBuilderStage,
)


def _decision(exploration_id: str = "exp-1") -> ExplorationDecision:
    """A minimal valid ExplorationDecision for the config builder stage."""
    return ExplorationDecision(
        exploration_id=exploration_id,
        capital_usd=10000,
        market="EURUSD",
        timeframe="H1",
        leverage=30.0,
        capital_limits={
            "risk_per_trade_usd": 100,
            "max_drawdown_pct": 15.0,
            "max_concurrent_positions": 3,
        },
        operational_restrictions={
            "trading_hours_start": 8,
            "trading_hours_end": 20,
        },
        risk_management={
            "stop_loss_pips": 50,
            "take_profit_pips": 100,
            "trailing_stop_pips": 0,
        },
        money_management={
            "position_sizing_method": "fixed_fractional",
            "fixed_fractional_pct": 1.0,
        },
        statistical_edge={"expected_sharpe": 1.5},
        hypothesis="Test hypothesis for exploration",
        broker_info=BrokerCostSnapshot(),
    )


def _run_stage(tmp_path: Path) -> object:
    ctx = PipelineContext(
        config={"campaign_id": "camp-t4"},
        artifacts={"exploration_decision": _decision()},
    )
    stage = ConfigBuilderStage(ConfigBuilderConfig(output_dir=str(tmp_path / "cfx")))
    return asyncio.run(stage.execute(ctx))


class TestConfigBuilderWritesTheCfx:
    """Observable contract of ConfigBuilderStage: it writes a valid .cfx archive."""

    def test_stage_succeeds_and_writes_a_readable_archive(self, tmp_path: Path) -> None:
        result = _run_stage(tmp_path)

        # The stage must complete successfully
        assert result.status == "success", f"stage failed: {result.risks}"

        # The CFX path must be in artifacts and point to a real file
        cfx_path = Path(result.artifacts["cfx_path"])
        assert cfx_path.is_file(), f"CFX not written at {cfx_path}"

        # The file must live inside the configured output_dir / exploration_id
        expected_dir = tmp_path / "cfx" / "exp-1"
        assert cfx_path.parent == expected_dir
        assert cfx_path.name == "exp-1.cfx"

        # The archive must be a valid ZIP with at least one entry
        with zipfile.ZipFile(cfx_path) as zf:
            assert zf.namelist(), "CFX archive is empty"
            assert zf.testzip() is None, "CFX archive is corrupted"

        # The project_name artifact must carry the exploration id
        assert result.artifacts["project_name"] == "exp-1"