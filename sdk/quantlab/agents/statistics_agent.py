"""StatisticsAgent — computes campaign statistics, aggregations, Monte Carlo bands, and regime detection.

Consumes ``export_paths`` from BuilderAgent, calls ``StatisticsEngine`` for
per-campaign metrics, ``StatisticsAggregator`` for cross-campaign aggregation
and Monte Carlo bootstrap, and detects degradation/regime shifts via rolling
metrics.

Implements the ``StatisticsStage.execute()`` contract for pipeline integration.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Optional

from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.agent_stages import StatisticsStage
from quantlab.readers.models import EquityPoint, Trade
from quantlab.stats.aggregation import StatisticsAggregator
from quantlab.stats.engine import StatisticsEngine
from quantlab.stats.models import StatsResult

logger = logging.getLogger(__name__)


class StatisticsAgent(StatisticsStage):
    """Computes campaign statistics, aggregations, Monte Carlo bands, and rolling metrics.

    Args:
        n_simulations: Number of Monte Carlo bootstrap simulations (default 1000).
        percentiles: Percentiles for MC bands (default [10, 50, 90]).
        mc_seed: Random seed for deterministic MC (default 42).
        rolling_window: Window for rolling metrics computation (default 60).
        annual_factor: Periods per year for annualized metrics (default 252).
        risk_free_rate: Risk-free rate per period (default 0.0).
    """

    def __init__(
        self,
        n_simulations: int = 1000,
        percentiles: Optional[list[int]] = None,
        mc_seed: int = 42,
        rolling_window: int = 60,
        annual_factor: int = 252,
        risk_free_rate: float = 0.0,
    ) -> None:
        self._n_simulations = n_simulations
        self._percentiles = percentiles or [10, 50, 90]
        self._mc_seed = mc_seed
        self._rolling_window = rolling_window
        self._annual_factor = annual_factor
        self._risk_free_rate = risk_free_rate
        self._engine = StatisticsEngine()
        self._aggregator = StatisticsAggregator()

    # ── Task 3.2: Statistics Computation ────────────────────────────────────────

    def compute_statistics(
        self,
        export_paths: list[str],
    ) -> StatsResult:
        """Compute full statistics from SQX export data.

        Reads ``trades.csv`` and ``equity.csv`` from export paths, then calls
        ``StatisticsEngine.compute_all()`` to compute all available metrics.

        Args:
            export_paths: List of file paths from BuilderAgent exports.
                Expected entries: ``trades.csv``, ``equity.csv``, ``statistics.json``.

        Returns:
            ``StatsResult`` with all computed metrics (float64 precision).

        Raises:
            FileNotFoundError: If required export files are missing.
        """
        trades: list[Trade] = []
        equity: list[EquityPoint] = []
        returns: list[float] = []
        net_profit: Optional[float] = None
        cagr: Optional[float] = None

        # Resolve paths — find trades.csv and equity.csv
        trades_path = self._resolve_export_path(export_paths, "trades.csv")
        equity_path = self._resolve_export_path(export_paths, "equity.csv")

        if not trades_path:
            logger.warning("No trades.csv found in export paths — statistics will be partial")
        else:
            trades = self._read_trades(trades_path)
            logger.info("Read %d trades from %s", len(trades), trades_path)

        if not equity_path:
            logger.warning("No equity.csv found in export paths — MDD and returns will be unavailable")
        else:
            equity = self._read_equity(equity_path)
            logger.info("Read %d equity points from %s", len(equity), equity_path)

            # Compute returns from equity curve
            if len(equity) >= 2:
                eq_vals = [e.equity for e in equity]
                for i in range(1, len(eq_vals)):
                    if eq_vals[i - 1] != 0:
                        returns.append((eq_vals[i] - eq_vals[i - 1]) / eq_vals[i - 1])

        # Try to read statistics.json for extra data
        stats_json_path = self._resolve_export_path(export_paths, "statistics.json")
        if stats_json_path:
            try:
                with open(stats_json_path, "r") as f:
                    stats_data = json.load(f)
                net_profit = stats_data.get("net_profit")
                cagr = stats_data.get("cagr")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Could not read statistics.json: %s", e)

        # Compute all metrics
        result = self._engine.compute_all(
            trades=trades if trades else None,
            equity=equity if equity else None,
            returns=returns if returns else None,
            cagr=cagr,
            net_profit=net_profit,
            annual_factor=self._annual_factor,
            risk_free_rate=self._risk_free_rate,
        )

        # Add derived fields: win_rate and total_trades from trades list
        if trades:
            total = len(trades)
            winning = sum(1 for t in trades if t.profit > 0)
            result.win_rate = winning / total if total > 0 else 0.0
            result.total_trades = total

        return result

    def _resolve_export_path(self, export_paths: list[str], filename: str) -> Optional[str]:
        """Find a file by name in the export paths list.

        Args:
            export_paths: List of file paths.
            filename: The filename to look for (e.g. ``trades.csv``).

        Returns:
            The full path if found, else ``None``.
        """
        for path in export_paths:
            if path.endswith(filename):
                return path
        return None

    def _read_trades(self, path: str) -> list[Trade]:
        """Read trades from a CSV file.

        Expected CSV columns: profit, entry_time (optional), exit_time (optional),
        direction (optional), lots (optional).

        Args:
            path: Path to trades.csv.

        Returns:
            List of ``Trade`` objects.
        """
        from datetime import datetime

        trades: list[Trade] = []
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                profit = float(row.get("profit", 0))
                entry_time = datetime.fromisoformat(row.get("entry_time", "2024-01-01T00:00:00"))
                exit_time = datetime.fromisoformat(row.get("exit_time", "2024-01-02T00:00:00"))
                direction = row.get("direction", "LONG")
                lots = float(row.get("lots", 1.0))
                trades.append(Trade(
                    profit=profit,
                    entry_time=entry_time,
                    exit_time=exit_time,
                    direction=direction,
                    lots=lots,
                ))
        return trades

    def _read_equity(self, path: str) -> list[EquityPoint]:
        """Read equity curve from a CSV file.

        Expected CSV columns: equity, timestamp (optional).

        Args:
            path: Path to equity.csv.

        Returns:
            List of ``EquityPoint`` objects.
        """
        from datetime import datetime

        points: list[EquityPoint] = []
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                equity_val = float(row.get("equity", row.get("balance", 0)))
                ts_str = row.get("timestamp", row.get("time", ""))
                timestamp = datetime.fromisoformat(ts_str) if ts_str else datetime.now()
                points.append(EquityPoint(equity=equity_val, timestamp=timestamp))
        return points

    # ── Task 3.3: Cross-Campaign Aggregation ────────────────────────────────────

    def aggregate_campaigns(
        self,
        campaign_results: list[Any],
        metrics: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Aggregate statistics across multiple campaigns.

        Delegates to ``StatisticsAggregator.aggregate_campaigns()``. When a
        custom ``metrics`` list is provided, only those metrics are returned.

        Args:
            campaign_results: List of CampaignResult objects.
            metrics: Optional list of metric names to include (e.g.
                     ``["sharpe", "sortino", "expectancy"]``).

        Returns:
            Dict mapping metric name -> ``AggregateStats`` (as dict).
        """
        result = self._aggregator.aggregate_campaigns(campaign_results)

        if metrics:
            result = {k: v for k, v in result.items() if k in metrics}

        # Convert AggregateStats models to dicts for context serialization
        return {
            k: v.model_dump() if hasattr(v, "model_dump") else v
            for k, v in result.items()
        }

    def monte_carlo_bands(
        self,
        trades: list[Trade],
        n_simulations: Optional[int] = None,
        percentiles: Optional[list[int]] = None,
        seed: Optional[int] = None,
    ) -> dict[int, Any]:
        """Run Monte Carlo bootstrap resampling of trade profits.

        Returns full equity curve percentile bands (initial + n_trades) instead
        of just terminal net profit percentiles. The base call to
        ``StatisticsAggregator.monte_carlo_bands()`` provides terminal
        distribution; this method extends it to per-trade equity curves.

        Args:
            trades: List of Trade objects.
            n_simulations: Number of bootstrap iterations (default from config).
            percentiles: Percentiles to compute (default from config).
            seed: Random seed for reproducibility (default from config).

        Returns:
            Dict mapping percentile -> list of equity values (length n_trades+1).
            Keys are int percentiles (e.g. 10, 50, 90), values are lists of
            cumulative equity after each trade.
        """
        import numpy as np

        n_sims = n_simulations or self._n_simulations
        pcts = percentiles or self._percentiles
        rng_seed = seed if seed is not None else self._mc_seed

        if not trades:
            raise ValueError("Empty trades list — cannot run Monte Carlo bootstrap.")

        profits = np.array([t.profit for t in trades], dtype=np.float64)
        n_trades = len(profits)

        np.random.seed(rng_seed)

        # Build equity curves for all simulations
        # Shape: (n_simulations, n_trades + 1) — initial equity (0) + after each trade
        all_curves = np.zeros((n_sims, n_trades + 1), dtype=np.float64)

        for i in range(n_sims):
            sample = np.random.choice(profits, size=n_trades, replace=True)
            all_curves[i, 1:] = np.cumsum(sample)

        # Compute percentiles at each step
        result: dict[int, list[float]] = {}
        for p in pcts:
            result[p] = [float(v) for v in np.percentile(all_curves, p, axis=0)]

        return result

    def assess_robustness(
        self,
        statistics: dict[str, Any],
        monte_carlo_bands: dict[int, list[float]],
    ) -> dict[str, Any]:
        """Assess strategy robustness using Monte Carlo bands.

        Checks if the MC p10 curve drops below zero at any point, indicating
        overfitting risk.

        Args:
            statistics: Dict with computed statistics (e.g. from ``StatsResult.model_dump()``).
            monte_carlo_bands: Dict from ``monte_carlo_bands()``.

        Returns:
            Dict with ``robustness_flag`` and ``rationale``.
        """
        sharpe = statistics.get("sharpe_ratio") or statistics.get("sharpe", 0)
        p10_curve = monte_carlo_bands.get(10, [])

        if not p10_curve:
            return {
                "robustness_flag": "INSUFFICIENT_DATA",
                "rationale": "No MC p10 curve available for assessment",
            }

        # Find where p10 goes negative
        negative_indices = [i for i, v in enumerate(p10_curve) if v < 0]
        if negative_indices:
            first_neg = negative_indices[0]
            pct_completed = first_neg / len(p10_curve) * 100
            if sharpe and sharpe > 1.5:
                return {
                    "robustness_flag": "OVERFIT_RISK",
                    "rationale": (
                        f"MC p10 below zero at trade {first_neg} "
                        f"({pct_completed:.0f}% of trades completed) — "
                        f"high Sharpe ({sharpe:.2f}) with negative p10 suggests overfitting"
                    ),
                }
            return {
                "robustness_flag": "OVERFIT_RISK",
                "rationale": f"MC p10 below zero at {pct_completed:.0f}% trades",
            }

        return {
            "robustness_flag": "ROBUST",
            "rationale": "MC p10 remains positive throughout",
        }

    # ── Task 3.4: Rolling Metrics & Regime Detection ────────────────────────────

    def compute_rolling_metrics(
        self,
        equity: list[EquityPoint],
        window: Optional[int] = None,
    ) -> dict[str, Any]:
        """Compute rolling Sharpe and drawdown over equity curve.

        Delegates to ``StatisticsAggregator.rolling_metrics()``.

        Args:
            equity: List of EquityPoint objects (sorted by timestamp).
            window: Rolling window size (default from config).

        Returns:
            Dict with ``rolling_sharpe`` and ``rolling_drawdown``
            ``RollingMetrics`` as dicts.
        """
        win = window or self._rolling_window

        if not equity:
            logger.warning("Empty equity curve — cannot compute rolling metrics")
            return {}

        try:
            rolling = self._aggregator.rolling_metrics(
                equity=equity,
                window=win,
                metrics=["sharpe", "drawdown"],
                risk_free_rate=self._risk_free_rate,
                annual_factor=self._annual_factor,
            )
        except ValueError as e:
            logger.warning("Rolling metrics computation failed: %s", e)
            return {}

        # Convert to dicts for context serialization
        result = {}
        for metric_name, rm in rolling.items():
            result[metric_name] = (
                rm.model_dump() if hasattr(rm, "model_dump") else rm
            )
        return result

    def detect_regime_change(
        self,
        rolling_sharpe: list[float],
        rolling_drawdown: list[float],
        threshold_drop: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Detect regime changes from rolling metrics.

        A regime shift is flagged when the rolling Sharpe drops significantly
        (e.g. from >1.0 to <0.5) AND rolling drawdown spikes (>2x previous
        average).

        Args:
            rolling_sharpe: List of rolling Sharpe values (with NaN at start).
            rolling_drawdown: List of rolling drawdown values.
            threshold_drop: Fractional drop threshold (default 0.5 = 50% drop).

        Returns:
            List of regime alert dicts. Each alert has:
                - ``type``: str ("REGIME_SHIFT")
                - ``confidence``: float (0.0-1.0)
                - ``from_regime``: str
                - ``to_regime``: str
                - ``action``: str (suggested action)
        """
        alerts: list[dict[str, Any]] = []

        # Filter out NaN values
        valid_sharpes = [s for s in rolling_sharpe if not (isinstance(s, float) and math.isnan(s))]
        valid_drawdowns = [d for d in rolling_drawdown if not (isinstance(d, float) and math.isnan(d))]

        if len(valid_sharpes) < 20 or len(valid_drawdowns) < 20:
            return alerts

        # Split into two halves
        mid = len(valid_sharpes) // 2
        early_sharpes = valid_sharpes[:mid]
        late_sharpes = valid_sharpes[mid:]

        early_avg_sharpe = sum(early_sharpes) / len(early_sharpes)
        late_avg_sharpe = sum(late_sharpes) / len(late_sharpes)

        early_avg_dd = sum(valid_drawdowns[:mid]) / max(len(valid_drawdowns[:mid]), 1)
        late_avg_dd = sum(valid_drawdowns[mid:]) / max(len(valid_drawdowns[mid:]), 1)

        # Check for regime change
        sharpe_drop_ratio = late_avg_sharpe / early_avg_sharpe if early_avg_sharpe > 0 else 1.0
        dd_spike_ratio = late_avg_dd / early_avg_dd if early_avg_dd > 0 else 1.0

        if sharpe_drop_ratio < threshold_drop and dd_spike_ratio > 2.0:
            # Significant regime shift detected
            confidence = min(0.85, (1.0 - sharpe_drop_ratio) * 0.5 + min(dd_spike_ratio * 0.1, 0.35))

            from_regime = "trending" if early_avg_sharpe > 1.0 else "choppy"
            to_regime = "choppy" if from_regime == "trending" else "volatile"

            # Determine suggested action
            if to_regime == "choppy":
                action = "Reduce position size, widen stops"
            elif to_regime == "volatile":
                action = "Reduce position size, tighten stops, add volatility filter"
            else:
                action = "Review market regime alignment"

            alerts.append({
                "type": "REGIME_SHIFT",
                "confidence": round(confidence, 2),
                "from_regime": from_regime,
                "to_regime": to_regime,
                "action": action,
                "sharpe_drop_ratio": round(sharpe_drop_ratio, 3),
                "dd_spike_ratio": round(dd_spike_ratio, 3),
            })

        return alerts

    # ── Task 3.1: Pipeline Context Integration ──────────────────────────────────

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Execute the statistics agent stage.

        Implements ``StatisticsStage.execute()`` per the pipeline contract.

        Reads ``export_paths`` from context artifacts, computes statistics,
        aggregates, and rolling metrics, then writes results to context.

        Args:
            ctx: ``PipelineContext`` with ``export_paths`` in artifacts.

        Returns:
            Dict with ``statistics``, ``aggregate_stats``, ``monte_carlo_bands``,
            ``rolling_metrics``, and ``regime_alerts``.
        """
        return await self.run(ctx)

    async def run(self, context: PipelineContext) -> dict[str, Any]:
        """Execute the statistics agent stage.

        Args:
            context: ``PipelineContext`` with ``export_paths`` in artifacts.

        Returns:
            Dict with all statistics artifacts.
        """
        export_paths = context.artifacts.get("export_paths", [])
        if not export_paths:
            logger.warning(
                "No export_paths found in context artifacts — returning empty statistics"
            )
            empty_stats = StatsResult()
            return {
                "statistics": empty_stats.model_dump() if hasattr(empty_stats, "model_dump") else {},
                "aggregate_stats": {},
                "monte_carlo_bands": {},
                "rolling_metrics": {},
                "regime_alerts": [],
            }

        # Task 3.2: Compute statistics from exports
        statistics = self.compute_statistics(export_paths)
        statistics_dict = statistics.model_dump() if hasattr(statistics, "model_dump") else {}

        # Task 3.3: Cross-campaign aggregation and Monte Carlo bands
        # Read trades from exports for MC bands
        trades_path = self._resolve_export_path(export_paths, "trades.csv")
        mc_bands: dict[int, list[float]] = {}
        aggregate_stats: dict[str, Any] = {}

        if trades_path:
            trades = self._read_trades(trades_path)
            if trades:
                # Monte Carlo bands
                mc_bands = self.monte_carlo_bands(trades)

                # Assess robustness
                robustness = self.assess_robustness(statistics_dict, mc_bands)
                statistics_dict["robustness"] = robustness

        # Task 3.4: Rolling metrics
        equity_path = self._resolve_export_path(export_paths, "equity.csv")
        rolling_metrics: dict[str, Any] = {}
        regime_alerts: list[dict[str, Any]] = []

        if equity_path:
            equity = self._read_equity(equity_path)
            if equity:
                rolling_metrics = self.compute_rolling_metrics(equity)
                # Detect regime changes from rolling metrics
                rolling_sharpe = rolling_metrics.get("sharpe", {}).get("values", [])
                rolling_drawdown = rolling_metrics.get("drawdown", {}).get("values", [])
                regime_alerts = self.detect_regime_change(rolling_sharpe, rolling_drawdown)

        # Write to context artifacts
        context.artifacts["statistics"] = statistics_dict
        context.artifacts["aggregate_stats"] = aggregate_stats
        context.artifacts["monte_carlo_bands"] = mc_bands
        context.artifacts["rolling_metrics"] = rolling_metrics
        context.artifacts["regime_alerts"] = regime_alerts

        logger.info(
            "StatisticsAgent: computed %d metrics, MC bands at %s, %d regime alerts",
            len(statistics_dict),
            list(mc_bands.keys()),
            len(regime_alerts),
        )

        return {
            "statistics": statistics_dict,
            "aggregate_stats": aggregate_stats,
            "monte_carlo_bands": mc_bands,
            "rolling_metrics": rolling_metrics,
            "regime_alerts": regime_alerts,
        }
