"""Regime classifier with 3-bar persistence smoothing.

Outputs are contextual regimes (trending, range-bound, volatile, quiet),
NOT entry/exit signals.  Perception layer only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
from ta.trend import ADXIndicator

from quantlab.data.market import Bar

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegimeResult:
    """Regime classification result."""

    regime: Literal["trending", "range-bound", "volatile", "quiet", "unknown"]
    confidence: float
    triggers: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percentile(series: pd.Series, value: float) -> float:
    """Return the fraction of historical values strictly less than `value`."""
    clean = series.dropna()
    if clean.empty:
        return 0.0
    return float((clean < value).mean())


def _true_range(df: pd.DataFrame) -> pd.Series:
    """Compute True Range series from OHLC DataFrame."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def _sma_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """Simple moving average ATR (stable, no Wilder ramp-up)."""
    tr = _true_range(df)
    return tr.rolling(window=window, min_periods=window).mean()


def _adx_trend_signal(adx: float, plus_di: float, minus_di: float) -> bool:
    return adx > 25 and plus_di > minus_di


def _volatility_signal(atr_percentile: float) -> bool:
    return atr_percentile > 0.90


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class RegimeClassifier:
    """Classify market regime from OHLCV bars with 3-bar persistence smoothing."""

    def __init__(self) -> None:
        self._history: list[str] = []

    def classify(self, bars: list[Bar], lookback: int = 20) -> RegimeResult:
        """Return regime + confidence for the latest bar window.

        Args:
            bars: Full bar list (only the last `lookback` bars are used for
                  regime decision, but indicators are computed on the full
                  list for stability).
            lookback: Number of recent bars to analyze (default 20).

        Returns:
            RegimeResult with smoothed regime, confidence in [0,1], and triggers.
        """
        if not bars:
            return RegimeResult(regime="unknown", confidence=0.0, triggers=[])

        window = bars[-lookback:] if len(bars) > lookback else bars
        if not window:
            return RegimeResult(regime="unknown", confidence=0.0, triggers=[])

        # Build DataFrames.
        df_full = pd.DataFrame(
            {
                "High": [b.high for b in bars],
                "Low": [b.low for b in bars],
                "Close": [b.close for b in bars],
            }
        )
        df_window = pd.DataFrame(
            {
                "High": [b.high for b in window],
                "Low": [b.low for b in window],
                "Close": [b.close for b in window],
            }
        )

        # ADX / DMI on full history for stability.
        adx_value = 0.0
        plus_di = 0.0
        minus_di = 0.0
        if len(bars) >= 14:
            try:
                adx_ind = ADXIndicator(
                    high=df_full["High"],
                    low=df_full["Low"],
                    close=df_full["Close"],
                    window=14,
                )
                adx_value = float(adx_ind.adx().iloc[-1])
                plus_di = float(adx_ind.adx_pos().iloc[-1])
                minus_di = float(adx_ind.adx_neg().iloc[-1])
            except Exception:
                pass

        # ATR on full history for a stable percentile baseline.
        atr_percentile = 0.0
        if len(bars) >= 14:
            try:
                atr_series = _sma_atr(df_full, window=14)
                current_atr = float(atr_series.iloc[-1])
                if not pd.isna(current_atr):
                    atr_percentile = _percentile(atr_series, current_atr)
            except Exception:
                pass

        # Classify raw regime.
        regime, confidence, triggers = self._classify_raw(
            adx_value, plus_di, minus_di, atr_percentile
        )

        # Smooth with 3-bar persistence.
        smoothed = self._smooth(regime)
        if smoothed != regime:
            confidence = max(0.0, confidence - 0.2)

        return RegimeResult(regime=smoothed, confidence=confidence, triggers=triggers)

    # -- Private helpers --------------------------------------------------------

    def _classify_raw(
        self,
        adx: float,
        plus_di: float,
        minus_di: float,
        atr_pct: float,
    ) -> tuple[str, float, list[str]]:
        triggers: list[str] = []

        if _volatility_signal(atr_pct):
            triggers.append("volatility_percentile > 90")
            return "volatile", 0.9, triggers

        if _adx_trend_signal(adx, plus_di, minus_di):
            triggers.append("ADX > 25")
            triggers.append("+DMI > -DMI")
            confidence = min(1.0, adx / 50.0)
            return "trending", confidence, triggers

        if adx < 15:
            return "quiet", 0.6, triggers

        return "range-bound", 0.7, triggers

    def _smooth(self, candidate: str) -> str:
        """3-bar persistence: only report a new regime after 3 consecutive matches."""
        self._history.append(candidate)
        if len(self._history) > 3:
            self._history = self._history[-3:]

        if len(self._history) < 3:
            return self._history[0] if self._history else "unknown"

        if all(r == candidate for r in self._history):
            return candidate

        return self._history[0]
