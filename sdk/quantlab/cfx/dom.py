"""Domain methods for CFX archive mutation — high-level API for LLM-driven editing.

Provides 8 typed domain methods that wrap CfxPatcher for common CFX modifications:
- set_market()
- add_timeframe()
- enable_block()
- disable_block()
- set_genetic()
- set_date_range()
- add_ranking_condition()
- enable_crosscheck()

Each method validates inputs and applies the corresponding patch instruction.
"""

from __future__ import annotations

from quantlab.cfx.models import CfxArchive
from quantlab.cfx.patcher import CfxPatcher


def set_market(archive: CfxArchive, symbol: str) -> CfxArchive:
    """Set the market symbol for the build task.

    Updates:
    - Data/Settings → Symbol@symbol, Symbol@name
    - Resources/Symbols (via raw XML if present)

    Args:
        archive: The CFX archive to modify.
        symbol: Market symbol (e.g., "EURUSD", "GBPUSD").

    Returns:
        The same archive instance (mutated in place).
    """
    CfxPatcher(archive).set_market(symbol)
    return archive


def add_timeframe(archive: CfxArchive, timeframe: str) -> CfxArchive:
    """Add a timeframe/chart to the data setup.

    Updates:
    - Data/Settings → TimeframeN@value
    - WhatToBuild/Settings → TimeframeN@value

    Args:
        archive: The CFX archive to modify.
        timeframe: Timeframe string (e.g., "H1", "M15", "D1").

    Returns:
        The same archive instance (mutated in place).

    Raises:
        ValidationError: If timeframe is not in supported set.
    """
    CfxPatcher(archive).add_timeframe(timeframe)
    return archive


def enable_block(archive: CfxArchive, block_key: str, weight: int = 100) -> CfxArchive:
    """Enable a building block with an optional weight.

    Args:
        archive: The CFX archive to modify.
        block_key: The unique key/name of the building block to enable.
        weight: Block weight (default 100).

    Returns:
        The same archive instance (mutated in place).
    """
    CfxPatcher(archive).enable_block(block_key, weight)
    return archive


def disable_block(archive: CfxArchive, block_key: str) -> CfxArchive:
    """Disable a building block by key.

    Args:
        archive: The CFX archive to modify.
        block_key: The unique key/name of the building block to disable.

    Returns:
        The same archive instance (mutated in place).
    """
    CfxPatcher(archive).disable_block(block_key)
    return archive


def set_genetic(
    archive: CfxArchive, enabled: bool, generations: int, population: int
) -> CfxArchive:
    """Configure genetic optimisation parameters.

    Updates WhatToBuild settings:
    - UseGenetic@value
    - Generations@value
    - Population@value

    Args:
        archive: The CFX archive to modify.
        enabled: Whether genetic optimisation is enabled.
        generations: Number of generations (must be > 0).
        population: Population size (must be > 0).

    Returns:
        The same archive instance (mutated in place).
    """
    CfxPatcher(archive).set_genetic(enabled, generations, population)
    return archive


def set_date_range(archive: CfxArchive, start: str, end: str) -> CfxArchive:
    """Set the backtesting date range with domain-specific format mapping.

    Format mapping per section domain:
    - Data, Setups: YYYY.MM.DD (string attribute)
    - Resources, Symbols, Sessions: epoch milliseconds (integer)

    Args:
        archive: The CFX archive to modify.
        start: Start date (YYYY.MM.DD or epoch ms string).
        end: End date (YYYY.MM.DD or epoch ms string).

    Returns:
        The same archive instance (mutated in place).
    """
    CfxPatcher(archive).set_date_range(start, end)
    return archive


def add_ranking_condition(
    archive: CfxArchive, metric: str, operator: str, value: float
) -> CfxArchive:
    """Add a ranking acceptance condition.

    Updates Rankings/Acceptance section with a new criterion.

    Args:
        archive: The CFX archive to modify.
        metric: Metric name (e.g., "profit_factor", "sharpe", "net_profit").
        operator: Comparison operator (>, >=, <, <=, ==, !=).
        value: Threshold value.

    Returns:
        The same archive instance (mutated in place).
    """
    CfxPatcher(archive).add_ranking_condition(metric, operator, value)
    return archive


def enable_crosscheck(
    archive: CfxArchive, wf_enabled: bool, mc_enabled: bool, wf_cycles: int = 50
) -> CfxArchive:
    """Enable walk-forward and/or Monte-Carlo cross-checks.

    Updates CrossChecks section:
    - WalkForward@enabled
    - MonteCarlo@enabled
    - WalkForward@cycles

    Args:
        archive: The CFX archive to modify.
        wf_enabled: Enable walk-forward analysis.
        mc_enabled: Enable Monte-Carlo simulation.
        wf_cycles: Number of walk-forward cycles (default 50).

    Returns:
        The same archive instance (mutated in place).
    """
    CfxPatcher(archive).enable_crosscheck(wf_enabled, mc_enabled, wf_cycles)
    return archive


# ── Public API ────────────────────────────────────────────────────────

__all__ = [
    "set_market",
    "add_timeframe",
    "enable_block",
    "disable_block",
    "set_genetic",
    "set_date_range",
    "add_ranking_condition",
    "enable_crosscheck",
]