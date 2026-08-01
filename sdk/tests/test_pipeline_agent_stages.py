"""Unit tests for all 8 new agent stages — task 1.14.

Verifies that each of the 8 new abstract stages declares the correct
``requires`` and ``provides`` attributes matching the pipeline-core spec.
"""

import pytest

from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.agent_stages import (
    AnalysisStage,
    BuilderStage,
    DeployStage,
    MonitorStage,
    PortfolioStage,
    ResearchStage,
    ReviewStage,
    StatisticsStage,
)


class TestResearchStage:
    """ResearchStage I/O contract per spec scenario."""

    def test_requires_empty(self) -> None:
        """GIVEN ResearchStage
        WHEN inspecting requires
        THEN it is empty (no dependencies).
        """
        stage = ResearchStage()
        assert stage.requires == []

    def test_provides_correct(self) -> None:
        """GIVEN ResearchStage
        WHEN inspecting provides
        THEN it provides the 5 spec-defined keys.
        """
        stage = ResearchStage()
        expected = [
            "research_config",
            "objectives",
            "hypotheses",
            "iteration_config",
            "gate_policies",
        ]
        assert stage.provides == expected

    def test_name(self) -> None:
        assert ResearchStage.name == "research"


class TestBuilderStage:
    """BuilderStage I/O contract per spec scenario."""

    def test_requires(self) -> None:
        stage = BuilderStage()
        assert stage.requires == ["research_config"]

    def test_provides(self) -> None:
        stage = BuilderStage()
        expected = ["cfx_bytes", "campaign_id", "sqcli_status", "export_paths"]
        assert stage.provides == expected

    def test_name(self) -> None:
        assert BuilderStage.name == "builder"


class TestStatisticsStage:
    """StatisticsStage I/O contract per spec scenario."""

    def test_requires(self) -> None:
        stage = StatisticsStage()
        assert stage.requires == ["export_paths"]

    def test_provides(self) -> None:
        stage = StatisticsStage()
        expected = [
            "statistics",
            "aggregate_stats",
            "monte_carlo_bands",
            "rolling_metrics",
            "regime_alerts",
        ]
        assert stage.provides == expected

    def test_name(self) -> None:
        assert StatisticsStage.name == "statistics"


class TestAnalysisStage:
    """AnalysisStage I/O contract per spec scenario."""

    def test_requires(self) -> None:
        stage = AnalysisStage()
        expected = ["export_paths", "statistics"]
        assert stage.requires == expected

    def test_provides(self) -> None:
        stage = AnalysisStage()
        expected = [
            "strategy_analysis",
            "selected_strategies",
            "strategy_verdicts",
            "wf_cycles",
        ]
        assert stage.provides == expected

    def test_name(self) -> None:
        assert AnalysisStage.name == "analysis"


class TestReviewStage:
    """ReviewStage I/O contract per spec scenario."""

    def test_requires(self) -> None:
        stage = ReviewStage()
        expected = ["statistics", "aggregate_stats", "monte_carlo_bands", "strategy_analysis"]
        assert stage.requires == expected

    def test_provides(self) -> None:
        stage = ReviewStage()
        expected = [
            "review_decision",
            "iteration_proposal",
            "wf_degradation",
            "mc_overfit_flag",
            "benchmark_comparison",
        ]
        assert stage.provides == expected

    def test_name(self) -> None:
        assert ReviewStage.name == "review"


class TestPortfolioStage:
    """PortfolioStage I/O contract per spec scenario."""

    def test_requires(self) -> None:
        stage = PortfolioStage()
        expected = ["selected_strategies", "review_decision"]
        assert stage.requires == expected

    def test_provides(self) -> None:
        stage = PortfolioStage()
        expected = [
            "portfolio_cfx",
            "portfolio_result",
            "correlation_matrix",
            "risk_allocation",
            "wf_aggregate_stats",
        ]
        assert stage.provides == expected

    def test_name(self) -> None:
        assert PortfolioStage.name == "portfolio"


class TestDeployStage:
    """DeployStage I/O contract per spec scenario."""

    def test_requires(self) -> None:
        stage = DeployStage()
        expected = ["portfolio_cfx", "gate_decision_HUMAN_APPROVE_PORTFOLIO"]
        assert stage.requires == expected

    def test_provides(self) -> None:
        stage = DeployStage()
        expected = ["jforex_package", "jcloud_config", "deployment_result"]
        assert stage.provides == expected

    def test_name(self) -> None:
        assert DeployStage.name == "deploy"


class TestMonitorStage:
    """MonitorStage I/O contract per spec scenario."""

    def test_requires(self) -> None:
        stage = MonitorStage()
        expected = ["live_equity", "deployment_result"]
        assert stage.requires == expected

    def test_provides(self) -> None:
        stage = MonitorStage()
        expected = [
            "rolling_metrics",
            "regime_alerts",
            "performance_alerts",
            "gate_decision_HUMAN_REVIEW_PERFORMANCE",
        ]
        assert stage.provides == expected

    def test_name(self) -> None:
        assert MonitorStage.name == "monitor"


class TestFullChainContract:
    """Verify the complete agent-stage chain satisfies contracts.
    
    Some keys come from external sources (config, gates, environment):
    - ``selected_strategies`` → provided by AnalysisStage
    - ``live_equity`` → provided by external data feed
    - ``gate_decision_*`` → provided by GateInterceptorStage
    - ``deployment_result`` → provided by DeployStage itself
    """

    def test_chain_contract_with_external_keys(self) -> None:
        """GIVEN all 8 agent stages in order plus external key sources
        WHEN checking requires against cumulative provides + external keys
        THEN all requirements are satisfied.
        """
        stages = [
            ResearchStage(),
            BuilderStage(),
            StatisticsStage(),
            AnalysisStage(),
            ReviewStage(),
        ]

        # External keys that would come from config, gates, or environment
        external_keys = {
            "live_equity",             # from external data feed
            "gate_decision_HUMAN_APPROVE_PORTFOLIO",  # from gate
            "gate_decision_HUMAN_REVIEW_PERFORMANCE", # from gate
            "deployment_result",       # from DeployStage
        }

        provided: set[str] = set(external_keys)
        violations = []

        for stage in stages:
            for req in stage.requires:
                if req not in provided:
                    violations.append(
                        f"Stage '{stage.name}' requires '{req}' "
                        f"which is not provided by any prior stage or external source"
                    )
            provided.update(stage.provides)

        # Now check the later stages that depend on both agent and external keys
        portfolio = PortfolioStage()
        for req in portfolio.requires:
            if req not in provided:
                violations.append(
                    f"PortfolioStage requires '{req}' which is not available"
                )
        provided.update(portfolio.provides)

        deploy = DeployStage()
        for req in deploy.requires:
            if req not in provided:
                violations.append(
                    f"DeployStage requires '{req}' which is not available"
                )
        provided.update(deploy.provides)

        monitor = MonitorStage()
        for req in monitor.requires:
            if req not in provided:
                violations.append(
                    f"MonitorStage requires '{req}' which is not available"
                )

        assert not violations, "\n".join(violations)
