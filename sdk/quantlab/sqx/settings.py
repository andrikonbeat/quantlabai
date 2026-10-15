"""SQX feature flags and settings.

Centralizes environment-driven configuration for the SQX HTTP layer.
"""

from __future__ import annotations

import os

# Feature flag: when true, use the SQX HTTP API instead of subprocess shelling.
# Controlled by the QUANTLAB_SQX_USE_HTTP environment variable.
# Default: false (preserves existing subprocess behavior).
def sqx_use_http() -> bool:
    """Return True if the HTTP API should be used instead of subprocess."""
    return os.environ.get("QUANTLAB_SQX_USE_HTTP", "").lower() in ("1", "true", "yes")


# Default SQX daemon base URL (port 5050 per SQX 145 default)
def sqx_base_url() -> str:
    """Return the SQX daemon base URL from env or default."""
    return os.environ.get("QUANTLAB_SQX_BASE_URL", "http://127.0.0.1:5050")


# Default request timeout in seconds
def sqx_timeout() -> float:
    """Return the SQX HTTP request timeout in seconds."""
    raw = os.environ.get("QUANTLAB_SQX_TIMEOUT", "")
    if raw:
        try:
            return max(1.0, float(raw))
        except ValueError:
            pass
    return 30.0


# Default retry count for transient failures
def sqx_max_retries() -> int:
    """Return the max retries for transient HTTP failures."""
    raw = os.environ.get("QUANTLAB_SQX_MAX_RETRIES", "")
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return 3


# =============================================================================
# JForex Bridge feature flags and settings (re-exported from jforex_settings)
# =============================================================================

from quantlab.jforex_bridge.jforex_settings import (
    jforex_bridge_enabled,
    jforex_bridge_base_url,
    jforex_bridge_ws_url,
    jforex_jnlp_url,
    jforex_bridge_timeout,
    jforex_bridge_max_retries,
)