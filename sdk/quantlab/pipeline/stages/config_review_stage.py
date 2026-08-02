"""ConfigReviewStage — reviews the in-flight BuildConfig before dispatch (REQ-05).

Runs after the builder and before dispatch. Emits a ``config_review_verdict``
artifact (APPROVE / MODIFY / BLOCK) with the CostConfigReview note. The stage
NEVER applies MODIFY changes itself — a MODIFY verdict must always wait for
human confirmation via the HUMAN_APPROVE_CONFIG gate (D3, REQ-06).
"""

from __future__ import annotations

from typing import Any

from quantlab.agents.config_reviewer import ConfigReviewer
from quantlab.pipeline.base import PipelineContext, Stage

try:  # CostsConfig is optional — the reviewer degrades to a preset note
    from quantlab.costs.models import CostsConfig
except ImportError:  # pragma: no cover - costs package is part of the SDK
    CostsConfig = None  # type: ignore[assignment,misc]


class ConfigReviewStage(Stage):
    """Review the in-flight BuildConfig and emit the review verdict.

    **Requires**: build_config
    **Provides**: config_review_verdict
    """

    name: str = "config_review"
    requires: list[str] = ["build_config"]
    provides: list[str] = ["config_review_verdict"]

    def __init__(
        self,
        reviewer: ConfigReviewer | None = None,
        costs: "CostsConfig | None" = None,
    ) -> None:
        self._reviewer = reviewer or ConfigReviewer()
        self._costs = costs

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Review the in-flight build_config and expose the verdict.

        Args:
            ctx: Pipeline context with ``build_config`` artifact.

        Returns:
            Dict with the verdict action, reason, proposed changes, and cost note.
        """
        build_config = ctx.artifacts["build_config"]
        verdict = self._reviewer.review(build_config, self._costs)
        verdict_dict = verdict.model_dump()

        # Expose the verdict for the HUMAN_APPROVE_CONFIG gate and dispatch stage.
        ctx.artifacts["config_review_verdict"] = verdict_dict
        return {
            "verdict": verdict_dict["action"],
            "reason": verdict_dict["reason"],
            "proposed_changes": verdict_dict["proposed_changes"],
            "cost_note": verdict_dict["cost_note"],
        }
