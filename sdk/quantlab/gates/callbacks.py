"""Gate callbacks for orchestrated mode — decision-file IPC + fail-closed (REQ-10, REQ-11).

The pipeline and the agent communicate through a decision-file channel (AD-4):

    {gate_event_dir}/{campaign_id}/{gate_id}.pending.json   → {gate_id, campaign_id, status, envelope}
    {gate_event_dir}/{campaign_id}/{gate_id}.decision.json  → {action, reason, decided_by, proposed_changes}

- ``QuestionToolGateCallback`` is the primary resolution path: it writes the
  pending file; the agent reads it, asks the human via the OpenCode
  ``question`` tool, and writes the decision file. The callback polls for the
  decision and returns it to the pipeline. On timeout it raises
  ``asyncio.TimeoutError`` so the orchestrator applies the gate's fail-closed
  fallback (HOLD for HUMAN_APPROVE_CONFIG) — never auto-approve.
- ``StdinGateCallback`` is the headless fallback: one decision-envelope JSON
  line read from stdin.
- ``fail_closed_callback`` returns HOLD — used when orchestrated mode has no
  callback registered. Legacy CLI behavior is unchanged (REQ-11): the legacy
  ``_auto_approve`` path is only replaced under the orchestrated flag.

``campaign_id`` is restricted to ``[A-Za-z0-9_-]`` (boundary 2) to prevent
path traversal via gate file names.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, Field

from quantlab.gates.models import GateDecision, GateDecisionAction

logger = logging.getLogger(__name__)

DEFAULT_GATE_EVENT_DIR = "/tmp/sqx-gates"
CAMPAIGN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


# ── Campaign id sanitisation (boundary 2) ─────────────────────────────────────


def sanitize_campaign_id(campaign_id: str) -> str:
    """Restrict ``campaign_id`` to ``[A-Za-z0-9_-]``; reject path traversal.

    Args:
        campaign_id: Raw campaign identifier from pipeline context.

    Returns:
        The sanitised campaign id.

    Raises:
        ValueError: If the id is empty or contains characters outside the
            allowed set (e.g. ``../`` traversal attempts).
    """
    if not isinstance(campaign_id, str) or not CAMPAIGN_ID_PATTERN.fullmatch(campaign_id):
        raise ValueError(
            f"Invalid campaign_id {campaign_id!r}: must match [A-Za-z0-9_-]+ "
            "(path traversal is not allowed)."
        )
    return campaign_id


# ── Decision-file protocol ────────────────────────────────────────────────────


def gate_dir(gate_event_dir: str | Path, campaign_id: str) -> Path:
    """Absolute directory for a campaign's gate files."""
    return Path(gate_event_dir) / sanitize_campaign_id(campaign_id)


def pending_path(gate_event_dir: str | Path, campaign_id: str, gate_id: str) -> Path:
    """Path of the pending file the callback writes for ``gate_id``."""
    return gate_dir(gate_event_dir, campaign_id) / f"{gate_id}.pending.json"


def decision_path(gate_event_dir: str | Path, campaign_id: str, gate_id: str) -> Path:
    """Path of the decision file the agent writes for ``gate_id``."""
    return gate_dir(gate_event_dir, campaign_id) / f"{gate_id}.decision.json"


class PendingFile(BaseModel):
    """Envelope the callback writes so the agent can present the gate."""

    gate_id: str
    campaign_id: str
    status: str = "pending"
    envelope: dict[str, Any] = Field(default_factory=dict)


class DecisionFile(BaseModel):
    """Decision envelope the agent writes after the human answers."""

    action: str
    reason: str = Field(default="")
    decided_by: str = Field(default="human")
    proposed_changes: dict[str, Any] = Field(default_factory=dict)


