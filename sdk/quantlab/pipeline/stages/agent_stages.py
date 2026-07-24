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


class ReviewStage(Stage, ABC):
    """Evaluates campaign results against acceptance criteria, proposes iterations.

    **Requires**: statistics, aggregate_stats, monte_carlo_bands
    **Provides**: review_decision, iteration_proposal, wf_degradation, mc_overfit_flag, benchmark_comparison
    """
    name: str = "review"
    requires: list[str] = [
        "statistics",
        "aggregate_stats",
        "monte_carlo_bands",
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
