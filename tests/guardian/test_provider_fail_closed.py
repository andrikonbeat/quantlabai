"""Slice A: guardians hard-fail when a data provider is missing.

Spec requirement "Hard-Fail on Missing Providers (Issue 1)":

- ``MetaGuardianOrchestrator`` MUST reject guardians whose provider is
  ``None`` by raising ``GuardianProviderError`` at construction time.
- The legacy ``_NullDataProvider`` pass-through MUST NOT be reintroduced;
  ``GuardianEvaluationAgentStage`` builds concrete guardians from
  ``ctx.config`` and fails closed when a provider is absent.

Strict TDD: written first — RED until Slice A lands.
"""

from __future__ import annotations

import pytest
from quantlab.guardian import (
    CapitalGuardian,
    ExecutionGuardian,
    PortfolioGuardian,
    QualityGuardian,
    RiskGuardian,
)
from quantlab.guardian.models import MetaGuardianConfig
from quantlab.guardian.orchestrator import MetaGuardianOrchestrator
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.errors import GuardianProviderError
from quantlab.pipeline.stages import agent_stages
from quantlab.pipeline.stages.agent_stages import GuardianEvaluationAgentStage


class _ConcreteProvider:
    """Minimal stand-in for a real injected data provider."""

    def collect(self, *_args: object, **_kwargs: object) -> dict:
        return {}

    def get_all_strategy_scores(self) -> dict:
        return {}


def _provider() -> _ConcreteProvider:
    return _ConcreteProvider()


class TestOrchestratorRejectsNoneProviders:
    """The constructor is the fail-closed boundary for guardian providers."""

    def test_risk_guardian_none_provider_raises(self) -> None:
        """GIVEN a RiskGuardian with a None provider
        WHEN the orchestrator is constructed
        THEN GuardianProviderError is raised and no orchestrator is created.
        """
        guardian = RiskGuardian(portfolio_data_provider=None)

        with pytest.raises(GuardianProviderError):
            MetaGuardianOrchestrator(MetaGuardianConfig(), [guardian])

    def test_portfolio_guardian_none_provider_raises(self) -> None:
        guardian = PortfolioGuardian(returns_data_provider=None)

        with pytest.raises(GuardianProviderError):
            MetaGuardianOrchestrator(MetaGuardianConfig(), [guardian])

    def test_capital_guardian_none_provider_raises(self) -> None:
        guardian = CapitalGuardian(strategy_performance_provider=None)

        with pytest.raises(GuardianProviderError):
            MetaGuardianOrchestrator(MetaGuardianConfig(), [guardian])

    def test_quality_guardian_none_provider_raises(self) -> None:
        guardian = QualityGuardian(health_score_system=None)

        with pytest.raises(GuardianProviderError):
            MetaGuardianOrchestrator(MetaGuardianConfig(), [guardian])

    def test_execution_guardian_none_provider_raises(self) -> None:
        guardian = ExecutionGuardian(broker_interface=None)

        with pytest.raises(GuardianProviderError):
            MetaGuardianOrchestrator(MetaGuardianConfig(), [guardian])

    def test_all_concrete_providers_succeed(self) -> None:
        """GIVEN concrete providers for all 5 guardian modules
        WHEN the orchestrator is constructed
        THEN initialisation completes.
        """
        guardians = [
            RiskGuardian(portfolio_data_provider=_provider()),
            PortfolioGuardian(returns_data_provider=_provider()),
            CapitalGuardian(strategy_performance_provider=_provider()),
            QualityGuardian(health_score_system=_provider()),
            ExecutionGuardian(broker_interface=_provider()),
        ]

        orchestrator = MetaGuardianOrchestrator(MetaGuardianConfig(), guardians)

        assert orchestrator.guardians == guardians

    def test_no_guardians_is_still_valid(self) -> None:
        """An empty guardian list is a legitimate state (MCP bridge bootstrap)."""
        orchestrator = MetaGuardianOrchestrator(MetaGuardianConfig(), [])

        assert orchestrator.guardians == []

    def test_error_names_the_offending_guardian(self) -> None:
        guardian = RiskGuardian(portfolio_data_provider=None)

        with pytest.raises(GuardianProviderError) as exc_info:
            MetaGuardianOrchestrator(MetaGuardianConfig(), [guardian])

        assert "RiskGuardian" in str(exc_info.value)


class TestGuardianStageProviderContract:
    """``GuardianEvaluationAgentStage`` passes providers through from config."""

    @pytest.mark.asyncio
    async def test_stage_without_providers_raises(self) -> None:
        """GIVEN a context with no guardian providers in config
        WHEN the stage executes
        THEN it raises GuardianProviderError instead of using a null provider.
        """
        ctx = PipelineContext(config={}, artifacts={"research_config": {}})

        with pytest.raises(GuardianProviderError):
            await GuardianEvaluationAgentStage().execute(ctx)

    @pytest.mark.asyncio
    async def test_stage_with_concrete_providers_produces_state(self) -> None:
        """GIVEN concrete providers in ctx.config
        WHEN the stage executes
        THEN guardian_state and portfolio_state are written.
        """
        ctx = PipelineContext(
            config={
                "portfolio_data_provider": _provider(),
                "strategy_performance_provider": _provider(),
            },
            artifacts={"research_config": {}},
        )

        outcome = await GuardianEvaluationAgentStage().execute(ctx)

        assert "guardian_state" in outcome
        assert "portfolio_state" in outcome
        assert ctx.artifacts["portfolio_state"] == outcome["portfolio_state"]

    def test_null_data_provider_class_is_removed(self) -> None:
        """The legacy pass-through provider no longer exists."""
        assert not hasattr(agent_stages, "_NullDataProvider")
