"""Tests for Knowledge Lake CLI commands."""

import pytest
import asyncio
import json
import csv
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import argparse

from quantlab.cli.knowledge_commands import (
    cmd_knowledge_query,
    cmd_knowledge_tag,
    cmd_knowledge_link,
    cmd_knowledge_export,
    add_knowledge_subparser,
)
from quantlab.knowledge.models import CampaignSummary, CampaignMetrics, QueryResult, QueryFilter
from quantlab.readers.models import Trade, EquityPoint
from quantlab.stats.models import StatsResult


def run_async(coro):
    """Helper to run async function in tests."""
    return asyncio.run(coro)


class TestKnowledgeQuery:
    """Tests for knowledge query command."""

    @pytest.fixture
    def mock_args(self):
        """Create mock args for query command."""
        args = argparse.Namespace()
        args.sqx_path = "knowledge"
        args.json = False
        args.sharpe = None
        args.profit_factor = None
        args.win_rate = None
        args.max_drawdown = None
        args.tags = None
        args.date = None
        args.text = None
        args.sort = "created"
        args.desc = True
        args.limit = 50
        args.offset = 0
        return args

    @patch('quantlab.cli.knowledge_commands.QueryBuilder')
    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_query_no_filters(self, mock_store_class, mock_builder_class, mock_args):
        """Test query with no filters."""
        mock_store = Mock()
        mock_store.read_index.return_value = {"directories": {}}
        mock_store_class.return_value = mock_store

        mock_builder = Mock()
        mock_builder.execute.return_value = QueryResult(
            campaigns=[],
            total_count=0,
            query_time_ms=1.0
        )
        mock_builder_class.return_value = mock_builder

        result = run_async(cmd_knowledge_query(mock_args))

        assert result == 0
        mock_builder.filter_by_sharpe.assert_not_called()

    @patch('quantlab.cli.knowledge_commands.QueryBuilder')
    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_query_with_sharpe_filter(self, mock_store_class, mock_builder_class, mock_args):
        """Test query with Sharpe ratio filter."""
        mock_args.sharpe = ">1.5"
        mock_store = Mock()
        mock_store.read_index.return_value = {"directories": {}}
        mock_store_class.return_value = mock_store

        mock_builder = Mock()
        mock_builder.execute.return_value = QueryResult(
            campaigns=[],
            total_count=0,
            query_time_ms=1.0
        )
        mock_builder_class.return_value = mock_builder

        result = run_async(cmd_knowledge_query(mock_args))

        assert result == 0
        mock_builder.filter_by_sharpe.assert_called_once_with(min_val=1.5)

    @patch('quantlab.cli.knowledge_commands.QueryBuilder')
    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_query_with_sharpe_filter_max(self, mock_store_class, mock_builder_class, mock_args):
        """Test query with Sharpe ratio max filter."""
        mock_args.sharpe = "<2.0"
        mock_store = Mock()
        mock_store.read_index.return_value = {"directories": {}}
        mock_store_class.return_value = mock_store

        mock_builder = Mock()
        mock_builder.execute.return_value = QueryResult(
            campaigns=[],
            total_count=0,
            query_time_ms=1.0
        )
        mock_builder_class.return_value = mock_builder

        result = run_async(cmd_knowledge_query(mock_args))

        assert result == 0
        mock_builder.filter_by_sharpe.assert_called_once_with(max_val=2.0)

    @patch('quantlab.cli.knowledge_commands.QueryBuilder')
    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_query_with_profit_factor_filter(self, mock_store_class, mock_builder_class, mock_args):
        """Test query with profit factor filter."""
        mock_args.profit_factor = ">1.2"
        mock_store = Mock()
        mock_store.read_index.return_value = {"directories": {}}
        mock_store_class.return_value = mock_store

        mock_builder = Mock()
        mock_builder.execute.return_value = QueryResult(
            campaigns=[],
            total_count=0,
            query_time_ms=1.0
        )
        mock_builder_class.return_value = mock_builder

        result = run_async(cmd_knowledge_query(mock_args))

        assert result == 0
        mock_builder.filter_by_profit_factor.assert_called_once_with(min_val=1.2)

    @patch('quantlab.cli.knowledge_commands.QueryBuilder')
    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_query_with_win_rate_filter(self, mock_store_class, mock_builder_class, mock_args):
        """Test query with win rate filter."""
        mock_args.win_rate = ">0.5"
        mock_store = Mock()
        mock_store.read_index.return_value = {"directories": {}}
        mock_store_class.return_value = mock_store

        mock_builder = Mock()
        mock_builder.execute.return_value = QueryResult(
            campaigns=[],
            total_count=0,
            query_time_ms=1.0
        )
        mock_builder_class.return_value = mock_builder

        result = run_async(cmd_knowledge_query(mock_args))

        assert result == 0
        mock_builder.filter_by_win_rate.assert_called_once_with(min_val=0.5)

    @patch('quantlab.cli.knowledge_commands.QueryBuilder')
    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_query_with_max_drawdown_filter(self, mock_store_class, mock_builder_class, mock_args):
        """Test query with max drawdown filter."""
        mock_args.max_drawdown = "<10"
        mock_store = Mock()
        mock_store.read_index.return_value = {"directories": {}}
        mock_store_class.return_value = mock_store

        mock_builder = Mock()
        mock_builder.execute.return_value = QueryResult(
            campaigns=[],
            total_count=0,
            query_time_ms=1.0
        )
        mock_builder_class.return_value = mock_builder

        result = run_async(cmd_knowledge_query(mock_args))

        assert result == 0
        mock_builder.filter_by_max_drawdown.assert_called_once_with(max_val=10.0)

    @patch('quantlab.cli.knowledge_commands.QueryBuilder')
    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_query_with_tags_filter(self, mock_store_class, mock_builder_class, mock_args):
        """Test query with tags filter."""
        mock_args.tags = ["trend", "momentum"]
        mock_store = Mock()
        mock_store.read_index.return_value = {"directories": {}}
        mock_store_class.return_value = mock_store

        mock_builder = Mock()
        mock_builder.execute.return_value = QueryResult(
            campaigns=[],
            total_count=0,
            query_time_ms=1.0
        )
        mock_builder_class.return_value = mock_builder

        result = run_async(cmd_knowledge_query(mock_args))

        assert result == 0
        mock_builder.filter_by_tags.assert_called_once_with(["trend", "momentum"])

    @patch('quantlab.cli.knowledge_commands.QueryBuilder')
    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_query_with_date_filter(self, mock_store_class, mock_builder_class, mock_args):
        """Test query with date filter."""
        mock_args.date = "2024-01-01..2024-12-31"
        mock_store = Mock()
        mock_store.read_index.return_value = {"directories": {}}
        mock_store_class.return_value = mock_store

        mock_builder = Mock()
        mock_builder.execute.return_value = QueryResult(
            campaigns=[],
            total_count=0,
            query_time_ms=1.0
        )
        mock_builder_class.return_value = mock_builder

        result = run_async(cmd_knowledge_query(mock_args))

        assert result == 0
        mock_builder.filter_by_date.assert_called_once_with("2024-01-01", "2024-12-31")

    @patch('quantlab.cli.knowledge_commands.QueryBuilder')
    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_query_with_text_search(self, mock_store_class, mock_builder_class, mock_args):
        """Test query with text search."""
        mock_args.text = "EURUSD"
        mock_store = Mock()
        mock_store.read_index.return_value = {"directories": {}}
        mock_store_class.return_value = mock_store

        mock_builder = Mock()
        mock_builder.execute.return_value = QueryResult(
            campaigns=[],
            total_count=0,
            query_time_ms=1.0
        )
        mock_builder_class.return_value = mock_builder

        result = run_async(cmd_knowledge_query(mock_args))

        assert result == 0
        mock_builder.search_text.assert_called_once_with("EURUSD")

    @patch('quantlab.cli.knowledge_commands.QueryBuilder')
    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_query_with_sort(self, mock_store_class, mock_builder_class, mock_args):
        """Test query with sort."""
        mock_args.sort = "sharpe"
        mock_args.desc = False
        mock_store = Mock()
        mock_store.read_index.return_value = {"directories": {}}
        mock_store_class.return_value = mock_store

        mock_builder = Mock()
        mock_builder.execute.return_value = QueryResult(
            campaigns=[],
            total_count=0,
            query_time_ms=1.0
        )
        mock_builder_class.return_value = mock_builder

        result = run_async(cmd_knowledge_query(mock_args))

        assert result == 0
        mock_builder.sort_by.assert_called_once_with("sharpe", True)

    @patch('quantlab.cli.knowledge_commands.QueryBuilder')
    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_query_with_pagination(self, mock_store_class, mock_builder_class, mock_args):
        """Test query with limit and offset."""
        mock_args.limit = 10
        mock_args.offset = 20
        mock_store = Mock()
        mock_store.read_index.return_value = {"directories": {}}
        mock_store_class.return_value = mock_store

        mock_builder = Mock()
        mock_builder.execute.return_value = QueryResult(
            campaigns=[],
            total_count=0,
            query_time_ms=1.0
        )
        mock_builder_class.return_value = mock_builder

        result = run_async(cmd_knowledge_query(mock_args))

        assert result == 0
        mock_builder.limit.assert_called_once_with(10)
        mock_builder.offset.assert_called_once_with(20)

    @patch('quantlab.cli.knowledge_commands.QueryBuilder')
    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_query_json_output(self, mock_store_class, mock_builder_class, mock_args):
        """Test query with JSON output."""
        mock_args.json = True
        mock_store = Mock()
        mock_store.read_index.return_value = {
            "directories": {
                "results": {
                    "camp1.yaml": {
                        "path": "results/camp1.yaml",
                        "metrics": {
                            "sharpe_ratio": 1.5,
                            "profit_factor": 1.8,
                            "win_rate": 0.65,
                            "max_drawdown": 5.0
                        },
                        "tags": ["trend"],
                        "created": "2024-01-01T00:00:00"
                    }
                }
            }
        }
        mock_store_class.return_value = mock_store

        mock_builder = Mock()
        mock_builder.execute.return_value = QueryResult(
            campaigns=[],
            total_count=0,
            query_time_ms=1.0
        )
        mock_builder_class.return_value = mock_builder

        result = run_async(cmd_knowledge_query(mock_args))

        assert result == 0


