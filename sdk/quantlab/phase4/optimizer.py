"""Optimizer models — walk-forward optimization cycles and results.

Provides data models for walk-forward optimization cycles used by
the statistics aggregation module and campaign orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class WalkForwardCycle:
    """A single walk-forward optimization cycle.

    Contains the in-sample and out-of-sample date ranges along with
    the computed metrics for the out-of-sample period.

    Attributes:
        cycle: Cycle index (1-based).
        metrics: Dict of metric name -> value (e.g., Sharpe, ProfitFactor).
        in_sample_start: In-sample period start date (ISO format string).
        in_sample_end: In-sample period end date (ISO format string).
        out_sample_start: Out-of-sample period start date.
        out_sample_end: Out-of-sample period end date.
        parameters: Optional dict of optimization parameters used.
    """

    cycle: int = 0
    metrics: dict[str, float] = field(default_factory=dict)
    in_sample_start: Optional[str] = None
    in_sample_end: Optional[str] = None
    out_sample_start: Optional[str] = None
    out_sample_end: Optional[str] = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def get_metric(self, name: str) -> Optional[float]:
        """Get a metric value by name (case-insensitive key lookup)."""
        for key, value in self.metrics.items():
            if key.lower() == name.lower():
                return float(value)
        return None


@dataclass
class OptimizationCycle:
    """An optimization cycle result with full configuration.

    Extends WalkForwardCycle with optimizer-specific configuration
    and result metadata.
    """

    cycle: int = 0
    generation: int = 0
    config: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
