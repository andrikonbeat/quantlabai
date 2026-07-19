"""Tests for Phase 4 translator extensions — Portfolio/Optimizer/Retester CFX generation."""

import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

import pytest
import tempfile

from quantlab.cfx import CfxReader, CfxWriter
from quantlab.translate import (
    CfxArchive,
    generate_portfolio_cfx_archive,
    generate_optimizer_cfx_archive,
    generate_retester_cfx_archive,
)
from quantlab.tools.exceptions import TranslationError


# ── Helpers ────────────────────────────────────────────────────────────


def _assert_valid_cfx(archive, expected_task_file: str) -> bytes:
    """Write archive to bytes and assert it's a valid CFX (ZIP with config.xml + task)."""
    with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
        CfxWriter.write(archive, tmp.name)
        tmp_path = Path(tmp.name)

    try:
        with zipfile.ZipFile(tmp_path, "r") as zf:
            names = zf.namelist()
            assert "config.xml" in names, f"Missing config.xml in {names}"
            assert expected_task_file in names, f"Missing {expected_task_file} in {names}"
            task_xml = zf.read(expected_task_file).decode("utf-8")
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)


def _assert_section(archive_bytes: bytes, task_file: str, section_tag: str) -> ElementTree.Element:
    """Parse a CFX archive and return an XML section by tag."""
    with zipfile.ZipFile(BytesIO(archive_bytes), "r") as zf:
        task_xml = zf.read(task_file).decode("utf-8")
    root = ElementTree.fromstring(task_xml)
    section = root.find(section_tag)
    assert section is not None, f"Section <{section_tag}> not found in {task_file}"
    return section


# ── Portfolio Generator Tests ──────────────────────────────────────────


class TestGeneratePortfolioCFXArchive:
    """Tests for ``generate_portfolio_cfx_archive()``."""

    def test_returns_cfx_archive(self):
        archive = generate_portfolio_cfx_archive(["strat-1", "strat-2"])
        assert archive is not None
        assert archive.config.name == "Portfolio Master"
        assert "Portfolio-Task1.xml" in archive.task_files

    def test_writes_valid_cfx(self):
        archive = generate_portfolio_cfx_archive(["strat-1"])
        _assert_valid_cfx(archive, "Portfolio-Task1.xml")

    def test_readable_by_cfx_reader(self):
        archive = generate_portfolio_cfx_archive(["strat-1"], generations=50, population=200)
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            CfxWriter.write(archive, tmp.name)
            tmp_path = tmp.name
        try:
            re_read = CfxReader.read(tmp_path)
            assert re_read.config is not None
            re_task = next(iter(re_read.task_files.values()))
            assert re_task.automatic_portfolio_builder is not None
            assert re_task.portfolio_settings is not None
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_has_automatic_portfolio_builder_section(self):
        archive = generate_portfolio_cfx_archive(
            ["strat-1"],
            generations=50,
            population=200,
            fitness="SharpeRatio",
        )
        cfx_bytes = _assert_valid_cfx(archive, "Portfolio-Task1.xml")
        section = _assert_section(cfx_bytes, "Portfolio-Task1.xml", "AutomaticPortfolioBuilder")
        assert section.find("Generations").get("value") == "50"
        assert section.find("PopulationSize").get("value") == "200"
        assert section.find("FitnessFunction").get("value") == "SharpeRatio"

    def test_has_portfolio_settings_section(self):
        archive = generate_portfolio_cfx_archive(
            ["strat-1"],
            min_strategies=2,
            max_strategies=10,
            rebalance="Quarterly",
        )
        cfx_bytes = _assert_valid_cfx(archive, "Portfolio-Task1.xml")
        section = _assert_section(cfx_bytes, "Portfolio-Task1.xml", "PortfolioSettings")
        assert section.find("MinStrategies").get("value") == "2"
        assert section.find("MaxStrategies").get("value") == "10"
        assert section.find("RebalancingPeriod").get("value") == "Quarterly"

    def test_has_project_config(self):
        archive = generate_portfolio_cfx_archive(["strat-1"])
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            CfxWriter.write(archive, tmp.name)
            tmp_path = tmp.name
        try:
            with zipfile.ZipFile(tmp_path, "r") as zf:
                config_xml = zf.read("config.xml").decode("utf-8")
            root = ElementTree.fromstring(config_xml)
            assert root.tag == "Project"
            assert root.get("version") == "144.2953"
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_rejects_empty_strategies(self):
        with pytest.raises(TranslationError, match="At least one strategy"):
            generate_portfolio_cfx_archive([])

    def test_rejects_invalid_generations(self):
        with pytest.raises(TranslationError, match="generations must be positive"):
            generate_portfolio_cfx_archive(["s1"], generations=0)

    def test_rejects_invalid_population(self):
        with pytest.raises(TranslationError, match="population must be positive"):
            generate_portfolio_cfx_archive(["s1"], population=0)

    def test_rejects_empty_fitness(self):
        with pytest.raises(TranslationError, match="fitness must not be empty"):
            generate_portfolio_cfx_archive(["s1"], fitness="")

    def test_rejects_min_strategies_zero(self):
        with pytest.raises(TranslationError, match="min_strategies must be positive"):
            generate_portfolio_cfx_archive(["s1"], min_strategies=0)

    def test_rejects_max_less_than_min(self):
        with pytest.raises(TranslationError, match="max_strategies must be >= min_strategies"):
            generate_portfolio_cfx_archive(["s1"], min_strategies=5, max_strategies=3)


