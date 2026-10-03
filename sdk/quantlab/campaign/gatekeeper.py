"""Post-phase gatekeeper (REQ-01).

Validates a ``PhaseResult`` envelope after a phase completes and allows exactly
one corrective re-run before halting.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from quantlab.campaign.delegation import (
    PhaseDirective,
    PhaseResult,
    _next_phase_id,
    validate_phase_result,
)

logger = logging.getLogger(__name__)


__all__ = [
    "GatekeeperError",
    "GatekeeperHalt",
    "run_post_phase_gatekeeper",
]


class GatekeeperError(Exception):
    """Raised when the post-phase gatekeeper detects an invalid result."""


class GatekeeperHalt(Exception):
    """Raised when the gatekeeper halts after exactly one corrective re-run."""


async def run_post_phase_gatekeeper(
    directive: PhaseDirective,
    result: PhaseResult,
    *,
    knowledge_root: str | None = None,
    executor: Callable[[PhaseDirective], Awaitable[PhaseResult]] | None = None,
) -> PhaseResult:
    """Post-phase gatekeeper (REQ-01).

    Steps:
    1. Contract conformance (``validate_phase_result``).
    2. Artifact read-back: declared artifacts exist on disk.
    3. No hallucination: spot-check for non-existent file/symbol/command refs.
    4. No input drift: result respects directive bounds.
    5. Routing coherence: ``next_recommended`` matches expected next phase.

    On first failure: re-run the phase exactly once with corrective feedback,
    then validate again. On second failure: raise ``GatekeeperHalt``.

    Args:
        directive: The original ``PhaseDirective`` for this phase.
        result: The ``PhaseResult`` returned by the phase executor.
        knowledge_root: Optional root directory for artifact existence checks.
        executor: Optional async callable for corrective re-run.  When ``None``
            and the gate fails, ``GatekeeperError`` is raised directly.

    Returns:
        The validated (or re-validated) ``PhaseResult``.

    Raises:
        GatekeeperError: When a gate check fails and no executor is available,
            or when the failure is not recoverable.
        GatekeeperHalt: When the phase fails the gatekeeper twice.
    """
    try:
        _run_gate_checks(directive, result, knowledge_root=knowledge_root)
    except GatekeeperError:
        if executor is None:
            raise
        corrective_directive = PhaseDirective(
            phase_id=directive.phase_id,
            scope=directive.scope,
            payload={
                **directive.payload,
                "corrective_feedback": {
                    "previous_risks": result.risks,
                    "previous_artifacts": result.artifacts,
                    "previous_summary": result.executive_summary,
                },
            },
            previous_result=result,
        )
        logger.info(
            "Gatekeeper re-running phase '%s' with corrective feedback",
            directive.phase_id,
        )
        corrected = await executor(corrective_directive)
        try:
            _run_gate_checks(directive, corrected, knowledge_root=knowledge_root)
        except GatekeeperError as exc:
            raise GatekeeperHalt(
                f"phase '{directive.phase_id}' failed gatekeeper twice: {exc}"
            ) from exc
        return corrected
    return result


def _run_gate_checks(
    directive: PhaseDirective,
    result: PhaseResult,
    *,
    knowledge_root: str | None = None,
) -> None:
    """Run all gatekeeper checks; raise ``GatekeeperError`` on first failure."""
    # 1. Contract conformance.
    validate_phase_result(result)

    # 2. Artifact read-back.
    if knowledge_root is not None:
        root = Path(knowledge_root)
        for artifact in result.artifacts:
            if not (root / artifact).exists():
                raise GatekeeperError(
                    f"artifact read-back failed: '{artifact}' not found under "
                    f"knowledge_root={knowledge_root}"
                )

    # 3. No hallucination.
    _check_no_hallucination(result)

    # 4. No input drift.
    _check_input_drift(result, directive)

    # 5. Routing coherence.
    expected_next = _next_phase_id(directive.phase_id)
    if result.next_recommended != expected_next:
        raise GatekeeperError(
            f"routing coherence: next_recommended='{result.next_recommended}' "
            f"!= expected='{expected_next}' for phase '{directive.phase_id}'"
        )


def _check_no_hallucination(result: PhaseResult) -> None:
    """Spot-check for hallucinated file/symbol/command references.

    Currently verifies:
    - Absolute-path artifacts point to real files.
    - Absolute-path strings inside ``evidence`` point to real files.
    """
    for artifact in result.artifacts:
        if artifact.startswith("/") and not Path(artifact).exists():
            raise GatekeeperError(
                f"hallucination: artifact '{artifact}' does not exist"
            )
    _check_paths_in_value(result.evidence)


def _check_paths_in_value(value: Any) -> None:
    """Recursively check absolute-path strings inside *value*."""
    if isinstance(value, str):
        if value.startswith("/") and not Path(value).exists():
            raise GatekeeperError(
                f"hallucination: evidence references non-existent path '{value}'"
            )
    elif isinstance(value, dict):
        for v in value.values():
            _check_paths_in_value(v)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_paths_in_value(item)


def _check_input_drift(result: PhaseResult, directive: PhaseDirective) -> None:
    """Ensure the result does not drift from the directive payload."""
    if result.phase_id != directive.phase_id:
        raise GatekeeperError(
            f"input drift: result.phase_id='{result.phase_id}' != "
            f"directive.phase_id='{directive.phase_id}'"
        )
