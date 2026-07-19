"""Tests for Retester — result parsing, CSV export, HTML formatting."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from quantlab.phase4.retester import (
    MonteCarloResult,
    Retester,
    RetesterConfig,
    RetestResult,
    WalkForwardResult,
)
from quantlab.phase4.errors import (
    RetesterRunError,
    RetesterDatabankError,
)


# ── Helper factories ──────────────────────────────────────────────────────────


def make_mc(
    runs: int = 100,
    percentile: int = 95,
    net_profit: float = 15000.0,
    sharpe: float = 1.8,
    drawdown: float = 8.5,
    ci_lower: float = 12000.0,
    ci_upper: float = 18000.0,
) -> MonteCarloResult:
    return MonteCarloResult(
        runs=runs,
        percentile=percentile,
        percentile_net_profit=net_profit,
        percentile_sharpe=sharpe,
        percentile_drawdown=drawdown,
        confidence_interval=(ci_lower, ci_upper),
    )


def make_wf(
    cycles: int = 5,
    avg_sharpe: float = 1.5,
    avg_profit_factor: float = 1.8,
    avg_drawdown: float = 6.0,
    stability: float = 0.85,
) -> WalkForwardResult:
    return WalkForwardResult(
        cycles=cycles,
        avg_sharpe_ratio=avg_sharpe,
        avg_profit_factor=avg_profit_factor,
        avg_drawdown=avg_drawdown,
        stability=stability,
    )


def make_result(
    strategy_id: str = "test-strat-1",
    mc: MonteCarloResult | None = None,
    wf: WalkForwardResult | None = None,
) -> RetestResult:
    return RetestResult(
        strategy_id=strategy_id,
        monte_carlo=mc or make_mc(),
        walk_forward=wf or make_wf(),
    )


# ── RetesterConfig ────────────────────────────────────────────────────────────


class TestRetesterConfig:
    """RetesterConfig validation."""

    def test_valid_config(self):
        cfg = RetesterConfig(
            strategy_id="strat-1",
            databanks=["EURUSD_H1"],
            monte_carlo_runs=500,
            mc_percentile=90,
            walkforward_cycles=10,
            min_trades=50,
            confidence_level=0.90,
        )
        assert cfg.strategy_id == "strat-1"
        assert cfg.databanks == ["EURUSD_H1"]
        assert cfg.monte_carlo_runs == 500
        assert cfg.mc_percentile == 90
        assert cfg.walkforward_cycles == 10
        assert cfg.min_trades == 50
        assert cfg.confidence_level == 0.90

    def test_default_values(self):
        cfg = RetesterConfig(strategy_id="s", databanks=["EURUSD_H1"])
        assert cfg.monte_carlo_runs == 100
        assert cfg.mc_percentile == 95
        assert cfg.walkforward_cycles == 5
        assert cfg.min_trades == 30
        assert cfg.confidence_level == 0.95

    def test_invalid_databank_pattern(self):
        with pytest.raises(RetesterDatabankError, match="Invalid databank"):
            RetesterConfig(strategy_id="s", databanks=["bad-name"])

    def test_invalid_monte_carlo_runs(self):
        with pytest.raises(ValueError, match="monte_carlo_runs"):
            RetesterConfig(strategy_id="s", databanks=["EURUSD_H1"], monte_carlo_runs=0)

    def test_invalid_mc_percentile(self):
        with pytest.raises(ValueError, match="mc_percentile"):
            RetesterConfig(strategy_id="s", databanks=["EURUSD_H1"], mc_percentile=0)

    def test_invalid_walkforward_cycles(self):
        with pytest.raises(ValueError, match="walkforward_cycles"):
            RetesterConfig(
                strategy_id="s", databanks=["EURUSD_H1"], walkforward_cycles=0
            )

    def test_invalid_min_trades(self):
        with pytest.raises(ValueError, match="min_trades"):
            RetesterConfig(strategy_id="s", databanks=["EURUSD_H1"], min_trades=0)

    def test_invalid_confidence_level(self):
        with pytest.raises(ValueError, match="confidence_level"):
            RetesterConfig(
                strategy_id="s", databanks=["EURUSD_H1"], confidence_level=0.5
            )

    def test_multiple_databanks(self):
        cfg = RetesterConfig(
            strategy_id="s",
            databanks=["EURUSD_H1", "GBPUSD_H1", "USDJPY_M15"],
        )
        assert len(cfg.databanks) == 3


# ── MonteCarloResult ──────────────────────────────────────────────────────────


class TestMonteCarloResult:
    """MonteCarloResult dataclass."""

    def test_fields(self):
        mc = make_mc()
        assert mc.runs == 100
        assert mc.percentile == 95
        assert mc.percentile_net_profit == 15000.0
        assert mc.percentile_sharpe == 1.8
        assert mc.percentile_drawdown == 8.5
        assert mc.confidence_interval == (12000.0, 18000.0)

    def test_confidence_interval_tuple(self):
        mc = make_mc(ci_lower=5000.0, ci_upper=25000.0)
        lower, upper = mc.confidence_interval
        assert lower == 5000.0
        assert upper == 25000.0


# ── WalkForwardResult ─────────────────────────────────────────────────────────


class TestWalkForwardResult:
    """WalkForwardResult dataclass."""

    def test_fields(self):
        wf = make_wf()
        assert wf.cycles == 5
        assert wf.avg_sharpe_ratio == 1.5
        assert wf.avg_profit_factor == 1.8
        assert wf.avg_drawdown == 6.0
        assert wf.stability == 0.85

    def test_low_stability(self):
        wf = make_wf(stability=0.35)
        assert wf.stability == 0.35


# ── RetestResult ──────────────────────────────────────────────────────────────


class TestRetestResult:
    """RetestResult dataclass and backward compat."""

    def test_fields(self):
        mc = make_mc()
        wf = make_wf()
        result = RetestResult(
            strategy_id="my-strat",
            monte_carlo=mc,
            walk_forward=wf,
            html_path=Path("/tmp/report.html"),
            csv_path=Path("/tmp/report.csv"),
        )
        assert result.strategy_id == "my-strat"
        assert result.monte_carlo is mc
        assert result.walk_forward is wf
        assert result.html_path == Path("/tmp/report.html")
        assert result.csv_path == Path("/tmp/report.csv")

    def test_html_report_backward_compat(self):
        """html_report property returns html_path (backward compat)."""
        mc = make_mc()
        wf = make_wf()
        result = RetestResult(
            strategy_id="s",
            monte_carlo=mc,
            walk_forward=wf,
            html_path=Path("/tmp/report.html"),
        )
        assert result.html_report == result.html_path

    def test_html_report_none_by_default(self):
        result = make_result()
        assert result.html_path is None
        assert result.html_report is None

    def test_partial_construction(self):
        """Can construct with only required fields."""
        mc = make_mc()
        wf = make_wf()
        result = RetestResult(strategy_id="s", monte_carlo=mc, walk_forward=wf)
        assert result.strategy_id == "s"
        assert result.html_path is None
        assert result.csv_path is None


# ── CSV parsing: key-value format ─────────────────────────────────────────────


KV_CSV = """Metric,Value
MC_Runs,100
MC_Percentile,95
MC_NetProfit,15000.0
MC_Sharpe,1.8
MC_Drawdown,8.5
CI_Lower,12000.0
CI_Upper,18000.0
WF_Cycles,5
WF_AvgSharpe,1.5
WF_AvgProfitFactor,1.8
WF_AvgDrawdown,6.0
WF_Stability,0.85
"""


class TestParseCsvKeyValue:
    """parse_csv with key-value (Metric,Value) format."""

    def test_parse_full_kv_csv(self, tmp_path: Path):
        csv_file = tmp_path / "retest.csv"
        csv_file.write_text(KV_CSV)

        result = Retester.parse_csv(csv_file)

        assert result.strategy_id == ""
        assert result.monte_carlo.runs == 100
        assert result.monte_carlo.percentile == 95
        assert result.monte_carlo.percentile_net_profit == 15000.0
        assert result.monte_carlo.percentile_sharpe == 1.8
        assert result.monte_carlo.percentile_drawdown == 8.5
        assert result.monte_carlo.confidence_interval == (12000.0, 18000.0)
        assert result.walk_forward.cycles == 5
        assert result.walk_forward.avg_sharpe_ratio == 1.5
        assert result.walk_forward.avg_profit_factor == 1.8
        assert result.walk_forward.avg_drawdown == 6.0
        assert result.walk_forward.stability == 0.85
        assert result.csv_path == csv_file

    def test_parse_kv_with_bom(self, tmp_path: Path):
        """UTF-8 BOM should be stripped automatically."""
        csv_file = tmp_path / "bom.csv"
        csv_file.write_bytes(b"\xef\xbb\xbf" + KV_CSV.encode("utf-8"))

        result = Retester.parse_csv(csv_file)
        assert result.monte_carlo.runs == 100
        assert result.monte_carlo.percentile_net_profit == 15000.0

    def test_parse_kv_missing_optional_metrics(self, tmp_path: Path):
        """Should handle partial data with sensible defaults."""
        partial = """Metric,Value
