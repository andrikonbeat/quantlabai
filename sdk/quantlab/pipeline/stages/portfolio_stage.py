"""PortfolioStage — composes the campaign portfolio (REQ-01 phase 9).

Concrete implementation of the abstract ``PortfolioStage`` anchor: consumes
the selected strategies + review decision and publishes the normalized
portfolio weights as ``portfolio_result``. The default optimizer is the pure
``PortfolioComposer.normalize_weights``; an injected ``optimize_fn`` keeps the
stage deterministic in tests (no SQX HTTP dependency on the stage path).
"""

from __future__ import annotations

import inspect
from typing import Any, Callable

from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.agent_stages import PortfolioStage as _PortfolioStage

#: Normalize a raw weight mapping into a portfolio allocation.
OptimizeFn = Callable[[dict[str, float]], dict[str, float]]


def _default_normalize(weights: dict[str, float]) -> dict[str, float]:
    from quantlab.phase4.portfolio_composer import PortfolioComposer

    return PortfolioComposer.normalize_weights(weights)


class PortfolioStage(_PortfolioStage):
    """Compose the campaign portfolio from selected strategies (REQ-43 chain).

    **Requires**: selected_strategies
    **Provides**: portfolio_result
    """

    name: str = "portfolio"
    requires: list[str] = ["selected_strategies", "review_decision"]
    provides: list[str] = [
        "portfolio_result",
        "portfolio_cfx",
        "correlation_matrix",
        "risk_allocation",
        "wf_aggregate_stats",
    ]

    def __init__(self, optimize_fn: OptimizeFn | None = None) -> None:
        # Injectable for tests; the default is the pure PortfolioComposer
        # normalizer (no SQX HTTP client needed for the weight computation).
        self._optimize_fn = optimize_fn

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Publish ``portfolio_result`` with the normalized weights.

        Args:
            ctx: Pipeline context carrying ``selected_strategies`` and, in
                ``config.portfolio_weights``, the raw per-strategy weights.

        Returns:
            Dict with ``portfolio_result`` (normalized weights) and
            ``portfolio_cfx`` (``None`` — compiled in the compile phase).
        """
        raw_weights: dict[str, float] = {}
        if ctx.config:
            raw_weights = dict(ctx.config.get("portfolio_weights") or {})
        if not raw_weights:
            selected = ctx.artifacts.get("selected_strategies") or []
            raw_weights = {name: 1.0 / len(selected) for name in selected} if selected else {}

        normalize = self._optimize_fn or _default_normalize
        result = normalize(raw_weights)
        # The injected fn may be async (deterministic test fakes); await it.
        if inspect.isawaitable(result):  # pragma: no cover - async test fakes
            result = await result

        ctx.artifacts["portfolio_result"] = result
        # portfolio_cfx is part of the stage's contract output but NOT part of
        # the orchestration chain artifacts — compilation publishes .jfx later.
        return {"portfolio_result": result, "portfolio_cfx": None}
