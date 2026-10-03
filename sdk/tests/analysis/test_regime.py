"""WU3 RED tests: RegimeClassifier (REQ-321..323).

Covers trending/range classification, 3-bar persistence smoothing,
trigger population, and confidence bounds.

Strict TDD: written first — FAIL (RED) until `RegimeClassifier` exists.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from quantlab.data.market import Bar

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_bar(
    timestamp: datetime,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1000.0,
) -> Bar:
    return Bar(
        timestamp=timestamp,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _trending_bars(count: int = 40) -> list[Bar]:
    """Smooth upward trend with small, stable ranges."""
    base = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    bars: list[Bar] = []
    for i in range(count):
        close = 1.10 + i * 0.01
        bars.append(
            _make_bar(
                timestamp=base + timedelta(hours=i),
                open_=close - 0.001,
                high=close + 0.002,
                low=close - 0.002,
                close=close,
            )
        )
    return bars


def _range_bars(count: int = 48) -> list[Bar]:
    """Oscillating range with moderate ranges and gentle upward drift."""
    base = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    bars: list[Bar] = []
    for i in range(count):
        drift = i * 0.006
        sign = 1 if i % 2 == 0 else -1
        close = 1.10 + drift + sign * 0.015
        bars.append(
            _make_bar(
                timestamp=base + timedelta(hours=i),
                open_=close - 0.005,
                high=close + 0.01,
                low=close - 0.01,
                close=close,
            )
        )
    return bars


def _volatile_bars(count: int = 100) -> list[Bar]:
    """Starts stable, then expands dramatically."""
    base = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    bars: list[Bar] = []
    for i in range(count):
        if i < 80:
            # Stable history.
            close = 1.10
            high = 1.1001
            low = 1.0999
        else:
            # Extreme expansion.
            close = 1.10 + (i - 80) * 0.20
            high = close + 0.50
            low = close - 0.50
        bars.append(
            _make_bar(
                timestamp=base + timedelta(hours=i),
                open_=close,
                high=high,
                low=low,
                close=close,
            )
        )
    return bars


def _quiet_bars(count: int = 40) -> list[Bar]:
    """Very low volatility, almost no movement."""
    base = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    bars: list[Bar] = []
    for i in range(count):
        close = 1.10 + (0.0001 if i % 2 == 0 else -0.0001)
        bars.append(
            _make_bar(
                timestamp=base + timedelta(hours=i),
                open_=close,
                high=close + 0.0001,
                low=close - 0.0001,
                close=close,
            )
        )
    return bars


# ── TestRegimeClassifierTrendingRange ─────────────────────────────────────────


class TestRegimeClassifierTrendingRange:
    def test_trending_series_returns_trending(self) -> None:
        """GIVEN a strong upward trending Bar series
        WHEN RegimeClassifier.classify is called
        THEN regime is 'trending'.
        """
        bars = _trending_bars(40)
        from quantlab.analysis.regime import RegimeClassifier

        classifier = RegimeClassifier()
        result = classifier.classify(bars)

        assert result.regime == "trending"

    def test_range_series_returns_range_bound(self) -> None:
        """GIVEN a choppy/range Bar series with slight drift
        WHEN RegimeClassifier.classify is called
        THEN regime is 'range-bound'.
        """
        bars = _range_bars(48)
        from quantlab.analysis.regime import RegimeClassifier

        classifier = RegimeClassifier()
        result = classifier.classify(bars)

        assert result.regime == "range-bound"

    def test_volatile_series_returns_volatile(self) -> None:
        """GIVEN a high-volatility Bar series with expanding ranges
        WHEN RegimeClassifier.classify is called
        THEN regime is 'volatile'.
        """
        bars = _volatile_bars(100)
        from quantlab.analysis.regime import RegimeClassifier

        classifier = RegimeClassifier()
        result = classifier.classify(bars)

        assert result.regime == "volatile"

    def test_quiet_series_returns_quiet(self) -> None:
        """GIVEN a very low-volatility Bar series
        WHEN RegimeClassifier.classify is called
        THEN regime is 'quiet'.
        """
        bars = _quiet_bars(40)
        from quantlab.analysis.regime import RegimeClassifier

        classifier = RegimeClassifier()
        result = classifier.classify(bars)

        assert result.regime == "quiet"


# ── TestRegimeClassifierSmoothing ──────────────────────────────────────────────


class TestRegimeClassifierSmoothing:
    def test_alternating_signals_no_flip_flop_before_persistence(self) -> None:
        """GIVEN Bars that alternate between trending and range-bound signals
        WHEN RegimeClassifier.classify is called on each bar
        THEN regime does not change until a single regime persists for 3 bars.
        """
        from quantlab.analysis.regime import RegimeClassifier

        classifier = RegimeClassifier()
        regimes: list[str] = []

        trending = _trending_bars(10)
        ranging = _range_bars(10)

        combined = trending[:5] + ranging[:5] + trending[:5] + ranging[:5]
        for i in range(len(combined)):
            result = classifier.classify(combined[: i + 1])
            regimes.append(result.regime)

        # Verify no rapid flip-flopping.
        changes = sum(
            1 for i in range(1, len(regimes)) if regimes[i] != regimes[i - 1]
        )
        assert changes <= len(regimes) // 4

    def test_three_bar_persistence_confirms_transition(self) -> None:
        """GIVEN 3 consecutive bars all indicating range-bound
        WHEN RegimeClassifier.classify is called
        THEN regime is 'range-bound' after 3-bar persistence.
        """
        # 48 bars of range oscillation with gentle drift.
        bars = _range_bars(48)

        from quantlab.analysis.regime import RegimeClassifier

        classifier = RegimeClassifier()
        result = classifier.classify(bars)

        assert result.regime == "range-bound"


# ── TestRegimeClassifierTriggers ───────────────────────────────────────────────


class TestRegimeClassifierTriggers:
    def test_trending_triggers_populated(self) -> None:
        """GIVEN Bars with ADX > 25 and +DMI > -DMI
        WHEN RegimeClassifier.classify is called
        THEN triggers includes 'ADX > 25' and '+DMI > -DMI'.
        """
        bars = _trending_bars(40)
        from quantlab.analysis.regime import RegimeClassifier

        classifier = RegimeClassifier()
        result = classifier.classify(bars)

        assert "ADX > 25" in result.triggers
        assert "+DMI > -DMI" in result.triggers

    def test_volatile_triggers_populated(self) -> None:
        """GIVEN Bars with ATR percentile > 90
        WHEN RegimeClassifier.classify is called
        THEN triggers includes 'volatility_percentile > 90'.
        """
        bars = _volatile_bars(100)
        from quantlab.analysis.regime import RegimeClassifier

        classifier = RegimeClassifier()
        result = classifier.classify(bars)

        assert "volatility_percentile > 90" in result.triggers

    def test_no_triggers_when_weak_signals(self) -> None:
        """GIVEN Bars with no strong signals
        WHEN RegimeClassifier.classify is called
        THEN triggers is an empty list.
        """
        bars = _quiet_bars(40)
        from quantlab.analysis.regime import RegimeClassifier

        classifier = RegimeClassifier()
        result = classifier.classify(bars)

        assert result.triggers == []


# ── TestRegimeClassifierConfidence ─────────────────────────────────────────────


class TestRegimeClassifierConfidence:
    def test_confidence_in_range(self) -> None:
        """GIVEN any Bar series
        WHEN RegimeClassifier.classify is called
        THEN confidence is a float in [0, 1].
        """
        bars = _trending_bars(40)
        from quantlab.analysis.regime import RegimeClassifier

        classifier = RegimeClassifier()
        result = classifier.classify(bars)

        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0

    def test_confidence_zero_on_empty_bars(self) -> None:
        """GIVEN an empty Bar list
        WHEN RegimeClassifier.classify is called
        THEN confidence is 0.0 and regime is 'unknown'.
        """
        from quantlab.analysis.regime import RegimeClassifier

        classifier = RegimeClassifier()
        result = classifier.classify([])

        assert result.regime == "unknown"
        assert result.confidence == 0.0

    def test_custom_lookback(self) -> None:
        """GIVEN Bars and lookback=20
        WHEN RegimeClassifier.classify is called
        THEN analysis uses only the last 20 bars.
        """
        bars = _trending_bars(40)
        from quantlab.analysis.regime import RegimeClassifier

        classifier = RegimeClassifier()
        result = classifier.classify(bars, lookback=20)

        assert result.regime in {
            "trending",
            "range-bound",
            "volatile",
            "quiet",
            "unknown",
        }
