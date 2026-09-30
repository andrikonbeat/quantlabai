"""CorrectionBus — unidirectional guardian → builder correction fan-out.

The bus decouples the MetaGuardian governance layer from the builder: the
guardian layer publishes corrections, downstream consumers subscribe. Design
decision: an ``asyncio.Queue`` fan-out (1 publisher, N subscribers) with a
one-pipeline-tick delivery guarantee — a published event is delivered to every
current subscriber within one event-loop tick.

``event_type`` validation lives on the bus, not on the model: the bus is the
fan-out boundary, so a malformed correction is rejected there instead of
silently entering the queue.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Final
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

#: Closed set of correction types the governance layer may emit.
CORRECTION_EVENT_TYPES: Final[tuple[str, ...]] = (
    "risk_delta",
    "state_transition",
    "capital_adjustment",
)

CorrectionHandler = Callable[["CorrectionEvent"], None]


class CorrectionBusError(Exception):
    """Raised when an envelope cannot enter the correction fan-out.

    Covers an unknown ``event_type`` and a saturated queue. The bus fails
    closed: a rejected correction is never delivered.

    Attributes:
        event_type: The offending event type, when the failure is a type
            rejection.
        event_id: Identifier of the rejected envelope, when available.
    """

    def __init__(
        self,
        message: str,
        event_type: str | None = None,
        event_id: UUID | None = None,
    ) -> None:
        super().__init__(message)
        self.event_type = event_type
        self.event_id = event_id


class CorrectionEvent(BaseModel):
    """A single correction emitted by the guardian governance layer.

    Attributes:
        event_id: Unique identifier for the envelope.
        timestamp: Emission time.
        source: Emitting component, e.g. ``"MetaGuardianOrchestrator"``.
        event_type: One of :data:`CORRECTION_EVENT_TYPES`. Validated by
            :meth:`CorrectionBus.publish`, not by the model.
        payload: Event-type-specific body.
        correlation_id: Optional link to a related envelope or campaign phase.
    """

    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.now)
    source: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class CorrectionBus:
    """Single-publisher / multi-subscriber correction fan-out.

    ``publish()`` validates the envelope and enqueues it; a drain task
    dispatches every queued envelope to the current subscribers in publication
    order. Use :meth:`flush` to await delivery deterministically.

    Usage::

        bus = CorrectionBus()
        unsubscribe = bus.subscribe(handler)
        bus.publish(CorrectionEvent(source="orchestrator",
                                    event_type="state_transition",
                                    payload={"to": "DEFENSIVE"}))
        await bus.flush()
    """

    def __init__(self, max_queue_size: int = 0) -> None:
        """Initialize the bus.

        Args:
            max_queue_size: Maximum queued envelopes. ``0`` (default) is
                unbounded, which is the production setting. A positive value
                makes saturation a :class:`CorrectionBusError` instead of an
                unbounded stall.
        """
        self._subscribers: list[CorrectionHandler] = []
        self._queue: asyncio.Queue[CorrectionEvent] = asyncio.Queue(
            maxsize=max_queue_size
        )
        self._drain_task: asyncio.Task[None] | None = None
        self._max_queue_size = max_queue_size

    # ── Introspection ───────────────────────────────────────────────────────────

    @property
    def max_queue_size(self) -> int:
        """Configured queue bound (``0`` means unbounded)."""
        return self._max_queue_size

    @property
    def subscriber_count(self) -> int:
        """Number of currently attached subscribers."""
        return len(self._subscribers)

    @property
    def pending_count(self) -> int:
        """Number of envelopes awaiting delivery."""
        return self._queue.qsize()

    # ── Publish / Subscribe ─────────────────────────────────────────────────────

    def publish(self, event: CorrectionEvent) -> None:
        """Validate and enqueue a correction for delivery.

        Args:
            event: The correction envelope to publish.

        Raises:
            CorrectionBusError: If ``event.event_type`` is not in
                :data:`CORRECTION_EVENT_TYPES`, or if a bounded queue is full.
        """
        if event.event_type not in CORRECTION_EVENT_TYPES:
            raise CorrectionBusError(
                f"Unknown correction event_type {event.event_type!r}; "
                f"allowed: {', '.join(CORRECTION_EVENT_TYPES)}",
                event_type=event.event_type,
                event_id=event.event_id,
            )

        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull as exc:
            raise CorrectionBusError(
                f"Correction queue is full (max_queue_size="
                f"{self._max_queue_size}); event {event.event_id} rejected",
                event_type=event.event_type,
                event_id=event.event_id,
            ) from exc

        self._ensure_drain_scheduled()

    def subscribe(self, handler: CorrectionHandler) -> Callable[[], None]:
        """Attach a handler to the fan-out.

        Args:
            handler: Callable invoked once per delivered envelope.

        Returns:
            A zero-argument callable that detaches ``handler``. Calling it
            more than once is a no-op.
        """

        def _unsubscribe() -> None:
            try:
                self._subscribers.remove(handler)
            except ValueError:
                pass

        self._subscribers.append(handler)
        return _unsubscribe

    # ── Delivery ────────────────────────────────────────────────────────────────

    async def flush(self) -> int:
        """Deliver every queued envelope and return how many were dispatched.

        Awaiting this is the deterministic delivery point: on return the queue
        is empty and all subscribers have been invoked.

        Returns:
            Number of envelopes dispatched by this call.
        """
        self._ensure_drain_scheduled()
        if self._drain_task is None:
            return 0
        return await asyncio.gather(self._drain_task)

    def _ensure_drain_scheduled(self) -> None:
        """Schedule the drain task on the running loop, if not already running.

        Without a running loop (sync callers, e.g. tests) delivery is deferred
        to the next :meth:`flush`.
        """
        if self._drain_task is not None and not self._drain_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._drain_task = loop.create_task(self._drain())

    async def _drain(self) -> int:
        """Dispatch queued envelopes until the queue is empty.

        Returns:
            Number of envelopes dispatched.
        """
        dispatched = 0
        while True:
            try:
                event = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                return dispatched
            self._dispatch(event)
            dispatched += 1

    def _dispatch(self, event: CorrectionEvent) -> None:
        """Invoke every current subscriber with ``event``.

        A raising subscriber is logged and skipped: one defective consumer
        must not starve the rest of the fan-out.
        """
        for handler in list(self._subscribers):
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Correction subscriber failed for event %s (%s)",
                    event.event_id,
                    event.event_type,
                )
