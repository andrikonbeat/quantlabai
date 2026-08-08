"""Prior-campaign context composition (REQ-104, REQ-105, REQ-501).

The read/consumption side of the phase-boundary memory loop (WU2 built the
write side: :class:`quantlab.knowledge.memory_capture.MemoryCaptureService`).
``compose_prior_context`` reads prior decisions, risks and lessons from the
memory lake (``agent-memory/{agent}/{campaign}/memory.yaml``) and renders a
markdown block that is injected into the next phase's Result Contract
envelope (REQ-104) — the orchestrator/ResearchDirector receives prior
campaign memory in-prompt.

Data flow (D10)::

    compose_prior_context ─► memory lake + find_similar_campaigns ─► markdown ► next envelope

Similar-campaign ranking (REQ-501) uses ``KnowledgeStore.find_similar_campaigns``
— when the ``embeddings/`` area is empty (WU6) it returns ``[]`` and no
ranking section is rendered. The compose surface never raises on an empty
lake: it returns a "no prior memory" placeholder (REQ-104/501 empty-lake
scenario).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import yaml

# Header for the injected block; the placeholder shares it so the envelope
# always carries the section even when the lake is empty.
CONTEXT_HEADER = "## Prior Context"

# Ordered envelope fields surfaced per prior decision (D2 + lessons).
DECISION_BULLETS: tuple[str, ...] = ("executive_summary", "risks", "lessons")


def _placeholder(phase: str) -> str:
    """Markdown block returned when no prior memory exists (REQ-104/501)."""
    return (
        f"{CONTEXT_HEADER}\n\n"
        f"No prior memory found for phase '{phase}'. Starting fresh."
    )


def _decision_label(agent: str, campaign_id: str) -> str:
    return f"{campaign_id} ({agent})"


def _as_list(value: Any) -> list[str]:
    """Normalize a decision field (list, string, or None) to bullet strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _load_prior_decisions(
    root: str | Path,
    *,
    exclude_campaign: str,
    agent: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Read decision records from ``agent-memory/*/*/memory.yaml``.

    The current campaign's own records are excluded (REQ-104 composes
    *prior* campaigns). Records are sorted newest-first by ``timestamp`` and
    capped at ``limit``. Corrupted files are skipped — the filesystem is the
    source of truth.
    """
    memory_root = Path(root) / "agent-memory"
    if not memory_root.is_dir():
        return []

    agent_dirs = (
        [memory_root / agent] if agent else [d for d in memory_root.iterdir() if d.is_dir()]
    )

    decisions: list[dict[str, Any]] = []
    for agent_dir in agent_dirs:
        if not agent_dir.is_dir():
            continue
        for camp_dir in agent_dir.iterdir():
            if not camp_dir.is_dir():
                continue
            if camp_dir.name == exclude_campaign:
                continue
            memory_file = camp_dir / "memory.yaml"
            if not memory_file.is_file():
                continue
            try:
                records = yaml.safe_load(memory_file.read_text(encoding="utf-8")) or []
                if not isinstance(records, list):
                    records = [records]
            except Exception:
                continue  # Corrupted entry — skip, never fail composition.
            for record in records:
                if not isinstance(record, dict):
                    continue
                decision = dict(record)
                decision.setdefault("agent_name", agent_dir.name)
                decision.setdefault("campaign_id", camp_dir.name)
                decisions.append(decision)

    decisions.sort(
        key=lambda d: str(d.get("timestamp", "")),
        reverse=True,
    )
    return decisions[:limit]


def render_prior_context(
    phase: str,
    decisions: Sequence[dict[str, Any]],
    similar: Sequence[dict[str, Any]] = (),
) -> str:
    """Render the markdown prior-context block (REQ-104/501).

    Args:
        phase: The phase the block is being composed for.
        decisions: Prior decision records (with ``status``,
            ``executive_summary``, ``risks`` and optionally ``lessons``).
        similar: ``find_similar_campaigns`` matches (``campaign_id`` +
            ``similarity_score``), rendered as a ranked section (REQ-501).

    Each decision contributes its summary, risks and lessons bullets; lessons
    fall back to the executive summary when a record has no explicit
    ``lessons`` key, so captured envelopes still surface a lesson.
    """
    lines: list[str] = [CONTEXT_HEADER, ""]
    if not decisions and not similar:
        return _placeholder(phase)

    lines.append(f"Prior campaign memory for phase `{phase}` ({len(decisions)} decision(s)):")
    lines.append("")
    for decision in decisions:
        label = _decision_label(
            str(decision.get("agent_name", "unknown")),
            str(decision.get("campaign_id", "unknown")),
        )
        lines.append(f"### {label} — {decision.get('status', 'unknown')}")
        summary = decision.get("executive_summary")
        if summary:
            lines.append(f"- **Summary**: {summary}")
        risks = _as_list(decision.get("risks"))
        if risks:
            lines.append(f"- **Risks**: {'; '.join(risks)}")
        lessons = _as_list(decision.get("lessons"))
        if not lessons and summary:
            lessons = [str(summary)]
        if lessons:
            lines.append(f"- **Lessons**: {'; '.join(lessons)}")
        lines.append("")

    if similar:
        lines.append("### Similar campaigns (ranked by embedding similarity)")
        for match in sorted(
            similar,
            key=lambda m: float(m.get("similarity_score", 0.0)),
            reverse=True,
        ):
            lines.append(
                f"- {match.get('campaign_id')} "
                f"({float(match.get('similarity_score', 0.0)):.2f})"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def compose_prior_context(
    campaign_id: str,
    phase: str,
    *,
    limit: int = 10,
    root: str | Path = "knowledge",
    agent: str | None = None,
) -> str:
    """Compose the prior-context markdown block for a phase (REQ-104/501).

    Reads prior decisions from the memory lake (excluding the current
    campaign's own records) and ranks similar campaigns via embedding
    similarity when ``embeddings/`` data exists.

    Args:
        campaign_id: The campaign the context is composed for.
        phase: The upcoming phase name.
        limit: Maximum number of prior decisions to include.
        root: Knowledge Lake root (default ``knowledge``).
        agent: Restrict to one agent's memory (e.g. ``"research-director"``).

    Returns:
        Markdown block for injection into the Result Contract envelope.
        Never raises on an empty/missing lake — returns a placeholder.
    """
    decisions = _load_prior_decisions(
        root,
        exclude_campaign=campaign_id,
        agent=agent,
        limit=limit,
    )

    from quantlab.knowledge.store import KnowledgeStore

    store = KnowledgeStore(root)
    similar: list[dict[str, Any]] = []
    try:
        similar = store.find_similar_campaigns(campaign_id, top_k=limit)
    except Exception:
        similar = []  # Ranking is best-effort; never blocks composition.

    if not decisions and not similar:
        return _placeholder(phase)
    return render_prior_context(phase, decisions, similar)
