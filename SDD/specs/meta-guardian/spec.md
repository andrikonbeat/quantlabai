# MetaGuardian Specification

## Purpose

The MetaGuardian is the governance layer that supervises all strategies, risk, and market conditions. It decides what can operate, when, and with how much capital.

## Requirements

### Requirement: Guardian Modules

The system MUST provide 6 independent guardian modules:
1. **MarketGuardian** — monitors regime, volatility, liquidity, session
2. **RiskGuardian** — monitors drawdown, Sharpe, exposure, Kelly
3. **PortfolioGuardian** — scores portfolio health, correlation, diversification
4. **CapitalGuardian** — dynamic capital allocation across families
5. **QualityGuardian** — dynamic Health Score per strategy (reuses Change 1)
6. **ExecutionGuardian** — broker health, latency, slippage, connection

#### Scenario: All guardians healthy
- GIVEN all guardians return green status
- WHEN `MetaGuardianOrchestrator.evaluate()` is called
- THEN portfolio state is NORMAL

#### Scenario: Risk guardian triggers alert
- GIVEN drawdown > 15% and Sharpe < 0.5
- WHEN `RiskGuardian.check()` returns alert
- THEN portfolio transitions toward DEFENSIVE state

### Requirement: State Machine

The MetaGuardian MUST implement a state machine with these states and transitions:

| State | Description | Trigger |
|-------|-------------|---------|
| NORMAL | All systems green | Default state |
| VIGILANCE | One or more warnings | Guardian score drops below threshold |
| DEFENSIVE | Active risk reduction | Drawdown > 10% or Sharpe < 1.0 |
| QUARANTINE | Strategies paused | Drawdown > 20% or critical risk |
| RECOVERY | Gradual re-entry | Drawdown recovering, Sharpe improving |

#### Scenario: NORMAL → VIGILANCE
- GIVEN portfolio in NORMAL state
- WHEN one guardian score drops below warning threshold
- THEN state transitions to VIGILANCE

#### Scenario: VIGILANCE → DEFENSIVE
- GIVEN portfolio in VIGILANCE state
- WHEN drawdown exceeds 10%
- THEN state transitions to DEFENSIVE

#### Scenario: DEFENSIVE → NORMAL (recovery)
- GIVEN portfolio in DEFENSIVE state
- WHEN drawdown drops below 5% for 5 consecutive checks
- THEN state transitions to NORMAL (with hysteresis)

### Requirement: Per-Strategy State Machine

Each strategy has its own state: ACTIVE → MONITORING → DEGRADING → REPLACEMENT_PENDING → RETIRED

#### Scenario: Strategy degrading
- GIVEN a strategy in ACTIVE state
- WHEN health score drops below threshold for 3 consecutive checks
- THEN state transitions to DEGRADING

#### Scenario: Strategy retirement
- GIVEN a strategy in DEGRADING state
- WHEN no replacement candidate found after 5 checks
- THEN state transitions to RETIRED

### Requirement: Action Hooks

State transitions MUST trigger configurable action hooks.

#### Scenario: DEFENSIVE hook
- GIVEN transition to DEFENSIVE state
- WHEN hook fires
- THEN reduces capital allocation by 50% for all strategies

#### Scenario: QUARANTINE hook
- GIVEN transition to QUARANTINE state
- WHEN hook fires
- THEN pauses all strategies and flags for human review

### Requirement: Configuration

Guardian thresholds and weights MUST be configurable per portfolio.

#### Scenario: Custom thresholds
- GIVEN a custom config with `risk.max_drawdown=10`
- WHEN drawdown reaches 10%
- THEN transitions to DEFENSIVE (not the default 15%)
#### Scenario: Default configuration

- GIVEN no custom config
- WHEN evaluating
- THEN default thresholds are used

### Requirement: Live Account Feed (REQ-40)

MetaGuardian MUST evaluate against live demo-account data (equity, positions, costs) streamed by the autonomous monitor (REQ-41) during the demo phase, in addition to backtest-derived signals. Live drawdown/degradation SHALL drive state transitions and feed the Guardian feedback record (REQ-34). Data scope is Dukascopy-only.

#### Scenario: Live drawdown drives DEFENSIVE

- GIVEN a live account stream with drawdown > 10%
- WHEN MetaGuardian evaluates
- THEN the state transitions to DEFENSIVE
- AND the transition is recorded for feedback

#### Scenario: No stream fails closed

- GIVEN the live stream is unavailable
- WHEN MetaGuardian would evaluate live data
- THEN evaluation holds with a STREAM_LOST alert
- AND no live-based state transition occurs

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

### Requirement: State Machine Enforcement (Issue 3)

The `PortfolioState` state machine MUST enforce pipeline gating after `GuardianEvaluationStage`. `BuilderStage` MUST block when `portfolio_state` is `QUARANTINE` or `DEFENSIVE` unless an explicit human override is granted via the existing `HUMAN_APPROVE_DEPLOY` gate. The orchestrator MUST NOT silently proceed to builder execution in blocked states.
(Previously: state machine had no enforcement hooks; `_execute_state_transition` only logged and called hooks)

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