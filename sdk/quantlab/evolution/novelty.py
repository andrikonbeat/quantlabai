"""NoveltyGenerator — generates new strategies via DSL + Builder pipeline."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from quantlab.evolution.config import EvolutionConfig
from quantlab.evolution.fitness import FitnessFunction
from quantlab.evolution.models import EvolutionCandidate, EvolutionMode


class NoveltyGenerator:
    """Generates novel trading strategies from scratch.

    Drives the ResearchDirector to produce DSL strategy descriptions,
    passes them through the BuilderAgent for CFX generation, runs
    a short backtest, and scores via FitnessFunction.
    """

    def __init__(
        self,
        config: EvolutionConfig,
        fitness: FitnessFunction,
    ) -> None:
        """Initialize the novelty generator.

        Args:
            config: Evolution configuration.
            fitness: Fitness function for scoring.
        """
        self._config = config
        self._fitness = fitness

    async def generate(
        self,
        context: Dict[str, Any],
        parent_candidate_id: Optional[str] = None,
    ) -> List[EvolutionCandidate]:
        """Generate novel strategy candidates.

        Args:
            context: Generation context (market regime, objectives, etc.).
            parent_candidate_id: Optional parent candidate ID.

        Returns:
            List of generated candidates.
        """
        # Placeholder — in production this would:
        # 1. Call ResearchDirector.run() to get DSL strategy descriptions
        # 2. Pass DSL to BuilderAgent for CFX generation
        # 3. Run short backtest via PipelineRunner
        # 4. Score via FitnessFunction
        # 5. Return candidates with scores
        return []
