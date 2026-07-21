"""SQX Session Serialization Lock.

Provides intra-process asyncio.Lock and optional cross-process file lock
to prevent concurrent SQX operations (HTTP API + CLI) from corrupting state.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import warnings
from pathlib import Path
from typing import Optional


class SQXSessionLock:
    """Serialization lock for SQX operations.

    Ensures only one SQX operation (HTTP API call or CLI command) runs at a time
    within a process, with best-effort cross-process protection via file lock.

    Lock file location: ~/.quantlab/sqx-{install_hash}.lock
    Where install_hash = first 12 chars of SHA256(SQX install path)

    Usage:
        lock = SQXSessionLock(sqx_install_path="/opt/SQX")
        async with lock:
            await client.load_strategy("123")
            await client.recompute_portfolio("NetProfit")
    """

    def __init__(self, install_path: str | Path) -> None:
        """Initialize the session lock.

        Args:
            install_path: Path to SQX installation directory. Used to generate
                a unique lock file per SQX instance (supports multiple installs).
        """
        self._async_lock = asyncio.Lock()
        self._install_hash = self._compute_install_hash(install_path)
        self._lock_dir = Path.home() / ".quantlab"
        self._lock_file = self._lock_dir / f"sqx-{self._install_hash}.lock"
        self._file_lock_fd: Optional[int] = None
        self._file_lock_acquired = False

    @staticmethod
    def _compute_install_hash(install_path: str | Path) -> str:
        """Compute short hash of install path for lock file naming."""
        path_str = str(Path(install_path).resolve())
        return hashlib.sha256(path_str.encode()).hexdigest()[:12]

    @property
    def install_hash(self) -> str:
        return self._install_hash

    @property
    def lock_file_path(self) -> Path:
        return self._lock_file

    async def __aenter__(self) -> None:
        """Acquire both async and file locks."""
        # Intra-process lock (always acquired)
        await self._async_lock.acquire()

        # Cross-process file lock (best-effort)
        self._acquire_file_lock()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Release both locks."""
        self._release_file_lock()
        self._async_lock.release()

    def _acquire_file_lock(self) -> None:
        """Acquire cross-process file lock (best-effort, non-blocking).

        Uses fcntl on Unix, falls back to portalocker if available.
        Logs warning on failure but doesn't block — intra-process lock still protects.
        """
        try:
            self._lock_dir.mkdir(parents=True, exist_ok=True)
            # Open lock file (create if needed)
            self._file_lock_fd = os.open(
                self._lock_file, os.O_CREAT | os.O_RDWR, 0o644
            )

            # Try fcntl (Unix)
            try:
                import fcntl

                fcntl.flock(self._file_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._file_lock_acquired = True
                return
            except (ImportError, OSError):
                pass

            # Try portalocker if available
            try:
                import portalocker

                portalocker.lock(
                    self._file_lock_fd, portalocker.LOCK_EX | portalocker.LOCK_NB
                )
                self._file_lock_acquired = True
                return
            except (ImportError, OSError):
                pass

            # If we get here, file lock couldn't be acquired
            # Close fd and warn
            if self._file_lock_fd is not None:
                os.close(self._file_lock_fd)
                self._file_lock_fd = None
            warnings.warn(
                f"Could not acquire cross-process SQX session lock at {self._lock_file}. "
                "Intra-process lock still active. Install 'portalocker' for better "
                "multi-process protection.",
                RuntimeWarning,
                stacklevel=2,
            )

        except Exception as e:
            # Any failure — warn but don't block
            warnings.warn(
                f"File lock setup failed: {e}. Intra-process lock still active.",
                RuntimeWarning,
                stacklevel=2,
            )

    def _release_file_lock(self) -> None:
        """Release cross-process file lock."""
        if not self._file_lock_acquired or self._file_lock_fd is None:
            return

        try:
            # Try fcntl unlock
            try:
                import fcntl

                fcntl.flock(self._file_lock_fd, fcntl.LOCK_UN)
            except ImportError:
                pass

            # Try portalocker unlock
            try:
                import portalocker

                portalocker.unlock(self._file_lock_fd)
            except ImportError:
                pass

        finally:
            if self._file_lock_fd is not None:
                os.close(self._file_lock_fd)
                self._file_lock_fd = None
            self._file_lock_acquired = False