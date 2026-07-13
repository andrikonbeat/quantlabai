"""Tests for the Databank result readers — CSV and XLSX parsing."""

from pathlib import Path

import pytest

from quantlab.readers.databank import DatabankCSVReader, DatabankXLSXReader
from quantlab.readers.models import EquityPoint, SummaryStats, Trade
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
