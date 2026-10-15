"""Advanced Analysis Stage — regime-aware metrics, Pareto analysis, sensitivity & robustness.

Provides a pipeline stage that performs deeper statistical analysis on SQX
results to feed richer data into the Bayesian optimizer feedback loop.

Features:
- Regime-segmented metrics (trending/ranging/volatile)
- Tail risk metrics (VaR, CVaR, skewness, kurtosis)
- Pareto frontier analysis for multi-objective optimization
- Sensitivity analysis (parameter importance)
- Robustness checks (bootstrap stability, cross-validation)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from quantlab.analysis.models import StrategyAnalysis
    from quantlab.analysis.reader import AnalysisReader
    from quantlab.readers.models import EquityPoint, Trade


@dataclass
class RegimeMetrics:
    """Metrics computed for a specific market regime."""

    regime: str
    n_periods: int
    profit_factor: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    win_rate: float | None = None
    avg_return: float | None = None
    volatility: float | None = None
    skewness: float | None = None
    kurtosis: float | None = None
    var_95: float | None = None  # Value at Risk 95%
    cvar_95: float | None = None  # Conditional VaR 95%


@dataclass
class ParetoResult:
    """Result of Pareto frontier analysis."""

    # Non-dominated strategies (Pareto front)
    pareto_front: list[dict[str, Any]]
    # All strategies with their metric values
    all_strategies: list[dict[str, Any]]
    # Metrics used for Pareto analysis
    metrics_used: list[str]
    # Dominance count for each strategy
    dominance_counts: dict[str, int]


@dataclass
class SensitivityResult:
    """Result of sensitivity/parameter importance analysis."""

    # Parameter name -> importance score (0-1)
    parameter_importance: dict[str, float]
    # Metric -> top 3 parameters affecting it
    metric_drivers: dict[str, list[tuple[str, float]]]
    # Correlation matrix (parameters vs metrics)
    correlation_matrix: dict[str, dict[str, float]]


@dataclass
class RobustnessResult:
    """Result of robustness checks."""

    # Bootstrap stability: metric -> (mean, std, CI)
    bootstrap_stability: dict[str, tuple[float, float, tuple[float, float]]]
    # Cross-validation scores: metric -> list of fold scores
    cv_scores: dict[str, list[float]]
    # Stability score (0-1): how consistent metrics are across splits
    overall_stability: float


@dataclass
class AdvancedAnalysisResult:
    """Complete result of advanced analysis."""

    # Regime-segmented metrics
    regime_metrics: list[RegimeMetrics]
    # Pareto frontier analysis
    pareto: ParetoResult | None = None
    # Sensitivity analysis
    sensitivity: SensitivityResult | None = None
    # Robustness checks
    robustness: RobustnessResult | None = None
    # Summary
    summary: dict[str, Any] = field(default_factory=dict)


class AdvancedAnalysisEngine:
    """Engine for advanced statistical analysis of strategy results."""

    def __init__(
        self,
        n_bootstrap: int = 1000,
        cv_folds: int = 5,
        confidence_level: float = 0.95,
    ) -> None:
        """Initialize advanced analysis engine.

        Args:
            n_bootstrap: Number of bootstrap samples for stability.
            cv_folds: Number of cross-validation folds.
            confidence_level: Confidence level for intervals (e.g., 0.95).
        """
        self.n_bootstrap = n_bootstrap
        self.cv_folds = cv_folds
        self.confidence_level = confidence_level

    # ── Regime-Segmented Analysis ────────────────────────────────────────────

    def analyze_by_regime(
        self,
        trades: list[Trade],
        equity: list[EquityPoint],
        regime_labels: list[str] | None = None,
    ) -> list[RegimeMetrics]:
        """Compute metrics segmented by market regime.

        If regime_labels not provided, uses a simple heuristic:
        - Trending: returns > 0 with low volatility
        - Ranging: returns near 0 with moderate volatility
        - Volatile: high absolute returns with high volatility
        """
        if not trades or not equity:
            return []

        # Extract per-period returns from equity
        returns = self._equity_to_returns(equity)
        if len(returns) < 10:
            return []

        # Assign regimes if not provided
        if regime_labels is None:
            regime_labels = self._detect_regimes(returns)

        # Group trades and returns by regime
        unique_regimes = sorted(set(regime_labels))
        results = []

        for regime in unique_regimes:
            regime_mask = np.array(regime_labels) == regime
            regime_returns = np.array(returns)[regime_mask]
            regime_trades = [t for i, t in enumerate(trades) if i < len(regime_mask) and regime_mask[i]]

            if len(regime_returns) < 5:
                continue

            metrics = RegimeMetrics(
                regime=regime,
                n_periods=len(regime_returns),
                profit_factor=self._compute_pf(regime_trades),
                sharpe_ratio=self._compute_sharpe(regime_returns),
                max_drawdown=self._compute_mdd_from_returns(regime_returns),
                win_rate=self._compute_win_rate(regime_trades),
                avg_return=float(np.mean(regime_returns)),
                volatility=float(np.std(regime_returns, ddof=1)),
                skewness=self._compute_skewness(regime_returns),
                kurtosis=self._compute_kurtosis(regime_returns),
            )

            # Tail risk metrics
            if len(regime_returns) >= 20:
                metrics.var_95 = self._compute_var(regime_returns, 0.95)
                metrics.cvar_95 = self._compute_cvar(regime_returns, 0.95)

            results.append(metrics)

        return results

    def _detect_regimes(self, returns: list[float]) -> list[str]:
        """Simple regime detection based on return characteristics."""
        returns_arr = np.array(returns)
        # Rolling statistics
        window = min(20, len(returns_arr) // 3)
        if window < 5:
            return ["unknown"] * len(returns_arr)

        regimes = []
        for i in range(len(returns_arr)):
            start = max(0, i - window)
            window_returns = returns_arr[start:i+1]
            mean_r = np.mean(window_returns)
            std_r = np.std(window_returns, ddof=1)

            if std_r > np.std(returns_arr) * 1.5:
                regimes.append("volatile")
            elif abs(mean_r) > std_r * 0.5:
                regimes.append("trending")
            else:
                regimes.append("ranging")

        return regimes

    def _equity_to_returns(self, equity: list[EquityPoint]) -> list[float]:
        """Convert equity curve to returns."""
        if len(equity) < 2:
            return []
        returns = []
        for i in range(1, len(equity)):
            prev = equity[i-1].equity
            curr = equity[i].equity
            if prev > 0:
                returns.append((curr - prev) / prev)
        return returns

    # ── Tail Risk Metrics ────────────────────────────────────────────────────

    def _compute_var(self, returns: np.ndarray, level: float) -> float:
        """Value at Risk (VaR) at given confidence level."""
        if len(returns) == 0:
            return 0.0
        return float(-np.percentile(returns, (1 - level) * 100))

    def _compute_cvar(self, returns: np.ndarray, level: float) -> float:
        """Conditional Value at Risk (CVaR) at given confidence level."""
        if len(returns) == 0:
            return 0.0
        var = self._compute_var(returns, level)
        tail = returns[returns <= -var]
        if len(tail) == 0:
            return var
        return float(-np.mean(tail))

    def _compute_skewness(self, returns: np.ndarray) -> float:
        """Sample skewness."""
        if len(returns) < 3:
            return 0.0
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        if std == 0:
            return 0.0
        n = len(returns)
        return float(np.sum(((returns - mean) / std) ** 3) * n / ((n - 1) * (n - 2)))

    def _compute_kurtosis(self, returns: np.ndarray) -> float:
        """Sample excess kurtosis."""
        if len(returns) < 4:
            return 0.0
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        if std == 0:
            return 0.0
        n = len(returns)
        kurt = np.sum(((returns - mean) / std) ** 4) * n * (n + 1) / ((n - 1) * (n - 2) * (n - 3))
        return float(kurt - 3 * (n - 1) ** 2 / ((n - 2) * (n - 3)))  # Excess kurtosis

    # ── Standard Metrics (for regime segments) ────────────────────────────────

    def _compute_pf(self, trades: list[Trade]) -> float | None:
        if not trades:
            return None
        gross_profit = sum(t.profit for t in trades if t.profit > 0)
        gross_loss = sum(t.profit for t in trades if t.profit < 0)
        if gross_loss == 0:
            return float("inf")
        return gross_profit / abs(gross_loss)

    def _compute_sharpe(self, returns: np.ndarray) -> float | None:
        if len(returns) < 2:
            return None
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        if std == 0:
            return float("inf") if mean > 0 else 0.0
        return float(mean / std * np.sqrt(252))

    def _compute_mdd_from_returns(self, returns: np.ndarray) -> float | None:
        if len(returns) == 0:
            return None
        equity = np.cumprod(1 + returns)
        peak = np.maximum.accumulate(equity)
        dd = (peak - equity) / peak
        return float(np.max(dd) * 100)

    def _compute_win_rate(self, trades: list[Trade]) -> float | None:
        if not trades:
            return None
        wins = sum(1 for t in trades if t.profit > 0)
        return wins / len(trades)

    # ── Pareto Frontier Analysis ─────────────────────────────────────────────

    def compute_pareto_frontier(
        self,
        strategies: list[StrategyAnalysis],
        metrics: list[str] = ("profit_factor", "sharpe_ratio", "max_drawdown", "win_rate"),
        maximize: dict[str, bool] | None = None,
    ) -> ParetoResult:
        """Compute Pareto frontier for multi-objective optimization.

        Args:
            strategies: List of analyzed strategies.
            metrics: Metric names to use for Pareto analysis.
            maximize: Dict mapping metric -> whether to maximize (True) or minimize (False).

        Returns:
            ParetoResult with front and dominance info.
        """
        if not strategies:
            return ParetoResult(
                pareto_front=[],
                all_strategies=[],
                metrics_used=metrics,
                dominance_counts={},
            )

        if maximize is None:
            maximize = {
                "profit_factor": True,
                "sharpe_ratio": True,
                "max_drawdown": False,  # Minimize
                "win_rate": True,
                "mar_ratio": True,
                "recovery_factor": True,
                "expectancy_ratio": True,
            }

        # Extract metric values for each strategy
        strategy_data = []
        for s in strategies:
            row = {"name": s.name, "score": s.score}
            for m in metrics:
                val = getattr(s.metrics, m, None)
                row[m] = val
            strategy_data.append(row)

        # Compute dominance
        n = len(strategy_data)
        dominance_counts = {s["name"]: 0 for s in strategy_data}
        is_dominated = [False] * n

        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                if self._dominates(strategy_data[j], strategy_data[i], metrics, maximize):
                    dominance_counts[strategy_data[i]["name"]] += 1
                    is_dominated[i] = True
                    break

        pareto_front = [s for i, s in enumerate(strategy_data) if not is_dominated[i]]

        return ParetoResult(
            pareto_front=pareto_front,
            all_strategies=strategy_data,
            metrics_used=metrics,
            dominance_counts=dominance_counts,
        )

    def _dominates(
        self,
        a: dict[str, Any],
        b: dict[str, Any],
        metrics: list[str],
        maximize: dict[str, bool],
    ) -> bool:
        """Check if strategy a dominates strategy b."""
        at_least_one_better = False
        for m in metrics:
            va, vb = a.get(m), b.get(m)
            if va is None or vb is None:
                continue
            if maximize.get(m, True):
                if va < vb:
                    return False
                if va > vb:
                    at_least_one_better = True
            else:  # minimize
                if va > vb:
                    return False
                if va < vb:
                    at_least_one_better = True
        return at_least_one_better

    # ── Sensitivity Analysis ──────────────────────────────────────────────────

    def compute_sensitivity(
        self,
        param_history: list[dict[str, Any]],
        metric_history: list[dict[str, float]],
    ) -> SensitivityResult:
        """Compute parameter importance via correlation and mutual information.

        Args:
            param_history: List of parameter dicts from optimization history.
            metric_history: List of metric dicts corresponding to each param set.

        Returns:
            SensitivityResult with importance scores and drivers.
        """
        if not param_history or not metric_history or len(param_history) != len(metric_history):
            return SensitivityResult(
                parameter_importance={},
                metric_drivers={},
                correlation_matrix={},
            )

        # Get parameter names
        param_names = list(param_history[0].keys())
        metric_names = list(metric_history[0].keys())

        # Build arrays
        X = np.array([[p.get(name, 0) for name in param_names] for p in param_history])
        Y = np.array([[m.get(name, 0) for name in metric_names] for m in metric_history])

        # Correlation matrix
        correlation_matrix = {}
        for i, pname in enumerate(param_names):
            correlation_matrix[pname] = {}
            for j, mname in enumerate(metric_names):
                if np.std(X[:, i]) > 0 and np.std(Y[:, j]) > 0:
                    corr = np.corrcoef(X[:, i], Y[:, j])[0, 1]
                    correlation_matrix[pname][mname] = float(corr)
                else:
                    correlation_matrix[pname][mname] = 0.0

        # Parameter importance = max absolute correlation across metrics
        parameter_importance = {}
        for pname in param_names:
            max_corr = max(abs(c) for c in correlation_matrix[pname].values())
            parameter_importance[pname] = float(max_corr)

        # Metric drivers = top 3 parameters for each metric
        metric_drivers = {}
        for mname in metric_names:
            drivers = sorted(
                [(pname, correlation_matrix[pname][mname]) for pname in param_names],
                key=lambda x: abs(x[1]),
                reverse=True,
            )[:3]
            metric_drivers[mname] = drivers

        return SensitivityResult(
            parameter_importance=parameter_importance,
            metric_drivers=metric_drivers,
            correlation_matrix=correlation_matrix,
        )

    # ── Robustness Checks ────────────────────────────────────────────────────

    def check_robustness(
        self,
        metric_values: list[float],
    ) -> RobustnessResult:
        """Check robustness via bootstrap and cross-validation.

        Args:
            metric_values: Time series of metric values (e.g., daily returns).

        Returns:
            RobustnessResult with stability metrics.
        """
        if len(metric_values) < self.cv_folds * 2:
            return RobustnessResult(
                bootstrap_stability={},
                cv_scores={},
                overall_stability=0.0,
            )

        arr = np.array(metric_values)

        # Bootstrap stability
        bootstrap_means = []
        for _ in range(self.n_bootstrap):
            sample = np.random.choice(arr, size=len(arr), replace=True)
            bootstrap_means.append(np.mean(sample))

        bootstrap_mean = np.mean(bootstrap_means)
        bootstrap_std = np.std(bootstrap_means, ddof=1)
        alpha = 1 - self.confidence_level
        ci = (
            float(np.percentile(bootstrap_means, alpha / 2 * 100)),
            float(np.percentile(bootstrap_means, (1 - alpha / 2) * 100)),
        )

        # Cross-validation
        fold_size = len(arr) // self.cv_folds
        cv_scores = []
        for i in range(self.cv_folds):
            start = i * fold_size
            end = start + fold_size if i < self.cv_folds - 1 else len(arr)
            fold_data = arr[start:end]
            if len(fold_data) > 0:
                cv_scores.append(float(np.mean(fold_data)))

        # Overall stability = 1 - (CV of bootstrap means)
        cv_of_mean = bootstrap_std / abs(bootstrap_mean) if bootstrap_mean != 0 else 1.0
        overall_stability = max(0.0, 1.0 - cv_of_mean)

        return RobustnessResult(
            bootstrap_stability={"mean": (bootstrap_mean, bootstrap_std, ci)},
            cv_scores={"metric": cv_scores},
            overall_stability=overall_stability,
        )

    # ── Full Advanced Analysis ────────────────────────────────────────────────

    def run_full_analysis(
        self,
        strategies: list[StrategyAnalysis],
        trades_by_strategy: dict[str, list[Trade]] | None = None,
        equity_by_strategy: dict[str, list[EquityPoint]] | None = None,
        param_history: list[dict[str, Any]] | None = None,
        metric_history: list[dict[str, float]] | None = None,
    ) -> AdvancedAnalysisResult:
        """Run complete advanced analysis pipeline."""
        result = AdvancedAnalysisResult()

        # Regime analysis (uses first strategy's data if available)
        if trades_by_strategy and equity_by_strategy:
            first_strat = next(iter(trades_by_strategy))
            result.regime_metrics = self.analyze_by_regime(
                trades_by_strategy[first_strat],
                equity_by_strategy[first_strat],
            )

        # Pareto analysis
        if strategies:
            result.pareto = self.compute_pareto_frontier(strategies)

        # Sensitivity analysis
        if param_history and metric_history:
            result.sensitivity = self.compute_sensitivity(param_history, metric_history)

        # Robustness (uses equity returns from first strategy)
        if equity_by_strategy:
            first_strat = next(iter(equity_by_strategy))
            returns = self._equity_to_returns(equity_by_strategy[first_strat])
            if returns:
                result.robustness = self.check_robustness(returns)

        # Summary
        result.summary = {
            "n_strategies": len(strategies),
            "n_regimes": len(result.regime_metrics),
            "pareto_size": len(result.pareto.pareto_front) if result.pareto else 0,
            "top_parameters": sorted(
                result.sensitivity.parameter_importance.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5] if result.sensitivity else [],
            "overall_stability": result.robustness.overall_stability if result.robustness else 0.0,
        }

        return result


def create_advanced_analysis_engine(**kwargs) -> AdvancedAnalysisEngine:
    """Factory function to create AdvancedAnalysisEngine."""
    return AdvancedAnalysisEngine(**kwargs)