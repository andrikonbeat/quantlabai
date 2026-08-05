"""Substrate status polling (REQ-26) — interval/timeout from phase config.

Completion detection is kept in a pure function (:func:`is_project_completed`)
with parity to the legacy ``cli_wrapper._is_completed`` plus the explicit
``Project execution stopped`` terminal signal used by both legacy paths.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

_COMPLETION_TERMS = ("completed", "finished", "done", "success")


@dataclass
class PollResult:
    """Outcome of a poll-until-done loop."""

    completed: bool
    status_text: str
    polls: int


def is_project_completed(status_text: str | None) -> bool:
    """Return whether an SQX status response is terminal.

    Terminal when the text carries the explicit stop signal or any of the
    completion keywords — parity with the legacy dispatch paths.
    """
    if not status_text:
        return False
    if "Project execution stopped" in status_text:
        return True
    text = status_text.lower()
    return any(term in text for term in _COMPLETION_TERMS)


async def poll_until_done(
    client: Any,
    campaign_id: str,
    *,
    poll_interval: float = 1.0,
    timeout: float = 30.0,
    on_poll: Callable[[str], Awaitable[None]] | None = None,
) -> PollResult:
    """Poll ``-project action=status`` until completion or timeout.

    Args:
        client: An object with ``async send_command(command) -> str``
            (``AsyncSQXClient`` or a test recording double).
        campaign_id: Project/campaign name to poll.
        poll_interval: Seconds between polls.
        timeout: Maximum wall-clock seconds to poll.
        on_poll: Optional async hook invoked with every status text (used by
            the substrate to feed event detection, REQ-42).

    Returns:
        A :class:`PollResult` with the terminal flag and last status text.
    """
    deadline = time.monotonic() + timeout
    status_text = ""
    polls = 0
    while time.monotonic() < deadline:
        status_text = await client.send_command(
            f"-project action=status name={campaign_id}"
        )
        polls += 1
        if on_poll is not None:
            await on_poll(status_text)
        if is_project_completed(status_text):
            return PollResult(completed=True, status_text=status_text, polls=polls)
        await asyncio.sleep(poll_interval)

    logger.warning(
        "Substrate poll for '%s' timed out after %.0fs (%d polls)",
        campaign_id, timeout, polls,
    )
    return PollResult(completed=False, status_text=status_text, polls=polls)
