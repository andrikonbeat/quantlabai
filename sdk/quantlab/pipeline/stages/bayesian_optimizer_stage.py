"""BayesianOptimizerStage — Pipeline integration for Bayesian Optimization.

Stage that sits between ExplorationDecision and ConfigBuilderStage.
Loads optimizer from Knowledge Lake, suggests next parameters via
Expected Improvement, and feeds optimization_config to ConfigBuilderStage.
Handles convergence detection and triggers PostAnalysisAgent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quantlab.exploration.models import ExplorationDecision
    from quantlab.optimization.bayesian_optimizer import BayesianOptimizer, OptimizationResult
    from quantlab.optimization.space import ParameterSpace

from quantlab.pipeline.base import PipelineContext, Stage


@dataclass
class BayesianOptimizerStageConfig:
    """Configuration for BayesianOptimizerStage.

    Attributes:
        campaign_id: Campaign identifier for Knowledge Lake persistence.
        max_iterations: Maximum optimization iterations per stage run.
        n_initial_points: Number of random initial evaluations.
        surrogate_model: Surrogate model type ("gp" or "rf").
        acquisition_function: Acquisition function ("ei", "ucb", "pi", "ts").
        acquisition_params: Additional acquisition function parameters.
        convergence_patience: Patience for no-improvement stopping.
        convergence_ei_threshold: EI threshold for stopping.
        knowledge_lake_path: Path to Knowledge Lake root.
        auto_advance_on_convergence: Whether to auto-advance to next phase on convergence.
        random_state: Random seed for reproducibility.
    """

    campaign_id: str
    max_iterations: int = 50
    n_initial_points: int = 5
    surrogate_model: str = "gp"
    acquisition_function: str = "ei"
    acquisition_params: dict[str, Any] = field(default_factory=dict)
    convergence_patience: int = 20
    convergence_ei_threshold: float = 1e-4
    knowledge_lake_path: str | Path | None = None
    auto_advance_on_convergence: bool = True
    random_state: int | None = None


class BayesianOptimizerStage(Stage):
    """Bayesian Optimization pipeline stage.

    Integrates Bayesian optimization into the QuantLab campaign pipeline.
    Sits between ExplorationDecision and ConfigBuilderStage, suggesting
    optimized parameters for each iteration.

    **Requires**: exploration_decision (or research_config with exploration_decision)
    **Provides**: optimization_config, optimization_result, bayesian_optimizer_state

    Flow:
    1. Load/create BayesianOptimizer from Knowledge Lake
    2. If first run: seed with ExplorationDecision parameters
    3. Suggest next parameters via acquisition function
    4. Convert to ConfigBuilderStage-compatible optimization_config
    5. On convergence: publish optimization_result and advance
    """

    name: str = "bayesian_optimizer"
    requires: list[str] = ["exploration_decision"]
    provides: list[str] = [
        "optimization_config",
        "optimization_result",
        "bayesian_optimizer_state",
    ]

    def __init__(
        self,
        config: BayesianOptimizerStageConfig | None = None,
        optimizer: Any = None,  # Injected for testing
        objective_func: Any = None,  # Injected for testing
    ) -> None:
        """Initialize BayesianOptimizerStage.

        Args:
            config: Stage configuration.
            optimizer: Pre-configured BayesianOptimizer (for testing).
            objective_func: Objective function (for testing; normally provided by pipeline).
        """
        self.config = config or BayesianOptimizerStageConfig(campaign_id="default")
        self._optimizer = optimizer
        self._objective_func = objective_func
        self._parameter_space: ParameterSpace | None = None

    def _get_parameter_space(self, exploration_decision: ExplorationDecision) -> ParameterSpace:
        """Get or create parameter space from exploration decision."""
        if self._parameter_space is None:
            from quantlab.optimization.space import ParameterSpace
            self._parameter_space = ParameterSpace.from_exploration_decision(exploration_decision)
        return self._parameter_space

    def _create_optimizer(self, exploration_decision: ExplorationDecision) -> BayesianOptimizer:
        """Create or load BayesianOptimizer."""
        if self._optimizer is not None:
            return self._optimizer

        from quantlab.optimization.bayesian_optimizer import BayesianOptimizer, create_bayesian_optimizer
        from quantlab.optimization.convergence import create_default_monitor

        space = self._get_parameter_space(exploration_decision)

        convergence_monitor = create_default_monitor(
            max_iterations=self.config.max_iterations,
            ei_threshold=self.config.convergence_ei_threshold,
            patience=self.config.convergence_patience,
        )

        optimizer = create_bayesian_optimizer(
            parameter_space=space,
            campaign_id=self.config.campaign_id,
            knowledge_lake_path=self.config.knowledge_lake_path,
            surrogate_model=self.config.surrogate_model,
            acquisition_function=self.config.acquisition_function,
            max_iterations=self.config.max_iterations,
            n_initial_points=self.config.n_initial_points,
            random_state=self.config.random_state,
        )
        # Replace convergence monitor with our configured one
        optimizer.convergence = convergence_monitor

        return optimizer

    def _build_optimization_config(
        self,
        suggested_params: dict[str, Any],
        exploration_decision: ExplorationDecision,
    ) -> dict[str, Any]:
        """Convert suggested parameters to ConfigBuilderStage optimization_config.

        Maps Bayesian optimizer parameters to the format expected by
        ConfigBuilderStage for CFX generation.
        """
        # Start with base config from exploration decision
        optimization_config = {
            "campaign": self.config.campaign_id,
            "market": exploration_decision.market,
            "timeframe": exploration_decision.timeframe,
            "capital_usd": exploration_decision.capital_usd,
            "leverage": exploration_decision.leverage,
        }

        # Map Bayesian optimizer parameters to SQX task parameters
        param_mapping = {
            "risk_per_trade_pct": ("Build", "risk_per_trade_pct"),
            "max_drawdown_pct": ("Build", "max_drawdown_pct"),
            "max_concurrent_positions": ("Build", "max_concurrent_positions"),
            "stop_loss_pips": ("Build", "stop_loss_pips"),
            "take_profit_pips": ("Build", "take_profit_pips"),
            "trailing_stop_pips": ("Build", "trailing_stop_pips"),
            "position_sizing_method": ("Build", "position_sizing_method"),
            "fixed_fractional_pct": ("Build", "fixed_fractional_pct"),
            "indicator_fast_period": ("Build", "indicator_fast_period"),
            "indicator_slow_period": ("Build", "indicator_slow_period"),
            "signal_threshold": ("Build", "signal_threshold"),
            "trading_hours_start": ("Build", "trading_hours_start"),
            "trading_hours_end": ("Build", "trading_hours_end"),
        }

        task_params: dict[str, dict[str, Any]] = {}
        for opt_param, (task_name, sqx_param) in param_mapping.items():
            if opt_param in suggested_params:
                if task_name not in task_params:
                    task_params[task_name] = {}
                task_params[task_name][sqx_param] = suggested_params[opt_param]

        optimization_config["task_parameters"] = task_params

        # Add metadata
        optimization_config["bayesian_optimizer"] = {
            "iteration": len(self._optimizer.history) if self._optimizer else 0,
            "acquisition_function": self.config.acquisition_function,
            "surrogate_model": self.config.surrogate_model,
        }

        return optimization_config

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Execute Bayesian optimization step.

        Args:
            ctx: Pipeline context with exploration_decision artifact.

        Returns:
            Dict with optimization_config, optimization_result (if converged),
            and bayesian_optimizer_state.
        """
        exploration_decision: ExplorationDecision = ctx.artifacts["exploration_decision"]

        # Create/load optimizer
        optimizer = self._create_optimizer(exploration_decision)
        self._optimizer = optimizer  # Cache for config building

        # Load existing history if available
        if len(optimizer.history) == 0:
            optimizer.load_history(self.config.campaign_id)

        # Determine objective function
        # In production, this would be provided by the pipeline orchestrator
        # For now, we use a placeholder that returns the SQX fitness value
        if self._objective_func is None:
            # This will be replaced by the pipeline with actual SQX evaluation
            self._objective_func = lambda params: 0.0

        # Run one optimization iteration (or until convergence if configured)
        if len(optimizer.history) == 0:
            # First run - seed and run initial evaluations
            result = optimizer.optimize(
                objective_func=self._objective_func,
                n_iterations=self.config.n_initial_points,
            )
        else:
            # Continue optimization - run one step or until convergence
            if self.config.auto_advance_on_convergence:
                result = optimizer.optimize(
                    objective_func=self._objective_func,
                    n_iterations=1,  # One step per stage execution
                )
            else:
                # Just get next suggestion
                next_params = optimizer.get_next_suggestion()
                if next_params is None:
                    # Should not happen if history exists
                    next_params = optimizer.space.defaults()

                result = optimizer.optimize(
                    objective_func=self._objective_func,
                    n_iterations=1,
                )

        # Build optimization config for ConfigBuilderStage
        suggested_params = result.best_parameters
        optimization_config = self._build_optimization_config(suggested_params, exploration_decision)

        # Prepare optimizer state for persistence
        optimizer_state = {
            "campaign_id": self.config.campaign_id,
            "optimizer_id": optimizer._optimizer_id,
            "n_evaluations": len(optimizer.history),
            "best_value": result.best_value,
            "best_parameters": result.best_parameters,
            "converged": result.convergence_state.converged,
            "convergence_reason": result.convergence_state.reason.value if result.convergence_state.reason else None,
            "convergence_message": result.convergence_state.message,
            "history_path": str(optimizer.history.history_file),
        }

        # Publish artifacts
        ctx.artifacts["optimization_config"] = optimization_config
        ctx.artifacts["bayesian_optimizer_state"] = optimizer_state

        if result.convergence_state.converged:
            ctx.artifacts["optimization_result"] = result.to_dict()
            # Signal convergence to pipeline
            ctx.artifacts["bayesian_converged"] = True
            ctx.artifacts["bayesian_convergence_reason"] = result.convergence_state.reason.value
        else:
            ctx.artifacts["bayesian_converged"] = False

        return {
            "optimization_config": optimization_config,
            "optimization_result": result.to_dict() if result.convergence_state.converged else None,
            "bayesian_optimizer_state": optimizer_state,
        }


