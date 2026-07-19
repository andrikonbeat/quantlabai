"""Tests for CFX reader/writer/patcher round-trips for Portfolio/Optimizer/Retester."""

import base64
import tempfile
from pathlib import Path

import pytest

from quantlab.cfx import CfxWriter
from quantlab.cfx.models import (
    AutomaticPortfolioBuilderConfig,
    BuildTask,
    CfxArchive,
    CfxConfig,
    CfxProject,
    CrossChecksConfig,
    DatabanksConfig,
    OptimizationConfig,
    OptimizationParametersConfig,
    PortfolioSettingsConfig,
    RankingsConfig,
    SettingsSection,
    WalkForwardConfig,
)
from quantlab.cfx.patcher import CfxPatcher, ValidationError
from quantlab.cfx.reader import CfxReader
from quantlab.phase4.templates import CfxTemplateBuilder


def _make_portfolio_task() -> BuildTask:
    """Create a BuildTask with Portfolio sections populated."""
    task = BuildTask()
    task.automatic_portfolio_builder = AutomaticPortfolioBuilderConfig(
        raw_xml="""<AutomaticPortfolioBuilder>
  <Generations value="50"/>
  <PopulationSize value="200"/>
  <FitnessFunction value="NetProfit"/>
</AutomaticPortfolioBuilder>"""
    )
    task.portfolio_settings = PortfolioSettingsConfig(
        raw_xml="""<PortfolioSettings>
  <MinStrategies value="2"/>
  <MaxStrategies value="10"/>
  <RebalancingPeriod value="Monthly"/>
</PortfolioSettings>"""
    )
    return task


def _make_optimizer_task() -> BuildTask:
    """Create a BuildTask with Optimizer sections populated."""
    task = BuildTask()
    task.optimization = OptimizationConfig(
        raw_xml="""<Optimization>
  <Method value="Genetic"/>
  <ObjectiveFunction value="SharpeRatio"/>
  <WalkForwardCycles value="10"/>
</Optimization>"""
    )
    task.optimization_parameters = OptimizationParametersConfig(
        raw_xml="""<OptimizationParameters>
  <Parameter name="PopulationSize" min="100" max="100" step="1"/>
  <Parameter name="Generations" min="50" max="50" step="1"/>
  <Parameter name="CrossoverRate" min="0.8" max="0.8" step="0.1"/>
  <Parameter name="MutationRate" min="0.1" max="0.1" step="0.01"/>
</OptimizationParameters>"""
    )
    task.walk_forward = WalkForwardConfig(
        raw_xml="""<WalkForward>
  <Cycles value="5"/>
  <OOTRatio value="0.3"/>
</WalkForward>"""
    )
    task.databanks_section = DatabanksConfig(
        raw_xml="""<Databanks>
  <Databank index="1" name="EURUSD_H1" enabled="true"/>
  <Databank index="2" name="GBPUSD_H1" enabled="true"/>
</Databanks>"""
    )
    return task


def _make_retester_task() -> BuildTask:
    """Create a BuildTask with Retester sections populated."""
    task = BuildTask()
    task.rankings_section = RankingsConfig(
        raw_xml="""<Rankings>
  <MinTrades value="30"/>
  <ConfidenceLevel value="0.95"/>
</Rankings>"""
    )
    task.cross_checks_section = CrossChecksConfig(
        raw_xml="""<CrossChecks>
  <MonteCarlo enabled="true" runs="100" percentile="95"/>
  <WalkForward enabled="true" cycles="5"/>
</CrossChecks>"""
    )
    task.data = SettingsSection(
        name="Data",
        settings={"EURUSD_H1": "true", "GBPUSD_H1": "true"},
    )
    return task


