"""phase_runner — standalone CLI bridge to the production executors (REQ-818).

A phase subagent invokes the runner through its bash allowlist
(``sdk/quantlab/campaign/*``, D1):

    python3 sdk/quantlab/campaign/phase_runner.py --phase <name> --directive '<json>'

The runner parses the directive (strict JSON), resolves the phase's production
executor via ``execute_phase()`` (REQ-815), enforces the bounded scope
deny-first (REQ-803), and emits the validated ``PhaseResult`` envelope as JSON
on stdout.  Exit code 0 on success; 1 with a JSON error envelope when the phase
is unknown, the directive is malformed, or the scope is out-of-bounds.

Handoff policy (D5): a mechanical ``LongOpSpec`` targets
``/tmp/opencode/{phase}.log`` with ``timeout >= 240`` and a cleanup command,
and the runner writes the per-phase report at
``/tmp/opencode/{phase}.report.md`` recording the handoff (REQ-818 s3).

This module is NOT a CLI subcommand (D1): the phase-agent bash allowlist only
matches ``sdk/quantlab/campaign/*`` paths, and REQ-818 requires the runner
"under ``sdk/quantlab/campaign/``".  ``cmd_campaign_run_flow`` remains the
infrastructure driver (REQ-817).
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

from quantlab.campaign.delegation import (
    AuthorityViolationError,
    PhaseDirective,
    PhaseNotFoundError,
    PhaseResult,
    execute_phase,
    validate_phase_result,
)
from quantlab.campaign.flow import PHASES

#: Handoff/report directory (D5).  Mechanical long ops log here and the
#: per-phase report lands at ``{phase}.report.md``.
_HANDOFF_DIR = Path("/tmp/opencode")


def build_directive(phase: str, directive_json: str) -> PhaseDirective:
    """Parse strict JSON into a :class:`PhaseDirective` (REQ-818).

    Args:
        phase: Canonical phase id — MUST be in ``PHASES``.
        directive_json: JSON object with optional ``scope``, ``payload`` and
            ``previous_result`` keys.

    Returns:
        A ``PhaseDirective`` for the phase.

    Raises:
        PhaseNotFoundError: If *phase* is not in ``PHASES`` (rejected before
            any parsing or execution).
        ValueError: If *directive_json* is not valid JSON or not an object.
    """
    if phase not in PHASES:
        raise PhaseNotFoundError(
            f"phase '{phase}' is not in PHASES — "
            "runner rejected the directive (REQ-818)"
        )
    try:
        data = json.loads(directive_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed directive JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(
            "directive JSON must be an object with scope/payload keys (REQ-818)"
        )

    previous_result: PhaseResult | None = None
    raw_previous = data.get("previous_result")
    if isinstance(raw_previous, dict):
        previous_result = PhaseResult(**raw_previous)

    return PhaseDirective(
        phase_id=phase,
        scope=str(data.get("scope") or f"{phase}-scope"),
        payload=dict(data.get("payload") or {}),
        previous_result=previous_result,
    )


async def run(phase: str, directive_json: str) -> PhaseResult:
    """Bridge a directive to its production executor (REQ-818).

    Args:
        phase: Canonical phase id.
        directive_json: Directive JSON (see :func:`build_directive`).

    Returns:
        A validated ``PhaseResult`` from the production executor.

    Raises:
        PhaseNotFoundError: Unknown phase.
        ValueError: Malformed directive.
        AuthorityViolationError: Out-of-scope directive — no stage runs.
    """
    directive = build_directive(phase, directive_json)
    result = await execute_phase(directive)
    validate_phase_result(result)
    return result


def _write_report(phase: str, result: PhaseResult) -> Path:
    """Write the per-phase report at ``/tmp/opencode/{phase}.report.md`` (D5).

    Records the phase outcome; for a mechanical phase the report records the
    handoff (REQ-818 s3).
    """
    report = _HANDOFF_DIR / f"{phase}.report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {phase} report",
        f"- phase: {phase}",
        f"- status: {result.status}",
        f"- next_recommended: {result.next_recommended}",
    ]
    if result.handoff_payload is not None:
        lines.append("- handoff: mechanical long-op")
        for key in ("command", "log_path", "timeout", "cleanup"):
            lines.append(f"  - {key}: {result.handoff_payload.get(key)}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``--phase`` / ``--directive`` → JSON envelope (REQ-818).

    Args:
        argv: CLI arguments (defaults to ``sys.argv[1:]``).

    Returns:
        0 on success (validated envelope on stdout); 1 with a JSON error
        envelope on stdout for unknown phase, malformed directive, or
        out-of-scope rejection.
    """
    parser = argparse.ArgumentParser(
        prog="phase_runner",
        description="Bridge a PhaseDirective to its production executor (REQ-818).",
    )
    parser.add_argument(
        "--phase",
        required=True,
        help="Canonical phase id from PHASES (e.g. research, dispatch)",
    )
    parser.add_argument(
        "--directive",
        required=True,
        help='Directive JSON with optional scope/payload keys, e.g. \'{"payload": {...}}\'',
    )
    args = parser.parse_args(argv)

    try:
        result = asyncio.run(run(args.phase, args.directive))
    except (PhaseNotFoundError, ValueError, AuthorityViolationError) as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": type(exc).__name__,
                    "detail": str(exc),
                }
            )
        )
        return 1

    _write_report(args.phase, result)
    print(json.dumps(dataclasses.asdict(result), default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
