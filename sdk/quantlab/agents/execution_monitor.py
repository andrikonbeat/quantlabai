"""ExecutionMonitor — long-polling SQX campaign monitor (execution-monitor spec).

Polls a running campaign at a configurable interval (default 30s), detects
stall conditions (no progress for 2x expected duration), error states, and
daemon disconnection, and emits events to the campaign event bus. On a stall
the monitor writes a checkpoint FIRST, then invokes LLM diagnostics within a
60s budget; a timeout (or missing/no remediation) yields ``HOLD`` for human
review (fail-closed). Phase completion yields ``CONTINUE``.

Collaborators are injectable (``progress_fn``, ``checkpoint_writer``,
``diagnostics_fn``, ``event_bus``) so the loop is deterministic under test;
the default ``progress_fn`` polls the substrate HTTP client with the same
``-project action=status`` command the unified substrate uses (REQ-42).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from quantlab.substrate.poller import is_project_completed

logger = logging.getLogger(__name__)

_PROGRESS_RE = re.compile(r"Strategies generated\s+(\d+)")

# Cap the generated-count progress signal below 1.0 so only a real terminal
# status (completed / stopped) maps to completion.
_MAX_PROGRESS_FRACTION = 0.999
_PROGRESS_DENOMINATOR = 1000.0


def extract_progress_fraction(status_text: str) -> float | None:
    """Map SQX status text to a 0..1 progress signal.

    A terminal status text (completed / ``Project execution stopped``) maps
    to ``1.0``. A ``Strategies generated N`` count maps to ``N/1000`` capped
    below ``1.0``. Any other text (no measurable progress) maps to ``None`` —
    the caller treats it as "unchanged" for stall accounting.
    """
    if is_project_completed(status_text):
        return 1.0
    match = _PROGRESS_RE.search(status_text)
    if match is None:
        return None
    return min(int(match.group(1)) / _PROGRESS_DENOMINATOR, _MAX_PROGRESS_FRACTION)


class MonitorStatus(str, Enum):
    """Terminal outcome of a monitoring run."""

    CONTINUE = "CONTINUE"
    HOLD = "HOLD"


@dataclass
class MonitorResult:
    """Outcome of :meth:`ExecutionMonitor.monitor`."""

    status: MonitorStatus
    campaign_id: str
    phase: str
    events: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: dict[str, Any] | None = None
    checkpoint_written: bool = False
    message: str = ""


def _phase_name(phase: Any) -> str:
    return phase.value if hasattr(phase, "value") else str(phase)


class ExecutionMonitor:
    """Long-poll with stall detection, checkpoint-before-diagnostics, HOLD.

    Args:
        client: Duck-typed substrate client (``async send_command``). Used by
            the default ``progress_fn`` when none is injected.
        progress_fn: ``() -> (alive, progress)`` — ``alive=False`` means the
            daemon is unreachable (HOLD); ``progress >= 1.0`` means completed;
            ``progress=None`` means no measurable progress (treated as
            unchanged). Defaults to status-text polling via ``client``.
        checkpoint_writer: ``() -> None`` invoked BEFORE diagnostics on stall.
        diagnostics_fn: ``(ctx) -> remediation dict | None`` run with a
            ``llm_timeout`` budget on stall. ``None`` result → HOLD.
        event_bus: Synchronous ``(event dict) -> None`` hook receiving every
            emitted event (campaign event bus, REQ-42).
        poll_interval: Seconds between status polls (default 30s).
        expected_duration: Expected phase duration; the stall threshold is
            ``stall_multiplier * expected_duration`` (default 2x).
        llm_timeout: LLM diagnostics budget in seconds (default 60s).
        now_fn: Monotonic clock injector (deterministic tests).
    """

    def __init__(
        self,
        *,
        client: Any | None = None,
        progress_fn: Callable[[], Awaitable[tuple[bool, float | None]]] | None = None,
        checkpoint_writer: Callable[[], Awaitable[None]] | None = None,
        diagnostics_fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]] | None = None,
        event_bus: Callable[[dict[str, Any]], None] | None = None,
        poll_interval: float = 30.0,
        expected_duration: float = 180.0,
        stall_multiplier: float = 2.0,
        llm_timeout: float = 60.0,
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        self._client = client
        if progress_fn is not None:
            # Injected progress sources are zero-arg closures; the monitor
            # calls its internal source with (client, campaign_id).
            self._progress_fn = lambda _client, _campaign: progress_fn()
        else:
            self._progress_fn = self._default_progress
        self._checkpoint_writer = checkpoint_writer
        self._diagnostics_fn = diagnostics_fn
        self._event_bus = event_bus
        self._poll_interval = poll_interval
        self._expected_duration = expected_duration
        self._stall_multiplier = stall_multiplier
        self._llm_timeout = llm_timeout
        self._now = now_fn or time.monotonic

    # ── Public contract ───────────────────────────────────────────────────────

    async def monitor(
        self,
        campaign_id: str,
        phase: Any,
        config: Any | None = None,
    ) -> MonitorResult:
        """Long-poll *campaign_id* until completion, stall, or daemon loss.

        On stall: writes a checkpoint (if configured), then invokes LLM
        diagnostics within ``llm_timeout``. Diagnostics timeout / failure /
        missing provider / no remediation → ``HOLD`` (fail-closed). Successful
        remediation → ``CONTINUE`` with ``diagnostics`` attached. Phase
        completion → ``CONTINUE``.
        """
        client = self._client
        if client is None and config is not None:
            client = getattr(config, "http_client", None)

        events: list[dict[str, Any]] = []
        threshold = self._expected_duration * self._stall_multiplier
        last_progress: float | None = None
        last_change_at = self._now()

        while True:
            alive, progress = await self._progress_fn(client, campaign_id)
            now_t = self._now()

            if not alive:
                self._emit(
                    events,
                    {
                        "event_type": "daemon_lost",
                        "campaign_id": campaign_id,
                        "phase": _phase_name(phase),
                        "severity": "CRITICAL",
                    },
                )
                return MonitorResult(
                    status=MonitorStatus.HOLD,
                    campaign_id=campaign_id,
                    phase=_phase_name(phase),
                    events=events,
                    message="SQX daemon unreachable — HOLD for human review",
                )

            if progress is not None and progress >= 1.0:
                self._emit(
                    events,
                    {
                        "event_type": "campaign_complete",
                        "campaign_id": campaign_id,
                        "phase": _phase_name(phase),
                        "severity": "INFO",
                    },
                )
                return MonitorResult(
                    status=MonitorStatus.CONTINUE,
                    campaign_id=campaign_id,
                    phase=_phase_name(phase),
                    events=events,
                    message=f"{_phase_name(phase)} completed",
                )

            # No measurable progress → keep the last signal for stall accounting.
            if progress is None:
                progress = last_progress

            if last_progress is not None and progress == last_progress:
                stalled_for = now_t - last_change_at
                if stalled_for >= threshold:
                    return await self._resolve_stall(
                        campaign_id,
                        phase,
                        progress,
                        stalled_for,
                        threshold,
                        events,
                    )
            else:
                last_progress = progress
                last_change_at = now_t

            await asyncio.sleep(self._poll_interval)

    # ── Stall resolution ──────────────────────────────────────────────────────

    async def _resolve_stall(
        self,
        campaign_id: str,
        phase: Any,
        progress: float | None,
        stalled_for: float,
        threshold: float,
        events: list[dict[str, Any]],
    ) -> MonitorResult:
        """Write checkpoint, then run LLM diagnostics; HOLD on failure."""
        phase_text = _phase_name(phase)
        self._emit(
            events,
            {
                "event_type": "stall",
                "campaign_id": campaign_id,
                "phase": phase_text,
                "severity": "WARNING",
                "stalled_for": stalled_for,
                "threshold": threshold,
            },
        )

        checkpoint_written = False
        if self._checkpoint_writer is not None:
            await self._checkpoint_writer()
            checkpoint_written = True

        if self._diagnostics_fn is None:
            return MonitorResult(
                status=MonitorStatus.HOLD,
                campaign_id=campaign_id,
                phase=phase_text,
                events=events,
                checkpoint_written=checkpoint_written,
                message=(
                    "stall detected but no diagnostics provider configured "
                    "— HOLD for human review"
                ),
            )

        diagnostics: dict[str, Any] | None = None
        context = {
            "campaign_id": campaign_id,
            "phase": phase_text,
            "progress": progress,
            "events": list(events),
        }
        try:
            diagnostics = await asyncio.wait_for(
                self._diagnostics_fn(context), timeout=self._llm_timeout
            )
        except asyncio.TimeoutError:
            self._emit(
                events,
                {
                    "event_type": "diagnostics_timeout",
                    "campaign_id": campaign_id,
                    "phase": phase_text,
                    "severity": "CRITICAL",
                },
            )
            return MonitorResult(
                status=MonitorStatus.HOLD,
                campaign_id=campaign_id,
                phase=phase_text,
                events=events,
                checkpoint_written=checkpoint_written,
                message=(
                    f"LLM diagnostics exceeded {self._llm_timeout:.0f}s "
                    "— HOLD for human review"
                ),
            )
        except Exception as exc:  # pragma: no cover - defensive fail-closed
            logger.warning("LLM diagnostics failed for %s: %s", campaign_id, exc)
            self._emit(
                events,
                {
                    "event_type": "diagnostics_error",
                    "campaign_id": campaign_id,
                    "phase": phase_text,
                    "severity": "CRITICAL",
                },
            )
            return MonitorResult(
                status=MonitorStatus.HOLD,
                campaign_id=campaign_id,
                phase=phase_text,
                events=events,
                checkpoint_written=checkpoint_written,
                message="LLM diagnostics failed — HOLD for human review",
            )

        if diagnostics:
            self._emit(
                events,
                {
                    "event_type": "remediation",
                    "campaign_id": campaign_id,
                    "phase": phase_text,
                    "severity": "INFO",
                },
            )
            return MonitorResult(
                status=MonitorStatus.CONTINUE,
                campaign_id=campaign_id,
                phase=phase_text,
                events=events,
                diagnostics=diagnostics,
                checkpoint_written=checkpoint_written,
                message="stall resolved with LLM remediation",
            )

        return MonitorResult(
            status=MonitorStatus.HOLD,
            campaign_id=campaign_id,
            phase=phase_text,
            events=events,
            checkpoint_written=checkpoint_written,
            message="no remediation proposed — HOLD for human review",
        )

    # ── Defaults / helpers ────────────────────────────────────────────────────

    async def _default_progress(
        self, client: Any, campaign_id: str
    ) -> tuple[bool, float | None]:
        """Poll ``-project action=status`` and derive (alive, progress)."""
        if client is None:
            return False, None
        try:
            text = await client.send_command(
                f"-project action=status name={campaign_id}"
            )
        except Exception:
            return False, None
        return True, extract_progress_fraction(text)

    def _emit(self, events: list[dict[str, Any]], event: dict[str, Any]) -> None:
        events.append(event)
        if self._event_bus is not None:
            try:
                self._event_bus(event)
            except Exception:  # pragma: no cover - bus must not break monitoring
                logger.warning("event bus rejected event %s", event.get("event_type"))