class TestKnowledgeTag:
    """Tests for knowledge tag command."""

    @pytest.fixture
    def mock_args(self):
        """Create mock args for tag command."""
        args = argparse.Namespace()
        args.sqx_path = "knowledge"
        args.campaign_id = "camp1"
        args.tags = ["trend", "momentum"]
        args.remove = False
        return args

    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_tag_add_tags(self, mock_store_class, mock_args):
        """Test adding tags to a campaign."""
        mock_store = Mock()
        mock_store.tag.return_value = True
        mock_store_class.return_value = mock_store

        result = run_async(cmd_knowledge_tag(mock_args))

        assert result == 0
        mock_store.tag.assert_called_once_with("camp1", ["trend", "momentum"])

    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_tag_campaign_not_found(self, mock_store_class, mock_args):
        """Test adding tags to non-existent campaign."""
        mock_store = Mock()
        mock_store.tag.return_value = False
        mock_store_class.return_value = mock_store

        result = run_async(cmd_knowledge_tag(mock_args))

        assert result == 1

    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    @patch('quantlab.knowledge.indexer.Indexer')
    def test_tag_remove_tags(self, mock_indexer_class, mock_store_class, mock_args):
        """Test removing tags from a campaign."""
        mock_args.remove = True
        mock_args.tags = ["trend"]

        mock_store = Mock()
        mock_store.get_tags.return_value = ["trend", "momentum"]
        mock_store.read_index.return_value = {
            "directories": {
                "results": {
                    "camp1.yaml": {"path": "results/camp1.yaml"}
                }
            }
        }
        mock_store_class.return_value = mock_store

        mock_indexer = Mock()
        mock_indexer_class.return_value = mock_indexer

        result = run_async(cmd_knowledge_tag(mock_args))

        assert result == 0
        mock_store._write_index.assert_called()


