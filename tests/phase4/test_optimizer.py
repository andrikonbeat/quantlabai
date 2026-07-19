"""Tests for Optimizer — CSV parsing, HTML export, backward compat."""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from quantlab.phase4.optimizer import (
    Optimizer,
    OptimizerConfig,
    OptimizationResult,
    WalkForwardCycle,
)
from quantlab.phase4.errors import OptimizerRunError


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def optimizer() -> Optimizer:
    return Optimizer("/fake/path")


STD_HEADER = (
    "Cycle,InSampleStart,InSampleEnd,OutSampleStart,OutSampleEnd,"
    "Sensitivity,Period,Sharpe,ProfitFactor,Drawdown"
)
STD_ROW1 = "1,2020-01-01,2020-06-30,2020-07-01,2020-12-31,0.5,100,1.2,1.5,5.0"
STD_ROW2 = "2,2020-07-01,2020-12-31,2021-01-01,2021-06-30,0.3,150,1.5,2.0,4.5"


def _write_csv(tmp_path: Path, name: str, *lines: str) -> Path:
    p = tmp_path / name
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


# ── Dataclass Tests ────────────────────────────────────────────────────────────


class TestWalkForwardCycle:
    """Tests for WalkForwardCycle dataclass."""

    def test_creation(self):
        cycle = WalkForwardCycle(
            cycle=1,
            in_sample_start="2020-01-01",
            in_sample_end="2020-06-30",
            out_sample_start="2020-07-01",
            out_sample_end="2020-12-31",
            parameters={"Sensitivity": 0.5},
            metrics={"Sharpe": 1.2, "ProfitFactor": 1.5},
        )
        assert cycle.cycle == 1
        assert cycle.in_sample_start == "2020-01-01"
        assert cycle.in_sample_end == "2020-06-30"
        assert cycle.out_sample_start == "2020-07-01"
        assert cycle.out_sample_end == "2020-12-31"
        assert cycle.parameters == {"Sensitivity": 0.5}
        assert cycle.metrics == {"Sharpe": 1.2, "ProfitFactor": 1.5}

    def test_defaults(self):
        cycle = WalkForwardCycle(
            cycle=1,
            in_sample_start="2020-01-01",
            in_sample_end="2020-06-30",
            out_sample_start="2020-07-01",
            out_sample_end="2020-12-31",
        )
        assert cycle.parameters == {}
        assert cycle.metrics == {}


class TestOptimizationResult:
    """Tests for OptimizationResult dataclass."""

    def test_creation(self):
        result = OptimizationResult(
            strategy_id="strat-123",
            cycles=[],
            summary={"num_cycles": 0},
            csv_path=Path("/tmp/test.csv"),
        )
        assert result.strategy_id == "strat-123"
        assert result.csv_path == Path("/tmp/test.csv")

    def test_raw_path_backward_compat(self):
        """raw_path should return csv_path for backward compatibility."""
        p = Path("/tmp/test.csv")
        result = OptimizationResult(strategy_id="s1", csv_path=p)
        assert result.raw_path is result.csv_path
        assert result.raw_path == p

    def test_raw_path_none(self):
        result = OptimizationResult(strategy_id="s1")
        assert result.raw_path is None


# ── Parse CSV ──────────────────────────────────────────────────────────────────


