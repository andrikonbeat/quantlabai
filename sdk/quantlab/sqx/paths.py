"""Paths resolver — where this skill's per-install artifacts live.

The deployed skill lives INSIDE the install it targets
(``<install>/user/extend/AIPlugins/sqx-project/skills/sqx-project/``),
so the install root is resolved by walking up from ``__file__`` -
never cwd, never an env var, never ``${CLAUDE_PLUGIN_ROOT}``
(SQAI does not substitute it).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


# ── Install markers ──────────────────────────────────────────────────────────

# Files that unambiguously identify an SQX install root
_INSTALL_MARKERS = (
    "internal/plugins/TaskBuild/task.xml",
    "internal/plugins/TaskBuild/task_forex.xml",
    "internal/web/SQAI/ai-guide.html",
    "user/settings/settings.xml",
)

_FALLBACK_APP_VERSION = "145.3191"

# Version warning regex (from oracle.pyc)
_VERSION_WARN_RE = re.compile(r"differs from this build \(([\d.]+)\)")
_START_RE = re.compile(r"^")
_EXIT_MARK = "Exit app"


# ── Public API ───────────────────────────────────────────────────────────────


def _find_install_root() -> Path | None:
    """
    Find SQX install root by walking up from this file.
    
    Returns the install root Path, or None if not found.
    """
    current = Path(__file__).resolve()
    for _ in range(15):
        for marker in _INSTALL_MARKERS:
            if (current / marker).exists():
                return current
        if current.parent == current:
            break
        current = current.parent
    return None


_INSTALL_ROOT = _find_install_root()


def install_root() -> Path:
    """Return the detected SQX install root."""
    if _INSTALL_ROOT is None:
        raise RuntimeError(
            "Could not locate SQX install root. "
            "Ensure this module lives inside an SQX install."
        )
    return _INSTALL_ROOT


def sessions_root() -> Path:
    """Return the SQAI sessions directory."""
    return install_root() / "internal" / "web" / "SQAI" / "state" / "sessions"


def session_projects_dir(session_id: str) -> Path:
    """Return the session's projects directory."""
    return sessions_root() / session_id / "projects"


def output_dir() -> Path:
    """Return the default output directory for generated artifacts."""
    return install_root() / "user" / "sqai-projects"


def discover_port(base_url: str = "http://127.0.0.1:5050") -> int | None:
    """Discover the SQX web server port by probing common ports."""
    import httpx
    
    for port in (5050, 8080, 8081, 8888):
        try:
            import httpx
            resp = httpx.get(f"http://127.0.0.1:{port}/call?cmd=-h", timeout=2.0)
            if resp.status_code == 200:
                return port
        except Exception:
            continue
    return None


def _version_key(version: str) -> tuple[int, ...]:
    """Parse version string into comparable tuple."""
    return tuple(int(x) for x in version.split("."))


def discover_app_version(base_url: str = "http://127.0.0.1:5050") -> str | None:
    """Discover the SQX app version by querying the CLI."""
    import httpx
    import subprocess
    
    try:
        # Try CLI first
        result = subprocess.run(
            ["sqcli", "--args=-h"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "SQX version:" in line:
                return line.split(":")[-1].strip()
    except Exception:
        pass
    
    # Fallback: try HTTP API
    try:
        import httpx
        resp = httpx.get("http://127.0.0.1:5050/call?cmd=-h", timeout=5.0)
        if resp.status_code == 200:
            for line in resp.text.splitlines():
                if "SQX version:" in line:
                    return line.split(":")[-1].strip()
    except Exception:
        pass
    
    return None


# ── CLI / Testing ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    print("Install root:", install_root())
    print("Sessions root:", sessions_root())
    print("Output dir:", output_dir())
    print("App version:", discover_app_version())
    print("Port:", discover_port())