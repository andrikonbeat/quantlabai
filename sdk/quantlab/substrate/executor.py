"""Unified execution substrate (REQ-26) — one runner parameterized by phase.

Replaces the three overlapping dispatch paths (CommandDispatcher,
``cli_wrapper._dispatch_real``, CampaignOrchestrator internals) with a single
daemon + project lifecycle + polling + event detection + checkpoint + export
runner, while the 14-phase human-gated flow stays intact (REQ-37).

Flag: ``QUANTLAB_UNIFIED_SUBSTRATE=1`` enables routing through the substrate;
the legacy paths stay operational until output parity is proven (REQ-28).
``SQX_FORCE_MOCK=1`` is honored for the 2790-test suite.

Interface (design contract): ``Executor.execute(phase, config) -> PhaseResult``
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable

from quantlab.phase4.models import PhaseStatus
from quantlab.sqx.campaign_monitor import WatcherEvent
from quantlab.substrate.events import SubstrateEventDetector
from quantlab.substrate.exporter import collect_exports, export_phase
from quantlab.substrate.lifecycle import (
    DaemonLifecycle,
    LifecycleState,
    SubstrateCheckpoint,
    WORK_STAGES,
    next_stage_after,
)
from quantlab.substrate.poller import poll_until_done

logger = logging.getLogger(__name__)

_DEFAULT_PORT = 5050


class Phase(str, Enum):
    """Substrate phase parameterization (REQ-26)."""

    BUILD = "build"
    RETEST = "retest"
    OPTIMIZE = "optimize"
    PORTFOLIO = "portfolio"


class SubstrateError(Exception):
    """Base error for the unified execution substrate."""


class SubstrateConfigError(SubstrateError):
    """Fail-closed configuration error (e.g. missing sqcli binary)."""


@dataclass
class PhaseConfig:
    """Configuration for a single substrate phase execution."""

    sqx_install_path: str | Path
    campaign_id: str
    project: str | Path | None = None  # CFX file (loadconfig) or project name
    poll_interval: float = 10.0
    timeout: float = 1800.0
    export_dir: str | Path = "/tmp/sqx-exports"
    export_databank: str = "Results"
    force_mock: bool = False
    checkpoint_root: str | Path | None = None
    http_client: Any = None
    on_watcher_event: Callable[[WatcherEvent], None] | None = None
    # Invoked on stall detection (WARNING/CRITICAL event) AFTER the stall
    # checkpoint is written, so LLM-assisted diagnostics always run against a
    # persisted state (execution-monitor spec: checkpoint before diagnostics).
    on_stall: Callable[
        [Phase, list[dict[str, Any]]], Awaitable[None]
    ] | None = None


@dataclass
class PhaseResult:
    """Result of a substrate phase execution (REQ-26)."""

    phase: Phase
    status: PhaseStatus
    export_paths: list[str] = field(default_factory=list)
    watcher_events: list[dict[str, Any]] = field(default_factory=list)
    checkpoint: LifecycleState | None = None
    error: str | None = None
    detail: str = ""

    @property
    def is_successful(self) -> bool:
        return self.status == PhaseStatus.COMPLETED


@dataclass
class ChainedTask:
    """A task inside a multi-task Custom Project (REQ-27)."""

    name: str
    phase: Phase
    databank: str = "Results"


@dataclass
class ChainSpec:
    """Chained multi-task run: tasks execute in ONE project load (REQ-27)."""

    tasks: list[ChainedTask]
    gate: Callable[[str, str], Awaitable[bool]] | None = None


def phase_name(phase: Any) -> str:
    """Normalize a Phase enum or raw string to its phase name."""
    return phase.value if hasattr(phase, "value") else str(phase)


def is_unified_substrate_enabled(env: dict[str, str] | None = None) -> bool:
    """Rollback gate (AD-4): ``QUANTLAB_UNIFIED_SUBSTRATE=1`` opts into the
    substrate; the default (and ``QUANTLAB_UNIFIED_SUBSTRATE=0``) keeps the
    legacy dispatch paths operational (REQ-28)."""
    env = os.environ if env is None else env
    return env.get("QUANTLAB_UNIFIED_SUBSTRATE", "0") == "1"


def resolve_sqcli_path(
    sqx_install_path: str | Path, env: dict[str, str] | None = None
) -> str | None:
    """Resolve the ``sqcli`` binary for real dispatch.

    Order: ``SQCLI_PATH`` env var → ``sqcli``/``sqcli.exe``/``sqcli.sh`` in
    the install directory. Relative paths resolve to absolute. Returns
    ``None`` when no candidate exists and is executable — the caller must
    fail closed (no dispatch) per the subprocess threat-matrix row.
    """
    env = os.environ if env is None else env
    candidates: list[Path] = []
    env_path = env.get("SQCLI_PATH")
    if env_path:
        candidates.append(Path(env_path))
    install = Path(sqx_install_path)
    candidates.extend(
        [install / "sqcli", install / "sqcli.exe", install / "sqcli.sh"]
    )
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate.resolve())
    return None


def select_dispatch_mode(
    sqx_install_path: str | Path,
    *,
    force_mock: bool = False,
    env: dict[str, str] | None = None,
) -> str:
    """Select the dispatch mode, fail-closed.

    Returns ``"mock"`` when ``force_mock`` or ``SQX_FORCE_MOCK`` is set;
    ``"real"`` when the sqcli binary resolves; ``"missing"`` otherwise —
    missing binary is never silently mocked or dispatched (threat matrix:
    validate existence before dispatch).
    """
    env = os.environ if env is None else env
    mock_env = env.get("SQX_FORCE_MOCK", "").lower() in ("1", "true", "yes")
    if force_mock or mock_env:
        return "mock"
    if resolve_sqcli_path(sqx_install_path, env) is not None:
        return "real"
    return "missing"


async def _send(client: Any, command: str) -> str:
    logger.debug("substrate → %s", command)
    return await client.send_command(command)


class Executor:
    """Unified execution substrate — one runner parameterized by phase."""

    @staticmethod
    async def execute(phase: Phase, config: PhaseConfig) -> PhaseResult:
        """Execute *phase* on the substrate (REQ-26).

        Flow: resolve dispatch mode → daemon start → load project → start
        project → poll with event detection → export → checkpoint each stage.
        Checkpoint resume: an interrupted phase re-runs from the stage after
        the last completed one (REQ-26 scenario 2).

        Raises:
            SubstrateConfigError: sqcli missing and mock not forced
                (fail-closed, no dispatch).
        """
        mode = select_dispatch_mode(
            config.sqx_install_path, force_mock=config.force_mock
        )
        if mode == "missing":
            raise SubstrateConfigError(
                "sqcli binary not found — dispatch refused. Install SQX, set "
                "SQCLI_PATH, or set SQX_FORCE_MOCK=1 for mock mode."
            )

        checkpoint: SubstrateCheckpoint | None = None
        skip_until = 0
        if config.checkpoint_root is not None:
            checkpoint = SubstrateCheckpoint(
                config.checkpoint_root, config.campaign_id, phase
            )
            last_stage = checkpoint.load()
            if last_stage == LifecycleState.EXPORTED:
                logger.info(
                    "Phase %s already exported for '%s' — resume is a no-op",
                    phase_name(phase), config.campaign_id,
                )
                return PhaseResult(
                    phase=phase,
                    status=PhaseStatus.COMPLETED,
                    export_paths=checkpoint.export_paths(),
                    checkpoint=LifecycleState.EXPORTED,
                    detail="resumed from exported checkpoint",
                )
            skip_until = next_stage_after(last_stage)

        lifecycle = DaemonLifecycle(
            config.sqx_install_path, mode=mode, port=_DEFAULT_PORT
        )
        client = config.http_client
        own_client = False
        try:
            await lifecycle.start()
            if client is None:
                client = await lifecycle.get_client()
                own_client = True

            # Resume contract (REQ-26 s2): pick up at the stage AFTER the last
            # completed one. The daemon lifecycle mirrors that position so the
            # state machine continues from the checkpointed stage instead of
            # resetting to IDLE (which would force a re-dispatch).
            if skip_until > 0:
                lifecycle.resume_at(WORK_STAGES[skip_until - 1])

            result = PhaseResult(
                phase=phase,
                status=PhaseStatus.RUNNING,
                detail=f"{phase_name(phase)} running on substrate",
            )

            for stage in WORK_STAGES[skip_until:]:
                if stage == LifecycleState.LOADED:
                    project = config.project or config.campaign_id
                    await _send(
                        client,
                        f"-project action=loadconfig "
                        f"name={config.campaign_id} file={project}",
                    )
                elif stage == LifecycleState.STARTED:
                    await _send(
                        client,
                        f"-project action=start name={config.campaign_id}",
                    )
                elif stage == LifecycleState.COMPLETED:
                    # RUNNING is a transient poll stage: advance through it so
                    # the state machine honors STARTED → RUNNING → COMPLETED.
                    lifecycle.transition(LifecycleState.RUNNING)
                    completed, events = await Executor._run_poll_stage(
                        phase, config, client, lifecycle
                    )
                    result.watcher_events = events
                    lifecycle.transition(LifecycleState.COMPLETED)
                    if not completed:
                        if Executor._halt_events(events):
                            # Checkpoint BEFORE LLM diagnostics: persist the
                            # stalled state first so the diagnostics callback
                            # runs against a checkpointed phase (fail-closed
                            # for human review after the fact). STARTED is the
                            # last durable stage before the (transient) poll.
                            if checkpoint is not None:
                                checkpoint.save(
                                    LifecycleState.STARTED,
                                    export_paths=result.export_paths,
                                )
                            if config.on_stall is not None:
                                await config.on_stall(phase, events)
                            raise SubstrateError(
                                "stall/config event detected — halted for human"
                            )
                        raise SubstrateError(
                            f"phase timed out after {config.timeout:.0f}s"
                        )
                elif stage == LifecycleState.EXPORTED:
                    result.export_paths = await export_phase(
                        client,
                        config.campaign_id,
                        phase,
                        sqx_install_path=config.sqx_install_path,
                        export_dir=config.export_dir,
                        databank=config.export_databank,
                    )

                # The poll branch already advanced through RUNNING → COMPLETED;
                # the remaining stages transition exactly once to their stage.
                if stage != LifecycleState.COMPLETED:
                    lifecycle.transition(stage)
                if checkpoint is not None:
                    checkpoint.save(stage, export_paths=result.export_paths)

            result.status = PhaseStatus.COMPLETED
            result.checkpoint = LifecycleState.EXPORTED
            result.detail = f"{phase_name(phase)} completed on substrate"
            return result

        except Exception as exc:
            try:
                lifecycle.transition(LifecycleState.FAILED)
            except ValueError:
                pass
            logger.warning(
                "Substrate phase %s failed for '%s': %s",
                phase_name(phase), config.campaign_id, exc,
            )
            return PhaseResult(
                phase=phase,
                status=PhaseStatus.FAILED,
                error=str(exc),
                watcher_events=result.watcher_events
                if "result" in locals() and hasattr(result, "watcher_events")
                else [],
                detail=f"{phase_name(phase)} failed on substrate",
            )
        finally:
            if own_client and client is not None:
                try:
                    await client.close()
                except Exception:
                    pass
            await lifecycle.stop()

    @staticmethod
    async def _run_poll_stage(
        phase: Phase,
        config: PhaseConfig,
        client: Any,
        lifecycle: DaemonLifecycle,
    ) -> tuple[bool, list[dict[str, Any]]]:
        """Poll to completion while the per-phase EventDetector watches.

        Returns ``(completed, watcher_events)``. Event detection runs on the
        substrate's own polling cadence (REQ-42).
        """
        detector = SubstrateEventDetector(
            campaign_id=config.campaign_id,
            base_url=lifecycle.base_url,
            phase=phase,
            poll_interval=max(0.5, config.poll_interval / 2),
            on_watcher_event=config.on_watcher_event,
            export_dir=str(Path(config.export_dir) / phase_name(phase)),
        )
        detector_task = asyncio.create_task(detector.run())
        events: list[dict[str, Any]] = []
        try:
            poll = await poll_until_done(
                client,
                config.campaign_id,
                poll_interval=config.poll_interval,
                timeout=config.timeout,
            )
            completed = poll.completed
        finally:
            await detector.cancel()
            await detector.final_check()
            try:
                collected = await asyncio.wait_for(detector_task, timeout=5.0)
                events = [e.to_dict() for e in collected]
            except (asyncio.TimeoutError, asyncio.CancelledError):
                events = [e.to_dict() for e in detector.events]
        return completed, events

    @staticmethod
    def _halt_events(events: list[dict[str, Any]]) -> bool:
        return any(
            e.get("severity") in ("WARNING", "CRITICAL") for e in events
        )

    # ── Chained multi-task runs (REQ-27) ─────────────────────────────────

    @staticmethod
    async def execute_chain(
        spec: ChainSpec, config: PhaseConfig
    ) -> list[PhaseResult]:
        """Run retest/optimize (etc.) chained in ONE project load (REQ-27).

        The multi-task Custom Project is loaded once and started once; SQX
        executes the tasks in declared order. A human gate configured between
        tasks holds execution until it resolves; denial blocks the remaining
        tasks (fail-closed).
        """
        if not spec.tasks:
            return []
        mode = select_dispatch_mode(
            config.sqx_install_path, force_mock=config.force_mock
        )
        if mode == "missing":
            raise SubstrateConfigError(
                "sqcli binary not found — dispatch refused. Set SQCLI_PATH or "
                "SQX_FORCE_MOCK=1."
            )

        lifecycle = DaemonLifecycle(
            config.sqx_install_path, mode=mode, port=_DEFAULT_PORT
        )
        client = config.http_client
        own_client = False
        results: list[PhaseResult] = []
        try:
            await lifecycle.start()
            if client is None:
                client = await lifecycle.get_client()
                own_client = True

            # ONE load + ONE start for the whole chained project (REQ-27).
            project = config.project or config.campaign_id
            await _send(
                client,
                f"-project action=loadconfig "
                f"name={config.campaign_id} file={project}",
            )
            lifecycle.transition(LifecycleState.LOADED)
            await _send(
                client,
                f"-project action=start name={config.campaign_id}",
            )
            lifecycle.transition(LifecycleState.STARTED)

            for index, task in enumerate(spec.tasks):
                if spec.gate is not None and index > 0:
                    previous = spec.tasks[index - 1]
                    resolved = await spec.gate(previous.name, task.name)
                    if not resolved:
                        logger.warning(
                            "Gate denied between '%s' and '%s' — '%s' blocked",
                            previous.name, task.name, task.name,
                        )
                        results.append(
                            PhaseResult(
                                phase=task.phase,
                                status=PhaseStatus.FAILED,
                                error=(
                                    f"gate denied between {previous.name} "
                                    f"and {task.name}"
                                ),
                                detail=f"{task.name} blocked by human gate",
                            )
                        )
                        continue

                completed, events = await Executor._run_poll_stage(
                    task.phase, config, client, lifecycle
                )
                exports = await export_phase(
                    client,
                    config.campaign_id,
                    task.phase,
                    sqx_install_path=config.sqx_install_path,
                    export_dir=config.export_dir,
                    databank=task.databank,
                )
                if not completed and Executor._halt_events(events):
                    # Checkpoint BEFORE LLM diagnostics (execution-monitor
                    # spec): persist the stalled state WITH the export paths as
                    # checkpoint metadata, then hand the phase to the
                    # diagnostics callback (parity with Executor.execute).
                    if config.checkpoint_root is not None:
                        SubstrateCheckpoint(
                            config.checkpoint_root,
                            config.campaign_id,
                            task.phase,
                        ).save(LifecycleState.STARTED, export_paths=exports)
                    if config.on_stall is not None:
                        await config.on_stall(task.phase, events)
                    results.append(
                        PhaseResult(
                            phase=task.phase,
                            status=PhaseStatus.FAILED,
                            export_paths=exports,
                            watcher_events=events,
                            error="stall/config event detected — halted for human",
                        )
                    )
                    continue
                if completed and config.checkpoint_root is not None:
                    # Per-task EXPORTED boundary checkpoint (REQ-26/REQ-27):
                    # record the phase completion and its export paths so a
                    # later resume continues from this task without redoing it.
                    SubstrateCheckpoint(
                        config.checkpoint_root,
                        config.campaign_id,
                        task.phase,
                    ).save(LifecycleState.EXPORTED, export_paths=exports)
                results.append(
                    PhaseResult(
                        phase=task.phase,
                        status=PhaseStatus.COMPLETED if completed
                        else PhaseStatus.FAILED,
                        export_paths=exports,
                        watcher_events=events,
                        checkpoint=LifecycleState.EXPORTED
                        if completed else None,
                        error=None if completed
                        else f"phase timed out after {config.timeout:.0f}s",
                        detail=f"{task.name} ({phase_name(task.phase)}) completed"
                        if completed else f"{task.name} failed",
                    )
                )

            return results
        finally:
            if own_client and client is not None:
                try:
                    await client.close()
                except Exception:
                    pass
            await lifecycle.stop()
