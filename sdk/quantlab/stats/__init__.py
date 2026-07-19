"""Statistics engine — pure Python trading metric computations and aggregation."""

from quantlab.stats.engine import StatisticsEngine
from quantlab.stats.models import (
    StatsResult,
    AggregateStats,
    RollingMetrics,
    BenchmarkComparison,
)
from quantlab.stats.aggregation import StatisticsAggregator

__all__ = [
    "StatisticsEngine",
    "StatsResult",
    "AggregateStats",
    "RollingMetrics",
    "BenchmarkComparison",
    "StatisticsAggregator",
]
