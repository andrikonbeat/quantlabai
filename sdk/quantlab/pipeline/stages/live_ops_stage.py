"""LiveOpsStage — canonical live-ops phase after archive (REQ-01 phase 14, REQ-6).

Consumes the archive state and publishes the live-ops status: the campaign is
deemed ``live`` only when an archive bundle exists (archive status +
maintenance plan ride on the ``archive_bundle`` from ``ArchivePhase.run``).
Without an archive state the stage fails closed — it never claims a live
account (status ``hold``), so a campaign that never reached the archive phase
cannot be reported as live.

Extended with live-ops pool management (C10): tracks candidate strategies
promoted to live demo, monitors their performance, and coordinates with
Guardian for state transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from quantlab.pipeline.base import PipelineContext, Stage


@dataclass
class LiveCandidate:
    """A strategy candidate in the live-ops pool."""

    strategy_id: str
    jfx_path: str
    added_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    status: str = "candidate"  # candidate, active, paused, retired, failed
    deployment_status: str = "pending"  # pending, deployed, failed
    performance: dict = field(default_factory=dict)  # live metrics
    last_evaluated: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class LiveOpsPool:
    """Manages the pool of live-ops candidate strategies."""

    candidates: dict[str, LiveCandidate] = field(default_factory=dict)
    max_candidates: int = 10
    auto_promote: bool = True
    auto_retire_drawdown_pct: float = 0.15  # 15% drawdown triggers retirement

    def add_candidate(self, candidate: LiveCandidate) -> bool:
        """Add a candidate to the pool. Returns True if added."""
        if len(self.candidates) >= self.max_candidates:
            return False
        if candidate.strategy_id in self.candidates:
            return False
        self.candidates[candidate.strategy_id] = candidate
        return True

    def remove_candidate(self, strategy_id: str, reason: str = "retired") -> bool:
        """Remove a candidate from the pool."""
        if candidate := self.candidates.pop(strategy_id, None):
            candidate.status = reason
            return True
        return False

    def update_performance(self, strategy_id: str, metrics: dict) -> bool:
        """Update performance metrics for a candidate."""
        if candidate := self.candidates.get(strategy_id):
            candidate.performance.update(metrics)
            candidate.last_evaluated = datetime.now(UTC).isoformat()
            return True
        return False

    def check_drawdown_retirement(self, threshold_pct: float | None = None) -> list[str]:
        """Check for candidates exceeding drawdown threshold. Returns retired IDs."""
        threshold = threshold_pct or self.auto_retire_drawdown_pct
        retired = []
        for sid, candidate in list(self.candidates.items()):
            dd = candidate.performance.get("max_drawdown_pct", 0)
            if dd >= threshold:
                self.remove_candidate(sid, "drawdown_exceeded")
                retired.append(sid)
        return retired

    def get_active_candidates(self) -> list[LiveCandidate]:
        """Get all active (deployed) candidates."""
        return [
            c for c in self.candidates.values()
            if c.status == "active" and c.deployment_status == "deployed"
        ]

    def get_candidate_pool_status(self) -> dict:
        """Get summary of pool status."""
        return {
            "total": len(self.candidates),
            "active": len(self.get_active_candidates()),
            "candidates": [
                {
                    "strategy_id": c.strategy_id,
                    "status": c.status,
                    "deployment_status": c.deployment_status,
                    "added_at": c.added_at,
                    "performance": c.performance,
                }
                for c in self.candidates.values()
            ],
        }


class LiveOpsStage(Stage):
    """Start live-ops monitoring for the archived campaign (REQ-6).

    **Requires**: archive_bundle
    **Provides**: live_ops_status, live_pool_status

    Extended with live-ops pool management (C10): tracks candidate strategies
    promoted to live demo, monitors their performance, and coordinates with
    Guardian for state transitions.
    """

    name: str = "live_ops"
    requires: list[str] = ["archive_bundle"]
    provides: list[str] = ["live_ops_status", "live_pool_status"]

    def __init__(self) -> None:
        self.pool = LiveOpsPool()

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Publish ``live_ops_status`` from the archive state.

        Extended: also manages live-ops candidate pool and publishes pool status.

        Args:
            ctx: Pipeline context with the ``archive_bundle`` artifact.

        Returns:
            Dict with ``live_ops_status`` and ``live_pool_status``.
        """
        bundle = ctx.artifacts.get("archive_bundle")
        if bundle is None:
            # Fail-closed: without an archive state the campaign cannot be
            # reported as live (never auto-approve, REQ-11/REQ-38).
            ctx.artifacts["live_ops_status"] = {
                "status": "hold",
                "archive_status": None,
                "maintenance_plan": None,
            }
            ctx.artifacts["live_pool_status"] = self.pool.get_candidate_pool_status()
            return {
                "live_ops_status": ctx.artifacts["live_ops_status"],
                "live_pool_status": ctx.artifacts["live_pool_status"],
            }

        if isinstance(bundle, dict):
            archive_status = bundle.get("status")
            maintenance_plan = bundle.get("maintenance_plan") or bundle.get("plan")
        else:
            archive_status = getattr(bundle, "status", None)
            maintenance_plan = getattr(bundle, "maintenance_plan", None) or getattr(
                bundle, "plan", None
            )

        live_ops_status = {
            "status": "live",
            "archive_status": archive_status,
            "maintenance_plan": maintenance_plan,
        }
        ctx.artifacts["live_ops_status"] = live_ops_status
        ctx.artifacts["live_pool_status"] = self.pool.get_candidate_pool_status()

        return {
            "live_ops_status": live_ops_status,
            "live_pool_status": ctx.artifacts["live_pool_status"],
        }

    def add_candidate(self, candidate: LiveCandidate) -> bool:
        """Add a strategy candidate to the live-ops pool."""
        return self.pool.add_candidate(candidate)

    def deploy_candidate(self, strategy_id: str, jfx_path: str) -> bool:
        """Mark a candidate as deployed."""
        if candidate := self.pool.candidates.get(strategy_id):
            candidate.deployment_status = "deployed"
            candidate.status = "active"
            candidate.jfx_path = jfx_path
            return True
        return False

    def update_candidate_performance(self, strategy_id: str, metrics: dict) -> bool:
        """Update live performance metrics for a candidate."""
        return self.pool.update_performance(strategy_id, metrics)

    def check_drawdown_retirement(self, threshold_pct: float | None = None) -> list[str]:
        """Check and retire candidates exceeding drawdown threshold."""
        return self.pool.check_drawdown_retirement()

    def get_pool_status(self) -> dict:
        """Get current pool status."""
        return self.pool.get_candidate_pool_status()