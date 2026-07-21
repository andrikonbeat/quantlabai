"""Engram audit logger for human gate decisions.

Persists every gate decision to an Engram topic keyed by campaign ID
so that the audit trail survives process restarts and is queryable
cross-campaign.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


async def record_gate_decision(
    engram_save_fn: Any,
    gate_id: str,
    decision: dict[str, Any],
    campaign_id: str,
    ctx: Any,
) -> None:
    """Persist a gate decision to Engram.

    Writes a structured observation to topic ``agent/research-director/{campaign_id}``
    with type ``decision``.  Failures are swallowed so that a notification
    system outage cannot block the pipeline.

    Args:
        engram_save_fn: Async function matching ``mem_save``'s async signature.
        gate_id: The gate that produced the decision.
        decision: Serialised ``GateDecision`` dict.
        campaign_id: Campaign this decision belongs to.
        ctx: Pipeline context (may provide extra metadata).
    """
    if engram_save_fn is None:
        logger.debug("Engram save function not configured — skipping audit for '%s'", gate_id)
        return

    topic_key = f"agent/research-director/{campaign_id}"

    timestamp = decision.get("timestamp") or datetime.now(timezone.utc).isoformat()
    context_summary = {}
    if hasattr(ctx, "artifacts"):
        context_summary = {
            k: type(v).__name__ if not isinstance(v, (str, int, float, bool)) else v
            for k, v in list(ctx.artifacts.items())[:10]
        }

    content = (
        "**What**: Gate '{gate_id}' decided {action}\n"
        "**Why**: {reason}\n"
        "**When**: {timestamp}\n"
        "**Decided by**: {decided_by}\n"
        "**Campaign**: {campaign_id}\n"
        "**Context summary**: {context_summary}"
    ).format(
        gate_id=gate_id,
        action=decision.get("action", "unknown"),
        reason=decision.get("reason", ""),
        timestamp=timestamp,
        decided_by=decision.get("decided_by", "system"),
        campaign_id=campaign_id,
        context_summary=context_summary,
    )

    try:
        await engram_save_fn(
            title=f"gate-decision/{gate_id}",
            type="decision",
            scope="project",
            topic_key=topic_key,
            content=content,
        )
        logger.info("Engram audit recorded for gate '%s' (topic=%s)", gate_id, topic_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Engram audit recording failed for gate '%s': %s", gate_id, exc)
