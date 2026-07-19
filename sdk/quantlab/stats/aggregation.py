"""Statistics Aggregation — campaign/portfolio-level metric aggregation and rolling analytics.

Provides stateless aggregation methods for campaign results, walk-forward cycles,
rolling metrics, benchmark comparison, and Monte Carlo bootstrap bands.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import numpy as np
import pandas as pd

from quantlab.readers.models import EquityPoint, Trade
from quantlab.phase4.optimizer import WalkForwardCycle
from quantlab.stats.engine import StatisticsEngine
from quantlab.stats.models import (
    AggregateStats,
    BenchmarkComparison,
    RollingMetrics,
)

if TYPE_CHECKING:
    from quantlab.phase4.campaign_orchestrator import CampaignResult


class StatisticsAggregator:
    """Stateless aggregation of trading metrics across campaigns and cycles.

    All methods are static — no instance state. Operates on campaign results,
    walk-forward cycles, equity curves, and trade lists using pandas/numpy
    for statistical computations.

    Usage::
        agg = StatisticsAggregator()

        # Aggregate across campaign results
        agg_stats = agg.aggregate_campaigns(campaign_results)

        # Rolling Sharpe on equity curve
        rolling = agg.rolling_sharpe(equity_points, window=252)

        # Benchmark comparison
        bench = agg.benchmark_compare(strategy_returns, benchmark_returns)

        # Monte Carlo bootstrap bands
        mc_bands = agg.monte_carlo_bands(trades, n_simulations=1000)
    """

    # ── Campaign Aggregation ─────────────────────────────────────────────────────

    @staticmethod
    def aggregate_campaigns(
        campaign_results: list["CampaignResult"],
    ) -> dict[str, AggregateStats]:
        """Aggregate metrics across multiple campaign results.

        Extracts key metrics from each campaign's statistics dict and computes
        aggregate statistics (mean, median, std, min, max, p25, p75, count)
        for each metric across all campaigns.

        Args:
            campaign_results: List of CampaignResult objects from phase4 orchestrator.

        Returns:
            Dict mapping metric name -> AggregateStats.
            Metrics: sharpe, profit_factor, max_drawdown, win_rate, expectancy, total_trades.

        Raises:
            ValueError: If campaign_results is empty.
        """
        if not campaign_results:
            return {}

        # Collect metric values across campaigns
        metric_values: dict[str, list[float]] = {
            "sharpe": [],
            "profit_factor": [],
            "max_drawdown": [],
            "win_rate": [],
            "expectancy": [],
            "total_trades": [],
        }

        from quantlab.stats.engine import StatisticsEngine

        engine = StatisticsEngine()

        for result in campaign_results:
            stats = result.statistics or {}

            # If statistics dict is empty or missing keys, compute from trades/equity
            if not stats and (result.trades or result.equity):
                trades = result.trades or []
                equity = result.equity or []

                # Convert to proper types if needed
                if trades and isinstance(trades[0], dict):
                    trades = [Trade(**t) if isinstance(t, dict) else t for t in trades]
                if equity and isinstance(equity[0], dict):
                    equity = [EquityPoint(**e) if isinstance(e, dict) else e for e in equity]

                # Compute returns from equity
                returns = []
                if len(equity) >= 2:
                    eq_vals = [e.equity for e in equity]
                    for i in range(1, len(eq_vals)):
                        if eq_vals[i - 1] != 0:
                            returns.append((eq_vals[i] - eq_vals[i - 1]) / eq_vals[i - 1])

                try:
                    computed = engine.compute_all(
                        trades=trades if trades else None,
                        equity=equity if equity else None,
                        returns=returns if returns else None,
                    )
                    # Merge computed stats into stats dict
                    computed_dict = computed.model_dump() if hasattr(computed, "model_dump") else computed.__dict__
                    stats.update({k: v for k, v in computed_dict.items() if v is not None})

                    # Also compute win_rate and total_trades from trades directly
                    if trades:
                        total = len(trades)
                        winning = sum(1 for t in trades if t.profit > 0)
                        stats["win_rate"] = winning / total if total > 0 else 0.0
                        stats["total_trades"] = total
                except Exception:
                    pass  # Fall back to whatever is in stats

            # Extract metrics with various possible key names
            metric_map = {
                "sharpe": ["sharpe_ratio", "sharpe", "SharpeRatio"],
                "profit_factor": ["profit_factor", "ProfitFactor", "profitfactor"],
                "max_drawdown": ["max_drawdown", "maxdrawdown", "MaxDrawdown", "drawdown"],
                "win_rate": ["win_rate", "winrate", "WinRate"],
                "expectancy": ["expectancy", "Expectancy"],
                "total_trades": ["total_trades", "totaltrades", "TotalTrades"],
            }

            for metric, keys in metric_map.items():
                for key in keys:
                    if key in stats and stats[key] is not None:
                        try:
                            val = float(stats[key])
                            if not math.isnan(val) and not math.isinf(val):
                                metric_values[metric].append(val)
                        except (ValueError, TypeError):
                            pass
                        break  # Use first matching key

        # Compute aggregates for each metric
        aggregates: dict[str, AggregateStats] = {}
        for metric, values in metric_values.items():
            if values:
                aggregates[metric] = StatisticsAggregator._compute_aggregate_stats(values)
            else:
                # Empty aggregate with NaN values
                aggregates[metric] = AggregateStats(
                    mean=math.nan,
                    median=math.nan,
                    std=math.nan,
                    min=math.nan,
                    max=math.nan,
                    p25=math.nan,
                    p75=math.nan,
                    count=0,
                )

        return aggregates

    @staticmethod
    def aggregate_wf_cycles(
        cycles: list[WalkForwardCycle],
    ) -> dict[str, AggregateStats]:
        """Aggregate out-of-sample metrics across walk-forward cycles.

        Uses OOS (out-of-sample) metrics from each WalkForwardCycle.
        Computes aggregate statistics for each metric found in the cycles.

        Args:
            cycles: List of WalkForwardCycle objects from optimizer results.

        Returns:
            Dict mapping metric name -> AggregateStats.
            Metric names are normalized to lowercase with underscores.
        """
        if not cycles:
            return {}

        # Normalize metric names (lowercase, spaces/dashes to underscores, PascalCase to snake_case)
        def normalize(name: str) -> str:
            import re
            # Insert underscore before uppercase letters (except first)
            s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
            # Insert underscore between lowercase and uppercase
            s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
            return s2.lower().replace(" ", "_").replace("-", "_")

        # Collect all metric names from all cycles
        all_metrics: set[str] = set()
        for cycle in cycles:
            for k in cycle.metrics.keys():
                all_metrics.add(normalize(k))

        # Collect values for each normalized metric
        metric_values: dict[str, list[float]] = {m: [] for m in all_metrics}
        for cycle in cycles:
            for metric, value in cycle.metrics.items():
                norm_metric = normalize(metric)
                try:
                    val = float(value)
                    if not math.isnan(val) and not math.isinf(val):
                        metric_values[norm_metric].append(val)
                except (ValueError, TypeError):
                    pass

        # Compute aggregates
        aggregates: dict[str, AggregateStats] = {}
        for metric, values in metric_values.items():
            if values:
                aggregates[metric] = StatisticsAggregator._compute_aggregate_stats(values)
            else:
                aggregates[metric] = AggregateStats(
                    mean=math.nan,
                    median=math.nan,
                    std=math.nan,
                    min=math.nan,
                    max=math.nan,
                    p25=math.nan,
                    p75=math.nan,
                    count=0,
                )

        return aggregates

    # ── Rolling Metrics ──────────────────────────────────────────────────────────

    @staticmethod
    def rolling_sharpe(
        equity: list[EquityPoint],
        window: int,
        risk_free_rate: float = 0.0,
        annual_factor: int = 252,
    ) -> RollingMetrics:
        """Compute rolling Sharpe ratio over equity curve.

        Uses pandas rolling window on period returns.
        First (window-1) values are NaN.

        Args:
            equity: List of EquityPoint objects (must be sorted by timestamp).
            window: Rolling window size in periods.
            risk_free_rate: Risk-free rate per period.
            annual_factor: Periods per year for annualization (252 for daily).

        Returns:
            RollingMetrics with timestamps and Sharpe values.

        Raises:
            ValueError: If equity list is empty, has fewer than 2 points, or window < 2.
        """
        if not equity:
            raise ValueError("Empty equity list — cannot compute rolling Sharpe.")
        if len(equity) < 2:
            raise ValueError("At least 2 equity points required for rolling Sharpe.")
        if window < 2:
            raise ValueError("Window must be at least 2 for rolling Sharpe.")

        # Convert to pandas Series with datetime index
        timestamps = [e.timestamp for e in equity]
        equities = [e.equity for e in equity]

        eq_series = pd.Series(equities, index=pd.DatetimeIndex(timestamps))

        # Compute period returns
        returns = eq_series.pct_change().dropna()

        if len(returns) < window:
            # Not enough data for even one full window
            return RollingMetrics(
                timestamps=timestamps,
                values=[float("nan")] * len(timestamps),
                window=window,
                metric_name="rolling_sharpe",
            )

        # Rolling Sharpe: (mean - rf) / std * sqrt(annual_factor)
        def sharpe_func(x: pd.Series) -> float:
            if len(x) < 2:
                return float("nan")
            mean_r = x.mean()
            std_r = x.std(ddof=1)
            if std_r == 0:
                return float("inf") if (mean_r - risk_free_rate) > 0 else 0.0
            return ((mean_r - risk_free_rate) / std_r) * math.sqrt(annual_factor)

        rolling_sharpe = returns.rolling(window=window).apply(sharpe_func, raw=False)

        # Align with original timestamps (prepend NaN for first return)
        values = [float("nan")] + rolling_sharpe.tolist()
        # Pad to match equity length
        while len(values) < len(timestamps):
            values.append(float("nan"))
        values = values[: len(timestamps)]

        return RollingMetrics(
            timestamps=timestamps,
            values=values,
            window=window,
            metric_name="rolling_sharpe",
        )

    @staticmethod
    def rolling_drawdown(
        equity: list[EquityPoint],
        window: int,
    ) -> RollingMetrics:
        """Compute rolling maximum drawdown over equity curve.

        For each window, computes the max peak-to-trough decline within that window.

        Args:
            equity: List of EquityPoint objects (sorted by timestamp).
            window: Rolling window size in periods.

        Returns:
            RollingMetrics with timestamps and drawdown values (percentage).

        Raises:
            ValueError: If equity list is empty or window < 2.
        """
        if not equity:
            raise ValueError("Empty equity list — cannot compute rolling drawdown.")
        if window < 2:
            raise ValueError("Window must be at least 2 for rolling drawdown.")

        timestamps = [e.timestamp for e in equity]
        equities = [e.equity for e in equity]

        eq_series = pd.Series(equities, index=pd.DatetimeIndex(timestamps))

        # Rolling max drawdown within window
        def max_dd_func(x: pd.Series) -> float:
            if len(x) < 2:
                return float("nan")
            peak = x.iloc[0]
            max_dd = 0.0
            for val in x:
                if val > peak:
                    peak = val
                if peak > 0:
                    dd = (peak - val) / peak * 100
                    if dd > max_dd:
                        max_dd = dd
            return max_dd

        rolling_dd = eq_series.rolling(window=window).apply(max_dd_func, raw=False)

        values = rolling_dd.tolist()
        # Pad to match equity length
        while len(values) < len(timestamps):
            values.insert(0, float("nan"))
        values = values[: len(timestamps)]

        return RollingMetrics(
            timestamps=timestamps,
            values=values,
            window=window,
            metric_name="rolling_drawdown",
        )

    @staticmethod
    def rolling_metrics(
        equity: list[EquityPoint],
        window: int,
        metrics: list[str],
        risk_free_rate: float = 0.0,
        annual_factor: int = 252,
    ) -> dict[str, RollingMetrics]:
        """Compute multiple rolling metrics over equity curve.

        Args:
            equity: List of EquityPoint objects (sorted by timestamp).
            window: Rolling window size.
            metrics: List of metric names to compute.
                     Supported: "sharpe", "sortino", "drawdown", "return", "volatility".
            risk_free_rate: Risk-free rate per period.
            annual_factor: Periods per year for annualization.

        Returns:
            Dict mapping metric name -> RollingMetrics.

        Raises:
            ValueError: If equity empty, window < 2, or unknown metric.
        """
        if not equity:
            raise ValueError("Empty equity list.")
        if window < 2:
            raise ValueError("Window must be at least 2.")

        supported = {"sharpe", "sortino", "drawdown", "return", "volatility"}
        unknown = set(metrics) - supported
        if unknown:
            raise ValueError(f"Unknown metrics: {unknown}. Supported: {supported}")

        timestamps = [e.timestamp for e in equity]
        equities = [e.equity for e in equity]
        eq_series = pd.Series(equities, index=pd.DatetimeIndex(timestamps))
        returns = eq_series.pct_change().dropna()

        results: dict[str, RollingMetrics] = {}

        def pad_values(raw_values: list[float]) -> list[float]:
            """Pad with NaN at start to match equity length."""
            while len(raw_values) < len(timestamps):
                raw_values.insert(0, float("nan"))
            return raw_values[: len(timestamps)]

        for metric in metrics:
            if metric == "sharpe":
                def sharpe_func(x: pd.Series) -> float:
                    if len(x) < 2:
                        return float("nan")
                    mean_r = x.mean()
                    std_r = x.std(ddof=1)
                    if std_r == 0:
                        return float("inf") if (mean_r - risk_free_rate) > 0 else 0.0
                    return ((mean_r - risk_free_rate) / std_r) * math.sqrt(annual_factor)

                rolling = returns.rolling(window=window).apply(sharpe_func, raw=False)
                values = pad_values([float("nan")] + rolling.tolist())

            elif metric == "sortino":
                def sortino_func(x: pd.Series) -> float:
                    if len(x) < 2:
                        return float("nan")
                    mean_r = x.mean()
                    downside = x[x < risk_free_rate]
                    if len(downside) == 0:
                        return float("inf")
                    downside_std = downside.std(ddof=1)
                    if downside_std == 0:
                        return float("inf")
                    return ((mean_r - risk_free_rate) / downside_std) * math.sqrt(annual_factor)

                rolling = returns.rolling(window=window).apply(sortino_func, raw=False)
                values = pad_values([float("nan")] + rolling.tolist())

            elif metric == "drawdown":
                def max_dd_func(x: pd.Series) -> float:
                    if len(x) < 2:
                        return float("nan")
                    peak = x.iloc[0]
                    max_dd = 0.0
                    for val in x:
                        if val > peak:
                            peak = val
                        if peak > 0:
                            dd = (peak - val) / peak * 100
                            if dd > max_dd:
                                max_dd = dd
                    return max_dd

                rolling = eq_series.rolling(window=window).apply(max_dd_func, raw=False)
                values = pad_values(rolling.tolist())

            elif metric == "return":
                # Rolling cumulative return
                def cumret_func(x: pd.Series) -> float:
                    if len(x) < 2:
                        return float("nan")
                    return (x.iloc[-1] / x.iloc[0] - 1) * 100 if x.iloc[0] != 0 else float("nan")

                rolling = eq_series.rolling(window=window).apply(cumret_func, raw=False)
                values = pad_values(rolling.tolist())

            elif metric == "volatility":
                # Rolling annualized volatility
                def vol_func(x: pd.Series) -> float:
                    if len(x) < 2:
                        return float("nan")
                    return x.std(ddof=1) * math.sqrt(annual_factor)

                rolling = returns.rolling(window=window).apply(vol_func, raw=False)
                values = pad_values([float("nan")] + rolling.tolist())

            results[metric] = RollingMetrics(
                timestamps=timestamps,
                values=values,
                window=window,
                metric_name=f"rolling_{metric}",
            )

        return results

    # ── Benchmark Comparison ─────────────────────────────────────────────────────

    @staticmethod
    def benchmark_compare(
        strategy_returns: list[float],
        benchmark_returns: list[float],
        risk_free_rate: float = 0.0,
    ) -> BenchmarkComparison:
        """Compare strategy returns against benchmark.

        Computes Alpha, Beta, Information Ratio, Correlation, and Tracking Error
        using pandas Series covariance/variance.

        Args:
            strategy_returns: List of strategy period returns.
            benchmark_returns: List of benchmark period returns (same length).
            risk_free_rate: Risk-free rate per period.

        Returns:
            BenchmarkComparison with all metrics.

        Raises:
            ValueError: If lists have different lengths or are empty.
        """
        if len(strategy_returns) != len(benchmark_returns):
            raise ValueError(
                f"Return series length mismatch: strategy={len(strategy_returns)}, "
                f"benchmark={len(benchmark_returns)}"
            )
        if not strategy_returns:
            raise ValueError("Empty return series — cannot compute benchmark comparison.")

        strat = pd.Series(strategy_returns)
        bench = pd.Series(benchmark_returns)

# Beta = Cov(strategy, benchmark) / Var(benchmark)
        cov = strat.cov(bench)
        bench_var = bench.var(ddof=1)

        # Handle near-zero variance (benchmark is constant/near-constant)
        if abs(bench_var) < 1e-15:
            # If covariance is also near zero and series are nearly identical, beta = 1
            # This handles the case where both series are constant and identical
            if abs(cov) < 1e-15:
                # Check if series are nearly identical
                if abs(strat.mean() - bench.mean()) < 1e-15:
                    beta = 1.0
                else:
                    beta = float("nan")
            else:
                beta = float("nan")
        else:
            beta = cov / bench_var

        # Alpha = mean(strategy) - beta * mean(benchmark) - risk_free_rate
        strat_mean = strat.mean()
        bench_mean = bench.mean()
        alpha = strat_mean - beta * bench_mean - risk_free_rate

        # Tracking Error = std(strategy - benchmark)
        active_returns = strat - bench
        tracking_error = active_returns.std(ddof=1) * math.sqrt(252)  # annualized

        # Information Ratio = mean(active_returns) / tracking_error (period)
        if tracking_error == 0:
            info_ratio = float("inf") if active_returns.mean() > 0 else 0.0
        else:
            info_ratio = (active_returns.mean() / active_returns.std(ddof=1)) * math.sqrt(252)

        # Correlation
        correlation = strat.corr(bench)

        return BenchmarkComparison(
            alpha=alpha,
            beta=beta,
            information_ratio=info_ratio,
            correlation=correlation,
            tracking_error=tracking_error,
        )

    # ── Monte Carlo Bootstrap ────────────────────────────────────────────────────

    @staticmethod
    def monte_carlo_bands(
        trades: list[Trade],
        n_simulations: int = 1000,
        percentiles: Optional[list[int]] = None,
        seed: int = 42,
    ) -> dict[int, float]:
        """Bootstrap resampling of trade PnL to estimate profit distribution.

        Randomly samples trades with replacement to build equity curves,
        computes net profit for each simulation, returns specified percentiles.

        Args:
            trades: List of Trade objects with profit attribute.
            n_simulations: Number of bootstrap iterations (default 1000).
            percentiles: List of percentiles to compute (default [10, 50, 90]).
            seed: Random seed for reproducibility (default 42).

        Returns:
            Dict mapping percentile -> net profit at that percentile.

        Raises:
            ValueError: If trades list is empty.
        """
        if not trades:
            raise ValueError("Empty trades list — cannot run Monte Carlo bootstrap.")

        if percentiles is None:
            percentiles = [10, 50, 90]

        profits = np.array([t.profit for t in trades], dtype=np.float64)
        n_trades = len(profits)

        np.random.seed(seed)

        sim_results = np.zeros(n_simulations, dtype=np.float64)

        for i in range(n_simulations):
            # Bootstrap sample with replacement
            sample = np.random.choice(profits, size=n_trades, replace=True)
            sim_results[i] = sample.sum()

        result = {}
        for p in percentiles:
            result[p] = float(np.percentile(sim_results, p))

        return result

    # ── Internal Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _compute_aggregate_stats(values: list[float]) -> AggregateStats:
        """Compute aggregate statistics for a list of values."""
        arr = np.array(values, dtype=np.float64)
        n = len(arr)
        if n == 0:
            return AggregateStats(
                mean=math.nan,
                median=math.nan,
                std=math.nan,
                min=math.nan,
                max=math.nan,
                p25=math.nan,
                p75=math.nan,
                count=0,
            )
        elif n == 1:
            val = float(arr[0])
            return AggregateStats(
                mean=val,
                median=val,
                std=0.0,  # std of single value is 0
                min=val,
                max=val,
                p25=val,
                p75=val,
                count=1,
            )
        else:
            arr = np.array(values, dtype=np.float64)
            return AggregateStats(
                mean=float(np.mean(arr)),
                median=float(np.median(arr)),
                std=float(np.std(arr, ddof=1)),
                min=float(np.min(arr)),
                max=float(np.max(arr)),
                p25=float(np.percentile(arr, 25)),
                p75=float(np.percentile(arr, 75)),
                count=len(arr),
            )