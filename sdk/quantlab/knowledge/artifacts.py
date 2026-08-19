"""SDK-owned deterministic campaign artifact writers (campaign-artifact-writers).

Phase agents keep the REQ-820 "artifacts not bytes" boundary: the SDK renders
and persists the user-facing campaign artifacts — ``proposal.md`` and
``spec.md`` — from in-memory stage outcome dicts. No LLM-generated text is
required: the renderers are deterministic and regenerable.

Layout::

    knowledge/structured/{campaign_id}/proposal.md   <- research stage (Q1)
    knowledge/structured/{campaign_id}/spec.md       <- hypothesis/config (Q1)

Writers degrade gracefully: an empty ``campaign_id`` or ``knowledge_root``
returns ``""`` instead of raising, so the delegation layer records the gap in
``risks`` and claims nothing (spec "Missing knowledge_root degrades"
scenarios). Write errors (``OSError``) propagate to the caller, which folds
them into a failed envelope (REQ-802) — a failed write is never reported as a
success.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

#: Relative Knowledge Lake paths (resolved against the lake root).
_PROPOSAL_REL = "structured/{campaign_id}/proposal.md"
_SPEC_REL = "structured/{campaign_id}/spec.md"

#: Deterministic marker for an explicitly empty section (never a silent lie).
_EMPTY_MARKER = "(none)"


def _json_safe(value: Any) -> Any:
    """Coerce *value* to JSON-safe types.

    Mirrors ``quantlab.campaign.delegation._json_safe`` (intentionally
    mirrored, not imported, to avoid an import cycle: delegation.py imports
    this module for the writer hooks).
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def _render_value(value: Any) -> str:
    """Deterministic YAML block for *value*; ``None``/empty render a marker."""
    if value is None or value == [] or value == {}:
        return _EMPTY_MARKER
    import yaml

    return yaml.safe_dump(
        _json_safe(value), sort_keys=False, default_flow_style=False
    ).rstrip()


def _section(title: str, value: Any) -> str:
    """One markdown section; the heading is always present."""
    return f"## {title}\n\n{_render_value(value)}\n"


def render_proposal_markdown(campaign_id: str, outcome: dict[str, Any]) -> str:
    """Deterministic ``proposal.md`` content from a research stage outcome.

    Renders the in-memory research output — ``research_config``, hypotheses,
    sources, evidence — so the persisted proposal survives agent failure.

    Args:
        campaign_id: Campaign identifier.
        outcome: The research stage outcome dict.

    Returns:
        The proposal markdown text.
    """
    lines = [f"# Campaign Proposal — {campaign_id}", ""]
    lines.append(_section("Research Configuration", outcome.get("research_config")))
    lines.append(_section("Hypotheses", outcome.get("hypotheses")))
    lines.append(_section("Sources", outcome.get("sources")))
    lines.append(_section("Evidence", outcome.get("evidence")))
    return "\n".join(lines)


def render_spec_markdown(campaign_id: str, outcome: dict[str, Any]) -> str:
    """Deterministic ``spec.md`` content from a hypothesis/config outcome.

    The technical contract covers builder/retester/optimizer/portfolio
    configuration and acceptance criteria; the hypotheses section renders
    explicitly empty when the campaign has zero hypotheses (spec scenario).

    Args:
        campaign_id: Campaign identifier.
        outcome: The hypothesis or config stage outcome dict.

    Returns:
        The spec markdown text.
    """
    lines = [f"# Campaign Spec — {campaign_id}", ""]
    lines.append(_section("Hypotheses", outcome.get("hypotheses")))
    builder = outcome.get("build_config") or outcome.get("building_blocks")
    lines.append(_section("Builder Configuration", builder))
    lines.append(_section("Strategies", outcome.get("strategies")))
    lines.append(_section("Retester Configuration", outcome.get("retest")))
    lines.append(_section("Optimizer Configuration", outcome.get("optimize")))
    lines.append(_section("Portfolio Configuration", outcome.get("portfolio")))
    lines.append(_section("Acceptance Criteria", outcome.get("acceptance_criteria")))
    return "\n".join(lines)


def write_proposal_artifact(
    campaign_id: str, outcome: dict[str, Any], root: str | Path
) -> str:
    """Persist ``proposal.md`` under ``structured/{campaign_id}/``.

    Args:
        campaign_id: Campaign identifier.
        outcome: The research stage outcome dict.
        root: Knowledge Lake root path.

    Returns:
        The relative Knowledge Lake path of the written artifact, or ``""``
        when *campaign_id* or *root* is empty (caller records the gap and
        claims nothing).

    Raises:
        OSError: On a write failure — propagates so the caller folds a failed
            envelope instead of claiming success.
    """
    if not campaign_id or not root:
        return ""
    rel = _PROPOSAL_REL.format(campaign_id=campaign_id)
    target = Path(root) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_proposal_markdown(campaign_id, outcome), encoding="utf-8"
    )
    return rel


def write_spec_artifact(
    campaign_id: str, outcome: dict[str, Any], root: str | Path
) -> str:
    """Persist ``spec.md`` under ``structured/{campaign_id}/``.

    Args:
        campaign_id: Campaign identifier.
        outcome: The hypothesis/config stage outcome dict.
        root: Knowledge Lake root path.

    Returns:
        The relative Knowledge Lake path of the written artifact, or ``""``
        when *campaign_id* or *root* is empty.

    Raises:
        OSError: On a write failure — propagates to the caller.
    """
    if not campaign_id or not root:
        return ""
    rel = _SPEC_REL.format(campaign_id=campaign_id)
    target = Path(root) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_spec_markdown(campaign_id, outcome), encoding="utf-8")
    return rel