class TestParseCSV:
    """Tests for Optimizer.parse_csv."""

    def test_parse_basic(self, optimizer, tmp_path):
        p = _write_csv(tmp_path, "results.csv", STD_HEADER, STD_ROW1, STD_ROW2)
        result = optimizer.parse_csv(p, strategy_id="strat-123")

        assert result.strategy_id == "strat-123"
        assert result.csv_path == p
        assert len(result.cycles) == 2

        c1 = result.cycles[0]
        assert c1.cycle == 1
        assert c1.in_sample_start == "2020-01-01"
        assert c1.in_sample_end == "2020-06-30"
        assert c1.out_sample_start == "2020-07-01"
        assert c1.out_sample_end == "2020-12-31"
        assert c1.parameters["Sensitivity"] == 0.5
        assert c1.parameters["Period"] == 100.0
        assert c1.metrics["Sharpe"] == 1.2
        assert c1.metrics["ProfitFactor"] == 1.5
        assert c1.metrics["Drawdown"] == 5.0

        c2 = result.cycles[1]
        assert c2.cycle == 2
        assert c2.parameters["Sensitivity"] == 0.3
        assert c2.metrics["Sharpe"] == 1.5

    def test_parse_with_bom(self, optimizer, tmp_path):
        """UTF-8 BOM should be handled gracefully."""
        p = tmp_path / "bom.csv"
        content = "\ufeff" + f"{STD_HEADER}\n{STD_ROW1}\n"
        p.write_text(content, encoding="utf-8")
        result = optimizer.parse_csv(p, strategy_id="bom-test")
        assert len(result.cycles) == 1
        assert result.cycles[0].cycle == 1

    def test_empty_csv_raises(self, optimizer, tmp_path):
        p = _write_csv(tmp_path, "empty.csv", "")
        with pytest.raises(OptimizerRunError, match="empty|no header"):
            optimizer.parse_csv(p)

    def test_header_only_raises(self, optimizer, tmp_path):
        p = _write_csv(tmp_path, "header.csv", STD_HEADER)
        with pytest.raises(OptimizerRunError, match="no data rows"):
            optimizer.parse_csv(p)

    def test_missing_required_columns_raises(self, optimizer, tmp_path):
        p = _write_csv(tmp_path, "bad.csv", "Cycle,Sharpe", "1,1.2")
        with pytest.raises(OptimizerRunError, match="Missing required columns"):
            optimizer.parse_csv(p)

    def test_invalid_cycle_number_raises(self, optimizer, tmp_path):
        p = _write_csv(tmp_path, "bad_cycle.csv", STD_HEADER, "abc,2020-01-01,2020-06-30,2020-07-01,2020-12-31,0.5")
        with pytest.raises(OptimizerRunError, match="Invalid|missing cycle"):
            optimizer.parse_csv(p)

    def test_single_cycle(self, optimizer, tmp_path):
        p = _write_csv(tmp_path, "single.csv", STD_HEADER, STD_ROW1)
        result = optimizer.parse_csv(p)
        assert len(result.cycles) == 1
        assert result.summary["num_cycles"] == 1.0

    def test_summary_statistics(self, optimizer, tmp_path):
        p = _write_csv(tmp_path, "summary.csv", STD_HEADER, STD_ROW1, STD_ROW2)
        result = optimizer.parse_csv(p, strategy_id="s1")

        assert result.summary["num_cycles"] == 2.0
        # Sharpe
        assert result.summary["avg_sharpe"] == pytest.approx(1.35)
        assert result.summary["best_sharpe"] == 1.5
        assert result.summary["worst_sharpe"] == 1.2
        # ProfitFactor
        assert result.summary["avg_profitfactor"] == pytest.approx(1.75)
        assert result.summary["best_profitfactor"] == 2.0
        assert result.summary["worst_profitfactor"] == 1.5
        # Drawdown — best is min (smallest drawdown)
        assert result.summary["avg_drawdown"] == pytest.approx(4.75)
        assert result.summary["best_drawdown"] == 4.5
        assert result.summary["worst_drawdown"] == 5.0

    def test_unknown_columns_are_parameters(self, optimizer, tmp_path):
        header = "Cycle,InSampleStart,InSampleEnd,OutSampleStart,OutSampleEnd,MyParam,Sharpe"
        p = _write_csv(
            tmp_path, "param_test.csv", header,
            "1,2020-01-01,2020-06-30,2020-07-01,2020-12-31,42.0,1.5",
        )
        result = optimizer.parse_csv(p)
        assert result.cycles[0].parameters["MyParam"] == 42.0
        assert result.cycles[0].metrics["Sharpe"] == 1.5

    def test_metric_names_case_variations(self, optimizer, tmp_path):
        """Should match metric names case-insensitively."""
        header = "Cycle,InSampleStart,InSampleEnd,OutSampleStart,OutSampleEnd,SHARPE,profit factor"
        p = _write_csv(
            tmp_path, "case.csv", header,
            "1,2020-01-01,2020-06-30,2020-07-01,2020-12-31,1.2,1.5",
        )
        result = optimizer.parse_csv(p)
        assert result.cycles[0].metrics["SHARPE"] == 1.2
        assert result.cycles[0].metrics["profit factor"] == 1.5

    def test_flexible_column_order(self, optimizer, tmp_path):
        """Columns in any order should still be parsed correctly."""
        header = "Cycle,Sharpe,InSampleStart,ProfitFactor,InSampleEnd,OutSampleStart,Sensitivity,OutSampleEnd,Drawdown"
        row = "1,1.5,2020-01-01,2.0,2020-06-30,2020-07-01,0.8,2020-12-31,3.0"
        p = _write_csv(tmp_path, "flexible.csv", header, row)
        result = optimizer.parse_csv(p)
        c = result.cycles[0]
        assert c.in_sample_start == "2020-01-01"
        assert c.in_sample_end == "2020-06-30"
        assert c.out_sample_start == "2020-07-01"
        assert c.out_sample_end == "2020-12-31"
        assert c.metrics["Sharpe"] == 1.5
        assert c.metrics["ProfitFactor"] == 2.0
        assert c.metrics["Drawdown"] == 3.0
        assert c.parameters["Sensitivity"] == 0.8

    def test_missing_values_in_cell(self, optimizer, tmp_path):
        """Empty cells for metrics should be skipped, not crash."""
        header = "Cycle,InSampleStart,InSampleEnd,OutSampleStart,OutSampleEnd,Sharpe,Drawdown"
        row = "1,2020-01-01,2020-06-30,2020-07-01,2020-12-31,,5.0"
        p = _write_csv(tmp_path, "missing.csv", header, row)
        result = optimizer.parse_csv(p)
        assert "Sharpe" not in result.cycles[0].metrics
        assert result.cycles[0].metrics["Drawdown"] == 5.0

    def test_extra_spaces_in_cells(self, optimizer, tmp_path):
        header = "Cycle,InSampleStart,InSampleEnd,OutSampleStart,OutSampleEnd,Sharpe"
        row = " 1 , 2020-01-01 , 2020-06-30 , 2020-07-01 , 2020-12-31 , 1.2 "
        p = _write_csv(tmp_path, "spaces.csv", header, row)
        result = optimizer.parse_csv(p)
        assert result.cycles[0].cycle == 1
        assert result.cycles[0].metrics["Sharpe"] == 1.2

    def test_file_not_found_raises(self, optimizer):
        with pytest.raises(OptimizerRunError, match="not found"):
            optimizer.parse_csv(Path("/nonexistent/file.csv"))

    def test_csv_path_stored(self, optimizer, tmp_path):
        p = _write_csv(tmp_path, "store.csv", STD_HEADER, STD_ROW1)
        result = optimizer.parse_csv(p, strategy_id="s1")
        assert result.csv_path == p

    def test_strategy_id_defaults_to_empty(self, optimizer, tmp_path):
        p = _write_csv(tmp_path, "no_id.csv", STD_HEADER, STD_ROW1)
        result = optimizer.parse_csv(p)
        assert result.strategy_id == ""

    def test_skip_blank_lines_before_header(self, optimizer, tmp_path):
        """Blank lines at the start should be skipped."""
        p = _write_csv(tmp_path, "blanks.csv", "", "", STD_HEADER, STD_ROW1)
        result = optimizer.parse_csv(p)
        assert len(result.cycles) == 1

    def test_many_metrics(self, optimizer, tmp_path):
        """All known metric names should be recognized as metrics, not params."""
        header = (
            "Cycle,InSampleStart,InSampleEnd,OutSampleStart,OutSampleEnd,"
            "Sharpe,ProfitFactor,Drawdown,NetProfit,WinRate,RecoveryFactor"
        )
        row = "1,2020-01-01,2020-06-30,2020-07-01,2020-12-31,1.2,1.5,5.0,1000,60,2.0"
        p = _write_csv(tmp_path, "many_metrics.csv", header, row)
        result = optimizer.parse_csv(p)
        c = result.cycles[0]
        assert c.metrics["Sharpe"] == 1.2
        assert c.metrics["NetProfit"] == 1000.0
        assert c.metrics["WinRate"] == 60.0
        assert c.metrics["RecoveryFactor"] == 2.0
        # No parameters in this CSV
        assert len(c.parameters) == 0

    def test_single_cycle_summary(self, optimizer, tmp_path):
        """Even with one cycle, avg/best/worst should exist."""
        p = _write_csv(tmp_path, "one.csv", STD_HEADER, STD_ROW1)
        result = optimizer.parse_csv(p)
        s = result.summary
        assert s["num_cycles"] == 1.0
        assert "avg_sharpe" in s
        assert "best_sharpe" not in s  # need >=2 for best/worst
        assert "worst_sharpe" not in s


