"""Tests for Reporting CLI."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import argparse

from quantlab.reporting.cli import generate_report_command, add_report_subparser
from quantlab.reporting.models import ReportConfig, ReportFormat, ReportTheme
from quantlab.readers.models import Trade, EquityPoint
from quantlab.stats.models import StatsResult


class TestReportCLI:
    """Tests for report CLI command."""

    @pytest.fixture
    def mock_args(self):
        """Create mock args for report generate command."""
        args = argparse.Namespace()
        args.campaign_id = "test-campaign"
        args.output_dir = "reports"
        args.knowledge_root = "knowledge"
        args.html = True
        args.json = True
        args.theme = "light"
        args.no_charts = False
        args.title = "Test Report"
        args.template = None
        args.benchmark = None
        args.knowledge_root = "knowledge"
        return args

    @patch('quantlab.reporting.cli.KnowledgeStore')
    @patch('quantlab.reporting.cli.generate_report')
    def test_generate_report_command_success(self, mock_generate, mock_store_class, mock_args, tmp_path):
        """Test successful report generation."""
        # Setup mock store
        mock_store = Mock()
        mock_store_class.return_value = mock_store

        # Setup mock generate_report
        mock_result = Mock()
        mock_result.html_path = Path("reports/test-campaign_report.html")
        mock_result.json_path = Path("reports/test-campaign_report.json")
        mock_result.warnings = []
        mock_result.is_successful.return_value = True
        mock_generate.return_value = mock_result

        # Mock _load_campaign_data
        with patch('quantlab.reporting.cli._load_campaign_data') as mock_load:
            mock_load.return_value = ([], [], Mock())

            result = generate_report_command(mock_args)

        assert result == 0
        mock_generate.assert_called_once()

    @patch('quantlab.reporting.cli.KnowledgeStore')
    def test_generate_report_command_campaign_not_found(self, mock_store_class, mock_args):
        """Test report generation when campaign not found."""
        mock_store = Mock()
        mock_store_class.return_value = mock_store

        with patch('quantlab.reporting.cli._load_campaign_data') as mock_load:
            mock_load.side_effect = FileNotFoundError("Campaign not found")

            result = generate_report_command(mock_args)

        assert result == 1

    @patch('quantlab.reporting.cli.KnowledgeStore')
    def test_generate_report_command_load_error(self, mock_store_class, mock_args):
        """Test report generation when loading fails."""
        mock_store = Mock()
        mock_store_class.return_value = mock_store

        with patch('quantlab.reporting.cli._load_campaign_data') as mock_load:
            mock_load.side_effect = Exception("Load failed")

            result = generate_report_command(mock_args)

        assert result == 2

    def test_add_report_subparser(self):
        """Test that report subparser is added correctly."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command", required=True)
        add_report_subparser(subparsers)

        # Parse report generate command
        args = parser.parse_args(["report", "generate", "test-campaign"])
        assert args.command == "report"
        assert args.report_cmd == "generate"
        assert args.campaign_id == "test-campaign"
        assert hasattr(args, 'func')

    def test_add_report_subparser_all_options(self):
        """Test report subparser with all options."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command", required=True)
        add_report_subparser(subparsers)

        args = parser.parse_args([
            "report", "generate", "test-campaign",
            "--output-dir", "custom_reports",
            "--knowledge-root", "my_knowledge",
            "--no-html",
            "--no-json",
            "--theme", "dark",
            "--no-charts",
            "--title", "Custom Title"
        ])
        assert args.output_dir == "custom_reports"
        assert args.knowledge_root == "my_knowledge"
        assert args.html is False
        assert args.json is False
        assert args.theme == "dark"
        assert args.no_charts is True
        assert args.title == "Custom Title"


class TestLoadCampaignData:
    """Tests for _load_campaign_data internal function."""

    def test_load_campaign_data_basic(self, tmp_path):
        """Test loading basic campaign data."""
        from quantlab.reporting.cli import _load_campaign_data
        from quantlab.knowledge.store import KnowledgeStore

        # Create knowledge lake structure
        store = KnowledgeStore(tmp_path)
        store.initialize()

        campaign_id = "test-campaign"

        # Create stats file
        stats_dir = tmp_path / "stats"
        stats_dir.mkdir(exist_ok=True)
        import yaml
        stats_data = {
            "sharpe_ratio": 1.5,
            "profit_factor": 1.8,
            "win_rate": 0.65,
            "max_drawdown": 5.0,
            "total_trades": 100,
            "net_profit": 5000.0,
        }
        (stats_dir / f"{campaign_id}.yaml").write_text(yaml.dump(stats_data))

        # Create trades CSV
        results_dir = tmp_path / "results"
        results_dir.mkdir(exist_ok=True)
        trades_csv = """entry_time,exit_time,direction,lots,profit
2024-01-01 10:00,2024-01-01 11:00,long,1.0,100.0
2024-01-01 12:00,2024-01-01 13:00,short,0.5,-50.0
"""
        (results_dir / f"{campaign_id}.csv").write_text(trades_csv)

        # Create equity CSV
        structured_dir = tmp_path / "structured"
        structured_dir.mkdir(exist_ok=True)
        equity_csv = """timestamp,equity
2024-01-01 10:00,10000.0
2024-01-01 11:00,10100.0
2024-01-01 12:00,10050.0
"""
        (structured_dir / f"{campaign_id}_equity.csv").write_text(equity_csv)

        # Load data
        trades, equity, statistics = _load_campaign_data(store, campaign_id)

        assert len(trades) == 2
        assert len(equity) == 3
        assert hasattr(statistics, 'sharpe_ratio')
        assert statistics.sharpe_ratio == 1.5

    def test_load_campaign_data_missing_stats(self, tmp_path):
        """Test loading when stats file is missing."""
        from quantlab.reporting.cli import _load_campaign_data
        from quantlab.knowledge.store import KnowledgeStore

        store = KnowledgeStore(tmp_path)
        store.initialize()

        with pytest.raises(FileNotFoundError):
            _load_campaign_data(store, "nonexistent-campaign")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])