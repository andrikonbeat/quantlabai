"""RefutationStrategy ABC — base class for all refutation strategies.

Each strategy implements the ``refute()`` async method that evaluates a
single hypothesis and returns a ``FalsationVerdict``.

Follows the same Strategy pattern as HypothesisBuilder (design decision 1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from quantlab.dsl.models import HypothesisConfig
from quantlab.agents.refutation.models import FalsationVerdict


class RefutationStrategy(ABC):
    """Abstract base for a refutation strategy.

    Each concrete strategy implements ``refute()`` to evaluate a hypothesis
    against a specific falsation dimension.
    """

    @abstractmethod
    async def refute(
        self,
        hypothesis: HypothesisConfig,
        market_context: dict[str, Any] | None = None,
    ) -> FalsationVerdict:
        """Evaluate a hypothesis and return a falsation verdict.

        Args:
            hypothesis: The hypothesis config to evaluate.
            market_context: Optional market metadata (e.g. detected regime,
                current volatility regime).

        Returns:
            A ``FalsationVerdict`` with the falsation score, evidence, and
            strategy name.
        """
        ...


__all__ = ["RefutationStrategy"]
