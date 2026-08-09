"""Abstract agent stage classes for the multi-agent research pipeline.

Each stage declares its I/O contract via ``requires``/``provides`` attributes,
matching the specification scenarios in the pipeline-core spec.

Concrete implementations are created in PR 2/3/4/5 and live under
``quantlab.agents``.
"""

from __future__ import annotations

from abc import ABC
from typing import Any

from quantlab.pipeline.base import PipelineContext, Stage

from quantlab.guardian import (
    CapitalGuardian,
    ExecutionGuardian,
    MarketGuardian,
    PortfolioGuardian,
    QualityGuardian,
    RiskGuardian,
)
from quantlab.guardian.models import MetaGuardianConfig, PortfolioState
from quantlab.guardian.orchestrator import MetaGuardianOrchestrator


class ResearchStage(Stage, ABC):
    """Generates ResearchConfig from objectives, market hypotheses, and knowledge lake queries.

    This is the first stage in the multi-agent pipeline. It reads campaign
    objectives from the pipeline config and writes the research configuration,
    hypotheses, iteration config, and gate policies.

    **Provides**: research_config, objectives, hypotheses, iteration_config, gate_policies
    """
    name: str = "research"
    requires: list[str] = []
    provides: list[str] = [
        "research_config",
        "objectives",
        "hypotheses",
        "iteration_config",
        "gate_policies",
    ]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        raise NotImplementedError("ResearchStage must be implemented by a concrete agent subclass")


class BuilderStage(Stage, ABC):
    """Translates DSL ResearchConfig to CFX, validates, dispatches to SQX, monitors execution.

    **Requires**: research_config
    **Provides**: cfx_bytes, campaign_id, sqcli_status, export_paths
    """
    name: str = "builder"
    requires: list[str] = ["research_config"]
    provides: list[str] = [
        "cfx_bytes",
        "campaign_id",
        "sqcli_status",
        "export_paths",
    ]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        raise NotImplementedError("BuilderStage must be implemented by a concrete agent subclass")


class StatisticsStage(Stage, ABC):
    """Computes campaign statistics, aggregations, and Monte Carlo bands.

    **Requires**: export_paths
    **Provides**: statistics, aggregate_stats, monte_carlo_bands, rolling_metrics, regime_alerts
    """
    name: str = "statistics"
    requires: list[str] = ["export_paths"]
    provides: list[str] = [
        "statistics",
        "aggregate_stats",
        "monte_carlo_bands",
        "rolling_metrics",
        "regime_alerts",
    ]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        raise NotImplementedError("StatisticsStage must be implemented by a concrete agent subclass")


class AnalysisStage(Stage, ABC):
    """Parses strategies.csv, computes per-strategy metrics, applies overfit heuristics, and selects strategies.

    **Requires**: export_paths, statistics
    **Provides**: strategy_analysis, selected_strategies, strategy_verdicts, wf_cycles
    """

    name: str = "analysis"
    requires: list[str] = ["export_paths", "statistics"]
    provides: list[str] = [
        "strategy_analysis",
        "selected_strategies",
        "strategy_verdicts",
        "wf_cycles",
    ]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        raise NotImplementedError("AnalysisStage must be implemented by a concrete agent subclass")


class ReviewStage(Stage, ABC):
    """Evaluates campaign results against acceptance criteria, proposes iterations.

    **Requires**: statistics, aggregate_stats, monte_carlo_bands, strategy_analysis
    **Provides**: review_decision, iteration_proposal, wf_degradation, mc_overfit_flag, benchmark_comparison
    """
    name: str = "review"
    requires: list[str] = [
        "statistics",
        "aggregate_stats",
        "monte_carlo_bands",
        "strategy_analysis",
    ]
    provides: list[str] = [
        "review_decision",
        "iteration_proposal",
        "wf_degradation",
        "mc_overfit_flag",
        "benchmark_comparison",
    ]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        raise NotImplementedError("ReviewStage must be implemented by a concrete agent subclass")


