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


# ── 4.2 typed builders preserve unmodeled content ─────────────────────────────


class TestTypedCrossChecksBuilders:
    """The builders must emit typed sections without losing dialect content.

    Task 4.2 required the adaptive retest builders to construct typed
    CrossChecksConfig objects. The typed layer is derived by parsing the
    builder's own XML, and every child keeps its original markup in the
    sub-models' raw_xml, so serializing back must reproduce the builder's
    content exactly — including the elements the models do not model
    (<Methods>, <Param1>/<Param2>, <OptimizeExitTypes>).
    """

    def test_automatic_retest_builder_is_typed_and_faithful(self, tmp_path: Path):
        cfx = tmp_path / "typed_auto.cfx"
        _write_cfx(
            cfx,
            BuildTask(
                data=SettingsSection(name="Data", settings={}),
                cross_checks_section=CrossChecksConfig(
                    raw_xml="<CrossChecks><MonteCarlo enabled='false'/></CrossChecks>"
                ),
            ),
        )
        apply_adaptive_mutations(cfx, RetestMode.AUTOMATIC_RETEST)

        cc = CfxReader.read(cfx).config.task.cross_checks_section
        ar = cc.automatic_retest

        # Typed access is available to consumers.
        assert cc.dialect == "automatic_retest"
        assert ar.retest_with_higher_precision.precision == 4
        assert ar.retest_with_higher_precision.spread == 2
        assert ar.monte_carlo_retest.number_of_simulations == 100
        assert ar.walk_forward_optimization.walk_forward_type == "1"
        assert ar.walk_forward_optimization.optimize_periods is True
        assert ar.walk_forward_matrix is not None

        # Unmodeled content survived the write/read round-trip.
        xml = cc.to_xml()
        assert "RandomizeHistoryData" in xml
        assert '<Param1 value="18" />' in xml
        assert "<OptimizeExitTypes>true</OptimizeExitTypes>" in xml

    def test_retest_builder_is_typed_and_keeps_child_form(self, tmp_path: Path):
        cfx = tmp_path / "typed_retest.cfx"
        _write_cfx(
            cfx,
            BuildTask(
                data=SettingsSection(name="Data", settings={}),
                cross_checks_section=CrossChecksConfig(
                    raw_xml="<CrossChecks><MonteCarlo enabled='false'/></CrossChecks>"
                ),
            ),
        )
        apply_adaptive_mutations(cfx, RetestMode.RETEST)

        cc = CfxReader.read(cfx).config.task.cross_checks_section

        assert cc.dialect == "generic"
        assert cc.generic.mc_enabled is True
        assert cc.generic.mc_runs == 100
        assert cc.generic.wf_cycles == 5
        assert cc.generic.confidence_level == 0.95

        # The builder emits the child form of ConfidenceLevel; the generic
        # serializer must not rewrite it into the attribute form.
        assert "<ConfidenceLevel>0.95</ConfidenceLevel>" in cc.to_xml()

    def test_built_section_has_no_duplicate_children(self, tmp_path: Path):
        """Typed parsing must not leave copies behind in raw_xml."""
        cfx = tmp_path / "typed_dedup.cfx"
        _write_cfx(
            cfx,
            BuildTask(
                data=SettingsSection(name="Data", settings={}),
                cross_checks_section=CrossChecksConfig(
                    raw_xml="<CrossChecks><MonteCarlo enabled='false'/></CrossChecks>"
                ),
            ),
        )
        apply_adaptive_mutations(cfx, RetestMode.AUTOMATIC_RETEST)

        cc = CfxReader.read(cfx).config.task.cross_checks_section
        xml = cc.to_xml()

        for tag in ("RetestWithHigherPrecision", "MonteCarloRetest", "WalkForwardMatrix"):
            assert xml.count(f"<{tag} ") + xml.count(f"<{tag}>") == 1, tag


# ── apply_adaptive_mutations ──────────────────────────────────────────────────


class TestApplyAdaptiveMutations:
    """CFX → patch → re-read round-trip."""

    def test_mutate_to_automatic_retest(self, tmp_path: Path):
        """GIVEN a CFX archive with a Retest task
        WHEN apply_adaptive_mutations(cfx_path, mode=AutomaticRetest) runs
        THEN the task CrossChecks reflect AutomaticRetest via typed fields.
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
        cc = task.cross_checks_section
        assert cc is not None
        assert cc.dialect == "automatic_retest"
        assert cc.automatic_retest is not None
        assert cc.automatic_retest.retest_with_higher_precision is not None
        assert cc.automatic_retest.opt_profile_sys_param_permutation is not None

    def test_mutate_to_retest(self, tmp_path: Path):
        """GIVEN a CFX archive with an AutomaticRetest task
        WHEN apply_adaptive_mutations(cfx_path, mode=Retest) runs
        THEN the task CrossChecks reflect full Retest via typed fields.
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
        cc = task.cross_checks_section
        assert cc is not None
        assert cc.dialect == "generic"
        assert cc.generic is not None
        assert cc.generic.mc_enabled is True
        assert cc.generic.wf_enabled is True

    def test_preserves_unrelated_cfx_content(self, tmp_path: Path):
        """GIVEN a CFX archive with a populated <Data> and two sibling sections
        WHEN apply_adaptive_mutations rewrites that same path in place
        THEN each non-retest section round-trips key-for-key and value-for-value.

        REQ-FLAT-7. The four-key ``<Data>`` is the canary: market symbol,
        timeframe and both date bounds are exactly what the pre-inversion codec
        destroyed, collapsing the section to a single ``Setting@key`` /
        ``Setting@value`` pair. That is why the previous probe —
        ``any("EURUSD" in v for v in ...)`` — stayed green through the defect:
        a substring match cannot see a key collapse or a mangled key name.
        Exact dict equality is the assertion that can.
        """
        cfx = tmp_path / "preserve.cfx"
        data_keys = {
            "Symbol@symbol": "EURUSD",
            "Timeframe1@value": "H1",
            "FromDate@value": "2015.01.01",
            "ToDate@value": "2024.12.31",
        }
        task = BuildTask(
            data=SettingsSection(name="Data", settings=dict(data_keys)),
            what_to_build=SettingsSection(name="WhatToBuild", settings={"StrategyType@type": "simple"}),
            cross_checks_section=CrossChecksConfig(raw_xml="<CrossChecks></CrossChecks>"),
            notes=SettingsSection(name="Notes", settings={"Note@text": "keep me"}),
        )
        _write_cfx(cfx, task)
        apply_adaptive_mutations(cfx, RetestMode.AUTOMATIC_RETEST)

        archive = CfxReader.read(cfx)
        task = archive.config.task
        assert task.data.settings == data_keys
        assert task.what_to_build.settings == {"StrategyType@type": "simple"}
        assert task.notes.settings == {"Note@text": "keep me"}
        # The mangled literals must not reappear as keys in their own right.
        assert not task.data.settings.keys() & {"Setting@key", "Setting@value"}


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
