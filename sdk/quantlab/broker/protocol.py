"""Broker adapter protocol and interface definitions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class BrokerAdapter(Protocol):
    """Canonical interface for broker adapters consumed by ExecutionGuardian.

    All broker adapters must implement these methods so that
    ExecutionGuardian can query connection, latency, health, and slippage
    without coupling to a specific platform.
    """

    def is_connected(self) -> bool:
        """Return whether the broker connection is active."""
        ...

    def get_latency(self) -> float:
        """Return latency in milliseconds."""
        ...

    def get_health_score(self) -> float:
        """Return broker health score in the 0.0-1.0 range."""
        ...

    def get_recent_slippage(self) -> float | None:
        """Return recent slippage in basis points, or None if unavailable."""
        ...