class PortfolioStage(Stage, ABC):
    """Runs Portfolio Master, composes portfolio CFX, applies risk limits.

    **Requires**: selected_strategies, review_decision
    **Provides**: portfolio_cfx, portfolio_result, correlation_matrix, risk_allocation, wf_aggregate_stats
    """
    name: str = "portfolio"
    requires: list[str] = [
        "selected_strategies",
        "review_decision",
    ]
    provides: list[str] = [
        "portfolio_cfx",
        "portfolio_result",
        "correlation_matrix",
        "risk_allocation",
        "wf_aggregate_stats",
    ]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        raise NotImplementedError("PortfolioStage must be implemented by a concrete agent subclass")


class DeployStage(Stage, ABC):
    """Packages portfolio CFX for JForex deployment, generates JCloud config.

    **Requires**: portfolio_cfx, gate_decision_HUMAN_APPROVE_PORTFOLIO
    **Provides**: jforex_package, jcloud_config, deployment_result
    """
    name: str = "deploy"
    requires: list[str] = [
        "portfolio_cfx",
        "gate_decision_HUMAN_APPROVE_PORTFOLIO",
    ]
    provides: list[str] = [
        "jforex_package",
        "jcloud_config",
        "deployment_result",
    ]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        raise NotImplementedError("DeployStage must be implemented by a concrete agent subclass")


class MonitorStage(Stage, ABC):
    """Tracks live performance, computes rolling metrics, detects regime changes.

    **Requires**: live_equity, deployment_result
    **Provides**: rolling_metrics, regime_alerts, performance_alerts, gate_decision_HUMAN_REVIEW_PERFORMANCE
    """
    name: str = "monitor"
    requires: list[str] = [
        "live_equity",
        "deployment_result",
    ]
    provides: list[str] = [
        "rolling_metrics",
        "regime_alerts",
        "performance_alerts",
        "gate_decision_HUMAN_REVIEW_PERFORMANCE",
    ]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        raise NotImplementedError("MonitorStage must be implemented by a concrete agent subclass")


class LLMResearchStage(Stage, ABC):
    """LLM-powered research stage using LLMResearchAgent.

    Same requires/provides as ResearchStage but routes to the LLM-powered
    agent instead of the classic keyword-based agent.

    **Provides**: research_config, objectives, hypotheses, iteration_config, gate_policies
    """
    name: str = "research_llm"
    requires: list[str] = []
    provides: list[str] = [
        "research_config",
        "objectives",
        "hypotheses",
        "iteration_config",
        "gate_policies",
    ]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        raise NotImplementedError(
            "LLMResearchStage must be implemented by a concrete agent subclass"
        )


class HypothesisBuilderStage(Stage, ABC):
    """Stage that transforms hypotheses into building blocks + strategies.

    Sits between the research stage (classic or LLM) and the builder stage.
    Uses ``HypothesisBuilder`` to convert qualitative ``HypothesisConfig``
    instances into structured ``BuildingBlock`` and ``Strategy`` objects.

    **Requires**: research_config, hypotheses, objectives
    **Provides**: building_blocks, strategies
    """
    name: str = "hypothesis_builder"
    requires: list[str] = [
        "research_config",
        "hypotheses",
        "objectives",
    ]
    provides: list[str] = [
        "building_blocks",
        "strategies",
    ]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        raise NotImplementedError(
            "HypothesisBuilderStage must be implemented by a concrete agent subclass"
        )