# ── Optimizer Generator Tests ──────────────────────────────────────────


class TestGenerateOptimizerCFXArchive:
    """Tests for ``generate_optimizer_cfx_archive()``."""

    def test_returns_cfx_archive(self):
        archive = generate_optimizer_cfx_archive("strat-1")
        assert archive is not None
        assert "Optimizer-Task1.xml" in archive.task_files

    def test_writes_valid_cfx(self):
        archive = generate_optimizer_cfx_archive("strat-1")
        _assert_valid_cfx(archive, "Optimizer-Task1.xml")

    def test_readable_by_cfx_reader(self):
        archive = generate_optimizer_cfx_archive(
            "strat-1",
            method="Genetic",
            objective="SharpeRatio",
            walkforward_cycles=10,
            population=100,
            generations=50,
            databanks=["EURUSD_H1"],
        )
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            CfxWriter.write(archive, tmp.name)
            tmp_path = tmp.name
        try:
            re_read = CfxReader.read(tmp_path)
            re_task = re_read.config.task
            assert re_task.optimization is not None
            assert re_task.optimization_parameters is not None
            assert re_task.walk_forward is not None
            assert re_task.databanks_section is not None
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_has_optimization_section(self):
        archive = generate_optimizer_cfx_archive(
            "strat-1",
            method="BruteForce",
            objective="NetProfit",
            walkforward_cycles=15,
        )
        cfx_bytes = _assert_valid_cfx(archive, "Optimizer-Task1.xml")
        section = _assert_section(cfx_bytes, "Optimizer-Task1.xml", "Optimization")
        assert section.find("Method").get("value") == "BruteForce"
        assert section.find("ObjectiveFunction").get("value") == "NetProfit"
        assert section.find("WalkforwardCycles").get("value") == "15"

    def test_has_optimization_parameters_section(self):
        archive = generate_optimizer_cfx_archive(
            "strat-1",
            population=80,
            generations=40,
            crossover=0.9,
            mutation=0.05,
        )
        cfx_bytes = _assert_valid_cfx(archive, "Optimizer-Task1.xml")
        section = _assert_section(cfx_bytes, "Optimizer-Task1.xml", "OptimizationParameters")
        params = {p.get("name"): p for p in section.findall("Parameter")}
        assert params["PopulationSize"].get("min") == "80"
        assert params["Generations"].get("max") == "40"
        assert params["CrossoverRate"].get("step") == "0.1"

    def test_has_walk_forward_section(self):
        archive = generate_optimizer_cfx_archive(
            "strat-1",
            walkforward_cycles=8,
            walkforward_oot_ratio=0.25,
        )
        cfx_bytes = _assert_valid_cfx(archive, "Optimizer-Task1.xml")
        section = _assert_section(cfx_bytes, "Optimizer-Task1.xml", "WalkForward")
        assert section.find("Cycles").get("value") == "8"
        assert section.find("OOTRatio").get("value") == "0.25"

    def test_databanks_section_when_provided(self):
        archive = generate_optimizer_cfx_archive(
            "strat-1",
            databanks=["EURUSD_H1", "GBPUSD_H1"],
        )
        cfx_bytes = _assert_valid_cfx(archive, "Optimizer-Task1.xml")
        section = _assert_section(cfx_bytes, "Optimizer-Task1.xml", "Databanks")
        banks = section.findall("Databank")
        assert len(banks) == 2
        assert banks[0].get("name") == "EURUSD_H1"
        assert banks[1].get("name") == "GBPUSD_H1"

    def test_no_databanks_section_when_not_provided(self):
        archive = generate_optimizer_cfx_archive("strat-1")
        cfx_bytes = _assert_valid_cfx(archive, "Optimizer-Task1.xml")
        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            task_xml = zf.read("Optimizer-Task1.xml").decode("utf-8")
        root = ElementTree.fromstring(task_xml)
        assert root.find("Databanks") is None

    def test_rejects_empty_strategy_id(self):
        with pytest.raises(TranslationError, match="strategy_id"):
            generate_optimizer_cfx_archive("")

    def test_rejects_invalid_method(self):
        with pytest.raises(TranslationError, match="Invalid method"):
            generate_optimizer_cfx_archive("s1", method="Unknown")

    def test_rejects_empty_objective(self):
        with pytest.raises(TranslationError, match="objective must not be empty"):
            generate_optimizer_cfx_archive("s1", objective="")

    def test_rejects_non_positive_walkforward_cycles(self):
        with pytest.raises(TranslationError, match="walkforward_cycles must be positive"):
            generate_optimizer_cfx_archive("s1", walkforward_cycles=0)

    def test_rejects_invalid_oot_ratio(self):
        with pytest.raises(TranslationError, match="walkforward_oot_ratio"):
            generate_optimizer_cfx_archive("s1", walkforward_oot_ratio=0)
        with pytest.raises(TranslationError, match="walkforward_oot_ratio"):
            generate_optimizer_cfx_archive("s1", walkforward_oot_ratio=1.5)

    def test_rejects_non_positive_population(self):
        with pytest.raises(TranslationError, match="population must be positive"):
            generate_optimizer_cfx_archive("s1", population=0)

    def test_rejects_non_positive_generations(self):
        with pytest.raises(TranslationError, match="generations must be positive"):
            generate_optimizer_cfx_archive("s1", generations=0)

    def test_rejects_out_of_range_crossover(self):
        with pytest.raises(TranslationError, match="crossover must be in"):
            generate_optimizer_cfx_archive("s1", crossover=0)
        with pytest.raises(TranslationError, match="crossover must be in"):
            generate_optimizer_cfx_archive("s1", crossover=1.5)

    def test_rejects_out_of_range_mutation(self):
        with pytest.raises(TranslationError, match="mutation must be in"):
            generate_optimizer_cfx_archive("s1", mutation=0)
        with pytest.raises(TranslationError, match="mutation must be in"):
            generate_optimizer_cfx_archive("s1", mutation=1.5)


