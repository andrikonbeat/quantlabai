"""Tests for Adaptive Retest Agent (WU-3 / PR-3).

Covers:
- select_retest_mode decision rules and metadata override precedence
- inspect_cfx_signals read-only behavior and missing-field defaults
- apply_adaptive_mutations round-trip via CfxWriter
- RetesterConfig.from_cfx
- RetesterStage CFX-sourced config and DSL fallback
"""

from __future__ import annotations

import hashlib
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from quantlab.agents.adaptive_retest_agent import (
    RetestMode,
    RetestSignals,
    apply_adaptive_mutations,
    inspect_cfx_signals,
    select_retest_mode,
)
from quantlab.cfx.models import (
    BuildTask,
    CfxArchive,
    CfxConfig,
    CfxProject,
    CrossChecksConfig,
    DatabanksConfig,
    RankingsConfig,
    RetesterDataConfig,
    SettingsSection,
)
from quantlab.cfx.reader import CfxReader
from quantlab.cfx.writer import CfxWriter
from quantlab.phase4.retester import RetesterConfig
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.retester_stage import RetesterStage


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_cfx_bytes(task: BuildTask | None = None, *, version: str = "144.2953") -> bytes:
    """Create a minimal single-task CFX archive in memory."""
    if task is None:
        task = BuildTask(
            options=SettingsSection(name="Options", settings={}),
            what_to_build=SettingsSection(name="WhatToBuild", settings={}),
            data=SettingsSection(name="Data", settings={}),
            cross_checks=SettingsSection(name="CrossChecks", settings={}),
            rankings=SettingsSection(name="Rankings", settings={}),
        )
    archive = CfxArchive(
        config=CfxConfig(task=task, schema_version=version),
    )
    return CfxWriter.to_bytes(archive)


def _write_cfx(path: Path, task: BuildTask | None = None) -> None:
    path.write_bytes(_make_cfx_bytes(task))


def _cfx_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── select_retest_mode ────────────────────────────────────────────────────────


class TestSelectRetestMode:
    """Table-driven tests for select_retest_mode decision rules."""

    @pytest.mark.parametrize(
        "signals, expected",
        [
            # No signals → default AutomaticRetest
            (
                RetestSignals(),
                RetestMode.AUTOMATIC_RETEST,
            ),
            # Low trade count → AutomaticRetest
            (
                RetestSignals(trade_count=30),
                RetestMode.AUTOMATIC_RETEST,
            ),
            # Exactly 50 trades → not low, fall through
            (
                RetestSignals(trade_count=50),
                RetestMode.AUTOMATIC_RETEST,
            ),
            # High trade count, all passed → default AutomaticRetest
            (
                RetestSignals(trade_count=200, monte_carlo_passed=True, walkforward_passed=True, databank_coverage=0.9),
                RetestMode.AUTOMATIC_RETEST,
            ),
            # Failed Monte Carlo → Retest
            (
                RetestSignals(trade_count=200, monte_carlo_passed=False),
                RetestMode.RETEST,
            ),
            # Failed Walk-Forward → Retest
            (
                RetestSignals(trade_count=200, walkforward_passed=False),
                RetestMode.RETEST,
            ),
            # Low databank coverage → Retest
            (
                RetestSignals(trade_count=200, databank_coverage=0.5),
                RetestMode.RETEST,
            ),
            # Exactly 0.8 coverage → not low, fall through
            (
                RetestSignals(trade_count=200, databank_coverage=0.8),
                RetestMode.AUTOMATIC_RETEST,
            ),
            # Multiple failures → Retest (MC wins first)
            (
                RetestSignals(trade_count=200, monte_carlo_passed=False, walkforward_passed=False),
                RetestMode.RETEST,
            ),
        ],
    )
    def test_decision_rules(self, signals, expected):
        assert select_retest_mode(signals) == expected

    def test_metadata_override_automatic_retest(self):
        """CFX metadata override forces AutomaticRetest even when signals say Retest."""
        signals = RetestSignals(trade_count=200, monte_carlo_passed=False)
        assert select_retest_mode(signals, metadata={"retest_mode": RetestMode.AUTOMATIC_RETEST}) == RetestMode.AUTOMATIC_RETEST

    def test_metadata_override_retest(self):
        """CFX metadata override forces Retest even when signals say AutomaticRetest."""
        signals = RetestSignals(trade_count=30)
        assert select_retest_mode(signals, metadata={"retest_mode": RetestMode.RETEST}) == RetestMode.RETEST

    def test_metadata_override_invalid_value_ignored(self):
        """Invalid metadata value is ignored; fallback to signal rules."""
        signals = RetestSignals(trade_count=30)
        assert select_retest_mode(signals, metadata={"retest_mode": "InvalidMode"}) == RetestMode.AUTOMATIC_RETEST

    def test_metadata_empty_dict_ignored(self):
        """Empty metadata dict falls back to signal rules."""
        signals = RetestSignals(trade_count=30)
        assert select_retest_mode(signals, metadata={}) == RetestMode.AUTOMATIC_RETEST


