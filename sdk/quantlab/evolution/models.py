"""Data models for the Strategic Evolution Engine."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict

from quantlab.evolution.config import EvolutionMode


class CandidateStatus(str, Enum):
    """Status of an evolution candidate."""
    PENDING = "pending"
    VALIDATING = "validating"
    PASSED = "passed"
    FAILED = "failed"
    PROMOTED = "promoted"
    EXPIRED = "expired"


class EvolutionSignal(BaseModel):
    """Signal from MetaGuardian triggering an evolution cycle."""
    model_config = ConfigDict(frozen=True)

    strategy_id: str
    mg_state: str  # e.g. DEGRADING, REPLACEMENT_PENDING, RETIRED
    health_score: float
    timestamp: datetime = Field(default_factory=datetime.now)
    priority: int = Field(default=50, ge=0, le=100)


class EvolutionCandidate(BaseModel):
    """A candidate evolved strategy awaiting or past validation."""
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    strategy_id: str
    mode: EvolutionMode
    cfx_content: Optional[str] = None
    dsl_content: Optional[str] = None
    parent_candidate_id: Optional[str] = None
    status: CandidateStatus = CandidateStatus.PENDING
    fitness_score: float = 0.0
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    promoted_at: Optional[datetime] = None
    error: Optional[str] = None


class EvolutionResult(BaseModel):
    """Result of a single evolution cycle."""
    model_config = ConfigDict(frozen=True)

    cycle_id: str
    mode: EvolutionMode
    candidates_generated: int = 0
    candidates_passed: int = 0
    candidates_promoted: int = 0
    signal_count: int = 0
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    errors: List[str] = Field(default_factory=list)
