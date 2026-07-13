"""Pydantic models for the QuantLab research DSL.

Defines the domain model for quantitative research campaigns:
markets, timeframes, strategy building blocks, and acceptance criteria.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ── Enums ──────────────────────────────────────────────────────────────────────


class Market(str, Enum):
    """Recognised financial markets."""

    EURUSD = "EURUSD"
    GBPUSD = "GBPUSD"
    USDJPY = "USDJPY"
    AUDUSD = "AUDUSD"
    USDCAD = "USDCAD"
    USDCHF = "USDCHF"
    NZDUSD = "NZDUSD"
    EURGBP = "EURGBP"
    EURJPY = "EURJPY"
    GBPJPY = "GBPJPY"

    # Indices
    SP500 = "SP500"
    NASDAQ = "NASDAQ"
    DOWJONES = "DOWJONES"
    DAX = "DAX"
    FTSE100 = "FTSE100"

    # Commodities
    XAUUSD = "XAUUSD"
    XAGUSD = "XAGUSD"
    BTCUSD = "BTCUSD"
    ETHUSD = "ETHUSD"


class Timeframe(str, Enum):
    """Recognised chart timeframes."""

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"
    MN = "MN"


class StrategyDirection(str, Enum):
    """Direction a strategy may trade."""

    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


# ── Building blocks ────────────────────────────────────────────────────────────


class IndicatorConfig(BaseModel):
    """Configuration for a single technical indicator.

    Examples:
        - ``{name: "RSI", params: {period: 14}}``
        - ``{name: "EMA", params: {period: 200}}``
    """

    name: str = Field(..., description="Indicator name (e.g. RSI, EMA, BB)")
    params: dict[str, Any] = Field(default_factory=dict, description="Indicator parameters")


class EntryRule(BaseModel):
    """Condition that triggers a trade entry."""

    description: str = Field(..., description="Human-readable rule description")
    conditions: list[str] = Field(default_factory=list, description="Condition expressions")


class ExitRule(BaseModel):
    """Condition that triggers a trade exit."""

    description: str = Field(..., description="Human-readable rule description")
    conditions: list[str] = Field(default_factory=list, description="Condition expressions")


class BuildingBlock(BaseModel):
    """A reusable trading logic component (indicator + rules)."""

    name: str = Field(..., description="Unique building-block name")
    indicator: IndicatorConfig
    entry: EntryRule | None = None
    exit: ExitRule | None = None


# ── Acceptance criteria ────────────────────────────────────────────────────────


class AcceptanceCriterion(BaseModel):
    """A measurable acceptance criterion for a research campaign."""

    metric: str = Field(..., description="Metric name (e.g. profit_factor, sharpe)")
    operator: str = Field(..., description="Comparison operator (>, >=, <, <=, ==)")
    value: float = Field(..., description="Threshold value")


# ── Strategy ────────────────────────────────────────────────────────────────────


class Strategy(BaseModel):
    """A named strategy composed of building blocks."""

    name: str = Field(..., description="Unique strategy name within campaign")
    direction: StrategyDirection = StrategyDirection.BOTH
    building_blocks: list[str] = Field(
        default_factory=list,
        description="Names of building blocks this strategy uses",
    )


# ── Root config ────────────────────────────────────────────────────────────────


class ResearchConfig(BaseModel):
    """Top-level research campaign configuration.

    Serialises to/from YAML for versionable, human-readable definitions.
    """

    campaign: str = Field(..., description="Campaign name / identifier")
    market: Market
    timeframe: Timeframe
    building_blocks: list[BuildingBlock] = Field(default_factory=list)
    strategies: list[Strategy] = Field(default_factory=list)
    criteria: list[AcceptanceCriterion] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_strategy_names(self) -> ResearchConfig:
        """Ensure all strategy names are unique within a campaign."""
        names = [s.name for s in self.strategies]
        if len(names) != len(set(names)):
            seen: set[str] = set()
            dups = {n for n in names if n in seen or seen.add(n)}
            from quantlab.tools.exceptions import ValidationError

            raise ValidationError(
                f"Duplicate strategy names: {', '.join(sorted(dups))}"
            )
        return self

    @model_validator(mode="after")
    def _validate_building_block_references(self) -> ResearchConfig:
        """Ensure all building-block references in strategies exist."""
        block_names = {b.name for b in self.building_blocks}
        for strategy in self.strategies:
            for ref in strategy.building_blocks:
                if ref not in block_names:
                    from quantlab.tools.exceptions import ValidationError

                    raise ValidationError(
                        f"Strategy '{strategy.name}' references unknown building "
                        f"block '{ref}'. Available: {', '.join(sorted(block_names)) or '(none)'}"
                    )
        return self
