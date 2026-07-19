"""Tests for reporting module."""

import pytest
from datetime import datetime
from pathlib import Path
from quantlab.reporting.models import ReportConfig, ReportFormat, ReportTheme
from quantlab.reporting.generator import ReportGenerator, generate_report
from quantlab.readers.models import Trade, EquityPoint
from quantlab.stats.models import StatsResult


class TestReportConfig:
    """Tests for ReportConfig model."""

    def test_default_config(self):
        config = ReportConfig(campaign_id="test-campaign")
        assert config.campaign_id == "test-campaign"
        assert config.formats == [ReportFormat.HTML, ReportFormat.JSON]
        assert config.include_charts is True
        assert config.theme == ReportTheme.LIGHT

    def test_custom_config(self):
        config = ReportConfig(
            campaign_id="custom",
            formats=[ReportFormat.JSON],
            include_charts=False,
            theme=ReportTheme.DARK,
        )
        assert config.formats == [ReportFormat.JSON]
        assert config.include_charts is False
        assert config.theme == ReportTheme.DARK

    def test_format_enum_values(self):
        assert ReportFormat.HTML.value == "html"
        assert ReportFormat.JSON.value == "json"
        assert ReportTheme.LIGHT.value == "light"
        assert ReportTheme.DARK.value == "dark"


class TestReportGenerator:
    """Tests for ReportGenerator class."""

    @pytest.fixture
    def sample_trades(self):
        return [
            Trade(
                entry_time=datetime(2024, 1, 1, 10, 0),
                exit_time=datetime(2024, 1, 1, 11, 0),
                direction="long",
                lots=1.0,
                profit=100.0,
            ),
            Trade(
                entry_time=datetime(2024, 1, 1, 12, 0),
                exit_time=datetime(2024, 1, 1, 13, 0),
                direction="short",
                lots=0.5,
                profit=-50.0,
            ),
        ]

    @pytest.fixture
    def sample_equity(self):
        return [
            EquityPoint(timestamp=datetime(2024, 1, 1, 10, 0), equity=10000.0),
            EquityPoint(timestamp=datetime(2024, 1, 1, 11, 0), equity=10100.0),
            EquityPoint(timestamp=datetime(2024, 1, 1, 12, 0), equity=10050.0),
        ]

    @pytest.fixture
    def sample_stats(self):
        return StatsResult(
            profit_factor=1.5,
            sharpe_ratio=1.2,
            sortino_ratio=1.5,
            max_drawdown=5.0,
            mar_ratio=0.8,
            recovery_factor=2.0,
            expectancy=10.0,
            expectancy_ratio=0.5,
            win_rate=0.6,
            total_trades=10,
        )

    def test_generator_creation(self):
        config = ReportConfig(campaign_id="test")
        generator = ReportGenerator(config)
        assert generator.config == config

    def test_generate_json_only(self, tmp_path, sample_trades, sample_equity, sample_stats):
        config = ReportConfig(
            campaign_id="test-json",
            output_dir=tmp_path,
            formats=[ReportFormat.JSON],
            include_charts=False,
        )
        generator = ReportGenerator(config)
        result = generator.generate(
            campaign_id="test-json",
            trades=sample_trades,
            equity=sample_equity,
            statistics=sample_stats,
        )
        assert result.json_path is not None
        assert result.html_path is None
        assert result.json_path.exists()
        assert "test-json" in str(result.json_path)

    def test_generate_html_only(self, tmp_path, sample_trades, sample_equity, sample_stats):
        config = ReportConfig(
            campaign_id="test-html",
            output_dir=tmp_path,
            formats=[ReportFormat.HTML],
            include_charts=True,
        )
        generator = ReportGenerator(config)
        result = generator.generate(
            campaign_id="test-html",
            trades=sample_trades,
            equity=sample_equity,
            statistics=sample_stats,
        )
        assert result.html_path is not None
        assert result.json_path is None
        assert result.html_path.exists()

    def test_generate_both_formats(self, tmp_path, sample_trades, sample_equity, sample_stats):
        config = ReportConfig(
            campaign_id="test-both",
            output_dir=tmp_path,
            formats=[ReportFormat.HTML, ReportFormat.JSON],
            include_charts=True,
        )
        generator = ReportGenerator(config)
        result = generator.generate(
            campaign_id="test-both",
            trades=sample_trades,
            equity=sample_equity,
            statistics=sample_stats,
        )
        assert result.html_path is not None
        assert result.json_path is not None
        assert result.html_path.exists()
        assert result.json_path.exists()

    def test_charts_generated_list(self, tmp_path, sample_trades, sample_equity, sample_stats):
        config = ReportConfig(campaign_id="charts", output_dir=tmp_path)
        generator = ReportGenerator(config)
        result = generator.generate(
            campaign_id="charts",
            trades=sample_trades,
            equity=sample_equity,
            statistics=sample_stats,
        )
        assert isinstance(result.charts_generated, list)
        # Should include at least equity_curve and drawdown_underwater
        expected_charts = ["equity_curve", "drawdown_underwater", "trade_scatter", "metrics_table"]
        for chart in expected_charts:
            assert chart in result.charts_generated


class TestConvenienceFunction:
    """Tests for generate_report convenience function."""

    def test_generate_report_function(self, tmp_path):
        from quantlab.stats.models import StatsResult
        config = ReportConfig(campaign_id="func-test", output_dir=tmp_path)
        result = generate_report(
            campaign_id="func-test",
            trades=[],
            equity=[],
            statistics=StatsResult(
                profit_factor=1.0, sharpe_ratio=0.0, sortino_ratio=0.0,
                max_drawdown=0.0, mar_ratio=0.0, recovery_factor=0.0,
                expectancy=0.0, expectancy_ratio=0.0, win_rate=0.0, total_trades=0
            ),
            config=config,
        )
        assert result is not None
        assert result.campaign_id == "func-test"