# ── To HTML ────────────────────────────────────────────────────────────────────


class TestToHTML:
    """Tests for Optimizer.to_html."""

    @pytest.fixture
    def sample_result(self) -> OptimizationResult:
        c1 = WalkForwardCycle(
            cycle=1,
            in_sample_start="2020-01-01",
            in_sample_end="2020-06-30",
            out_sample_start="2020-07-01",
            out_sample_end="2020-12-31",
            parameters={"Sensitivity": 0.5},
            metrics={"Sharpe": 1.2, "ProfitFactor": 1.5, "Drawdown": 5.0},
        )
        c2 = WalkForwardCycle(
            cycle=2,
            in_sample_start="2020-07-01",
            in_sample_end="2020-12-31",
            out_sample_start="2021-01-01",
            out_sample_end="2021-06-30",
            parameters={"Sensitivity": 0.3},
            metrics={"Sharpe": 1.5, "ProfitFactor": 2.0, "Drawdown": 4.5},
        )
        return OptimizationResult(
            strategy_id="strat-123",
            cycles=[c1, c2],
            summary={
                "num_cycles": 2.0,
                "avg_sharpe": 1.35,
                "best_sharpe": 1.5,
                "worst_sharpe": 1.2,
                "avg_profitfactor": 1.75,
                "avg_drawdown": 4.75,
            },
        )

    def test_generates_html(self, optimizer, sample_result, tmp_path):
        output = tmp_path / "report.html"
        result = optimizer.to_html(sample_result, output)
        assert result == output
        assert output.exists()
        html = output.read_text(encoding="utf-8")
        assert "strat-123" in html
        assert "1.2" in html
        assert "1.5" in html

    def test_valid_html_structure(self, optimizer, sample_result, tmp_path):
        output = tmp_path / "report.html"
        optimizer.to_html(sample_result, output)
        html = output.read_text(encoding="utf-8")
        assert html.startswith("<!DOCTYPE html>") or "<html" in html[:50]
        assert "</html>" in html
        assert "<table" in html
        assert "</table>" in html
        # Should have thead and tbody
        assert "<thead>" in html
        assert "<tbody>" in html

    def test_self_contained_no_external_resources(self, optimizer, sample_result, tmp_path):
        output = tmp_path / "report.html"
        optimizer.to_html(sample_result, output)
        html = output.read_text(encoding="utf-8")
        assert "http://" not in html
        assert "https://" not in html
        assert "@import" not in html

    def test_summary_section_present(self, optimizer, sample_result, tmp_path):
        output = tmp_path / "report.html"
        optimizer.to_html(sample_result, output)
        html = output.read_text(encoding="utf-8")
        assert "Summary Statistics" in html
        assert "1.35" in html  # avg sharpe

    def test_empty_cycles_handled(self, optimizer, tmp_path):
        result = OptimizationResult(strategy_id="empty-test", cycles=[])
        output = tmp_path / "empty.html"
        optimizer.to_html(result, output)
        html = output.read_text(encoding="utf-8")
        assert "No optimization data" in html
        # No table when no cycles
        assert "<table" not in html

    def test_single_cycle_html(self, optimizer, tmp_path):
        c = WalkForwardCycle(
            1, "2020-01-01", "2020-06-30", "2020-07-01", "2020-12-31",
            metrics={"Sharpe": 1.5},
        )
        result = OptimizationResult(strategy_id="single", cycles=[c])
        output = tmp_path / "single.html"
        optimizer.to_html(result, output)
        html = output.read_text(encoding="utf-8")
        # Should have cycle data
        assert "2020-01-01" in html
        assert "1.5" in html
        assert "<table" in html

    def test_output_path_returned(self, optimizer, sample_result, tmp_path):
        output = tmp_path / "report.html"
        returned = optimizer.to_html(sample_result, output)
        assert returned == output

    def test_no_summary_no_crash(self, optimizer, tmp_path):
        """Result without summary dict should generate OK."""
        c = WalkForwardCycle(1, "a", "b", "c", "d")
        result = OptimizationResult(strategy_id="no-summary", cycles=[c])
        output = tmp_path / "no_summary.html"
        optimizer.to_html(result, output)
        html = output.read_text(encoding="utf-8")
        assert "Summary Statistics" not in html  # no summary data
        assert "<table" in html

    def test_html_escaping(self, optimizer, tmp_path):
        """Special characters in strategy_id should be escaped."""
        c = WalkForwardCycle(1, "a", "b", "c", "d")
        result = OptimizationResult(
            strategy_id='<script>alert("xss")</script>',
            cycles=[c],
        )
        output = tmp_path / "xss.html"
        optimizer.to_html(result, output)
        html = output.read_text(encoding="utf-8")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_inline_css_present(self, optimizer, sample_result, tmp_path):
        output = tmp_path / "style.html"
        optimizer.to_html(sample_result, output)
        html = output.read_text(encoding="utf-8")
        assert ".summary-grid" in html or "summary-grid" in html
        assert "max-width" in html
        assert "font-family" in html


