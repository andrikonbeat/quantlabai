"""EvolutionOrchestrator — central coordinator for the Strategic Evolution Engine."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

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

logger = logging.getLogger(__name__)


class EvolutionOrchestrator:
    """Central coordinator for the Strategic Evolution Engine.

    Handles:
    - Scheduled cycle triggers (configurable interval)
    - MetaGuardian signal-based triggers (degraded strategies)
    - Evolution mode selection and dispatch
    - Priority sorting of pending work
    - Concurrency limits
    """

    def __init__(
        self,
        config: EvolutionConfig,
        pool: Optional[CandidatePool] = None,
        fitness: Optional[FitnessFunction] = None,
        genetic: Optional[GeneticOptimizer] = None,
        novelty: Optional[NoveltyGenerator] = None,
        validator: Optional[CandidateValidator] = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            config: Evolution configuration.
            pool: Candidate pool instance.
            fitness: Fitness function instance.
            genetic: Genetic optimizer instance.
            novelty: Novelty generator instance.
            validator: Candidate validator instance.
        """
        self.config = config
        self.pool = pool or CandidatePool(
            pool_directory=config.pool_directory
        )
        self.fitness = fitness or FitnessFunction()
        self._genetic = genetic
        self._novelty = novelty
        self._validator = validator
        self._active_cycles: Dict[str, EvolutionResult] = {}
        self._cycle_count: int = 0
        self._last_cycle_time: float = 0.0
        self._running: bool = False
        self._task: Optional[asyncio.Task[None]] = None

    @property
    def enabled(self) -> bool:
        """Whether evolution is enabled."""
        return self.config.enabled and self.config.mode != EvolutionMode.DISABLED

    @property
    def active_cycle_count(self) -> int:
        """Number of currently active evolution cycles."""
        return len(self._active_cycles)

    async def start(self) -> None:
        """Start the scheduled evolution loop."""
        if self._running:
            logger.warning("EvolutionOrchestrator already running")
            return
        if not self.enabled:
            logger.info("EvolutionOrchestrator is disabled — not starting")
            return

        self._running = True
        interval = self.config.schedule.interval_hours * 3600
        logger.info(
            "EvolutionOrchestrator started (interval=%.1fh, mode=%s)",
            self.config.schedule.interval_hours, self.config.mode
        )

        self._task = asyncio.create_task(self._run_loop(interval))

    async def stop(self) -> None:
        """Stop the scheduled evolution loop."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        logger.info("EvolutionOrchestrator stopped")

    async def _run_loop(self, interval: float) -> None:
        """Main evolution loop — runs on schedule.

        Args:
            interval: Sleep interval between cycles in seconds.
        """
        while self._running:
            now = time.time()
            if now - self._last_cycle_time >= interval:
                await self._run_cycle(signals=None)
                self._last_cycle_time = now
            await asyncio.sleep(min(60, interval))  # Check every minute

    async def process_signals(
        self, signals: List[EvolutionSignal]
    ) -> List[EvolutionResult]:
        """Process incoming MetaGuardian signals.

        Args:
            signals: List of signals from MetaGuardian.

        Returns:
            List of evolution cycle results.
        """
        if not self.enabled:
            logger.info("Evolution disabled — ignoring %d signals", len(signals))
            return []

        # Sort signals by priority (highest first)
        sorted_signals = sorted(
            signals, key=lambda s: s.priority, reverse=True
        )

        results: List[EvolutionResult] = []
        for signal in sorted_signals:
            if self.active_cycle_count >= self.config.concurrency.max_concurrent_evolutions:
                logger.warning("Concurrency limit reached — deferring signal %s", signal.strategy_id)
                break

            result = await self._execute_signal(signal)
            results.append(result)

        return results

    async def _execute_signal(self, signal: EvolutionSignal) -> EvolutionResult:
        """Execute an evolution cycle for a single signal.

        Args:
            signal: The triggering signal.

        Returns:
            Evolution cycle result.
        """
        self._cycle_count += 1
        cycle_id = f"cycle-{self._cycle_count:04d}-{int(time.time())}"
        result = EvolutionResult(
            cycle_id=cycle_id,
            mode=self.config.mode,
            signal_count=1,
        )

        logger.info(
            "Evolution cycle %s: strategy=%s, priority=%d, mode=%s",
            cycle_id, signal.strategy_id, signal.priority, self.config.mode
        )

        self._active_cycles[cycle_id] = result

        try:
            candidates: List[EvolutionCandidate] = []

            if self.config.mode in (EvolutionMode.FULL, EvolutionMode.GENETIC_ONLY):
                if self._genetic is not None:
                    genetic_candidates = await self._genetic.optimize(
                        strategy_id=signal.strategy_id,
                        cfx_content="",  # Would load from strategy store
                    )
                    candidates.extend(genetic_candidates)

            if self.config.mode in (EvolutionMode.FULL, EvolutionMode.GENERATIVE_ONLY):
                if self._novelty is not None:
                    novel_candidates = await self._novelty.generate(
                        context={"signal": signal.model_dump()},
                    )
                    candidates.extend(novel_candidates)

            # Persist candidates to pool
            for candidate in candidates:
                self.pool.add(candidate)

            result.candidates_generated = len(candidates)

            # Validate candidates
            if self._validator is not None and candidates:
                validated = await self._validator.validate_batch(candidates)
                result.candidates_passed = sum(
                    1 for c in validated if c.status == CandidateStatus.PASSED
                )

                # Promote candidates above threshold
                ready = self.pool.get_ready_for_promotion(
                    threshold=self.config.concurrency.pool_promotion_threshold
                )
                for ready_candidate in ready:
                    self.pool.promote(ready_candidate.candidate_id)
                result.candidates_promoted = len(ready)

        except Exception:
            logger.exception("Evolution cycle %s failed", cycle_id)
            result.errors.append("Cycle failed with exception")

        result.completed_at = datetime.now()
        # Remove from active set when done so concurrency limit works correctly
        self._active_cycles.pop(cycle_id, None)
        return result

    async def _run_cycle(
        self, signals: Optional[List[EvolutionSignal]] = None
    ) -> EvolutionResult:
        """Run a full evolution cycle.

        Args:
            signals: Optional list of MG signals (uses empty if not provided).

        Returns:
            Evolution cycle result.
        """
        if signals is None:
            signals = []

        # Clean expired candidates first
        removed = self.pool.cleanup_expired(
            ttl_days=self.config.candidate_ttl_days
        )
        if removed:
            logger.info("Cleaned %d expired candidates", removed)

        # Process signals if any
        if signals:
            results = await self.process_signals(signals)
            if results:
                return results[0]

        # Scheduled cycle — generate candidates
        self._cycle_count += 1
        cycle_id = f"cycle-{self._cycle_count:04d}-{int(time.time())}"
        result = EvolutionResult(
            cycle_id=cycle_id, mode=self.config.mode
        )

        logger.info("Scheduled evolution cycle %s starting", cycle_id)
        self._active_cycles[cycle_id] = result

        try:
            # Genetic optimization for existing strategies
            if self.config.mode in (EvolutionMode.FULL, EvolutionMode.GENETIC_ONLY):
                if self._genetic is not None:
                    candidates = await self._genetic.optimize(
                        strategy_id="default",
                        cfx_content="",
                    )
                    for c in candidates:
                        self.pool.add(c)
                    result.candidates_generated += len(candidates)

            # Novelty generation
            if self.config.mode in (EvolutionMode.FULL, EvolutionMode.GENERATIVE_ONLY):
                if self._novelty is not None:
                    candidates = await self._novelty.generate(
                        context={"cycle": "scheduled"},
                    )
                    for c in candidates:
                        self.pool.add(c)
                    result.candidates_generated += len(candidates)

        except Exception:
            logger.exception("Scheduled cycle %s failed", cycle_id)
            result.errors.append("Scheduled cycle failed with exception")

        result.completed_at = datetime.now()
        self._active_cycles[cycle_id] = result
        return result
