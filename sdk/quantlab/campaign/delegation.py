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

import base64
import dataclasses
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from quantlab.campaign.flow import PHASES, STAGE_FOR_PHASE

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
    "PRODUCTION_EXECUTORS",
    "PhaseExecutor",
    "execute_phase",
    "validate_phase_result",
    "run_stage_for_handoff",
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
# Production executor registry (REQ-815)
# ---------------------------------------------------------------------------

PhaseExecutor = Callable[[PhaseDirective], Awaitable[PhaseResult]]

#: Orchestrated stage bindings for the REQ-815 executor resolution.  The
#: research phase binds to the LLM-routed stage (``research_llm``) and the
#: monitor phase binds to the ADR-3 ``execution_monitor`` stage in the
#: orchestrated flow; every other phase resolves straight from
#: ``STAGE_FOR_PHASE``.
_STAGE_ORCHESTRATED_BINDING: dict[str, str] = {
    "research": "research_llm",
    "monitor": "execution_monitor",
}


def _stage_name_for_phase(phase: str) -> str:
    """Resolve the concrete orchestrated SDK stage name for *phase* (REQ-815).

    Uses ``STAGE_FOR_PHASE`` from :mod:`quantlab.campaign.flow` and prefers the
    orchestrated alias binding for the research/monitor phases.

    Args:
        phase: A canonical ``PHASES`` entry.

    Returns:
        The concrete stage name the phase's production executor runs.
    """
    return _STAGE_ORCHESTRATED_BINDING.get(phase, STAGE_FOR_PHASE[phase])


_STAGE_REGISTRY: Any | None = None


def _get_stage_registry() -> Any:
    """Lazily build the pipeline ``StageRegistry`` (avoids import cycles)."""
    global _STAGE_REGISTRY
    if _STAGE_REGISTRY is None:
        from quantlab.pipeline.registry import StageRegistry

        _STAGE_REGISTRY = StageRegistry()
    return _STAGE_REGISTRY


def _json_safe(value: Any) -> Any:
    """Recursively coerce *value* into a JSON-serialisable form.

    Dataclasses become dicts (``asdict``), pydantic models use ``model_dump``,
    paths become strings; anything else falls back to ``str``.  Stage outcomes
    are folded into ``PhaseResult.evidence``, which the runner emits as JSON
    (REQ-818).
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if dataclasses.is_dataclass(value):
        return _json_safe(dataclasses.asdict(value))
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    return str(value)


async def _run_sdk_stage(phase: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Resolve and execute the SDK stage for *phase* (REQ-815/REQ-803).

    The stage class is looked up in the pipeline ``StageRegistry`` under the
    stage name resolved by :func:`_stage_name_for_phase`.  A stage that is not
    registered fails closed with :class:`AuthorityViolationError` BEFORE any
    execution (deny-first, REQ-803).

    Args:
        phase: Canonical ``PHASES`` entry.
        payload: ``PhaseDirective.payload`` — optional ``config`` and
            ``artifacts`` sub-dicts feed the ``PipelineContext``.

    Returns:
        The stage outcome dict (artifacts written into the context).

    Raises:
        AuthorityViolationError: If no stage class is registered for the
            resolved stage name.
    """
    stage_name = _stage_name_for_phase(phase)
    stage_class = _get_stage_registry().get_stage_class(stage_name)
    if stage_class is None:
        raise AuthorityViolationError(
            f"No SDK stage '{stage_name}' registered for phase '{phase}' — "
            "execution rejected before any stage ran (REQ-815)"
        )

    from quantlab.pipeline.base import PipelineContext

    ctx = PipelineContext(
        config=dict(payload.get("config") or {}),
        artifacts=dict(payload.get("artifacts") or {}),
    )
    return await stage_class().execute(ctx)


def _next_phase_id(phase: str) -> str:
    """The phase that follows *phase* in the canonical flow (REQ-802)."""
    index = PHASES.index(phase)
    return PHASES[index + 1] if index + 1 < len(PHASES) else "live-ops"


