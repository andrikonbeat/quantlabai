"""Pydantic models for the MetaGuardian governance system."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Dict


class GuardianType(str, Enum):
    """Types of guardians in the MetaGuardian system."""
    MARKET = "market"
    RISK = "risk"
    PORTFOLIO = "portfolio"
    CAPITAL = "capital"
    QUALITY = "quality"
    EXECUTION = "execution"


class GuardianStatus(str, Enum):
    """Status levels for guardian health checks."""
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class GuardianResult(BaseModel):
    """Result of a guardian health check."""
    model_config = ConfigDict(frozen=True)

    guardian_type: GuardianType
    status: GuardianStatus
    score: float = Field(ge=0.0, le=1.0)
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)


class PortfolioState(str, Enum):
    """Portfolio-level states in the MetaGuardian state machine."""
    NORMAL = "NORMAL"
    VIGILANCE = "VIGILANCE"
    DEFENSIVE = "DEFENSIVE"
    QUARANTINE = "QUARANTINE"
    RECOVERY = "RECOVERY"


class StrategyState(str, Enum):
    """Per-strategy states for degradation tracking."""
    ACTIVE = "ACTIVE"
    MONITORING = "MONITORING"
    DEGRADING = "DEGRADING"
    REPLACEMENT_PENDING = "REPLACEMENT_PENDING"
    RETIRED = "RETIRED"


class MetaGuardianConfig(BaseModel):
    """Configuration for the MetaGuardian orchestrator."""
    model_config = ConfigDict(frozen=True)

    weights: Dict[GuardianType, float] = Field(
        default_factory=lambda: {
            GuardianType.MARKET: 0.15,
            GuardianType.RISK: 0.30,
            GuardianType.PORTFOLIO: 0.20,
            GuardianType.CAPITAL: 0.15,
            GuardianType.QUALITY: 0.10,
            GuardianType.EXECUTION: 0.10,
        }
    )

    thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "defensive_drawdown": 0.10,
            "quarantine_drawdown": 0.20,
            "recovery_drawdown": 0.05,
            "degradation_checks": 3,
            "retirement_checks": 5,
        }
    )