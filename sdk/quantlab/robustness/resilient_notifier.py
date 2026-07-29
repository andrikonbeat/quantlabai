"""ResilientNotifier — wraps any Notifier with retry and bounded JSONL queue."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from quantlab.robustness.retry_policy import RetryPolicy

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_MAX_SIZE = 1000
DEFAULT_QUEUE_FILE = "notifications.jsonl"


class ResilientNotifier:
    """Wraps any Notifier with retry logic and a bounded JSONL queue for failed notifications.

    On send(), the underlying Notifier is called through a RetryPolicy.
    If all retries are exhausted, the notification is enqueued in a bounded
    in-memory queue persisted to a JSONL file.  Oldest entries are evicted
    when the queue reaches its max size.  Call flush() to retry all queued
    notifications.

    Parameters
    ----------
    notifier: Notifier
        The underlying notification adapter to wrap.
    retry_policy: RetryPolicy, optional
        Retry policy used for each send attempt.  Defaults to a fresh
        RetryPolicy() (max_retries=3, base_delay=1s, max_delay=60s, jitter=True).
    queue_max_size: int, optional
        Maximum number of notifications held in the queue.  Default is 1000.
    queue_file: str or Path, optional
        Path to the JSONL file used for persistent queue storage.
        Default is "notifications.jsonl" in the current working directory.
    """

    def __init__(
        self,
        notifier: Any,
        retry_policy: RetryPolicy | None = None,
        queue_max_size: int = DEFAULT_QUEUE_MAX_SIZE,
        queue_file: str | os.PathLike = DEFAULT_QUEUE_FILE,
    ) -> None:
        self._notifier = notifier
        self._retry_policy = retry_policy or RetryPolicy()
        self._queue_max_size = queue_max_size
        self._queue_file = os.fspath(queue_file)
        self._queue: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

        # Load any persisted notifications from the queue file
        self._load_queue()

    # ── Queue Persistence ──────────────────────────────────────────────────

    def _load_queue(self) -> None:
        """Load queued notifications from the JSONL persistence file."""
        if not os.path.exists(self._queue_file):
            return
        try:
            with open(self._queue_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._queue.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            logger.warning("Failed to load queue from %s, starting empty", self._queue_file)
            self._queue = []

    async def _persist_queue(self) -> None:
        """Write the current queue to the JSONL persistence file."""
        try:
            with open(self._queue_file, "w", encoding="utf-8") as f:
                for entry in self._queue:
                    f.write(json.dumps(entry) + "\n")
        except OSError:
            logger.warning("Failed to persist queue to %s", self._queue_file)

    # ── Send ────────────────────────────────────────────────────────────────

    async def send(self, message: str, **kwargs: Any) -> None:
        """Send a notification through the underlying Notifier with retry.

        If all retries are exhausted, the notification is enqueued in the
        bounded JSONL queue for later delivery via flush(), and the
        last exception is re-raised so the caller knows delivery failed.

        Parameters
        ----------
        message: str
            The notification message body.
        **kwargs: Any
            Extra payload fields passed to the underlying Notifier.

        Raises
        ------
        Exception
            The last exception from the underlying Notifier after
            all retries are exhausted.
        """
        try:
            await self._retry_policy.retry(
                lambda: self._notifier.send(message, **kwargs)
            )
        except Exception:
            await self._enqueue(message, **kwargs)
            raise

    async def _enqueue(self, message: str, **kwargs: Any) -> None:
        """Enqueue a failed notification, evicting oldest if queue is full."""
        async with self._lock:
            if len(self._queue) >= self._queue_max_size:
                self._queue.pop(0)
            self._queue.append({"message": message, "kwargs": kwargs})
            await self._persist_queue()

    # ── Flush ──────────────────────────────────────────────────────────────

    async def flush(self) -> None:
        """Retry all queued notifications.  Successful deliveries are removed."""
        async with self._lock:
            queue = self._queue[:]
            self._queue.clear()
            await self._persist_queue()

        for entry in queue:
            try:
                await self._retry_policy.retry(
                    lambda: self._notifier.send(
                        entry["message"], **(entry.get("kwargs") or {})
                    )
                )
            except Exception:
                async with self._lock:
                    self._queue.append(entry)
                    await self._persist_queue()

    @property
    def queue_size(self) -> int:
        """Current number of notifications waiting in the queue."""
        return len(self._queue)
