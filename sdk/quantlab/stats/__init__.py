"""Statistics engine — pure Python trading metric computations and aggregation."""

from quantlab.stats.aggregation import StatisticsAggregator
from quantlab.stats.engine import StatisticsEngine
from quantlab.stats.models import (
    AggregateStats,
    BenchmarkComparison,
    RollingMetrics,
    StatsResult,
)

__all__ = [
    "AggregateStats",
    "BenchmarkComparison",
    "RollingMetrics",
    "StatisticsAggregator",
    "StatisticsEngine",
    "StatsResult",
]
