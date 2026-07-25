"""Real SQX CLI wrapper — dispatches CFX campaigns to a live SQX instance.

Architecture
------------
SQX does NOT run as a persistent daemon. Each sqcli invocation starts the
Java backend, processes a command, and exits — the backend process also
exits when sqcli finishes.

The one exception is ``-project action=start``: sqcli stays alive for the
duration of the strategy generation (minutes to hours), and the HTTP API
on port 5050 is available DURING that window. This wrapper exploits that
window to dispatch ``loadconfig`` → ``start`` → poll ``status`` via HTTP →
``stop`` → ``export`` → collect files.

When the real sqcli binary is unavailable, the wrapper falls back to a
lightweight mock server (``MockSQXServer``) so demos can run end-to-end.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal
import subprocess
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx

from quantlab.sqx.mock_sqx_server import MockSQXServer

logger = logging.getLogger(__name__)

_DEFAULT_POLL_INTERVAL = 10.0
_DEFAULT_TIMEOUT = 900.0  # 15 minutes (sqcli takes ~60s to start)

_EXPORT_DIRS = [
    "user/projects/{campaign_id}/exports",
    "user/settings/Exports/{campaign_id}",
    "/tmp/sqx-exports/{campaign_id}",
]

_COMMAND_ENDPOINT = "/call?cmd="

_SQCLI_READY_TIMEOUT = 60.0  # max seconds to wait for HTTP API after sqcli start


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
) -> dict[str, Any]:
    """Dispatch a CFX campaign to SQX.

    Uses the real sqcli binary if available; otherwise falls back to the
    mock HTTP server.

    Args:
        cfx_bytes: Raw CFX archive bytes.
        campaign_id: Unique campaign identifier (alphanumeric + hyphens
            recommended — avoid spaces).
        config: Campaign configuration object. Used to extract
            ``sqx_install_path`` if not explicitly provided.
        sqx_install_path: Explicit path to the SQX installation root.
            Falls back to ``config.sqx_install_path``, then
            ``SQX_INSTALL_PATH`` env var, then the default path.
        poll_interval: Seconds between status polls (default 10).
        timeout: Max seconds to wait for strategy generation (default 300).

    Returns:
        Dict with ``status`` (``"completed"``, ``"timeout"``, or
        ``"failed"``), ``export_paths`` (list of exported file paths),
        and optionally ``error`` (description on failure).
    """
    if sqx_install_path is None:
        sqx_install_path = _resolve_sqx_install_path(config)

    sqcli_path = _find_sqcli(sqx_install_path)

    temp_cfx: str | None = None
    try:
        # --- Write CFX to temp file ---
        with tempfile.NamedTemporaryFile(delete=False, suffix=".cfx") as f:
            f.write(cfx_bytes)
            temp_cfx = f.name
        logger.info("Wrote CFX (%d bytes) to %s", len(cfx_bytes), temp_cfx)

        if sqcli_path:
            return await _dispatch_real(
                sqcli_path=sqcli_path,
                sqx_install_path=sqx_install_path,
                campaign_id=campaign_id,
                temp_cfx=temp_cfx,
                poll_interval=poll_interval,
                timeout=timeout,
            )
        else:
            return await _dispatch_mock(
                sqx_install_path=sqx_install_path,
                campaign_id=campaign_id,
                temp_cfx=temp_cfx,
                poll_interval=poll_interval,
                timeout=timeout,
            )

    except Exception as e:
        logger.error("dispatch_campaign('%s') failed: %s", campaign_id, e)
        return {
            "status": "failed",
            "export_paths": [],
            "error": str(e),
        }
    finally:
        if temp_cfx and os.path.exists(temp_cfx):
            try:
                os.unlink(temp_cfx)
                logger.debug("Removed temp CFX %s", temp_cfx)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Real SQX dispatch
# ---------------------------------------------------------------------------


async def _dispatch_real(
    sqcli_path: str,
    sqx_install_path: str,
    campaign_id: str,
    temp_cfx: str,
    poll_interval: float,
    timeout: float,
) -> dict[str, Any]:
    """Dispatch using the real sqcli binary.

    Flow:
        1. ``loadconfig`` — import the CFX into a new SQX project.
        2. ``start`` in background — begin strategy generation.
        3. Poll ``status`` via HTTP while sqcli is alive.
        4. ``stop`` via HTTP when done (or on timeout).
        5. ``export`` databanks via HTTP.
        6. Collect exported files from the filesystem.
    """
    # --- Phase 1: Load config (sync) ---
    logger.info("Phase 1/5: Loading config for '%s' ...", campaign_id)
    load_ok = await _run_sqcli_command(
        sqcli_path,
        f'-project action=loadconfig name={campaign_id} file={temp_cfx}',
        ready_timeout=_SQCLI_READY_TIMEOUT,
    )
    if not load_ok:
        return {"status": "failed", "export_paths": [], "error": "sqcli loadconfig failed"}

    # --- Phase 2: Start project in background ---
    logger.info("Phase 2/5: Starting campaign '%s' ...", campaign_id)
    bg_proc = await _start_sqcli_background(
        sqcli_path,
        f'-project action=start name={campaign_id}',
        ready_timeout=_SQCLI_READY_TIMEOUT,
    )
    if bg_proc is None:
        return {"status": "failed", "export_paths": [], "error": "sqcli start failed"}

    base_url = "http://127.0.0.1:5050"

    # --- Phase 3: Poll status ---
    logger.info("Phase 3/5: Polling status for '%s' ...", campaign_id)
    deadline = time.monotonic() + timeout
    is_completed = False
    while time.monotonic() < deadline:
        # Check process liveness
        if bg_proc.returncode is not None:
            logger.warning("sqcli exited unexpectedly (code %s)", bg_proc.returncode)
            break

        status_text = await _send_http(base_url, f"-project action=status name={campaign_id}")
        logger.debug("Status for '%s': %s", campaign_id, status_text[:200])
        if _is_completed(status_text):
            is_completed = True
            logger.info("Campaign '%s' completed!", campaign_id)
            break
        await asyncio.sleep(poll_interval)

    if not is_completed:
        logger.warning("Campaign '%s' timed out after %.0fs", campaign_id, timeout)

    # --- Phase 4: Stop project ---
    logger.info("Phase 4/5: Stopping campaign '%s' ...", campaign_id)
    try:
        await _send_http(base_url, f"-project action=stop name={campaign_id}")
    except Exception as e:
        logger.warning("Stop command failed: %s", e)

    # --- Phase 5: Export databanks ---
    export_paths: list[str] = []
    try:
        logger.info("Phase 5/5: Exporting databanks for '%s' ...", campaign_id)
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
        logger.warning("Export command failed: %s", e)
    finally:
        # Also collect from SQX-standard paths
        export_paths = list(set(export_paths + _collect_exports(sqx_install_path, campaign_id)))
    status = "completed" if is_completed else "timeout"

    # Gracefully let sqcli finish
    try:
        _graceful_stop(bg_proc)
    except Exception:
        pass

    return {"status": status, "export_paths": export_paths}


# ---------------------------------------------------------------------------
# Mock dispatch
# ---------------------------------------------------------------------------


async def _dispatch_mock(
    sqx_install_path: str,
    campaign_id: str,
    temp_cfx: str,
    poll_interval: float,
    timeout: float,
) -> dict[str, Any]:
    """Dispatch using the mock HTTP server (no real sqcli required)."""
    base_url = await _ensure_mock_server()

    # Load config
    await _send_http(base_url, f"-project action=loadconfig name={campaign_id} file={temp_cfx}")

    # Start project
    await _send_http(base_url, f"-project action=start name={campaign_id}")

    # Poll status
    deadline = time.monotonic() + timeout
    is_completed = False
    while time.monotonic() < deadline:
        status_text = await _send_http(
            base_url, f"-project action=status name={campaign_id}"
        )
        if _is_completed(status_text):
            is_completed = True
            break
        await asyncio.sleep(poll_interval)

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
    return {"status": "completed" if is_completed else "timeout", "export_paths": export_paths}


# ---------------------------------------------------------------------------
# sqcli process helpers
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
        Path(shutil.which("sqcli") or "/nonexistent"),
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c.resolve())
    return None


async def _run_sqcli_command(
    sqcli_path: str,
    command: str,
    *,
    ready_timeout: float = _SQCLI_READY_TIMEOUT,
) -> bool:
    """Run a sqcli command synchronously and wait for completion.

    Returns ``True`` if the command succeeded (exit code 0).
    """
    logger.debug("sqcli command: %s %s", sqcli_path, command)
    proc = await asyncio.create_subprocess_exec(
        sqcli_path,
        *command.split(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={**os.environ, "JAVA_HOME": _resolve_java_home(sqcli_path)},
    )

    try:
        stdout_bytes, _ = await asyncio.wait_for(
            proc.communicate(), timeout=ready_timeout + 60
        )
    except asyncio.TimeoutError:
        logger.error("sqcli command timed out: %s", command)
        _kill_process(proc)
        return False

    ret = proc.returncode
    if ret != 0:
        logger.error(
            "sqcli command failed (exit %s): %s\n%s",
            ret,
            command,
            stdout_bytes.decode(errors="replace")[:500],
        )
        return False

    logger.debug("sqcli command OK (exit 0): %s", command[:120])
    return True


async def _start_sqcli_background(
    sqcli_path: str,
    command: str,
    *,
    ready_timeout: float = _SQCLI_READY_TIMEOUT,
) -> asyncio.subprocess.Process | None:
    """Start sqcli in background and wait for the HTTP API to become ready.

    Returns the process handle if successful, or ``None`` on failure.
    The HTTP API on port 5050 will be available after this returns.
    """
    logger.debug("sqcli background: %s %s", sqcli_path, command)
    proc = await asyncio.create_subprocess_exec(
        sqcli_path,
        *command.split(),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        env={**os.environ, "JAVA_HOME": _resolve_java_home(sqcli_path)},
    )

    # Poll until HTTP API is ready or timeout
    base_url = "http://127.0.0.1:5050"
    deadline = time.monotonic() + ready_timeout
    while time.monotonic() < deadline:
        ret = proc.returncode
        if ret is not None:
            logger.error("sqcli background process exited early (code %s)", ret)
            return None

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base_url}/call?cmd=-h")
                if resp.status_code == 200 and "Usage" in resp.text:
                    logger.info("sqcli HTTP API ready at %s", base_url)
                    return proc
        except (httpx.ConnectError, httpx.TimeoutException):
            pass

        await asyncio.sleep(2)

    logger.error("sqcli HTTP API did not become ready within %.0fs", ready_timeout)
    _kill_process(proc)
    return None


def _resolve_java_home(sqcli_path: str) -> str:
    """Resolve JAVA_HOME from the sqcli installation directory."""
    sqx_dir = Path(sqcli_path).parent.resolve()
    j64 = sqx_dir / "j64"
    if j64.is_dir() and (j64 / "bin" / "java").is_file():
        return str(j64)
    return os.environ.get("JAVA_HOME", "")


def _kill_process(proc: asyncio.subprocess.Process) -> None:
    """Kill a subprocess gracefully, then forcefully."""
    if proc.returncode is not None:
        return
    try:
        proc.send_signal(signal.SIGTERM)
        for _ in range(10):
            if proc.returncode is not None:
                return
            time.sleep(0.5)
        proc.kill()
    except ProcessLookupError:
        pass


def _graceful_stop(proc: asyncio.subprocess.Process) -> None:
    """Wait for sqcli to exit, then kill if it doesn't."""
    if proc.returncode is not None:
        return
    try:
        for _ in range(30):  # up to 15 seconds
            if proc.returncode is not None:
                return
            time.sleep(0.5)
        _kill_process(proc)
    except ProcessLookupError:
        pass


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
