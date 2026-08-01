"""Databank export readers — CSV and XLSX parsers.

Parses StrategyQuant Databank export files (CSV and XLSX formats)
into the structured Pydantic models defined in ``readers.models``.
Supports trades, equity curves, and summary statistics with
format-agnostic output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from quantlab.readers.models import EquityPoint, StrategySummary, SummaryStats, Trade
from quantlab.tools.exceptions import ParseError

# ── Expected column name mappings ─────────────────────────────────────────────

TRADE_COLUMNS = {
    "entry_time": ["EntryTime", "Entry Time", "entry_time", "OpenTime"],
    "exit_time": ["ExitTime", "Exit Time", "exit_time", "CloseTime"],
    "direction": ["Direction", "Type", "direction", "Position"],
    "lots": ["Lots", "Volume", "lots", "Size"],
    "profit": ["Profit", "profit", "NetProfit", "P&L"],
    "drawdown": ["Drawdown", "DD", "drawdown", "MaxDD"],
}

EQUITY_COLUMNS = {
    "timestamp": ["Time", "Timestamp", "DateTime", "Date"],
    "equity": ["Equity", "Balance", "equity", "Value"],
}

SUMMARY_FIELDS = {
    "net_profit": "net_profit",
    "total_trades": "total_trades",
    "win_rate": "win_rate",
    "max_drawdown": "max_drawdown",
    "profit_factor": "profit_factor",
    "sharpe_ratio": "sharpe_ratio",
}

STRATEGY_COLUMNS = {
    "strategy_name": ["Name", "Strategy", "StrategyName"],
    "profit_factor": ["Profit Factor", "PF", "ProfitFactor"],
    "sharpe_ratio": ["Sharpe Ratio", "Sharpe", "SharpeRatio"],
    "win_rate": ["Win Rate", "WinRate", "Win %"],
    "total_trades": ["Trades", "Total Trades", "TradesCount"],
    "max_drawdown": ["Max DD", "MaxDrawdown", "Max Drawdown"],
    "mc_p10": ["MC p10", "MC P10", "Monte Carlo p10"],
    "wf_is_sharpe": ["WF IS Sharpe", "IS Sharpe"],
    "wf_oos_sharpe": ["WF OOS Sharpe", "OOS Sharpe"],
    "wf_cycles": ["WF Cycles", "WF_Cycles"],
}


def _find_column(columns: list[str], aliases: list[str]) -> Optional[str]:
    """Find the first matching column name from a list of aliases."""
    for alias in aliases:
        if alias in columns:
            return alias
    return None


def _parse_trades(df: pd.DataFrame) -> list[Trade]:
    """Parse a trades DataFrame into a list of Trade models."""
    cols = list(df.columns)
    mapped: dict[str, str] = {}

    for field, aliases in TRADE_COLUMNS.items():
        col = _find_column(cols, aliases)
        if col:
            mapped[field] = col

    missing = [f for f in TRADE_COLUMNS if f not in mapped and f != "drawdown"]
    if missing:
        raise ParseError(
            f"Missing required trade columns: {', '.join(missing)}. "
            f"Found columns: {', '.join(cols)}"
        )

    trades: list[Trade] = []
    for _, row in df.iterrows():
        trades.append(
            Trade(
                entry_time=pd.Timestamp(row[mapped["entry_time"]]).to_pydatetime(),
                exit_time=pd.Timestamp(row[mapped["exit_time"]]).to_pydatetime(),
                direction=str(row[mapped["direction"]]).strip().upper(),
                lots=float(row[mapped["lots"]]),
                profit=float(row[mapped["profit"]]),
                drawdown=float(row[mapped.get("drawdown", "")]) if mapped.get("drawdown") and pd.notna(row.get(mapped["drawdown"], None)) else 0.0,
            )
        )

    return trades


def _parse_equity(df: pd.DataFrame) -> list[EquityPoint]:
    """Parse an equity curve DataFrame into a list of EquityPoint models."""
    cols = list(df.columns)
    mapped: dict[str, str] = {}

    for field, aliases in EQUITY_COLUMNS.items():
        col = _find_column(cols, aliases)
        if col:
            mapped[field] = col

    if "timestamp" not in mapped or "equity" not in mapped:
        # No equity columns found — return empty list
        return []

    points: list[EquityPoint] = []
    for _, row in df.iterrows():
        points.append(
            EquityPoint(
                timestamp=pd.Timestamp(row[mapped["timestamp"]]).to_pydatetime(),
                equity=float(row[mapped["equity"]]),
            )
        )

    return points


def _parse_summary(df: pd.DataFrame) -> SummaryStats:
    """Parse a summary statistics DataFrame into a SummaryStats model.

    Expects a single-row or two-column (key, value) layout.
    """
    if df.empty:
        return SummaryStats()

    row = df.iloc[0].to_dict()
    # If the DataFrame has exactly two columns and one is a key column
    if len(df.columns) == 2:
        key_col = df.columns[0]
        val_col = df.columns[1]
        kv = dict(zip(df[key_col].astype(str), df[val_col]))
        row = kv

    return SummaryStats(
        net_profit=_safe_float(row.get("net_profit") or row.get("NetProfit") or row.get("Net Profit")),
        total_trades=_safe_int(row.get("total_trades") or row.get("TotalTrades") or row.get("Total Trades")),
        win_rate=_safe_float(row.get("win_rate") or row.get("WinRate") or row.get("Win Rate")),
        max_drawdown=_safe_float(row.get("max_drawdown") or row.get("MaxDrawdown") or row.get("Max Drawdown") or row.get("MaxDD")),
        profit_factor=_safe_float(row.get("profit_factor") or row.get("ProfitFactor") or row.get("Profit Factor")),
        sharpe_ratio=_safe_float(row.get("sharpe_ratio") or row.get("SharpeRatio") or row.get("Sharpe Ratio")),
    )


def _parse_strategies(df: pd.DataFrame) -> list[StrategySummary]:
    """Parse a strategies DataFrame into a list of StrategySummary models.

    Unknown columns are ignored; absent mapped columns yield None.
    """
    cols = list(df.columns)
    mapped: dict[str, str] = {}

    for field, aliases in STRATEGY_COLUMNS.items():
        col = _find_column(cols, aliases)
        if col:
            mapped[field] = col

    strategies: list[StrategySummary] = []
    for _, row in df.iterrows():
        strategies.append(
            StrategySummary(
                strategy_name=(
                    str(row[mapped["strategy_name"]]).strip()
                    if mapped.get("strategy_name")
                    else None
                ),
                profit_factor=_safe_float(row.get(mapped["profit_factor"])) if mapped.get("profit_factor") else None,
                sharpe_ratio=_safe_float(row.get(mapped["sharpe_ratio"])) if mapped.get("sharpe_ratio") else None,
                win_rate=_safe_float(row.get(mapped["win_rate"])) if mapped.get("win_rate") else None,
                total_trades=_safe_int(row.get(mapped["total_trades"])) if mapped.get("total_trades") else None,
                max_drawdown=_safe_float(row.get(mapped["max_drawdown"])) if mapped.get("max_drawdown") else None,
                mc_p10=_safe_float(row.get(mapped["mc_p10"])) if mapped.get("mc_p10") else None,
                wf_is_sharpe=_safe_float(row.get(mapped["wf_is_sharpe"])) if mapped.get("wf_is_sharpe") else None,
                wf_oos_sharpe=_safe_float(row.get(mapped["wf_oos_sharpe"])) if mapped.get("wf_oos_sharpe") else None,
                wf_cycles=_safe_int(row.get(mapped["wf_cycles"])) if mapped.get("wf_cycles") else None,
            )
        )

    return strategies


def _safe_float(value: object) -> Optional[float]:
    """Safely convert a value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value: object) -> Optional[int]:
    """Safely convert a value to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def read_strategies(path: str | Path) -> list[StrategySummary]:
    """Parse a strategies CSV into a list of StrategySummary models.

    Args:
        path: Path to the CSV file.

    Returns:
        A list of StrategySummary models.

    Raises:
        ParseError: If the CSV is corrupted or cannot be read.
    """
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        raise ParseError(f"Failed to read CSV: {exc}") from exc

    return _parse_strategies(df)


# ── Public readers ────────────────────────────────────────────────────────────


class DatabankCSVReader:
    """Reader for Databank CSV exports.

    Parses CSV files exported from StrategyQuant Databank into
    ``Trade[]``, ``EquityPoint[]``, and ``SummaryStats`` models.

    Usage::

        reader = DatabankCSVReader()
        trades = reader.read_trades("path/to/trades.csv")
        equity = reader.read_equity("path/to/equity.csv")
        summary = reader.read_summary("path/to/summary.csv")
    """

    def read_trades(self, path: str | Path) -> list[Trade]:
        """Parse a trades CSV into a list of Trade models.

        Args:
            path: Path to the CSV file.

        Returns:
            A list of Trade models.

        Raises:
            ParseError: If the CSV is missing required columns or
                cannot be read.
        """
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            raise ParseError(f"Failed to read CSV: {exc}") from exc

        return _parse_trades(df)

    def read_equity(self, path: str | Path) -> list[EquityPoint]:
        """Parse an equity curve CSV into a list of EquityPoint models.

        Args:
            path: Path to the CSV file.

        Returns:
            A list of EquityPoint models (empty list if no equity
            columns found).
        """
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            raise ParseError(f"Failed to read CSV: {exc}") from exc

        return _parse_equity(df)

    def read_summary(self, path: str | Path) -> SummaryStats:
        """Parse a summary statistics CSV into a SummaryStats model.

        Args:
            path: Path to the CSV file.

        Returns:
            A SummaryStats model with available fields populated.
        """
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            raise ParseError(f"Failed to read CSV: {exc}") from exc

        return _parse_summary(df)

    def read_strategies(self, path: str | Path) -> list[StrategySummary]:
        """Parse a strategies CSV into a list of StrategySummary models.

        Args:
            path: Path to the CSV file.

        Returns:
            A list of StrategySummary models.

        Raises:
            ParseError: If the CSV is corrupted or cannot be read.
        """
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            raise ParseError(f"Failed to read CSV: {exc}") from exc

        return _parse_strategies(df)


class DatabankXLSXReader:
    """Reader for Databank XLSX exports.

    Parses XLSX files exported from StrategyQuant Databank into
    the same model types as ``DatabankCSVReader``. Output is
    format-agnostic — identical data produces identical models.

    Usage::

        reader = DatabankXLSXReader()
        trades = reader.read_trades("path/to/trades.xlsx")
        equity = reader.read_equity("path/to/equity.xlsx")
        summary = reader.read_summary("path/to/summary.xlsx")
    """

    def read_trades(self, path: str | Path) -> list[Trade]:
        """Parse a trades XLSX sheet into a list of Trade models.

        Args:
            path: Path to the XLSX file.

        Returns:
            A list of Trade models.

        Raises:
            ParseError: If the XLSX is corrupted, missing required
                columns, or cannot be read.
        """
        try:
            df = pd.read_excel(path, engine="openpyxl")
        except Exception as exc:
            raise ParseError(f"Failed to read XLSX: {exc}") from exc

        return _parse_trades(df)

    def read_equity(self, path: str | Path) -> list[EquityPoint]:
        """Parse an equity curve XLSX sheet into EquityPoint models."""
        try:
            df = pd.read_excel(path, engine="openpyxl")
        except Exception as exc:
            raise ParseError(f"Failed to read XLSX: {exc}") from exc

        return _parse_equity(df)

    def read_summary(self, path: str | Path) -> SummaryStats:
        """Parse a summary statistics XLSX sheet into a SummaryStats."""
        try:
            df = pd.read_excel(path, engine="openpyxl")
        except Exception as exc:
            raise ParseError(f"Failed to read XLSX: {exc}") from exc

        return _parse_summary(df)