# ── inspect_cfx_signals ───────────────────────────────────────────────────────


class TestInspectCfxSignals:
    """Read-only signal extraction and missing-field defaults."""

    def test_read_only_archive_hash_unchanged(self, tmp_path: Path):
        """GIVEN a CFX archive
        WHEN inspect_cfx_signals reads it
        THEN the file hash is unchanged.
        """
        cfx = tmp_path / "readonly.cfx"
        task = BuildTask(
            data=SettingsSection(name="Data", settings={}),
            cross_checks=SettingsSection(name="CrossChecks", settings={}),
            rankings=SettingsSection(name="Rankings", settings={}),
            retester_data=RetesterDataConfig(
                raw_xml=(
                    "<RetesterData>"
                    "<MinTrades value=\"150\"/>"
                    "<MonteCarloRuns value=\"100\"/>"
                    "<WalkforwardCycles value=\"5\"/>"
                    "</RetesterData>"
                )
            ),
            databanks_section=DatabanksConfig(raw_xml='<Databanks><Databank name="EURUSD_H1" enabled="true"/></Databanks>'),
        )
        _write_cfx(cfx, task)
        before = _cfx_hash(cfx)

        signals = inspect_cfx_signals(cfx)

        after = _cfx_hash(cfx)
        assert before == after
        assert signals.trade_count == 150

    def test_missing_optional_signals_default_to_none(self, tmp_path: Path):
        """GIVEN a CFX archive from a template with no prior retest runs
        WHEN inspect_cfx_signals reads it
        THEN optional signals are None and no exception is raised.
        """
        cfx = tmp_path / "empty.cfx"
        _write_cfx(cfx)
        signals = inspect_cfx_signals(cfx)
        assert signals.last_run_status is None
        assert signals.trade_count is None
        assert signals.monte_carlo_passed is None
        assert signals.walkforward_passed is None
        assert signals.databank_coverage is None

    def test_extracts_monte_carlo_and_walkforward_status(self, tmp_path: Path):
        cfx = tmp_path / "status.cfx"
        task = BuildTask(
            cross_checks_section=CrossChecksConfig(
                raw_xml=(
                    "<CrossChecks>"
                    '<MonteCarlo enabled="true" runs="100" percentile="95" />'
                    '<WalkForward enabled="false" cycles="5" />'
                    "</CrossChecks>"
                )
            ),
        )
        _write_cfx(cfx, task)
        signals = inspect_cfx_signals(cfx)
        assert signals.monte_carlo_passed is True
        assert signals.walkforward_passed is False

    def test_extracts_databank_coverage(self, tmp_path: Path):
        cfx = tmp_path / "coverage.cfx"
        task = BuildTask(
            databanks_section=DatabanksConfig(
                raw_xml=(
                    '<Databanks>'
                    '<Databank name="EURUSD_H1" enabled="true"/>'
                    '<Databank name="GBPUSD_H1" enabled="false"/>'
                    "</Databanks>"
                )
            ),
        )
        _write_cfx(cfx, task)
        signals = inspect_cfx_signals(cfx)
        assert signals.databank_coverage == pytest.approx(0.5)

    def test_extracts_last_run_status_from_metadata(self, tmp_path: Path):
        cfx = tmp_path / "meta.cfx"
        archive = CfxArchive(
            config=CfxProject(
                name="Meta",
                tasks={},
                schema_version="144.2953",
                metadata={"last_run_status": "completed"},
            ),
            task_files={},
        )
        CfxWriter.write(archive, cfx)
        signals = inspect_cfx_signals(cfx)
        assert signals.last_run_status == "completed"


# ── apply_adaptive_mutations ──────────────────────────────────────────────────


