"""BayesianPostAnalysisAgent — Extends AnalysisAgent with Bayesian optimization feedback.

Integrates Bayesian optimization results into the post-analysis phase.
Updates optimizer history with SQX evaluation results, decides whether
to continue optimizing, converge, or advance to backtest comparison.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from quantlab.analysis.engine import AnalysisEngine, AnalysisThresholds
from quantlab.analysis.frame import Frame
from quantlab.analysis.models import SelectionResult, StrategyAnalysis
from quantlab.analysis.reader import AnalysisReader
from quantlab.analysis.selection import SelectionEngine
from quantlab.optimization.history import HistoryBuffer, OptimizationStep
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.agent_stages import AnalysisStage
from quantlab.tools.exceptions import ParseError

logger = logging.getLogger(__name__)


@dataclass
class BayesianFeedbackDecision:
    """Decision from Bayesian feedback loop.

    Attributes:
        action: "continue_optimizing", "converged", "advance_to_backtest", "diverged".
        reason: Human-readable reason for the decision.
        best_parameters: Best parameters found so far.
        best_value: Best objective value.
        n_evaluations: Total evaluations performed.
        convergence_info: Additional convergence details.
    """

    action: str
    reason: str
    best_parameters: dict[str, Any]
    best_value: float
    n_evaluations: int
    convergence_info: dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.convergence_info is None:
            self.convergence_info = {}


class BayesianPostAnalysisAgent(AnalysisStage):
    """Post-analysis agent with Bayesian optimization feedback loop.

    Extends AnalysisAgent to incorporate Bayesian optimizer state.
    After analyzing SQX results, updates the optimizer history and
    makes a decision about continuing optimization.
    """

    def __init__(
        self,
        campaign_id: str,
        knowledge_lake_path: str | None = None,
        min_trades: int = 50,
        extreme_pf: float = 3.0,
        extreme_sharpe: float = 2.0,
        oos_is_threshold: float = 0.7,
        score_weights: dict[str, float] | None = None,
    ) -> None:
        """Initialize Bayesian post-analysis agent.

        Args:
            campaign_id: Campaign identifier for Knowledge Lake.
            knowledge_lake_path: Path to Knowledge Lake root.
            min_trades: Minimum trades to avoid extreme-metric flag.
            extreme_pf: Profit factor above this is extreme with low trades.
            extreme_sharpe: Sharpe above this is extreme with low trades.
            oos_is_threshold: Minimum OOS/IS Sharpe ratio.
            score_weights: Per-metric weights for composite score.
        """
        self.campaign_id = campaign_id
        self.knowledge_lake_path = knowledge_lake_path

        # Delegate to base AnalysisAgent for core analysis
        self._base_agent = AnalysisAgent(
            min_trades=min_trades,
            extreme_pf=extreme_pf,
            extreme_sharpe=extreme_sharpe,
            oos_is_threshold=oos_is_threshold,
            score_weights=score_weights,
        )

        # Initialize history buffer for Bayesian optimizer
        self._history = HistoryBuffer(
            campaign_id=campaign_id,
            knowledge_lake_path=knowledge_lake_path,
        )
        self._history.load()

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Execute post-analysis with Bayesian feedback.

        Args:
            ctx: Pipeline context with export_paths, statistics,
                and bayesian_optimizer_state artifacts.

        Returns:
            Dict with base analysis artifacts plus bayesian_feedback_decision.
        """
        # Run base analysis first
        base_result = await self._base_agent.run(ctx)

        # Extract Bayesian optimizer state if present
        bayesian_state = ctx.artifacts.get("bayesian_optimizer_state", {})
        optimization_config = ctx.artifacts.get("optimization_config", {})
        sqx_evaluation_result = ctx.artifacts.get("sqx_evaluation_result", {})

        # If no Bayesian optimizer state, just return base result
        if not bayesian_state:
            return base_result

        # Extract evaluated parameters from optimization config
        suggested_params = self._extract_params_from_config(optimization_config)

        # Extract objective value from SQX result
        objective_value = self._extract_objective(sqx_evaluation_result)

        # Update optimizer history with the evaluation result
        self._history.add(
            parameters=suggested_params,
            objective_value=objective_value,
            metadata={
                "source": "sqx_evaluation",
                "sqx_result": sqx_evaluation_result,
                "strategy_analysis": base_result.get("strategy_analysis", []),
                "selected_strategies": base_result.get("selected_strategies", []),
            },
        )

        # Persist updated history
        self._history.persist()

        # Make Bayesian feedback decision
        feedback_decision = self._make_feedback_decision(
            suggested_params=suggested_params,
            objective_value=objective_value,
            base_result=base_result,
            bayesian_state=bayesian_state,
        )

        # Add feedback decision to result
        base_result["bayesian_feedback_decision"] = {
            "action": feedback_decision.action,
            "reason": feedback_decision.reason,
            "best_parameters": feedback_decision.best_parameters,
            "best_value": feedback_decision.best_value,
            "n_evaluations": feedback_decision.n_evaluations,
            "convergence_info": feedback_decision.convergence_info,
        }

        # Also publish to context artifacts for pipeline stages
        ctx.artifacts["bayesian_feedback_decision"] = base_result["bayesian_feedback_decision"]
        ctx.artifacts["bayesian_history_n_evaluations"] = len(self._history)

        return base_result

    def _extract_params_from_config(self, optimization_config: dict[str, Any]) -> dict[str, Any]:
        """Extract flat parameter dict from optimization config."""
        params = {}
        task_params = optimization_config.get("task_parameters", {})
        for task_name, task_param_dict in task_params.items():
            params.update(task_param_dict)
        return params

    def _extract_objective(self, sqx_result: dict[str, Any]) -> float:
        """Extract objective value from SQX evaluation result."""
        # Try common keys for fitness/objective value
        for key in ["fitness", "objective_value", "sharpe_ratio", "net_profit", "score"]:
            if key in sqx_result:
                val = sqx_result[key]
                if isinstance(val, (int, float)):
                    return float(val)

        # If nested in metrics
        if "metrics" in sqx_result:
            metrics = sqx_result["metrics"]
            for key in ["sharpe_ratio", "net_profit", "profit_factor", "score"]:
                if key in metrics:
                    val = metrics[key]
                    if isinstance(val, (int, float)):
                        return float(val)

        # Try to compute from strategy analysis if available
        # This would require the base analysis to run first
        return 0.0

    def _make_feedback_decision(
        self,
        suggested_params: dict[str, Any],
        objective_value: float,
        base_result: dict[str, Any],
        bayesian_state: dict[str, Any],
    ) -> BayesianFeedbackDecision:
        """Decide next action based on Bayesian optimization state."""
        n_evaluations = len(self._history)
        best_value, best_params = self._history.get_best()

        # Get convergence info from bayesian state
        converged = bayesian_state.get("converged", False)
        convergence_reason = bayesian_state.get("convergence_reason", "unknown")
        convergence_message = bayesian_state.get("convergence_message", "")

        # Check if we have selected strategies with good metrics
        selected_strategies = base_result.get("selected_strategies", [])
        has_good_strategies = len(selected_strategies) > 0

        # Decision logic
        if converged:
            if convergence_reason == "max_iterations":
                return BayesianFeedbackDecision(
                    action="advance_to_backtest",
                    reason=f"Optimization converged: {convergence_message}. "
                           f"{'Good strategies found' if has_good_strategies else 'No strong strategies'}. "
                           f"Advancing to backtest comparison.",
                    best_parameters=best_params or suggested_params,
                    best_value=best_value or objective_value,
                    n_evaluations=n_evaluations,
                    convergence_info={"reason": convergence_reason, "message": convergence_message},
                )
            elif convergence_reason in ("ei_threshold", "patience_exhausted", "target_reached"):
                return BayesianFeedbackDecision(
                    action="converged",
                    reason=f"Optimization converged: {convergence_message}. "
                           f"Best value: {best_value:.4f} at evaluation {bayesian_state.get('best_iteration', '?')}.",
                    best_parameters=best_params or suggested_params,
                    best_value=best_value or objective_value,
                    n_evaluations=n_evaluations,
                    convergence_info={"reason": convergence_reason, "message": convergence_message},
                )
            elif convergence_reason == "diverged":
                return BayesianFeedbackDecision(
                    action="diverged",
                    reason=f"Optimization diverged: {convergence_message}. "
                           f"Consider adjusting parameter space or surrogate model.",
                    best_parameters=best_params or suggested_params,
                    best_value=best_value or objective_value,
                    n_evaluations=n_evaluations,
                    convergence_info={"reason": convergence_reason, "message": convergence_message},
                )

        # Not converged yet - continue optimizing
        if n_evaluations < 5:
            reason = "Initial exploration phase - continuing optimization"
        elif has_good_strategies:
            reason = f"Found {len(selected_strategies)} promising strategies - continuing to optimize"
        else:
            reason = f"No strong strategies yet (eval {n_evaluations}) - continuing optimization"

        return BayesianFeedbackDecision(
            action="continue_optimizing",
            reason=reason,
            best_parameters=best_params or suggested_params,
            best_value=best_value or objective_value,
            n_evaluations=n_evaluations,
            convergence_info={},
        )


def create_bayesian_post_analysis_agent(
    campaign_id: str,
    knowledge_lake_path: str | None = None,
    **kwargs,
) -> BayesianPostAnalysisAgent:
    """Factory function to create BayesianPostAnalysisAgent."""
    return BayesianPostAnalysisAgent(
        campaign_id=campaign_id,
        knowledge_lake_path=knowledge_lake_path,
        **kwargs,
    )