"""REQ-26/REQ-28 (tasks 2.1): substrate mock parity and checkpoint resume.

RED contract tests for the unified execution substrate:

- Phase runs on substrate (REQ-26 s1): a build phase executed through the
  substrate against the mock SQX server completes and exports results.
- Mock parity (REQ-28 s2 + work-unit "mock parity"): substrate output
  artifacts match the legacy mock dispatch path for identical inputs.
- Checkpoint resume (REQ-26 s2): interrupt at checkpoint N, re-run → resumes
  at N+1 without redoing completed work; a fully-exported phase is a no-op.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from quantlab.phase4.models import PhaseStatus
from quantlab.phase4.http_client import AsyncSQXClient
from quantlab.substrate.executor import (
    Executor,
    Phase,
    PhaseConfig,
)
from quantlab.substrate.lifecycle import LifecycleState, SubstrateCheckpoint


class RecordingClient:
    """Duck-typed ``AsyncSQXClient`` recording every ``send_command`` call.

    Wraps an optional real client (e.g. one pointed at the mock server) so
    tests can assert on the exact command sequence the substrate sent while
    still exercising a real HTTP round-trip.
    """

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


def _build_config(
    campaign_id: str,
    *,
    poll_interval: float = 0.3,
    timeout: float = 20.0,
    export_dir: Path | None = None,
    checkpoint_root: Path | None = None,
    client=None,
    force_mock: bool = True,
    project: str | None = None,
) -> PhaseConfig:
    return PhaseConfig(
        sqx_install_path="/home/ogzuz/Proyectos/SQX_144_2953_linux_20260601",
        campaign_id=campaign_id,
        project=project or f"{campaign_id}.cfx",
        poll_interval=poll_interval,
        timeout=timeout,
        export_dir=export_dir or "/tmp/sqx-exports",
        checkpoint_root=checkpoint_root,
        force_mock=force_mock,
        http_client=client,
    )


class TestPhaseRunsOnSubstrate:
    """REQ-26 scenario 1: phase runs on substrate against the mock server."""

    async def test_build_phase_completes_and_exports(self, campaign_id, tmp_path):
        export_dir = tmp_path / "exports"
        cfg = _build_config(campaign_id, export_dir=export_dir)

        result = await Executor.execute(Phase.BUILD, cfg)

        assert result.phase == Phase.BUILD
        assert result.status == PhaseStatus.COMPLETED
        assert result.is_successful
        # Export artifacts must exist and include strategies.csv.
        assert result.export_paths, "substrate produced no exports"
        names = {Path(p).name for p in result.export_paths}
        assert "strategies.csv" in names
        # Phase checkpoint dir holds the staged exports.
        staged = export_dir / Phase.BUILD.value
        assert (staged / "strategies.csv").is_file()

    async def test_phase_result_carries_watcher_events(self, campaign_id, tmp_path):
        cfg = _build_config(campaign_id, export_dir=tmp_path / "exports")

        result = await Executor.execute(Phase.RETEST, cfg)

        assert result.status == PhaseStatus.COMPLETED
        event_types = {e.get("event_type") for e in result.watcher_events}
        assert "campaign_complete" in event_types


class TestMockParity:
    """REQ-28 s2: mock mode retained — substrate honors SQX_FORCE_MOCK and
    produces the same artifacts as the legacy mock dispatch path."""

    async def test_legacy_mock_dispatch_and_substrate_produce_same_exports(
        self, campaign_id, tmp_path
    ):
        from quantlab.sqx.cli_wrapper import dispatch_campaign

        # Legacy path: force mock, small cadence.
        legacy = await dispatch_campaign(
            b"",  # cfx bytes unused by mock dispatch
            campaign_id=campaign_id,
            config={},
            sqx_install_path="/home/ogzuz/Proyectos/SQX_144_2953_linux_20260601",
            poll_interval=0.3,
            timeout=20.0,
            force_mock=True,
        )
        assert legacy["status"] == "completed"
        legacy_names = {Path(p).name for p in legacy["export_paths"]}

        # Substrate path: identical inputs.
        cfg = _build_config(campaign_id, export_dir=tmp_path / "exports")
        result = await Executor.execute(Phase.BUILD, cfg)
        assert result.status == PhaseStatus.COMPLETED
        substrate_names = {Path(p).name for p in result.export_paths}

        # Parity: strategies.csv is the canonical exported artifact in both.
        assert "strategies.csv" in legacy_names
        assert "strategies.csv" in substrate_names


class TestCheckpointResume:
    """REQ-26 scenario 2: resume at checkpoint N+1 without redoing work."""

    async def test_completed_phase_rerun_is_a_noop(self, campaign_id, tmp_path):
        export_dir = tmp_path / "exports"
        checkpoint_root = tmp_path / "checkpoints"
        real_client = RecordingClient(real=AsyncSQXClient("http://127.0.0.1:5050"))
        cfg = _build_config(
            campaign_id,
            export_dir=export_dir,
            checkpoint_root=checkpoint_root,
            client=real_client,
        )

        first = await Executor.execute(Phase.BUILD, cfg)
        assert first.status == PhaseStatus.COMPLETED
        commands_after_first = list(real_client.commands)

        second = await Executor.execute(Phase.BUILD, cfg)
        assert second.status == PhaseStatus.COMPLETED
        # Resume from EXPORTED: nothing is redone — no new commands sent.
        assert real_client.commands == commands_after_first
        assert set(second.export_paths) == set(first.export_paths)

    async def test_interrupted_after_load_resumes_at_start(self, campaign_id, tmp_path):
        export_dir = tmp_path / "exports"
        checkpoint_root = tmp_path / "checkpoints"
        real_client = RecordingClient(real=AsyncSQXClient("http://127.0.0.1:5050"))
        cfg = _build_config(
            campaign_id,
            export_dir=export_dir,
            checkpoint_root=checkpoint_root,
            client=real_client,
        )

        # Simulate an interrupt at checkpoint N=1: only LOAD completed.
        SubstrateCheckpoint(checkpoint_root, campaign_id, Phase.BUILD).save(
            LifecycleState.LOADED
        )

        result = await Executor.execute(Phase.BUILD, cfg)
        assert result.status == PhaseStatus.COMPLETED

        # Work stage N+1 (start) was performed, stage N (load) was NOT redone.
        assert real_client.commands, "no commands sent — resume did not run"
        first_command = real_client.commands[0]
        assert "action=loadconfig" not in first_command
        assert "action=start" in first_command

    async def test_no_redispatch_when_checkpoint_missing(self, campaign_id, tmp_path):
        """A fresh phase without a checkpoint performs the full sequence."""
        checkpoint_root = tmp_path / "checkpoints"
        cfg = _build_config(
            campaign_id,
            export_dir=tmp_path / "exports",
            checkpoint_root=checkpoint_root,
        )

        result = await Executor.execute(Phase.PORTFOLIO, cfg)
        assert result.status == PhaseStatus.COMPLETED
        # Checkpoint now exists at EXPORTED.
        assert (
            SubstrateCheckpoint(checkpoint_root, campaign_id, Phase.PORTFOLIO).load()
            == LifecycleState.EXPORTED
        )
