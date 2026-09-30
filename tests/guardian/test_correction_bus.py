"""Slice B: CorrectionBus — unidirectional guardian → builder event fan-out.

Spec requirement "Adaptive Correction Bus":

- ``CorrectionBus.publish()`` MUST reject an unknown ``event_type`` with
  ``CorrectionBusError`` so a malformed correction can never enter fan-out.
- The bus is a single-publisher / multi-subscriber ``asyncio.Queue`` fan-out
  with a one-pipeline-tick delivery guarantee.

Strict TDD: written first — RED until Slice B lands.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import uuid4

import pytest

from quantlab.guardian.correction_bus import (
    CORRECTION_EVENT_TYPES,
    CorrectionBus,
    CorrectionBusError,
    CorrectionEvent,
)
from quantlab.guardian.models import PortfolioState
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.agent_stages import (
    BuilderStage,
    GuardianEvaluationAgentStage,
)


def _event(event_type: str = "state_transition", **overrides) -> CorrectionEvent:
    """Build a valid correction event, overriding individual fields."""
    payload = overrides.pop("payload", {"from": "NORMAL", "to": "DEFENSIVE"})
    return CorrectionEvent(
        event_id=overrides.pop("event_id", uuid4()),
        timestamp=overrides.pop("timestamp", datetime.now()),
        source=overrides.pop("source", "MetaGuardianOrchestrator"),
        event_type=event_type,
        payload=payload,
        correlation_id=overrides.pop("correlation_id", None),
        **overrides,
    )


class TestCorrectionEventModel:
    """CorrectionEvent carries the typed correction envelope."""

    def test_allowed_event_types_are_exactly_the_design_contract(self) -> None:
        assert set(CORRECTION_EVENT_TYPES) == {
            "risk_delta",
            "state_transition",
            "capital_adjustment",
        }

    def test_event_fields_round_trip(self) -> None:
        event = _event()

        assert event.event_type == "state_transition"
        assert event.source == "MetaGuardianOrchestrator"
        assert event.correlation_id is None
        assert event.payload == {"from": "NORMAL", "to": "DEFENSIVE"}

    def test_event_id_is_unique_per_event(self) -> None:
        assert _event().event_id != _event().event_id

    def test_event_is_immutable(self) -> None:
        """A published envelope MUST NOT be mutated by a subscriber."""
        event = _event()

        with pytest.raises(Exception):
            event.event_type = "risk_delta"  # type: ignore[misc]


class TestPublishRejectsInvalidEventType:
    """The bus owns event-type validation; it is the fan-out boundary."""

    def test_publish_rejects_unknown_event_type(self) -> None:
        """GIVEN an event with an unknown event_type
        WHEN it is published
        THEN CorrectionBusError is raised.
        """
        bus = CorrectionBus()

        with pytest.raises(CorrectionBusError):
            bus.publish(_event(event_type="teleport_portfolio"))

    def test_publish_rejects_empty_event_type(self) -> None:
        bus = CorrectionBus()

        with pytest.raises(CorrectionBusError):
            bus.publish(_event(event_type=""))

    def test_rejected_event_names_the_offending_type(self) -> None:
        bus = CorrectionBus()

        with pytest.raises(CorrectionBusError) as exc_info:
            bus.publish(_event(event_type="teleport_portfolio"))

        assert "teleport_portfolio" in str(exc_info.value)

    def test_rejected_event_never_reaches_subscribers(self) -> None:
        """A rejected envelope MUST NOT be delivered to any subscriber."""
        bus = CorrectionBus()
        received: list[CorrectionEvent] = []
        bus.subscribe(received.append)

        with pytest.raises(CorrectionBusError):
            bus.publish(_event(event_type="teleport_portfolio"))

        assert received == []

    @pytest.mark.asyncio
    async def test_every_allowed_event_type_publishes(self) -> None:
        """GIVEN each allowed event type
        WHEN published
        THEN the envelope reaches the subscriber.
        """
        bus = CorrectionBus()
        received: list[CorrectionEvent] = []
        bus.subscribe(received.append)

        for event_type in CORRECTION_EVENT_TYPES:
            bus.publish(_event(event_type=event_type))
        await bus.flush()

        assert [e.event_type for e in received] == list(CORRECTION_EVENT_TYPES)


class TestFanOut:
    """One publisher, N subscribers."""

    @pytest.mark.asyncio
    async def test_publish_delivers_to_every_subscriber(self) -> None:
        bus = CorrectionBus()
        first: list[CorrectionEvent] = []
        second: list[CorrectionEvent] = []
        bus.subscribe(first.append)
        bus.subscribe(second.append)

        bus.publish(_event())
        await bus.flush()

        assert len(first) == 1
        assert len(second) == 1
        assert first[0].event_id == second[0].event_id

    @pytest.mark.asyncio
    async def test_delivery_guarantee_is_one_pipeline_tick(self) -> None:
        """GIVEN a publish inside a running event loop
        WHEN a single pipeline tick elapses
        THEN the event is already delivered.
        """
        bus = CorrectionBus()
        received: list[CorrectionEvent] = []
        bus.subscribe(received.append)

        bus.publish(_event())
        await asyncio.sleep(0)

        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_subscribe_returns_unsubscribe_callable(self) -> None:
        bus = CorrectionBus()
        received: list[CorrectionEvent] = []
        unsubscribe = bus.subscribe(received.append)

        assert callable(unsubscribe)
        unsubscribe()

        bus.publish(_event())
        await bus.flush()

        assert received == []

    @pytest.mark.asyncio
    async def test_unsubscribe_only_detaches_its_own_handler(self) -> None:
        bus = CorrectionBus()
        kept: list[CorrectionEvent] = []
        dropped: list[CorrectionEvent] = []
        bus.subscribe(kept.append)
        bus.subscribe(dropped.append)()
        bus.subscribe(dropped.append)

        bus.publish(_event())
        await bus.flush()

        assert len(kept) == 1
        assert len(dropped) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe_is_idempotent(self) -> None:
        bus = CorrectionBus()
        unsubscribe = bus.subscribe(lambda event: None)

        unsubscribe()
        unsubscribe()

        bus.publish(_event())
        await bus.flush()

    @pytest.mark.asyncio
    async def test_preserves_publication_order(self) -> None:
        bus = CorrectionBus()
        received: list[CorrectionEvent] = []
        bus.subscribe(received.append)

        for index in range(5):
            bus.publish(_event(payload={"index": index}))
        await bus.flush()

        assert [e.payload["index"] for e in received] == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_subscriber_failure_does_not_break_fan_out(self) -> None:
        """A raising subscriber MUST NOT starve the other subscribers."""
        bus = CorrectionBus()
        delivered: list[CorrectionEvent] = []

        def _boom(event: CorrectionEvent) -> None:
            raise RuntimeError("subscriber defect")

        bus.subscribe(_boom)
        bus.subscribe(delivered.append)

        bus.publish(_event())
        await bus.flush()

        assert len(delivered) == 1


class TestBackPressure:
    """A bounded queue surfaces saturation instead of blocking the publisher."""

    @pytest.mark.asyncio
    async def test_full_queue_raises_correction_bus_error(self) -> None:
        """GIVEN a bounded queue with no consumer
        WHEN the queue overflows
        THEN CorrectionBusError is raised rather than blocking the pipeline.
        """
        bus = CorrectionBus(max_queue_size=1)
        bus.publish(_event())  # fills the queue; the drain task cannot run yet

        with pytest.raises(CorrectionBusError):
            bus.publish(_event())

    def test_default_queue_is_unbounded(self) -> None:
        assert CorrectionBus().max_queue_size == 0


class _ConcreteProvider:
    """Minimal stand-in for a real injected data provider."""

    def collect(self, *_args: object, **_kwargs: object) -> dict:
        return {}

    def get_all_strategy_scores(self) -> dict:
        return {}


def _stage_context(bus: CorrectionBus | None = None) -> PipelineContext:
    """Build a context with the providers the guardian stage requires."""
    config: dict = {
        "portfolio_data_provider": _ConcreteProvider(),
        "strategy_performance_provider": _ConcreteProvider(),
    }
    if bus is not None:
        config["correction_bus"] = bus
    return PipelineContext(config=config, artifacts={"research_config": {}})


class TestGuardianStageCorrectionWiring:
    """``GuardianEvaluationStage`` publishes corrections from its evaluation."""

    @pytest.mark.asyncio
    async def test_stage_publishes_state_transition_correction(self) -> None:
        """GIVEN a context with concrete providers
        WHEN the guardian stage executes
        THEN a ``state_transition`` correction is published on the bus.
        """
        bus = CorrectionBus()
        received: list[CorrectionEvent] = []
        bus.subscribe(received.append)

        await GuardianEvaluationAgentStage().execute(_stage_context(bus))

        assert len(received) == 1
        assert received[0].event_type == "state_transition"
        assert received[0].source == "GuardianEvaluationAgentStage"
        assert "to" in received[0].payload

    @pytest.mark.asyncio
    async def test_stage_correction_payload_carries_the_new_state(self) -> None:
        bus = CorrectionBus()
        received: list[CorrectionEvent] = []
        bus.subscribe(received.append)
        ctx = _stage_context(bus)

        outcome = await GuardianEvaluationAgentStage().execute(ctx)

        assert received[0].payload["to"] == outcome["portfolio_state"]
        assert received[0].payload["from"] == PortfolioState.NORMAL.value

    @pytest.mark.asyncio
    async def test_stage_records_correction_events_artifact(self) -> None:
        """The published envelope is auditable from the pipeline artifacts."""
        ctx = _stage_context()

        outcome = await GuardianEvaluationAgentStage().execute(ctx)

        assert "correction_events" in outcome
        assert ctx.artifacts["correction_events"] == outcome["correction_events"]
        assert len(outcome["correction_events"]) == 1

    def test_correction_events_is_a_provided_key(self) -> None:
        assert "correction_events" in GuardianEvaluationAgentStage.provides
        # The canonical flow runs builder before guardian_evaluate, so the key
        # stays optional for the consumer and out of BuilderStage.requires.
        assert "correction_events" not in BuilderStage.requires

    @pytest.mark.asyncio
    async def test_stage_works_without_an_injected_bus(self) -> None:
        """Absence of an injected bus is not a failure — the event is still recorded."""
        ctx = _stage_context()

        outcome = await GuardianEvaluationAgentStage().execute(ctx)

        assert outcome["correction_events"][0]["event_type"] == "state_transition"

