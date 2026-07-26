"""Normalisation functions and default weights for the health score system.

Each metric normalisation function maps a raw trading metric value to a
0–1 score using piecewise-linear interpolation over domain-tuned breakpoints.
"""

from __future__ import annotations

import math
from typing import Final

from quantlab.health.models import HealthWeights


# ── Default weights ──────────────────────────────────────────────────────────

DEFAULT_WEIGHTS: Final[HealthWeights] = HealthWeights()
"""Module-level default weight configuration.

Shorthand for ``HealthWeights()`` — aligns 7 metrics into the standard
distribution defined by ``HealthWeights`` defaults.
"""


# ── Internal helpers ─────────────────────────────────────────────────────────


def _interpolate(value: float | None, breakpoints: list[tuple[float, float]]) -> float:
    """Piecewise-linear interpolation over ``breakpoints``.

    Args:
        value: Raw metric value (may be ``None``, ``nan``, or ``inf``).
        breakpoints: List of ``(x, y)`` pairs defining the function.
            Must be sorted by ``x`` ascending, with at least 2 points.

    Returns:
        Normalised score in the output range of the breakpoints.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0

    if isinstance(value, float) and math.isinf(value):
        if value > 0:
            return breakpoints[-1][1]
        return breakpoints[0][1]

    if value <= breakpoints[0][0]:
        return breakpoints[0][1]
    if value >= breakpoints[-1][0]:
        return breakpoints[-1][1]

    for i in range(len(breakpoints) - 1):
        x1, y1 = breakpoints[i]
        x2, y2 = breakpoints[i + 1]
        if x1 <= value <= x2:
            if x2 == x1:
                return y1
            return y1 + (y2 - y1) * (value - x1) / (x2 - x1)

    return breakpoints[-1][1]


# ── Per-metric normalisation ─────────────────────────────────────────────────


def normalize_profit_factor(pf: float | None) -> float:
    """Normalise Profit Factor to 0–1.

    Breakpoints: PF=0→0.0, 1.0→0.3, 1.5→0.6, 2.0→0.8, 3.0→0.95, inf→0.95

    A PF of 1.0 (breakeven) maps to 0.3 — it is not ideal but not terrible.
    PF of 2.0+ is good; 3.0+ is exceptional (capped at 0.95).
    """
    return _interpolate(pf, [(0.0, 0.0), (1.0, 0.3), (1.5, 0.6), (2.0, 0.8), (3.0, 0.95)])


def normalize_sharpe_ratio(sr: float | None) -> float:
    """Normalise Sharpe Ratio to 0–1.

    Breakpoints: SR=0→0.3, 1.0→0.6, 2.0→0.85, 3.0→0.95, inf→0.95

    A Sharpe of 0 (matching risk-free) still scores 0.3 — neutral.
    Sharpe of 1.0 is decent, 2.0+ is very good, 3.0+ exceptional.
    """
    return _interpolate(sr, [(0.0, 0.3), (1.0, 0.6), (2.0, 0.85), (3.0, 0.95)])


def normalize_sortino_ratio(sr: float | None) -> float:
    """Normalise Sortino Ratio to 0–1.

    Breakpoints: SR=0→0.2, 1.0→0.5, 2.0→0.8, 3.0→0.95, inf→0.95

    Slightly stricter than Sharpe at the low end because Sortino already
    ignores upside volatility, so a low Sortino is more concerning.
    """
    return _interpolate(sr, [(0.0, 0.2), (1.0, 0.5), (2.0, 0.8), (3.0, 0.95)])


def normalize_max_drawdown(mdd: float | None) -> float:
    """Normalise Max Drawdown (as percentage) to 0–1.

    Breakpoints: DD=0%→1.0, 5%→0.9, 10%→0.7, 20%→0.4, 30%→0.1, 50%+→0.0

    Lower drawdowns score higher. A 0% drawdown is perfect (1.0).
    A 50%+ drawdown scores 0.0 (complete failure for this metric).
    ``mdd`` is expected as a percentage (e.g. 12.5 for 12.5%).
    """
    return _interpolate(mdd, [(0.0, 1.0), (5.0, 0.9), (10.0, 0.7), (20.0, 0.4), (30.0, 0.1), (50.0, 0.0)])


def normalize_recovery_factor(rf: float | None) -> float:
    """Normalise Recovery Factor to 0–1.

    Breakpoints: RF=0→0.0, 1.0→0.3, 2.0→0.6, 5.0→0.85, 10.0→0.95, inf→0.95

    Recovery factor measures how quickly a strategy recovers from drawdowns.
    RF of 5+ is solid; 10+ is excellent.
    """
    return _interpolate(rf, [(0.0, 0.0), (1.0, 0.3), (2.0, 0.6), (5.0, 0.85), (10.0, 0.95)])


def normalize_win_rate(wr: float | None) -> float:
    """Normalise Win Rate (as percentage) to 0–1.

    Breakpoints: WR=0%→0.0, 80%→0.95, 100%→0.95, inf→0.95

    Linear from 0% to 80%, then capped at 0.95. Win rate alone is a
    weak signal (very high win rates can hide poor risk/reward), so it
    is capped at 0.95 even at 100%.
    ``wr`` is expected as a percentage (e.g. 65.0 for 65%).
    """
    return _interpolate(wr, [(0.0, 0.0), (80.0, 0.95), (100.0, 0.95)])


def normalize_expectancy_ratio(er: float | None) -> float:
    """Normalise Expectancy Ratio to 0–1.

    Breakpoints: ER=0→0.0, 0.5→0.3, 1.0→0.6, 2.0→0.85, 5.0→0.95, inf→0.95

    Expectancy ratio > 1.0 means the average winner is larger than the
    average loser — a positive risk/reward signal.
    """
    return _interpolate(er, [(0.0, 0.0), (0.5, 0.3), (1.0, 0.6), (2.0, 0.85), (5.0, 0.95)])


# ── Dispatcher ───────────────────────────────────────────────────────────────


_NORMALIZERS: dict[str, callable] = {
    "profit_factor": normalize_profit_factor,
    "sharpe_ratio": normalize_sharpe_ratio,
    "sortino_ratio": normalize_sortino_ratio,
    "max_drawdown": normalize_max_drawdown,
    "recovery_factor": normalize_recovery_factor,
    "win_rate": normalize_win_rate,
    "expectancy_ratio": normalize_expectancy_ratio,
}


def normalize_metric(name: str, value: float | None) -> float:
    """Dispatch to the correct normalisation function by metric name.

    Args:
        name: Metric key (e.g. ``"profit_factor"``, ``"sharpe_ratio"``).
        value: Raw metric value (may be ``None``).

    Returns:
        Normalised 0–1 score.

    Raises:
        KeyError: If ``name`` is not a recognised metric.
    """
    normalizer = _NORMALIZERS.get(name)
    if normalizer is None:
        raise KeyError(f"Unknown metric '{name}'. Known: {', '.join(sorted(_NORMALIZERS))}")
    return normalizer(value)
