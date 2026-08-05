"""Substrate daemon lifecycle and checkpointing (REQ-26, AD-4).

The unified substrate runs one daemon lifecycle parameterized by phase. This
module provides:

- :class:`LifecycleState` — the public state machine
  ``IDLE → LOADED → STARTED → RUNNING → COMPLETED → EXPORTED`` with a
  ``FAILED`` sink for stall/error (WatcherEvent, halt for human).
- :class:`DaemonLifecycle` — one daemon abstraction over the real
  ``SQXDaemonManager`` (phase4) and the mock server (``SQX_FORCE_MOCK``).
- :class:`SubstrateCheckpoint` — stage-level resume checkpoints built on the
  phase4 ``CheckpointManager`` pattern (interrupt at N → resume at N+1).
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

from quantlab.phase4.checkpoint import CampaignCheckpoint, CheckpointManager
from quantlab.phase4.daemon import SQXDaemonManager
from quantlab.phase4.http_client import AsyncSQXClient
from quantlab.phase4.models import CampaignPhase, PhaseResult, PhaseStatus
from quantlab.sqx.mock_sqx_server import MockSQXServer

logger = logging.getLogger(__name__)

DEFAULT_PORT = 5050


class LifecycleState(str, Enum):
    """Daemon lifecycle states (design AD-4 state machine)."""

    IDLE = "idle"
    LOADED = "loaded"
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    EXPORTED = "exported"
    FAILED = "failed"


# Checkpointable work stages, in execution order. RUNNING is transient (the
# poll loop) and is never persisted as a completed stage.
WORK_STAGES: list[LifecycleState] = [
    LifecycleState.LOADED,
    LifecycleState.STARTED,
    LifecycleState.COMPLETED,
    LifecycleState.EXPORTED,
]

# Map substrate stages onto the phase4 campaign-phase vocabulary so the
# existing phase4 CheckpointManager can persist them unchanged (AD-4 reuse).
_STAGE_TO_CAMPAIGN_PHASE: dict[LifecycleState, CampaignPhase] = {
    LifecycleState.LOADED: CampaignPhase.LOAD_CONFIG,
    LifecycleState.STARTED: CampaignPhase.RUN,
    LifecycleState.COMPLETED: CampaignPhase.POLL,
    LifecycleState.EXPORTED: CampaignPhase.EXPORT,
}
_CAMPAIGN_PHASE_TO_STAGE = {v: k for k, v in _STAGE_TO_CAMPAIGN_PHASE.items()}

# Valid transitions in the design state machine.
_VALID_TRANSITIONS: dict[LifecycleState, set[LifecycleState]] = {
    LifecycleState.IDLE: {LifecycleState.LOADED, LifecycleState.FAILED},
    LifecycleState.LOADED: {LifecycleState.STARTED, LifecycleState.FAILED},
    LifecycleState.STARTED: {LifecycleState.RUNNING, LifecycleState.FAILED},
    LifecycleState.RUNNING: {LifecycleState.COMPLETED, LifecycleState.FAILED},
    LifecycleState.COMPLETED: {LifecycleState.EXPORTED, LifecycleState.FAILED},
    LifecycleState.EXPORTED: set(),
    LifecycleState.FAILED: set(),
}


def can_transition(current: LifecycleState, next_state: LifecycleState) -> bool:
    """Return whether *next_state* is a legal successor of *current*."""
    return next_state in _VALID_TRANSITIONS.get(current, set())


def next_stage_after(state: LifecycleState | None) -> int:
    """Return the WORK_STAGES index at which execution should resume.

    ``None`` (no checkpoint) → start at index 0. A completed stage N resumes
    at N+1 (REQ-26: "resumes at checkpoint N+1 without redoing completed
    work").
    """
    if state is None:
        return 0
    if state in WORK_STAGES:
        return WORK_STAGES.index(state) + 1
    return 0


async def ensure_mock_server(port: int = DEFAULT_PORT) -> str:
    """Start (or re-use) the mock SQX server and return its base URL.

    Mirrors the legacy ``cli_wrapper._ensure_mock_server`` readiness probe so
    mock parity holds under ``SQX_FORCE_MOCK``.
    """
    base_url = f"http://127.0.0.1:{port}"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{base_url}/call?cmd=-h")
            if resp.status_code == 200:
                return base_url
    except Exception:
        pass

    MockSQXServer.reset()
    await asyncio.sleep(0.3)
    MockSQXServer.instance(port=port, mode="normal").start()

    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base_url}/call?cmd=-h")
                if resp.status_code == 200 and "Usage" in resp.text:
                    logger.info("Mock SQX server ready at %s", base_url)
                    return base_url
        except Exception:
            pass
        await asyncio.sleep(0.5)

    raise RuntimeError("Mock SQX server did not start")


class DaemonLifecycle:
    """Unified daemon abstraction: real SQXDaemonManager or mock server.

    Args:
        sqx_install_path: SQX installation root (real mode only).
        mode: ``"mock"`` (SQX_FORCE_MOCK honored) or ``"real"`` (sqcli
            resolved and validated before dispatch).
        port: HTTP API port.
        startup_timeout: Daemon readiness timeout in seconds.
    """

    def __init__(
        self,
        sqx_install_path: str | Path,
        *,
        mode: str = "mock",
        port: int = DEFAULT_PORT,
        startup_timeout: float = 60.0,
    ) -> None:
        self._sqx_install_path = Path(sqx_install_path)
        self._mode = mode
        self._port = port
        self._startup_timeout = startup_timeout
        self._daemon: SQXDaemonManager | None = None
        self._state = LifecycleState.IDLE

    @property
    def state(self) -> LifecycleState:
        return self._state

    @property
    def is_mock(self) -> bool:
        return self._mode == "mock"

    @property
    def base_url(self) -> str:
        if self._daemon is not None:
            return self._daemon.base_url
        return f"http://127.0.0.1:{self._port}"

    def transition(self, next_state: LifecycleState) -> None:
        """Advance the state machine; reject illegal transitions."""
        if not can_transition(self._state, next_state):
            raise ValueError(
                f"illegal substrate lifecycle transition: "
                f"{self._state.value} → {next_state.value}"
            )
        self._state = next_state

    def resume_at(self, state: LifecycleState) -> None:
        """Position the lifecycle at a checkpointed stage for resume (REQ-26 s2).

        After a fresh daemon start the state machine would otherwise sit at
        IDLE; a resume must continue from the last completed stage so
        ``IDLE → LOADED`` is not forced and no completed work is redone.
        """
        if state not in WORK_STAGES:
            raise ValueError(
                f"cannot resume at non-work stage: {state.value}"
            )
        self._state = state

    async def start(self) -> str:
        """Start the daemon (real or mock) and return the base URL."""
        if self._mode == "mock":
            base_url = await ensure_mock_server(self._port)
            self._state = LifecycleState.IDLE
            return base_url

        self._daemon = SQXDaemonManager(
            str(self._sqx_install_path),
            port=self._port,
            startup_timeout=self._startup_timeout,
        )
        base_url = await self._daemon.start()
        self._state = LifecycleState.IDLE
        return base_url

    async def stop(self) -> None:
        if self._daemon is not None:
            try:
                await self._daemon.stop()
            except Exception:
                logger.warning("Substrate daemon stop failed", exc_info=True)
            self._daemon = None

    async def get_client(self) -> AsyncSQXClient:
        return AsyncSQXClient(self.base_url)


class SubstrateCheckpoint:
    """Stage-level resume checkpoint for a single substrate phase.

    Persists via the phase4 ``CheckpointManager`` (keyed
    ``{campaign_id}-{phase}``) with the completed work stages mapped onto the
    phase4 ``CampaignPhase`` vocabulary — the AD-4 reuse contract.
    """

    def __init__(
        self,
        root: str | Path,
        campaign_id: str,
        phase: Any,
    ) -> None:
        from quantlab.substrate.executor import phase_name

        self._mgr = CheckpointManager(Path(root))
        self._project = f"{campaign_id}-{phase_name(phase)}"

    def save(
        self,
        stage: LifecycleState,
        export_paths: list[str] | None = None,
    ) -> Path:
        """Persist the stage (and everything before it) as completed."""
        completed = WORK_STAGES[: WORK_STAGES.index(stage) + 1]
        checkpoint = CampaignCheckpoint(
            project_name=self._project,
            completed_phases=[
                _STAGE_TO_CAMPAIGN_PHASE[s] for s in completed
            ],
            phase_results=[
                PhaseResult(
                    phase=_STAGE_TO_CAMPAIGN_PHASE[s],
                    status=PhaseStatus.COMPLETED,
                    detail=f"substrate stage {s.value} completed",
                )
                for s in completed
            ],
            export_paths={
                str(i): p for i, p in enumerate(export_paths or [])
            },
        )
        return self._mgr.save(checkpoint)

    def load(self) -> LifecycleState | None:
        """Return the last completed stage, or ``None`` when absent."""
        checkpoint = self._mgr.load(self._project)
        if checkpoint is None or not checkpoint.completed_phases:
            return None
        last = _CAMPAIGN_PHASE_TO_STAGE.get(checkpoint.completed_phases[-1])
        return last

    def export_paths(self) -> list[str]:
        checkpoint = self._mgr.load(self._project)
        if checkpoint is None:
            return []
        return list(checkpoint.export_paths.values())
