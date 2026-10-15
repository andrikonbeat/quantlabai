"""
JForex Bridge feature flags and settings.

Centralizes environment-driven configuration for the JForex Bridge layer.
"""

from __future__ import annotations

import os

# Feature flag: when true, use the JForex Bridge instead of hardcoded values.
# Controlled by the QUANTLAB_JFOREX_BRIDGE environment variable.
# Default: false (preserves existing behavior).
def jforex_bridge_enabled() -> bool:
    """Return True if the JForex Bridge should be used."""
    return os.environ.get("QUANTLAB_JFOREX_BRIDGE", "").lower() in ("1", "true", "yes")


# Default JForex Bridge base URL
def jforex_bridge_base_url() -> str:
    """Return the JForex Bridge base URL from env or default."""
    return os.environ.get("QUANTLAB_JFOREX_BRIDGE_URL", "http://localhost:8082")


# Default JForex Bridge WebSocket URL
def jforex_bridge_ws_url() -> str:
    """Return the JForex Bridge WebSocket URL from env or default."""
    return os.environ.get("QUANTLAB_JFOREX_BRIDGE_WS_URL", "ws://localhost:8082/ws")


# Default request timeout in seconds
def jforex_bridge_timeout() -> float:
    """Return the JForex Bridge request timeout in seconds."""
    raw = os.environ.get("QUANTLAB_JFOREX_BRIDGE_TIMEOUT", "")
    if raw:
        try:
            return max(1.0, float(raw))
        except ValueError:
            pass
    return 30.0


# Default retry count for transient failures
def jforex_bridge_max_retries() -> int:
    """Return the max retries for transient HTTP failures."""
    raw = os.environ.get("QUANTLAB_JFOREX_BRIDGE_MAX_RETRIES", "")
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return 3