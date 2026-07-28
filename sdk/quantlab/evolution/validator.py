"""CandidateValidator — validates candidates through 3-tier BT → WF → MC pipeline."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from quantlab.evolution.config import EvolutionConfig
from quantlab.evolution.fitness import FitnessFunction
from quantlab.evolution.models import CandidateStatus, EvolutionCandidate
from quantlab.evolution.pool import CandidatePool
from quantlab.pipeline.base import Pipeline, PipelineContext
from quantlab.pipeline.models import StageStatus
from quantlab.pipeline.runner import PipelineRunner

logger = logging.getLogger(__name__)

# Default tier fitness thresholds
TIER1_BT_THRESHOLD = 30.0   # minimum fitness to advance to walk-forward
TIER2_WF_THRESHOLD = 50.0   # minimum fitness to advance to Monte Carlo
TIER3_MC_THRESHOLD = 60.0   # minimum fitness to be marked PASSED


class CandidateValidator:
    """Validates evolution candidates through the full validation pipeline.

    Runs each candidate through backtest → walk-forward → Monte Carlo
    using the existing PipelineRunner, with per-tier gating: only pass
    to WF if backtest passes, only pass to MC if WF passes.
    """

    def __init__(
        self,
        config: EvolutionConfig,
        fitness: FitnessFunction,
        pool: CandidatePool,
        runner: Optional[PipelineRunner] = None,
    ) -> None:
        """Initialize the validator.

        Args:
            config: Evolution configuration.
            fitness: Fitness function for scoring.
            pool: Candidate pool for persisting results.
            runner: Optional PipelineRunner (creates a default one).
        """
        self._config = config
        self._fitness = fitness
        self._pool = pool
        self._runner = runner or PipelineRunner()

    async def validate(self, candidate: EvolutionCandidate) -> EvolutionCandidate:
        """Run the full validation pipeline for a candidate.

        Three-tier validation:
          Tier 1: Backtest — all candidates
          Tier 2: Walk-Forward — only if BT fitness >= TIER1_BT_THRESHOLD
          Tier 3: Monte Carlo — only if WF fitness >= TIER2_WF_THRESHOLD

        Args:
            candidate: Candidate to validate.

        Returns:
            Updated candidate with validation results.
        """
        validation_results: Dict[str, Any] = {}
        errors: List[str] = []
        overall_status = CandidateStatus.FAILED

        # Mark as validating
        try:
            self._pool.update_status(candidate.candidate_id, CandidateStatus.VALIDATING)
        except Exception:
            pass  # pool update is best-effort

        # ── Tier 1: Backtest ────────────────────────────────────────────
        bt_result = await self._run_tier(
            candidate, "backtest",
            stages=["daemon_start", "load_cfx", "run_backtest", "compute_stats", "export"],
        )
        bt_fitness = bt_result.get("fitness", 0.0)
        validation_results["backtest"] = bt_result

        logger.info(
            "Tier-1 (BT) for %s: fitness=%.2f, threshold=%.1f",
            candidate.candidate_id[:12], bt_fitness, TIER1_BT_THRESHOLD,
        )

        if bt_fitness < TIER1_BT_THRESHOLD:
            errors.append(f"Tier-1 backtest failed: fitness {bt_fitness:.2f} < {TIER1_BT_THRESHOLD}")
            validation_results["passed_tier1"] = False
            validation_results["passed_tier2"] = False
            validation_results["passed_tier3"] = False
            return self._finalize(candidate, overall_status, validation_results, errors)

        validation_results["passed_tier1"] = True

        # ── Tier 2: Walk-Forward ────────────────────────────────────────
        wf_result = await self._run_tier(
            candidate, "walk_forward",
            stages=["daemon_start", "load_cfx", "run_backtest", "compute_stats",
                     "walk_forward", "export"],
        )
        wf_fitness = wf_result.get("fitness", 0.0)
        validation_results["walk_forward"] = wf_result

        logger.info(
            "Tier-2 (WF) for %s: fitness=%.2f, threshold=%.1f",
            candidate.candidate_id[:12], wf_fitness, TIER2_WF_THRESHOLD,
        )

        if wf_fitness < TIER2_WF_THRESHOLD:
            errors.append(f"Tier-2 walk-forward failed: fitness {wf_fitness:.2f} < {TIER2_WF_THRESHOLD}")
            validation_results["passed_tier2"] = False
            validation_results["passed_tier3"] = False
            return self._finalize(candidate, overall_status, validation_results, errors)

        validation_results["passed_tier2"] = True

        # ── Tier 3: Monte Carlo ─────────────────────────────────────────
        mc_result = await self._run_tier(
            candidate, "monte_carlo",
            stages=["daemon_start", "load_cfx", "run_backtest", "compute_stats",
                     "monte_carlo", "export"],
        )
        mc_fitness = mc_result.get("fitness", 0.0)
        validation_results["monte_carlo"] = mc_result

        logger.info(
            "Tier-3 (MC) for %s: fitness=%.2f, threshold=%.1f",
            candidate.candidate_id[:12], mc_fitness, TIER3_MC_THRESHOLD,
        )

        if mc_fitness >= TIER3_MC_THRESHOLD:
            validation_results["passed_tier3"] = True
            overall_status = CandidateStatus.PASSED
        else:
            errors.append(f"Tier-3 Monte Carlo failed: fitness {mc_fitness:.2f} < {TIER3_MC_THRESHOLD}")
            validation_results["passed_tier3"] = False

        return self._finalize(candidate, overall_status, validation_results, errors)

    async def _run_tier(
        self,
        candidate: EvolutionCandidate,
        tier_name: str,
        stages: List[str],
    ) -> Dict[str, Any]:
        """Run a single validation tier via PipelineRunner.

        Args:
            candidate: Candidate to validate.
            tier_name: Short name for the tier ("backtest", "walk_forward", "monte_carlo").
            stages: List of stage names to run.

        Returns:
            Dict with tier result (fitness, duration, success, details).
        """
        from quantlab.pipeline.registry import StageRegistry

        registry = StageRegistry()
        pipeline = Pipeline(name=f"validation-{tier_name}")

        for name in stages:
            stage_class = registry.get_stage_class(name)
            if stage_class is None:
                from quantlab.evolution.genetic import _NoopStage
                stage = _NoopStage(name=name)
            else:
                stage = stage_class()
            pipeline.stages.append(stage)

        pipeline_ctx = PipelineContext(
            config={
                "tier": tier_name,
                "candidate_id": candidate.candidate_id,
                "strategy_id": candidate.strategy_id,
            },
            artifacts={
                "cfx_content": candidate.cfx_content or "",
                "candidate_id": candidate.candidate_id,
                "strategy_id": candidate.strategy_id,
            },
        )

        start = time.monotonic()
        try:
            result = await self._runner.run(pipeline, pipeline_ctx)
            duration = time.monotonic() - start

            fitness = self._extract_fitness(result)
            return {
                "fitness": round(fitness, 4),
                "duration_seconds": round(duration, 2),
                "successful": result.is_successful,
                "stages_completed": sum(
                    1 for s in result.stages if s.status == StageStatus.COMPLETED
                ),
                "stages_total": len(result.stages),
                "error": result.error,
            }
        except Exception as exc:
            duration = time.monotonic() - start
            logger.warning("Tier '%s' failed for %s: %s", tier_name, candidate.candidate_id[:12], exc)
            return {
                "fitness": 0.0,
                "duration_seconds": round(duration, 2),
                "successful": False,
                "stages_completed": 0,
                "stages_total": len(stages),
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _extract_fitness(self, pipeline_result: Any) -> float:
        """Extract a fitness score from pipeline results."""
        if pipeline_result is None:
            return 0.0
        if not hasattr(pipeline_result, "is_successful") or not pipeline_result.is_successful:
            return 0.0

        # Look for statistics in stage outputs
        if hasattr(pipeline_result, "stages"):
            for stage in reversed(pipeline_result.stages):
                if stage.output and isinstance(stage.output, dict):
                    stats = stage.output.get("statistics") or stage.output.get("stats")
                    if stats is not None:
                        try:
                            from quantlab.stats.models import StatsResult
                            if isinstance(stats, dict):
                                stats_obj = StatsResult(**stats)
                            else:
                                stats_obj = stats
                            return self._fitness.evaluate(stats_obj)
                        except Exception:
                            pass

        # Fallback: score based on completion ratio
        if hasattr(pipeline_result, "stages"):
            completed = sum(1 for s in pipeline_result.stages if s.status == StageStatus.COMPLETED)
            total = len(pipeline_result.stages) or 1
            return (completed / total) * 50.0
        return 0.0

    def _finalize(
        self,
        candidate: EvolutionCandidate,
        status: CandidateStatus,
        validation_results: Dict[str, Any],
        errors: List[str],
    ) -> EvolutionCandidate:
        """Build the final candidate with updated status and error info."""
        validation_results["status"] = status.value
        validation_results["errors"] = errors

        # Derive final fitness: use the best tier result
        final_fitness = candidate.fitness_score
        for tier in ("monte_carlo", "walk_forward", "backtest"):
            tier_data = validation_results.get(tier, {})
            if isinstance(tier_data, dict):
                tier_fitness = tier_data.get("fitness", 0.0)
                if tier_fitness > final_fitness:
                    final_fitness = tier_fitness

        # Update the pool
        try:
            self._pool.update_status(candidate.candidate_id, status, fitness_score=final_fitness)
        except Exception:
            pass

        return EvolutionCandidate(
            candidate_id=candidate.candidate_id,
            strategy_id=candidate.strategy_id,
            mode=candidate.mode,
            cfx_content=candidate.cfx_content,
            dsl_content=candidate.dsl_content,
            parent_candidate_id=candidate.parent_candidate_id,
            status=status,
            fitness_score=final_fitness,
            validation_results=validation_results,
            created_at=candidate.created_at,
            error=errors[0] if errors else None,
        )

    async def validate_batch(
        self, candidates: List[EvolutionCandidate],
    ) -> List[EvolutionCandidate]:
        """Validate multiple candidates sequentially.

        Args:
            candidates: Candidates to validate.

        Returns:
            List of validated candidates.
        """
        results: List[EvolutionCandidate] = []
        for candidate in candidates:
            result = await self.validate(candidate)
            results.append(result)
        return results
