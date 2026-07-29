"""Tests for ResilientNotifier — retry, queue eviction, JSONL persistence, flush()."""

import asyncio
import json
import os
import tempfile

import pytest

from quantlab.robustness.resilient_notifier import ResilientNotifier
from quantlab.robustness.retry_policy import RetryPolicy


class FakeNotifier:
    """Test double for Notifier that tracks send calls and can be configured to fail."""

    def __init__(self, fail_count: int = 0, fail_exception: Exception | None = None):
        self.send_count = 0
        self.fail_count = fail_count
        self.fail_exception = fail_exception or RuntimeError("notifier failed")
        self.messages: list[str] = []

    async def send(self, message: str, **kwargs) -> None:
        self.send_count += 1
        self.messages.append(message)
        if self.send_count <= self.fail_count:
            raise self.fail_exception


class TestResilientNotifierRetrySuccess:
    """ResilientNotifier retries failed sends and succeeds on transient recovery."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_after_transient_failures(self):
        """GIVEN a notifier that fails twice then succeeds, WHEN send() is called, THEN alert is delivered on 3rd attempt."""
        notifier = FakeNotifier(fail_count=2)
        policy = RetryPolicy(max_retries=3, base_delay=0.01, max_delay=0.1, jitter=False)
        rn = ResilientNotifier(notifier, retry_policy=policy, queue_max_size=100)

        await rn.send("alert message")

        assert notifier.send_count == 3
        assert "alert message" in notifier.messages

    @pytest.mark.asyncio
    async def test_happy_path_delivers_on_first_attempt(self):
        """GIVEN a working notifier, WHEN send() is called, THEN underlying send() is invoked once."""
        notifier = FakeNotifier(fail_count=0)
        policy = RetryPolicy(max_retries=3, base_delay=0.01, max_delay=0.1, jitter=False)
        rn = ResilientNotifier(notifier, retry_policy=policy, queue_max_size=100)

        await rn.send("alert message")

        assert notifier.send_count == 1
        assert notifier.messages == ["alert message"]


class TestResilientNotifierQueueEviction:
    """ResilientNotifier queues failed notifications and evicts oldest when full."""

    @pytest.mark.asyncio
    async def test_queue_evicts_oldest_when_full(self):
        """GIVEN a queue at max capacity, WHEN a notification fails all retries, THEN oldest is evicted and new failure is appended."""
        notifier = FakeNotifier(fail_count=999)  # always fails
        policy = RetryPolicy(max_retries=1, base_delay=0.01, max_delay=0.1, jitter=False)
        rn = ResilientNotifier(notifier, retry_policy=policy, queue_max_size=3)

        # Fill the queue to capacity
        for i in range(3):
            with pytest.raises(RuntimeError):
                await rn.send(f"message-{i}")

        assert len(rn._queue) == 3

        # Next failure should evict the oldest
        with pytest.raises(RuntimeError):
            await rn.send("message-3")

        assert len(rn._queue) == 3
        # Oldest message-0 should be evicted
        assert rn._queue[0]["message"] == "message-1"
        # New message-3 should be at the end
        assert rn._queue[-1]["message"] == "message-3"


class TestResilientNotifierQueuePersistence:
    """ResilientNotifier persists queued notifications to JSONL file."""

    @pytest.mark.asyncio
    async def test_queue_persists_to_jsonl_and_reloads(self):
        """GIVEN 3 notifications in the persistent queue, WHEN process restarts, THEN 3 notifications are loaded from queue file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, "notifications.jsonl")
            notifier = FakeNotifier(fail_count=999)  # always fails
            policy = RetryPolicy(max_retries=1, base_delay=0.01, max_delay=0.1, jitter=False)
            rn = ResilientNotifier(
                notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=queue_file,
            )

            # Queue 3 notifications
            for i in range(3):
                with pytest.raises(RuntimeError):
                    await rn.send(f"persistent-message-{i}")

            assert len(rn._queue) == 3

            # Simulate process restart: create a new ResilientNotifier with same queue file
            rn2 = ResilientNotifier(
                notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=queue_file,
            )

            assert len(rn2._queue) == 3
            assert rn2._queue[0]["message"] == "persistent-message-0"
            assert rn2._queue[-1]["message"] == "persistent-message-2"