class RefutationStage(Stage, ABC):
    """Stage that annotates hypotheses with falsification scores.

    Sits between hypothesis_builder and builder. Runs RefutationLayer to
    proactively assess hypotheses against regime mismatch, historical
    counter-examples, and LLM adversarial analysis.

    **Requires**: research_config, hypotheses, building_blocks, strategies
    **Provides**: falsation_results (annotations, no filtering)
    """
    name: str = "refutation"
    requires: list[str] = [
        "research_config",
        "hypotheses",
        "building_blocks",
        "strategies",
    ]
    provides: list[str] = [
        "falsation_results",
    ]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        raise NotImplementedError(
            "RefutationStage must be implemented by a concrete agent subclass"
        )


class GuardianEvaluationStage(Stage, ABC):
    """Evaluates all guardians before builder stage.

    Runs MetaGuardianOrchestrator to check market, risk, portfolio,
    capital, quality, and execution conditions before building strategies.

    **Requires**: research_config
    **Provides**: guardian_state, portfolio_state
    """
    name: str = "guardian_evaluate"
    requires: list[str] = [
        "research_config",
    ]
    provides: list[str] = [
        "guardian_state",
        "portfolio_state",
    ]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        raise NotImplementedError("GuardianEvaluationStage must be implemented by a concrete agent subclass")


class GuardianEvaluationAgentStage(GuardianEvaluationStage):
    """Concrete wrapper: runs MetaGuardianOrchestrator against pipeline context.

    Builds guardians from available context artifacts when possible; falls back
    to passive guardians when external collectors/providers are not present so
    the stage never hard-fails the pipeline.
    """

    def __init__(self, **kwargs: Any) -> None:
        self._kwargs = kwargs

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:  # type: ignore[override]
        research_config = ctx.artifacts.get("research_config") or {}
        config = ctx.config or {}

        guardians = self._build_guardians(research_config, config)

        orchestrator = MetaGuardianOrchestrator(
            config=MetaGuardianConfig(),
            guardians=guardians,
        )

        portfolio_state = orchestrator.evaluate()
        guardian_state = {
            "portfolio_state": portfolio_state.value,
            "state_history": [
                {"state": s.value, "timestamp": t}
                for s, t in orchestrator.get_state_history()
            ],
            "strategy_states": orchestrator.get_strategy_states(),
        }

        ctx.artifacts["guardian_state"] = guardian_state
        ctx.artifacts["portfolio_state"] = portfolio_state.value

        return {
            "guardian_state": guardian_state,
            "portfolio_state": portfolio_state.value,
        }

    def _build_guardians(self, research_config: dict[str, Any], pipeline_config: dict[str, Any]) -> list:
        market_context = research_config.get("market_context") if isinstance(research_config, dict) else {}
        capital_constraints = research_config.get("capital_constraints") if isinstance(research_config, dict) else {}

        regime_collector = pipeline_config.get("regime_collector") if isinstance(pipeline_config, dict) else None
        cost_collector = pipeline_config.get("cost_collector") if isinstance(pipeline_config, dict) else None
        portfolio_data_provider = pipeline_config.get("portfolio_data_provider") if isinstance(pipeline_config, dict) else None
        strategy_performance_provider = pipeline_config.get("strategy_performance_provider") if isinstance(pipeline_config, dict) else None

        guardians = [
            MarketGuardian(
                regime_collector=regime_collector,
                cost_collector=cost_collector,
            ),
            RiskGuardian(
                portfolio_data_provider=portfolio_data_provider or _NullDataProvider(),
            ),
            PortfolioGuardian(
                returns_data_provider=portfolio_data_provider or _NullDataProvider(),
            ),
            CapitalGuardian(
                strategy_performance_provider=strategy_performance_provider or _NullDataProvider(),
                risk_guardian=None,
                portfolio_guardian=None,
            ),
            QualityGuardian(
                health_score_system=portfolio_data_provider or _NullDataProvider(),
            ),
            ExecutionGuardian(
                broker_interface=portfolio_data_provider or _NullDataProvider(),
                cost_collector=cost_collector,
            ),
        ]

        return guardians


class _NullDataProvider:
    """Pass-through provider that returns empty/defaults when real data is absent."""

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: {}