class TestKnowledgeLink:
    """Tests for knowledge link command."""

    @pytest.fixture
    def mock_args(self):
        """Create mock args for link command."""
        args = argparse.Namespace()
        args.sqx_path = "knowledge"
        args.list = False
        args.parent = None
        args.children = None
        args.json = False
        args.campaign_id = None
        return args

    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_link_list(self, mock_store_class, mock_args):
        """Test listing links for a campaign."""
        mock_args.list = True
        mock_args.campaign_id = "camp1"

        mock_store = Mock()
        mock_store.get_links.return_value = {"parents": ["parent1"], "children": ["child1", "child2"]}
        mock_store_class.return_value = mock_store

        result = run_async(cmd_knowledge_link(mock_args))

        assert result == 0
        mock_store.get_links.assert_called_once_with("camp1")

    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_link_create(self, mock_store_class, mock_args):
        """Test creating parent-child links."""
        mock_args.parent = "parent1"
        mock_args.children = ["child1", "child2"]

        mock_store = Mock()
        mock_store.link.return_value = True
        mock_store_class.return_value = mock_store

        result = run_async(cmd_knowledge_link(mock_args))

        assert result == 0
        mock_store.link.assert_called_once_with("parent1", ["child1", "child2"])

    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_link_create_parent_not_found(self, mock_store_class, mock_args):
        """Test creating links when parent not found."""
        mock_args.parent = "parent1"
        mock_args.children = ["child1"]

        mock_store = Mock()
        mock_store.link.return_value = False
        mock_store_class.return_value = mock_store

        result = run_async(cmd_knowledge_link(mock_args))

        assert result == 1

    def test_link_invalid_args(self, mock_args):
        """Test link with invalid args (neither list nor parent+children)."""
        mock_args.list = False
        mock_args.parent = None
        mock_args.children = None

        result = run_async(cmd_knowledge_link(mock_args))

        assert result == 1


