"""Archiver — maintenance plan, replacement runbook, account stats (REQ-33).

In the archive phase the Archiver composes (1) a maintenance/replacement plan
for the deployed strategy from live demo performance and Guardian data, (2) a
replacement runbook when the deployed strategy is DEGRADING (candidates from
the campaign portfolio, with expected improvement and risk assessment), and
(3) account statistics (equity, drawdown, P&L) over the demo window. Plan and
runbook are persisted under the KnowledgeStore ``maintenance/`` and
``campaign-phases/`` directories.

Human confirmation is enforced by the surrounding archive phase gate
(``HUMAN_APPROVE_ARCHIVE``, fail-closed by default); the runbook records the
required confirmation so the audit trail is explicit. Without live Guardian
data the plan falls back to default review intervals and warns about the
missing live data (campaign-archive spec scenario 2).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

import yaml

from quantlab.guardian.models import PortfolioState, StrategyState
from quantlab.knowledge.models import MaintenancePlan
from quantlab.phase4.campaign_archive import account_stats

logger = logging.getLogger(__name__)

# Next review date is 7 days from archive when live demo data exists
# (campaign-archive spec scenario 1); default interval without live data.
LIVE_REVIEW_CYCLE_DAYS = 7
DEFAULT_REVIEW_CYCLE_DAYS = 30
# Replacement criteria: drawdown > 10% (campaign-archive spec scenario 1).
REPLACEMENT_DRAWDOWN_THRESHOLD = 0.10
# Cost budget for the next maintenance cycle when none is supplied.
DEFAULT_NEXT_CYCLE_BUDGET = 100.0
# Confidence below which a parameter is flagged for review (REQ-34).
FLAG_CONFIDENCE_THRESHOLD = 0.3
ARCHIVE_GATE_ID = "HUMAN_APPROVE_ARCHIVE"

MAINTENANCE_DIR = "maintenance"
CAMPAIGN_PHASES_DIR = "campaign-phases"


def review_cycle_days(*, has_live_data: bool) -> int:
    """Return the maintenance review cycle in days (7 live, 30 default)."""
    return LIVE_REVIEW_CYCLE_DAYS if has_live_data else DEFAULT_REVIEW_CYCLE_DAYS


def refresh_triggers(
    parameter_matrix: Sequence[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Derive parameter refresh triggers from the justification matrix.

    Parameters with confidence below 0.3 (consistently underperforming in
    live performance, REQ-34) are flagged for review in the next cycle.
    Without a matrix, a single default trigger reviews the whole set.
    """
    if not parameter_matrix:
        return [{"tab": "all", "parameter": "all", "reason": "default review"}]
    triggers: list[dict[str, Any]] = []
    for entry in parameter_matrix:
        confidence = float(entry.get("confidence", 1.0))
        if confidence < FLAG_CONFIDENCE_THRESHOLD:
            triggers.append(
                {
                    "tab": entry.get("tab", ""),
                    "parameter": entry.get("parameter", ""),
                    "reason": "confidence below 0.3",
                }
            )
    return triggers


@dataclass(frozen=True)
class ReplacementCandidate:
    """A portfolio strategy proposed to replace the deployed one (REQ-33)."""

    strategy_id: str
    expected_improvement: str
    risk: str


@dataclass(frozen=True)
class ReplacementRunbook:
    """Replacement recommendation when the deployed strategy is DEGRADING."""

    deployed_strategy_id: str
    strategy_state: str
    recommendation: str  # "REPLACE" | "MAINTAIN"
    candidates: list[ReplacementCandidate] = field(default_factory=list)
    drawdown_threshold: float = REPLACEMENT_DRAWDOWN_THRESHOLD
    required_confirmations: list[str] = field(
        default_factory=lambda: [ARCHIVE_GATE_ID]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployed_strategy_id": self.deployed_strategy_id,
            "strategy_state": self.strategy_state,
            "recommendation": self.recommendation,
            "candidates": [c.strategy_id for c in self.candidates],
            "drawdown_threshold": self.drawdown_threshold,
            "required_confirmations": list(self.required_confirmations),
        }


