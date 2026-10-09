# Delta for meta-guardian

## ADDED Requirements

### Requirement: Hard-Fail on Missing Providers (Issue 1)

`MetaGuardianOrchestrator` MUST require concrete data providers for all guardian modules at construction time. If any provider is `None` or absent, the constructor MUST raise `GuardianProviderError`. The system SHALL NOT fall back to `_NullDataProvider` or any silent pass-through. This requirement applies to `RiskGuardian`, `PortfolioGuardian`, `CapitalGuardian`, `QualityGuardian`, and `ExecutionGuardian`.

#### Scenario: Missing provider fails closed

- GIVEN a `MetaGuardianOrchestrator` instantiation with `RiskGuardian` provider set to `None`
- WHEN the constructor runs
- THEN `GuardianProviderError` is raised
- AND no guardian instance is created

#### Scenario: All providers present succeeds

- GIVEN concrete providers for all 5 guardian modules
- WHEN `MetaGuardianOrchestrator` is constructed
- THEN initialization completes
- AND each guardian receives its provider

#### Scenario: _NullDataProvider removed

- GIVEN the legacy `_NullDataProvider` class
- WHEN the module is imported
- THEN it is no longer available or raises `DeprecationError`
- AND all call sites in `_build_guardians` use concrete providers

## MODIFIED Requirements

### Requirement: State Machine Enforcement (Issue 3)

The `PortfolioState` state machine MUST enforce pipeline gating after `GuardianEvaluationStage`. `BuilderStage` MUST block when `portfolio_state` is `QUARANTINE` or `DEFENSIVE` unless an explicit human override is granted via the existing `HUMAN_APPROVE_DEPLOY` gate. The orchestrator MUST NOT silently proceed to builder execution in blocked states.

#### Scenario: QUARANTINE blocks builder

- GIVEN `portfolio_state` is `QUARANTINE`
- WHEN `GuardianEvaluationStage` completes
- THEN `BuilderStage` does not execute
- AND the pipeline waits for `HUMAN_APPROVE_DEPLOY`

#### Scenario: DEFENSIVE blocks builder

- GIVEN `portfolio_state` is `DEFENSIVE`
- WHEN the pipeline reaches `BuilderStage`
- THEN dispatch is blocked
- AND a CorrectionBus event is emitted

#### Scenario: NORMAL permits builder

- GIVEN `portfolio_state` is `NORMAL`
- WHEN `GuardianEvaluationStage` completes
- THEN `BuilderStage` executes normally

#### Scenario: Human override unblocks

- GIVEN `portfolio_state` is `QUARANTINE`
- WHEN human approves via `HUMAN_APPROVE_DEPLOY`
- THEN `BuilderStage` proceeds
- AND the override is recorded in the audit log

(Previously: state machine had no enforcement hooks; `_execute_state_transition` only logged and called hooks)

## ADDED Requirements

### Requirement: Guardian Metrics Persistence (Issue 6)

`MetaGuardianOrchestrator` MUST persist guardian evaluation metrics per campaign run: timestamped scores per guardian, portfolio state transitions, and risk metrics. The system SHALL write to `knowledge/guardian-feedback/{campaign_id}/metrics.jsonl` and expose a read API via `GuardianMetricsStore`.

#### Scenario: Metrics written per evaluation

- GIVEN a campaign run with id `camp_001`
- WHEN `MetaGuardianOrchestrator.evaluate()` completes
- THEN `knowledge/guardian-feedback/camp_001/metrics.jsonl` contains one JSON line per guardian score
- AND each line includes `timestamp`, `guardian_name`, `score`, `portfolio_state`, and `risk_metrics`

#### Scenario: Read API returns history

- GIVEN persisted metrics for campaigns `camp_001` and `camp_002`
- WHEN `GuardianMetricsStore.query(campaign_id="camp_001")` is called
- THEN a list of `GuardianMetricRecord` objects is returned
- AND records are ordered by timestamp ascending
