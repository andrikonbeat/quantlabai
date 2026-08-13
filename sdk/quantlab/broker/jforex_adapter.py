"""JForex4 broker adapter — reads execution state from local filesystem."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from quantlab.broker.protocol import BrokerAdapter
from quantlab.jforex.config import JForexCredentials


class JForexBrokerAdapter:
    """Broker adapter that reads JForex4 local state from the filesystem.

    JForex4 writes connection, latency, health, and slippage data to a local
    state directory. This adapter reads those files and exposes them through
    the canonical ``BrokerAdapter`` interface expected by
    ``ExecutionGuardian``.

    Attributes:
        credentials: JForex4 connection credentials.
        state_dir: Path to the JForex4 local state directory.
    """

    def __init__(
        self,
        credentials: JForexCredentials,
        state_dir: Optional[Path] = None,
    ) -> None:
        self.credentials = credentials
        self.state_dir = Path(state_dir) if state_dir else None

    # ── BrokerAdapter protocol ────────────────────────────────────────────────

    def is_connected(self) -> bool:
        """Return whether the broker connection is active."""
        if self.state_dir is None:
            return False
        path = self.state_dir / "connection.json"
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return bool(data.get("connected", False))
        except (json.JSONDecodeError, OSError):
            return False

    def get_latency(self) -> float:
        """Return latency in milliseconds.

        Raises:
            FileNotFoundError: If the latency state file does not exist.
        """
        if self.state_dir is None:
            raise FileNotFoundError("No state directory configured")
        path = self.state_dir / "latency.txt"
        if not path.exists():
            raise FileNotFoundError(f"Latency state not found: {path}")
        return float(path.read_text(encoding="utf-8").strip())

    def get_health_score(self) -> float:
        """Return broker health score in the 0.0-1.0 range.

        Raises:
            FileNotFoundError: If the health state file does not exist.
        """
        if self.state_dir is None:
            raise FileNotFoundError("No state directory configured")
        path = self.state_dir / "health.txt"
        if not path.exists():
            raise FileNotFoundError(f"Health state not found: {path}")
        score = float(path.read_text(encoding="utf-8").strip())
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"Health score out of range: {score}")
        return score

    def get_recent_slippage(self) -> Optional[float]:
        """Return recent slippage in basis points, or None if unavailable."""
        if self.state_dir is None:
            return None
        path = self.state_dir / "slippage.txt"
        if not path.exists():
            return None
        try:
            return float(path.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            return None