@dataclass
class ArchiveResult:
    """Outcome of :meth:`Archiver.archive`."""

    campaign_id: str
    plan: MaintenancePlan
    runbook: ReplacementRunbook
    stats: dict[str, float]
    artifacts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Archiver:
    """Compose and persist the archive maintenance artifacts (REQ-33)."""

    async def archive(
        self,
        campaign_id: str,
        guardian_state: PortfolioState | None,
        portfolio_data: dict[str, Any],
    ) -> ArchiveResult:
        """Write maintenance plan, replacement runbook, and account stats.

        Args:
            campaign_id: Campaign identifier.
            guardian_state: MetaGuardian portfolio state (``None`` when no
                Guardian data exists).
            portfolio_data: Mapping with:
                - ``knowledge_root``: KnowledgeStore root (default ``knowledge``).
                - ``equity_points``: demo-window equity curve
                  (``EquityPoint`` objects or dicts).
                - ``portfolio_candidates``: strategy IDs in the campaign
                  portfolio (replacement source).
                - ``deployed_strategy_id``: currently deployed strategy.
                - ``strategy_state``: per-strategy Guardian state
                  (``StrategyState`` or string; DEGRADING triggers REPLACE).
                - ``parameter_matrix``: parameter justification matrix.
                - ``candidate_metrics``: per-candidate metric dicts used for
                  expected-improvement / risk assessment.
                - ``next_cycle_budget``: cost budget for the next cycle.

        Returns:
            :class:`ArchiveResult` with the plan, runbook, stats, and the
            artifact paths persisted to the KnowledgeStore.
        """
        warnings: list[str] = []

        # ── Inputs ────────────────────────────────────────────────────────────
        equity_points = self._equity_points(portfolio_data.get("equity_points"))
        portfolio_candidates = list(portfolio_data.get("portfolio_candidates") or [])
        deployed = str(portfolio_data.get("deployed_strategy_id") or "")
        strategy_state = portfolio_data.get("strategy_state")
        state_text = self._state_text(strategy_state)
        has_live_data = bool(equity_points) or state_text not in ("", "UNKNOWN") or guardian_state is not None
        parameter_matrix = portfolio_data.get("parameter_matrix")
        candidate_metrics = portfolio_data.get("candidate_metrics") or {}
        budget = float(portfolio_data.get("next_cycle_budget", DEFAULT_NEXT_CYCLE_BUDGET))

        # ── Account statistics over the demo window (REQ-33) ────────────────
        stats = account_stats(equity_points)
        stats_dict: dict[str, float] = {
            "start_equity": stats.start_equity,
            "end_equity": stats.end_equity,
            "max_drawdown": stats.max_drawdown,
            "pnl": stats.pnl,
        }

        # ── Degradation → replacement runbook (REQ-33 scenario 2) ────────────
        degrading = state_text == StrategyState.DEGRADING.value
        runbook_candidates: list[ReplacementCandidate] = []
        replacement_ids: list[str] = []
        if degrading:
            for sid in portfolio_candidates:
                if sid == deployed:
                    continue
                runbook_candidates.append(
                    self._assess_candidate(sid, candidate_metrics.get(sid, {}))
                )
                replacement_ids.append(sid)
        recommendation = "REPLACE" if degrading else "MAINTAIN"

        runbook = ReplacementRunbook(
            deployed_strategy_id=deployed,
            strategy_state=state_text,
            recommendation=recommendation,
            candidates=runbook_candidates,
        )

        # ── Maintenance plan (REQ-33 scenario 1) ─────────────────────────────
        cycle_days = review_cycle_days(has_live_data=has_live_data)
        if not has_live_data:
            warnings.append(
                "missing live data — using default review intervals"
            )
        triggers = refresh_triggers(parameter_matrix)
        notes = json.dumps(
            {
                "next_review_days": cycle_days,
                "next_review_date": (
                    datetime.now(timezone.utc) + timedelta(days=cycle_days)
                ).date().isoformat(),
                "refresh_triggers": triggers,
                "replacement_criteria": [
                    f"drawdown > {REPLACEMENT_DRAWDOWN_THRESHOLD:.0%}",
                    "guardian strategy state DEGRADING",
                ],
                "cost_budget": budget,
            },
            sort_keys=True,
        )
        plan = MaintenancePlan(
            campaign_id=campaign_id,
            review_cycle_days=cycle_days,
            replacement_candidates=replacement_ids,
            live_strategy_ids=[deployed] if deployed else [],
            notes=notes,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        # ── Persist to the KnowledgeStore (maintenance/ + campaign-phases/) ──
        artifacts = self._persist(
            campaign_id=campaign_id,
            plan=plan,
            runbook=runbook,
            stats=stats_dict,
            guardian_state=guardian_state,
            knowledge_root=portfolio_data.get("knowledge_root", "knowledge"),
        )

        return ArchiveResult(
            campaign_id=campaign_id,
            plan=plan,
            runbook=runbook,
            stats=stats_dict,
            artifacts=artifacts,
            warnings=warnings,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _equity_points(self, raw: Any) -> list[Any]:
        from quantlab.readers.models import EquityPoint

        points = raw or []
        return [
            EquityPoint(**p) if isinstance(p, dict) else p for p in points
        ]

    @staticmethod
    def _state_text(strategy_state: Any) -> str:
        if strategy_state is None:
            return ""
        return (
            strategy_state.value
            if hasattr(strategy_state, "value")
            else str(strategy_state)
        )

    @staticmethod
    def _assess_candidate(
        strategy_id: str, metrics: dict[str, Any]
    ) -> ReplacementCandidate:
        sharpe = metrics.get("sharpe")
        drawdown = metrics.get("max_drawdown")
        if sharpe is not None and drawdown is not None:
            expected = f"Sharpe {float(sharpe):.2f}, max drawdown {float(drawdown):.0%}"
        else:
            expected = "portfolio replacement candidate"
        if drawdown is None:
            risk = "medium"
        elif float(drawdown) <= 0.05:
            risk = "low"
        elif float(drawdown) <= 0.10:
            risk = "medium"
        else:
            risk = "high"
        return ReplacementCandidate(
            strategy_id=strategy_id,
            expected_improvement=expected,
            risk=risk,
        )

    def _persist(
        self,
        *,
        campaign_id: str,
        plan: MaintenancePlan,
        runbook: ReplacementRunbook,
        stats: dict[str, float],
        guardian_state: PortfolioState | None,
        knowledge_root: str | Any,
    ) -> list[str]:
        from quantlab.knowledge.store import KnowledgeStore

        store = KnowledgeStore(root=knowledge_root)
        store.initialize()

        plan_path = store.root / MAINTENANCE_DIR / f"{campaign_id}.yaml"
        runbook_path = store.root / MAINTENANCE_DIR / f"{campaign_id}.runbook.yaml"
        stats_path = store.root / CAMPAIGN_PHASES_DIR / f"{campaign_id}_archive.yaml"

        plan_path.write_text(
            yaml.dump(
                {
                    "campaign_id": plan.campaign_id,
                    "review_cycle_days": plan.review_cycle_days,
                    "replacement_candidates": list(plan.replacement_candidates),
                    "live_strategy_ids": list(plan.live_strategy_ids),
                    "disconnected_strategy_ids": list(plan.disconnected_strategy_ids),
                    "notes": plan.notes,
                    "updated_at": plan.updated_at,
                },
                default_flow_style=False,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        runbook_path.write_text(
            yaml.dump(runbook.to_dict(), default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        stats_path.write_text(
            yaml.dump(
                {
                    "campaign_id": campaign_id,
                    "phase": "archive",
                    "status": "archived",
                    "guardian_state": (
                        guardian_state.value if guardian_state else None
                    ),
                    "strategy_state": runbook.strategy_state,
                    "recommendation": runbook.recommendation,
                    "stats": stats,
                    "archived_at": datetime.now(timezone.utc).isoformat(),
                },
                default_flow_style=False,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        return [str(plan_path), str(runbook_path), str(stats_path)]
