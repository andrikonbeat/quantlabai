"""RegimeMismatchStrategy — falsation via regime mismatch detection.

Compares the hypothesis's assumed market regime (inferred from its
description) against the current detected regime. A mismatch increases
the falsification score by up to 0.6 points (RF-2).

Reuses the same regime classification logic from
``StatisticsAgent.detect_regime_change()`` (design decision 4).
"""

from __future__ import annotations

import logging
from typing import Any

from quantlab.dsl.models import HypothesisConfig
from quantlab.agents.refutation.models import FalsationVerdict
from quantlab.agents.refutation.strategies import RefutationStrategy

logger = logging.getLogger(__name__)

# ── Regime keyword matching ────────────────────────────────────────────────────

# Map description keywords to assumed market regimes.
_ASSUMED_REGIME_KEYWORDS: dict[str, str] = {
    "trend-following": "trending",
    "trend following": "trending",
    "trend": "trending",
    "momentum": "trending",
    "mean-reversion": "range-bound",
    "mean reversion": "range-bound",
    "range-bound": "range-bound",
    "range bound": "range-bound",
}


def _infer_assumed_regime(description: str) -> str:
    """Infer the assumed market regime from a hypothesis description.

    Args:
        description: The hypothesis description text.

    Returns:
        One of ``"trending"``, ``"range-bound"``, or ``"unknown"`` if no
        regime keyword is matched.
    """
    desc_lower = description.lower().strip()
    if not desc_lower:
        return "unknown"

    for keyword, regime in _ASSUMED_REGIME_KEYWORDS.items():
        if keyword in desc_lower:
            return regime

    return "unknown"


def _compute_mismatch_score(
    assumed_regime: str,
    detected_regime: str,
) -> tuple[float, list[str]]:
    """Compute falsation score and evidence for a regime mismatch.

    Args:
        assumed_regime: The regime inferred from the hypothesis description.
        detected_regime: The current detected market regime.

    Returns:
        Tuple of ``(score, evidence)``. Score is 0.0 when regimes match or
        when either regime is unknown, else ranges 0.3–0.6.
    """
    if assumed_regime == "unknown" or detected_regime == "unknown":
        return 0.0, []

    if assumed_regime == detected_regime:
        return 0.0, []

    # Regime mismatch: score based on severity
    evidence = [
        f"Hypothesis assumes '{assumed_regime}' regime but "
        f"detected regime is '{detected_regime}'",
        "Regime mismatch increases falsation risk",
    ]
    score = 0.5  # base mismatch score
    return score, evidence


class RegimeMismatchStrategy(RefutationStrategy):
    """Evaluates a hypothesis by comparing its assumed regime against reality.

    Uses keyword matching on the hypothesis description to infer the assumed
    regime, then compares it with the ``detected_regime`` provided through
    ``market_context``.

    Args:
        detect_regime: Optional callable for external regime detection
            injection. When provided, it will be used instead of
            ``market_context["detected_regime"]``.
    """

    def __init__(
        self,
        detect_regime: Any = None,
    ) -> None:
        self._detect_regime = detect_regime

    async def refute(
        self,
        hypothesis: HypothesisConfig,
        market_context: dict[str, Any] | None = None,
    ) -> FalsationVerdict:
        """Evaluate regime mismatch for a single hypothesis.

        Args:
            hypothesis: The hypothesis to evaluate.
            market_context: Optional dict that may contain ``detected_regime``.

        Returns:
            A ``FalsationVerdict``.
        """
        # Infer assumed regime from description
        assumed = _infer_assumed_regime(hypothesis.description)

        # Resolve detected regime
        detected: str | None = None
        if self._detect_regime is not None:
            detected = self._detect_regime(hypothesis, market_context)
        elif market_context is not None:
            detected = market_context.get("detected_regime")

        if detected is None:
            logger.debug(
                "No detected regime for '%s' — score=0",
                hypothesis.name,
            )
            return FalsationVerdict(
                hypothesis_name=hypothesis.name,
                falsification_score=0.0,
                evidence=[],
                strategy="regime_mismatch",
            )

        score, evidence = _compute_mismatch_score(assumed, detected)

        logger.debug(
            "RegimeMismatch for '%s': assumed=%s detected=%s score=%.2f",
            hypothesis.name,
            assumed,
            detected,
            score,
        )

        return FalsationVerdict(
            hypothesis_name=hypothesis.name,
            falsification_score=score,
            evidence=evidence,
            strategy="regime_mismatch",
        )


__all__ = ["RegimeMismatchStrategy", "_infer_assumed_regime"]
