"""Pydantic models for the health score system.

Defines the domain model for strategy health assessment:
categorical bands, weighted metric scores, and full health records.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HealthState(str, Enum):
    """Categorical health bands mapping a 0–100 score to a qualitative state.

    Bands follow a severity scale from EXCELLENT (fully healthy) to
    IMMEDIATE_WITHDRAWAL (critical — strategy must be stopped).

    .. code-block::

        EXCELLENT               90 – 100
        STABLE                  75 –  89
        OBSERVATION             60 –  74
        DEGRADING               45 –  59
        REPLACEMENT_RECOMMENDED 30 –  44
        IMMEDIATE_WITHDRAWAL     0 –  29
    """

    EXCELLENT = "excellent"
    STABLE = "stable"
    OBSERVATION = "observation"
    DEGRADING = "degrading"
    REPLACEMENT_RECOMMENDED = "replacement_recommended"
    IMMEDIATE_WITHDRAWAL = "immediate_withdrawal"


class HealthScore(BaseModel):
    """Health assessment result for a single strategy over one time period.

    Attributes:
        overall_score: Composite 0–100 health score (weighted average of
            individual normalised metric scores).
        state: Categorical band derived from ``overall_score``.
        metric_scores: Per-metric normalised scores (0–1) keyed by metric
            name (e.g. ``{"profit_factor": 0.85, "sharpe_ratio": 0.62}``).
        period: Time window label (e.g. ``"30d"``, ``"90d"``, ``"1y"``,
            ``"all"``). The calculator stamps this as metadata without
            performing any time-windowing logic.
    """

    overall_score: float = Field(ge=0, le=100, description="Composite health score 0–100")
    state: HealthState = Field(description="Categorical band for this score")
    metric_scores: dict[str, float] = Field(description="Per-metric normalised scores (0–1 range)")
    period: str = Field(default="all", description="Time window label (pass-through)")


class HealthWeights(BaseModel):
    """Configurable weight distribution for the seven health metrics.

    Defaults are tuned for a balanced multi-metric strategy assessment
    where Profit Factor and Max Drawdown carry the most weight.

    The model is frozen (immutable) after construction, and a validator
    ensures the weights sum to approximately 1.0.
    """

    profit_factor: float = Field(default=0.25, ge=0.0, le=1.0)
    sharpe_ratio: float = Field(default=0.20, ge=0.0, le=1.0)
    sortino_ratio: float = Field(default=0.10, ge=0.0, le=1.0)
    max_drawdown: float = Field(default=0.20, ge=0.0, le=1.0)
    recovery_factor: float = Field(default=0.10, ge=0.0, le=1.0)
    win_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    expectancy_ratio: float = Field(default=0.10, ge=0.0, le=1.0)

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def _validate_weight_sum(self) -> HealthWeights:
        """Ensure all weights sum to approximately 1.0 (within 1e-6)."""
        total = (
            self.profit_factor
            + self.sharpe_ratio
            + self.sortino_ratio
            + self.max_drawdown
            + self.recovery_factor
            + self.win_rate
            + self.expectancy_ratio
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"HealthWeights must sum to 1.0, got {total:.10f}. "
                f"Adjust one or more weights."
            )
        return self


class HealthRecord(BaseModel):
    """A timestamped health assessment for a specific strategy.

    Persisted in monitoring logs and consumed by downstream decision
    systems (MetaGuardian, SEE) to trigger alerts or rebalance actions.
    """

    strategy_id: str = Field(..., description="Unique strategy identifier")
    timestamp: datetime = Field(default_factory=datetime.now, description="Assessment timestamp")
    score: HealthScore = Field(..., description="Health assessment result")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata payload")
