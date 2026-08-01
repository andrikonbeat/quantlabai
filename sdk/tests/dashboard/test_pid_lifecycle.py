"""RED tests for the dashboard PID lifecycle (DSH-02, threat-matrix).

Covers:
- Missing PID file -> status reports "not running"
- Stale PID (dead process) -> file is removed
- SIGTERM termination -> process dies and the PID file is removed
- Running status reports PID + uptime
"""

from __future__ import annotations

import signal
import subprocess
import sys
import time

from quantlab.cli.dashboard_commands import status, stop, write_pid_file


def _sleepy_process() -> subprocess.Popen:
    """Start a long-lived child process that will not exit on its own."""
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class TestMissingPidFile:
    """No PID file -> the dashboard is reported as not running."""

    def test_status_reports_not_running(self, tmp_path) -> None:
        result = status(tmp_path / "dashboard.pid")
        assert result["running"] is False
        assert result.get("pid") is None
        assert result.get("uptime_s") is None

    def test_stop_reports_not_running(self, tmp_path) -> None:
        result = stop(tmp_path / "dashboard.pid")
        assert result["stopped"] is False


class TestStalePidFile:
    """A PID file pointing at a dead process is treated as not running."""

    def test_status_removes_stale_pid_file(self, tmp_path) -> None:
        pid_file = tmp_path / "dashboard.pid"
        # 2**30 is (effectively) never a live PID on this system
        write_pid_file(pid_file, pid=2**30)
        result = status(pid_file)
        assert result["running"] is False
        assert not pid_file.exists()

    def test_stop_removes_stale_pid_file(self, tmp_path) -> None:
        pid_file = tmp_path / "dashboard.pid"
        write_pid_file(pid_file, pid=2**30)
        result = stop(pid_file)
        assert result["stopped"] is False
        assert not pid_file.exists()


class TestRunningProcess:
    """A live PID -> running status with uptime; stop sends SIGTERM."""

    def test_status_reports_running_with_uptime(self, tmp_path) -> None:
        proc = _sleepy_process()
        try:
            pid_file = tmp_path / "dashboard.pid"
            write_pid_file(pid_file, pid=proc.pid)
            result = status(pid_file)
            assert result["running"] is True
            assert result["pid"] == proc.pid
            assert result["uptime_s"] is not None
            assert result["uptime_s"] >= 0
        finally:
            proc.kill()
            proc.wait(timeout=10)

    def test_stop_terminates_process_and_removes_file(self, tmp_path) -> None:
        proc = _sleepy_process()
        try:
            pid_file = tmp_path / "dashboard.pid"
            write_pid_file(pid_file, pid=proc.pid)

            result = stop(pid_file)

            assert result["stopped"] is True
            assert not pid_file.exists()
            proc.wait(timeout=10)
            assert proc.returncode == -signal.SIGTERM
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)
