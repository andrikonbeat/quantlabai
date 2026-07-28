"""StrategyGenerator — unified facade for strategy generation and evolution."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from quantlab.evolution.config import EvolutionConfig, EvolutionMode
from quantlab.evolution.genetic import GeneticOptimizer
from quantlab.evolution.models import CandidateStatus, EvolutionCandidate, EvolutionSignal
from quantlab.evolution.novelty import NoveltyGenerator
from quantlab.evolution.pool import CandidatePool
from quantlab.evolution.validator import CandidateValidator

logger = logging.getLogger(__name__)


class StrategyGenerator:
    """Unified entry point for strategy generation and evolution.

    Accepts user intent (market, timeframe, risk profile, objective) and
    orchestrates the full lifecycle: generate/evolve → backtest → validate → score.
    """

    def __init__(
        self,
        config: Optional[EvolutionConfig] = None,
        pool: Optional[CandidatePool] = None,
        genetic: Optional[GeneticOptimizer] = None,
        novelty: Optional[NoveltyGenerator] = None,
        validator: Optional[CandidateValidator] = None,
    ) -> None:
        self.config = config or EvolutionConfig()
        self.pool = pool or CandidatePool(
            pool_directory=self.config.pool_directory
        )
        self._genetic = genetic
        self._novelty = novelty
        self._validator = validator

    async def generate(self, intent: Dict[str, Any]) -> List[EvolutionCandidate]:
        """Generate strategies from user intent.

        Args:
            intent: Dict with keys: market, timeframe, risk_profile, objective, count, mode

        Returns:
            Ranked list of validated EvolutionCandidate objects.
        """
        raw = intent.get("mode", "full")
        try:
            mode = EvolutionMode(raw.lower().replace("-", "_"))
        except ValueError:
            mode = EvolutionMode.FULL
        count = intent.get("count", 5)
        candidates: List[EvolutionCandidate] = []

        if mode in (EvolutionMode.FULL, EvolutionMode.GENERATIVE_ONLY):
            if self._novelty is not None:
                novel = await self._novelty.generate(context=intent)
                candidates.extend(novel[:count])

        if mode in (EvolutionMode.FULL, EvolutionMode.GENETIC_ONLY):
            if self._genetic is not None:
                genetic_candidates = await self._genetic.optimize(
                    strategy_id=intent.get("strategy_id", "default"),
                    cfx_content=intent.get("cfx_content", ""),
                )
                candidates.extend(genetic_candidates[:count])

        # Persist to pool
        for candidate in candidates:
            self.pool.add(candidate)

        # Validate if validator available
        if self._validator is not None and candidates:
            validated = await self._validator.validate_batch(candidates)
            # Sort by fitness descending
            validated.sort(key=lambda c: c.fitness_score, reverse=True)
            return validated

        return candidates

    async def evolve(self, strategy_id: str) -> List[EvolutionCandidate]:
        """Evolve an existing strategy from the pool.

        Args:
            strategy_id: ID of the strategy to evolve.

        Returns:
            List of evolved candidates.
        """
        parent = self.pool.get(strategy_id)
        if parent is None:
            logger.warning("Strategy %s not found in pool", strategy_id)
            return []

        intent = {
            "strategy_id": strategy_id,
            "cfx_content": parent.cfx_content or "",
            "mode": "genetic_only",
            "market": parent.validation_results.get("market", "forex"),
            "timeframe": parent.validation_results.get("timeframe", "H1"),
        }
        return await self.generate(intent)

    def list_strategies(
        self, status: Optional[CandidateStatus] = None
    ) -> List[EvolutionCandidate]:
        """List strategies from the pool.

        Args:
            status: Optional status filter.

        Returns:
            List of matching candidates.
        """
        if status is not None:
            return self.pool.get_by_status(status)
        return self.pool.load_all()