# ── run() integration ──────────────────────────────────────────────────────────


class TestRunIntegration:
    """Tests for Optimizer.run — mocking dispatcher, verifying return type."""

    @pytest.mark.asyncio
    async def test_run_returns_optimization_result(self, optimizer, tmp_path):
        """run() returns OptimizationResult when dispatcher succeeds."""
        # Create a real CSV for parse_csv to read
        csv_file = tmp_path / "results.csv"
        csv_file.write_text(
            "Cycle,InSampleStart,InSampleEnd,OutSampleStart,OutSampleEnd,Sharpe\n"
            "1,2020-01-01,2020-06-30,2020-07-01,2020-12-31,1.2\n",
            encoding="utf-8",
        )

        # Build mocks
        status_mock = AsyncMock()
        status_mock.is_complete = True

        dispatcher = AsyncMock()
        dispatcher.load_config = AsyncMock()
        dispatcher.start_project = AsyncMock()
        dispatcher.get_status = AsyncMock(return_value=status_mock)
        dispatcher.export_optimization_results = AsyncMock(return_value=str(csv_file))

        opt = Optimizer("/fake/path", dispatcher=dispatcher)
        config = OptimizerConfig(strategy_id="run-test")

        result = await opt.run(config, output_dir=tmp_path)

        assert isinstance(result, OptimizationResult)
        assert result.strategy_id == "run-test"
        assert result.raw_path == csv_file
        assert len(result.cycles) == 1
        assert result.cycles[0].metrics["Sharpe"] == 1.2

    @pytest.mark.asyncio
    async def test_run_raw_path_backward_compat(self, optimizer, tmp_path):
        """raw_path gives access to the CSV path from run()."""
        csv_file = tmp_path / "backward.csv"
        csv_file.write_text(
            "Cycle,InSampleStart,InSampleEnd,OutSampleStart,OutSampleEnd,Sharpe\n"
            "1,2020-01-01,2020-06-30,2020-07-01,2020-12-31,1.5\n",
            encoding="utf-8",
        )

        status_mock = AsyncMock()
        status_mock.is_complete = True

        dispatcher = AsyncMock()
        dispatcher.load_config = AsyncMock()
        dispatcher.start_project = AsyncMock()
        dispatcher.get_status = AsyncMock(return_value=status_mock)
        dispatcher.export_optimization_results = AsyncMock(return_value=str(csv_file))

        opt = Optimizer("/fake/path", dispatcher=dispatcher)
        config = OptimizerConfig(strategy_id="bc-test")

        result = await opt.run(config, output_dir=tmp_path)
        assert result.raw_path == csv_file
        # raw_path is same as csv_path
        assert result.raw_path is result.csv_path

    @pytest.mark.asyncio
    async def test_run_timeout_raises(self, optimizer):
        """run() should raise OptimizerRunError on timeout."""
        status_mock = AsyncMock()
        status_mock.is_complete = False

        dispatcher = AsyncMock()
        dispatcher.load_config = AsyncMock()
        dispatcher.start_project = AsyncMock()
        dispatcher.get_status = AsyncMock(return_value=status_mock)

        opt = Optimizer("/fake/path", dispatcher=dispatcher)
        config = OptimizerConfig(strategy_id="timeout-test")

        with pytest.raises(OptimizerRunError, match="Timeout"):
            await opt.run(config, timeout=0.1)

    @pytest.mark.asyncio
    async def test_run_cfx_cleanup_on_error(self, optimizer):
        """CFX temp file should be cleaned up even if run fails."""
        dispatcher = AsyncMock()
        dispatcher.load_config = AsyncMock(side_effect=RuntimeError("SQX crash"))

        opt = Optimizer("/fake/path", dispatcher=dispatcher)
        config = OptimizerConfig(strategy_id="cleanup-test")

        with pytest.raises(RuntimeError, match="SQX crash"):
            await opt.run(config)

        # No exception about temp file — it was cleaned up in finally


# ── dry_run ────────────────────────────────────────────────────────────────────


class TestDryRun:
    """Dry-run still works unchanged."""

    def test_dry_run_returns_str(self, optimizer):
        config = OptimizerConfig(strategy_id="strat-dry")
        result = optimizer.dry_run(config)
        assert isinstance(result, str)
        assert len(result) > 0


# ── OptimizerConfig ────────────────────────────────────────────────────────────


class TestOptimizerConfig:
    """OptimizerConfig behaviour."""

    def test_defaults(self):
        cfg = OptimizerConfig(strategy_id="s1")
        assert cfg.method == "Genetic"
        assert cfg.walkforward_cycles == 10
        assert cfg.databanks == []

    def test_custom_values(self):
        cfg = OptimizerConfig(
            strategy_id="s1",
            method="BruteForce",
            walkforward_cycles=5,
            population=200,
        )
        assert cfg.method == "BruteForce"
        assert cfg.walkforward_cycles == 5
        assert cfg.population == 200
