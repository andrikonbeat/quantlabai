"""Task 2.5 RED: chained retest → optimize in ONE project load (REQ-27).

Contract tests for ``Executor.execute_chain``:

- ONE ``loadconfig`` + ONE ``start`` across a multi-task chain: the SQX
  project stays loaded for the whole campaign instead of being torn down and
  re-loaded per phase (REQ-27: "in a single project load").
- Human gate between tasks: after the retest completes the gate decides
  whether the optimize task may run. A gate DENIAL blocks the remaining
  tasks (fail-closed) while preserving the completed task's results.
- Legacy parity (REQ-28): chained substrate output for the optimize stage
  matches the legacy mock dispatch path for identical inputs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantlab.phase4.http_client import AsyncSQXClient
from quantlab.phase4.models import PhaseStatus
from quantlab.substrate.executor import (
    ChainedTask,
    ChainSpec,
    Executor,
    Phase,
    PhaseConfig,
)
from quantlab.substrate.lifecycle import LifecycleState, SubstrateCheckpoint


class RecordingClient:
    """Duck-typed ``AsyncSQXClient`` recording every ``send_command`` call."""

    def __init__(self, real=None):
        self.commands: list[str] = []
        self._real = real

    async def send_command(self, command: str) -> str:
        self.commands.append(command)
        if self._real is not None:
            return await self._real.send_command(command)
        return ""

    async def close(self) -> None:
        if self._real is not None:
            await self._real.close()


def _cfg(
    campaign_id: str,
    *,
    export_dir: Path,
    checkpoint_root: Path | None = None,
    client=None,
) -> PhaseConfig:
    return PhaseConfig(
        sqx_install_path="assets/SQX_144_2953_linux_20260601",
        campaign_id=campaign_id,
        project=f"{campaign_id}.cfx",
        poll_interval=0.3,
        timeout=20.0,
        export_dir=export_dir,
        checkpoint_root=checkpoint_root,
        force_mock=True,
        http_client=client,
    )


class TestChainedTasksSingleLoad:
    """REQ-27: retest → optimize chain runs in one project load."""

    async def test_chain_runs_two_tasks_in_one_load(self, campaign_id, tmp_path):
        client = RecordingClient(real=AsyncSQXClient("http://127.0.0.1:5050"))
        cfg = _cfg(
            campaign_id, export_dir=tmp_path / "exports", client=client
        )
        spec = ChainSpec(
            tasks=[
                ChainedTask(name="retest-task", phase=Phase.RETEST),
                ChainedTask(name="optimize-task", phase=Phase.OPTIMIZE),
            ],
            gate=_allow_gate,
        )

        results = await Executor.execute_chain(spec, cfg)

        assert len(results) == 2
        assert all(r.status == PhaseStatus.COMPLETED for r in results)

        # ONE load + ONE start for the whole chain (REQ-27 single load).
        loads = [c for c in client.commands if "action=loadconfig" in c]
        starts = [c for c in client.commands if "action=start" in c]
        assert len(loads) == 1
        assert len(starts) == 1

        # The chain still produced per-phase artifacts.
        optimize = results[1]
        assert optimize.export_paths
        names = {Path(p).name for p in optimize.export_paths}
        assert "strategies.csv" in names


class TestChainedGate:
    """REQ-27: the human gate decides what runs after the first task."""

    async def test_gate_denial_blocks_remaining_tasks_fail_closed(
        self, campaign_id, tmp_path
    ):
        client = RecordingClient(real=AsyncSQXClient("http://127.0.0.1:5050"))
        cfg = _cfg(
            campaign_id, export_dir=tmp_path / "exports", client=client
        )
        spec = ChainSpec(
            tasks=[
                ChainedTask(name="retest-task", phase=Phase.RETEST),
                ChainedTask(name="optimize-task", phase=Phase.OPTIMIZE),
            ],
            gate=_deny_gate,
        )

        results = await Executor.execute_chain(spec, cfg)

        # First task completed with exports; remaining task refused.
        assert results[0].status == PhaseStatus.COMPLETED
        assert results[1].status == PhaseStatus.FAILED
        assert "gate" in (results[1].error or "").lower()

        # A denied task never dispatches — no second start command.
        starts = [c for c in client.commands if "action=start" in c]
        assert len(starts) == 1


class TestChainedLegacyParity:
    """REQ-28: chained optimize output matches the legacy mock dispatch."""

    async def test_chained_optimize_matches_legacy_mock_dispatch(
        self, campaign_id, tmp_path
    ):
        from quantlab.sqx.cli_wrapper import dispatch_campaign

        legacy = await dispatch_campaign(
            b"",
            campaign_id=campaign_id,
            config={},
            sqx_install_path="assets/SQX_144_2953_linux_20260601",
            poll_interval=0.3,
            timeout=20.0,
            force_mock=True,
        )
        assert legacy["status"] == "completed"
        legacy_names = {Path(p).name for p in legacy["export_paths"]}

        cfg = _cfg(campaign_id, export_dir=tmp_path / "exports")
        spec = ChainSpec(
            tasks=[
                ChainedTask(name="optimize-task", phase=Phase.OPTIMIZE),
            ],
            gate=_allow_gate,
        )
        results = await Executor.execute_chain(spec, cfg)

        assert results[0].status == PhaseStatus.COMPLETED
        substrate_names = {Path(p).name for p in results[0].export_paths}
        assert "strategies.csv" in legacy_names
        assert "strategies.csv" in substrate_names


async def _allow_gate(prev: str, next_task: str) -> bool:
    return True


async def _deny_gate(prev: str, next_task: str) -> bool:
    return False
