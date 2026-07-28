"""Strategic Evolution Engine — evolves trading strategies over time.

The SEE closes the loop between MetaGuardian degradation detection and
strategy improvement or replacement. It supports two evolution modes:

1. **Genetic**: CFX parameter mutation via existing OptimizerAutomation
2. **Generative**: New strategy generation via ResearchDirector + Builder pipeline
"""

from __future__ import annotations

from quantlab.evolution.config import EvolutionConfig, EvolutionMode
from quantlab.evolution.models import (
    CandidateStatus,
    EvolutionCandidate,
    EvolutionResult,
    EvolutionSignal,
)

__all__ = [
    "EvolutionCandidate",
    "EvolutionConfig",
    "EvolutionMode",
    "EvolutionResult",
    "EvolutionSignal",
    "CandidateStatus",
]
