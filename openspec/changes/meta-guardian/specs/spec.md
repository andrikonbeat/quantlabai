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