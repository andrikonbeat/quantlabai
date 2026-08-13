"""JForex4 live feed — reads equity and order streams from local filesystem."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Iterable, List

from quantlab.jforex.models import OrderEvent
from quantlab.readers.models import EquityPoint

#: Monotonic progress signal when the feed has at least one equity point.
_ALIVE_PROGRESS = 0.5


def jforex_progress_fn(
    feed: "JForexLiveFeed | None" = None,
    *,
    poll_equity_count: int | None = None,
) -> Callable[[], Awaitable[tuple[bool, float | None]]]:
    """Build an ExecutionMonitor-compatible progress source from a live feed.

    REQ-06 Scenario 2: ``ExecutionMonitor`` polls progress and uses
    ``JForexLiveFeed`` instead of the SQX HTTP status. This factory returns a
    zero-arg ``() -> (alive, progress)`` coroutine that reads the feed's
    equity stream: a missing/unusable feed yields ``(False, None)`` (daemon
    lost); an empty equity stream yields ``(True, None)`` (alive, no
    measurable progress); at least one equity point yields
    ``(True, 0.5)`` (alive with measurable — but never terminal — progress).

    Args:
        feed: The live feed to poll. ``None`` is allowed and always yields
            ``(False, None)`` (fail closed).
        poll_equity_count: Optional stub hook for deterministic tests —
            when provided, the number of equity points is read from this
            callable instead of ``feed.read_equity()``.

    Returns:
        A zero-arg async callback usable as ``ExecutionMonitor(progress_fn=...)``.
    """

    async def _progress() -> tuple[bool, float | None]:
        if feed is None:
            return False, None
        try:
            if poll_equity_count is not None:
                count = poll_equity_count()
            else:
                count = len(feed.read_equity())
        except Exception:  # noqa: BLE001 - fail-closed on any feed error
            return False, None
        if count <= 0:
            return True, None
        return True, _ALIVE_PROGRESS

    return _progress


class JForexLiveFeed:
    """Live feed that reads JForex4 state from the local filesystem.

    JForex4 writes account equity and order events to a local state
    directory. This feed reads those files and exposes them as structured
    Python objects consumed by :class:`quantlab.guardian.live.LiveEvaluation`.

    Attributes:
        state_dir: Path to the JForex4 local state directory.
    """

    def __init__(self, state_dir: Path | None = None) -> None:
        self.state_dir = Path(state_dir) if state_dir else None

    # ── Public API ────────────────────────────────────────────────────────────

    def read_equity(self) -> List[EquityPoint]:
        """Return the equity curve from local state.

        Reads ``equity.json`` from the state directory and parses each
        entry into an :class:`quantlab.readers.models.EquityPoint`.

        Returns:
            A list of equity points in timestamp order. Returns an empty
            list when the state directory or file is missing/malformed.
        """
        return self._parse_equity(self._read_json("equity.json"))

    def read_orders(self) -> List[OrderEvent]:
        """Return the order event stream from local state.

        Reads ``orders.json`` from the state directory and parses each
        entry into an :class:`quantlab.jforex.models.OrderEvent`.

        Returns:
            A list of order events. Returns an empty list when the state
            directory or file is missing/malformed.
        """
        return self._parse_orders(self._read_json("orders.json"))

    def __iter__(self) -> Iterable[EquityPoint]:
        """Iterate over equity points (enables ``list(feed)``)."""
        return iter(self.read_equity())

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _read_json(self, filename: str) -> list[dict]:
        """Read a JSON array from *filename* inside the state directory.

        Returns an empty list when the directory/file is missing or the
        JSON cannot be decoded.
        """
        if self.state_dir is None:
            return []
        path = self.state_dir / filename
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return []
            return data
        except (json.JSONDecodeError, OSError):
            return []

    @staticmethod
    def _parse_equity(raw: list[dict]) -> List[EquityPoint]:
        """Convert raw JSON dicts to EquityPoint objects."""
        points: List[EquityPoint] = []
        for item in raw:
            try:
                ts = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
                points.append(EquityPoint(timestamp=ts, equity=float(item["equity"])))
            except (KeyError, ValueError, TypeError):
                continue
        return points

    @staticmethod
    def _parse_orders(raw: list[dict]) -> List[OrderEvent]:
        """Convert raw JSON dicts to OrderEvent objects."""
        events: List[OrderEvent] = []
        for item in raw:
            try:
                events.append(OrderEvent(**item))
            except (ValueError, TypeError):
                continue
        return events
