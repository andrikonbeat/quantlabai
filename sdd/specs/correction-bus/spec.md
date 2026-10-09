# Delta for correction-bus

## ADDED Requirements

### Requirement: CorrectionBus Event Channel

The system MUST provide a lightweight in-process `CorrectionBus` that publishes `CorrectionEvent` objects from `GuardianEvaluationStage` and delivers them to `BuilderStage` before CFX generation. The bus SHALL be unidirectional: guardian → builder. No cyclic dependencies are permitted. Events MUST be typed, serializable, and observable.

#### Scenario: Risk delta reaches builder

- GIVEN `MetaGuardianOrchestrator` evaluates and produces a risk delta
- WHEN `GuardianEvaluationStage` publishes a `CorrectionEvent` on the bus
- THEN `BuilderStage` receives the event
- AND adjusts CFX `risk_money_mgmt` parameters before dispatch

#### Scenario: State transition blocks builder

- GIVEN portfolio transitions to `QUARANTINE`
- WHEN `GuardianEvaluationStage` publishes a state-transition event
- THEN `BuilderStage` blocks dispatch
- AND the pipeline halts until human override

#### Scenario: Bus decouples stages

- GIVEN `GuardianEvaluationStage` and `BuilderStage` are in the same pipeline
- WHEN an event is published
- THEN the stages remain decoupled via the bus interface
- AND no direct import cycles exist between guardian and builder modules

## ADDED Requirements

### Requirement: CorrectionEvent Schema

`CorrectionEvent` MUST be a typed dataclass with fields: `event_id` (UUID), `timestamp` (datetime UTC), `source` (str), `event_type` (Literal["risk_delta", "state_transition", "capital_adjustment"]), `payload` (dict[str, Any]), and `correlation_id` (str | None). The system SHALL validate events at publish time; invalid events MUST raise `CorrectionBusError`.

#### Scenario: Valid event accepted

- GIVEN a well-formed `CorrectionEvent`
- WHEN `CorrectionBus.publish(event)` is called
- THEN the event is queued
- AND subscribers receive it within one pipeline tick

#### Scenario: Invalid event rejected

- GIVEN a `CorrectionEvent` with an unknown `event_type`
- WHEN `CorrectionBus.publish(event)` is called
- THEN `CorrectionBusError` is raised
- AND no subscribers receive the event