class TestPortfolioCFXRoundTrip:
    """Round-trip tests for Portfolio CFX."""

    def test_write_read_portfolio_config_preserves_sections(self):
        task = _make_portfolio_task()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config, task_files={"Portfolio-Task1.xml": task})

        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            CfxWriter.write(archive, tmp.name)
            tmp_path = tmp.name

        try:
            re_read = CfxReader.read(tmp_path)
            re_task = re_read.config.task

            assert re_task.automatic_portfolio_builder is not None
            assert re_task.automatic_portfolio_builder.raw_xml is not None

            assert re_task.portfolio_settings is not None
            assert re_task.portfolio_settings.raw_xml is not None
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_write_read_portfolio_project_preserves_task_mapping(self):
        task = _make_portfolio_task()
        project = CfxProject(
            name="Portfolio Master Test",
            tasks={"Portfolio-Task1.xml": task},
            schema_version="144.2953",
        )
        archive = CfxArchive(config=project, task_files={"Portfolio-Task1.xml": task})

        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            CfxWriter.write(archive, tmp.name)
            tmp_path = tmp.name

        try:
            re_read = CfxReader.read(tmp_path)
            assert re_read.config.task_type == "project"
            assert "Portfolio-Task1.xml" in re_read.task_files

            re_task = re_read.task_files["Portfolio-Task1.xml"]
            assert re_task.automatic_portfolio_builder is not None
            assert re_task.portfolio_settings is not None
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_template_builder_portfolio_roundtrip(self):
        cfx_bytes = CfxTemplateBuilder.build_portfolio_cfx(
            strategies=["strat-1", "strat-2"],
            generations=30,
            population=100,
            fitness="SharpeRatio",
        )

        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(cfx_bytes)
            tmp_path = tmp.name

        try:
            archive = CfxReader.read(tmp_path)
            task = archive.task_files.get("Portfolio-Task1.xml") or archive.config.task
            assert task.automatic_portfolio_builder is not None
            assert task.portfolio_settings is not None
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestOptimizerCFXRoundTrip:
    """Round-trip tests for Optimizer CFX."""

    def test_write_read_optimizer_config_preserves_sections(self):
        task = _make_optimizer_task()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config, task_files={"Optimizer-Task1.xml": task})

        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            CfxWriter.write(archive, tmp.name)
            tmp_path = tmp.name

        try:
            re_read = CfxReader.read(tmp_path)
            re_task = re_read.config.task

            assert re_task.optimization is not None
            assert re_task.optimization.raw_xml is not None

            assert re_task.optimization_parameters is not None
            assert re_task.optimization_parameters.raw_xml is not None

            assert re_task.walk_forward is not None
            assert re_task.walk_forward.raw_xml is not None

            assert re_task.databanks_section is not None
            assert re_task.databanks_section.raw_xml is not None
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_template_builder_optimizer_roundtrip(self):
        cfx_bytes = CfxTemplateBuilder.build_optimizer_cfx(
            strategy_id="strat-1",
            method="BruteForce",
            objective="NetProfit",
            walkforward_cycles=10,
            databanks=["EURUSD_H1", "GBPUSD_H1"],
        )

        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(cfx_bytes)
            tmp_path = tmp.name

        try:
            archive = CfxReader.read(tmp_path)
            task = archive.task_files.get("Optimizer-Task1.xml") or archive.config.task
            assert task.optimization is not None
            assert task.optimization_parameters is not None
            assert task.walk_forward is not None
            assert task.databanks_section is not None
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestRetesterCFXRoundTrip:
    """Round-trip tests for Retester CFX."""

    def test_write_read_retester_config_preserves_sections(self):
        task = _make_retester_task()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config, task_files={"Retester-Task1.xml": task})

        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            CfxWriter.write(archive, tmp.name)
            tmp_path = tmp.name

        try:
            re_read = CfxReader.read(tmp_path)
            re_task = re_read.config.task

            assert re_task.rankings_section is not None
            assert re_task.rankings_section.raw_xml is not None

            assert re_task.cross_checks_section is not None
            assert re_task.cross_checks_section.raw_xml is not None

            assert re_task.data is not None
            assert re_task.data.settings is not None
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_template_builder_retester_roundtrip(self):
        cfx_bytes = CfxTemplateBuilder.build_retester_cfx(
            strategy_id="strat-1",
            databanks=["EURUSD_H1", "GBPUSD_H1"],
            mc_runs=200,
            mc_percentile=99,
            walkforward_cycles=10,
            min_trades=50,
            confidence_level=0.99,
        )

        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(cfx_bytes)
            tmp_path = tmp.name

        try:
            archive = CfxReader.read(tmp_path)
            task = archive.task_files.get("Retester-Task1.xml") or archive.config.task
            assert task.rankings_section is not None
            assert task.cross_checks_section is not None
            assert task.data is not None
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestPatcherPhase4Instructions:
    """Tests for Phase 4 patcher instructions."""

    def test_set_automatic_portfolio_builder_valid(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetAutomaticPortfolioBuilderInstruction

        instr = SetAutomaticPortfolioBuilderInstruction(
            generations=50,
            population=200,
            fitness="NetProfit",
            min_strategies=2,
            max_strategies=10,
            rebalancing="Monthly",
        )
        patcher.apply([instr])

        assert task.automatic_portfolio_builder is not None
        assert task.automatic_portfolio_builder.raw_xml is not None
        assert "Generations" in task.automatic_portfolio_builder.raw_xml
        assert "50" in task.automatic_portfolio_builder.raw_xml

    def test_set_automatic_portfolio_builder_invalid_generations(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetAutomaticPortfolioBuilderInstruction

        instr = SetAutomaticPortfolioBuilderInstruction(
            generations=0,
            population=100,
            fitness="NetProfit",
        )
        with pytest.raises(ValidationError, match="generations must be positive"):
            patcher.apply([instr])

    def test_set_automatic_portfolio_builder_invalid_max_strategies(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetAutomaticPortfolioBuilderInstruction

        instr = SetAutomaticPortfolioBuilderInstruction(
            generations=50,
            population=100,
            fitness="NetProfit",
            min_strategies=5,
            max_strategies=3,
        )
        with pytest.raises(ValidationError, match="max_strategies must be >= min_strategies"):
            patcher.apply([instr])

    def test_set_portfolio_settings(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetPortfolioSettingsInstruction

        instr = SetPortfolioSettingsInstruction(
            weight_constraints={"strat-1": "0.3", "strat-2": "0.7"},
        )
        patcher.apply([instr])

        assert task.portfolio_settings is not None
        assert "strat-1" in task.portfolio_settings.raw_xml
        assert "strat-2" in task.portfolio_settings.raw_xml

    def test_set_optimization_valid_methods(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetOptimizationInstruction

        for method in ["Genetic", "BruteForce", "Grid"]:
            task2 = BuildTask()
            config2 = CfxConfig(task=task2, schema_version="144.2953")
            archive2 = CfxArchive(config=config2)
            patcher2 = CfxPatcher(archive2)

            instr = SetOptimizationInstruction(
                method=method,
                objective_function="NetProfit",
                walkforward_cycles=5,
                walkforward_oot_ratio=0.3,
            )
            patcher2.apply([instr])
            assert task2.optimization is not None

    def test_set_optimization_invalid_method(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetOptimizationInstruction

        instr = SetOptimizationInstruction(
            method="InvalidMethod",
            objective_function="NetProfit",
            walkforward_cycles=5,
            walkforward_oot_ratio=0.3,
        )
        with pytest.raises(ValidationError, match="invalid method"):
            patcher.apply([instr])

    def test_set_optimization_invalid_oot_ratio(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetOptimizationInstruction

        instr = SetOptimizationInstruction(
            method="Genetic",
            objective_function="NetProfit",
            walkforward_cycles=5,
            walkforward_oot_ratio=1.5,
        )
        with pytest.raises(ValidationError, match="oot_ratio must be in"):
            patcher.apply([instr])

    def test_set_optimization_parameters(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetOptimizationParametersInstruction

        instr = SetOptimizationParametersInstruction(
            parameters={"param1": {"min": 1, "max": 10, "step": 1}},
        )
        patcher.apply([instr])

        assert task.optimization_parameters is not None
        assert "param1" in task.optimization_parameters.raw_xml
        assert 'min="1.0"' in task.optimization_parameters.raw_xml

    def test_set_optimization_parameters_invalid_range(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetOptimizationParametersInstruction

        instr = SetOptimizationParametersInstruction(
            parameters={"param1": {"min": 10, "max": 1, "step": 1}},
        )
        with pytest.raises(ValidationError, match="max must be >= min"):
            patcher.apply([instr])

    def test_set_walkforward(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetWalkForwardInstruction

        instr = SetWalkForwardInstruction(cycles=10, oot_ratio=0.3, anchored=True)
        patcher.apply([instr])

        assert task.walk_forward is not None
        assert "Cycles" in task.walk_forward.raw_xml
        assert "10" in task.walk_forward.raw_xml
        assert "Anchored" in task.walk_forward.raw_xml
        assert "true" in task.walk_forward.raw_xml

    def test_set_databanks_valid(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetDatabanksInstruction

        instr = SetDatabanksInstruction(databanks=["EURUSD_H1", "GBPUSD_H1"])
        patcher.apply([instr])

        assert task.databanks_section is not None
        assert "EURUSD_H1" in task.databanks_section.raw_xml
        assert "GBPUSD_H1" in task.databanks_section.raw_xml

    def test_set_databanks_invalid_format(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetDatabanksInstruction

        instr = SetDatabanksInstruction(databanks=["EURUSD_H1", "invalid-format"])
        with pytest.raises(ValidationError, match="invalid databank name"):
            patcher.apply([instr])

    def test_set_rankings(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetRankingsInstruction

        instr = SetRankingsInstruction(metrics=["NetProfit", "SharpeRatio"], min_trades=50)
        patcher.apply([instr])

        assert task.rankings_section is not None
        assert "NetProfit" in task.rankings_section.raw_xml
        assert "SharpeRatio" in task.rankings_section.raw_xml
        assert "MinTrades" in task.rankings_section.raw_xml
        assert "50" in task.rankings_section.raw_xml

    def test_set_crosschecks(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetCrossChecksInstruction

        instr = SetCrossChecksInstruction(
            mc_enabled=True,
            wf_enabled=True,
            mc_runs=100,
            mc_percentile=95,
            wf_cycles=5,
            confidence_level=0.95,
        )
        patcher.apply([instr])

        assert task.cross_checks_section is not None
        assert "MonteCarlo" in task.cross_checks_section.raw_xml
        assert "enabled=\"true\"" in task.cross_checks_section.raw_xml
        assert "WalkForward" in task.cross_checks_section.raw_xml

    def test_set_crosschecks_invalid_confidence(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetCrossChecksInstruction

        instr = SetCrossChecksInstruction(
            mc_enabled=False,
            wf_enabled=False,
            confidence_level=0.999,
        )
        with pytest.raises(ValidationError, match="confidence_level must be in"):
            patcher.apply([instr])

    def test_set_retester_data(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetRetesterDataInstruction

        instr = SetRetesterDataInstruction(
            databanks=["EURUSD_H1"],
            monte_carlo_runs=100,
            walkforward_cycles=5,
            confidence_level=0.95,
            min_trades=30,
            mc_percentile=95,
        )
        patcher.apply([instr])

        assert task.retester_data is not None
        assert "MonteCarloRuns" in task.retester_data.raw_xml
        assert "WalkforwardCycles" in task.retester_data.raw_xml
        assert "EURUSD_H1" in task.retester_data.raw_xml

    def test_set_retester_data_invalid_databank(self):
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import SetRetesterDataInstruction

        instr = SetRetesterDataInstruction(databanks=["invalid"])
        with pytest.raises(ValidationError, match="invalid databank name"):
            patcher.apply([instr])

    def test_validate_all_then_apply_atomic(self):
        """Validation failure should roll back all instructions."""
        task = BuildTask()
        config = CfxConfig(task=task, schema_version="144.2953")
        archive = CfxArchive(config=config)
        patcher = CfxPatcher(archive)

        from quantlab.cfx.models import (
            SetMarketInstruction,
            SetAutomaticPortfolioBuilderInstruction,
        )

        instructions = [
            SetMarketInstruction(symbol="EURUSD"),
            SetAutomaticPortfolioBuilderInstruction(
                generations=0,  # Invalid!
                population=100,
                fitness="NetProfit",
            ),
        ]

        with pytest.raises(ValidationError):
            patcher.apply(instructions)

        # Verify rollback: no mutation should have occurred
        assert task.data is None