"""RefutationLayer — proactive falsation system for hypotheses.

Annotates hypotheses with falsification scores and evidence before they
reach the BuilderAgent, without blocking execution (RF-6).

Architecture
------------
::

    HypothesisBuilder → RefutationLayer → builder
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
         RegimeMismatch  Historical   LLM Adversarial
         Strategy      Counter-       Strategy
                        Example
                        Strategy
                │           │           │
                └───────────┼───────────┘
                            ▼
                  Score Aggregation (max)
                            ▼
                  RefutationResult
                  (annotations, no filtering)

Usage::

    layer = RefutationLayer()
    result = await layer.refute(hypotheses, market_context={...})
    # result.verdicts — per-hypothesis falsation scores
    # result.summary — aggregate statistics
"""

from __future__ import annotations

import logging
from typing import Any

from quantlab.dsl.models import HypothesisConfig
from quantlab.agents.refutation.config import RefutationConfig
from quantlab.agents.refutation.models import FalsationVerdict, RefutationResult
from quantlab.agents.refutation.strategies import RefutationStrategy
from quantlab.agents.refutation.strategies.regime import RegimeMismatchStrategy
from quantlab.agents.refutation.strategies.historical import (
    HistoricalCounterExampleStrategy,
)
from quantlab.agents.refutation.strategies.adversarial import (
    LLMAdversarialStrategy,
)

logger = logging.getLogger(__name__)


class RefutationLayer:
    """Facade that dispatches hypotheses to all registered strategies.

    Aggregates scores using MAX (conservative: if ANY strategy finds a
    problem, the hypothesis is considered falsified at that level).

    Does NOT filter hypotheses — it only annotates (RF-6).

    Args:
        config: Optional ``RefutationConfig``. Defaults to enabled.
        strategies: Optional list of ``RefutationStrategy`` instances.
            Defaults to ``[RegimeMismatchStrategy(),
            HistoricalCounterExampleStrategy(), LLMAdversarialStrategy()]``.
    """

    def __init__(
        self,
        config: RefutationConfig | None = None,
        strategies: list[RefutationStrategy] | None = None,
    ) -> None:
        self._config = config or RefutationConfig()
        self._strategies = strategies or [
            RegimeMismatchStrategy(),
            HistoricalCounterExampleStrategy(),
            LLMAdversarialStrategy(),
        ]

    # ── Public API ────────────────────────────────────────────────────────────

    async def refute(
        self,
        hypotheses: list[HypothesisConfig],
        building_blocks: Any = None,
        market_context: dict[str, Any] | None = None,
    ) -> RefutationResult:
        """Evaluate all hypotheses through every enabled strategy.

        Args:
            hypotheses: List of hypothesis configs to evaluate.
            building_blocks: Optional building blocks (reserved for future
                strategies).
            market_context: Optional market metadata (e.g. detected regime).

        Returns:
            A ``RefutationResult`` with per-hypothesis verdicts and an
            aggregate summary.
        """
        if not hypotheses:
            return RefutationResult(verdicts=[], summary={
                "total_verdicts": 0,
                "max_score": 0.0,
                "mean_score": 0.0,
            })

        if not self._config.enabled:
            return self._empty_result(hypotheses)

        return await self._run_strategies(hypotheses, market_context)

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _run_strategies(
        self,
        hypotheses: list[HypothesisConfig],
        market_context: dict[str, Any] | None = None,
    ) -> RefutationResult:
        """Run all strategies against all hypotheses, aggregate with max.

        Args:
            hypotheses: List of hypothesis configs.
            market_context: Optional market metadata.

        Returns:
            Aggregated ``RefutationResult``.
        """
        verdicts: list[FalsationVerdict] = []

        for hyp in hypotheses:
            best_verdict: FalsationVerdict | None = None

            for strategy in self._strategies:
                try:
                    verdict = await strategy.refute(hyp, market_context)
                except Exception:
                    logger.exception(
                        "Strategy '%s' failed for hypothesis '%s' — skipping",
                        type(strategy).__name__,
                        hyp.name,
                    )
                    continue

                # RF-5: Score aggregation = MAX across strategies
                if (
                    best_verdict is None
                    or verdict.falsification_score > best_verdict.falsification_score
                ):
                    best_verdict = verdict

            if best_verdict is not None:
                verdicts.append(best_verdict)

        # Build summary
        scores = [v.falsification_score for v in verdicts]
        summary: dict[str, Any] = {
            "total_verdicts": len(verdicts),
            "max_score": max(scores) if scores else 0.0,
            "mean_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        }

        return RefutationResult(verdicts=verdicts, summary=summary)

    @staticmethod
    def _empty_result(
        hypotheses: list[HypothesisConfig],
    ) -> RefutationResult:
        """Produce a no-op result when the layer is disabled (RF-9).

        Args:
            hypotheses: The input hypotheses (returned with score 0.0).

        Returns:
            A ``RefutationResult`` with zero scores and no evidence.
        """
        verdicts = [
            FalsationVerdict(
                hypothesis_name=h.name,
                falsification_score=0.0,
                evidence=[],
                strategy="none",
            )
            for h in hypotheses
        ]
        summary = {
            "total_verdicts": len(verdicts),
            "max_score": 0.0,
            "mean_score": 0.0,
            "disabled": True,
        }
        return RefutationResult(verdicts=verdicts, summary=summary)


__all__ = [
    "FalsationVerdict",
    "HistoricalCounterExampleStrategy",
    "LLMAdversarialStrategy",
    "RefutationConfig",
    "RefutationLayer",
    "RefutationResult",
    "RefutationStrategy",
]