class TestKnowledgeExport:
    """Tests for knowledge export command."""

    @pytest.fixture
    def mock_args(self):
        """Create mock args for export command."""
        args = argparse.Namespace()
        args.sqx_path = "knowledge"
        args.json = False
        args.sharpe = None
        args.profit_factor = None
        args.win_rate = None
        args.max_drawdown = None
        args.tags = None
        args.date = None
        args.text = None
        args.sort = "created"
        args.desc = True
        args.limit = 50
        args.offset = 0
        args.format = "csv"
        args.output = "/tmp/export.csv"
        return args

    @patch('quantlab.cli.knowledge_commands.QueryBuilder')
    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_export_csv(self, mock_store_class, mock_builder_class, mock_args, tmp_path):
        """Test export to CSV."""
        mock_args.output = str(tmp_path / "export.csv")

        mock_store = Mock()
        mock_store.read_index.return_value = {"directories": {"results": {}}}
        mock_store_class.return_value = mock_store

        mock_builder = Mock()
        mock_campaign = Mock()
        mock_campaign.campaign_id = "camp1"
        mock_campaign.name = "Campaign 1"
        mock_campaign.metrics = CampaignMetrics(
            sharpe_ratio=1.5,
            profit_factor=1.8,
            win_rate=0.65,
            max_drawdown=5.0,
            total_trades=100,
            net_profit=5000.0
        )
        mock_campaign.tags = ["trend"]
        mock_campaign.created = datetime(2024, 1, 1)
        mock_campaign.path = Path("results/camp1")

        mock_builder.execute.return_value = QueryResult(
            campaigns=[mock_campaign],
            total_count=1,
            query_time_ms=1.0
        )
        mock_builder_class.return_value = mock_builder

        result = run_async(cmd_knowledge_export(mock_args))

        assert result == 0
        assert Path(mock_args.output).exists()

        # Verify CSV content
        with open(mock_args.output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["campaign_id"] == "camp1"

    @patch('quantlab.cli.knowledge_commands.QueryBuilder')
    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_export_json(self, mock_store_class, mock_builder_class, mock_args, tmp_path):
        """Test export to JSON."""
        mock_args.format = "json"
        mock_args.output = str(tmp_path / "export.json")

        mock_store = Mock()
        mock_store.read_index.return_value = {"directories": {"results": {}}}
        mock_store_class.return_value = mock_store

        mock_builder = Mock()
        mock_campaign = Mock()
        mock_campaign.campaign_id = "camp1"
        mock_campaign.name = "Campaign 1"
        mock_campaign.metrics = CampaignMetrics(
            sharpe_ratio=1.5,
            profit_factor=1.8,
            win_rate=0.65,
            max_drawdown=5.0,
            total_trades=100,
            net_profit=5000.0
        )
        mock_campaign.tags = ["trend"]
        mock_campaign.created = datetime(2024, 1, 1)
        mock_campaign.path = Path("results/camp1")

        mock_builder.execute.return_value = QueryResult(
            campaigns=[mock_campaign],
            total_count=1,
            query_time_ms=1.0
        )
        mock_builder_class.return_value = mock_builder

        result = run_async(cmd_knowledge_export(mock_args))

        assert result == 0
        assert Path(mock_args.output).exists()

        with open(mock_args.output) as f:
            data = json.load(f)
            assert len(data) == 1
            assert data[0]["campaign_id"] == "camp1"

    @patch('quantlab.cli.knowledge_commands.QueryBuilder')
    @patch('quantlab.cli.knowledge_commands.KnowledgeStore')
    def test_export_empty_results(self, mock_store_class, mock_builder_class, mock_args, tmp_path):
        """Test export with no results."""
        mock_args.output = str(tmp_path / "export.csv")

        mock_store = Mock()
        mock_store.read_index.return_value = {"directories": {}}
        mock_store_class.return_value = mock_store

        mock_builder = Mock()
        mock_builder.execute.return_value = QueryResult(
            campaigns=[],
            total_count=0,
            query_time_ms=1.0
        )
        mock_builder_class.return_value = mock_builder

        result = run_async(cmd_knowledge_export(mock_args))

        assert result == 0
        assert Path(mock_args.output).exists()

        # Verify CSV has only headers
        with open(mock_args.output) as f:
            content = f.read()
            assert "campaign_id" in content
            assert "sharpe_ratio" in content


class TestKnowledgeSubparser:
    """Tests for knowledge subparser registration."""

    def test_add_knowledge_subparser(self):
        """Test that knowledge subparser is added correctly."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command", required=True)
        add_knowledge_subparser(subparsers)

        # Test query subcommand
        args = parser.parse_args(["knowledge", "query", "--sharpe", ">1.5"])
        assert args.command == "knowledge"
        assert args.knowledge_cmd == "query"
        assert args.sharpe == ">1.5"
        assert hasattr(args, 'func')

        # Test tag subcommand
        args = parser.parse_args(["knowledge", "tag", "camp1", "trend", "momentum"])
        assert args.knowledge_cmd == "tag"
        assert args.campaign_id == "camp1"
        assert args.tags == ["trend", "momentum"]

        # Test link subcommand
        args = parser.parse_args(["knowledge", "link", "--parent", "p1", "--children", "c1", "c2"])
        assert args.knowledge_cmd == "link"
        assert args.parent == "p1"
        assert args.children == ["c1", "c2"]

        # Test export subcommand
        args = parser.parse_args(["knowledge", "export", "--output", "out.csv"])
        assert args.knowledge_cmd == "export"
        assert args.output == "out.csv"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])