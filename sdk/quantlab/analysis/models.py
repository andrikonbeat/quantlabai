"""Models for the analysis library — per-strategy analysis and selection results."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from quantlab.stats.models import StatsResult


class StrategyAnalysis(BaseModel):
    """Per-strategy analysis result.

    Attributes:
        name: Strategy identifier.
        metrics: Computed statistics (StatsResult). Absent source fields are ``None``.
        flags: Overfit-risk flags raised by heuristics.
        score: Composite bounded score (0–100) used for ordering accepted strategies.
    """

    name: str = Field(..., description="Strategy identifier")
    metrics: StatsResult = Field(..., description="Computed per-strategy metrics")
    flags: list[str] = Field(default_factory=list, description="Overfit-risk flags")
    score: float = Field(default=0.0, description="Composite score (0–100)")


class SelectionResult(BaseModel):
    """Result of strategy selection.

    Attributes:
        analyses: All analyzed strategies (one-to-one with inputs).
        verdicts: Per-strategy verdict mapping (ACCEPT or REJECT).
        selected: Ordered list of accepted strategy names, highest score first.
        warnings: Non-fatal warnings produced during selection.
    """

    analyses: list[StrategyAnalysis] = Field(
        default_factory=list, description="All analyzed strategies"
    )
    verdicts: dict[str, str] = Field(
        default_factory=dict, description="Per-strategy verdict (ACCEPT/REJECT)"
    )
    selected: list[str] = Field(
        default_factory=list, description="Accepted strategy names ordered by score desc"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Non-fatal warnings"
    )
