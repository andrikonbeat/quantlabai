"""Dashboard CLI commands — serve and manage the web UI."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from quantlab.dashboard.app import DashboardServer, ServerConfig

# Env var to override the PID file location (mainly for tests and packagers).
PID_FILE_ENV = "QUANTLAB_PID_FILE"
DEFAULT_PID_FILE = Path.home() / ".quantlab" / "dashboard.pid"


def _default_pid_file() -> Path:
    """Resolve the PID file path, honouring the QUANTLAB_PID_FILE override."""
    override = os.environ.get(PID_FILE_ENV)
    return Path(override) if override else DEFAULT_PID_FILE


def _pid_alive(pid: int) -> bool:
    """Return True if a process with the given PID is running."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Exists but owned by another user — treat as alive.
        return True
    except OSError:
        return False
    return True


def write_pid_file(pid_file: Path, pid: int | None = None, started_at: str | None = None) -> Path:
    """Persist the running dashboard PID and start time to the PID file."""
    payload = {
        "pid": pid if pid is not None else os.getpid(),
        "started_at": started_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return pid_file


def read_pid_file(pid_file: Path) -> dict | None:
    """Read and parse the PID file, returning None when missing/invalid."""
    try:
        payload = json.loads(pid_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("pid"), int):
        return None
    return payload


def _uptime_s(started_at: str | None) -> float | None:
    """Seconds since the recorded start time, or None when unparseable."""
    if not started_at:
        return None
    try:
        start = datetime.fromisoformat(started_at)
    except (ValueError, TypeError):
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return max(0.0, time.time() - start.timestamp())


def status(pid_file: Path) -> dict:
    """Report dashboard status, removing stale PID files."""
    payload = read_pid_file(pid_file)
    if payload is None:
        return {"running": False, "pid": None, "uptime_s": None}

    pid = int(payload["pid"])
    if not _pid_alive(pid):
        # Stale entry — a dead process left the file behind. Clean it up.
        try:
            pid_file.unlink()
        except FileNotFoundError:
            pass
        return {"running": False, "pid": None, "uptime_s": None}

    return {
        "running": True,
        "pid": pid,
        "uptime_s": _uptime_s(payload.get("started_at")),
    }


def stop(pid_file: Path) -> dict:
    """Terminate the recorded dashboard process and remove the PID file.

    Returns a dict with ``stopped`` plus a human-readable ``reason``.
    """
    payload = read_pid_file(pid_file)
    if payload is None:
        return {"stopped": False, "reason": "Dashboard is not running"}

    pid = int(payload["pid"])
    if not _pid_alive(pid):
        try:
            pid_file.unlink()
        except FileNotFoundError:
            pass
        return {"stopped": False, "reason": "Stale PID file removed"}

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as e:
        return {"stopped": False, "reason": f"Failed to signal process {pid}: {e}"}

    # Give the process a moment to exit, then clean up the PID file.
    for _ in range(50):
        if not _pid_alive(pid):
            break
        time.sleep(0.05)
    try:
        pid_file.unlink()
    except FileNotFoundError:
        pass
    return {"stopped": True, "reason": f"Terminated process {pid}"}


def add_dashboard_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add dashboard subcommands to the main parser."""
    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Start/stop the QuantLab dashboard web UI",
    )
    dashboard_parser.set_defaults(func=_cmd_dashboard)

    dashboard_subparsers = dashboard_parser.add_subparsers(
        dest="dashboard_action",
        metavar="ACTION",
        help="Dashboard action",
    )

    # dashboard start
    start_parser = dashboard_subparsers.add_parser(
        "start",
        help="Start the dashboard server",
    )
    start_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind (default: 127.0.0.1)",
    )
    start_parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind (default: 8080)",
    )
    start_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode",
    )
    start_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically",
    )
    start_parser.set_defaults(dashboard_action="start")

    # dashboard stop
    stop_parser = dashboard_subparsers.add_parser(
        "stop",
        help="Stop the dashboard server",
    )
    stop_parser.set_defaults(dashboard_action="stop")

    # dashboard status
    status_parser = dashboard_subparsers.add_parser(
        "status",
        help="Show dashboard server status",
    )
    status_parser.set_defaults(dashboard_action="status")


def _cmd_dashboard(args: argparse.Namespace) -> int:
    """Execute dashboard command."""
    if args.dashboard_action == "start":
        return _cmd_dashboard_start(args)
    elif args.dashboard_action == "stop":
        return _cmd_dashboard_stop(args)
    elif args.dashboard_action == "status":
        return _cmd_dashboard_status(args)
    else:
        print("Error: Dashboard action required (start/stop/status)", file=sys.stderr)
        return 1


def _cmd_dashboard_start(args: argparse.Namespace) -> int:
    """Start the dashboard server."""
    config = ServerConfig(
        host=args.host,
        port=args.port,
        debug=args.debug,
    )

    server = DashboardServer(config)

    try:
        print(f"Starting QuantLab Dashboard on http://{args.host}:{args.port}...")
        server.start()
        write_pid_file(_default_pid_file())

        if not args.no_browser:
            import webbrowser
            try:
                webbrowser.open(server.url)
            except Exception:
                pass  # Browser open failed, continue anyway

        print(f"Dashboard running at {server.url}")
        print("Press Ctrl+C to stop...")

        # Keep the main thread alive
        try:
            while server.is_running:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            server.stop()
            _remove_pid_file(_default_pid_file())

        return 0

    except Exception as e:
        print(f"Error starting dashboard: {e}", file=sys.stderr)
        return 1


def _remove_pid_file(pid_file: Path) -> None:
    """Best-effort removal of a PID file, ignoring races."""
    try:
        pid_file.unlink()
    except FileNotFoundError:
        pass


def _cmd_dashboard_stop(args: argparse.Namespace) -> int:
    """Stop the dashboard server by terminating its recorded process."""
    result = stop(_default_pid_file())
    if result["stopped"]:
        print(f"Dashboard stopped ({result['reason']})")
        return 0
    print(f"Dashboard stop: {result['reason']}", file=sys.stderr)
    return 1


def _cmd_dashboard_status(args: argparse.Namespace) -> int:
    """Show dashboard server status."""
    result = status(_default_pid_file())
    if result["running"]:
        uptime = result["uptime_s"]
        uptime_str = f"{uptime:.1f}s" if uptime is not None else "unknown"
        print(f"Dashboard is running (pid={result['pid']}, uptime={uptime_str})")
    else:
        print("Dashboard is not running")
    return 0