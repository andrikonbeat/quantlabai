"""Configuration models for the Strategic Evolution Engine."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field, ConfigDict


class EvolutionMode(str, Enum):
    """Operational mode for the evolution engine."""
    DISABLED = "disabled"
    GENETIC_ONLY = "genetic_only"
    GENERATIVE_ONLY = "generative_only"
    FULL = "full"


class ScheduleConfig(BaseModel):
    """Scheduled trigger configuration."""
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    interval_hours: float = Field(default=168, ge=1.0, description="Hours between scheduled cycles")
    max_candidates_per_cycle: int = Field(default=3, ge=1, le=20)


class ConcurrencyConfig(BaseModel):
    """Concurrency and resource limits."""
    model_config = ConfigDict(frozen=True)

    max_concurrent_evolutions: int = Field(default=1, ge=1, le=10)
    max_pool_size: int = Field(default=50, ge=1, le=1000)
    pool_promotion_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class WeightProfile(BaseModel):
    """Fitness function weight profile."""
    model_config = ConfigDict(frozen=True)

    sharpe: float = Field(default=0.25, ge=0.0, le=1.0)
    profit_factor: float = Field(default=0.20, ge=0.0, le=1.0)
    sortino: float = Field(default=0.15, ge=0.0, le=1.0)
    max_drawdown: float = Field(default=0.15, ge=0.0, le=1.0)
    recovery_factor: float = Field(default=0.10, ge=0.0, le=1.0)
    expectancy: float = Field(default=0.10, ge=0.0, le=1.0)
    trades_quality: float = Field(default=0.05, ge=0.0, le=1.0)

    def as_dict(self) -> Dict[str, float]:
        return {
            "sharpe": self.sharpe,
            "profit_factor": self.profit_factor,
            "sortino": self.sortino,
            "max_drawdown": self.max_drawdown,
            "recovery_factor": self.recovery_factor,
            "expectancy": self.expectancy,
            "trades_quality": self.trades_quality,
        }


class EvolutionConfig(BaseModel):
    """Top-level configuration for the Strategic Evolution Engine."""
    model_config = ConfigDict(frozen=True)

    enabled: bool = Field(default=False, description="Master toggle — disabled by default")
    mode: EvolutionMode = Field(default=EvolutionMode.FULL)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    weight_profile: WeightProfile = Field(default_factory=WeightProfile)
    mg_signal_priorities: Dict[str, int] = Field(
        default_factory=lambda: {
            "RETIRED": 100,
            "REPLACEMENT_PENDING": 80,
            "DEGRADING": 60,
            "MONITORING": 30,
        }
    )
    candidate_ttl_days: int = Field(default=30, ge=1, le=365)
    pool_directory: str = Field(default=".evolution_pool")
