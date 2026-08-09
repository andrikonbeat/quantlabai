"""ConfigReviewer — reviews the in-flight BuildConfig before dispatch (REQ-05).

Emits a ``ConfigReviewVerdict``:
- ``BLOCK``: contradictory risk settings (e.g. SL required but PT stricter
  than SL, inverted SL/PT/RRR ranges). Dispatch must NOT be attempted.
- ``MODIFY``: the config needs adjustment; ``proposed_changes`` carries
  concrete, diff-able BuildConfig field changes for human review.
- ``APPROVE``: the config is safe to dispatch.

The verdict always includes a ``cost_note`` (CostConfigReview) surfacing
preset-vs-live cost profiles.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from quantlab.sqx.project_builder import BuildConfig

try:  # CostsConfig is optional at review time — a missing config yields a preset note
    from quantlab.costs.models import CostsConfig
except ImportError:  # pragma: no cover - costs package is part of the SDK
    CostsConfig = None  # type: ignore[assignment,misc]


class ConfigReviewVerdict(BaseModel):
    """Outcome of reviewing an in-flight BuildConfig.

    Attributes:
        action: ``APPROVE`` | ``MODIFY`` | ``BLOCK``.
        reason: Concrete reason for the verdict.
        proposed_changes: BuildConfig field diffs — populated only for MODIFY.
        cost_note: CostConfigReview note surfacing preset-vs-live cost profiles.
    """

    action: Literal["APPROVE", "MODIFY", "BLOCK"]
    reason: str
    proposed_changes: dict[str, Any] = Field(default_factory=dict)
    cost_note: str = Field(default="")

    @property
    def is_block(self) -> bool:
        """True when dispatch must not be attempted."""
        return self.action == "BLOCK"


_SL_PT_VALUE_TYPES = ("pips", "atr", "percent", "indicator")


def build_cost_note(costs: "CostsConfig | None") -> str:
    """Surface preset-vs-live cost profiles for the CostConfigReview note."""
    if costs is None:
        return (
            "CostConfigReview: no cost config supplied — review assumes "
            "broker preset costs (live profile unknown)."
        )

    deviations: list[str] = []
    if costs.commission_override is not None:
        deviations.append(
            f"live commission override (type={costs.commission_override.type.value})"
        )
    if costs.spread_config is not None:
        deviations.append("live spread overrides")
    if costs.slippage_mode and costs.slippage_mode != "static":
        deviations.append(f"slippage mode '{costs.slippage_mode}' (preset static)")

    if deviations:
        return (
            f"CostConfigReview: live profile deviates from {costs.broker} preset "
            f"— {', '.join(deviations)}."
        )
    return (
        f"CostConfigReview: live cost profile matches {costs.broker} preset "
        "(no overrides)."
    )


class ConfigReviewer:
    """Pure reviewer over an in-flight ``BuildConfig`` (REQ-05)."""

    def review(
        self,
        build_config: BuildConfig | None,
        costs: "CostsConfig | None" = None,
    ) -> ConfigReviewVerdict:
        """Review ``build_config`` and emit APPROVE / MODIFY / BLOCK.

        Args:
            build_config: In-flight BuildConfig produced by the builder stage.
                ``None`` is vacuously safe — nothing to review.
            costs: Optional cost config; drives the preset-vs-live cost note.

        Returns:
            ConfigReviewVerdict — BLOCK stops dispatch, MODIFY waits for
            human confirmation (D3), APPROVE proceeds.
        """
        if build_config is None:
            return ConfigReviewVerdict(
                action="APPROVE",
                reason="No build config provided — nothing to review.",
                proposed_changes={},
                cost_note=build_cost_note(costs),
            )

        contradiction = self._find_contradiction(build_config)
        if contradiction is not None:
            return ConfigReviewVerdict(
                action="BLOCK",
                reason=contradiction,
                proposed_changes={},
                cost_note=build_cost_note(costs),
            )

        adjustments = self._find_adjustments(build_config)
        if adjustments:
            detail = "; ".join(f"{key}={value}" for key, value in adjustments.items())
            return ConfigReviewVerdict(
                action="MODIFY",
                reason=f"Config needs adjustment: {detail}",
                proposed_changes=adjustments,
                cost_note=build_cost_note(costs),
            )

        return ConfigReviewVerdict(
            action="APPROVE",
            reason="Config review passed — risk settings consistent.",
            proposed_changes={},
            cost_note=build_cost_note(costs),
        )

    # ── Review rules ──────────────────────────────────────────────────────────

    def _find_contradiction(self, bc: BuildConfig) -> str | None:
        """Return a concrete reason when risk settings are contradictory, else None."""
        # SL required but PT stricter than SL — take profit tighter than stop loss.
        if (
            bc.sl_required
            and bc.pt_required
            and bc.min_sl_pips is not None
            and bc.max_pt_pips is not None
            and bc.max_pt_pips < bc.min_sl_pips
        ):
            return (
                f"Contradictory risk settings: SL required (min {bc.min_sl_pips} pips) "
                f"but PT stricter than SL (max {bc.max_pt_pips} pips) — take profit "
                "is tighter than the stop loss."
            )

        # Inverted RRR limiting range.
        if (
            bc.limit_slpt_rrr
            and bc.limit_slpt_rrr_from is not None
            and bc.limit_slpt_rrr_to is not None
            and bc.limit_slpt_rrr_from > bc.limit_slpt_rrr_to
        ):
            return (
                f"Contradictory risk settings: inverted RRR range "
                f"(limit_slpt_rrr_from {bc.limit_slpt_rrr_from} > "
                f"limit_slpt_rrr_to {bc.limit_slpt_rrr_to})."
            )

        # Inverted SL pips range.
        if (
            bc.min_sl_pips is not None
            and bc.max_sl_pips is not None
            and bc.min_sl_pips > bc.max_sl_pips
        ):
            return (
                f"Contradictory risk settings: inverted SL pips range "
                f"(min_sl_pips {bc.min_sl_pips} > max_sl_pips {bc.max_sl_pips})."
            )

        # Inverted PT pips range.
        if (
            bc.min_pt_pips is not None
            and bc.max_pt_pips is not None
            and bc.min_pt_pips > bc.max_pt_pips
        ):
            return (
                f"Contradictory risk settings: inverted PT pips range "
                f"(min_pt_pips {bc.min_pt_pips} > max_pt_pips {bc.max_pt_pips})."
            )

        return None

    def _find_adjustments(self, bc: BuildConfig) -> dict[str, Any]:
        """Return concrete BuildConfig field diffs for adjustments, else empty."""
        changes: dict[str, Any] = {}
        if bc.sl_required and bc.sl_value_type is None:
            changes["sl_value_type"] = self._suggest_value_type(
                atr=bool(bc.sl_atr),
                percent=bool(bc.sl_percent),
                indicator=bool(bc.sl_indicator_based),
            )
        if bc.pt_required and bc.pt_value_type is None:
            changes["pt_value_type"] = self._suggest_value_type(
                atr=bool(bc.pt_atr),
                percent=bool(bc.pt_percent),
                indicator=bool(bc.pt_indicator_based),
            )
        return changes

    @staticmethod
    def _suggest_value_type(
        *,
        atr: bool = False,
        percent: bool = False,
        indicator: bool = False,
    ) -> str:
        """Derive the SQX value type from the explicit flags, defaulting to pips."""
        if atr:
            return "atr"
        if percent:
            return "percent"
        if indicator:
            return "indicator"
        return "pips"