def _make_reasoning_executor() -> PhaseExecutor:
    """Build the executor for a reasoning-heavy phase (REQ-816).

    Runs the SDK stage resolved via ``STAGE_FOR_PHASE``; the LLM phase agent
    reasons over the outcome (F2).  Never hands off: ``handoff_payload=None``.
    A stage failure folds into a ``status="failed"`` envelope (REQ-802 halts
    folding); an :class:`AuthorityViolationError` (deny-first) propagates.
    """

    async def executor(directive: PhaseDirective) -> PhaseResult:
        phase = directive.phase_id
        stage = _stage_name_for_phase(phase)
        try:
            outcome = await _run_sdk_stage(phase, directive.payload)
        except AuthorityViolationError:
            raise
        except Exception as exc:  # stage failure -> failed envelope (REQ-802)
            logger.warning("Phase %s stage '%s' failed: %s", phase, stage, exc)
            return PhaseResult(
                status="failed",
                executive_summary=(
                    f"{phase} SDK stage '{stage}' failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
                artifacts=[],
                next_recommended="halt",
                risks=[f"{phase} stage failed: {exc}"],
                phase_id=phase,
                evidence={"stage": stage, "error": str(exc)},
                handoff_payload=None,
            )
        return PhaseResult(
            status="success",
            executive_summary=f"{phase} phase completed — SDK stage '{stage}' ran",
            artifacts=[f"{phase}_{stage}.json"],
            next_recommended=_next_phase_id(phase),
            risks=[],
            phase_id=phase,
            evidence={"stage": stage, "outcome": _json_safe(outcome)},
            handoff_payload=None,
        )

    return executor


def _make_mechanical_executor(phase: str) -> PhaseExecutor:
    """Build the executor for a mechanical/long phase (REQ-816/REQ-809).

    Returns a ``LongOpSpec`` handoff for orchestrator-shell execution; the SDK
    stage is NEVER run inline (REQ-809: no subagent MAY wait on it).  Handoff
    policy (D5): log under ``/tmp/opencode/``, ``timeout >= 240`` (default
    300), cleanup required, per-phase report at
    ``/tmp/opencode/{phase}.report.md``.
    """

    async def executor(directive: PhaseDirective) -> PhaseResult:
        stage = _stage_name_for_phase(phase)
        log_path = f"/tmp/opencode/{phase}.log"
        payload_b64 = base64.b64encode(
            json.dumps(directive.payload).encode("utf-8")
        ).decode("ascii")
        command = (
            f"nohup python3 -c 'import asyncio,base64,json;"
            f"from quantlab.campaign.delegation import run_stage_for_handoff;"
            f"d=json.loads(base64.b64decode(\"{payload_b64}\").decode());"
            f"r=asyncio.run(run_stage_for_handoff(\"{phase}\", d));"
            f"print(json.dumps(r, default=str))' "
            f">> '{log_path}' 2>&1"
        )
        spec = LongOpSpec(
            command=command,
            log_path=log_path,
            expected="DONE",
            timeout=300,
            cleanup=(
                f"pkill -f 'phase_runner --phase {phase}' 2>/dev/null; "
                f"rm -f '{log_path}'"
            ),
        )
        logger.info(
            "Phase %s handed off long op to orchestrator shell (REQ-809): "
            "command=%s timeout=%ds log=%s",
            phase,
            spec.command,
            spec.timeout,
            spec.log_path,
        )
        return PhaseResult(
            status="success",
            executive_summary=(
                f"{phase} produced a long-running script for the orchestrator shell"
            ),
            artifacts=[f"{phase}_handoff.json"],
            next_recommended="orchestrator-shell",
            risks=["long operation delegated"],
            phase_id=phase,
            evidence={"stage": stage, "handoff": True},
            handoff_payload=dataclasses.asdict(spec),
        )

    return executor


async def _retest_executor(directive: PhaseDirective) -> PhaseResult:
    """Conditional retest executor (REQ-816).

    A retest run marked long in the directive payload (``long_op: true``)
    hands off via ``LongOpSpec``; otherwise the retester stage runs inline.
    """

    if directive.payload.get("long_op"):
        return await _make_mechanical_executor("retest")(directive)
    return await _make_reasoning_executor()(directive)


async def _live_ops_executor(directive: PhaseDirective) -> PhaseResult:
    """Live-ops executor — guardian delegation (REQ-816/REQ-37).

    Delegates to ``execute_guardian_directive()`` via the guardian SDK and
    folds the ``GuardianReport`` into ``evidence``.  Never adds a flow stage
    (REQ-37: ``PHASES`` stays 14) and never hands off.
    """
    from quantlab.guardian.agent import execute_guardian_directive
    from quantlab.guardian.feedback import GuardianDirective

    payload = directive.payload
    try:
        guardian = GuardianDirective(
            kind=str(payload.get("kind") or "live_ops_status"),
            campaign_id=str(payload.get("campaign_id") or "campaign"),
        )
        report = await execute_guardian_directive(guardian)
    except Exception as exc:
        logger.warning("live-ops guardian delegation failed: %s", exc)
        return PhaseResult(
            status="failed",
            executive_summary=f"live-ops guardian delegation failed: {exc}",
            artifacts=[],
            next_recommended="halt",
            risks=["live-ops guardian delegation failed"],
            phase_id=directive.phase_id,
            evidence={"stage": "live_ops", "error": str(exc)},
            handoff_payload=None,
        )
    report_dict = {
        "guardian_state": report.guardian_state,
        "feedback": (
            report.feedback.next_cycle_inputs()
            if report.feedback is not None
            else None
        ),
        "live_ops_status": report.live_ops_status,
        "escalations_acked": list(report.escalations_acked),
    }
    return PhaseResult(
        status="success",
        executive_summary=(
            "live-ops delegated to the guardian surface "
            f"(kind={guardian.kind})"
        ),
        artifacts=[],
        next_recommended="live-ops",
        risks=[],
        phase_id=directive.phase_id,
        evidence={
            "stage": "live_ops",
            "guardian_report": _json_safe(report_dict),
        },
        handoff_payload=None,
    )


def _build_production_executors() -> dict[str, PhaseExecutor]:
    """Build the 14 production executors, one per ``PHASES`` entry (REQ-815).

    REQ-816 hybrid split: reasoning-heavy phases (research, hypothesis,
    config, review, portfolio, optimize, archive) run the SDK stage with no
    handoff; mechanical phases (dispatch, monitor, compile, deploy, demo)
    return a ``LongOpSpec``; retest is conditional; live-ops delegates to the
    guardian surface.
    """
    reasoning = (
        "research", "hypothesis", "config", "review",
        "portfolio", "optimize", "archive",
    )
    mechanical = ("dispatch", "monitor", "compile", "deploy", "demo")

    executors: dict[str, PhaseExecutor] = {
        phase: _make_reasoning_executor() for phase in reasoning
    }
    executors.update({phase: _make_mechanical_executor(phase) for phase in mechanical})
    executors["retest"] = _retest_executor
    executors["live-ops"] = _live_ops_executor
    return executors


#: Registered production executors keyed by ``PHASES`` entry (REQ-815).
#: ``execute_phase()`` resolves: explicit ``executor`` arg → this registry →
#: mock under ``SQX_FORCE_MOCK=1`` → ``AuthorityViolationError`` (D2).
PRODUCTION_EXECUTORS: dict[str, PhaseExecutor] = _build_production_executors()


async def run_stage_for_handoff(phase: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Orchestrator-shell driver for a mechanical handoff (REQ-809/REQ-816).

    Executes the SDK stage for *phase* with *payload* and writes the
    per-phase report at ``/tmp/opencode/{phase}.report.md`` (D5).  This is the
    command target inside a mechanical ``LongOpSpec`` — it runs in the
    orchestrator shell, never inside the delegation glue.

    Args:
        phase: Canonical ``PHASES`` entry.
        payload: Directive payload feeding the stage context.

    Returns:
        The stage outcome dict.
    """
    outcome = await _run_sdk_stage(phase, payload)
    report = Path(f"/tmp/opencode/{phase}.report.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        f"# {phase} report\n"
        f"- status: completed\n"
        f"- stage: {_stage_name_for_phase(phase)}\n"
        f"- outcome: {json.dumps(_json_safe(outcome), default=str)}\n",
        encoding="utf-8",
    )
    return outcome


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
    3. Resolve the executor (D2): explicit arg → ``PRODUCTION_EXECUTORS``
       registry → mock when ``SQX_FORCE_MOCK`` is set → deny-first
       ``AuthorityViolationError``.
    4. Validate the returned envelope via :func:`validate_phase_result`.
    5. Return the envelope.

    Long-running operations are NEVER waited on inline.  When the executor
    returns a ``handoff_payload`` with a script spec, the glue hands it back
    to the orchestrator shell for ``nohup``/poll/cancel execution (REQ-809).

    Args:
        directive: The phase directive to execute.
        executor: Optional async callable that consumes the directive and
            returns a ``PhaseResult``.  When ``None``, the executor is
            resolved from the ``PRODUCTION_EXECUTORS`` registry; when the
            registry has no entry, a mock executor is used if
            ``SQX_FORCE_MOCK=1`` is set; otherwise ``AuthorityViolationError``
            is raised (deny-first, REQ-815 s2).

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

    # Step 3: resolve the executor (D2): explicit arg → PRODUCTION_EXECUTORS
    # registry → mock under SQX_FORCE_MOCK=1 → AuthorityViolationError
    # (deny-first, REQ-815 s2).  The registry is checked BEFORE the mock so a
    # registered production executor always runs in production.
    if executor is None:
        executor = PRODUCTION_EXECUTORS.get(directive.phase_id)
    if executor is None:
        if os.environ.get("SQX_FORCE_MOCK") == "1":
            executor = _mock_executor
        else:
            raise AuthorityViolationError(
                "No executor registered for phase "
                f"{directive.phase_id} — production execution must be "
                "provided by a registered PRODUCTION_EXECUTORS entry or the "
                "phase agent"
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
