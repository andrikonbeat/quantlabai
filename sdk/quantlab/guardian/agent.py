"""Guardian orchestration agent glue — REQ-641/REQ-643/REQ-644.

``execute_guardian_directive`` is the SDK entry the ``quantlab-guardian``
subagent (PR 2) dispatches to. It wraps the EXISTING guardian stages
(``GuardianEvaluationAgentStage``, ``LiveOpsStage``) unmodified — the agent
NEVER introduces a pipeline phase (REQ-37) and never touches human gates
(REQ-643) — reuses the ops surface for escalation acks (REQ-36), and returns
the bidirectional ``GuardianReport`` envelope carrying ``guardian_state`` and
the ``FeedbackRecord`` payload exposed by ``next_cycle_inputs()`` (REQ-34).

This module is impure glue: it builds pipeline contexts and calls stage
``execute()``. All envelope construction stays pure in ``feedback.py``.
"""

from __future__ import annotations

from typing import Any

from quantlab.guardian.feedback import (
    DIRECTIVE_KINDS,
    GuardianDirective,
    GuardianReport,
    build_report,
)
from quantlab.guardian.live import evaluate_live
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.agent_stages import GuardianEvaluationAgentStage
from quantlab.pipeline.stages.live_ops_stage import LiveOpsStage


async def execute_guardian_directive(
    directive: GuardianDirective,
    *,
    ops_surface: Any | None = None,
) -> GuardianReport:
    """Execute a bounded orchestrator directive via the guardian agent (REQ-641).

    Dispatches on :attr:`GuardianDirective.kind`:

    - ``evaluate`` — runs ``GuardianEvaluationAgentStage.execute`` to produce
      ``guardian_state``, then ``evaluate_live`` over the directive's points;
      the resulting ``FeedbackRecord`` (only on a live transition, REQ-34) is
      carried in the report envelope (REQ-644).
    - ``live_ops_status`` — runs ``LiveOpsStage.execute``; without an archive
      bundle the stage fails closed with status ``hold`` (never claims a live
      account).
    - ``escalation_ack`` — acknowledges the escalation through the ops
      surface (REQ-36); an unknown id surfaces as ``None`` and is never
      fabricated into the report.

    Args:
        directive: The bounded directive to execute. An unknown ``kind``
            raises :class:`ValueError` pre-execution (REQ-643).
        ops_surface: Optional 24-7 ops surface (REQ-36) for escalation acks.
            When ``None`` an ``escalation_ack`` directive is a graceful
            no-op — the report claims no acked ids.

    Returns:
        A :class:`GuardianReport` with ``guardian_state`` (evaluate only),
        ``feedback`` (evaluate with a live transition), ``live_ops_status``
        (live-ops status directive), and ``escalations_acked`` (real acked
        ids only). No gate or flow fields.
    """
    if directive.kind not in DIRECTIVE_KINDS:
        raise ValueError(
            f"unknown GuardianDirective kind {directive.kind!r} — bounded to "
            f"{', '.join(DIRECTIVE_KINDS)} (REQ-643)"
        )

    if directive.kind == "escalation_ack":
        return _ack_escalation(directive, ops_surface)

    if directive.kind == "live_ops_status":
        return await _live_ops_status()

    return await _evaluate(directive)


async def _evaluate(directive: GuardianDirective) -> GuardianReport:
    """Run the existing Guardian evaluation stage plus a live evaluation."""
    ctx = PipelineContext(
        config={},
        artifacts={"research_config": directive.research_config or {}},
    )
    stage = GuardianEvaluationAgentStage()
    outcome = await stage.execute(ctx)
    guardian_state = outcome["guardian_state"]

    feedback = None
    if directive.points is not None:
        evaluation = evaluate_live(
            directive.points,
            campaign_id=directive.campaign_id,
        )
        feedback = evaluation.feedback  # None without a live transition (REQ-644 s2)

    return build_report(
        guardian_state=guardian_state,
        feedback=feedback,
    )


async def _live_ops_status() -> GuardianReport:
    """Publish live-ops status via the existing LiveOpsStage (fail-closed)."""
    ctx = PipelineContext(config={}, artifacts={})
    stage = LiveOpsStage()
    outcome = await stage.execute(ctx)
    live_ops_status = outcome.get("live_ops_status") or ctx.artifacts.get(
        "live_ops_status"
    )
    return build_report(
        guardian_state=None,
        live_ops_status=live_ops_status,
    )


def _ack_escalation(
    directive: GuardianDirective,
    ops_surface: Any | None,
) -> GuardianReport:
    """Acknowledge an escalation via the ops surface; never fabricate (REQ-36)."""
    acked: tuple[str, ...] = ()
    if ops_surface is not None and directive.alert_id is not None:
        alert = ops_surface.ack(directive.alert_id)
        if alert is not None:  # unknown id → None surfaced as no claim
            acked = (alert.alert_id,)
    return build_report(
        guardian_state=None,
        escalations_acked=acked,
    )