class TestApplyAdaptiveMutations:
    """CFX → patch → re-read round-trip."""

    def test_mutate_to_automatic_retest(self, tmp_path: Path):
        """GIVEN a CFX archive with a Retest task
        WHEN apply_adaptive_mutations(cfx_path, mode=AutomaticRetest) runs
        THEN the task CrossChecks reflect AutomaticRetest.
        """
        cfx = tmp_path / "mutate.cfx"
        task = BuildTask(
            data=SettingsSection(name="Data", settings={}),
            cross_checks_section=CrossChecksConfig(raw_xml="<CrossChecks><MonteCarlo enabled='false'/></CrossChecks>"),
        )
        _write_cfx(cfx, task)
        apply_adaptive_mutations(cfx, RetestMode.AUTOMATIC_RETEST)

        archive = CfxReader.read(cfx)
        task = archive.config.task
        assert "RetestWithHigherPrecision" in task.cross_checks_section.raw_xml
        assert "OptProfileSysParamPermutation" in task.cross_checks_section.raw_xml

    def test_mutate_to_retest(self, tmp_path: Path):
        """GIVEN a CFX archive with an AutomaticRetest task
        WHEN apply_adaptive_mutations(cfx_path, mode=Retest) runs
        THEN the task CrossChecks reflect full Retest.
        """
        cfx = tmp_path / "mutate_retest.cfx"
        task = BuildTask(
            data=SettingsSection(name="Data", settings={}),
            cross_checks_section=CrossChecksConfig(raw_xml="<CrossChecks><RetestWithHigherPrecision use='false'/></CrossChecks>"),
        )
        _write_cfx(cfx, task)
        apply_adaptive_mutations(cfx, RetestMode.RETEST)

        archive = CfxReader.read(cfx)
        task = archive.config.task
        assert '<MonteCarlo enabled="true"' in task.cross_checks_section.raw_xml
        assert '<WalkForward enabled="true"' in task.cross_checks_section.raw_xml

    def test_preserves_unrelated_cfx_content(self, tmp_path: Path):
        """GIVEN a CFX archive with multiple settings sections
        WHEN apply_adaptive_mutations runs
        THEN non-retest sections are unchanged.
        """
        cfx = tmp_path / "preserve.cfx"
        task = BuildTask(
            data=SettingsSection(name="Data", settings={"Symbol@symbol": "EURUSD"}),
            what_to_build=SettingsSection(name="WhatToBuild", settings={"StrategyType@type": "simple"}),
            cross_checks_section=CrossChecksConfig(raw_xml="<CrossChecks></CrossChecks>"),
            notes=SettingsSection(name="Notes", settings={"Note@text": "keep me"}),
        )
        _write_cfx(cfx, task)
        apply_adaptive_mutations(cfx, RetestMode.AUTOMATIC_RETEST)

        archive = CfxReader.read(cfx)
        task = archive.config.task
        # SettingsSection keys flatten on round-trip; verify the original values
        # are still present in the read-back structure.
        assert any("EURUSD" in v for v in task.data.settings.values())
        assert any("simple" in v for v in task.what_to_build.settings.values())
        assert any("keep me" in v for v in task.notes.settings.values())


# ── RetesterConfig.from_cfx ───────────────────────────────────────────────────


class TestRetesterConfigFromCfx:
    """RetesterConfig.from_cfx integration."""

    def test_from_cfx_returns_valid_config(self, tmp_path: Path):
        cfx = tmp_path / "retester.cfx"
        task = BuildTask(
            retester_data=RetesterDataConfig(
                raw_xml=(
                    "<RetesterData>"
                    "<MonteCarloRuns value=\"200\"/>"
                    "<WalkforwardCycles value=\"8\"/>"
                    "<ConfidenceLevel value=\"0.90\"/>"
                    "<MinTrades value=\"50\"/>"
                    "<MCPercentile value=\"90\"/>"
                    "<Databanks>"
                    '<Databank name="EURUSD_H1" enabled="true"/>'
                    '<Databank name="GBPUSD_H1" enabled="true"/>'
                    "</Databanks>"
                    "</RetesterData>"
                )
            ),
        )
        _write_cfx(cfx, task)
        config = RetesterConfig.from_cfx(cfx)

        assert config.monte_carlo_runs == 200
        assert config.walkforward_cycles == 8
        assert config.confidence_level == 0.90
        assert config.min_trades == 50
        assert config.mc_percentile == 90
        assert config.databanks == ["EURUSD_H1", "GBPUSD_H1"]

    def test_from_cfx_defaults_when_sections_missing(self, tmp_path: Path):
        cfx = tmp_path / "empty_retester.cfx"
        task = BuildTask(
            retester_data=RetesterDataConfig(raw_xml="<RetesterData></RetesterData>"),
        )
        _write_cfx(cfx, task)
        config = RetesterConfig.from_cfx(cfx)

        assert config.monte_carlo_runs == 100
        assert config.walkforward_cycles == 5
        assert config.confidence_level == 0.95
        assert config.min_trades == 30
        assert config.mc_percentile == 95
        assert config.databanks == []

    def test_from_cfx_raises_when_no_retester_data(self, tmp_path: Path):
        cfx = tmp_path / "no_retester.cfx"
        _write_cfx(cfx)
        with pytest.raises(ValueError, match="No RetesterData"):
            RetesterConfig.from_cfx(cfx)


