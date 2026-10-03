"""Technical indicators calculator backed by ``ta``.

Calculates a fixed set of spot technical indicators from OHLCV data
and returns the latest available values as plain Python types.

Design goals:
- Fail-soft: if ``ta`` is unavailable or the input is too short, return
  ``None`` for each indicator instead of raising.
- No side effects: does not mutate the input DataFrame.
- Deterministic output shape: always returns the same keys.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

try:
    import ta

    _TA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TA_AVAILABLE = False


def _latest_valid(series: pd.Series) -> Any:
    """Return the latest non-null value from a Series, or None."""
    clean = series.dropna()
    if clean.empty:
        return None
    val = clean.iloc[-1]
    if hasattr(val, "item"):
        try:
            return val.item()
        except (TypeError, ValueError):
            return float(val)
    return val


def compute_indicators(
    prices: list[dict[str, Any]],
    *,
    min_rows: int = 30,
) -> dict[str, Any]:
    """Compute spot technical indicators from OHLCV price history.

    Args:
        prices: List of OHLCV dicts with keys ``date``, ``open``,
            ``high``, ``low``, ``close``, ``volume``.
        min_rows: Minimum number of valid rows required to compute
            indicators. Fewer rows returns all ``None`` values.

    Returns:
        Dict with indicator names as keys and the latest available
        value (or ``None``) as values.
    """
    result: dict[str, Any] = {
        "close": None,
        "volume": None,
        "rsi": None,
        "sma_50": None,
        "sma_200": None,
        "ema_200": None,
        "atr": None,
        "bb_lower": None,
        "bb_middle": None,
        "bb_upper": None,
        "macd": None,
        "macd_signal": None,
        "macd_hist": None,
        "volume_sma_20": None,
    }

    if not prices or len(prices) < min_rows:
        return result

    df = pd.DataFrame(prices)
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    if len(df) < min_rows:
        return result

    # Ensure numeric
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    if len(df) < min_rows:
        return result

    result["close"] = _latest_valid(df["close"])
    result["volume"] = _latest_valid(df["volume"])

    if not _TA_AVAILABLE:
        logger.warning("ta library is not installed; technical indicators unavailable")
        return result

    try:
        # RSI(14)
        rsi_series = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
        result["rsi"] = _latest_valid(rsi_series)

        # SMA(50) and SMA(200)
        sma_50_series = ta.trend.SMAIndicator(df["close"], window=50).sma_indicator()
        sma_200_series = ta.trend.SMAIndicator(df["close"], window=200).sma_indicator()
        result["sma_50"] = _latest_valid(sma_50_series)
        result["sma_200"] = _latest_valid(sma_200_series)

        # EMA(200)
        ema_200_series = ta.trend.EMAIndicator(df["close"], window=200).ema_indicator()
        result["ema_200"] = _latest_valid(ema_200_series)

        # ATR(14)
        atr_series = ta.volatility.AverageTrueRange(
            df["high"], df["low"], df["close"], window=14
        ).average_true_range()
        result["atr"] = _latest_valid(atr_series)

        # Bollinger Bands(20, 2)
        bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2.0)
        result["bb_lower"] = _latest_valid(bb.bollinger_lband())
        result["bb_middle"] = _latest_valid(bb.bollinger_mavg())
        result["bb_upper"] = _latest_valid(bb.bollinger_hband())

        # MACD(12, 26, 9)
        macd = ta.trend.MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
        result["macd"] = _latest_valid(macd.macd())
        result["macd_signal"] = _latest_valid(macd.macd_signal())
        result["macd_hist"] = _latest_valid(macd.macd_diff())

        # Volume SMA(20)
        vol_sma_series = ta.trend.SMAIndicator(df["volume"], window=20).sma_indicator()
        result["volume_sma_20"] = _latest_valid(vol_sma_series)
    except Exception as exc:
        logger.warning("Failed to compute technical indicators: %s", exc)

    return result


__all__ = ["compute_indicators"]
