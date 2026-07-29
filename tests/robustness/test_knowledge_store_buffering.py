"""Tests for KnowledgeStore write buffering when circuit breaker is OPEN."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from quantlab.robustness.circuit_breaker import CircuitBreaker, CircuitOpenError
from quantlab.knowledge.store import KnowledgeStore


class TestKnowledgeStoreCircuitBreaker:
    """KnowledgeStore integrates CircuitBreaker for write protection."""

    @pytest.mark.asyncio
    async def test_store_has_circuit_breaker(self):
        """GIVEN a KnowledgeStore, WHEN created, THEN it has a CircuitBreaker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=tmpdir)
            assert store._circuit_breaker is not None
            assert isinstance(store._circuit_breaker, CircuitBreaker)

    @pytest.mark.asyncio
    async def test_store_accepts_custom_circuit_breaker(self):
        """GIVEN a custom CircuitBreaker, WHEN passed to KnowledgeStore, THEN it is used."""
        custom_cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.5)
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=tmpdir, circuit_breaker=custom_cb)
            assert store._circuit_breaker is custom_cb


class TestKnowledgeStoreWriteBuffering:
    """KnowledgeStore buffers writes when circuit breaker is OPEN."""

    @pytest.mark.asyncio
    async def test_write_buffered_when_circuit_open(self):
        """GIVEN an OPEN circuit breaker, WHEN a write is attempted via _check_write_circuit,
        THEN the write is buffered instead of executed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.5)
            store = KnowledgeStore(root=tmpdir, circuit_breaker=cb)
            store.initialize()

            # Open the circuit
            async def fail_write():
                raise OSError("write failed")

            with pytest.raises(OSError):
                await cb.call(fail_write())
            assert cb.state == "OPEN"

            # Attempt a write while circuit is OPEN — should be buffered
            store._check_write_circuit("test.yaml", "content")

            # The write should be in the buffer, not on disk
            assert len(store._write_buffer) == 1
            assert store._write_buffer[0]["path"] == "test.yaml"
            assert store._write_buffer[0]["content"] == "content"

            # The file should NOT exist on disk yet
            assert not (store.root / "test.yaml").exists()

    @pytest.mark.asyncio
    async def test_buffered_write_replayed_when_circuit_closes(self):
        """GIVEN a buffered write and a CLOSED circuit, WHEN replay occurs,
        THEN the buffered write is executed to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.05)
            store = KnowledgeStore(root=tmpdir, circuit_breaker=cb)
            store.initialize()

            # Open the circuit by forcing a failure
            async def fail_write():
                raise OSError("write failed")

            with pytest.raises(OSError):
                await cb.call(fail_write())
            assert cb.state == "OPEN"

            # Buffer a write while circuit is OPEN
            store._check_write_circuit("buffered.yaml", "buffered content")
            assert len(store._write_buffer) == 1
            assert not (store.root / "buffered.yaml").exists()

            # Wait for recovery timeout
            await asyncio.sleep(0.06)

            # Circuit should now be HALF_OPEN, then CLOSED on success
            async def succeed_write():
                return "ok"

            result = await cb.call(succeed_write())
            assert result == "ok"
            assert cb.state == "CLOSED"

            # Replay buffered writes
            store._replay_buffer()

            # The buffered write should now be on disk
            assert (store.root / "buffered.yaml").exists()
            assert (store.root / "buffered.yaml").read_text() == "buffered content"
            assert len(store._write_buffer) == 0

    @pytest.mark.asyncio
    async def test_buffer_evicts_oldest_when_full(self):
        """GIVEN a buffer at max capacity, WHEN a new write is buffered,
        THEN the oldest entry is evicted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.5)
            store = KnowledgeStore(root=tmpdir, circuit_breaker=cb)
            store.initialize()

            # Set a small buffer max size
            store._buffer_max_size = 2

            # Open the circuit
            async def fail_write():
                raise OSError("write failed")

            with pytest.raises(OSError):
                await cb.call(fail_write())
            assert cb.state == "OPEN"

            # Buffer 2 writes
            store._check_write_circuit("file1.yaml", "content1")
            store._check_write_circuit("file2.yaml", "content2")
            assert len(store._write_buffer) == 2

            # Buffer a 3rd write — should evict the oldest
            store._check_write_circuit("file3.yaml", "content3")
            assert len(store._write_buffer) == 2
            assert store._write_buffer[0]["path"] == "file2.yaml"
            assert store._write_buffer[1]["path"] == "file3.yaml"

    @pytest.mark.asyncio
    async def test_health_check_replays_buffered_writes(self):
        """GIVEN buffered writes and an OPEN circuit, WHEN health_check() succeeds,
        THEN buffered writes are replayed to disk but circuit remains OPEN."""
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

            # Buffer a write while circuit is OPEN
            store._check_write_circuit("buffered.yaml", "buffered content")
            assert len(store._write_buffer) == 1

            # health_check() should replay buffered writes to disk
            result = await store.health_check()
            assert result.status.name == "HEALTHY"

            # Circuit remains OPEN — health_check doesn't close it
            assert cb.state == "OPEN"

            # The buffered write should have been replayed to disk
            assert (store.root / "buffered.yaml").exists()
            assert (store.root / "buffered.yaml").read_text() == "buffered content"
            assert len(store._write_buffer) == 0

    @pytest.mark.asyncio
    async def test_multiple_buffered_writes_replayed_in_order(self):
        """GIVEN multiple buffered writes, WHEN replay occurs,
        THEN writes are executed in FIFO order."""
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

            # Buffer multiple writes
            store._check_write_circuit("file1.yaml", "content1")
            store._check_write_circuit("file2.yaml", "content2")
            store._check_write_circuit("file3.yaml", "content3")

            # Wait for recovery timeout and close the circuit with a successful async call
            await asyncio.sleep(0.06)

            async def succeed():
                return "ok"

            await cb.call(succeed())

            # Replay buffered writes
            store._replay_buffer()

            # All files should exist on disk in order
            assert (store.root / "file1.yaml").exists()
            assert (store.root / "file2.yaml").exists()
            assert (store.root / "file3.yaml").exists()
            assert (store.root / "file1.yaml").read_text() == "content1"
            assert (store.root / "file2.yaml").read_text() == "content2"
            assert (store.root / "file3.yaml").read_text() == "content3"

    @pytest.mark.asyncio
    async def test_replay_buffer_preserves_failed_writes(self):
        """GIVEN a buffered write that fails on replay, WHEN replay occurs,
        THEN the failed write is re-buffered."""
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

            # Buffer a write
            store._check_write_circuit("file1.yaml", "content1")

            # Wait for recovery timeout and close the circuit
            await asyncio.sleep(0.06)

            async def succeed():
                return "ok"

            await cb.call(succeed())

            # Make the directory read-only so writes fail
            import os

            os.chmod(tmpdir, 0o555)

            try:
                # Replay should fail and re-buffer the write
                store._replay_buffer()

                # The write should be back in the buffer
                assert len(store._write_buffer) == 1
            finally:
                os.chmod(tmpdir, 0o755)
