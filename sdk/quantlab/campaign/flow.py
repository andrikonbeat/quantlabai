"""Flow-integrity invariant for the orchestrated campaign loop (REQ-37).

The full lifecycle MUST retain all 14 flow phases, in order, each gated by
human confirmation. Simplification applies ONLY to code/infrastructure — it
MUST NOT remove, reorder, merge, or auto-approve any flow phase. Phase count
and order MUST be asserted at campaign start and after any harness change.

``PHASES`` is the single canonical list, mirrored in
``AI/opencode/agents/campaign.md`` (kept in sync by test). ``assert_flow``
aborts with :class:`FlowIntegrityError` before any execution begins when a
phase is dropped, reordered, merged, duplicated, or unknown.
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = ["PHASES", "FlowIntegrityError", "assert_flow"]

# Canonical 14-phase lifecycle (REQ-01 modified): research → hypothesis →
# SQX config → config review → dispatch → monitor → retest → optimize →
# portfolio → compile → deploy → demo → archive → live-ops (Guardian
# watching the demo account).
PHASES: tuple[str, ...] = (
    "research",
    "hypothesis",
    "config",
    "review",
    "dispatch",
    "monitor",
    "retest",
    "optimize",
    "portfolio",
    "compile",
    "deploy",
    "demo",
    "archive",
    "live-ops",
)


class FlowIntegrityError(RuntimeError):
    """The campaign flow deviates from the canonical 14-phase lifecycle."""


def assert_flow(phases: Sequence[str]) -> None:
    """Assert *phases* is exactly the canonical lifecycle, in order.

    Fail-closed (REQ-37): ANY deviation — missing, reordered, merged,
    duplicated, or unknown phase — raises :class:`FlowIntegrityError`
    naming the offending phase. The campaign MUST abort before execution
    begins; nothing is ever reordered or skipped.

    Args:
        phases: The phase sequence a harness would run.

    Raises:
        FlowIntegrityError: On any deviation from ``PHASES``.
    """
    if len(phases) != len(PHASES):
        missing = [p for p in PHASES if p not in set(phases)]
        extra = [p for p in phases if p not in set(PHASES)]
        raise FlowIntegrityError(
            "flow-integrity error: expected 14 phases, got "
            f"{len(phases)} (missing={missing}, extra={extra})"
        )
    seen: set[str] = set()
    for idx, phase in enumerate(phases):
        if phase not in set(PHASES):
            raise FlowIntegrityError(
                f"flow-integrity error: unknown phase '{phase}' at position {idx}"
            )
        if phase in seen:
            raise FlowIntegrityError(
                f"flow-integrity error: duplicate phase '{phase}'"
            )
        seen.add(phase)
        if phase != PHASES[idx]:
            raise FlowIntegrityError(
                f"flow-integrity error: phase '{phase}' at position {idx} "
                f"out of order — expected '{PHASES[idx]}'"
            )