class TestResilientNotifierFlush:
    """ResilientNotifier.flush() retries all queued notifications."""

    @pytest.mark.asyncio
    async def test_flush_delivers_queued_alerts(self):
        """GIVEN 3 notifications in the queue after an outage, WHEN flush() is called, THEN all 3 are retried for delivery."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, "notifications.jsonl")
            notifier = FakeNotifier(fail_count=0)  # always succeeds
            policy = RetryPolicy(max_retries=1, base_delay=0.01, max_delay=0.1, jitter=False)
            rn = ResilientNotifier(
                notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=queue_file,
            )

            # Queue 3 notifications (they fail because notifier is configured to fail)
            failing_notifier = FakeNotifier(fail_count=999)
            rn2 = ResilientNotifier(
                failing_notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=queue_file,
            )

            for i in range(3):
                with pytest.raises(RuntimeError):
                    await rn2.send(f"queued-message-{i}")

            # Now replace with a working notifier and flush
            rn3 = ResilientNotifier(
                notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=queue_file,
            )

            await rn3.flush()

            # All 3 should have been delivered
            assert notifier.send_count == 3
            assert len(notifier.messages) == 3
            # Queue should be empty after successful flush
            assert len(rn3._queue) == 0

    @pytest.mark.asyncio
    async def test_flush_removes_successful_from_queue(self):
        """GIVEN a mix of queued notifications, WHEN flush() is called, THEN successful ones are removed from queue."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, "notifications.jsonl")
            notifier = FakeNotifier(fail_count=0)
            policy = RetryPolicy(max_retries=1, base_delay=0.01, max_delay=0.1, jitter=False)

            # Queue 2 notifications using a failing notifier
            failing_notifier = FakeNotifier(fail_count=999)
            rn = ResilientNotifier(
                failing_notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=queue_file,
            )

            for i in range(2):
                with pytest.raises(RuntimeError):
                    await rn.send(f"queued-{i}")

            # Flush with working notifier
            rn2 = ResilientNotifier(
                notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=queue_file,
            )

            await rn2.flush()

            assert notifier.send_count == 2
            assert len(rn2._queue) == 0


class TestResilientNotifierQueueFullEvictionOrder:
    """ResilientNotifier evicts oldest entries first (FIFO)."""

    @pytest.mark.asyncio
    async def test_eviction_is_fifo(self):
        """GIVEN a queue at capacity, WHEN new failures are added, THEN oldest entries are evicted first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, "notifications.jsonl")
            notifier = FakeNotifier(fail_count=999)
            policy = RetryPolicy(max_retries=1, base_delay=0.01, max_delay=0.1, jitter=False)
            rn = ResilientNotifier(
                notifier,
                retry_policy=policy,
                queue_max_size=2,
                queue_file=queue_file,
            )

            # Fill queue
            for i in range(2):
                with pytest.raises(RuntimeError):
                    await rn.send(f"msg-{i}")

            assert len(rn._queue) == 2
            assert rn._queue[0]["message"] == "msg-0"
            assert rn._queue[1]["message"] == "msg-1"

            # Add one more — should evict msg-0
            with pytest.raises(RuntimeError):
                await rn.send("msg-2")

            assert len(rn._queue) == 2
            assert rn._queue[0]["message"] == "msg-1"
            assert rn._queue[1]["message"] == "msg-2"

            # Add one more — should evict msg-1
            with pytest.raises(RuntimeError):
                await rn.send("msg-3")

            assert len(rn._queue) == 2
            assert rn._queue[0]["message"] == "msg-2"
            assert rn._queue[1]["message"] == "msg-3"
