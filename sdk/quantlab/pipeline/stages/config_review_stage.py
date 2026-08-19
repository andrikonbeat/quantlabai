"""ConfigReviewStage — reviews the in-flight BuildConfig before dispatch (REQ-05).

Runs after the builder and before dispatch. Emits a ``config_review_verdict``
artifact (APPROVE / MODIFY / BLOCK) with the CostConfigReview note. The stage
NEVER applies MODIFY changes itself — a MODIFY verdict must always wait for
human confirmation via the HUMAN_APPROVE_CONFIG gate (D3, REQ-06).

G7 (parameter-educational-table): the reviewer owns a persisted teaching table.
After the verdict, the stage builds the REQ-205 table via ``build_teaching_table``
from ``KbStore.consult`` hits for the configured ``BuildConfig`` review fields,
persists it to ``structured/{campaign_id}/review/teaching-table.md`` and exposes
the relative lake path under ``teaching_table`` in BOTH the verdict and the
outcome (the delegation layer lists it in ``PhaseResult.artifacts`` when the
file exists — REQ-819 only claims real artifacts). Missing ``campaign_id`` /
``knowledge_root`` degrade to ``teaching_table=""`` (nothing persisted, nothing
claimed), mirroring the delegation gap contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Sequence

from quantlab.agents.config_reviewer import ConfigReviewer
from quantlab.knowledge.kb.models import KbParameter
from quantlab.knowledge.kb.store import KbStore
from quantlab.knowledge.kb.teaching import (
    EMPTY_TABLE_NOTE,
    TABLE_HEADERS,
    build_teaching_table,
)
from quantlab.pipeline.base import PipelineContext, Stage

try:  # CostsConfig is optional — the reviewer degrades to a preset note
    from quantlab.costs.models import CostsConfig
except ImportError:  # pragma: no cover - costs package is part of the SDK
    CostsConfig = None  # type: ignore[assignment,misc]

#: BuildConfig fields the reviewer evaluates — the "configured fields" the
#: teaching table teaches (parameter-educational-table, G7).
REVIEW_FIELDS: tuple[str, ...] = (
    "sl_required",
    "sl_fixed_pips",
    "sl_atr",
    "sl_percent",
    "sl_indicator_based",
    "sl_value_type",
    "min_sl_pips",
    "max_sl_pips",
    "min_sl_atr_multiple",
    "max_sl_atr_multiple",
    "min_sl_percent",
    "max_sl_percent",
    "pt_required",
    "pt_fixed_pips",
    "pt_atr",
    "pt_percent",
    "pt_indicator_based",
    "pt_value_type",
    "min_pt_pips",
    "max_pt_pips",
    "min_pt_atr_multiple",
    "max_pt_atr_multiple",
    "min_pt_percent",
    "max_pt_percent",
    "limit_slpt_rrr",
    "limit_slpt_rrr_from",
    "limit_slpt_rrr_to",
)

#: BuildConfig field -> human-readable KB consult term.  SL/PT fields consult
#: the seeded "Stop Loss"/"Profit Target" parameters; fields without a KB
#: entry (e.g. the RRR limiters) consult their own name and render the stable
#: fallback row (parameter-educational-table s2).
KB_TERM_FOR_FIELD: dict[str, str] = {
    "sl_required": "Stop Loss",
    "sl_fixed_pips": "Stop Loss",
    "sl_atr": "Stop Loss",
    "sl_percent": "Stop Loss",
    "sl_indicator_based": "Stop Loss",
    "sl_value_type": "Stop Loss",
    "min_sl_pips": "Stop Loss",
    "max_sl_pips": "Stop Loss",
    "min_sl_atr_multiple": "Stop Loss",
    "max_sl_atr_multiple": "Stop Loss",
    "min_sl_percent": "Stop Loss",
    "max_sl_percent": "Stop Loss",
    "pt_required": "Profit Target",
    "pt_fixed_pips": "Profit Target",
    "pt_atr": "Profit Target",
    "pt_percent": "Profit Target",
    "pt_indicator_based": "Profit Target",
    "pt_value_type": "Profit Target",
    "min_pt_pips": "Profit Target",
    "max_pt_pips": "Profit Target",
    "min_pt_atr_multiple": "Profit Target",
    "max_pt_atr_multiple": "Profit Target",
    "min_pt_percent": "Profit Target",
    "max_pt_percent": "Profit Target",
}

#: Stable "no KB entry" cell for a configured field without KB guidance (s2).
NO_KB_ENTRY_NOTE = "No KB entry"

#: Relative Knowledge Lake path for the reviewer deliverable (G7).
_TEACHING_REL = "structured/{campaign_id}/review/teaching-table.md"


def _fallback_row(field: str) -> str:
    """Stable REQ-205-shape row for a configured field with no KB entry."""
    return f"| Review | {field} | {NO_KB_ENTRY_NOTE} | — | — | — | — | — |"


def build_review_teaching_table(
    build_config: "BuildConfig | None",
    consult: Callable[[str], list[dict[str, object]]],
) -> str:
    """Render the reviewer-owned REQ-205 teaching table (G7).

    Consults the KB once per *configured* review field, renders KB hits
    through :func:`build_teaching_table`, and appends a stable fallback row
    for every configured field with no KB entry. Returns the stable
    placeholder line when there is nothing to review.

    Args:
        build_config: The in-flight BuildConfig (``None`` is vacuously safe).
        consult: KB lookup — the real ``KbStore.consult`` (exact-or-fuzzy
            name match returning guidance metadata dicts).

    Returns:
        Markdown teaching table (header + KB rows + fallback rows), or
        ``EMPTY_TABLE_NOTE`` when there are no configured fields.
    """
    if build_config is None:
        return EMPTY_TABLE_NOTE

    fields = [
        name
        for name in REVIEW_FIELDS
        if getattr(build_config, name, None) is not None
    ]
    if not fields:
        return EMPTY_TABLE_NOTE

    params: list[KbParameter] = []
    seen: set[str] = set()
    fallback: list[str] = []
    for name in fields:
        term = KB_TERM_FOR_FIELD.get(name, name)
        hits = consult(term)
        if not hits:
            fallback.append(name)
            continue
        for hit in hits:
            param = KbParameter.model_validate(hit)
            if param.name in seen:
                continue
            seen.add(param.name)
            params.append(param)

    if params:
        lines = [build_teaching_table(params)]
        if fallback:
            lines.extend(_fallback_row(name) for name in fallback)
        return "\n".join(lines)

    if not fallback:
        return EMPTY_TABLE_NOTE
    header = "| " + " | ".join(TABLE_HEADERS) + " |"
    separator = "|" + "---|" * len(TABLE_HEADERS)
    return "\n".join([header, separator, *(_fallback_row(name) for name in fallback)])


class ConfigReviewStage(Stage):
    """Review the in-flight BuildConfig and emit the review verdict.

    **Requires**: build_config
    **Provides**: config_review_verdict

    G7: also persists the reviewer-owned teaching table under
    ``structured/{campaign_id}/review/teaching-table.md`` and exposes its
    relative lake path as ``teaching_table`` in the verdict + outcome.
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
            ctx: Pipeline context with ``build_config`` artifact and optional
                ``config.campaign_id`` / ``config.knowledge_root`` (D3) driving
                teaching-table persistence.

        Returns:
            Dict with the verdict action, reason, proposed changes, cost note,
            and the persisted ``teaching_table`` relative path (``""`` when the
            campaign context is missing — nothing persisted, nothing claimed).
        """
        build_config = ctx.artifacts["build_config"]
        verdict = self._reviewer.review(build_config, self._costs)
        verdict_dict = verdict.model_dump()

        # G7: the reviewer owns the persisted teaching table deliverable.
        verdict_dict["teaching_table"] = self._persist_teaching_table(ctx, build_config)

        # Expose the verdict for the HUMAN_APPROVE_CONFIG gate and dispatch stage.
        ctx.artifacts["config_review_verdict"] = verdict_dict
        return {
            "verdict": verdict_dict["action"],
            "reason": verdict_dict["reason"],
            "proposed_changes": verdict_dict["proposed_changes"],
            "cost_note": verdict_dict["cost_note"],
            "teaching_table": verdict_dict["teaching_table"],
        }

    def _persist_teaching_table(
        self, ctx: PipelineContext, build_config: "BuildConfig | None"
    ) -> str:
        """Persist the teaching table and return its relative lake path.

        Returns ``""`` when ``campaign_id``/``knowledge_root`` are missing —
        the delegation layer then claims nothing (REQ-819).
        """
        config = ctx.config or {}
        campaign_id = config.get("campaign_id")
        knowledge_root = config.get("knowledge_root")
        if not campaign_id or not knowledge_root:
            return ""

        kb = KbStore(root=str(knowledge_root))
        table = build_review_teaching_table(build_config, kb.consult)
        rel = _TEACHING_REL.format(campaign_id=campaign_id)
        target = Path(str(knowledge_root)) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(table + "\n", encoding="utf-8")
        return rel