"""Delegation glue for per-phase sub-agent dispatch (REQ-801..REQ-804, REQ-809).

This module wraps the immutable ``PHASES`` tuple with a delegation layer:
``PhaseDirective`` handoffs, ``PhaseResult`` envelopes, ``PHASE_AGENTS``
registry, and ``execute_phase()`` glue that enforces bounded authority
without mutating ``sdk/quantlab/campaign/flow.py`` (REQ-37/REQ-804).

Name-collision guard (design AD-6): ``PhaseResult`` is also declared in
``quantlab.substrate.executor`` and ``quantlab.phase4.models`` with different
semantics.  Consumers MUST alias-on-import to disambiguate:

    from quantlab.campaign.delegation import PhaseResult as CampaignPhaseResult
    from quantlab.substrate.executor import PhaseResult as SubstratePhaseResult
    from quantlab.phase4.models import PhaseResult as Phase4PhaseResult

Do NOT rename the existing types.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from quantlab.campaign.flow import PHASES

# Name-collision guard (AD-6): import the other PhaseResult definitions under
# explicit aliases so the three distinct envelope types are visible in this
# module's namespace without renaming the existing types.
from quantlab.substrate.executor import PhaseResult as SubstratePhaseResult  # noqa: F401
from quantlab.phase4.models import PhaseResult as Phase4PhaseResult  # noqa: F401

logger = logging.getLogger(__name__)

__all__ = [
    "PhaseDirective",
    "PhaseResult",
    "PHASE_AGENTS",
    "execute_phase",
    "validate_phase_result",
    "PhaseNotFoundError",
    "AuthorityViolationError",
    "LongOpSpec",
]


# ---------------------------------------------------------------------------
# Envelope types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PhaseDirective:
    """Directive for a single phase dispatch (REQ-801).

    Attributes:
        phase_id: Canonical phase id — MUST be in ``PHASES``.
        scope: Bounded authority label for the phase agent.
        payload: Campaign context refs (campaign_id, artifacts, prior_context).
        previous_result: Optional preceding ``PhaseResult`` for context handoff.
    """

    phase_id: str
    scope: str
    payload: dict[str, Any]
    previous_result: PhaseResult | None = None


@dataclass(frozen=True)
class PhaseResult:
    """Result envelope returned by a phase agent (REQ-802).

    Attributes:
        status: ``"success"`` | ``"failed"`` | ``"partial"``.
            Anything other than ``"success"`` halts folding (REQ-802).
        executive_summary: One-paragraph human-readable outcome.
        artifacts: Artifact keys produced by the phase.
        next_recommended: Suggested next phase or action.
        risks: List of risk strings identified during the phase.
        phase_id: Canonical phase id that produced this result.
        evidence: Per-phase evidence dict for audit.
        handoff_payload: Optional runnable script spec for orchestrator-shell
            execution (REQ-809).  Shape: ``{"command", "log_path",
            "expected", "timeout": int >= 240, "cleanup"}``.
    """

    status: str
    executive_summary: str
    artifacts: list[str]
    next_recommended: str
    risks: list[str]
    phase_id: str
    evidence: dict[str, Any] = field(default_factory=dict)
    handoff_payload: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Agent names derived from ``PHASES`` (REQ-805/REQ-804).  Wrap-only: never
#: mutate, reorder, rename, or remove entries from ``PHASES``.
PHASE_AGENTS: dict[str, str] = {phase: f"quantlab-phase-{phase}" for phase in PHASES}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


class PhaseNotFoundError(ValueError):
    """Raised when a directive references an unknown phase id."""


class AuthorityViolationError(RuntimeError):
    """Raised when an executor attempts an out-of-scope action."""


def validate_phase_result(result: PhaseResult) -> None:
    """Validate a ``PhaseResult`` envelope against the Result Contract (REQ-802).

    Args:
        result: The envelope to validate.

    Raises:
        ValueError: If required fields are missing or empty.
        PhaseNotFoundError: If ``phase_id`` is not in ``PHASES``.
    """
    if not result.status:
        raise ValueError("PhaseResult.status must be non-empty")
    if not result.executive_summary:
        raise ValueError("PhaseResult.executive_summary must be non-empty")
    if not isinstance(result.artifacts, list):
        raise ValueError("PhaseResult.artifacts must be a list")
    if not isinstance(result.risks, list):
        raise ValueError("PhaseResult.risks must be a list")
    if not result.phase_id:
        raise ValueError("PhaseResult.phase_id must be non-empty")
    if result.phase_id not in PHASES:
        raise PhaseNotFoundError(
            f"PhaseResult.phase_id '{result.phase_id}' is not in PHASES"
        )


# ---------------------------------------------------------------------------
# Long-running op spec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LongOpSpec:
    """Runnable script spec for orchestrator-shell execution (REQ-809).

    Attributes:
        command: Shell command to execute.
        log_path: Path to the log file to poll.
        expected: Expected success marker in the log.
        timeout: Seconds to wait before cancelling (>= 240).
        cleanup: Cleanup command to run after completion/cancel.
    """

    command: str
    log_path: str
    expected: str
    timeout: int = 300
    cleanup: str = ""

    def __post_init__(self) -> None:
        if self.timeout < 240:
            raise ValueError(
                f"LongOpSpec.timeout must be >= 240 seconds, got {self.timeout}"
            )


# ---------------------------------------------------------------------------
# Glue
# ---------------------------------------------------------------------------


async def execute_phase(
    directive: PhaseDirective,
    *,
    executor: Callable[[PhaseDirective], Awaitable[PhaseResult]] | None = None,
) -> PhaseResult:
    """Dispatch a phase and return its ``PhaseResult`` (REQ-803).

    Steps:
    1. Validate ``directive.phase_id`` is in ``PHASES``.
    2. Scope-check the executor (reject out-of-scope actions).
    3. Run the executor (or a default mock when ``SQX_FORCE_MOCK`` is set).
    4. Validate the returned envelope via :func:`validate_phase_result`.
    5. Return the envelope.

    Long-running operations are NEVER waited on inline.  When the executor
    returns a ``handoff_payload`` with a script spec, the glue hands it back
    to the orchestrator shell for ``nohup``/poll/cancel execution (REQ-809).

    Args:
        directive: The phase directive to execute.
        executor: Optional async callable that consumes the directive and
            returns a ``PhaseResult``.  When ``None``, a mock executor is
            used if ``SQX_FORCE_MOCK=1`` is set; otherwise
            ``AuthorityViolationError`` is raised (no production executor
            registered here — phase agents own real execution).

    Returns:
        ``PhaseResult`` envelope from the phase agent.

    Raises:
        PhaseNotFoundError: If ``directive.phase_id`` is not in ``PHASES``.
        AuthorityViolationError: If the executor attempts an out-of-scope action.
    """
    import os

    # Step 1: validate phase id.
    if directive.phase_id not in PHASES:
        raise PhaseNotFoundError(
            f"phase_id '{directive.phase_id}' is not in PHASES — "
            "dispatch rejected (REQ-801)"
        )

    # Step 2: scope-check — reject known out-of-scope actions.
    scope = directive.scope.lower()
    forbidden = ("mutate flow.py", "skip gate", "wait long", "touch live trading")
    if any(term in scope for term in forbidden):
        raise AuthorityViolationError(
            f"Scope '{directive.scope}' contains a forbidden action — "
            "execution rejected (REQ-803)"
        )

    # Step 3: run executor (mock path for tests).
    if executor is None:
        if os.environ.get("SQX_FORCE_MOCK") == "1":
            executor = _mock_executor
        else:
            raise AuthorityViolationError(
                "No executor registered for phase "
                f"{directive.phase_id} — production execution must be "
                "provided by the phase agent"
            )

    result = await executor(directive)

    # Step 4: validate the envelope.
    validate_phase_result(result)

    # Step 5: long-op handoff guard — if the executor returned a handoff_payload,
    # ensure it is a properly shaped LongOpSpec and log the handoff.
    if result.handoff_payload is not None:
        try:
            spec = LongOpSpec(**result.handoff_payload)
            logger.info(
                "Phase %s handed off long op to orchestrator shell: "
                "command=%s timeout=%ds log=%s",
                directive.phase_id,
                spec.command,
                spec.timeout,
                spec.log_path,
            )
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Phase %s returned malformed handoff_payload: %s",
                directive.phase_id,
                exc,
            )

    return result


# ---------------------------------------------------------------------------
# Mock executor (test helper — not exported)
# ---------------------------------------------------------------------------


async def _mock_executor(directive: PhaseDirective) -> PhaseResult:
    """Default mock executor used when ``SQX_FORCE_MOCK=1``."""
    phase_id = directive.phase_id
    scope = directive.scope
    # Simulate an out-of-scope attempt when the scope payload says so.
    if "authority violation" in str(directive.payload).lower():
        return PhaseResult(
            status="failed",
            executive_summary=f"Authority violation detected in {phase_id}",
            artifacts=[],
            next_recommended="halt",
            risks=["out-of-scope action attempted"],
            phase_id=phase_id,
            evidence={"violation": scope},
            handoff_payload=None,
        )
    # Simulate a long-op handoff when the scope indicates it.
    if "long op" in scope.lower():
        return PhaseResult(
            status="success",
            executive_summary=f"{phase_id} produced a long-running script",
            artifacts=[f"{phase_id}_script.json"],
            next_recommended="orchestrator-shell",
            risks=["long operation delegated"],
            phase_id=phase_id,
            evidence={"handoff": True},
            handoff_payload={
                "command": f"echo 'running {phase_id} long op'",
                "log_path": f"/tmp/sqx-logs/{phase_id}.log",
                "expected": "DONE",
                "timeout": 300,
                "cleanup": f"rm -f /tmp/sqx-logs/{phase_id}.log",
            },
        )
    # Normal success path.
    return PhaseResult(
        status="success",
        executive_summary=f"{phase_id} completed successfully",
        artifacts=[f"{phase_id}_output.json"],
        next_recommended=(
            PHASES[PHASES.index(phase_id) + 1]
            if PHASES.index(phase_id) + 1 < len(PHASES)
            else "live-ops"
        ),
        risks=[],
        phase_id=phase_id,
        evidence={"mock": True},
        handoff_payload=None,
    )
