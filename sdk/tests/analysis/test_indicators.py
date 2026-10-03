"""WU2 RED tests: Technical indicators engine (REQ-311..314).

Covers selective computation, zone normalization (RSI/ATR/ADX), and
graceful handling of insufficient data via `zone="insufficient_data"`.

Strict TDD: written first — FAIL (RED) until `IndicatorEngine` exists.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


from quantlab.analysis.indicators import (
    IndicatorEngine,
    IndicatorResult as IndicatorResult,
)
from quantlab.data.market import Bar

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_bar(close: float, high: float, low: float, volume: float = 1000.0) -> Bar:
    """Create a Bar with a fixed UTC timestamp, varying OHLCV fields."""
    return Bar(
        timestamp=datetime(2024, 1, 2, 0, 0, tzinfo=UTC),
        open=close - 0.01,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _bars_from_closes(closes: list[float]) -> list[Bar]:
    """Build a deterministic Bar list from close prices only."""
    from datetime import timedelta

    result: list[Bar] = []
    base = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    for i, c in enumerate(closes):
        high = c + 0.01
        low = c - 0.01
        result.append(
            Bar(
                timestamp=base + timedelta(hours=i),
                open=c - 0.005,
                high=high,
                low=low,
                close=c,
                volume=1000.0,
            )
        )
    return result


# ── TestIndicatorEngineSelectiveCompute ────────────────────────────────────────


class TestIndicatorEngineSelectiveCompute:
    def test_only_requested_indicators_computed(self) -> None:
        """GIVEN a Bar list and indicators ['RSI', 'MACD']
        WHEN IndicatorEngine.compute is called
        THEN exactly 2 IndicatorResults are returned (RSI + MACD only).
        """
        bars = _bars_from_closes([1.10 + i * 0.01 for i in range(60)])
        engine = IndicatorEngine()
        results = engine.compute(bars, ["RSI", "MACD"])

        assert isinstance(results, list)
        assert len(results) == 2
        names = {r["indicator_name"] for r in results}
        assert names == {"RSI", "MACD"}

    def test_single_indicator_request(self) -> None:
        """GIVEN a Bar list and indicators ['ATR']
        WHEN IndicatorEngine.compute is called
        THEN exactly one IndicatorResult is returned.
        """
        bars = _bars_from_closes([1.10 + i * 0.01 for i in range(30)])
        engine = IndicatorEngine()
        results = engine.compute(bars, ["ATR"])

        assert len(results) == 1
        assert results[0]["indicator_name"] == "ATR"

    def test_empty_indicator_list_returns_empty(self) -> None:
        """GIVEN a Bar list and an empty indicator list
        WHEN IndicatorEngine.compute is called
        THEN an empty list is returned.
        """
        bars = _bars_from_closes([1.10 + i * 0.01 for i in range(30)])
        engine = IndicatorEngine()
        results = engine.compute(bars, [])

        assert results == []


# ── TestIndicatorResultZones ───────────────────────────────────────────────────


class TestIndicatorResultZones:
    def test_rsi_overbought_zone(self) -> None:
        """GIVEN RSI computed from an overbought series (>70)
        WHEN IndicatorEngine.compute is called with ['RSI']
        THEN the result zone is 'overbought'.
        """
        # Strong upward move pushes RSI well above 70.
        bars = _bars_from_closes([1.10 + i * 0.02 for i in range(30)])
        engine = IndicatorEngine()
        results = engine.compute(bars, ["RSI"])

        assert len(results) == 1
        rsi = results[0]
        assert rsi["indicator_name"] == "RSI"
        assert rsi["zone"] == "overbought"
        assert isinstance(rsi["value"], float)

    def test_rsi_oversold_zone(self) -> None:
        """GIVEN RSI computed from an oversold series (<30)
        WHEN IndicatorEngine.compute is called with ['RSI']
        THEN the result zone is 'oversold'.
        """
        # Strong downward move pushes RSI well below 30.
        bars = _bars_from_closes([1.20 - i * 0.02 for i in range(30)])
        engine = IndicatorEngine()
        results = engine.compute(bars, ["RSI"])

        assert len(results) == 1
        rsi = results[0]
        assert rsi["zone"] == "oversold"

    def test_rsi_neutral_zone(self) -> None:
        """GIVEN RSI computed from a sideways series
        WHEN IndicatorEngine.compute is called with ['RSI']
        THEN the result zone is 'neutral'.
        """
        bars = _bars_from_closes([1.10, 1.11, 1.10, 1.11, 1.10] * 8)
        engine = IndicatorEngine()
        results = engine.compute(bars, ["RSI"])

        assert len(results) == 1
        assert results[0]["zone"] == "neutral"

    def test_atr_high_zone(self) -> None:
        """GIVEN ATR computed from a volatility spike at the end
        WHEN IndicatorEngine.compute is called with ['ATR']
        THEN the result zone is 'high' (last ATR > 2x series median).
        """
        from datetime import timedelta

        base = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        bars: list[Bar] = []
        for i in range(40):
            if i < 37:
                close = 1.10
                high = close + 0.0005
                low = close - 0.0005
            else:
                close = 1.10 + (i - 37) * 0.10
                high = close + 0.50
                low = close - 0.50
            bars.append(
                Bar(
                    timestamp=base + timedelta(hours=i),
                    open=close,
                    high=high,
                    low=low,
                    close=close,
                    volume=1000.0,
                )
            )
        engine = IndicatorEngine()
        results = engine.compute(bars, ["ATR"])

        assert len(results) == 1
        assert results[0]["indicator_name"] == "ATR"
        assert results[0]["zone"] == "high"

    def test_atr_low_zone(self) -> None:
        """GIVEN ATR computed from a compression at the end
        WHEN IndicatorEngine.compute is called with ['ATR']
        THEN the result zone is 'low' (last ATR < 0.5x series median).
        """
        from datetime import timedelta

        base = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        bars: list[Bar] = []
        for i in range(60):
            # First 40 bars have wide range; last 20 compress.
            if i < 40:
                close = 1.10 + (i % 5) * 0.05
                high = close + 0.10
                low = close - 0.10
            else:
                close = 1.10
                high = close + 0.0001
                low = close - 0.0001
            bars.append(
                Bar(
                    timestamp=base + timedelta(hours=i),
                    open=close,
                    high=high,
                    low=low,
                    close=close,
                    volume=1000.0,
                )
            )
        engine = IndicatorEngine()
        results = engine.compute(bars, ["ATR"])

        assert len(results) == 1
        assert results[0]["zone"] == "low"

    def test_adx_trending_zone(self) -> None:
        """GIVEN ADX computed from a strong trend
        WHEN IndicatorEngine.compute is called with ['ADX']
        THEN the result zone is 'trending'.
        """
        # Strong directional move.
        bars = _bars_from_closes([1.10 + i * 0.03 for i in range(40)])
        engine = IndicatorEngine()
        results = engine.compute(bars, ["ADX"])

        assert len(results) == 1
        assert results[0]["indicator_name"] == "ADX"
        assert results[0]["zone"] == "trending"

    def test_adx_range_zone(self) -> None:
        """GIVEN ADX computed from a choppy/range series
        WHEN IndicatorEngine.compute is called with ['ADX']
        THEN the result zone is 'range'.
        """
        bars = _bars_from_closes([1.10, 1.12, 1.10, 1.12, 1.10, 1.12, 1.10, 1.12] * 6)
        engine = IndicatorEngine()
        results = engine.compute(bars, ["ADX"])

        assert len(results) == 1
        assert results[0]["zone"] == "range"

    def test_bollinger_overbought_zone(self) -> None:
        """GIVEN Bollinger computed with a close far above the 2σ upper band
        WHEN IndicatorEngine.compute is called with ['Bollinger']
        THEN the result zone is 'overbought'.
        """
        base = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        bars: list[Bar] = []
        for i in range(19):
            bars.append(
                Bar(
                    timestamp=base + timedelta(hours=i),
                    open=1.10,
                    high=1.10 + 0.01,
                    low=1.10 - 0.01,
                    close=1.10,
                    volume=1000.0,
                )
            )
        # Spike closes far above the prior range.
        bars.append(
            Bar(
                timestamp=base + timedelta(hours=19),
                open=3.00,
                high=3.10,
                low=2.90,
                close=3.00,
                volume=1000.0,
            )
        )
        engine = IndicatorEngine()
        results = engine.compute(bars, ["Bollinger"])

        assert len(results) == 1
        assert results[0]["indicator_name"] == "Bollinger"
        assert results[0]["zone"] == "overbought"

    def test_bollinger_oversold_zone(self) -> None:
        """GIVEN Bollinger computed with a close far below the 2σ lower band
        WHEN IndicatorEngine.compute is called with ['Bollinger']
        THEN the result zone is 'oversold'.
        """
        base = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        bars: list[Bar] = []
        for i in range(19):
            bars.append(
                Bar(
                    timestamp=base + timedelta(hours=i),
                    open=3.00,
                    high=3.00 + 0.01,
                    low=3.00 - 0.01,
                    close=3.00,
                    volume=1000.0,
                )
            )
        # Spike closes far below the prior range.
        bars.append(
            Bar(
                timestamp=base + timedelta(hours=19),
                open=0.50,
                high=0.60,
                low=0.40,
                close=0.50,
                volume=1000.0,
            )
        )
        engine = IndicatorEngine()
        results = engine.compute(bars, ["Bollinger"])

        assert len(results) == 1
        assert results[0]["indicator_name"] == "Bollinger"
        assert results[0]["zone"] == "oversold"

    def test_sma_overbought_zone(self) -> None:
        """GIVEN SMA computed with close above the SMA
        WHEN IndicatorEngine.compute is called with ['SMA']
        THEN the result zone is 'overbought'.
        """
        closes = [1.10 + i * 0.02 for i in range(30)]
        bars = _bars_from_closes(closes)
        engine = IndicatorEngine()
        results = engine.compute(bars, ["SMA"])

        assert len(results) == 1
        assert results[0]["indicator_name"] == "SMA"
        assert results[0]["zone"] == "overbought"

    def test_sma_oversold_zone(self) -> None:
        """GIVEN SMA computed with close below the SMA
        WHEN IndicatorEngine.compute is called with ['SMA']
        THEN the result zone is 'oversold'.
        """
        closes = [1.20 - i * 0.02 for i in range(30)]
        bars = _bars_from_closes(closes)
        engine = IndicatorEngine()
        results = engine.compute(bars, ["SMA"])

        assert len(results) == 1
        assert results[0]["indicator_name"] == "SMA"
        assert results[0]["zone"] == "oversold"

    def test_ema_overbought_zone(self) -> None:
        """GIVEN EMA computed with close above the EMA
        WHEN IndicatorEngine.compute is called with ['EMA']
        THEN the result zone is 'overbought'.
        """
        closes = [1.10 + i * 0.02 for i in range(30)]
        bars = _bars_from_closes(closes)
        engine = IndicatorEngine()
        results = engine.compute(bars, ["EMA"])

        assert len(results) == 1
        assert results[0]["indicator_name"] == "EMA"
        assert results[0]["zone"] == "overbought"

    def test_ema_oversold_zone(self) -> None:
        """GIVEN EMA computed with close below the EMA
        WHEN IndicatorEngine.compute is called with ['EMA']
        THEN the result zone is 'oversold'.
        """
        closes = [1.20 - i * 0.02 for i in range(30)]
        bars = _bars_from_closes(closes)
        engine = IndicatorEngine()
        results = engine.compute(bars, ["EMA"])

        assert len(results) == 1
        assert results[0]["indicator_name"] == "EMA"
        assert results[0]["zone"] == "oversold"


# ── TestInsufficientData ───────────────────────────────────────────────────────


class TestInsufficientData:
    def test_empty_bar_list_returns_insufficient_data(self) -> None:
        """GIVEN an empty Bar list
        WHEN IndicatorEngine.compute is called with any indicator
        THEN returns IndicatorResult with zone='insufficient_data' and no exception.
        """
        engine = IndicatorEngine()
        results = engine.compute([], ["RSI", "MACD"])

        assert len(results) == 2
        for r in results:
            assert r["zone"] == "insufficient_data"
            assert r["indicator_name"] in {"RSI", "MACD"}

    def test_too_few_bars_returns_insufficient_data(self) -> None:
        """GIVEN 5 Bars and RSI(14) requested
        WHEN IndicatorEngine.compute is called
        THEN result has zone='insufficient_data' and no exception is raised.
        """
        bars = _bars_from_closes([1.10, 1.11, 1.10, 1.11, 1.10])
        engine = IndicatorEngine()
        results = engine.compute(bars, ["RSI"])

        assert len(results) == 1
        assert results[0]["zone"] == "insufficient_data"
        assert results[0]["indicator_name"] == "RSI"

    def test_unsupported_indicator_returns_insufficient_data(self) -> None:
        """GIVEN an indicator name that IndicatorEngine does not support
        WHEN compute is called
        THEN result has zone='insufficient_data' with reason in metadata.
        """
        bars = _bars_from_closes([1.10 + i * 0.01 for i in range(30)])
        engine = IndicatorEngine()
        results = engine.compute(bars, ["STOCH"])

        assert len(results) == 1
        assert results[0]["zone"] == "insufficient_data"
        assert "unsupported_indicator" in results[0]["metadata"].get("reason", "")

    def test_indicator_result_metadata_populated(self) -> None:
        """GIVEN a successful RSI computation
        WHEN compute returns the result
        THEN metadata contains the expected window key.
        """
        bars = _bars_from_closes([1.10 + i * 0.01 for i in range(30)])
        engine = IndicatorEngine()
        results = engine.compute(bars, ["RSI"])

        assert len(results) == 1
        assert "window" in results[0]["metadata"]
        assert results[0]["metadata"]["window"] == 14

    def test_all_nan_prices_returns_insufficient_data(self) -> None:
        """GIVEN a Bar list where every OHLCV field is NaN
        WHEN IndicatorEngine.compute is called
        THEN returns IndicatorResult with zone='insufficient_data' and no exception.
        """
        base = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        bars: list[Bar] = []
        for i in range(40):
            bars.append(
                Bar(
                    timestamp=base + timedelta(hours=i),
                    open=float("nan"),
                    high=float("nan"),
                    low=float("nan"),
                    close=float("nan"),
                    volume=float("nan"),
                )
            )
        engine = IndicatorEngine()
        results = engine.compute(
            bars, ["RSI", "MACD", "ATR", "ADX", "Bollinger", "SMA", "EMA"]
        )

        assert len(results) == 7
        for r in results:
            assert r["zone"] == "insufficient_data"
            assert "nan" in r["metadata"].get("reason", "")


class TestTaVersionPin:
    def test_pyproject_requires_ta_minimum_version(self) -> None:
        """GIVEN the project pyproject.toml
        WHEN we read dependencies
        THEN 'ta>=0.11.0' is present in install requirements.
        """
        import tomllib

        with open("sdk/pyproject.toml", "rb") as fh:
            config = tomllib.load(fh)

        deps = config["project"]["dependencies"]
        assert any(dep.strip().startswith("ta>=") for dep in deps)
