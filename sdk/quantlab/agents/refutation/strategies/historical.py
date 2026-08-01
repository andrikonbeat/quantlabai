"""HistoricalCounterExampleStrategy — falsation via historical data analysis.

Fetches historical OHLCV data via YahooFinanceProvider and searches for
periods where the hypothesis's expected conditions existed but the expected
outcome failed (RF-3).

Uses a simple RSI-based counter-example heuristic: when RSI < 30 (oversold)
and the subsequent forward return is negative, that period is counted as a
counter-example. Score is proportional to the counter-example rate, capped
at 0.8.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from quantlab.dsl.models import HypothesisConfig
from quantlab.agents.refutation.models import FalsationVerdict
from quantlab.agents.refutation.strategies import RefutationStrategy
from quantlab.data.fundamental.yahoo import YahooFinanceProvider

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

_RSI_PERIOD = 14
_FORWARD_LOOKBACK = 5  # days to look ahead after a signal
_MAX_SCORE = 0.8


# ── Helpers ────────────────────────────────────────────────────────────────────


def _extract_symbol(hypothesis: HypothesisConfig) -> str | None:
    """Extract a trading symbol from the hypothesis.

    Priority:
    1. ``parameters.symbol``
    2. Uppercase ticker-like word in the description (2–8 chars, alphabetic)
    3. ``None`` if nothing found

    Args:
        hypothesis: The hypothesis config to extract from.

    Returns:
        The symbol string, or ``None``.
    """
    # Check parameters first
    symbol = hypothesis.parameters.get("symbol")
    if symbol and isinstance(symbol, str) and len(symbol.strip()) > 0:
        return symbol.strip().upper()

    # Fall back to description — look for uppercase ticker patterns
    desc = hypothesis.description or ""
    # Match words that are all uppercase, 2–8 characters (common tickers/forex)
    match = re.search(r"\b[A-Z]{2,8}\b", desc)
    if match:
        return match.group(0)

    return None


def _compute_rsi(prices: list[dict[str, Any]], period: int = _RSI_PERIOD) -> list[float]:
    """Compute RSI values from a list of OHLCV price dicts.

    Uses Wilder's smoothing (SMA of gains/losses over the RSI period).

    Args:
        prices: List of price dicts with ``close`` keys (chronological).
        period: RSI lookback period (default 14).

    Returns:
        List of RSI values, same length as ``prices``. First ``period``
        entries are ``None`` (insufficient data).
    """
    if len(prices) < period + 1:
        return [None] * len(prices)

    closes = [p["close"] for p in prices]
    rsis: list[float | None] = [None] * period  # first N periods have no RSI

    # Initial SMA of gains/losses
    gains: list[float] = []
    losses: list[float] = []

    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    # First RSI value
    if avg_loss == 0:
        rsis.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsis.append(100.0 - 100.0 / (1.0 + rs))

    # Subsequent values using Wilder's smoothing
    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            rsis.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsis.append(100.0 - 100.0 / (1.0 + rs))

    return rsis


def _find_counter_examples(
    prices: list[dict[str, Any]],
    rsis: list[float | None],
) -> tuple[float, list[str]]:
    """Find counter-examples where RSI < 30 was followed by a decline.

    Args:
        prices: List of OHLCV price dicts (chronological).
        rsis: List of RSI values (same length, may contain ``None``).

    Returns:
        Tuple of ``(score, evidence)``. Score is 0.0 to ``_MAX_SCORE``.
    """
    signals: list[int] = []
    for i, rsi in enumerate(rsis):
        if rsi is not None and rsi < 30:
            signals.append(i)

    if not signals:
        return 0.0, []

    counter_examples = 0
    for idx in signals:
        if idx + _FORWARD_LOOKBACK >= len(prices):
            continue
        entry_price = prices[idx]["close"]
        exit_price = prices[idx + _FORWARD_LOOKBACK]["close"]
        forward_return = (exit_price - entry_price) / entry_price
        if forward_return < 0:
            counter_examples += 1

    total_checkable = sum(
        1 for idx in signals if idx + _FORWARD_LOOKBACK < len(prices)
    )
    if total_checkable == 0:
        return 0.0, []

    counter_rate = counter_examples / total_checkable
    evidence = [
        f"RSI < 30 occurred {len(signals)} times; "
        f"{counter_examples} were followed by decline "
        f"(rate={counter_rate:.1%})",
    ]

    score = min(counter_rate * _MAX_SCORE, _MAX_SCORE)
    return round(score, 4), evidence


# ── Strategy ───────────────────────────────────────────────────────────────────


class HistoricalCounterExampleStrategy(RefutationStrategy):
    """Falsation strategy using historical price data.

    Fetches OHLCV data via ``YahooFinanceProvider`` and detects
    counter-examples: periods where RSI < 30 (common buy signal) was
    followed by further price declines.

    Args:
        provider: A ``YahooFinanceProvider`` instance. Created with
            defaults if omitted.
    """

    def __init__(self, provider: YahooFinanceProvider | None = None) -> None:
        self._provider = provider or YahooFinanceProvider()

    async def refute(
        self,
        hypothesis: HypothesisConfig,
        market_context: dict[str, Any] | None = None,
    ) -> FalsationVerdict:
        """Evaluate a hypothesis using historical price data.

        Args:
            hypothesis: The hypothesis to evaluate.
            market_context: Optional context (unused in this strategy).

        Returns:
            A ``FalsationVerdict``.
        """
        symbol = _extract_symbol(hypothesis)
        if symbol is None:
            return FalsationVerdict(
                hypothesis_name=hypothesis.name,
                falsification_score=0.0,
                evidence=[],
                strategy="historical_counterexample",
            )

        # Fetch 2 years of OHLCV data
        try:
            data = await self._provider.fetch(symbol)
        except Exception:
            logger.debug(
                "Historical data fetch failed for '%s' — score=0",
                hypothesis.name,
            )
            return FalsationVerdict(
                hypothesis_name=hypothesis.name,
                falsification_score=0.0,
                evidence=[],
                strategy="historical_counterexample",
            )

        prices = data.get("prices", [])
        if not prices:
            return FalsationVerdict(
                hypothesis_name=hypothesis.name,
                falsification_score=0.0,
                evidence=[],
                strategy="historical_counterexample",
            )

        rsis = _compute_rsi(prices)
        score, evidence = _find_counter_examples(prices, rsis)

        return FalsationVerdict(
            hypothesis_name=hypothesis.name,
            falsification_score=score,
            evidence=evidence,
            strategy="historical_counterexample",
        )


__all__ = ["HistoricalCounterExampleStrategy", "_extract_symbol", "_compute_rsi"]
