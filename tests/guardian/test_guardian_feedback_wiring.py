"""Slice B: ``MetaGuardianOrchestrator`` persists guardian metrics.

Spec requirement "Guardian Metrics Persistence":

- ``MetaGuardianOrchestrator.evaluate()`` MUST persist one
  ``GuardianMetricRecord`` per guardian result through
  ``GuardianFeedbackStore``.
- Persistence is opt-in: an orchestrator without a configured store keeps its
  previous side-effect-free behaviour.

Strict TDD: written first — RED until Slice B lands.
"""

from __future__ import annotations

import pytest
from quantlab.guardian.base import BaseGuardian
from quantlab.guardian.models import (
    GuardianResult,
    GuardianStatus,
    GuardianType,
    MetaGuardianConfig,
    PortfolioState,
)
from quantlab.guardian.orchestrator import MetaGuardianOrchestrator
from quantlab.knowledge.guardian_store import GuardianFeedbackStore
from quantlab.knowledge.store import TimeSeriesStore
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.agent_stages import GuardianEvaluationAgentStage


class _StubGuardian(BaseGuardian):
    """Guardian returning a fixed, fully controlled result."""

    def __init__(self, guardian_type: GuardianType, score: float) -> None:
        self._type = guardian_type
        self._score = score

    def check(self) -> GuardianResult:
        return GuardianResult(
            guardian_type=self._type,
            status=GuardianStatus.GREEN,
            score=self._score,
            message="stub",
        )

    def guardian_type(self) -> GuardianType:
        return self._type


class _ConcreteProvider:
    """Minimal stand-in for a real injected data provider."""

    def collect(self, *_args: object, **_kwargs: object) -> dict:
        return {}

    def get_all_strategy_scores(self) -> dict:
        return {}


def _orchestrator(
    store: GuardianFeedbackStore | None,
    campaign_id: str | None = "camp_001",
    **kwargs,
) -> MetaGuardianOrchestrator:
    guardians = [
        _StubGuardian(GuardianType.RISK, 0.90),
        _StubGuardian(GuardianType.MARKET, 0.85),
    ]
    return MetaGuardianOrchestrator(
        config=MetaGuardianConfig(),
        guardians=guardians,
        feedback_store=store,
        campaign_id=campaign_id,
        **kwargs,
    )


@pytest.fixture
def store(tmp_path) -> GuardianFeedbackStore:
    """A feedback store rooted in a temporary knowledge directory."""
    return GuardianFeedbackStore(tmp_path)


class TestOrchestratorPersistsMetrics:
    """``evaluate()`` writes one record per guardian result."""

    def test_evaluate_persists_one_record_per_guardian(
        self, store: GuardianFeedbackStore
    ) -> None:
        _orchestrator(store).evaluate()

        assert len(store.query("camp_001")) == 2

    def test_record_carries_guardian_score(self, store: GuardianFeedbackStore) -> None:
        _orchestrator(store).evaluate()

        by_name = {r.guardian_name: r for r in store.query("camp_001")}
        assert by_name["risk"].score == pytest.approx(0.90)
        assert by_name["market"].score == pytest.approx(0.85)

    def test_record_carries_resulting_portfolio_state(
        self, store: GuardianFeedbackStore
    ) -> None:
        _orchestrator(store).evaluate()

        # Both stubs score >= 0.8, so the first evaluation lands in NORMAL.
        assert {r.portfolio_state for r in store.query("camp_001")} == {
            PortfolioState.NORMAL
        }

    def test_record_source_is_evaluation(self, store: GuardianFeedbackStore) -> None:
        _orchestrator(store).evaluate()

        assert {r.source for r in store.query("camp_001")} == {"evaluation"}

    def test_correlation_id_is_propagated(self, store: GuardianFeedbackStore) -> None:
        _orchestrator(store, correlation_id="phase-5").evaluate()

        assert {r.correlation_id for r in store.query("camp_001")} == {"phase-5"}

    def test_evaluate_appends_across_calls(self, store: GuardianFeedbackStore) -> None:
        orchestrator = _orchestrator(store)
        orchestrator.evaluate()
        orchestrator.evaluate()

        assert len(store.query("camp_001")) == 4

    def test_records_are_readable_through_the_knowledge_api(
        self, tmp_path
    ) -> None:
        _orchestrator(GuardianFeedbackStore(tmp_path)).evaluate()

        rows = TimeSeriesStore(str(tmp_path / "ts.db")).query_guardian_metrics(
            "camp_001", knowledge_root=tmp_path
        )

        assert len(rows) == 2
        assert {r["source"] for r in rows} == {"evaluation"}

    def test_persist_failure_does_not_break_evaluation(self, tmp_path) -> None:
        """Persistence is observability — a broken sink must not fail the loop."""
        store = GuardianFeedbackStore(tmp_path / "not-a-dir" / "x")
        (tmp_path / "not-a-dir").write_text("occupied", encoding="utf-8")
        orchestrator = _orchestrator(store)

        assert orchestrator.evaluate() is not None


class TestPersistenceIsOptIn:
    """Without configuration, evaluate() stays side-effect free."""

    def test_no_store_writes_nothing(self, tmp_path) -> None:
        _orchestrator(None).evaluate()

        assert not (tmp_path / "guardian-feedback").exists()

    def test_no_campaign_id_writes_nothing(self, store: GuardianFeedbackStore) -> None:
        _orchestrator(store, campaign_id=None).evaluate()

        assert store.query("camp_001") == []

    def test_evaluate_still_returns_state(self) -> None:
        assert _orchestrator(None).evaluate() is PortfolioState.NORMAL


class TestGuardianStageFeedbackWiring:
    """The stage passes the configured store through to the orchestrator."""

    @pytest.mark.asyncio
    async def test_stage_persists_when_a_store_is_configured(
        self, store: GuardianFeedbackStore
    ) -> None:
        ctx = PipelineContext(
            config={
                "portfolio_data_provider": _ConcreteProvider(),
                "strategy_performance_provider": _ConcreteProvider(),
                "guardian_feedback_store": store,
                "campaign_id": "camp_777",
            },
            artifacts={"research_config": {}},
        )

        await GuardianEvaluationAgentStage().execute(ctx)

        assert len(store.query("camp_777")) == 6  # one per configured guardian

    @pytest.mark.asyncio
    async def test_stage_without_store_persists_nothing(self, tmp_path) -> None:
        ctx = PipelineContext(
            config={
                "portfolio_data_provider": _ConcreteProvider(),
                "strategy_performance_provider": _ConcreteProvider(),
                "campaign_id": "camp_777",
            },
            artifacts={"research_config": {}},
        )

        await GuardianEvaluationAgentStage().execute(ctx)

        assert not (tmp_path / "guardian-feedback").exists()
