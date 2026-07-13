"""SQX CLI wrapper — Executor protocol, real + mock implementations.

Provides a clean Python interface over ``sqcli.exe`` with full dry-run
support, enabling development and testing without an SQX installation.
"""

from __future__ import annotations

import platform as _platform
import subprocess
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from quantlab.tools.exceptions import SQXNotFoundError, TimeoutError
from quantlab.tools.platform import get_sqcli_binary, resolve_sqcli_path


# ── Structured result model ────────────────────────────────────────────────────


class CliResult(BaseModel):
    """Structured result from any ``sqcli.exe`` command execution.

    Attributes:
        stdout:           Captured standard output.
        stderr:           Captured standard error.
        exit_code:        Process exit code.
        duration_seconds: Wall-clock execution time in seconds.
        is_dry_run:       Whether this result came from a mock execution.
        platform:         The operating system where the command ran.
    """

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_seconds: float = 0.0
    is_dry_run: bool = False
    platform: str = Field(default_factory=lambda: _platform.system().lower())


# ── Executor protocol ──────────────────────────────────────────────────────────


@runtime_checkable
class Executor(Protocol):
    """Protocol for SQX command executors.

    Implementations must provide an ``execute`` method that accepts a
    command string and optional keyword arguments, returning a ``CliResult``.
    """

    def execute(self, command: str, **kwargs: object) -> CliResult:
        """Execute an ``sqcli`` command and return structured results.

        Args:
            command: The CLI command string to execute
                     (e.g. ``"backtest --cfx output/Test.cfx"``).
            **kwargs: Optional overrides (e.g. ``timeout``).

        Returns:
            A ``CliResult`` with captured output and metadata.
        """
        ...


# ── Mock executor (dry-run) ────────────────────────────────────────────────────


class MockExecutor:
    """Dry-run executor that returns canned results without spawning a process.

    Attributes:
        default_result: The ``CliResult`` returned for every invocation.
    """

    def __init__(self, default_result: CliResult | None = None) -> None:
        self.default_result = default_result or CliResult(
            stdout="[mock] SQX command executed successfully (dry-run)",
            stderr="",
            exit_code=0,
            duration_seconds=0.001,
            is_dry_run=True,
        )

    def execute(self, command: str, **kwargs: object) -> CliResult:
        """Return the canned result immediately.

        All arguments are accepted and ignored — no subprocess is spawned.
        """
        return self.default_result


# ── Real executor (subprocess) ─────────────────────────────────────────────────


class RealExecutor:
    """Real SQX executor that spawns ``sqcli`` as a subprocess.

    The binary path is resolved at construction time.  Raises
    ``SQXNotFoundError`` immediately if the binary cannot be found.

    Attributes:
        _binary: Resolved path to the ``sqcli`` / ``sqcli.exe`` binary.
    """

    def __init__(self, sqcli_path: str | Path | None = None) -> None:
        binary = resolve_sqcli_path(sqcli_path)
        if binary is None:
            hint = f" at '{sqcli_path}'" if sqcli_path else ""
            raise SQXNotFoundError(
                f"SQX CLI binary (sqcli) not found{hint}. "
                "Install StrategyQuant X or use dry-run mode."
            )
        self._binary = binary

    def execute(
        self,
        command: str,
        timeout: int = 60,
        **kwargs: object,
    ) -> CliResult:
        """Execute an ``sqcli`` subprocess command.

        Args:
            command: The CLI command string to execute.
            timeout: Maximum wall-clock time in seconds before the process
                     is terminated (default 60).

        Returns:
            A ``CliResult`` with captured output and metadata.

        Raises:
            TimeoutError: The subprocess exceeded *timeout* seconds.
        """
        start = time.monotonic()

        try:
            proc = subprocess.run(
                [str(self._binary), *command.split()],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - start
            raise TimeoutError(
                f"SQX command timed out after {timeout}s: {command}",
                cause=exc,
            ) from exc

        elapsed = time.monotonic() - start

        return CliResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
            duration_seconds=elapsed,
            is_dry_run=False,
        )


# ── Facade ─────────────────────────────────────────────────────────────────────


class CliRunner:
    """Facade for SQX command execution with dry-run support.

    Usage::

        # Dry-run mode (no SQX required)
        runner = CliRunner(dry_run=True)
        result = runner.execute("backtest --cfx test.cfx")

        # Per-call override
        result = runner.execute("backtest", dry_run=False)  # attempts real

        # Custom executor injection
        runner = CliRunner(executor=MockExecutor())
    """

    def __init__(
        self,
        dry_run: bool = False,
        executor: Executor | None = None,
        sqcli_path: str | Path | None = None,
    ) -> None:
        self._dry_run = dry_run
        self._sqcli_path = sqcli_path

        if executor is not None:
            self._executor = executor
        elif dry_run:
            self._executor = MockExecutor()
        else:
            self._executor = RealExecutor(sqcli_path=sqcli_path)

    def execute(self, command: str, **overrides: object) -> CliResult:
        """Execute an ``sqcli`` command.

        Args:
            command:   The CLI command string to execute.
            **overrides: Per-call overrides.  Supported keys:

                - ``dry_run`` (bool): Override the runner's dry-run mode for
                  this single call.

        Returns:
            A ``CliResult`` with output and metadata.
        """
        # Check for per-call dry_run override
        call_dry_run = overrides.pop("dry_run", None)
        if call_dry_run is not None and call_dry_run != self._dry_run:
            # Override differs — use a temporary executor for this call
            if call_dry_run:
                executor: Executor = MockExecutor()
            else:
                executor = RealExecutor(sqcli_path=self._sqcli_path)
            return executor.execute(command, **overrides)

        # Normal path — use the runner's executor
        return self._executor.execute(command, **overrides)
