"""Tests for the Databank result readers — CSV and XLSX parsing."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from quantlab.readers.databank import DatabankCSVReader, DatabankXLSXReader, read_strategies
from quantlab.readers.models import (
    EquityPoint,
    StrategySummary,
    SummaryStats,
    Trade,
)
from quantlab.tools.exceptions import ParseError

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class TestDatabankCSVReader:
    """Tests for ``DatabankCSVReader`` — CSV format."""

    reader = DatabankCSVReader()

    def test_read_trades_valid_csv(self) -> None:
        """GIVEN a Databank CSV export containing 10 trades
        WHEN the reader parses the file
        THEN a list of 10 Trade models is returned with all fields populated.
        """
        trades = self.reader.read_trades(FIXTURES / "sample_trades.csv")

        assert isinstance(trades, list)
        assert len(trades) == 10
        assert all(isinstance(t, Trade) for t in trades)

        first = trades[0]
        assert first.direction == "LONG"
        assert first.lots == 0.1
        assert first.profit == 250.0
        assert first.drawdown == 50.0

    def test_read_trades_all_fields_populated(self) -> None:
        """All fields should be correctly parsed for each trade."""
        trades = self.reader.read_trades(FIXTURES / "sample_trades.csv")

        # Check a few specific trades
        assert trades[1].direction == "SHORT"
        assert trades[1].profit == -150.0
        assert trades[2].lots == 0.1
        assert trades[4].lots == 0.2

    def test_read_trades_missing_columns_raises_parse_error(self) -> None:
        """GIVEN a CSV file missing required columns (e.g., no "Profit")
        WHEN the reader attempts to parse
        THEN a ParseError is raised identifying the missing column.
        """
        with pytest.raises(ParseError, match="Missing"):
            self.reader.read_trades(FIXTURES / "missing_columns.csv")

    def test_read_equity_valid_csv(self) -> None:
        """GIVEN a Databank equity curve CSV with 12 data points
        WHEN the reader parses the equity curve
        THEN a list of 12 ordered equity points is returned.
        """
        equity = self.reader.read_equity(FIXTURES / "sample_equity.csv")

        assert isinstance(equity, list)
        assert len(equity) == 12
        assert all(isinstance(e, EquityPoint) for e in equity)

        # First point
        assert equity[0].equity == 100000.0
        # Last point
        assert equity[-1].equity == 100570.0

    def test_read_equity_ordering(self) -> None:
        """Equity points should maintain CSV row ordering."""
        equity = self.reader.read_equity(FIXTURES / "sample_equity.csv")
        values = [e.equity for e in equity]
        assert values == [
            100000.0, 100250.0, 100100.0, 100200.0, 100380.0,
            100300.0, 100620.0, 100820.0, 100420.0, 100620.0,
            100710.0, 100570.0,
        ]

    def test_read_summary_valid_csv(self) -> None:
        """GIVEN a Databank export with full summary statistics
        WHEN the reader parses the summary
        THEN a SummaryStats model is returned with all numeric fields.
        """
        summary = self.reader.read_summary(FIXTURES / "sample_summary.csv")

        assert isinstance(summary, SummaryStats)
        assert summary.net_profit == 1060.0
        assert summary.total_trades == 10
        assert summary.win_rate == 0.6
        assert summary.max_drawdown == 0.25
        assert summary.profit_factor == 2.65
        assert summary.sharpe_ratio == 1.42

    def test_read_equity_empty_columns_returns_empty_list(self) -> None:
        """GIVEN a CSV with no equity curve columns
        WHEN the reader parses it
        THEN an empty list is returned (not an error).
        """
        equity = self.reader.read_equity(FIXTURES / "sample_trades.csv")
        assert equity == []

    def test_corrupt_csv_raises_parse_error(self) -> None:
        """GIVEN a corrupted CSV file
        WHEN the reader attempts to parse
        THEN a ParseError is raised without crashing.
        """
        with pytest.raises(ParseError):
            self.reader.read_trades(FIXTURES / "corrupt.csv")

    def test_corrupt_csv_equity_returns_empty_list(self) -> None:
        """Corrupted CSV with no equity columns returns empty list."""
        equity = self.reader.read_equity(FIXTURES / "corrupt.csv")
        assert equity == []

    def test_nonexistent_file_raises_parse_error(self) -> None:
        """GIVEN a path to a file that does not exist
        WHEN the reader attempts to parse
        THEN a ParseError is raised.
        """
        with pytest.raises(ParseError, match="Failed to read"):
            self.reader.read_trades("/nonexistent/path/trades.csv")


class TestDatabankXLSXReader:
    """Tests for ``DatabankXLSXReader`` — XLSX format."""

    reader = DatabankXLSXReader()

    def test_nonexistent_file_raises_parse_error(self) -> None:
        """GIVEN a path to a non-existent XLSX file
        WHEN the reader attempts to parse
        THEN a ParseError is raised.
        """
        with pytest.raises(ParseError, match="Failed to read"):
            self.reader.read_trades("/nonexistent/path/trades.xlsx")


class TestTradeModel:
    """Tests for the ``Trade`` Pydantic model."""

    def test_minimal_trade(self) -> None:
        trade = Trade(
            entry_time="2024-01-01 08:00:00",
            exit_time="2024-01-01 16:00:00",
            direction="LONG",
            lots=0.1,
            profit=100.0,
        )
        assert trade.direction == "LONG"
        assert trade.lots == 0.1
        assert trade.profit == 100.0
        assert trade.drawdown == 0.0  # default

    def test_trade_with_drawdown(self) -> None:
        trade = Trade(
            entry_time="2024-01-01 08:00:00",
            exit_time="2024-01-01 16:00:00",
            direction="SHORT",
            lots=0.2,
            profit=-50.0,
            drawdown=25.0,
        )
        assert trade.drawdown == 25.0

    def test_trade_direction_validation(self) -> None:
        """Direction accepts any string — model is flexible."""
        trade = Trade(
            entry_time="2024-01-01 08:00:00",
            exit_time="2024-01-01 16:00:00",
            direction="long",  # lowercase ok
            lots=0.1,
            profit=50.0,
        )
        # The CSV reader uppercases, but the model accepts any string
        assert trade.direction == "long"


class TestEquityPointModel:
    """Tests for the ``EquityPoint`` Pydantic model."""

    def test_valid_equity_point(self) -> None:
        point = EquityPoint(
            timestamp="2024-01-01 00:00:00",
            equity=100000.0,
        )
        assert point.equity == 100000.0

    def test_negative_equity(self) -> None:
        """Equity can theoretically be negative."""
        point = EquityPoint(
            timestamp="2024-01-01 00:00:00",
            equity=-5000.0,
        )
        assert point.equity == -5000.0


class TestSummaryStatsModel:
    """Tests for the ``SummaryStats`` Pydantic model."""

    def test_default_fields_are_none(self) -> None:
        stats = SummaryStats()
        assert stats.net_profit is None
        assert stats.total_trades is None
        assert stats.win_rate is None

    def test_partial_fields(self) -> None:
        """GIVEN a Databank export missing the Sharpe ratio field
        WHEN the reader parses the summary
        THEN the missing field is set to None.
        """
        stats = SummaryStats(net_profit=1000.0, total_trades=50)
        assert stats.net_profit == 1000.0
        assert stats.total_trades == 50
        assert stats.win_rate is None
        assert stats.sharpe_ratio is None


class TestStrategySummaryModel:
    """Tests for the ``StrategySummary`` Pydantic model."""

    def test_default_fields_are_none(self) -> None:
        """GIVEN a StrategySummary with no fields
        WHEN the model is instantiated
        THEN all optional fields are None.
        """
        summary = StrategySummary()
        assert summary.strategy_name is None
        assert summary.profit_factor is None
        assert summary.total_trades is None

    def test_partial_fields(self) -> None:
        """GIVEN a StrategySummary with only strategy_name and profit_factor
        WHEN the model is instantiated
        THEN only those fields are populated; others remain None.
        """
        summary = StrategySummary(strategy_name="Test", profit_factor=2.5)
        assert summary.strategy_name == "Test"
        assert summary.profit_factor == 2.5
        assert summary.total_trades is None


class TestReadStrategies:
    """Tests for ``read_strategies`` — strategies databank parsing."""

    def test_alias_profit_factor_maps(self) -> None:
        """GIVEN a strategies CSV with column 'Profit Factor'
        WHEN read_strategies parses it
        THEN profit_factor is populated via alias mapping.
        """
        strategies = read_strategies(FIXTURES / "strategies.csv")
        assert len(strategies) == 5
        assert strategies[0].strategy_name == "Momentum_EMA_30"
        assert strategies[0].profit_factor == 1.85

    def test_alias_sharpe_ratio_maps(self) -> None:
        """GIVEN a strategies CSV with column 'Sharpe Ratio'
        WHEN read_strategies parses it
        THEN sharpe_ratio is populated via alias mapping.
        """
        strategies = read_strategies(FIXTURES / "strategies.csv")
        assert strategies[0].sharpe_ratio == 1.42

    def test_alias_win_rate_maps(self) -> None:
        """GIVEN a strategies CSV with column 'Win Rate'
        WHEN read_strategies parses it
        THEN win_rate is populated via alias mapping.
        """
        strategies = read_strategies(FIXTURES / "strategies.csv")
        assert strategies[0].win_rate == 0.61

    def test_alias_total_trades_maps(self) -> None:
        """GIVEN a strategies CSV with column 'Trades'
        WHEN read_strategies parses it
        THEN total_trades is populated via alias mapping.
        """
        strategies = read_strategies(FIXTURES / "strategies.csv")
        assert strategies[0].total_trades == 320

    def test_alias_max_drawdown_maps(self) -> None:
        """GIVEN a strategies CSV with column 'Max DD'
        WHEN read_strategies parses it
        THEN max_drawdown is populated via alias mapping.
        """
        strategies = read_strategies(FIXTURES / "strategies.csv")
        assert strategies[0].max_drawdown == 12.4

    def test_alias_mc_p10_maps(self) -> None:
        """GIVEN a strategies CSV with column 'MC p10'
        WHEN read_strategies parses it
        THEN mc_p10 is populated via alias mapping.
        """
        strategies = read_strategies(FIXTURES / "strategies.csv")
        assert strategies[0].mc_p10 == 2.5

    def test_alias_wf_is_sharpe_maps(self) -> None:
        """GIVEN a strategies CSV with column 'WF IS Sharpe'
        WHEN read_strategies parses it
        THEN wf_is_sharpe is populated via alias mapping.
        """
        strategies = read_strategies(FIXTURES / "strategies.csv")
        assert strategies[0].wf_is_sharpe == 1.55

    def test_alias_wf_oos_sharpe_maps(self) -> None:
        """GIVEN a strategies CSV with column 'WF OOS Sharpe'
        WHEN read_strategies parses it
        THEN wf_oos_sharpe is populated via alias mapping.
        """
        strategies = read_strategies(FIXTURES / "strategies.csv")
        assert strategies[0].wf_oos_sharpe == 1.31

    def test_alias_wf_cycles_maps(self) -> None:
        """GIVEN a strategies CSV with column 'WF Cycles'
        WHEN read_strategies parses it
        THEN wf_cycles is populated via alias mapping.
        """
        strategies = read_strategies(FIXTURES / "strategies.csv")
        assert strategies[0].wf_cycles == 8

    def test_unknown_columns_tolerated(self) -> None:
        """GIVEN a strategies CSV with unrecognized extra columns
        WHEN read_strategies parses it
        THEN known columns are mapped and unknown ones ignored without error.
        """
        strategies = read_strategies(FIXTURES / "strategies.csv")
        assert len(strategies) == 5
        # Extra columns like Recovery Factor, System Quality, Curve Score are ignored
        assert strategies[0].strategy_name is not None

    def test_absent_columns_none(self) -> None:
        """GIVEN a strategies CSV missing optional columns
        WHEN read_strategies parses it
        THEN absent fields are None.
        """
        # Create a minimal CSV with only strategy_name
        import tempfile

        import pandas as pd

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Name\n")
            f.write("TestStrategy\n")
            path = f.name

        try:
            strategies = read_strategies(path)
            assert len(strategies) == 1
            assert strategies[0].strategy_name == "TestStrategy"
            assert strategies[0].profit_factor is None
            assert strategies[0].sharpe_ratio is None
            assert strategies[0].total_trades is None
        finally:
            Path(path).unlink()

    def test_corrupt_csv_raises_parse_error(self) -> None:
        """GIVEN a corrupted CSV file
        WHEN read_strategies attempts to parse it
        THEN a ParseError is raised without crashing.
        """
        import tempfile

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as f:
            f.write(b"")
            path = f.name

        try:
            with pytest.raises(ParseError):
                read_strategies(path)
        finally:
            Path(path).unlink()

    def test_multiple_strategies_parsed(self) -> None:
        """GIVEN a strategies CSV with multiple rows
        WHEN read_strategies parses it
        THEN all strategies are returned in order.
        """
        strategies = read_strategies(FIXTURES / "strategies.csv")
        assert len(strategies) == 5
        names = [s.strategy_name for s in strategies]
        assert names == [
            "Momentum_EMA_30",
            "MeanRev_RSI_14",
            "Breakout_ATR_5",
            "Trend_Follow_200",
            "Scalp_Boll_20",
        ]

    def test_nonexistent_file_raises_parse_error(self) -> None:
        """GIVEN a path to a file that does not exist
        WHEN read_strategies attempts to parse
        THEN a ParseError is raised.
        """
        with pytest.raises(ParseError, match="Failed to read"):
            read_strategies("/nonexistent/path/strategies.csv")
