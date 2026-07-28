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
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any, Callable

import httpx

from quantlab.sqx.campaign_monitor import CampaignMonitor, WatcherEvent, compute_baseline
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

_DAEMON_START_TIMEOUT = 60.0  # max seconds for daemon to become ready
_SQX_PORT = 5050
_SQX_BASE_URL = f"http://127.0.0.1:{_SQX_PORT}"


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

    Returns:
        Dict with ``status`` (``"completed"``, ``"timeout"``,
        ``"failed"``), ``export_paths``, ``watcher_events``, and
        optionally ``error``.
    """
    if sqx_install_path is None:
        sqx_install_path = _resolve_sqx_install_path(config)

    sqx_install_path_str = str(sqx_install_path)
    sqcli_path = _find_sqcli(sqx_install_path_str)

    use_mock = (
        force_mock
        or os.environ.get("SQX_FORCE_MOCK", "").lower() in ("1", "true", "yes")
    )

    try:
        if sqcli_path and not use_mock:
            return await _dispatch_real(
                sqx_install_path=sqx_install_path_str,
                campaign_id=campaign_id,
                config=config,
                poll_interval=poll_interval,
                timeout=timeout,
                on_watcher_event=on_watcher_event,
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
    """
    base_url = _SQX_BASE_URL

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
    monitor = CampaignMonitor(
        campaign_id=campaign_id,
        base_url=base_url,
        baseline=baseline,
        on_watcher_event=on_watcher_event,
    )
    monitor_task = asyncio.create_task(monitor.run())

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
        # Always cancel the monitor when the poll loop exits
        await monitor.cancel()
        watcher_events: list[dict[str, Any]] = []
        try:
            collected = await asyncio.wait_for(monitor_task, timeout=5.0)
            watcher_events = [e.to_dict() for e in collected]
        except (asyncio.TimeoutError, asyncio.CancelledError):
            watcher_events = [e.to_dict() for e in monitor._events]

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
    return {"status": status, "export_paths": export_paths, "watcher_events": watcher_events}


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

        # Wait for HTTP API readiness
        deadline = time.monotonic() + _DAEMON_START_TIMEOUT
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

        logger.error("SQX daemon not ready after %.0fs", _DAEMON_START_TIMEOUT)
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
) -> dict[str, Any]:
    """Dispatch using the mock HTTP server (no real sqcli required).

    Also spawns a CampaignMonitor for E2E integration testing.
    """
    base_url = await _ensure_mock_server()

    # Load config
    await _send_http(base_url, f"-project action=loadconfig name={campaign_id} file={temp_cfx}")

    # Start project
    await _send_http(base_url, f"-project action=start name={campaign_id}")

    # ── CampaignMonitor setup — poll faster than dispatch loop ──
    monitor_poll = max(0.5, poll_interval / 2)
    baseline = compute_baseline({"timeframe": "H1"}, poll_interval=monitor_poll)
    monitor = CampaignMonitor(
        campaign_id=campaign_id,
        base_url=base_url,
        baseline=baseline,
        poll_interval=monitor_poll,
        on_watcher_event=on_watcher_event,
    )
    monitor_task = asyncio.create_task(monitor.run())

    # Poll status
    deadline = time.monotonic() + timeout
    is_completed = False
    try:
        while time.monotonic() < deadline:
            status_text = await _send_http(
                base_url, f"-project action=status name={campaign_id}"
            )
            if _is_completed(status_text):
                is_completed = True
                break
            await asyncio.sleep(poll_interval)
    finally:
        # Always cancel the monitor when the poll loop exits
        await monitor.cancel()
        watcher_events: list[dict[str, Any]] = []
        try:
            collected = await asyncio.wait_for(monitor_task, timeout=5.0)
            watcher_events = [e.to_dict() for e in collected]
        except (asyncio.TimeoutError, asyncio.CancelledError):
            watcher_events = [e.to_dict() for e in monitor._events]

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
    return {
        "status": "completed" if is_completed else "timeout",
        "export_paths": export_paths,
        "watcher_events": watcher_events,
    }


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
