"""LLMAdversarialStrategy — falsation via LLM adversarial refutation.

Prompts the LLM (with temperature=0.2) to actively refute the hypothesis
using its ``llm_rationale``, ``source_urls``, and ``data_sources``. The
LLM returns a JSON with ``score`` (0-1) and ``evidence`` (list of
counter-arguments). If the LLM is unavailable, the strategy skips
gracefully without affecting other strategies (RF-4).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from quantlab.dsl.models import HypothesisConfig, LLMConfig
from quantlab.agents.llm_research_agent import LLMResearchAgent
from quantlab.agents.refutation.models import FalsationVerdict
from quantlab.agents.refutation.strategies import RefutationStrategy

logger = logging.getLogger(__name__)


class LLMAdversarialStrategy(RefutationStrategy):
    """Falsation strategy that uses an LLM to adversarially refute hypotheses.

    Builds a structured prompt from the hypothesis's rationale and sources,
    calls the LLM provider with temperature=0.2, and parses the JSON response.

    Args:
        llm_config: ``LLMConfig`` for the LLM call. Defaults to
            ``LLMConfig(temperature=0.2)``.
        llm_agent: An ``LLMResearchAgent`` instance. Created with defaults
            if omitted.
    """

    def __init__(
        self,
        llm_config: LLMConfig | None = None,
        llm_agent: LLMResearchAgent | None = None,
    ) -> None:
        self._llm_config = llm_config or LLMConfig(temperature=0.2)
        self._llm_agent = llm_agent or LLMResearchAgent()

    async def refute(
        self,
        hypothesis: HypothesisConfig,
        market_context: dict[str, Any] | None = None,
    ) -> FalsationVerdict:
        """Evaluate a hypothesis by asking the LLM to refute it.

        Args:
            hypothesis: The hypothesis to evaluate.
            market_context: Optional context (unused in this strategy).

        Returns:
            A ``FalsationVerdict``.
        """
        prompt = self._build_prompt(hypothesis)

        try:
            response_text = await self._llm_agent.call_llm(
                prompt, self._llm_config
            )
        except Exception:
            logger.debug(
                "LLM unavailable for '%s' — skipping adversarial strategy",
                hypothesis.name,
            )
            return FalsationVerdict(
                hypothesis_name=hypothesis.name,
                falsification_score=0.0,
                evidence=[],
                strategy="llm_adversarial",
            )

        try:
            result: dict[str, Any] = json.loads(response_text)
            score = float(result.get("score", 0.0))
            evidence: list[str] = result.get("evidence", [])
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.debug(
                "Failed to parse LLM response for '%s' — score=0",
                hypothesis.name,
            )
            return FalsationVerdict(
                hypothesis_name=hypothesis.name,
                falsification_score=0.0,
                evidence=[],
                strategy="llm_adversarial",
            )

        # Clamp score to [0.0, 1.0]
        score = max(0.0, min(1.0, score))

        logger.debug(
            "LLMAdversarial for '%s': score=%.2f evidence=%d items",
            hypothesis.name,
            score,
            len(evidence),
        )

        return FalsationVerdict(
            hypothesis_name=hypothesis.name,
            falsification_score=score,
            evidence=evidence,
            strategy="llm_adversarial",
        )

    def _build_prompt(self, hypothesis: HypothesisConfig) -> str:
        """Build a structured prompt asking the LLM to refute a hypothesis.

        Args:
            hypothesis: The hypothesis config with rationale and sources.

        Returns:
            A formatted prompt string.
        """
        sections: list[str] = [
            "You are a quantitative analyst conducting adversarial review. ",
            "Your task is to ACTIVELY REFUTE the following trading hypothesis.\n",
            f"Hypothesis: {hypothesis.name}",
            f"Description: {hypothesis.description}",
            f"Rationale: {hypothesis.llm_rationale or 'N/A'}",
            f"Expected Outcome: {hypothesis.expected_outcome or 'N/A'}",
            f"Source URLs: {', '.join(hypothesis.source_urls) if hypothesis.source_urls else 'N/A'}",
            f"Data Sources: {', '.join(hypothesis.data_sources) if hypothesis.data_sources else 'N/A'}",
            "",
            "Find counter-arguments, logical flaws, and missing context. "
            "Be critical — your goal is to identify why this hypothesis MIGHT fail.",
            "",
            "Return your response as valid JSON with the following structure:",
            "{",
            '  "score": 0.0 to 1.0,  # How strongly you refute this hypothesis',
            '  "evidence": [          # List of counter-arguments',
            '    "First counter-argument with reasoning",',
            '    "Second counter-argument with reasoning"',
            "  ]",
            "}",
            "",
            "IMPORTANT: Return ONLY valid JSON. No markdown, no explanation.",
        ]
        return "\n".join(sections)


__all__ = ["LLMAdversarialStrategy"]