# ── Retester Generator Tests ───────────────────────────────────────────


class TestGenerateRetesterCFXArchive:
    """Tests for ``generate_retester_cfx_archive()``."""

    def test_returns_cfx_archive(self):
        archive = generate_retester_cfx_archive("strat-1", databanks=["EURUSD_H1"])
        assert archive is not None
        assert "Retester-Task1.xml" in archive.task_files

    def test_writes_valid_cfx(self):
        archive = generate_retester_cfx_archive("strat-1", databanks=["EURUSD_H1"])
        _assert_valid_cfx(archive, "Retester-Task1.xml")

    def test_readable_by_cfx_reader(self):
        archive = generate_retester_cfx_archive(
            "strat-1",
            databanks=["EURUSD_H1", "GBPUSD_H1"],
            mc_runs=200,
            mc_percentile=99,
            walkforward_cycles=10,
            min_trades=50,
            confidence_level=0.98,
        )
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            CfxWriter.write(archive, tmp.name)
            tmp_path = tmp.name
        try:
            re_read = CfxReader.read(tmp_path)
            re_task = re_read.config.task
            assert re_task.rankings_section is not None
            assert re_task.cross_checks_section is not None
            assert re_task.retester_data is not None
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_has_rankings_section(self):
        archive = generate_retester_cfx_archive(
            "strat-1",
            databanks=["EURUSD_H1"],
            min_trades=50,
            confidence_level=0.9,
        )
        cfx_bytes = _assert_valid_cfx(archive, "Retester-Task1.xml")
        section = _assert_section(cfx_bytes, "Retester-Task1.xml", "Rankings")
        assert section.find("MinTrades").get("value") == "50"
        assert float(section.find("ConfidenceLevel").get("value")) == pytest.approx(0.9)

    def test_has_cross_checks_section(self):
        archive = generate_retester_cfx_archive(
            "strat-1",
            databanks=["EURUSD_H1"],
            mc_runs=200,
            mc_percentile=99,
            walkforward_cycles=10,
        )
        cfx_bytes = _assert_valid_cfx(archive, "Retester-Task1.xml")
        section = _assert_section(cfx_bytes, "Retester-Task1.xml", "CrossChecks")
        mc = section.find("MonteCarlo")
        assert mc is not None
        assert mc.get("runs") == "200"
        assert mc.get("percentile") == "99"
        wf = section.find("WalkForward")
        assert wf is not None
        assert wf.get("cycles") == "10"

    def test_has_data_section(self):
        archive = generate_retester_cfx_archive(
            "strat-1",
            databanks=["EURUSD_H1", "GBPUSD_H1"],
        )
        cfx_bytes = _assert_valid_cfx(archive, "Retester-Task1.xml")
        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            task_xml = zf.read("Retester-Task1.xml").decode("utf-8")
        assert "<Data>" in task_xml

    def test_has_retester_data_section(self):
        archive = generate_retester_cfx_archive(
            "strat-1",
            databanks=["EURUSD_H1"],
            mc_runs=150,
            mc_percentile=95,
            walkforward_cycles=8,
        )
        cfx_bytes = _assert_valid_cfx(archive, "Retester-Task1.xml")
        section = _assert_section(cfx_bytes, "Retester-Task1.xml", "RetesterData")
        assert section.find("MonteCarloRuns").get("value") == "150"
        assert section.find("WalkforwardCycles").get("value") == "8"
        assert section.find("MonteCarloPercentile").get("value") == "95"
        banks = section.find(".//Databanks")
        assert banks is not None
        assert banks.find("Databank").get("name") == "EURUSD_H1"

    def test_rejects_empty_strategy_id(self):
        with pytest.raises(TranslationError, match="strategy_id"):
            generate_retester_cfx_archive("", databanks=["EURUSD_H1"])

    def test_rejects_empty_databanks(self):
        with pytest.raises(TranslationError, match="databanks must not be empty"):
            generate_retester_cfx_archive("s1", databanks=[])

    def test_rejects_non_positive_mc_runs(self):
        with pytest.raises(TranslationError, match="mc_runs must be positive"):
            generate_retester_cfx_archive("s1", databanks=["EURUSD_H1"], mc_runs=0)

    def test_rejects_invalid_mc_percentile(self):
        with pytest.raises(TranslationError, match="mc_percentile"):
            generate_retester_cfx_archive("s1", databanks=["EURUSD_H1"], mc_percentile=0)
        with pytest.raises(TranslationError, match="mc_percentile"):
            generate_retester_cfx_archive("s1", databanks=["EURUSD_H1"], mc_percentile=100)

    def test_rejects_non_positive_walkforward_cycles(self):
        with pytest.raises(TranslationError, match="walkforward_cycles must be positive"):
            generate_retester_cfx_archive("s1", databanks=["EURUSD_H1"], walkforward_cycles=0)

    def test_rejects_non_positive_min_trades(self):
        with pytest.raises(TranslationError, match="min_trades must be positive"):
            generate_retester_cfx_archive("s1", databanks=["EURUSD_H1"], min_trades=0)

    def test_rejects_invalid_confidence_level(self):
        with pytest.raises(TranslationError, match="confidence_level"):
            generate_retester_cfx_archive("s1", databanks=["EURUSD_H1"], confidence_level=0.5)
        with pytest.raises(TranslationError, match="confidence_level"):
            generate_retester_cfx_archive("s1", databanks=["EURUSD_H1"], confidence_level=0.99)


