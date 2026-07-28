"""Strategic Evolution Engine — evolves trading strategies over time.

The SEE closes the loop between MetaGuardian degradation detection and
strategy improvement or replacement. It supports two evolution modes:

1. **Genetic**: CFX parameter mutation via existing OptimizerAutomation
2. **Generative**: New strategy generation via ResearchDirector + Builder pipeline
"""

from __future__ import annotations

from quantlab.evolution.config import EvolutionConfig, EvolutionMode
from quantlab.evolution.fitness import FitnessFunction
from quantlab.evolution.genetic import GeneticOptimizer
from quantlab.evolution.models import (
    CandidateStatus,
    EvolutionCandidate,
    EvolutionResult,
    EvolutionSignal,
)
from quantlab.evolution.novelty import NoveltyGenerator
from quantlab.evolution.pool import CandidatePool
from quantlab.evolution.validator import CandidateValidator

__all__ = [
    "CandidatePool",
    "CandidateStatus",
    "CandidateValidator",
    "EvolutionCandidate",
    "EvolutionConfig",
    "EvolutionMode",
    "EvolutionResult",
    "EvolutionSignal",
    "FitnessFunction",
    "GeneticOptimizer",
    "NoveltyGenerator",
]
