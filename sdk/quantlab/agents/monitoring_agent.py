"""MonitoringAgent — live equity ingestion, rolling metrics, regime detection, alerting."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

from quantlab.knowledge.store import KnowledgeStore
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.agent_stages import MonitorStage
from quantlab.readers.models import EquityPoint
from quantlab.readers.result_reader import ResultReader
from quantlab.stats.aggregation import StatisticsAggregator

logger = logging.getLogger(__name__)


class MonitoringAgent(MonitorStage):
    """Tracks live strategy performance via equity streaming, computes rolling
    metrics, detects regime changes, and emits alerts. Archives live metrics
    to Knowledge Lake.

    Args:
        window: Rolling window size for Sharpe/drawdown computation (default 252).
        drawdown_threshold: Alert threshold for max drawdown as fraction
            (default 0.15 = 15%).
        sharpe_degradation_pct: Minimum Sharpe degradation to trigger alert
            (default 0.4 = 40%).
        knowledge_root: Root path for Knowledge Lake (default ``knowledge``).
    """

    name: str = "monitor"
    requires: list[str] = ["live_equity", "deployment_result"]
    provides: list[str] = [
        "rolling_metrics",
        "regime_alerts",
        "performance_alerts",
        "gate_decision_HUMAN_REVIEW_PERFORMANCE",
    ]

    def __init__(
        self,
        window: int = 252,
        drawdown_threshold: float = 0.15,
        sharpe_degradation_pct: float = 0.4,
        knowledge_root: str | Path = "knowledge",
    ) -> None:
        self._window = window
        self._drawdown_threshold = drawdown_threshold
        self._sharpe_degradation_pct = sharpe_degradation_pct
        self._aggregator = StatisticsAggregator()
        self._knowledge_root = Path(knowledge_root)
        self._store = KnowledgeStore(root=self._knowledge_root)

    # ── Pipeline contract ────────────────────────────────────────────────────────

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Execute the monitoring stage."""
        return await self.run(ctx)

    async def run(self, context: PipelineContext) -> dict[str, Any]:
        """Execute the monitoring stage.

        Reads ``live_equity`` from ``context.artifacts``, computes rolling
        metrics, detects regime changes, checks thresholds, and writes
        ``rolling_metrics``, ``regime_alerts``, and ``performance_alerts``
        back to the context.

        Args:
            context: ``PipelineContext`` with ``live_equity`` in ``artifacts``.

        Returns:
            Dict with ``rolling_metrics``, ``regime_alerts``, and
            ``performance_alerts``.
        """
        live_equity = context.artifacts.get("live_equity", [])
        if not live_equity:
            logger.info("MonitoringAgent: no live_equity in context, skipping metrics")
            context.artifacts.update(
                {
                    "rolling_metrics": {},
                    "regime_alerts": [],
                    "performance_alerts": [],
                    "gate_decision_HUMAN_REVIEW_PERFORMANCE": {
                        "status": "no_data",
                        "note": "Monitoring skipped — no live equity",
                    },
                }
            )
            return {
                "rolling_metrics": {},
                "regime_alerts": [],
                "performance_alerts": [],
            }

        # Normalise to EquityPoint
        if isinstance(live_equity[0], dict):
            live_equity = [EquityPoint(**dict(pt)) for pt in live_equity]

        # 1. Rolling metrics
        rolling_metrics = self.compute_rolling_metrics(live_equity)

        # 2. Regime detection
        regime_alerts = self.detect_regime_change(rolling_metrics)

        # 3. Performance alerts
        performance_alerts = self.check_alerts(rolling_metrics, live_equity)

        # 4. Knowledge Lake persistence (every 100 points)
        self._persist_metrics(live_equity, rolling_metrics, regime_alerts, performance_alerts)

        # 5. Gate decision (auto-approve if no alerts, else flag review)
        gate_decision = self._build_gate_decision(regime_alerts, performance_alerts)

        # 6. Write artifacts
        context.artifacts["rolling_metrics"] = rolling_metrics
        context.artifacts["regime_alerts"] = regime_alerts
        context.artifacts["performance_alerts"] = performance_alerts
        context.artifacts["gate_decision_HUMAN_REVIEW_PERFORMANCE"] = gate_decision

        logger.info(
            "MonitoringAgent: %d regime alerts, %d performance alerts",
            len(regime_alerts),
            len(performance_alerts),
        )

        return {
            "rolling_metrics": rolling_metrics,
            "regime_alerts": regime_alerts,
            "performance_alerts": performance_alerts,
        }

    # ── Task 5.3: Rolling metrics ────────────────────────────────────────────────

    def compute_rolling_metrics(self, equity: list[EquityPoint]) -> dict[str, Any]:
        """Compute rolling Sharpe, drawdown, and volatility.

        Args:
            equity: Sorted list of ``EquityPoint`` objects.

        Returns:
            Dict mapping metric name -> ``RollingMetrics`` as dict.
        """
        if len(equity) < 2:
            return {}

        try:
            rolling = self._aggregator.rolling_metrics(
                equity=equity,
                window=self._window,
                metrics=["sharpe", "drawdown", "volatility"],
            )
        except ValueError:
            return {}

        result: dict[str, Any] = {}
        for metric_name, rm in rolling.items():
            serialised: dict[str, Any] = {
                "timestamps": [
                    t.isoformat() if hasattr(t, "isoformat") else str(t)
                    for t in rm.timestamps
                ],
                "values": [float(v) for v in rm.values],
                "window": rm.window,
                "metric_name": rm.metric_name,
            }
            result[metric_name] = serialised
        return result

    # ── Task 5.4: Regime detection ───────────────────────────────────────────────

    def detect_regime_change(self, rolling_metrics: dict[str, Any]) -> list[dict[str, Any]]:
        """Detect regime shifts from rolling metrics.

        Uses two signals:
        - ``REGIME_SHIFT``: Sharpe drops to < 0.7 of early average AND drawdown
          spikes > 2x.
        - ``VOLATILITY_SPIKE``: Current volatility > 3x baseline.

        Args:
            rolling_metrics: Dict from ``compute_rolling_metrics()``.

        Returns:
            List of regime alert dicts.
        """
        alerts: list[dict[str, Any]] = []

        sharpe_values = rolling_metrics.get("sharpe", {}).get("values", [])
        drawdown_values = rolling_metrics.get("drawdown", {}).get("values", [])
        volatility_values = rolling_metrics.get("volatility", {}).get("values", [])

        valid_sharpes = [
            s
            for s in sharpe_values
            if isinstance(s, (int, float)) and not math.isnan(float(s))
        ]
        valid_drawdowns = [
            d
            for d in drawdown_values
            if isinstance(d, (int, float)) and not math.isnan(float(d))
        ]
        valid_vols = [
            v
            for v in volatility_values
            if isinstance(v, (int, float)) and not math.isnan(float(v))
        ]

        min_len = self._window // 2
        if len(valid_sharpes) < min_len or len(valid_drawdowns) < min_len:
            return alerts

        mid = len(valid_sharpes) // 2
        early_sharpes = valid_sharpes[:mid]
        late_sharpes = valid_sharpes[mid:]

        early_avg_sharpe = (
            sum(early_sharpes) / len(early_sharpes) if early_sharpes else 0.0
        )
        late_avg_sharpe = (
            sum(late_sharpes) / len(late_sharpes) if late_sharpes else 0.0
        )

        early_avg_dd = (
            sum(valid_drawdowns[:mid]) / max(len(valid_drawdowns[:mid]), 1)
        )
        late_avg_dd = (
            sum(valid_drawdowns[mid:]) / max(len(valid_drawdowns[mid:]), 1)
        )

        sharpe_drop_ratio = (
            late_avg_sharpe / early_avg_sharpe if early_avg_sharpe > 0 else 1.0
        )
        dd_spike_ratio = (
            late_avg_dd / early_avg_dd if early_avg_dd > 0 else 1.0
        )

        if sharpe_drop_ratio < 0.7 and dd_spike_ratio > 2.0:
            confidence = min(
                0.85,
                (1.0 - sharpe_drop_ratio) * 0.5 + min(dd_spike_ratio * 0.1, 0.35),
            )
            from_regime = "trending" if early_avg_sharpe > 1.0 else "choppy"
            to_regime = "choppy" if from_regime == "trending" else "volatile"

            if to_regime == "choppy":
                action = "Reduce position size 50%, widen stops"
            elif to_regime == "volatile":
                action = (
                    "Reduce position size 50%, widen stops 2x, "
                    "pause new entries until vol normalizes"
                )
            else:
                action = "Review market regime alignment"

            alerts.append(
                {
                    "type": "REGIME_SHIFT",
                    "confidence": round(confidence, 2),
                    "from_regime": from_regime,
                    "to_regime": to_regime,
                    "suggested_actions": [action],
                    "sharpe_drop_ratio": round(sharpe_drop_ratio, 3),
                    "dd_spike_ratio": round(dd_spike_ratio, 3),
                }
            )

        # Volatility spike detection
        if len(valid_vols) >= mid and mid > 0:
            baseline_vol = sum(valid_vols[:mid]) / mid
            current_vol = valid_vols[-1]
            if baseline_vol > 0 and current_vol > 3 * baseline_vol:
                alerts.append(
                    {
                        "type": "VOLATILITY_SPIKE",
                        "severity": "HIGH",
                        "suggested_actions": [
                            "Widen stops 2x",
                            "Pause new entries until vol normalizes",
                        ],
                        "baseline_vol": round(baseline_vol, 4),
                        "current_vol": round(current_vol, 4),
                    }
                )

        return alerts

    # ── Task 5.5: Alerting ───────────────────────────────────────────────────────

    def check_alerts(
        self,
        rolling_metrics: dict[str, Any],
        equity: list[EquityPoint],
    ) -> list[dict[str, Any]]:
        """Check performance alerts against configured thresholds.

        Args:
            rolling_metrics: Dict from ``compute_rolling_metrics()``.
            equity: Full equity curve for drawdown computation.

        Returns:
            List of alert dicts.
        """
        alerts: list[dict[str, Any]] = []

        # Max drawdown breach
        drawdown_values = rolling_metrics.get("drawdown", {}).get("values", [])
        valid_dds = [
            d
            for d in drawdown_values
            if isinstance(d, (int, float)) and not math.isnan(float(d))
        ]
        if valid_dds:
            current_dd = max(valid_dds)
            threshold_pct = self._drawdown_threshold * 100
            if current_dd > threshold_pct:
                alerts.append(
                    {
                        "type": "DRAWDOWN_BREACH",
                        "severity": "CRITICAL",
                        "current": f"{current_dd:.2f}%",
                        "threshold": f"{threshold_pct:.2f}%",
                        "suggested_action": "Reduce exposure, review stop-loss levels",
                        "escalation": "HUMAN_REVIEW_PERFORMANCE",
                    }
                )

        # Sharpe degradation
        sharpe_values = rolling_metrics.get("sharpe", {}).get("values", [])
        valid_sharpes = [
            s
            for s in sharpe_values
            if isinstance(s, (int, float)) and not math.isnan(float(s))
        ]
        if len(valid_sharpes) >= self._window:
            window_30 = min(30, len(valid_sharpes))
            recent_bucket = valid_sharpes[-window_30:]
            early_bucket = valid_sharpes[:window_30]
            if early_bucket and early_bucket[0] > 0:
                degradation = (early_bucket[0] - recent_bucket[-1]) / early_bucket[0]
                if degradation > self._sharpe_degradation_pct:
                    alerts.append(
                        {
                            "type": "SHARPE_DEGRADATION",
                            "severity": "WARNING",
                            "current": f"{recent_bucket[-1]:.2f}",
                            "previous": f"{early_bucket[0]:.2f}",
                            "degradation_pct": f"{degradation * 100:.0f}%",
                            "suggested_action": (
                                "Review strategy parameters, consider re-optimization"
                            ),
                        }
                    )

        return alerts

    # ── Task 5.2: Live equity ingestion ─────────────────────────────────────────

    @staticmethod
    async def start_monitoring(
        campaign_id: str,
        equity_data: list[EquityPoint] | None = None,
        window: int = 252,
        drawdown_threshold: float = 0.15,
        knowledge_root: str | Path = "knowledge",
    ) -> dict[str, Any]:
        """Standalone monitoring entry point.

        Streams equity data, computes metrics, and returns alerts without
        requiring a ``PipelineContext``.

        Args:
            campaign_id: Campaign to monitor.
            equity_data: Optional replay buffer.
            window: Rolling window size.
            drawdown_threshold: Drawdown alert threshold as fraction.

        Returns:
            Dict with ``rolling_metrics``, ``regime_alerts``, and
            ``performance_alerts``.
        """
        agent = MonitoringAgent(
            window=window,
            drawdown_threshold=drawdown_threshold,
            knowledge_root=knowledge_root,
        )
        if equity_data:
            rolling = agent.compute_rolling_metrics(equity_data)
            regime = agent.detect_regime_change(rolling)
            perf = agent.check_alerts(rolling, equity_data)
            return {
                "rolling_metrics": rolling,
                "regime_alerts": regime,
                "performance_alerts": perf,
            }
        return {"rolling_metrics": {}, "regime_alerts": [], "performance_alerts": []}

    # ── Internal helpers ─────────────────────────────────────────────────────────

    def _persist_metrics(
        self,
        equity: list[EquityPoint],
        rolling_metrics: dict[str, Any],
        regime_alerts: list[dict[str, Any]],
        performance_alerts: list[dict[str, Any]],
    ) -> None:
        """Persist a snapshot of rolling metrics to Knowledge Lake."""
        if len(equity) < 1 or len(equity) % max(self._window, 1) != 0:
            return
        try:
            self._store.initialize()
        except Exception:
            pass

        metrics_dir = self._store.resolve("monitoring")
        metrics_dir.mkdir(parents=True, exist_ok=True)
        import yaml

        metrics_path = metrics_dir / "latest_metrics.yaml"
        metrics_path.write_text(
            yaml.dump(
                {
                    "equity_tail": [
                        {
                            "timestamp": (
                                e.timestamp.isoformat()
                                if hasattr(e.timestamp, "isoformat")
                                else str(e.timestamp)
                            ),
                            "equity": e.equity,
                        }
                        for e in equity[-10:]
                    ],
                    "rolling_metrics": rolling_metrics,
                    "regime_alerts": regime_alerts,
                    "performance_alerts": performance_alerts,
                    "saved_at": datetime.now().isoformat(),
                },
                default_flow_style=False,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def _build_gate_decision(
        self,
        regime_alerts: list[dict[str, Any]],
        performance_alerts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build a gate decision artifact for HUMAN_REVIEW_PERFORMANCE.

        Auto-approves when there are no alerts; otherwise flags for review.
        """
        critical = [a for a in performance_alerts if a.get("severity") == "CRITICAL"]
        if critical:
            return {
                "status": "review_required",
                "reason": "; ".join(a.get("type", "") for a in critical),
                "auto_decision": False,
                "alerts_count": len(regime_alerts) + len(performance_alerts),
            }
        return {
            "status": "approved",
            "auto_decision": True,
            "alerts_count": len(regime_alerts) + len(performance_alerts),
        }
