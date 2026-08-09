"""Executor stall-callback tests (task 3.5, execution-monitor spec).

The unified substrate must checkpoint a stalled phase BEFORE invoking the
LLM-diagnostics callback (spec: "a checkpoint is written immediately, then
LLM diagnostics are invoked after checkpoint completion"). Tests:

- ``Executor.execute`` with halt events → checkpoint persisted, then the
  ``on_stall`` callback runs and observes the checkpoint (ordering proof),
  and the phase fails closed (HOLD semantics via FAILED result).
- ``Executor.execute_chain`` with halt events → same ordering, FAILED result.
- Clean completion never invokes the diagnostics callback.
- A timeout without halt events does NOT invoke the callback (only stall
  conditions do — event-driven diagnostics, fail-closed on timeout).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from quantlab.phase4.models import PhaseStatus
from quantlab.substrate.executor import (
    ChainedTask,
    ChainSpec,
    Executor,
    Phase,
    PhaseConfig,
)
from quantlab.substrate.lifecycle import LifecycleState, SubstrateCheckpoint

HALT_EVENTS = [{"event_type": "stall", "severity": "CRITICAL"}]


def _cfg(campaign_id: str, export_dir: Path, checkpoint_root: Path | None, on_stall=None) -> PhaseConfig:
    return PhaseConfig(
        sqx_install_path="assets/SQX_144_2953_linux_20260601",
        campaign_id=campaign_id,
        project=f"{campaign_id}.cfx",
        poll_interval=0.3,
        timeout=20.0,
        export_dir=export_dir,
        checkpoint_root=checkpoint_root,
        force_mock=True,
        on_stall=on_stall,
    )


class TestExecutorStallCheckpointBeforeDiagnostics:
    async def test_stall_checkpoints_before_callback_and_fails_closed(
        self, campaign_id, tmp_path
    ) -> None:
        export_dir = tmp_path / "exports"
        checkpoint_root = tmp_path / "checkpoints"
        observed: list[str] = []

        async def on_stall(phase, events):
            ckpt = SubstrateCheckpoint(checkpoint_root, campaign_id, phase)
            observed.append(f"callback checkpoint={ckpt.load()}")

        cfg = _cfg(campaign_id, export_dir, checkpoint_root, on_stall=on_stall)
        stalled = AsyncMock(return_value=(False, HALT_EVENTS))

        with patch.object(Executor, "_run_poll_stage", new=stalled):
            result = await Executor.execute(Phase.BUILD, cfg)

        # Fail-closed: the stalled phase never completes.
        assert result.status == PhaseStatus.FAILED
        assert "stall" in (result.error or "").lower()
        # The callback observed a persisted STARTED checkpoint (the last
        # durable stage before the transient poll) → the executor wrote it
        # BEFORE invoking the LLM diagnostics callback.
        assert observed == [f"callback checkpoint={LifecycleState.STARTED}"]

    async def test_chain_stall_checkpoints_before_callback(self, campaign_id, tmp_path) -> None:
        export_dir = tmp_path / "exports"
        checkpoint_root = tmp_path / "checkpoints"
        observed: list[str] = []

        async def on_stall(phase, events):
            ckpt = SubstrateCheckpoint(checkpoint_root, campaign_id, phase)
            observed.append(f"callback checkpoint={ckpt.load()}")

        cfg = _cfg(campaign_id, export_dir, checkpoint_root, on_stall=on_stall)
        spec = ChainSpec(tasks=[ChainedTask(name="retest-task", phase=Phase.RETEST)])
        stalled = AsyncMock(return_value=(False, HALT_EVENTS))

        with patch.object(Executor, "_run_poll_stage", new=stalled):
            results = await Executor.execute_chain(spec, cfg)

        assert len(results) == 1
        assert results[0].status == PhaseStatus.FAILED
        assert "stall" in (results[0].error or "").lower()
        assert observed == [f"callback checkpoint={LifecycleState.STARTED}"]




class TestChainedCheckpointMetadata:
    """Task 4.4: execute_chain persists checkpoint metadata (REQ-26/REQ-27).

    - A completed chained task writes an EXPORTED boundary checkpoint so a
      later resume continues from that task without redoing it.
    - A stalled chained task checkpoints with its export paths BEFORE the
      diagnostics callback runs (parity with Executor.execute).
    """

    async def test_completed_task_writes_exported_boundary_checkpoint(
        self, campaign_id, tmp_path
    ) -> None:
        export_dir = tmp_path / "exports"
        checkpoint_root = tmp_path / "checkpoints"
        cfg = _cfg(campaign_id, export_dir, checkpoint_root)
        spec = ChainSpec(tasks=[ChainedTask(name="retest-task", phase=Phase.RETEST)])
        completed = AsyncMock(return_value=(True, []))

        with patch.object(Executor, "_run_poll_stage", new=completed):
            results = await Executor.execute_chain(spec, cfg)

        assert results[0].status == PhaseStatus.COMPLETED
        ckpt = SubstrateCheckpoint(checkpoint_root, campaign_id, Phase.RETEST)
        assert ckpt.load() == LifecycleState.EXPORTED
        assert ckpt.export_paths(), "boundary checkpoint must carry export paths"

    async def test_stalled_task_checkpoint_carries_export_paths_before_callback(
        self, campaign_id, tmp_path
    ) -> None:
        export_dir = tmp_path / "exports"
        checkpoint_root = tmp_path / "checkpoints"
        observed: list[tuple[LifecycleState, list[str]]] = []

        async def on_stall(phase, events):
            ckpt = SubstrateCheckpoint(checkpoint_root, campaign_id, phase)
            observed.append((ckpt.load(), ckpt.export_paths()))

        cfg = _cfg(campaign_id, export_dir, checkpoint_root, on_stall=on_stall)
        spec = ChainSpec(tasks=[ChainedTask(name="retest-task", phase=Phase.RETEST)])
        stalled = AsyncMock(return_value=(False, HALT_EVENTS))

        with patch.object(Executor, "_run_poll_stage", new=stalled):
            results = await Executor.execute_chain(spec, cfg)

        assert results[0].status == PhaseStatus.FAILED
        state, paths = observed[0]
        assert state == LifecycleState.STARTED
        assert paths, "stall checkpoint must carry the phase export paths as metadata"
class TestExecutorStallCallbackNotInvoked:
    async def test_clean_completion_skips_callback(self, campaign_id, tmp_path) -> None:
        export_dir = tmp_path / "exports"
        observed: list[str] = []

        async def on_stall(phase, events):
            observed.append("callback-called")

        cfg = _cfg(campaign_id, export_dir, None, on_stall=on_stall)
        completed = AsyncMock(return_value=(True, []))

        with patch.object(Executor, "_run_poll_stage", new=completed):
            result = await Executor.execute(Phase.BUILD, cfg)

        assert result.status == PhaseStatus.COMPLETED
        # Diagnostics are event-driven: no stall → no LLM invocation.
        assert observed == []

    async def test_timeout_without_halt_events_skips_callback(
        self, campaign_id, tmp_path
    ) -> None:
        export_dir = tmp_path / "exports"
        observed: list[str] = []

        async def on_stall(phase, events):
            observed.append("callback-called")

        cfg = _cfg(campaign_id, export_dir, None, on_stall=on_stall)
        timed_out = AsyncMock(return_value=(False, []))

        with patch.object(Executor, "_run_poll_stage", new=timed_out):
            result = await Executor.execute(Phase.BUILD, cfg)

        assert result.status == PhaseStatus.FAILED
        assert "timed out" in (result.error or "").lower()
        # A plain timeout is not a stall — diagnostics stay off.
        assert observed == []
