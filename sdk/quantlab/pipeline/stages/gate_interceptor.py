"""GateInterceptorStage — async human gate interceptor with timeout, fallback, and Engram recording.

A GateInterceptorStage is inserted after a configurable pipeline stage position.
It pauses pipeline execution, invokes an async callback for human approval,
handles timeout with configurable fallback (ABORT / CONTINUE / ESCALATE),
and records the gate decision to Engram for audit.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Protocol

from quantlab.pipeline.base import PipelineContext, Stage

logger = logging.getLogger(__name__)


class GateAction(str, Enum):
    """Possible outcomes of a gate decision."""
    APPROVED = "approved"
    REJECTED = "rejected"
    ABORT = "abort"
    TIMEOUT = "timeout"
    FALLBACK = "fallback"


class FallbackPolicy(str, Enum):
    """Fallback behaviour when a gate times out without a response."""
    ABORT = "ABORT"          # Stop the pipeline
    CONTINUE = "CONTINUE"    # Proceed as if approved
    ESCALATE = "ESCALATE"    # Escalate to a human lead (external)


@dataclass
class GateDecision:
    """Decision produced by a gate interceptor after callback resolution."""
    gate_id: str
    action: GateAction = GateAction.APPROVED
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""
    decided_by: str = "system"  # "human", "system" (timeout/fallback), "escalation"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GateContext:
    """Context provided to the gate callback."""
    gate_id: str
    pipeline_name: str
    stage_name: str
    context_artifacts: dict[str, Any]
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    timeout_hours: float = 24.0
    fallback: FallbackPolicy = FallbackPolicy.ESCALATE


# Async callback protocol
GateCallback = Callable[[GateContext], Awaitable[GateDecision]]


class GateInterceptorStage(Stage, ABC):
    """Abstract stage that pauses pipeline execution for human gate approval.

    Attributes:
        name: Stage name (default "gate").
        gate_id: Unique gate identifier (e.g. "HUMAN_REVIEW_OBJECTIVES").
        requires: Artifact keys this gate reads. Typically gate-specific artifacts.
        provides: Artifact keys this gate writes. Includes "gate_decision_{gate_id}".
        timeout_hours: Maximum wait time for human response.
        fallback: Fallback policy on timeout (ABORT / CONTINUE / ESCALATE).
        callback: Async callable invoked with GateContext, returns GateDecision.
            Set via ``set_callback()``.
    """
    name: str = "gate"
    gate_id: str = ""
    requires: list[str] = []
    provides: list[str] = []
    timeout_hours: float = 24.0
    fallback: FallbackPolicy = FallbackPolicy.ESCALATE

    _callback: GateCallback | None = None
    _engaged: bool = False

    def set_callback(self, callback: GateCallback) -> None:
        """Set the async callback that resolves the gate decision.

        Args:
            callback: An async function that takes a GateContext and returns
                      a GateDecision.
        """
        self._callback = callback

    def build_gate_context(self, ctx: PipelineContext) -> GateContext:
        """Build the GateContext from the current pipeline context.

        Override in subclasses to customise which artifacts are exposed.
        """
        return GateContext(
            gate_id=self.gate_id,
            pipeline_name=ctx.metadata.get("pipeline_name", "unknown"),
            stage_name=self.name,
            context_artifacts=dict(ctx.artifacts),
            timeout_hours=self.timeout_hours,
            fallback=self.fallback,
        )

    async def _resolve_decision(self, gate_ctx: GateContext) -> GateDecision:
        """Resolve the gate decision via callback or fallback.

        Returns:
            The resolved GateDecision.
        """
        if self._callback is not None:
            try:
                decision = await asyncio.wait_for(
                    self._callback(gate_ctx),
                    timeout=self.timeout_hours * 3600,
                )
                return decision
            except asyncio.TimeoutError:
                logger.warning(
                    "Gate '%s' timed out after %.1f h — applying fallback '%s'",
                    self.gate_id, self.timeout_hours, self.fallback.value,
                )
        else:
            logger.info(
                "Gate '%s' has no callback — applying fallback '%s'",
                self.gate_id, self.fallback.value,
            )

        # Apply fallback on timeout or missing callback
        action: GateAction
        if self.fallback == FallbackPolicy.ABORT:
            action = GateAction.ABORT
            reason = "ABORT fallback — pipeline stopped"
        elif self.fallback == FallbackPolicy.ESCALATE:
            action = GateAction.FALLBACK
            reason = "ESCALATE fallback — external escalation required"
        else:  # CONTINUE
            action = GateAction.FALLBACK
            reason = "CONTINUE fallback — proceeding as approved"

        return GateDecision(
            gate_id=self.gate_id,
            action=action,
            reason=reason,
            decided_by="system",
        )

    async def _record_to_engram(self, ctx: PipelineContext, decision: GateDecision) -> None:
        """Record the gate decision to Engram.

        Uses the Engram protocol from the pipeline context if available.
        This is a best-effort operation — failures are logged but not raised.
        """
        try:
            engram_save = ctx.metadata.get("engram_save")
            if engram_save is not None:
                await engram_save(
                    title=f"gate-decision/{self.gate_id}",
                    type="decision",
                    scope="project",
                    topic_key=f"agent/research-director/gate/{self.gate_id}",
                    content=(
                        f"**What**: Gate '{self.gate_id}' decided {decision.action.value}\n"
                        f"**Why**: {decision.reason}\n"
                        f"**When**: {decision.timestamp.isoformat()}\n"
                        f"**Decided by**: {decision.decided_by}\n"
                        f"**Metadata**: {decision.metadata}"
                    ),
                )
                logger.info("Gate decision recorded to Engram for '%s'", self.gate_id)
        except Exception as exc:
            logger.warning("Failed to record gate decision to Engram: %s", exc)

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Execute the gate interceptor stage.

        Builds a GateContext from the pipeline context, invokes the async
        callback, handles timeout/fallback, records the decision, and
        returns the result.
        """
        gate_ctx = self.build_gate_context(ctx)
        decision = await self._resolve_decision(gate_ctx)

        if decision.action in (GateAction.ABORT, GateAction.TIMEOUT):
            # Record to Engram before raising
            await self._record_to_engram(ctx, decision)
            from quantlab.pipeline.errors import GateTimeoutError
            raise GateTimeoutError(
                message=f"Gate '{self.gate_id}' aborted pipeline: {decision.reason}",
                gate_id=self.gate_id,
                fallback_action=self.fallback.value,
            )

        # Record the decision to Engram
        await self._record_to_engram(ctx, decision)

        # Write the gate decision to context artifacts
        artifact_key = f"gate_decision_{self.gate_id}"
        ctx.artifacts[artifact_key] = {
            "action": decision.action.value,
            "timestamp": decision.timestamp.isoformat(),
            "reason": decision.reason,
            "decided_by": decision.decided_by,
        }

        self._engaged = True
        return {
            "gate_id": self.gate_id,
            "decision": decision.action.value,
            "timestamp": decision.timestamp.isoformat(),
            "reason": decision.reason,
            "decided_by": decision.decided_by,
        }

    @property
    def is_engaged(self) -> bool:
        """Whether this gate has been triggered in the current pipeline run."""
        return self._engaged


# ─── Predefined Gate IDs ──────────────────────────────────────────────────────

HUMAN_GATE_IDS: list[str] = [
    "HUMAN_REVIEW_OBJECTIVES",
    "HUMAN_APPROVE_ITERATION",
    "HUMAN_APPROVE_PORTFOLIO",
    "HUMAN_APPROVE_DEPLOY",
    "HUMAN_REVIEW_PERFORMANCE",
]
