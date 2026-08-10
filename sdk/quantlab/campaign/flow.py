"""Flow-integrity invariant for the orchestrated campaign loop (REQ-37).

The full lifecycle MUST retain all 14 flow phases, in order, each gated by
human confirmation. Simplification applies ONLY to code/infrastructure — it
MUST NOT remove, reorder, merge, or auto-approve any flow phase. Phase count
and order MUST be asserted at campaign start and after any harness change.

``PHASES`` is the single canonical list, mirrored in
``AI/opencode/agents/campaign.md`` (kept in sync by test). ``assert_flow``
aborts with :class:`FlowIntegrityError` before any execution begins when a
phase is dropped, reordered, merged, duplicated, or unknown.
``assert_flow_segments`` is the segment-preserving preflight for a built
pipeline: presence plus the post-deploy boundary and loop-tail order.
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = [
    "PHASES",
    "STAGE_FOR_PHASE",
    "FlowIntegrityError",
    "assert_flow",
    "assert_flow_segments",
    "missing_flow_stages",
]

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


# Stage-name mapping used to resolve the canonical phases onto the built
# orchestrated pipeline (REQ-37). Each canonical phase maps to the pipeline
# stage that implements it, so the flow-integrity preflight can assert that
# no phase was dropped before execution begins.
STAGE_FOR_PHASE: dict[str, str] = {
    "research": "research",
    "hypothesis": "hypothesis_builder",
    "config": "builder",
    "review": "config_review",
    "dispatch": "dispatch",
    # ADR-3: the orchestrated tail binds the monitor phase to
    # ExecutionMonitorStage ("execution_monitor"). The legacy "monitor"
    # MonitoringAgent satisfies the phase via the alias below.
    "monitor": "execution_monitor",
    "retest": "retester",
    "optimize": "optimizer",
    "portfolio": "portfolio",
    "compile": "compile",
    "deploy": "deploy",
    "demo": "demo",
    "archive": "archive",
    "live-ops": "live_ops",
}


# Stage-name aliases that satisfy a canonical phase. The LLM-routed research
# stage ("research_llm") satisfies the "research" phase; the legacy
# MonitoringAgent ("monitor") satisfies the "monitor" phase (ADR-3).
_STAGE_ALIASES: dict[str, tuple[str, ...]] = {
    "research": ("research", "research_llm"),
    "monitor": ("monitor", "execution_monitor"),
}


def _present_stage(canonical: str, names: Sequence[str]) -> str:
    """Resolve *canonical* to the concrete stage name present in *names*.

    Prefers the exact canonical name, then falls back to its aliases — e.g.
    the orchestrated pipeline binds the monitor phase to ``execution_monitor``
    (ADR-3) while legacy pipelines keep ``monitor``; both satisfy the phase.
    Returns *canonical* unchanged when no alias matches, letting the caller's
    ``index()`` raise a clear ``ValueError``.
    """
    if canonical in names:
        return canonical
    for alias in _STAGE_ALIASES.get(canonical, ()):
        if alias in names:
            return alias
    return canonical


def _optional_stage_names(optional_phases: Sequence[str]) -> set[str]:
    """Resolve *optional_phases* (canonical phase or stage names) to stages."""
    resolved: set[str] = set()
    for name in optional_phases:
        resolved.add(STAGE_FOR_PHASE.get(name, name))
    return resolved


def assert_flow_segments(
    stage_names: Sequence[str],
    *,
    optional_phases: Sequence[str] = (),
) -> None:
    """Assert *stage_names* preserve the REQ-37 segment structure.

    Unlike :func:`assert_flow` (exact 14-phase equality) and
    :func:`missing_flow_stages` (presence only), this is the
    SEGMENT-PRESERVING preflight: it verifies, fail-closed, that the built
    pipeline keeps every canonical phase present and in its segment order:

    - presence: every canonical phase maps to a stage in *stage_names*
      (``"research_llm"`` satisfies ``"research"``), unless the phase's
      stage is listed in *optional_phases*;
    - post-deploy boundary: ``deploy < demo < archive < live_ops < monitor``;
    - loop tail: ``monitor < guardian_evaluate < [retester] < [optimizer]``.

    *optional_phases* holds canonical phase names or stage names (e.g.
    ``("retester", "optimizer")``) whose absence is allowed — callers derive
    it from config so the conditional ``retester``/``optimizer`` stages are
    only required when configured (ADR-1).

    Args:
        stage_names: Stage names of a built pipeline (e.g.
            ``[s.name for s in pipeline.stages]``).
        optional_phases: Canonical phase or stage names allowed to be absent.

    Raises:
        FlowIntegrityError: On any dropped phase or reordered segment,
            before any execution begins.
    """
    names = list(stage_names)
    present = set(names)
    optional_stages = _optional_stage_names(optional_phases)

    # 1. Presence — every non-optional canonical phase must have a stage.
    missing: list[str] = []
    for phase in PHASES:
        stage = STAGE_FOR_PHASE[phase]
        if stage in optional_stages:
            continue
        candidates = _STAGE_ALIASES.get(phase, (stage,))
        if not any(candidate in present for candidate in candidates):
            missing.append(phase)
    if missing:
        raise FlowIntegrityError(
            "flow-integrity error: missing phases "
            f"({', '.join(missing)}) — aborting before execution (REQ-37)"
        )

    # 2. Post-deploy boundary: deploy < demo < archive < live_ops < monitor
    #    (the monitor phase resolves to its bound stage — ADR-3).
    boundary = ("deploy", "demo", "archive", "live_ops", "monitor")
    resolved_boundary = [_present_stage(s, names) for s in boundary]
    for earlier, later in zip(resolved_boundary, resolved_boundary[1:]):
        if names.index(earlier) >= names.index(later):
            raise FlowIntegrityError(
                "flow-integrity error: boundary reorder — "
                f"'{earlier}' must precede '{later}' (REQ-37)"
            )

    # 3. Loop tail: monitor < guardian_evaluate < [retester] < [optimizer].
    tail = [_present_stage("monitor", names), "guardian_evaluate"]
    for stage in ("retester", "optimizer"):
        if stage in present:
            tail.append(stage)
    for earlier, later in zip(tail, tail[1:]):
        if names.index(earlier) >= names.index(later):
            raise FlowIntegrityError(
                "flow-integrity error: loop-tail reorder — "
                f"'{earlier}' must precede '{later}' (REQ-37)"
            )


def missing_flow_stages(stage_names: Sequence[str]) -> list[str]:
    """Return canonical phases whose stage is absent from *stage_names*.

    The REQ-37 preflight: an empty result means the pipeline covers every
    canonical phase, so execution may proceed. Any non-empty result names the
    dropped phases and the campaign SHALL abort before execution begins.

    Args:
        stage_names: Stage names of a built pipeline (e.g.
            ``[s.name for s in pipeline.stages]``).

    Returns:
        Canonical phase names (in ``PHASES`` order) with no mapped stage
        present in *stage_names*.
    """
    present = set(stage_names)
    return [phase for phase in PHASES if STAGE_FOR_PHASE[phase] not in present]
