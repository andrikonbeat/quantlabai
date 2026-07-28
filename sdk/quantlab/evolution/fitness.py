"""FitnessFunction — wraps HealthScore with configurable weight profiles."""

from __future__ import annotations

from typing import Dict, Optional

from quantlab.evolution.config import WeightProfile
from quantlab.health.calculator import HealthScoreCalculator
from quantlab.stats.models import StatsResult


class FitnessFunction:
    """Evaluates strategy fitness using the Health Score system.

    Wraps ``HealthScoreCalculator`` with configurable weight profiles
    that can be swapped per evolution cycle.
    """

    def __init__(self, weight_profile: Optional[WeightProfile] = None) -> None:
        """Initialize with an optional weight profile.

        Args:
            weight_profile: Custom weight profile (defaults to standard).
        """
        if weight_profile is not None:
            weights = weight_profile.as_dict()
        else:
            weights = None
        self._calculator = HealthScoreCalculator(weights=weights)
        self._profile = weight_profile or WeightProfile()

    @property
    def profile(self) -> WeightProfile:
        """Current weight profile."""
        return self._profile

    def evaluate(self, stats: StatsResult) -> float:
        """Compute fitness score from strategy statistics.

        Args:
            stats: Computed strategy statistics.

        Returns:
            Fitness score (0–100) where higher is better.
        """
        health = self._calculator.compute(stats)
        return health.overall

    def evaluate_with_profile(
        self, stats: StatsResult, profile: WeightProfile
    ) -> float:
        """Evaluate using a specific weight profile temporarily.

        Args:
            stats: Computed strategy statistics.
            profile: Temporary weight profile for this evaluation.

        Returns:
            Fitness score (0–100).
        """
        weights = profile.as_dict()
        calc = HealthScoreCalculator(weights=weights)
        health = calc.compute(stats)
        return health.overall
