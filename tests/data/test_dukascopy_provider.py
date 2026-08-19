"""RED tests for the Dukascopy research data provider (G3).

Spec: dukascopy-research-data "Dukascopy Market Data Provider" —
normalized OHLC Bars for M1/M5/H1 via DataManager → JForexProvider;
missing history fails closed (returns no data without raising).

Strict TDD: written first — FAIL until ``DukascopyProvider`` exists.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from quantlab.data import DataManager
from quantlab.data.datasource_registry import DatasourceHandler, DatasourceRegistry
from quantlab.data.market.models import Bar


# ── Helpers ────────────────────────────────────────────────────────────────────


def _sample_bars(count: int = 40) -> list[Bar]:
    """Deterministic rising Bar series (normalized, aware UTC)."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Bar(
            timestamp=base + timedelta(hours=i),
            open=1.10 + i * 0.01,
            high=1.11 + i * 0.01,
            low=1.09 + i * 0.01,
            close=1.10 + i * 0.01,
            volume=1000.0,
        )
        for i in range(count)
    ]


class _FakeJForexHandler(DatasourceHandler):
    """Minimal jforex handler returning a fixed bar list (hermetic)."""

    name = "jforex"

    def __init__(self, bars: list[Bar]) -> None:
        self.bars = bars
        self.requests: list[tuple[str, str]] = []

    def sqx_name(self, symbol: str, datatype: str) -> str:
        return f"{symbol}_{datatype}_jforex"

    async def ensure(self, symbol: str, datatype: str, sqx_name: str) -> None:  # noqa: ARG002
        return None

    async def update(self, symbol: str, datatype: str, sqx_name: str) -> None:  # noqa: ARG002
        return None

    def fetch_history(self, symbol: str, datatype: str) -> list[Bar]:
        self.requests.append((symbol, datatype))
        return self.bars


class _ExplodingJForexHandler(_FakeJForexHandler):
    """Handler whose fetch raises — the provider must never propagate."""

    def fetch_history(self, symbol: str, datatype: str) -> list[Bar]:
        raise RuntimeError("boom")


def _manager_with(bars: list[Bar]) -> DataManager:
    reg = DatasourceRegistry()
    reg.register(_FakeJForexHandler(bars))
    return DataManager(datasources=reg)


def _manager_with_empty_datasources() -> DataManager:
    return DataManager(datasources=DatasourceRegistry())


# ── TestDukascopyProviderFetch ─────────────────────────────────────────────────


class TestDukascopyProviderFetch:
    """fetch_bars returns normalized Bars; gaps are soft ([]), never raise."""

    def test_fetch_bars_returns_normalized_bars(self) -> None:
        from quantlab.data.dukascopy.provider import DukascopyProvider

        expected = _sample_bars()
        dm = _manager_with(expected)
        provider = DukascopyProvider(data_manager=dm)

        bars = provider.fetch_bars("EURUSD", "H1")

        assert bars == expected
        assert all(b.timestamp.tzinfo is not None for b in bars)
        assert all(b.timestamp == expected[i].timestamp for i, b in enumerate(bars))

    def test_fetch_bars_requests_exact_symbol_and_timeframe(self) -> None:
        from quantlab.data.dukascopy.provider import DukascopyProvider

        handler = _FakeJForexHandler(_sample_bars())
        reg = DatasourceRegistry()
        reg.register(handler)
        provider = DukascopyProvider(data_manager=DataManager(datasources=reg))

        provider.fetch_bars("EURUSD", "M5")

        assert handler.requests == [("EURUSD", "M5")]

    def test_fetch_bars_gap_returns_empty_list_without_raise(self) -> None:
        from quantlab.data.dukascopy.provider import DukascopyProvider

        provider = DukascopyProvider(data_manager=_manager_with([]))

        bars = provider.fetch_bars("EURUSD", "H1")

        assert bars == []

    def test_fetch_bars_missing_state_dir_returns_empty(self, tmp_path: Path) -> None:
        from quantlab.data.dukascopy.provider import DukascopyProvider

        provider = DukascopyProvider(jforex_state_dir=tmp_path / "does-not-exist")

        bars = provider.fetch_bars("EURUSD", "H1")

        assert bars == []

    def test_fetch_bars_missing_jforex_handler_returns_empty(self) -> None:
        from quantlab.data.dukascopy.provider import DukascopyProvider

        provider = DukascopyProvider(data_manager=_manager_with_empty_datasources())

        bars = provider.fetch_bars("EURUSD", "H1")

        assert bars == []

    def test_fetch_bars_invalid_symbol_returns_empty_without_raise(
        self, tmp_path: Path
    ) -> None:
        from quantlab.data.dukascopy.provider import DukascopyProvider

        # state_dir is set so the boundary-1 validation path runs before
        # any file lookup; "AAPL" fails the ^[A-Z]{6}$ symbol regex.
        provider = DukascopyProvider(jforex_state_dir=tmp_path)

        bars = provider.fetch_bars("AAPL", "H1")

        assert bars == []

    def test_fetch_bars_never_raises_on_handler_error(self) -> None:
        from quantlab.data.dukascopy.provider import DukascopyProvider

        reg = DatasourceRegistry()
        reg.register(_ExplodingJForexHandler(_sample_bars()))
        provider = DukascopyProvider(data_manager=DataManager(datasources=reg))

        bars = provider.fetch_bars("EURUSD", "H1")

        assert bars == []

    def test_fetch_bars_real_jforex_history_normalizes_bars(
        self, tmp_path: Path
    ) -> None:
        """Full real path: local JForex history JSON → normalized Bars."""
        from quantlab.data.dukascopy.provider import DukascopyProvider

        state_dir = tmp_path / "jforex"
        history_dir = state_dir / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        raw = [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "open": 1.10,
                "high": 1.11,
                "low": 1.09,
                "close": 1.105,
                "volume": 1000.0,
            },
            {
                "timestamp": "2026-01-01T01:00:00Z",
                "open": 1.105,
                "high": 1.115,
                "low": 1.095,
                "close": 1.110,
                "volume": 1200.0,
            },
        ]
        (history_dir / "EURUSD_H1_jforex.json").write_text(
            json.dumps(raw), encoding="utf-8"
        )

        provider = DukascopyProvider(jforex_state_dir=state_dir)
        bars = provider.fetch_bars("EURUSD", "H1")

        assert len(bars) == 2
        assert bars[0].open == 1.10
        assert bars[0].close == 1.105
        assert bars[0].timestamp == datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert bars[1].timestamp == datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)
        assert all(b.timestamp.tzinfo is not None for b in bars)