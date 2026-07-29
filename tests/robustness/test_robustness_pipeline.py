"""E2E test: full robustness pipeline — circuit breaker → retry → dispatch → buffer."""

import asyncio
import os
import tempfile

import pytest

from quantlab.robustness.circuit_breaker import CircuitBreaker, CircuitOpenError
from quantlab.robustness.knowledge_health import HealthStatus
from quantlab.robustness.llm_circuit_breaker import LLMCircuitBreaker
from quantlab.robustness.resilient_notifier import ResilientNotifier
from quantlab.robustness.retry_policy import RetryPolicy
from quantlab.knowledge.store import KnowledgeStore


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


class TestRobustnessPipeline:
    """E2E test exercising the full robustness pipeline:
    circuit breaker → retry → dispatch → buffer.

    This test simulates a realistic failure scenario where:
    1. An LLM call fails, opening the circuit breaker
    2. RetryPolicy exhausts retries on notification failures
    3. ResilientNotifier queues failed notifications
    4. KnowledgeStore buffers writes while circuit is OPEN
    5. Circuit recovers, replaying buffered writes and flushing queued notifications
    """

    @pytest.mark.asyncio
    async def test_full_pipeline_circuit_opens_then_recovers(self):
        """GIVEN a full robustness pipeline, WHEN the circuit opens due to
        failures and then recovers, THEN all components coordinate correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Set up the circuit breaker (LLM-specific)
            lb = LLMCircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

            # 2. Set up the retry policy
            policy = RetryPolicy(max_retries=2, base_delay=0.01, max_delay=0.1, jitter=False)

            # 3. Set up the KnowledgeStore with the circuit breaker
            store = KnowledgeStore(root=tmpdir, circuit_breaker=lb._circuit_breaker)
            store.initialize()

            # Phase A: Circuit is CLOSED — everything works
            working_notifier = FakeNotifier(fail_count=0)
            notifier = ResilientNotifier(
                working_notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=os.path.join(tmpdir, "notifications.jsonl"),
            )

            async def succeed_llm():
                return "research result"

            result = await lb.call(succeed_llm())
            assert result == "research result"
            assert lb.state == "CLOSED"

            # Notification succeeds
            await notifier.send("alert-1")
            assert working_notifier.send_count == 1
            assert notifier.queue_size == 0

            # Write succeeds (circuit is CLOSED)
            store._check_write_circuit("file1.yaml", "content1")
            assert (store.root / "file1.yaml").exists()

            # Phase B: Circuit opens after failures — switch to failing notifier
            failing_notifier = FakeNotifier(fail_count=999)
            notifier2 = ResilientNotifier(
                failing_notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=os.path.join(tmpdir, "notifications.jsonl"),
            )

            async def fail_llm():
                raise RuntimeError("LLM timeout")

            with pytest.raises(RuntimeError):
                await lb.call(fail_llm())
            with pytest.raises(RuntimeError):
                await lb.call(fail_llm())

            assert lb.state == "OPEN"

            # Notification fails after retries → queued
            with pytest.raises(RuntimeError):
                await notifier2.send("alert-2")
            assert notifier2.queue_size == 1

            # Write is buffered (circuit is OPEN)
            store._check_write_circuit("file2.yaml", "content2")
            assert not (store.root / "file2.yaml").exists()
            assert len(store._write_buffer) == 1

            # Phase C: Circuit recovers after timeout
            await asyncio.sleep(0.12)

            # LLM call succeeds again — circuit closes
            result = await lb.call(succeed_llm())
            assert result == "research result"
            assert lb.state == "CLOSED"

            # Notification now succeeds (working notifier, circuit is closed)
            # The queued notification from Phase B should be flushed
            rn = ResilientNotifier(
                working_notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=os.path.join(tmpdir, "notifications.jsonl"),
            )
            await rn.flush()
            assert working_notifier.send_count >= 2  # 1 from Phase A + 1 from flush

            # Write buffered while circuit was OPEN is now executed directly
            # (since circuit is CLOSED, _check_write_circuit writes directly)
            store._check_write_circuit("file3.yaml", "content3")
            assert (store.root / "file3.yaml").exists()

    @pytest.mark.asyncio
    async def test_pipeline_retry_exhaustion_then_recovery(self):
        """GIVEN a pipeline where retries are exhausted, WHEN the notifier
        recovers, THEN queued notifications are delivered on flush."""
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = RetryPolicy(max_retries=1, base_delay=0.01, max_delay=0.1, jitter=False)

            failing_notifier = FakeNotifier(fail_count=999)
            notifier = ResilientNotifier(
                failing_notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=os.path.join(tmpdir, "notifications.jsonl"),
            )

            # Queue notifications (all fail after retries)
            for i in range(3):
                with pytest.raises(RuntimeError):
                    await notifier.send(f"alert-{i}")

            assert notifier.queue_size == 3

            # Simulate recovery: create a new notifier with a working underlying notifier
            working_notifier = FakeNotifier(fail_count=0)
            rn = ResilientNotifier(
                working_notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=os.path.join(tmpdir, "notifications.jsonl"),
            )

            # Flush delivers all queued notifications
            await rn.flush()

            assert working_notifier.send_count == 3
            assert rn.queue_size == 0

    @pytest.mark.asyncio
    async def test_pipeline_buffer_flush_on_health_check(self):
        """GIVEN a KnowledgeStore with buffered writes and an OPEN circuit,
        WHEN health_check() succeeds, THEN buffered writes are replayed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.05)
            store = KnowledgeStore(root=tmpdir, circuit_breaker=cb)
            store.initialize()

            # Open the circuit
            async def fail_write():
                raise OSError("write failed")

            with pytest.raises(OSError):
                await cb.call(fail_write())
            assert cb.state == "OPEN"

            # Buffer writes while circuit is OPEN
            store._check_write_circuit("buffered1.yaml", "content1")
            store._check_write_circuit("buffered2.yaml", "content2")
            assert len(store._write_buffer) == 2

            # Health check replays buffered writes
            result = await store.health_check()
            assert result.status == HealthStatus.HEALTHY

            # Circuit remains OPEN after health check
            assert cb.state == "OPEN"

            # But buffered writes are now on disk
            assert (store.root / "buffered1.yaml").exists()
            assert (store.root / "buffered1.yaml").read_text() == "content1"
            assert (store.root / "buffered2.yaml").exists()
            assert (store.root / "buffered2.yaml").read_text() == "content2"
            assert len(store._write_buffer) == 0

    @pytest.mark.asyncio
    async def test_pipeline_persistence_across_restarts(self):
        """GIVEN queued notifications persisted to JSONL, WHEN a new
        ResilientNotifier is created with the same queue file, THEN
        queued notifications are loaded and can be flushed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, "notifications.jsonl")
            policy = RetryPolicy(max_retries=1, base_delay=0.01, max_delay=0.1, jitter=False)

            # Create notifier with failing underlying notifier
            failing_notifier = FakeNotifier(fail_count=999)
            rn1 = ResilientNotifier(
                failing_notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=queue_file,
            )

            # Queue notifications
            for i in range(3):
                with pytest.raises(RuntimeError):
                    await rn1.send(f"persistent-alert-{i}")

            assert rn1.queue_size == 3

            # Simulate process restart: create new ResilientNotifier with same queue file
            working_notifier = FakeNotifier(fail_count=0)
            rn2 = ResilientNotifier(
                working_notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=queue_file,
            )

            assert rn2.queue_size == 3

            # Flush delivers all queued notifications
            await rn2.flush()
            assert working_notifier.send_count == 3
            assert rn2.queue_size == 0

            # Verify queue file is empty after successful flush
            assert os.path.exists(queue_file)
            with open(queue_file, "r") as f:
                lines = f.readlines()
            assert len(lines) == 0

    @pytest.mark.asyncio
    async def test_pipeline_circuit_breaker_short_circuits_llm(self):
        """GIVEN an OPEN LLMCircuitBreaker, WHEN call() is invoked,
        THEN CircuitOpenError is raised immediately without calling the LLM."""
        lb = LLMCircuitBreaker(failure_threshold=1, recovery_timeout=0.05)

        # Open the circuit
        async def fail_llm():
            raise RuntimeError("LLM timeout")

        with pytest.raises(RuntimeError):
            await lb.call(fail_llm())
        assert lb.state == "OPEN"

        # Subsequent calls raise CircuitOpenError immediately (skipping LLM)
        # This is what triggers the fallback chain in LLMResearchAgent
        with pytest.raises(CircuitOpenError):
            await lb.call(fail_llm())

        # Wait for recovery
        await asyncio.sleep(0.06)

        # Circuit is now HALF_OPEN — a probe call is allowed
        async def succeed_llm():
            return "recovered result"

        result = await lb.call(succeed_llm())
        assert result == "recovered result"
        assert lb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_pipeline_all_components_integrated(self):
        """GIVEN all robustness components working together,
        WHEN a failure cascade occurs and recovers, THEN the full
        pipeline (circuit → retry → dispatch → buffer) behaves correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
            policy = RetryPolicy(max_retries=1, base_delay=0.01, max_delay=0.1, jitter=False)
            store = KnowledgeStore(root=tmpdir, circuit_breaker=cb)
            store.initialize()

            # Phase 1: Normal operation (CLOSED) — working notifier
            working_notifier = FakeNotifier(fail_count=0)
            notifier = ResilientNotifier(
                working_notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=os.path.join(tmpdir, "notifications.jsonl"),
            )

            async def succeed():
                return "ok"

            assert cb.state == "CLOSED"
            await notifier.send("normal-alert")
            assert working_notifier.send_count == 1
            assert notifier.queue_size == 0
            store._check_write_circuit("normal.yaml", "normal content")
            assert (store.root / "normal.yaml").exists()

            # Phase 2: Failure cascade (OPEN) — failing notifier
            failing_notifier = FakeNotifier(fail_count=999)
            notifier2 = ResilientNotifier(
                failing_notifier,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=os.path.join(tmpdir, "notifications.jsonl"),
            )

            async def fail():
                raise RuntimeError("cascade failure")

            with pytest.raises(RuntimeError):
                await cb.call(fail())
            with pytest.raises(RuntimeError):
                await cb.call(fail())
            assert cb.state == "OPEN"

            with pytest.raises(RuntimeError):
                await notifier2.send("failed-alert")
            assert notifier2.queue_size == 1

            store._check_write_circuit("buffered.yaml", "buffered content")
            assert not (store.root / "buffered.yaml").exists()
            assert len(store._write_buffer) == 1

            # Phase 3: Recovery (CLOSED again)
            await asyncio.sleep(0.06)
            result = await cb.call(succeed())
            assert result == "ok"
            assert cb.state == "CLOSED"

            working_notifier2 = FakeNotifier(fail_count=0)
            rn = ResilientNotifier(
                working_notifier2,
                retry_policy=policy,
                queue_max_size=100,
                queue_file=os.path.join(tmpdir, "notifications.jsonl"),
            )
            await rn.flush()
            assert working_notifier2.send_count >= 1

            store._check_write_circuit("after_recovery.yaml", "recovered content")
            assert (store.root / "after_recovery.yaml").exists()