def write_pending(
    gate_event_dir: str | Path,
    campaign_id: str,
    gate_id: str,
    envelope: dict[str, Any],
) -> Path:
    """Write the pending file for ``gate_id`` and return its path."""
    path = pending_path(gate_event_dir, campaign_id, gate_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = PendingFile(
        gate_id=gate_id,
        campaign_id=campaign_id,
        status="pending",
        envelope=envelope,
    )
    path.write_text(payload.model_dump_json(), encoding="utf-8")
    logger.info("Gate pending file written: %s", path)
    return path


def read_decision_file(path: str | Path) -> DecisionFile:
    """Parse a decision file into a ``DecisionFile`` envelope."""
    return DecisionFile.model_validate_json(Path(path).read_text(encoding="utf-8"))


def decision_file_to_gate_decision(
    decision_file: DecisionFile,
    gate_id: str,
) -> GateDecision:
    """Map a decision-file envelope to a pipeline ``GateDecision``."""
    action = GateDecisionAction(decision_file.action)
    metadata: dict[str, Any] = {}
    if decision_file.proposed_changes:
        metadata["proposed_changes"] = decision_file.proposed_changes
    return GateDecision(
        gate_id=gate_id,
        action=action,
        reason=decision_file.reason,
        decided_by=decision_file.decided_by,
        metadata=metadata,
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────


class QuestionToolGateCallback:
    """Primary orchestrated callback — decision-file protocol (AD-4).

    Writes ``{gate_id}.pending.json``, then polls for ``{gate_id}.decision.json``
    (written by the agent after the human answers via the ``question`` tool).

    Args:
        gate_event_dir: Base directory for gate files (default ``/tmp/sqx-gates``).
        campaign_id: Fixed campaign id; falls back to ``ctx["campaign_id"]``.
        poll_interval: Seconds between decision-file polls.
        timeout: Seconds to wait for the decision before raising
            ``asyncio.TimeoutError`` (the orchestrator then applies the
            gate's HOLD fallback). ``None`` waits indefinitely — the
            orchestrator's own ``asyncio.wait_for`` governs the ceiling.
    """

    def __init__(
        self,
        gate_event_dir: str | Path = DEFAULT_GATE_EVENT_DIR,
        campaign_id: str | None = None,
        *,
        poll_interval: float = 0.1,
        timeout: float | None = None,
    ) -> None:
        self._gate_event_dir = Path(gate_event_dir)
        self._campaign_id = campaign_id
        self._poll_interval = poll_interval
        self._timeout = timeout

    async def __call__(self, ctx: dict[str, Any]) -> GateDecision:
        """Run the decision-file protocol for the gate in ``ctx``."""
        gate_id = ctx.get("gate_id", "")
        if not gate_id:
            raise ValueError("gate_id is required in the gate context")

        campaign_id = sanitize_campaign_id(self._campaign_id or ctx.get("campaign_id", ""))
        write_pending(self._gate_event_dir, campaign_id, gate_id, ctx)

        target = decision_path(self._gate_event_dir, campaign_id, gate_id)
        deadline = None if self._timeout is None else time.monotonic() + self._timeout

        while True:
            if target.exists():
                decision_file = read_decision_file(target)
                logger.info("Gate decision file consumed: %s", target)
                return decision_file_to_gate_decision(decision_file, gate_id)

            if deadline is not None and time.monotonic() >= deadline:
                raise asyncio.TimeoutError(
                    f"No decision file for gate {gate_id} (campaign {campaign_id}) "
                    f"within {self._timeout}s — fail closed."
                )
            await asyncio.sleep(self._poll_interval)


class StdinGateCallback:
    """Headless fallback — reads one decision-envelope JSON line from stdin.

    Args:
        reader: Async callable returning one line of JSON. Defaults to reading
            a line from ``sys.stdin``.
    """

    def __init__(self, reader: Callable[[], Awaitable[str]] | None = None) -> None:
        self._reader = reader or self._default_reader

    @staticmethod
    async def _default_reader() -> str:
        import sys

        return await asyncio.to_thread(sys.stdin.readline)

    async def __call__(self, ctx: dict[str, Any]) -> GateDecision:
        """Read the human decision from the fallback stdin channel."""
        line = await self._reader()
        decision_file = DecisionFile.model_validate_json(line)
        return decision_file_to_gate_decision(decision_file, ctx.get("gate_id", ""))


async def fail_closed_callback(ctx: dict[str, Any]) -> GateDecision:
    """Fail-closed decision when orchestrated mode has no callback (REQ-11).

    Never auto-approves: returns a HOLD decision for the gate in ``ctx``.
    """
    gate_id = ctx.get("gate_id", "UNKNOWN")
    return GateDecision(
        gate_id=gate_id,
        action=GateDecisionAction.HOLD,
        reason=(
            f"Fail-closed: no gate callback registered for {gate_id} in "
            "orchestrated mode — holding for manual resolution."
        ),
        decided_by="system",
    )
