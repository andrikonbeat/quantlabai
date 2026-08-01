"""Data models for the RefutationLayer.

Separated from ``__init__.py`` to avoid circular imports with strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FalsationVerdict:
    """Result of a single strategy evaluating a single hypothesis.

    Attributes:
        hypothesis_name: Name of the evaluated hypothesis.
        falsification_score: Score from 0.0 (not refuted) to 1.0 (fully
            refuted) — the max of all strategies that ran.
        evidence: Human-readable reasons for the score.
        strategy: Name of the strategy that produced this verdict.
    """

    hypothesis_name: str
    falsification_score: float
    evidence: list[str]
    strategy: str


@dataclass
class RefutationResult:
    """Aggregate result from the full refutation layer.

    Attributes:
        verdicts: One ``FalsationVerdict`` per hypothesis evaluated.
        summary: Aggregated statistics (mean, max, count).
    """

    verdicts: list[FalsationVerdict]
    summary: dict[str, Any] = field(default_factory=dict)


__all__ = ["FalsationVerdict", "RefutationResult"]