# ── RetesterStage CFX-sourced config ─────────────────────────────────────────


class TestRetesterStageCfxConfig:
    """RetesterStage DSL fallback and CFX-sourced config."""

    @pytest.mark.asyncio
    async def test_dsl_fallback_when_cfx_absent(self):
        """GIVEN no CFX path and no DSL retest block
        WHEN RetesterStage.execute runs
        THEN retest_result is None and no CFX parsing is attempted.
        """
        from quantlab.dsl.models import ResearchConfig

        stage = RetesterStage(retester=None)
        research_config = ResearchConfig(campaign="Test", market="EURUSD", timeframe="H1")
        ctx = PipelineContext(config={}, artifacts={"research_config": research_config})

        result = await stage.execute(ctx)
        assert result == {"retest_result": None}
        assert ctx.artifacts["retest_result"] is None

    @pytest.mark.asyncio
    async def test_cfx_config_used_when_dsl_block_absent(self, tmp_path: Path):
        """GIVEN a CFX path and no DSL retest block
        WHEN RetesterStage.execute runs
        THEN RetesterConfig is built from CFX and the retester is invoked.
        """
        from quantlab.dsl.models import ResearchConfig
        from unittest.mock import AsyncMock, MagicMock

        cfx = tmp_path / "stage.cfx"
        task = BuildTask(
            retester_data=RetesterDataConfig(
                raw_xml=(
                    "<RetesterData>"
                    "<MonteCarloRuns value=\"300\"/>"
                    "<WalkforwardCycles value=\"12\"/>"
                    "<Databanks>"
                    '<Databank name="EURUSD_H1" enabled="true"/>'
                    "</Databanks>"
                    "</RetesterData>"
                )
            ),
        )
        _write_cfx(cfx, task)

        fake_retester = AsyncMock(return_value=MagicMock())
        stage = RetesterStage(retester=fake_retester, cfx_path=str(cfx))

        research_config = ResearchConfig(campaign="Test", market="EURUSD", timeframe="H1")
        ctx = PipelineContext(
            config={
                "rationale_overrides": {
                    "monte_carlo_runs": "from CFX",
                    "walkforward_cycles": "from CFX",
                    "databanks": "required by CFX",
                }
            },
            artifacts={"research_config": research_config},
        )

        await stage.execute(ctx)

        fake_retester.run.assert_awaited_once()
        call_args = fake_retester.run.call_args
        config_arg = call_args[0][0]  # first positional arg
        assert config_arg.monte_carlo_runs == 300
        assert config_arg.walkforward_cycles == 12
        assert config_arg.databanks == ["EURUSD_H1"]

    @pytest.mark.asyncio
    async def test_dsl_block_takes_precedence_over_cfx(self, tmp_path: Path):
        """GIVEN both DSL retest block and CFX path
        WHEN RetesterStage.execute runs
        THEN DSL config is used and CFX is ignored.
        """
        from quantlab.dsl.models import ResearchConfig, RetestBlock
        from unittest.mock import AsyncMock, MagicMock

        cfx = tmp_path / "stage_dsl.cfx"
        task = BuildTask(
            retester_data=RetesterDataConfig(
                raw_xml=(
                    "<RetesterData>"
                    "<MonteCarloRuns value=\"300\"/>"
                    "<Databanks>"
                    '<Databank name="EURUSD_H1" enabled="true"/>'
                    "</Databanks>"
                    "</RetesterData>"
                )
            ),
        )
        _write_cfx(cfx, task)

        fake_retester = AsyncMock(return_value=MagicMock())
        block = RetestBlock(strategy_id="S1", databanks=["EURUSD_H1"], monte_carlo_runs=500)
        stage = RetesterStage(retester=fake_retester, cfx_path=str(cfx))

        research_config = ResearchConfig(
            campaign="Test",
            market="EURUSD",
            timeframe="H1",
            retest=block,
        )
        ctx = PipelineContext(
            config={
                "rationale_overrides": {
                    "databanks": "required by DSL",
                    "monte_carlo_runs": "500 MC runs from DSL",
                }
            },
            artifacts={"research_config": research_config},
        )

        await stage.execute(ctx)

        call_args = fake_retester.run.call_args
        config_arg = call_args[0][0]  # first positional arg
        assert config_arg.monte_carlo_runs == 500  # DSL value, not CFX 300
        assert config_arg.strategy_id == "S1"
