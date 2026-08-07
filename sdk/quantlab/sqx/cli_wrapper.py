"""Real SQX CLI wrapper — dispatches campaigns to a live SQX daemon.

Architecture
------------
SQX runs as a persistent daemon (``sqcli`` with no arguments). All commands
go through the HTTP API on port 5050 (``/call?cmd=<command>``).

The dispatch flow:
  1. Stop any existing daemon.
  2. Create campaign project directory from template (``project_builder``).
  3. Start daemon (scans projects at startup).
  4. Start campaign via HTTP API (``-project action=start``).
  5. Poll status until completion.
  6. Stop project.
  7. Export databanks.
  8. Stop daemon.

When the real sqcli binary is unavailable, the wrapper falls back to a
lightweight mock server (``MockSQXServer``) so demos can run end-to-end.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from quantlab.dsl.models import LLMConfig
from quantlab.gates.notifiers import ConsoleNotifier, WebhookNotifier
from quantlab.sqx.blocks_bridge import validate_exported_blocks
from quantlab.sqx.campaign_monitor import CampaignMonitor, WatcherEvent, compute_baseline
from quantlab.sqx.llm_generation_monitor import LLMGenerationMonitor, Verdict
from quantlab.sqx.mock_sqx_server import MockSQXServer
from quantlab.sqx.project_builder import create_project, remove_project

logger = logging.getLogger(__name__)

_DEFAULT_POLL_INTERVAL = 10.0
_DEFAULT_TIMEOUT = 1800.0  # 30 minutes for strategy generation

_EXPORT_DIRS = [
    "user/projects/{campaign_id}/exports",
    "user/settings/Exports/{campaign_id}",
    "/tmp/sqx-exports/{campaign_id}",
    "/tmp/sqx-mock-exports/{campaign_id}",
]

_COMMAND_ENDPOINT = "/call?cmd="

# The sqcli daemon can take 90-105s to become ready on first launch (it
# loads every legacy project under ``user/projects/`` at startup).  The
# readiness deadline is resolved via QUANTLAB_SQCLI_TIMEOUT (default 180s)
# in cli/runner.resolve_sqcli_timeout.
_SQX_PORT = 5050
_SQX_BASE_URL = f"http://127.0.0.1:{_SQX_PORT}"


def mock_mode_guard(force_mock: bool = False) -> None:
    """Guard against silent mock dispatch (MOK-01/02).

    Real mode (no mock) is a no-op. When dispatch would run in mock mode the
    warning is emitted BOTH through the module logger and stderr, so
    simulation can never happen silently. In ``QUANTLAB_ENV=production``,
    mock mode raises unless the operator explicitly opted in via
    ``SQX_FORCE_MOCK=1`` — an unforced ``dry_run`` or code-level mock flag is
    treated as an accident, not an override.
    """
    explicit_override = os.environ.get("SQX_FORCE_MOCK", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if not (force_mock or explicit_override):
        return

    warning = (
        "Mock mode active — dispatch results are simulated, not live SQX. "
        "Set SQX_FORCE_MOCK=1 to allow explicit simulation."
    )
    logger.warning(warning)
    print(f"WARNING: {warning}", file=sys.stderr)

    is_production = os.environ.get("QUANTLAB_ENV", "").lower() == "production"
    if is_production and not explicit_override:
        raise RuntimeError(
            "Mock mode is not allowed in production (QUANTLAB_ENV=production). "
            "Set SQX_FORCE_MOCK=1 to explicitly enable simulation."
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def dispatch_campaign(
    cfx_bytes: bytes,
    campaign_id: str,
    config: Any,
    *,
    sqx_install_path: str | None = None,
    poll_interval: float = _DEFAULT_POLL_INTERVAL,
    timeout: float = _DEFAULT_TIMEOUT,
    force_mock: bool = False,
    on_watcher_event: Callable[[WatcherEvent], None] | None = None,
    llm_config: LLMConfig | None = None,
    on_llm_verdict: Callable[[Verdict], None] | None = None,
    llm_caller: Callable[[str, LLMConfig], Awaitable[str]] | None = None,
    confirm_stop: Callable[[Verdict], Awaitable[bool]] | None = None,
    confidence_threshold: float = 0.7,
    poll_every_n: int = 5,
    build_config: Any = None,
    orchestrated: bool = False,
    gate_event_dir: str | None = None,
    webhook_url: str | None = None,
) -> dict[str, Any]:
    """Dispatch a campaign to SQX via the daemon-based HTTP API.

    Uses the real sqcli binary if available; otherwise falls back to the
    mock HTTP server.

    Args:
        cfx_bytes: Raw CFX archive bytes (used only for mock fallback).
            Real dispatch reads config directly from the ``config`` object.
        campaign_id: Unique campaign identifier (alphanumeric + hyphens).
        config: Campaign config (ResearchConfig). Used to extract DSL
            settings (market, timeframe, generations, criteria, etc.) and
            ``sqx_install_path``.
        sqx_install_path: Explicit path to SQX installation root.
        poll_interval: Seconds between status polls (default 10).
        timeout: Max seconds for strategy generation (default 1800).
        force_mock: Force mock server even if sqcli is available.
        on_watcher_event: Optional callback invoked for every WatcherEvent
            emitted by the background CampaignMonitor. When ``None``,
            WARNING/CRITICAL events trigger a ``rich.prompt.Confirm`` prompt.
        llm_config: Optional LLMConfig. When set, an
            ``LLMGenerationMonitor`` runs as a sibling task to the
            ``CampaignMonitor`` and LLM verdicts are produced on a slow
            cadence. When ``None`` (default), no LLM monitor is created and
            dispatch behaves exactly as before this change — zero LLM calls.
        on_llm_verdict: Optional callback invoked with every validated
            ``Verdict`` produced by the LLM monitor. Mirrors
            ``on_watcher_event``. Ignored when ``llm_config`` is ``None``.
        llm_caller: Optional async ``(prompt, llm_config) -> str`` caller
            for the LLM monitor (defaults to the built-in LLM provider
            call). Tests inject a fake caller here.
        confirm_stop: Optional async ``(verdict) -> bool`` hook for the
            human-confirmation step before a ``stop`` verdict is executed.
            ``None`` uses the monitor's default ``rich.prompt.Confirm``
            prompt (CLI mode).
        confidence_threshold: Minimum verdict confidence required to
            dispatch an action (default 0.7).
        poll_every_n: Run the LLM poll every N-th monitor tick (default 5).
        orchestrated: Orchestrated mode (REQ-20). Registers webhook + console
            notifiers and a gate writer on the spawned monitors, and appends
            a post-dispatch blocks-validation report (REQ-04) to the result.
            ``False`` keeps the legacy dispatch path byte-identical.
        gate_event_dir: Base directory for gate decision files (REQ-20).
            Used to write stall/error gate events in orchestrated mode.
        webhook_url: Webhook URL for the webhook notifier (REQ-15). Falls
            back to the ``QUANTLAB_WEBHOOK_URL`` environment variable.

    Returns:
        Dict with ``status`` (``"completed"``, ``"timeout"``,
        ``"failed"``), ``export_paths``, ``watcher_events``, and
        optionally ``error``. In orchestrated mode also ``blocks_report``.
    """
    if sqx_install_path is None:
        sqx_install_path = _resolve_sqx_install_path(config)

    sqx_install_path_str = str(sqx_install_path)
    sqcli_path = _find_sqcli(sqx_install_path_str)

    use_mock = (
        force_mock
        or os.environ.get("SQX_FORCE_MOCK", "").lower() in ("1", "true", "yes")
    )
    mock_mode_guard(force_mock=use_mock)

    try:
        if sqcli_path and not use_mock:
            return await _dispatch_real(
                sqx_install_path=sqx_install_path_str,
                campaign_id=campaign_id,
                config=config,
                poll_interval=poll_interval,
                timeout=timeout,
                on_watcher_event=on_watcher_event,
                llm_config=llm_config,
                on_llm_verdict=on_llm_verdict,
                llm_caller=llm_caller,
                confirm_stop=confirm_stop,
                confidence_threshold=confidence_threshold,
                poll_every_n=poll_every_n,
                build_config=build_config,
                orchestrated=orchestrated,
                gate_event_dir=gate_event_dir,
                webhook_url=webhook_url,
            )
        else:
            # Write CFX to temp file for mock path
            with tempfile.NamedTemporaryFile(delete=False, suffix=".cfx") as f:
                f.write(cfx_bytes if isinstance(cfx_bytes, bytes) else cfx_bytes.encode())
                temp_cfx = f.name
            try:
                return await _dispatch_mock(
                    sqx_install_path=sqx_install_path_str,
                    campaign_id=campaign_id,
                    temp_cfx=temp_cfx,
                    poll_interval=poll_interval,
                    timeout=timeout,
                    on_watcher_event=on_watcher_event,
                    llm_config=llm_config,
                    on_llm_verdict=on_llm_verdict,
                    llm_caller=llm_caller,
                    confirm_stop=confirm_stop,
                    confidence_threshold=confidence_threshold,
                    poll_every_n=poll_every_n,
                    build_config=build_config,
                    orchestrated=orchestrated,
                    gate_event_dir=gate_event_dir,
                    webhook_url=webhook_url,
                )
            finally:
                if os.path.exists(temp_cfx):
                    try:
                        os.unlink(temp_cfx)
                    except OSError:
                        pass

    except Exception as e:
        logger.error("dispatch_campaign('%s') failed: %s", campaign_id, e)
        return {
            "status": "failed",
            "export_paths": [],
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Real SQX dispatch
# ---------------------------------------------------------------------------


async def _dispatch_real(
    sqx_install_path: str,
    campaign_id: str,
    config: Any,
    poll_interval: float,
    timeout: float,
    *,
    on_watcher_event: Callable[[WatcherEvent], None] | None = None,
    llm_config: LLMConfig | None = None,
    on_llm_verdict: Callable[[Verdict], None] | None = None,
    llm_caller: Callable[[str, LLMConfig], Awaitable[str]] | None = None,
    confirm_stop: Callable[[Verdict], Awaitable[bool]] | None = None,
    confidence_threshold: float = 0.7,
    poll_every_n: int = 5,
    build_config: Any = None,
    orchestrated: bool = False,
    gate_event_dir: str | None = None,
    webhook_url: str | None = None,
) -> dict[str, Any]:
    """Dispatch using the real SQX daemon (sqcli without arguments).

    Flow:
        1. Create project directory from template (project_builder).
        2. Stop any existing daemon, start fresh (daemon scans projects
           at startup).
        3. Start campaign via HTTP API.
        4. Poll status until completion or timeout, with a concurrent
           CampaignMonitor watching for stall/error patterns.
        5. Stop project.
        6. Export databanks.
        7. Stop daemon.
        8. Collect and return watcher events.

    Args:
        sqx_install_path: Path to SQX installation.
        campaign_id: Campaign/project identifier.
        config: ResearchConfig with DSL settings (market, timeframe,
            strategies, criteria, building_blocks, etc.).
        poll_interval: Seconds between status polls.
        timeout: Max seconds for strategy generation.
        on_watcher_event: Optional callback for WatcherEvents. When
            ``None``, the monitor uses ``rich.prompt.Confirm`` prompts.
        llm_config: Optional LLMConfig enabling the LLM monitor sibling
            task (see :func:`dispatch_campaign`).
        on_llm_verdict: Optional hook invoked with every validated verdict.
        llm_caller: Optional injected LLM caller (tests).
        confirm_stop: Optional human-confirmation hook for stop verdicts.
        confidence_threshold: Minimum verdict confidence to dispatch.
        poll_every_n: LLM poll cadence (every N-th monitor tick).
        orchestrated: Orchestrated mode — registers notifiers + gate writer
            on the spawned monitors (REQ-15/REQ-20) and appends a
            post-dispatch blocks report (REQ-04).
        gate_event_dir: Gate decision-file base directory (REQ-20).
        webhook_url: Webhook URL for the webhook notifier (REQ-15).
    """
    base_url = _SQX_BASE_URL

    # ── License pre-flight (LIC-01/02): real path only, before any SQX work ──
    from quantlab.cli.runner import RealExecutor
    from quantlab.pipeline.license import license_preflight

    sqcli_binary = _find_sqcli(sqx_install_path)
    if sqcli_binary:
        license_preflight(RealExecutor(sqcli_binary))
    else:
        logger.warning(
            "sqcli binary not found for license pre-flight at '%s'", sqx_install_path
        )

    # ── Phase 0: Create project directory from template ──
    logger.info("Phase 0/6: Creating project '%s' from template ...", campaign_id)

    # Extract DSL settings from config
    cfg_dict = config if isinstance(config, dict) else vars(config)
    symbol = _get_config_value(cfg_dict, "market", "EURUSD")
    timeframe = _get_config_value(cfg_dict, "timeframe", "H1")
    campaign_name = _get_config_value(cfg_dict, "campaign", campaign_id)

    # Extract WF/MC flags for project builder and baseline computation
    walk_forward = bool(_get_config_value(cfg_dict, "walk_forward", True))
    monte_carlo = bool(_get_config_value(cfg_dict, "monte_carlo", True))

    # Extract genetic settings from strategies list if available
    generations = 80
    population = 200
    strategies = _get_config_value(cfg_dict, "strategies", [])
    if strategies and isinstance(strategies, list):
        s = strategies[0]
        if isinstance(s, dict):
            generations = int(s.get("generations", generations))
            population = int(s.get("population", population))
        elif hasattr(s, "generations"):
            generations = int(getattr(s, "generations", generations))
            population = int(getattr(s, "population", population))

    # Extract ranking criteria if available
    criteria = _get_config_value(cfg_dict, "criteria", [])
    pf = 1.3
    return_dd = 4.0
    avg_trades = 2
    for c in criteria:
        c_dict = c if isinstance(c, dict) else vars(c) if hasattr(c, "__dict__") else {}
        metric = c_dict.get("metric", "")
        op = c_dict.get("operator", ">=")
        val = float(c_dict.get("value", 0))
        if "profit" in metric.lower():
            pf = val
        elif "sharpe" in metric.lower() or "return" in metric.lower() or "dd" in metric.lower():
            return_dd = val
        elif "avg" in metric.lower() or "trades" in metric.lower():
            avg_trades = val

    try:
        create_project(
            sqx_install_path=sqx_install_path,
            campaign_id=campaign_id,
            symbol=symbol,
            timeframe=timeframe,
            date_from="2023.1.1",
            date_to="2024.12.31",
            generations=generations,
            population=population,
            rankings_min_profit_factor=pf,
            rankings_min_return_dd=return_dd,
            rankings_min_avg_trades=avg_trades,
            walk_forward=walk_forward,
            monte_carlo=monte_carlo,
            build_config=build_config,
        )
    except Exception as e:
        logger.error("Failed to create project: %s", e)
        return {"status": "failed", "export_paths": [], "error": f"project creation failed: {e}", "watcher_events": []}

    # ── Phase 0.5: Daemon lifecycle ──
    logger.info("Phase 0.5/6: Starting SQX daemon ...")
    daemon = _SQXDaemonHandle(sqx_install_path)
    try:
        daemon_ready = await daemon.start(base_url)
        if not daemon_ready:
            return {"status": "failed", "export_paths": [], "error": "daemon start failed", "watcher_events": []}
    except Exception as e:
        logger.error("Daemon start failed: %s", e)
        return {"status": "failed", "export_paths": [], "error": f"daemon start failed: {e}", "watcher_events": []}

    # ── Phase 1: Start campaign via HTTP API ──
    logger.info("Phase 1/6: Starting campaign '%s' ...", campaign_id)
    start_resp = await _send_http(base_url, f"-project action=start name={campaign_id}")
    if "Error" in start_resp[:100] or "does not exist" in start_resp:
        logger.error("Start failed: %s", start_resp[:300])
        await daemon.stop()
        return {"status": "failed", "export_paths": [], "error": f"start failed: {start_resp}", "watcher_events": []}

    # ── CampaignMonitor setup ──
    baseline = compute_baseline(cfg_dict, poll_interval=5.0)
    notifiers = _build_notifiers(webhook_url) if orchestrated else []
    gate_writer = _build_gate_writer(gate_event_dir, campaign_id) \
        if orchestrated else None
    monitor = CampaignMonitor(
        campaign_id=campaign_id,
        base_url=base_url,
        baseline=baseline,
        on_watcher_event=on_watcher_event,
        config=cfg_dict,
        export_dir=f"/tmp/sqx-exports/{campaign_id}",
        gate_writer=gate_writer,
    )
    for notifier in notifiers:
        monitor.add_notifier(notifier)
    monitor_task = asyncio.create_task(monitor.run())

    # ── Optional LLM monitor (opt-in via llm_config) ──
    llm_monitor_task = _spawn_llm_monitor(
        campaign_id=campaign_id,
        base_url=base_url,
        monitor=monitor,
        llm_config=llm_config,
        on_llm_verdict=on_llm_verdict,
        llm_caller=llm_caller,
        confirm_stop=confirm_stop,
        confidence_threshold=confidence_threshold,
        poll_every_n=poll_every_n,
        orchestrated=orchestrated,
        notifiers=notifiers,
    )

    # ── Phase 2: Poll status ──
    logger.info("Phase 2/6: Polling status for '%s' ...", campaign_id)
    deadline = time.monotonic() + timeout
    is_completed = False
    try:
        while time.monotonic() < deadline:
            status_text = await _send_http(base_url, f"-project action=status name={campaign_id}")
            # Check if still running — if the "In databank" line shows strategies
            if "Project execution stopped" in status_text:
                is_completed = True
                logger.info("Campaign '%s' completed (project stopped)!", campaign_id)
                break
            if _is_completed(status_text):
                is_completed = True
                logger.info("Campaign '%s' completed!", campaign_id)
                break
            await asyncio.sleep(poll_interval)
    finally:
        # Always cancel the monitor when the poll loop exits; a final
        # status check emits a missed campaign_complete when the loop saw
        # completion before the monitor's own done-check poll ran.
        await monitor.cancel()
        await monitor.final_check()
        watcher_events: list[dict[str, Any]] = []
        try:
            collected = await asyncio.wait_for(monitor_task, timeout=5.0)
            watcher_events = [e.to_dict() for e in collected]
        except (asyncio.TimeoutError, asyncio.CancelledError):
            watcher_events = [e.to_dict() for e in monitor._events]
        if llm_monitor_task is not None:
            await _stop_llm_monitor_task(llm_monitor_task)

    if not is_completed:
        logger.warning("Campaign '%s' timed out after %.0fs", campaign_id, timeout)

    # ── Phase 3: Stop project ──
    logger.info("Phase 3/6: Stopping campaign '%s' ...", campaign_id)
    try:
        await _send_http(base_url, f"-project action=stop name={campaign_id}")
    except Exception as e:
        logger.warning("Stop failed: %s", e)

    # ── Phase 4: Export databanks ──
    export_paths: list[str] = []
    try:
        logger.info("Phase 4/6: Exporting databanks for '%s' ...", campaign_id)
        export_dir = Path(f"/tmp/sqx-exports/{campaign_id}")
        export_dir.mkdir(parents=True, exist_ok=True)
        export_file = str(export_dir / "strategies.csv")
        await _send_http(
            base_url,
            f"-databank action=export project={campaign_id} name=Results file={export_file}",
        )
        if os.path.isfile(export_file):
            export_paths.append(export_file)
    except Exception as e:
        logger.warning("Export failed: %s", e)

    # Also collect from SQX-standard paths
    export_paths = list(set(export_paths + _collect_exports(sqx_install_path, campaign_id)))

    # ── Phase 5: Stop daemon ──
    logger.info("Phase 5/6: Stopping daemon ...")
    try:
        await daemon.stop()
    except Exception as e:
        logger.warning("Daemon stop failed: %s", e)

    status = "completed" if is_completed else "timeout"
    result: dict[str, Any] = {
        "status": status,
        "export_paths": export_paths,
        "watcher_events": watcher_events,
    }
    if orchestrated:
        result["blocks_report"] = _validate_blocks(build_config, export_paths)
    return result


# ── Lightweight daemon handle for cli_wrapper ──


class _SQXDaemonHandle:
    """Minimal handle to start/stop the sqcli daemon.

    Uses subprocess to launch sqcli (no arguments) and monitors its
    HTTP API readiness.
    """

    def __init__(self, sqx_install_path: str) -> None:
        self.sqx_install_path = sqx_install_path
        self._proc: asyncio.subprocess.Process | None = None

    async def start(self, base_url: str) -> bool:
        """Stop any existing process on the port, start sqcli daemon."""
        # Kill any process on the port
        proc = await asyncio.create_subprocess_exec(
            "fuser", "-k", f"{_SQX_PORT}/tcp",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        await asyncio.sleep(1)

        # Start sqcli with no arguments (daemon mode)
        sqcli = Path(self.sqx_install_path) / "sqcli"
        java_home = str(Path(self.sqx_install_path) / "j64")

        self._proc = await asyncio.create_subprocess_exec(
            str(sqcli),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env={**os.environ, "JAVA_HOME": java_home},
        )

        # Wait for HTTP API readiness.  The daemon can take 90-105s to
        # become ready (it loads legacy projects at startup), so the
        # deadline honors QUANTLAB_SQCLI_TIMEOUT (default 180s).
        from quantlab.cli.runner import resolve_sqcli_timeout

        deadline = time.monotonic() + resolve_sqcli_timeout()
        async with httpx.AsyncClient(timeout=5.0) as client:
            while time.monotonic() < deadline:
                if self._proc.returncode is not None:
                    logger.error("sqcli exited early (code %s)", self._proc.returncode)
                    return False
                try:
                    resp = await client.get(f"{base_url}/call?cmd=-h")
                    if resp.status_code == 200:
                        body = resp.text
                        if "Usage" in body and "not ready" not in body.lower():
                            logger.info("SQX daemon ready at %s", base_url)
                            return True
                except Exception:
                    pass
                await asyncio.sleep(1)

        logger.error(
            "SQX daemon not ready after %.0fs", resolve_sqcli_timeout()
        )
        return False

    async def stop(self) -> None:
        """Stop the daemon process."""
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                self._proc.kill()
                await self._proc.wait()

        # Also ensure port is free
        proc = await asyncio.create_subprocess_exec(
            "fuser", "-k", f"{_SQX_PORT}/tcp",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

    def __del__(self) -> None:
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.kill()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Mock dispatch
# ---------------------------------------------------------------------------


async def _dispatch_mock(
    sqx_install_path: str,
    campaign_id: str,
    temp_cfx: str,
    poll_interval: float,
    timeout: float,
    *,
    on_watcher_event: Callable[[WatcherEvent], None] | None = None,
    llm_config: LLMConfig | None = None,
    on_llm_verdict: Callable[[Verdict], None] | None = None,
    llm_caller: Callable[[str, LLMConfig], Awaitable[str]] | None = None,
    confirm_stop: Callable[[Verdict], Awaitable[bool]] | None = None,
    confidence_threshold: float = 0.7,
    poll_every_n: int = 5,
    build_config: Any = None,
    orchestrated: bool = False,
    gate_event_dir: str | None = None,
    webhook_url: str | None = None,
) -> dict[str, Any]:
    """Dispatch using the mock HTTP server (no real sqcli required).

    Also spawns a CampaignMonitor for E2E integration testing. In
    orchestrated mode mirrors the real path's notifier/gate-writer wiring
    and post-dispatch blocks validation (REQ-04/REQ-15/REQ-20).
    """
    base_url = await _ensure_mock_server()

    # Create project directory (versioned dirs must exist for E2E assertions)
    try:
        create_project(
            sqx_install_path=sqx_install_path,
            campaign_id=campaign_id,
            build_config=build_config,
        )
    except Exception as exc:
        logger.warning("Mock project creation failed: %s", exc)

    # Load config
    await _send_http(base_url, f"-project action=loadconfig name={campaign_id} file={temp_cfx}")

    # Start project
    await _send_http(base_url, f"-project action=start name={campaign_id}")

    # ── CampaignMonitor setup — poll faster than dispatch loop ──
    monitor_poll = max(0.5, poll_interval / 2)
    baseline = compute_baseline({"timeframe": "H1"}, poll_interval=monitor_poll)
    notifiers = _build_notifiers(webhook_url) if orchestrated else []
    gate_writer = _build_gate_writer(gate_event_dir, campaign_id) \
        if orchestrated else None
    monitor = CampaignMonitor(
        campaign_id=campaign_id,
        base_url=base_url,
        baseline=baseline,
        poll_interval=monitor_poll,
        on_watcher_event=on_watcher_event,
        config={"timeframe": "H1"},
        export_dir=f"/tmp/sqx-exports/{campaign_id}",
        gate_writer=gate_writer,
    )
    for notifier in notifiers:
        monitor.add_notifier(notifier)
    monitor_task = asyncio.create_task(monitor.run())

    # ── Optional LLM monitor (opt-in via llm_config) ──
    llm_monitor_task = _spawn_llm_monitor(
        campaign_id=campaign_id,
        base_url=base_url,
        monitor=monitor,
        llm_config=llm_config,
        on_llm_verdict=on_llm_verdict,
        llm_caller=llm_caller,
        confirm_stop=confirm_stop,
        confidence_threshold=confidence_threshold,
        poll_every_n=poll_every_n,
        orchestrated=orchestrated,
        notifiers=notifiers,
    )

    # Poll status
    deadline = time.monotonic() + timeout
    is_completed = False
    try:
        while time.monotonic() < deadline:
            status_text = await _send_http(
                base_url, f"-project action=status name={campaign_id}"
            )
            # Parity with _dispatch_real: an explicit stop (e.g. from the
            # LLM monitor) shows as "Project execution stopped".
            if "Project execution stopped" in status_text:
                is_completed = True
                logger.info("Campaign '%s' stopped — ending dispatch", campaign_id)
                break
            if _is_completed(status_text):
                is_completed = True
                break
            await asyncio.sleep(poll_interval)
    finally:
        # Always cancel the monitor when the poll loop exits; a final
        # status check emits a missed campaign_complete when the loop saw
        # completion before the monitor's own done-check poll ran.
        await monitor.cancel()
        await monitor.final_check()
        watcher_events: list[dict[str, Any]] = []
        try:
            collected = await asyncio.wait_for(monitor_task, timeout=5.0)
            watcher_events = [e.to_dict() for e in collected]
        except (asyncio.TimeoutError, asyncio.CancelledError):
            watcher_events = [e.to_dict() for e in monitor._events]
        if llm_monitor_task is not None:
            await _stop_llm_monitor_task(llm_monitor_task)

    # Stop
    try:
        await _send_http(base_url, f"-project action=stop name={campaign_id}")
    except Exception:
        pass

    # Export
    try:
        await _send_http(base_url, f"-databank action=export project={campaign_id}")
    except Exception:
        pass

    export_paths = _collect_exports(sqx_install_path, campaign_id)
    result: dict[str, Any] = {
        "status": "completed" if is_completed else "timeout",
        "export_paths": export_paths,
        "watcher_events": watcher_events,
    }
    if orchestrated:
        result["blocks_report"] = _validate_blocks(build_config, export_paths)
    return result


# ---------------------------------------------------------------------------
# LLM monitor helpers
# ---------------------------------------------------------------------------


def _spawn_llm_monitor(
    *,
    campaign_id: str,
    base_url: str,
    monitor: CampaignMonitor,
    llm_config: LLMConfig | None,
    on_llm_verdict: Callable[[Verdict], None] | None,
    llm_caller: Callable[[str, LLMConfig], Awaitable[str]] | None,
    confirm_stop: Callable[[Verdict], Awaitable[bool]] | None,
    confidence_threshold: float,
    poll_every_n: int,
    orchestrated: bool = False,
    notifiers: list[Any] | None = None,
) -> asyncio.Task[None] | None:
    """Spawn the optional LLM monitor as a sibling task to CampaignMonitor.

    Returns ``None`` when ``llm_config`` is ``None`` — the opt-in hook is
    disabled and dispatch behaves exactly as before (spec: "Hook not
    registered preserves behavior", zero LLM calls).

    In orchestrated mode (REQ-15) the webhook/console notifiers are
    registered on the LLM monitor so verdicts fan out through the same
    channels as watcher events.
    """
    if llm_config is None:
        return None

    llm_monitor = LLMGenerationMonitor(
        campaign_id=campaign_id,
        base_url=base_url,
        snapshot_provider=monitor.current_snapshot,
        llm_config=llm_config,
        llm_caller=llm_caller,
        confirm_stop=confirm_stop,
        confidence_threshold=confidence_threshold,
        poll_every_n=poll_every_n,
        on_verdict=on_llm_verdict,
        monitor=monitor,
    )
    if orchestrated:
        for notifier in notifiers or []:
            llm_monitor.add_notifier(notifier)
    return asyncio.create_task(llm_monitor.run())


async def _stop_llm_monitor_task(llm_monitor_task: asyncio.Task[None]) -> None:
    """Cancel and reap the LLM monitor task when the dispatch loop exits.

    The dispatch loop ending means the campaign is finished or stopped —
    the LLM monitor has nothing left to do, so an immediate cancel is safe
    (all its poll paths degrade to log-and-continue; none mutate campaign
    state outside the already-handled stop action).
    """
    llm_monitor_task.cancel()
    await asyncio.gather(llm_monitor_task, return_exceptions=True)


# ---------------------------------------------------------------------------
# Orchestrated monitor wiring helpers (REQ-04/REQ-15/REQ-20)
# ---------------------------------------------------------------------------


def _build_notifiers(webhook_url: str | None) -> list[Any]:
    """Build the notifier fanout for orchestrated dispatch (REQ-15).

    Always includes a console notifier. A webhook notifier is added when a
    URL is provided explicitly or via ``QUANTLAB_WEBHOOK_URL`` (design open
    question resolved: env default).
    """
    notifiers: list[Any] = [ConsoleNotifier()]
    url = webhook_url or os.environ.get("QUANTLAB_WEBHOOK_URL")
    if url:
        notifiers.append(WebhookNotifier(url))
    return notifiers


def _build_gate_writer(
    gate_event_dir: str | None, campaign_id: str
) -> Callable[[WatcherEvent], None] | None:
    """Build the gate decision-file writer for monitor events (REQ-20).

    WARNING/CRITICAL watcher events are surfaced as pending gate files in
    ``{gate_event_dir}/{campaign_id}/{gate_id}.pending.json`` so the OpenCode
    agent (or any gate resolver) can act on them. Returns ``None`` when no
    ``gate_event_dir`` is configured — the monitor then falls back to its
    CLI prompt path (legacy behavior).
    """
    if not gate_event_dir:
        return None
    from quantlab.gates.callbacks import write_pending

    def writer(event: WatcherEvent) -> None:
        try:
            write_pending(
                gate_event_dir,
                campaign_id,
                f"campaign_{event.event_type}",
                {"event": event.to_dict()},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Gate writer for '%s' failed (%s): %s",
                campaign_id,
                event.event_type,
                exc,
            )

    return writer


def _exported_strategy_names(export_paths: list[str]) -> list[str]:
    """Collect strategy names from exported ``strategies.csv`` files.

    Returns ``[]`` when no CSV export is available — the post-dispatch
    blocks report then flags every intended block as missing (REQ-04).
    """
    from quantlab.sqx.campaign_monitor import parse_strategy_counts_csv

    names: list[str] = []
    for path in export_paths:
        if not path.endswith(".csv"):
            continue
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError:
            continue
        names.extend(parse_strategy_counts_csv(text).keys())
    return sorted(set(names))


def _validate_blocks(
    build_config: Any, export_paths: list[str]
) -> dict[str, Any]:
    """Validate exported strategies against intended blocks (REQ-04).

    Builds the ``blocks_report`` for orchestrated dispatch results:
    ``{"ok": bool, "missing": [block names]}``. ``ok`` is ``True`` when no
    intended blocks are missing from the exports (no CSV export ⇒ all
    intended blocks missing).
    """
    intended = list(getattr(build_config, "enabled_blocks", []) or [])
    report = validate_exported_blocks(_exported_strategy_names(export_paths), intended)
    return {"ok": report.ok, "missing": report.missing}


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _find_sqcli(sqx_install_path: str) -> str | None:
    """Locate the ``sqcli`` binary.

    Returns the absolute path, or ``None`` if not found.
    """
    install = Path(sqx_install_path)
    candidates = [
        install / "sqcli",
        install / "sqcli.exe",
        install / "sqcli.sh",
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c.resolve())
    return None


def _get_config_value(cfg: dict[str, Any], key: str, default: Any = None) -> Any:
    """Extract a config value, handling enum types and nested access."""
    val = cfg.get(key, default) if isinstance(cfg, dict) else getattr(cfg, key, default)
    if hasattr(val, "value"):
        return val.value
    return val


# ---------------------------------------------------------------------------
# Mock server helpers
# ---------------------------------------------------------------------------


async def _ensure_mock_server() -> str:
    """Start (or re-use) the mock SQX server and return its base URL."""
    base_url = "http://127.0.0.1:5050"

    # Quick check if mock is already running
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{base_url}/call?cmd=-h")
            if resp.status_code == 200:
                return base_url
    except Exception:
        pass

    # Start mock
    MockSQXServer.reset()
    await asyncio.sleep(0.3)
    server = MockSQXServer.instance(port=5050)
    server.start()

    for attempt in range(10):
        await asyncio.sleep(1.5 * (attempt + 1))
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base_url}/call?cmd=-h")
                if resp.status_code == 200 and "Usage" in resp.text:
                    logger.info("Mock SQX server ready at %s", base_url)
                    return base_url
        except Exception:
            continue

    raise RuntimeError("Mock SQX server did not start")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


async def _send_http(base_url: str, command: str) -> str:
    """Send a single command to the SQX HTTP API."""
    encoded = urllib.parse.quote(command, safe="=")
    url = f"{base_url}{_COMMAND_ENDPOINT}{encoded}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text

    if "Error:" in text[:100]:
        logger.warning("SQX HTTP API error for '%s': %s", command[:80], text[:200])
    return text


# ---------------------------------------------------------------------------
# Config / filesystem helpers
# ---------------------------------------------------------------------------


def _resolve_sqx_install_path(config: Any) -> str:
    """Extract SQX install path from config, env var, or default."""
    if hasattr(config, "sqx_install_path"):
        return str(config.sqx_install_path)
    if isinstance(config, dict) and "sqx_install_path" in config:
        return str(config["sqx_install_path"])
    env_path = os.environ.get("SQX_INSTALL_PATH")
    if env_path:
        return env_path
    return "assets/SQX_144_2953_linux_20260601"


def _collect_exports(sqx_install_path: str, campaign_id: str) -> list[str]:
    """Collect exported files from expected SQX directories."""
    base = Path(sqx_install_path)
    export_paths: list[str] = []

    for pattern in _EXPORT_DIRS:
        export_dir = base / pattern.format(campaign_id=campaign_id)
        if not export_dir.is_dir():
            continue
        for f in export_dir.iterdir():
            if f.is_file():
                export_paths.append(str(f))

    if not export_paths:
        logger.warning("No exports found for '%s' in %s", campaign_id, sqx_install_path)

    return sorted(export_paths)


def _is_completed(status_text: str) -> bool:
    """Check if status text indicates project completion."""
    text = status_text.lower()
    return any(term in text for term in ("completed", "finished", "done", "success"))