# ── CfxArchiveFactory Integration Tests ────────────────────────────────


class TestCfxArchiveFactoryPhase4:
    """Tests for ``CfxArchiveFactory`` Phase 4 methods."""

    def test_from_portfolio_dry_run(self):
        result = CfxArchive.from_portfolio(["strat-1"], dry_run=True)
        assert result.xml_content is not None
        assert result.path is not None
        assert result.path.suffix == ".json"
        assert "portfolio" in result.path.name

    def test_from_portfolio_writes_cfx(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = CfxArchive.from_portfolio(["strat-1", "strat-2"], output_dir=tmp)
            assert result.path is not None
            assert result.path.suffix == ".cfx"
            assert result.path.exists()
            # Verify it's a valid CFX
            with zipfile.ZipFile(result.path, "r") as zf:
                assert "config.xml" in zf.namelist()

    def test_from_optimizer_dry_run(self):
        result = CfxArchive.from_optimizer("strat-1", dry_run=True)
        assert result.xml_content is not None
        assert result.path is not None
        assert "optimizer" in result.path.name

    def test_from_optimizer_writes_cfx(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = CfxArchive.from_optimizer(
                "strat-1",
                databanks=["EURUSD_H1"],
                output_dir=tmp,
            )
            assert result.path is not None
            assert result.path.suffix == ".cfx"
            assert result.path.exists()
            with zipfile.ZipFile(result.path, "r") as zf:
                assert "Optimizer-Task1.xml" in zf.namelist()

    def test_from_retester_dry_run(self):
        result = CfxArchive.from_retester("strat-1", databanks=["EURUSD_H1"], dry_run=True)
        assert result.xml_content is not None
        assert result.path is not None
        assert "retester" in result.path.name

    def test_from_retester_writes_cfx(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = CfxArchive.from_retester(
                "strat-1",
                databanks=["EURUSD_H1", "GBPUSD_H1"],
                output_dir=tmp,
            )
            assert result.path is not None
            assert result.path.suffix == ".cfx"
            assert result.path.exists()
            with zipfile.ZipFile(result.path, "r") as zf:
                assert "Retester-Task1.xml" in zf.namelist()