class BayesianOptimizerFeedbackStage(Stage):
    """Feedback stage that updates Bayesian optimizer with SQX results.

    Runs after SQX evaluation to feed back the actual objective value
    and update the optimizer history. Decides whether to continue
    optimizing or advance to the next phase.

    **Requires**: optimization_config, sqx_evaluation_result
    **Provides**: bayesian_feedback_decision, updated_optimizer_state
    """

    name: str = "bayesian_feedback"
    requires: list[str] = ["optimization_config", "sqx_evaluation_result"]
    provides: list[str] = ["bayesian_feedback_decision", "updated_optimizer_state"]

    def __init__(
        self,
        campaign_id: str,
        knowledge_lake_path: str | Path | None = None,
    ) -> None:
        """Initialize feedback stage.

        Args:
            campaign_id: Campaign identifier.
            knowledge_lake_path: Path to Knowledge Lake.
        """
        self.campaign_id = campaign_id
        self.knowledge_lake_path = Path(knowledge_lake_path) if knowledge_lake_path else None

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Process SQX evaluation result and update optimizer.

        Args:
            ctx: Pipeline context with optimization_config and sqx_evaluation_result.

        Returns:
            Dict with feedback decision and updated optimizer state.
        """
        optimization_config: dict[str, Any] = ctx.artifacts["optimization_config"]
        sqx_result: dict[str, Any] = ctx.artifacts["sqx_evaluation_result"]

        # Extract the parameters that were evaluated
        task_params = optimization_config.get("task_parameters", {})
        # Flatten task parameters back to optimizer parameter space
        suggested_params = {}
        for task_name, params in task_params.items():
            suggested_params.update(params)

        # Extract objective value from SQX result
        # SQX result format depends on the evaluation stage
        objective_value = self._extract_objective(sqx_result)

        # Load optimizer history
        from quantlab.optimization.history import HistoryBuffer
        history = HistoryBuffer(
            campaign_id=self.campaign_id,
            knowledge_lake_path=self.knowledge_lake_path,
        )
        history.load()

        # Add the evaluated point to history
        history.add(
            parameters=suggested_params,
            objective_value=objective_value,
            metadata={
                "source": "sqx_evaluation",
                "sqx_result": sqx_result,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

        # Persist updated history
        history.persist()

        # Determine feedback decision
        best_value, _ = history.get_best()
        decision = {
            "continue_optimizing": True,
            "reason": "continue",
            "best_value": best_value,
            "current_value": objective_value,
            "n_evaluations": len(history),
        }

        # Check if we should stop (convergence would be checked in optimizer stage)
        # This stage just records the result

        updated_state = {
            "campaign_id": self.campaign_id,
            "n_evaluations": len(history),
            "best_value": best_value,
            "last_evaluation": {
                "parameters": suggested_params,
                "value": objective_value,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }

        ctx.artifacts["bayesian_feedback_decision"] = decision
        ctx.artifacts["updated_optimizer_state"] = updated_state

        return {
            "bayesian_feedback_decision": decision,
            "updated_optimizer_state": updated_state,
        }

    def _extract_objective(self, sqx_result: dict[str, Any]) -> float:
        """Extract objective value from SQX evaluation result.

        Args:
            sqx_result: Result from SQX evaluation stage.

        Returns:
            Objective value (higher is better).
        """
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

        # Default: return 0 if no recognizable objective
        return 0.0