MC_Runs,50
MC_Percentile,90
MC_NetProfit,8000.0
WF_Cycles,3
"""
        csv_file = tmp_path / "partial.csv"
        csv_file.write_text(partial)

        result = Retester.parse_csv(csv_file)

        # Present fields
        assert result.monte_carlo.runs == 50
        assert result.monte_carlo.percentile == 90
        assert result.monte_carlo.percentile_net_profit == 8000.0
        # Missing fields default to 0.0 / 0
        assert result.monte_carlo.percentile_sharpe == 0.0
        assert result.monte_carlo.percentile_drawdown == 0.0
        assert result.monte_carlo.confidence_interval == (0.0, 0.0)
        assert result.walk_forward.cycles == 3
        assert result.walk_forward.avg_sharpe_ratio == 0.0

    def test_parse_kv_empty_file(self, tmp_path: Path):
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("")

        with pytest.raises(RetesterRunError, match="No parseable metrics"):
            Retester.parse_csv(csv_file)

    def test_parse_kv_file_not_found(self, tmp_path: Path):
        csv_file = tmp_path / "nonexistent.csv"

        with pytest.raises(RetesterRunError, match="CSV file not found"):
            Retester.parse_csv(csv_file)

    def test_parse_kv_with_integer_values(self, tmp_path: Path):
        """Integer-only values should parse correctly."""
        csv_file = tmp_path / "ints.csv"
        csv_file.write_text(
            "Metric,Value\nMC_Runs,200\nMC_Percentile,90\nWF_Cycles,10\n"
        )

        result = Retester.parse_csv(csv_file)
        assert result.monte_carlo.runs == 200
        assert result.monte_carlo.percentile == 90
        assert result.walk_forward.cycles == 10

    def test_parse_kv_with_percent_sign(self, tmp_path: Path):
        csv_file = tmp_path / "pct.csv"
        csv_file.write_text(
            "Metric,Value\nMC_Drawdown,8.5%\nWF_Stability,0.85\n"
        )

        result = Retester.parse_csv(csv_file)
        assert result.monte_carlo.percentile_drawdown == 8.5
        assert result.walk_forward.stability == 0.85

    def test_parse_kv_with_thousands_separator(self, tmp_path: Path):
        csv_file = tmp_path / "thousands.csv"
        csv_file.write_text(
            "Metric,Value\nMC_NetProfit,\"15,000.0\"\nCI_Lower,\"12,000\"\nCI_Upper,18000.0\n"
        )

        result = Retester.parse_csv(csv_file)
        assert result.monte_carlo.percentile_net_profit == 15000.0
        assert result.monte_carlo.confidence_interval == (12000.0, 18000.0)

    def test_parse_kv_extra_columns_ignored(self, tmp_path: Path):
        csv_file = tmp_path / "extra_cols.csv"
        csv_file.write_text(
            "Metric,Value,Notes\n"
            "MC_Runs,100,some note\n"
            "MC_Percentile,95,another note\n"
            "WF_Cycles,5,note\n"
        )

        result = Retester.parse_csv(csv_file)
        assert result.monte_carlo.runs == 100
        assert result.monte_carlo.percentile == 95
        assert result.walk_forward.cycles == 5


# ── CSV parsing: multi-column format ──────────────────────────────────────────


class TestParseCsvMultiColumn:
    """parse_csv with multi-column format."""

    def test_multi_column_header_scan(self, tmp_path: Path):
        """Header-row keyword scanning."""
        csv_file = tmp_path / "multi.csv"
        csv_file.write_text(
            "Runs,Percentile,NetProfit,Sharpe,Drawdown,Lower,Upper\n"
            "100,95,15000.0,1.8,8.5,12000.0,18000.0\n"
        )

        result = Retester.parse_csv(csv_file)
        assert result.monte_carlo.runs == 100
        assert result.monte_carlo.percentile == 95
        assert result.monte_carlo.percentile_net_profit == 15000.0
        assert result.monte_carlo.percentile_sharpe == 1.8
        assert result.monte_carlo.percentile_drawdown == 8.5
        assert result.monte_carlo.confidence_interval == (12000.0, 18000.0)

    def test_multi_column_with_wf_headers(self, tmp_path: Path):
        csv_file = tmp_path / "multi_wf.csv"
        csv_file.write_text(
            "Cycles,AvgSharpe,AvgProfitFactor,AvgDrawdown,Stability\n"
            "5,1.5,1.8,6.0,0.85\n"
        )

        result = Retester.parse_csv(csv_file)
        assert result.walk_forward.cycles == 5
        assert result.walk_forward.avg_sharpe_ratio == 1.5
        assert result.walk_forward.avg_profit_factor == 1.8
        assert result.walk_forward.avg_drawdown == 6.0
        assert result.walk_forward.stability == 0.85

    def test_multi_column_label_scan(self, tmp_path: Path):
        """Row-by-row label scanning fallback."""
        csv_file = tmp_path / "labels.csv"
        csv_file.write_text(
            "MC_Runs,100\n"
            "MC_Percentile,95\n"
            "MC_NetProfit,15000.0\n"
            "MC_Sharpe,1.8\n"
            "MC_Drawdown,8.5\n"
            "WF_Cycles,5\n"
            "WF_AvgSharpe,1.5\n"
            "WF_AvgProfitFactor,1.8\n"
        )

        result = Retester.parse_csv(csv_file)
        assert result.monte_carlo.runs == 100
        assert result.monte_carlo.percentile == 95
        assert result.monte_carlo.percentile_net_profit == 15000.0
        assert result.monte_carlo.percentile_sharpe == 1.8
        assert result.monte_carlo.percentile_drawdown == 8.5
        assert result.walk_forward.cycles == 5
        assert result.walk_forward.avg_sharpe_ratio == 1.5
        assert result.walk_forward.avg_profit_factor == 1.8

    def test_multi_column_label_scan_variant_names(self, tmp_path: Path):
        """Variant label names in label-scan mode."""
        csv_file = tmp_path / "variants.csv"
        csv_file.write_text(
            "MC_NET_PROFIT,15000.0\n"
            "MC_MAX_DRAWDOWN,8.5\n"
            "CI_LOWER_BOUND,12000.0\n"
            "CI_UPPER_BOUND,18000.0\n"
            "WF_AVG_SHARPE,1.5\n"
            "WF_AVG_DRAWDOWN,6.0\n"
        )

        result = Retester.parse_csv(csv_file)
        assert result.monte_carlo.percentile_net_profit == 15000.0
        assert result.monte_carlo.percentile_drawdown == 8.5
        assert result.monte_carlo.confidence_interval == (12000.0, 18000.0)
        assert result.walk_forward.avg_sharpe_ratio == 1.5
        assert result.walk_forward.avg_drawdown == 6.0

    def test_multi_column_combined_mc_wf(self, tmp_path: Path):
        """Both MC and WF sections in one multi-column file."""
        csv_file = tmp_path / "combined.csv"
        csv_file.write_text(
            "Runs,Percentile,NetProfit,Sharpe,Drawdown,Lower,Upper,Cycles,AvgSharpe,AvgProfitFactor,AvgDrawdown,Stability\n"
            "100,95,15000.0,1.8,8.5,12000.0,18000.0,5,1.5,1.8,6.0,0.85\n"
        )

        result = Retester.parse_csv(csv_file)
        assert result.monte_carlo.runs == 100
        assert result.monte_carlo.percentile == 95
        assert result.walk_forward.cycles == 5
        assert result.walk_forward.avg_sharpe_ratio == 1.5
        assert result.walk_forward.stability == 0.85


# ── HTML generation ───────────────────────────────────────────────────────────


class TestToHtml:
    """Retester.to_html output."""

    def test_generates_valid_html(self, tmp_path: Path):
        result = make_result()
        out = tmp_path / "report.html"

        html_path = Retester.to_html(result, out)

        assert html_path == out
        assert out.exists()
        html = out.read_text()
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_includes_strategy_id(self, tmp_path: Path):
        result = make_result(strategy_id="my-custom-strat")
        out = tmp_path / "report.html"

        Retester.to_html(result, out)
        html = out.read_text()
        assert "my-custom-strat" in html

    def test_includes_mc_metrics(self, tmp_path: Path):
        result = make_result()
        out = tmp_path / "report.html"

        Retester.to_html(result, out)
        html = out.read_text()
        assert "Monte Carlo Simulation" in html
        assert "100" in html  # runs
        assert "95%" in html  # percentile
        assert "15,000.00" in html  # net profit formatted
        assert "1.80" in html  # sharpe

    def test_includes_confidence_interval(self, tmp_path: Path):
        result = make_result(mc=make_mc(ci_lower=10000.0, ci_upper=20000.0))
        out = tmp_path / "report.html"

        Retester.to_html(result, out)
        html = out.read_text()
        assert "10,000.00" in html
        assert "20,000.00" in html
        assert "range" in html

    def test_includes_walk_forward_table(self, tmp_path: Path):
        result = make_result()
        out = tmp_path / "report.html"

        Retester.to_html(result, out)
        html = out.read_text()
        assert "Walk-Forward Analysis" in html
        assert "1.50" in html  # avg sharpe
        assert "1.80" in html  # profit factor

    def test_stability_coloring_good(self, tmp_path: Path):
        result = make_result(wf=make_wf(stability=0.92))
        out = tmp_path / "report.html"
        Retester.to_html(result, out)
        html = out.read_text()
        assert "stability-good" in html

    def test_stability_coloring_warn(self, tmp_path: Path):
        result = make_result(wf=make_wf(stability=0.70))
        out = tmp_path / "report.html"
        Retester.to_html(result, out)
        html = out.read_text()
        assert "stability-warn" in html

    def test_stability_coloring_poor(self, tmp_path: Path):
        result = make_result(wf=make_wf(stability=0.40))
        out = tmp_path / "report.html"
        Retester.to_html(result, out)
        html = out.read_text()
        assert "stability-poor" in html

    def test_includes_csv_path_in_meta(self, tmp_path: Path):
        result = make_result()
        result.csv_path = Path("/some/path/results.csv")
        out = tmp_path / "report.html"

        Retester.to_html(result, out)
        html = out.read_text()
        assert "results.csv" in html

    def test_creates_parent_directories(self, tmp_path: Path):
        result = make_result()
        nested = tmp_path / "a" / "b" / "report.html"

        Retester.to_html(result, nested)
        assert nested.exists()

    def test_returns_path(self, tmp_path: Path):
        result = make_result()
        out = tmp_path / "report.html"

        returned = Retester.to_html(result, out)
        assert isinstance(returned, Path)
        assert returned == out


# ── Run method ────────────────────────────────────────────────────────────────


class TestRun:
    """Retester.run integration with mocked dispatcher."""

    @pytest.fixture
    def mock_dispatcher(self):
        dispatcher = AsyncMock()
        dispatcher.load_config = AsyncMock()
        dispatcher.start_project = AsyncMock()
        dispatcher.get_status = AsyncMock()
        dispatcher.export_retest_report = AsyncMock(return_value="/tmp/retest.html")
        dispatcher.export_retest_csv = AsyncMock(return_value="/tmp/retest_retest.csv")
        return dispatcher

    @pytest.fixture
    def csv_content(self):
        return KV_CSV

    @pytest.mark.asyncio
    async def test_run_returns_retest_result(
        self, tmp_path: Path, mock_dispatcher, csv_content
    ):
        """run() returns a RetestResult (not Path) after updating return type."""
        status = AsyncMock()
        status.is_complete = True
        mock_dispatcher.get_status.return_value = status

        # Write the CSV to the expected path before run() parses it
        csv_path = Path("/tmp/retest_retest.csv")
        csv_path.write_text(csv_content)

        try:
            retester = Retester(sqx_install_path="/tmp", dispatcher=mock_dispatcher)
            cfg = RetesterConfig(
                strategy_id="my-strat",
                databanks=["EURUSD_H1"],
            )

            result = await retester.run(cfg, output_dir=tmp_path)

            assert isinstance(result, RetestResult)
            assert result.strategy_id == "my-strat"
            assert result.monte_carlo.runs == 100
            assert result.walk_forward.cycles == 5
            assert result.html_path is not None
            assert result.csv_path is not None

            # Backward compat
            assert result.html_report is not None
            assert result.html_report == result.html_path

        finally:
            csv_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_run_export_both_formats(
        self, tmp_path: Path, mock_dispatcher, csv_content
    ):
        """run() calls both export_retest_report and export_retest_csv."""
        status = AsyncMock()
        status.is_complete = True
        mock_dispatcher.get_status.return_value = status

        csv_path = Path("/tmp/retest_retest.csv")
        csv_path.write_text(csv_content)

        try:
            retester = Retester(sqx_install_path="/tmp", dispatcher=mock_dispatcher)
            cfg = RetesterConfig(
                strategy_id="my-strat",
                databanks=["EURUSD_H1"],
            )

            await retester.run(cfg, output_dir=tmp_path)

            mock_dispatcher.export_retest_report.assert_awaited_once()
            mock_dispatcher.export_retest_csv.assert_awaited_once()
        finally:
            csv_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_run_timeout(
        self, tmp_path: Path, mock_dispatcher, csv_content
    ):
        """Timeout raises RetesterRunError."""
        status = AsyncMock()
        status.is_complete = False
        mock_dispatcher.get_status.return_value = status

        retester = Retester(sqx_install_path="/tmp", dispatcher=mock_dispatcher)
        cfg = RetesterConfig(strategy_id="s", databanks=["EURUSD_H1"])

        with pytest.raises(RetesterRunError, match="Timeout"):
            await retester.run(cfg, output_dir=tmp_path, timeout=0.1)

    @pytest.mark.asyncio
    async def test_run_dispatcher_error_propagates(
        self, tmp_path: Path, mock_dispatcher
    ):
        """Dispatchers errors are wrapped in RetesterRunError."""
        mock_dispatcher.load_config.side_effect = RuntimeError("SQX crash")

        retester = Retester(sqx_install_path="/tmp", dispatcher=mock_dispatcher)
        cfg = RetesterConfig(strategy_id="s", databanks=["EURUSD_H1"])

        with pytest.raises(RetesterRunError, match="SQX crash"):
            await retester.run(cfg, output_dir=tmp_path, timeout=0.1)

    @pytest.mark.asyncio
    async def test_run_parses_csv_from_dispatcher(
        self, tmp_path: Path, mock_dispatcher, csv_content
    ):
        """The CSV written by export_retest_csv is parsed into the result."""
        status = AsyncMock()
        status.is_complete = True
        mock_dispatcher.get_status.return_value = status

        csv_path = Path("/tmp/retest_retest.csv")
        csv_path.write_text(csv_content)

        try:
            retester = Retester(sqx_install_path="/tmp", dispatcher=mock_dispatcher)
            cfg = RetesterConfig(
                strategy_id="my-strat",
                databanks=["EURUSD_H1"],
            )

            result = await retester.run(cfg, output_dir=tmp_path)

            assert result.monte_carlo.percentile_net_profit == 15000.0
            assert result.walk_forward.stability == 0.85
        finally:
            csv_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_run_cfx_cleaned_up(
        self, tmp_path: Path, mock_dispatcher, csv_content
    ):
        """Temp CFX file is cleaned up after run (even on error)."""
        status = AsyncMock()
        status.is_complete = True
        mock_dispatcher.get_status.return_value = status

        csv_path = Path("/tmp/retest_retest.csv")
        csv_path.write_text(csv_content)

        try:
            with patch.object(Retester, "_wait_for_completion") as mock_wait:
                mock_wait.side_effect = RetesterRunError("boom")

                retester = Retester(
                    sqx_install_path="/tmp", dispatcher=mock_dispatcher
                )
                cfg = RetesterConfig(
                    strategy_id="s", databanks=["EURUSD_H1"]
                )

                with pytest.raises(RetesterRunError):
                    await retester.run(cfg, output_dir=tmp_path)

                # CFX file should still be removed (finally block)
                mock_dispatcher.load_config.assert_awaited_once()
        finally:
            csv_path.unlink(missing_ok=True)


# ── Dry run ───────────────────────────────────────────────────────────────────


class TestDryRun:
    """dry_run method."""

    def test_dry_run_returns_base64(self):
        retester = Retester(sqx_install_path="/tmp")
        cfg = RetesterConfig(
            strategy_id="strat-1",
            databanks=["EURUSD_H1"],
        )
        result = retester.dry_run(cfg)
        assert isinstance(result, str)
        assert len(result) > 0
        # Should be valid base64
        import base64
        decoded = base64.b64decode(result)
        assert len(decoded) > 0


# ── Integration: parse_csv + to_html round trip ───────────────────────────────


class TestRoundTrip:
    """Parse CSV then generate HTML from the result."""

    def test_parse_then_html(self, tmp_path: Path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text(KV_CSV)

        result = Retester.parse_csv(csv_file)
        html_out = tmp_path / "report.html"

        Retester.to_html(result, html_out)

        assert html_out.exists()
        html = html_out.read_text()
        assert "15,000.00" in html
        assert "1.80" in html
        assert "1.50" in html
        assert "0.85" in html
