"""Cross-platform path resolution utilities.

Uses platformdirs for standard config/data directories and pathlib
for POSIX/Windows separator normalization.
"""

import os
import platform
from pathlib import Path

from platformdirs import PlatformDirs

_dirs = PlatformDirs(appname="quantlab", appauthor=False)


def get_platform_name() -> str:
    """Return the normalized platform name.

    Returns:
        One of ``"windows"``, ``"linux"``, ``"darwin"``.
    """
    system = platform.system().lower()
    if system == "darwin":
        return "darwin"
    if system == "windows":
        return "windows"
    return "linux"


def get_sqcli_binary() -> str:
    """Return the platform-appropriate SQX CLI binary name.

    Returns:
        ``"sqcli.exe"`` on Windows, ``"sqcli"`` on Linux/macOS.
    """
    return "sqcli.exe" if get_platform_name() == "windows" else "sqcli"


def resolve_sqcli_path(custom_path: Path | str | None = None) -> Path | None:
    """Resolve the path to the ``sqcli`` executable.

    On Windows, searches common installation paths if no custom path
    is given. On Linux/macOS, only a custom path is accepted.

    Args:
        custom_path: Optional explicit path to the sqcli binary.

    Returns:
        The resolved Path, or ``None`` if not found.
    """
    if custom_path is not None:
        candidate = Path(custom_path)
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
        return None

    platform_name = get_platform_name()
    binary = get_sqcli_binary()

    if platform_name == "windows":
        # Common SQX installation paths on Windows
        search_dirs = [
            Path(os.environ.get(key, ""))
            for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")
            if os.environ.get(key)
        ]
        for base in search_dirs:
            candidate = base / "StrategyQuant" / binary
            if candidate.exists():
                return candidate.resolve()

    return None


def get_app_data_dir() -> Path:
    """Return the platform-appropriate application data directory.

    Uses ``platformdirs`` to resolve the correct path per OS:
    Linux → ``~/.local/share/quantlab``,
    Windows → ``%APPDATA%/quantlab``,
    macOS → ``~/Library/Application Support/quantlab``.
    """
    return Path(_dirs.user_data_dir)


def get_app_config_dir() -> Path:
    """Return the platform-appropriate configuration directory."""
    return Path(_dirs.user_config_dir)


def normalize_path(path: str | Path) -> Path:
    """Normalize a path string to a ``pathlib.Path`` using OS-appropriate separators.

    On Windows, forward slashes in the input are converted to backslashes.
    On POSIX, backslashes are converted to forward slashes.
    """
    return Path(path).resolve()
