"""Tests for CfxTemplateBuilder — Portfolio/Optimizer/Retester CFX output validation."""

import base64
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

import pytest

from quantlab.cfx.reader import CfxReader
from quantlab.phase4.templates import CfxTemplateBuilder


class TestPortfolioCFX:
    """Tests for Portfolio Master CFX generation."""

    def test_build_portfolio_cfx_returns_bytes(self):
        result = CfxTemplateBuilder.build_portfolio_cfx(
            strategies=["strat-1", "strat-2"],
            generations=50,
            population=200,
            fitness="NetProfit",
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_portfolio_cfx_is_valid_zip(self):
        cfx_bytes = CfxTemplateBuilder.build_portfolio_cfx(["strat-1"])

        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            names = zf.namelist()
            assert "config.xml" in names
            assert "Portfolio-Task1.xml" in names

    def test_portfolio_cfx_has_correct_schema_version(self):
        cfx_bytes = CfxTemplateBuilder.build_portfolio_cfx(["strat-1"])

        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            config_xml = zf.read("config.xml").decode("utf-8")
            root = ElementTree.fromstring(config_xml)
            assert root.tag == "Project"
            assert root.get("version") == "144.2953"

    def test_portfolio_cfx_has_automatic_portfolio_builder_section(self):
        cfx_bytes = CfxTemplateBuilder.build_portfolio_cfx(
            strategies=["strat-1"],
            generations=50,
            population=200,
            fitness="SharpeRatio",
        )

        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            task_xml = zf.read("Portfolio-Task1.xml").decode("utf-8")
            root = ElementTree.fromstring(task_xml)
            assert root.tag == "Settings"

            # Find AutomaticPortfolioBuilder section
            apb = root.find("AutomaticPortfolioBuilder")
            assert apb is not None
            assert apb.find("Generations").get("value") == "50"
            assert apb.find("PopulationSize").get("value") == "200"
            assert apb.find("FitnessFunction").get("value") == "SharpeRatio"

    def test_portfolio_cfx_has_portfolio_settings_section(self):
        cfx_bytes = CfxTemplateBuilder.build_portfolio_cfx(
            strategies=["strat-1"],
            min_strategies=2,
            max_strategies=10,
            rebalance="Quarterly",
        )

        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            task_xml = zf.read("Portfolio-Task1.xml").decode("utf-8")
            root = ElementTree.fromstring(task_xml)

            ps = root.find("PortfolioSettings")
            assert ps is not None
            assert ps.find("MinStrategies").get("value") == "2"
            assert ps.find("MaxStrategies").get("value") == "10"
            assert ps.find("RebalancingPeriod").get("value") == "Quarterly"

    def test_portfolio_cfx_readable_by_cfx_reader(self):
        cfx_bytes = CfxTemplateBuilder.build_portfolio_cfx(["strat-1", "strat-2"])

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(cfx_bytes)
            tmp_path = tmp.name

        try:
            archive = CfxReader.read(tmp_path)
            assert archive.config.task_type == "project"
            assert "Portfolio-Task1.xml" in archive.task_files
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestOptimizerCFX:
    """Tests for Optimizer CFX generation."""

    def test_build_optimizer_cfx_returns_bytes(self):
        result = CfxTemplateBuilder.build_optimizer_cfx(
            strategy_id="strat-123",
            method="Genetic",
            objective="SharpeRatio",
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_optimizer_cfx_is_valid_zip(self):
        cfx_bytes = CfxTemplateBuilder.build_optimizer_cfx("strat-1")

        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            names = zf.namelist()
            assert "config.xml" in names
            assert "Optimizer-Task1.xml" in names

    def test_optimizer_cfx_has_optimization_section(self):
        cfx_bytes = CfxTemplateBuilder.build_optimizer_cfx(
            strategy_id="strat-1",
            method="BruteForce",
            objective="NetProfit",
            walkforward_cycles=10,
        )

        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            task_xml = zf.read("Optimizer-Task1.xml").decode("utf-8")
            root = ElementTree.fromstring(task_xml)

            opt = root.find("Optimization")
            assert opt is not None
            assert opt.find("Method").get("value") == "BruteForce"
            assert opt.find("ObjectiveFunction").get("value") == "NetProfit"
            assert opt.find("WalkforwardCycles").get("value") == "10"

    def test_optimizer_cfx_has_parameters_section(self):
        cfx_bytes = CfxTemplateBuilder.build_optimizer_cfx(
            strategy_id="strat-1",
            population=100,
            generations=50,
            crossover=0.8,
            mutation=0.1,
        )

        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            task_xml = zf.read("Optimizer-Task1.xml").decode("utf-8")
            root = ElementTree.fromstring(task_xml)

            params = root.find("OptimizationParameters")
            assert params is not None
            param_list = params.findall("Parameter")
            param_map = {p.get("name"): p for p in param_list}
            assert param_map["PopulationSize"].get("min") == "100"
            assert param_map["Generations"].get("min") == "50"
            assert param_map["CrossoverRate"].get("min") == "0.8"
            assert param_map["MutationRate"].get("min") == "0.1"

    def test_optimizer_cfx_has_walkforward_section(self):
        cfx_bytes = CfxTemplateBuilder.build_optimizer_cfx(
            strategy_id="strat-1",
            walkforward_cycles=5,
        )

        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            task_xml = zf.read("Optimizer-Task1.xml").decode("utf-8")
            root = ElementTree.fromstring(task_xml)

            wf = root.find("WalkForward")
            assert wf is not None
            assert wf.find("Cycles").get("value") == "5"
            assert wf.find("OOTRatio").get("value") == "0.3"

    def test_optimizer_cfx_has_databanks_section(self):
        cfx_bytes = CfxTemplateBuilder.build_optimizer_cfx(
            strategy_id="strat-1",
            databanks=["EURUSD_H1", "GBPUSD_H1"],
        )

        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            task_xml = zf.read("Optimizer-Task1.xml").decode("utf-8")
            root = ElementTree.fromstring(task_xml)

            dbs = root.find("Databanks")
            assert dbs is not None
            eur = dbs.find("Databank[@name='EURUSD_H1']")
            assert eur is not None
            assert eur.get("enabled") == "true"
            gbp = dbs.find("Databank[@name='GBPUSD_H1']")
            assert gbp is not None

    def test_optimizer_cfx_readable_by_cfx_reader(self):
        cfx_bytes = CfxTemplateBuilder.build_optimizer_cfx("strat-1")

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(cfx_bytes)
            tmp_path = tmp.name

        try:
            archive = CfxReader.read(tmp_path)
            assert archive.config.task_type == "config"
            assert "Optimizer-Task1.xml" in archive.task_files
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestRetesterCFX:
    """Tests for Retester CFX generation."""

    def test_build_retester_cfx_returns_bytes(self):
        result = CfxTemplateBuilder.build_retester_cfx(
            strategy_id="strat-123",
            databanks=["EURUSD_H1"],
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_retester_cfx_is_valid_zip(self):
        cfx_bytes = CfxTemplateBuilder.build_retester_cfx("strat-1", databanks=["EURUSD_H1"])

        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            names = zf.namelist()
            assert "config.xml" in names
            assert "Retester-Task1.xml" in names

    def test_retester_cfx_has_rankings_section(self):
        cfx_bytes = CfxTemplateBuilder.build_retester_cfx(
            strategy_id="strat-1",
            databanks=["EURUSD_H1"],
            min_trades=30,
            confidence_level=0.95,
        )

        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            task_xml = zf.read("Retester-Task1.xml").decode("utf-8")
            root = ElementTree.fromstring(task_xml)

            rankings = root.find("Rankings")
            assert rankings is not None
            assert rankings.find("MinTrades").get("value") == "30"
            assert rankings.find("ConfidenceLevel").get("value") == "0.95"

    def test_retester_cfx_has_crosschecks_section(self):
        cfx_bytes = CfxTemplateBuilder.build_retester_cfx(
            strategy_id="strat-1",
            databanks=["EURUSD_H1"],
            mc_runs=100,
            mc_percentile=95,
            walkforward_cycles=5,
        )

        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            task_xml = zf.read("Retester-Task1.xml").decode("utf-8")
            root = ElementTree.fromstring(task_xml)

            cc = root.find("CrossChecks")
            assert cc is not None
            mc = cc.find("MonteCarlo")
            assert mc is not None
            assert mc.get("enabled") == "true"
            assert mc.get("runs") == "100"
            assert mc.get("percentile") == "95"
            wf = cc.find("WalkForward")
            assert wf is not None
            assert wf.get("enabled") == "true"
            assert wf.get("cycles") == "5"

    def test_retester_cfx_has_data_section(self):
        cfx_bytes = CfxTemplateBuilder.build_retester_cfx(
            strategy_id="strat-1",
            databanks=["EURUSD_H1", "GBPUSD_H1"],
        )

        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            task_xml = zf.read("Retester-Task1.xml").decode("utf-8")
            root = ElementTree.fromstring(task_xml)

            data = root.find("Data")
            assert data is not None
            assert data.find("Setting[@key='EURUSD_H1']").get("value") == "true"
            assert data.find("Setting[@key='GBPUSD_H1']").get("value") == "true"

    def test_retester_cfx_readable_by_cfx_reader(self):
        cfx_bytes = CfxTemplateBuilder.build_retester_cfx("strat-1", databanks=["EURUSD_H1"])

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(cfx_bytes)
            tmp_path = tmp.name

        try:
            archive = CfxReader.read(tmp_path)
            assert archive.config.task_type == "config"
            assert "Retester-Task1.xml" in archive.task_files
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestDryRunMethods:
    """Tests for dry-run convenience methods."""

    def test_dry_run_portfolio_returns_json(self):
        result = CfxTemplateBuilder.dry_run_portfolio_cfx(
            strategies=["strat-1"],
            generations=10,
            population=50,
        )
        assert isinstance(result, str)
        assert '"type": "portfolio"' in result

    def test_dry_run_optimizer_returns_json(self):
        result = CfxTemplateBuilder.dry_run_optimizer_cfx(
            strategy_id="strat-1",
            method="Genetic",
        )
        assert isinstance(result, str)
        assert '"type": "optimizer"' in result

    def test_dry_run_retester_returns_json(self):
        result = CfxTemplateBuilder.dry_run_retester_cfx(
            strategy_id="strat-1",
            databanks=["EURUSD_H1"],
        )
        assert isinstance(result, str)
        assert '"type": "retester"' in result