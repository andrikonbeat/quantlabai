"""AdvancedAnalysisStage — Pipeline stage for deep statistical analysis.

Runs after SQX execution/monitoring to perform advanced analytics:
- Regime-segmented metrics
- Pareto frontier for multi-objective optimization
- Sensitivity analysis (parameter importance)
- Robustness checks (bootstrap, cross-validation)

Feeds enriched data into Bayesian optimizer feedback loop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quantlab.analysis.advanced import (
        AdvancedAnalysisEngine,
        AdvancedAnalysisResult,
    )
    from quantlab.analysis.models import StrategyAnalysis
    from quantlab.readers.models import EquityPoint, Trade

from quantlab.pipeline.base import PipelineContext, Stage


class AdvancedAnalysisStage(Stage):
    """Advanced statistical analysis pipeline stage.

    **Requires**: strategy_analysis, export_paths (for trades/equity)
    **Provides**: advanced_analysis_result, regime_metrics, pareto_frontier,
                  sensitivity_analysis, robustness_check

    Runs after AnalysisAgent to enrich the strategy analysis with:
    - Regime-aware metrics
    - Multi-objective Pareto frontier
    - Parameter sensitivity drivers
    - Robustness/stability scores
    """

    name: str = "advanced_analysis"
    requires: list[str] = ["strategy_analysis"]
    provides: list[str] = [
        "advanced_analysis_result",
        "regime_metrics",
        "pareto_frontier",
        "sensitivity_analysis",
        "robustness_check",
    ]

    def __init__(
        self,
        engine: Any = None,  # Injected for testing
        n_bootstrap: int = 1000,
        cv_folds: int = 5,
        confidence_level: float = 0.95,
    ) -> None:
        """Initialize advanced analysis stage.

        Args:
            engine: Pre-configured AdvancedAnalysisEngine (for testing).
            n_bootstrap: Bootstrap samples for stability.
            cv_folds: Cross-validation folds.
            confidence_level: Confidence level for intervals.
        """
        self._engine = engine
        self._n_bootstrap = n_bootstrap
        self._cv_folds = cv_folds
        self._confidence_level = confidence_level

    def _get_engine(self) -> AdvancedAnalysisEngine:
        """Get or create the analysis engine."""
        if self._engine is not None:
            return self._engine

        from quantlab.analysis.advanced import AdvancedAnalysisEngine
        return AdvancedAnalysisEngine(
            n_bootstrap=self._n_bootstrap,
            cv_folds=self._cv_folds,
            confidence_level=self._confidence_level,
        )

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Execute advanced analysis.

        Args:
            ctx: Pipeline context with strategy_analysis and export_paths.

        Returns:
            Dict with advanced analysis artifacts.
        """
        strategy_analysis: list[StrategyAnalysis] = ctx.artifacts.get("strategy_analysis", [])

        if not strategy_analysis:
            # No strategies to analyze
            empty_result = {
                "regime_metrics": [],
                "pareto_frontier": [],
                "sensitivity_analysis": {},
                "robustness_check": {},
                "summary": {"n_strategies": 0},
            }
            ctx.artifacts["advanced_analysis_result"] = empty_result
            ctx.artifacts["regime_metrics"] = []
            ctx.artifacts["pareto_frontier"] = []
            ctx.artifacts["sensitivity_analysis"] = {}
            ctx.artifacts["robustness_check"] = {}
            return empty_result

        # Try to load trades and equity from export paths
        trades_by_strategy: dict[str, list[Trade]] = {}
        equity_by_strategy: dict[str, list[EquityPoint]] = {}

        export_paths = ctx.artifacts.get("export_paths", [])
        if export_paths:
            trades_by_strategy, equity_by_strategy = self._load_trades_equity(export_paths)

        # Get optimization history for sensitivity analysis
        param_history = ctx.artifacts.get("bayesian_param_history", [])
        metric_history = ctx.artifacts.get("bayesian_metric_history", [])

        # Run advanced analysis
        engine = self._get_engine()
        result: AdvancedAnalysisResult = engine.run_full_analysis(
            strategies=strategy_analysis,
            trades_by_strategy=trades_by_strategy if trades_by_strategy else None,
            equity_by_strategy=equity_by_strategy if equity_by_strategy else None,
            param_history=param_history if param_history else None,
            metric_history=metric_history if metric_history else None,
        )

        # Prepare artifacts
        artifacts = {
            "advanced_analysis_result": self._serialize_result(result),
            "regime_metrics": [self._serialize_regime(m) for m in result.regime_metrics],
            "pareto_frontier": self._serialize_pareto(result.pareto) if result.pareto else [],
            "sensitivity_analysis": self._serialize_sensitivity(result.sensitivity) if result.sensitivity else {},
            "robustness_check": self._serialize_robustness(result.robustness) if result.robustness else {},
        }

        # Publish to context
        for key, value in artifacts.items():
            ctx.artifacts[key] = value

        return artifacts

    def _load_trades_equity(
        self,
        export_paths: list[str],
    ) -> tuple[dict[str, list[Trade]], dict[str, list[EquityPoint]]]:
        """Load trades and equity from SQX export files."""
        trades_by_strategy = {}
        equity_by_strategy = {}

        try:
            from quantlab.analysis.reader import AnalysisReader
            reader = AnalysisReader()

            for path in export_paths:
                if path.endswith("strategies.csv"):
                    strategies = reader.parse(path)
                    for strat in strategies:
                        if strat.trades is not None:
                            trades_by_strategy[strat.strategy_name] = strat.trades
                        if strat.equity is not None:
                            equity_by_strategy[strat.strategy_name] = strat.equity
        except Exception:
            # Silently skip if loading fails
            pass

        return trades_by_strategy, equity_by_strategy

    def _serialize_result(self, result: AdvancedAnalysisResult) -> dict[str, Any]:
        """Serialize AdvancedAnalysisResult to dict."""
        return {
            "regime_metrics": [self._serialize_regime(m) for m in result.regime_metrics],
            "pareto": self._serialize_pareto(result.pareto) if result.pareto else None,
            "sensitivity": self._serialize_sensitivity(result.sensitivity) if result.sensitivity else None,
            "robustness": self._serialize_robustness(result.robustness) if result.robustness else None,
            "summary": result.summary,
        }

    def _serialize_regime(self, m: Any) -> dict[str, Any]:
        """Serialize RegimeMetrics to dict."""
        return {
            "regime": m.regime,
            "n_periods": m.n_periods,
            "profit_factor": m.profit_factor,
            "sharpe_ratio": m.sharpe_ratio,
            "max_drawdown": m.max_drawdown,
            "win_rate": m.win_rate,
            "avg_return": m.avg_return,
            "volatility": m.volatility,
            "skewness": m.skewness,
            "kurtosis": m.kurtosis,
            "var_95": m.var_95,
            "cvar_95": m.cvar_95,
        }

    def _serialize_pareto(self, pareto: Any) -> dict[str, Any]:
        """Serialize ParetoResult to dict."""
        if pareto is None:
            return {}
        return {
            "pareto_front": pareto.pareto_front,
            "all_strategies": pareto.all_strategies,
            "metrics_used": pareto.metrics_used,
            "dominance_counts": pareto.dominance_counts,
        }

    def _serialize_sensitivity(self, sens: Any) -> dict[str, Any]:
        """Serialize SensitivityResult to dict."""
        if sens is None:
            return {}
        return {
            "parameter_importance": sens.parameter_importance,
            "metric_drivers": sens.metric_drivers,
            "correlation_matrix": sens.correlation_matrix,
        }

    def _serialize_robustness(self, rob: Any) -> dict[str, Any]:
        """Serialize RobustnessResult to dict."""
        if rob is None:
            return {}
        return {
            "bootstrap_stability": rob.bootstrap_stability,
            "cv_scores": rob.cv_scores,
            "overall_stability": rob.overall_stability,
        }