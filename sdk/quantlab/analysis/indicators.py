"""Thin `ta` wrapper: IndicatorEngine + IndicatorResult.

Outputs are contextual zones (overbought/oversold/neutral, high/normal/low,
trending/range), NOT entry/exit signals.  Perception layer only.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, ADXIndicator, EMAIndicator, SMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands

from quantlab.data.market import Bar

# ---------------------------------------------------------------------------
# Version gate
# ---------------------------------------------------------------------------

_MIN_TA_VERSION = "0.11.0"


def _check_ta_version() -> str:
    """Return ta version string, raising on import failure."""
    try:
        from importlib.metadata import version

        return version("ta")
    except Exception as exc:
        raise ImportError(
            "The 'ta' package is required but not installed. "
            f"Install it with: pip install 'ta>={_MIN_TA_VERSION}'"
        ) from exc


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class IndicatorResult(TypedDict):
    indicator_name: str
    value: float
    zone: Literal[
        "overbought",
        "oversold",
        "neutral",
        "high",
        "normal",
        "low",
        "trending",
        "range",
        "insufficient_data",
    ]
    metadata: dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bars_to_frame(bars: list[Bar]) -> pd.DataFrame:
    """Convert Bar list to the OHLCV DataFrame ta expects."""
    data = {
        "Open": [b.open for b in bars],
        "High": [b.high for b in bars],
        "Low": [b.low for b in bars],
        "Close": [b.close for b in bars],
        "Volume": [b.volume for b in bars],
    }
    return pd.DataFrame(data)


def _rsi_zone(value: float) -> str:
    if value > 70:
        return "overbought"
    if value < 30:
        return "oversold"
    return "neutral"


def _atr_zone(value: float, atr_series: pd.Series) -> str:
    median = atr_series.median()
    if median == 0:
        return "neutral"
    ratio = value / median
    if ratio > 2.0:
        return "high"
    if ratio < 0.5:
        return "low"
    return "normal"


def _adx_zone(value: float) -> str:
    if value > 25:
        return "trending"
    if value < 20:
        return "range"
    return "neutral"


def _reject_nan_close(df: pd.DataFrame, indicator_name: str) -> IndicatorResult | None:
    """Return an insufficient_data IndicatorResult when the last close is NaN."""
    if not pd.notna(df["Close"].iloc[-1]):
        return IndicatorResult(
            indicator_name=indicator_name,
            value=0.0,
            zone="insufficient_data",
            metadata={"reason": "nan_close"},
        )
    return None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class IndicatorEngine:
    """Thin wrapper around `ta` that returns contextual zones, not signals."""

    def __init__(self, min_ta_version: str = _MIN_TA_VERSION) -> None:
        actual = _check_ta_version()
        # Simple PEP 440 compare (major.minor.patch).
        actual_parts = tuple(int(x) for x in actual.split(".")[:3])
        required_parts = tuple(int(x) for x in min_ta_version.split(".")[:3])
        if actual_parts < required_parts:
            raise RuntimeError(
                f"ta>={min_ta_version} required, found {actual}. "
                f"Upgrade with: pip install 'ta>={min_ta_version}'"
            )
        self._ta_version = actual

    @property
    def ta_version(self) -> str:
        return self._ta_version

    def compute(
        self, bars: list[Bar], indicators: list[str]
    ) -> list[IndicatorResult]:
        """Compute requested indicators and return only those results.

        Returns `zone="insufficient_data"` for each requested indicator when
        bars are empty or too short; never raises on bad input.
        """
        if not bars:
            return [
                IndicatorResult(
                    indicator_name=name,
                    value=0.0,
                    zone="insufficient_data",
                    metadata={"reason": "empty_bar_list"},
                )
                for name in indicators
            ]

        df = _bars_to_frame(bars)
        results: list[IndicatorResult] = []

        for name in indicators:
            upper = name.upper()
            try:
                if upper == "RSI":
                    results.append(self._compute_rsi(df, bars))
                elif upper == "MACD":
                    results.append(self._compute_macd(df, bars))
                elif upper == "ATR":
                    results.append(self._compute_atr(df, bars))
                elif upper == "ADX":
                    results.append(self._compute_adx(df, bars))
                elif upper == "BOLLINGER":
                    results.append(self._compute_bollinger(df, bars))
                elif upper == "SMA":
                    results.append(self._compute_sma(df, bars))
                elif upper == "EMA":
                    results.append(self._compute_ema(df, bars))
                else:
                    results.append(
                        IndicatorResult(
                            indicator_name=name,
                            value=0.0,
                            zone="insufficient_data",
                            metadata={"reason": f"unsupported_indicator:{name}"},
                        )
                    )
            except Exception:
                # Graceful degradation: never propagate.
                results.append(
                    IndicatorResult(
                        indicator_name=name,
                        value=0.0,
                        zone="insufficient_data",
                        metadata={"reason": "computation_failed"},
                    )
                )

        return results

    # -- Private per-indicator helpers -----------------------------------------

    @staticmethod
    def _compute_rsi(df: pd.DataFrame, bars: list[Bar]) -> IndicatorResult:
        if len(bars) < 15:
            return IndicatorResult(
                indicator_name="RSI",
                value=0.0,
                zone="insufficient_data",
                metadata={"reason": "too_few_bars", "required": 15, "got": len(bars)},
            )
        nan_result = _reject_nan_close(df, "RSI")
        if nan_result is not None:
            return nan_result
        indicator = RSIIndicator(close=df["Close"], window=14)
        series = indicator.rsi()
        value = float(series.iloc[-1])
        if pd.isna(value):
            return IndicatorResult(
                indicator_name="RSI",
                value=0.0,
                zone="insufficient_data",
                metadata={"reason": "nan_value"},
            )
        return IndicatorResult(
            indicator_name="RSI",
            value=round(value, 4),
            zone=_rsi_zone(value),
            metadata={"window": 14},
        )

    @staticmethod
    def _compute_macd(df: pd.DataFrame, bars: list[Bar]) -> IndicatorResult:
        if len(bars) < 35:
            return IndicatorResult(
                indicator_name="MACD",
                value=0.0,
                zone="insufficient_data",
                metadata={"reason": "too_few_bars", "required": 35, "got": len(bars)},
            )
        indicator = MACD(close=df["Close"])
        macd_series = indicator.macd()
        value = float(macd_series.iloc[-1])
        if pd.isna(value):
            return IndicatorResult(
                indicator_name="MACD",
                value=0.0,
                zone="insufficient_data",
                metadata={"reason": "nan_value"},
            )
        return IndicatorResult(
            indicator_name="MACD",
            value=round(value, 6),
            zone="neutral",
            metadata={"window_fast": 12, "window_slow": 26, "window_signal": 9},
        )

    @staticmethod
    def _compute_atr(df: pd.DataFrame, bars: list[Bar]) -> IndicatorResult:
        if len(bars) < 15:
            return IndicatorResult(
                indicator_name="ATR",
                value=0.0,
                zone="insufficient_data",
                metadata={"reason": "too_few_bars", "required": 15, "got": len(bars)},
            )
        indicator = AverageTrueRange(high=df["High"], low=df["Low"], close=df["Close"])
        series = indicator.average_true_range()
        value = float(series.iloc[-1])
        if pd.isna(value):
            return IndicatorResult(
                indicator_name="ATR",
                value=0.0,
                zone="insufficient_data",
                metadata={"reason": "nan_value"},
            )
        zone = _atr_zone(value, series)
        return IndicatorResult(
            indicator_name="ATR",
            value=round(value, 6),
            zone=zone,
            metadata={"window": 14, "atr_median": round(float(series.median()), 6)},
        )

    @staticmethod
    def _compute_adx(df: pd.DataFrame, bars: list[Bar]) -> IndicatorResult:
        if len(bars) < 30:
            return IndicatorResult(
                indicator_name="ADX",
                value=0.0,
                zone="insufficient_data",
                metadata={"reason": "too_few_bars", "required": 30, "got": len(bars)},
            )
        indicator = ADXIndicator(
            high=df["High"], low=df["Low"], close=df["Close"], window=14
        )
        series = indicator.adx()
        value = float(series.iloc[-1])
        if pd.isna(value):
            return IndicatorResult(
                indicator_name="ADX",
                value=0.0,
                zone="insufficient_data",
                metadata={"reason": "nan_value"},
            )
        return IndicatorResult(
            indicator_name="ADX",
            value=round(value, 4),
            zone=_adx_zone(value),
            metadata={"window": 14},
        )

    @staticmethod
    def _compute_bollinger(df: pd.DataFrame, bars: list[Bar]) -> IndicatorResult:
        if len(bars) < 20:
            return IndicatorResult(
                indicator_name="Bollinger",
                value=0.0,
                zone="insufficient_data",
                metadata={"reason": "too_few_bars", "required": 20, "got": len(bars)},
            )
        indicator = BollingerBands(close=df["Close"], window=20, window_dev=2)
        upper = float(indicator.bollinger_hband().iloc[-1])
        lower = float(indicator.bollinger_lband().iloc[-1])
        close = float(df["Close"].iloc[-1])
        if pd.isna(upper) or pd.isna(lower) or pd.isna(close):
            return IndicatorResult(
                indicator_name="Bollinger",
                value=0.0,
                zone="insufficient_data",
                metadata={"reason": "nan_value"},
            )
        band_width = upper - lower
        if band_width == 0:
            zone = "neutral"
        else:
            percent_b = (close - lower) / band_width
            if percent_b > 1.0:
                zone = "overbought"
            elif percent_b < 0.0:
                zone = "oversold"
            else:
                zone = "neutral"
        return IndicatorResult(
            indicator_name="Bollinger",
            value=round(close, 4),
            zone=zone,
            metadata={"upper": round(upper, 4), "lower": round(lower, 4), "width": round(band_width, 4), "percent_b": round(percent_b, 4) if band_width != 0 else None},
        )

    @staticmethod
    def _compute_sma(df: pd.DataFrame, bars: list[Bar]) -> IndicatorResult:
        if len(bars) < 20:
            return IndicatorResult(
                indicator_name="SMA",
                value=0.0,
                zone="insufficient_data",
                metadata={"reason": "too_few_bars", "required": 20, "got": len(bars)},
            )
        indicator = SMAIndicator(close=df["Close"], window=20)
        series = indicator.sma_indicator()
        value = float(series.iloc[-1])
        close = float(df["Close"].iloc[-1])
        if pd.isna(value):
            return IndicatorResult(
                indicator_name="SMA",
                value=0.0,
                zone="insufficient_data",
                metadata={"reason": "nan_value"},
            )
        if close > value:
            zone = "overbought"
        elif close < value:
            zone = "oversold"
        else:
            zone = "neutral"
        return IndicatorResult(
            indicator_name="SMA",
            value=round(value, 4),
            zone=zone,
            metadata={"window": 20, "close": round(close, 4)},
        )

    @staticmethod
    def _compute_ema(df: pd.DataFrame, bars: list[Bar]) -> IndicatorResult:
        if len(bars) < 20:
            return IndicatorResult(
                indicator_name="EMA",
                value=0.0,
                zone="insufficient_data",
                metadata={"reason": "too_few_bars", "required": 20, "got": len(bars)},
            )
        indicator = EMAIndicator(close=df["Close"], window=20)
        series = indicator.ema_indicator()
        value = float(series.iloc[-1])
        close = float(df["Close"].iloc[-1])
        if pd.isna(value):
            return IndicatorResult(
                indicator_name="EMA",
                value=0.0,
                zone="insufficient_data",
                metadata={"reason": "nan_value"},
            )
        if close > value:
            zone = "overbought"
        elif close < value:
            zone = "oversold"
        else:
            zone = "neutral"
        return IndicatorResult(
            indicator_name="EMA",
            value=round(value, 4),
            zone=zone,
            metadata={"window": 20, "close": round(close, 4)},
        )
