"""Phase 4 — SQX Command Dispatcher for CLI-based HTTP API operations.

Wraps AsyncSQXClient to provide high-level campaign operations via the SQX
HTTP ``/call?cmd=<command>`` API.  All campaign methods are async.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, Optional

from quantlab.phase4.errors import (
    JForexConnectionError,
    SQXSessionLockError,
)
from quantlab.phase4.http_client import (
    AsyncSQXClient,
    SQXSessionLock,
)


# ── Status parsing regex helpers ─────────────────────────────────────────────

# Flexible patterns for SQUANT CLI status output
_RE_PROJECT_NAME = re.compile(
    r"(?:Project|Campaign|Name)\s*:?\s*(.+?)[\r\n]",
    re.IGNORECASE,
)
_RE_STATUS = re.compile(
    r"(?:Status)\s*:?\s*(.+?)[\r\n]",
    re.IGNORECASE,
)
_RE_PROGRESS = re.compile(
    r"(?:Progress)\s*:?\s*(\d+(?:\.\d+)?)\s*%?",
    re.IGNORECASE,
)
_RE_GENERATION = re.compile(
    r"(?:(?:Generation|Gen|Task))\s*:?\s*(\d+)\s*(?:/|of)\s*(\d+)",
    re.IGNORECASE,
)
_RE_ERROR = re.compile(
    r"(?:Error|Failed|Exception)\s*:?\s*(.+?)(?:[\r\n]|$)",
    re.IGNORECASE,
)


class CampaignStatus:
    """Parsed campaign status from SQX CLI text output."""

    def __init__(
        self,
        campaign_name: str,
        status: str,
        progress: float = 0.0,
        current_generation: int = 0,
        total_generations: int = 0,
        error_message: Optional[str] = None,
    ):
        self.campaign_name = campaign_name
        self.status = status
        self.progress = progress
        self.current_generation = current_generation
        self.total_generations = total_generations
        self.error_message = error_message

    @property
    def is_complete(self) -> bool:
        return self.status.lower() in ("completed", "finished", "done", "success", "finished")

    @property
    def is_running(self) -> bool:
        return self.status.lower() in ("running", "in progress", "working")

    @property
    def is_failed(self) -> bool:
        return self.status.lower() in ("failed", "error", "aborted")

    @classmethod
    def from_text(cls, text: str, campaign_name: str = "") -> CampaignStatus:
        """Parse campaign status from CLI text output.

        Tries flexible regex patterns first, falls back to line-by-line
        keyword matching for unstructured output.
        """
        name = campaign_name
        if not name:
            m = _RE_PROJECT_NAME.search(text)
            if m:
                name = m.group(1).strip()

        # Determine status from keywords
        status = "unknown"
        text_lower = text.lower()
        if any(w in text_lower for w in ("completed", "finished", "succeeded")):
            status = "completed"
        elif any(w in text_lower for w in ("failed", "error", "exception", "aborted")):
            status = "failed"
            m = _RE_ERROR.search(text)
        elif any(w in text_lower for w in ("running", "in progress", "working", "started")):
            status = "running"
        elif any(w in text_lower for w in ("stopped", "paused", "cancelled")):
            status = "stopped"
        elif any(w in text_lower for w in ("not found", "not exist", "unknown")):
            status = "not_found"

        m = _RE_STATUS.search(text)
        if m:
            status = m.group(1).strip()

        progress = 0.0
        m = _RE_PROGRESS.search(text)
        if m:
            progress = float(m.group(1))

        current_gen = 0
        total_gen = 0
        m = _RE_GENERATION.search(text)
        if m:
            current_gen = int(m.group(1))
            total_gen = int(m.group(2))

        error = None
        if status.lower() in ("failed", "error"):
            m = _RE_ERROR.search(text)
            if m:
                error = m.group(1).strip()

        return cls(
            campaign_name=name or "unknown",
            status=status,
            progress=progress,
            current_generation=current_gen,
            total_generations=total_gen,
            error_message=error,
        )

    def __repr__(self) -> str:
        base = (
            f"CampaignStatus(campaign={self.campaign_name}, "
            f"status={self.status}, progress={self.progress})"
        )
        if self.error_message:
            return f"{base[:-1]}, error={self.error_message!r})"
        return base


class CommandDispatcher:
    """High-level wrapper around AsyncSQXClient for campaign operations.

    Uses the SQX HTTP command-based API (via AsyncSQXClient.send_command)
    instead of REST endpoints.  All campaign methods are async and integrate
    SQXSessionLock.

    Project output directory (``project_output_dir``) is used for export
    operations — SQX projects save results to local files rather than
    serving them through the HTTP API.
    """

    PROJECT_OUTPUT_MAP: dict[str, str] = {
        "builder": "user/strategies",
        "optimizer": "user/optimizer",
        "retester": "user/retest",
        "portfoliomaster": "user/portfolio",
        "portfoliocomposer": "user/portfolio",
    }

    def __init__(
        self,
        client: Optional[AsyncSQXClient] = None,
        *,
        sqx_install_path: Optional[str | Path] = None,
        project_output_dir: Optional[str | Path] = None,
        use_file_lock: bool = False,
        lock_blocking: bool = True,
        lock_timeout: Optional[float] = None,
    ):
        self._client = client
        self._sqx_install_path = Path(sqx_install_path).resolve() if sqx_install_path else None
        self._project_output_dir = (
            Path(project_output_dir).resolve() if project_output_dir else None
        )
        self._lock = SQXSessionLock(
            str(sqx_install_path or Path.cwd()),
            use_file_lock=use_file_lock,
        )
        self._lock_blocking = lock_blocking
        self._lock_timeout = lock_timeout

    # ── Alternative constructors ──────────────────────────────────────────────

    @classmethod
    async def from_daemon(
        cls,
        daemon_manager: Any,
        **kwargs: Any,
    ) -> CommandDispatcher:
        """Create a CommandDispatcher from an SQXDaemonManager."""
        # Duck-typing check for mock compatibility in tests
        required_attrs = ("base_url", "get_client", "start", "stop", "health_check")
        if not all(hasattr(daemon_manager, attr) for attr in required_attrs):
            raise TypeError(
                "Expected SQXDaemonManager-like instance with base_url, get_client, start, stop, health_check"
            )
        client = await daemon_manager.get_client()
        return cls(client, **kwargs)

    # ── Lock helper ───────────────────────────────────────────────────────────

    async def _run_with_lock(self, coro: Any) -> Any:
        """Acquire the session lock, run *coro*, then release."""
        timeout = self._lock_timeout
        if not self._lock_blocking and timeout is None:
            timeout = 0.001

        acquired = False
        try:
            acquired = await self._lock.acquire(
                blocking=self._lock_blocking,
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            coro.close()
            if not self._lock_blocking:
                raise SQXSessionLockError(
                    "SQX session lock could not be acquired (already held)"
                ) from None
            raise SQXSessionLockError(
                f"SQX session lock timed out after {timeout}s"
            ) from None

        if not acquired:
            coro.close()
            raise SQXSessionLockError(
                "SQX session lock could not be acquired"
            )

        try:
            return await coro
        finally:
            self._lock.release()

    # ── Command sending ──────────────────────────────────────────────────────

    async def _send(self, command: str) -> str:
        """Send a CLI command via the HTTP client."""
        if self._client is None:
            raise ValueError(
                "CommandDispatcher has no AsyncSQXClient configured. "
                "Pass a client to the constructor or use from_daemon()."
            )
        return await self._client.send_command(command)

    # ── Campaign operations ───────────────────────────────────────────────────

    async def load_config(self, cfx_path: str | Path) -> str:
        """Load a CFX configuration into SQX via ``-project action=loadconfig``.

        Returns the raw response text.

        Raises:
            FileNotFoundError: If *cfx_path* does not exist.
        """
        cfx_path = Path(cfx_path).resolve()
        if not cfx_path.exists():
            raise FileNotFoundError(f"CFX file not found: {cfx_path}")

        async def _op() -> str:
            return await self._send(
                f'-project action=loadconfig file="{cfx_path}"'
            )

        return await self._run_with_lock(_op())

    @staticmethod
    def _name_param(name: str) -> str:
        """Format a name parameter for SQX command lines.

        The HTTP API's parser splits on spaces and does not understand
        shell quoting, so names with spaces are not supported via the
        HTTP API. Use ``-project action=loadconfig file=`` for projects
        with spaces in their names.
        """
        return f"name={name}"

    async def start_project(self, campaign_name: str) -> str:
        """Start a campaign/project by name.

        Uses ``-project action=start name=<name>``.

        .. note::
           Project names with spaces are not supported via the HTTP API.
           Use :meth:`load_config` with the file path for such projects.
        """
        async def _op() -> str:
            return await self._send(
                f'-project action=start {self._name_param(campaign_name)}'
            )

        return await self._run_with_lock(_op())

    async def stop_project(self, campaign_name: str) -> str:
        """Stop a running campaign via ``-project action=stop``."""
        async def _op() -> str:
            return await self._send(
                f'-project action=stop {self._name_param(campaign_name)}'
            )

        return await self._run_with_lock(_op())

    async def get_status(self, campaign_name: str) -> CampaignStatus:
        """Get campaign status via ``-project action=status``."""
        async def _op() -> CampaignStatus:
            text = await self._send(
                f'-project action=status {self._name_param(campaign_name)}'
            )
            return CampaignStatus.from_text(text, campaign_name)

        return await self._run_with_lock(_op())

    async def list_databanks(self) -> dict[str, int]:
        """List per-databank record counts via ``-databank action=list``.

        Returns a mapping of databank name → record count, parsed
        defensively. Any unparseable line is skipped; if the entire
        output is unparseable the result is an empty dict (never raises).
        """
        async def _op() -> dict[str, int]:
            text = await self._send("-databank action=list")
            counts: dict[str, int] = {}
            for line in text.splitlines():
                # Expect: "Results, Records: 3" (colon and comma optional,
                # case-insensitive). Banner/separator lines are skipped.
                m = re.search(
                    r"^([^,]+),?\s+Records\s*:?\s*(\d+)$",
                    line.strip(),
                    re.IGNORECASE,
                )
                if m:
                    counts[m.group(1).strip()] = int(m.group(2))
            return counts

        return await self._run_with_lock(_op())

    async def list_projects(self) -> list[str]:
        """List all available projects via ``-project action=list``.

        Filters out timestamp headers, separator lines, and empty output
        to return only actual project names.
        """
        async def _op() -> list[str]:
            import re
            text = await self._send("-project action=list")
            lines = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Skip timestamp headers (e.g. "23:45:22 List of available projects")
                if re.match(r"^\d{2}:\d{2}:\d{2}", line):
                    continue
                # Skip separators, CLI usage hints, and empty markers
                if line.startswith("-") or line.startswith("sqcli"):
                    continue
                if "available projects" in line.lower():
                    continue
                if "example" in line.lower():
                    continue
                lines.append(line)
            return lines

        return await self._run_with_lock(_op())

    # ── Export methods ────────────────────────────────────────────────────────

    def _resolve_output_path(self, campaign_name: str, project_type: str) -> Path:
        """Resolve the output directory for a project type.

        Searches:
        1. Explicit ``project_output_dir``
        2. SQX install path + known subdirectory for *project_type*
        3. Falls back to temp dir
        """
        if self._project_output_dir:
            return self._project_output_dir / campaign_name

        if self._sqx_install_path:
            rel = self.PROJECT_OUTPUT_MAP.get(project_type.lower())
            if rel:
                return self._sqx_install_path / rel / campaign_name

        return Path.cwd() / campaign_name

    async def export_results(
        self, campaign_name: str, output_dir: str | Path
    ) -> str:
        """Export campaign results by reading project output files.

        Searches the project output directory for CSV/text result files.
        Returns the path to the first found result file.
        """
        output_path = Path(output_dir) / f"{campaign_name}_results.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        async def _op() -> str:
            # Look for result files in expected project output dirs
            candidates = []
            if self._sqx_install_path:
                for rel_dir in ("user/strategies", "user/optimizer", "user/retest"):
                    search_dir = self._sqx_install_path / rel_dir / campaign_name
                    if search_dir.is_dir():
                        candidates.extend(sorted(search_dir.glob("*.csv")))

            if candidates:
                import shutil
                shutil.copy2(candidates[0], output_path)
            else:
                output_path.write_text(
                    f"# Results for {campaign_name}\n"
                    f"# No CSV result file found — project may still be running.\n"
                )

            return str(output_path)

        return await self._run_with_lock(_op())

    async def export_retest_report(
        self, campaign_name: str, output_path: str | Path
    ) -> str:
        """Export retester HTML report from project output files."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        async def _op() -> str:
            if self._sqx_install_path:
                search_dir = self._sqx_install_path / "user/retest" / campaign_name
                if search_dir.is_dir():
                    html_files = sorted(search_dir.glob("*.html"))
                    if html_files:
                        import shutil
                        shutil.copy2(html_files[0], output_path)
                        return str(output_path)

            output_path.write_text(
                f"<!-- Retest report for {campaign_name} -->\n"
                f"<p>No HTML report found — project may still be running.</p>\n"
            )
            return str(output_path)

        return await self._run_with_lock(_op())

    async def export_retest_csv(
        self, campaign_name: str, output_path: str | Path
    ) -> str:
        """Export retester CSV results from project output files."""
        async def _op() -> str:
            result = await self.export_results(
                campaign_name, Path(output_path).parent
            )
            return result

        return await self._run_with_lock(_op())

    async def export_optimization_results(
        self, campaign_name: str, output_dir: str | Path
    ) -> str:
        """Export optimizer results from project output files."""
        return await self.export_results(campaign_name, output_dir)

    async def export_databanks(
        self, campaign_name: str, output_dir: str | Path
    ) -> list[str]:
        """Export retester databank files from project output."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        async def _op() -> list[str]:
            if self._sqx_install_path:
                search_dir = self._sqx_install_path / "user/retest" / campaign_name
                if search_dir.is_dir():
                    for f in search_dir.iterdir():
                        if f.is_file():
                            import shutil
                            shutil.copy2(f, output_dir / f.name)

            return [str(p) for p in output_dir.iterdir() if p.is_file()]

        return await self._run_with_lock(_op())

    async def get_results_xml(self, campaign_name: str) -> str:
        """Get raw results XML from project output files."""
        async def _op() -> str:
            if self._sqx_install_path:
                search_dir = self._sqx_install_path / "user/strategies" / campaign_name
                if search_dir.is_dir():
                    xml_files = sorted(search_dir.glob("*.xml"))
                    if xml_files:
                        return xml_files[0].read_text()

            return f"<?xml version=\"1.0\"?>\n<results campaign=\"{campaign_name}\">\n</results>\n"

        return await self._run_with_lock(_op())

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the underlying AsyncSQXClient."""
        if self._client:
            await self._client.close()
