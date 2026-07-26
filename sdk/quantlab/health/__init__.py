"""Health score system — normalise trading metrics into a composable 0–100 score.

Provides categorical health bands, weighted metric aggregation, and a
stateless calculator that transforms ``StatsResult`` into ``HealthScore``.
"""

from quantlab.health.calculator import HealthScoreCalculator
from quantlab.health.models import HealthRecord, HealthScore, HealthState, HealthWeights

__all__ = [
    "HealthScoreCalculator",
    "HealthRecord",
    "HealthScore",
    "HealthState",
    "HealthWeights",
]
