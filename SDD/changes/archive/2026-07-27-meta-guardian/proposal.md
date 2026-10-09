# Proposal: MetaGuardian for QuantLab AI

## Intent

The MetaGuardian is a governance layer that supervises the entire portfolio of trading strategies, the risk exposure, and the market conditions. It decides what can operate, when, and with how much capital. Without it, the project is a strategy factory without a production supervisor — strategies can run unchecked even when market conditions are hostile or a strategy is degrading.

The MetaGuardian transforms QuantLab AI from a research laboratory into a production-grade quantitative trading system.

## Scope

### In Scope
- New `sdk/quantlab/guardian/` module with:
  - `MarketGuardian` — monitors market regime, volatility, liquidity, session
  - `RiskGuardian` — monitors drawdown, Sharpe, exposure, Kelly criterion
  - `PortfolioGuardian` — scores portfolio health, correlation, effective diversification
  - `CapitalGuardian` — dynamic capital allocation across strategy families
  - `QualityGuardian` — dynamic Health Score per strategy (integrates with Change 1)
  - `ExecutionGuardian` — broker health, latency, slippage, connection status
  - `MetaGuardianOrchestrator` — state machine coordinating all guardians
- State machine: NORMAL → VIGILANCE → DEFENSIVE → QUARANTINE → RECOVERY → NORMAL
- Per-strategy state machine: ACTIVE → MONITORING → DEGRADING → REPLACEMENT_PENDING → RETIRED
- Integration with existing Health Score System (Change 1)
- Integration with Regime Classifier (Change 3)
- Integration with Auto-Costs (Change 2)
- Tests for all components

### Out of Scope
- Strategic Evolution Engine (Change 5) — MetaGuardian makes go/no-go decisions, SEE handles replacement
- UI/Notifications (excluded per user request)
- Real-time streaming — batch checks on a schedule
- Broker execution — only monitors, does not execute

## Approach

1. **Guardian Modules**: Each guardian is an independent checker that returns a health score and alert level
2. **Orchestrator**: Combines all guardian scores into a single portfolio state using weighted aggregation
3. **State Machine**: The orchestrator transitions the portfolio through states based on aggregated scores
4. **Per-Strategy States**: Each strategy has its own state machine for degradation tracking
5. **Action Hooks**: State transitions trigger actions (reduce capital, pause strategy, flag for review)
6. **Config-Driven**: Thresholds and weights are configurable per portfolio

## Key Design Decisions

### 1. Guardian Modules are Independent
Each guardian (Market, Risk, Portfolio, Capital, Quality, Execution) operates independently. This allows adding/removing guardians without changing the orchestrator logic.

### 2. Weighted Score Aggregation
The orchestrator combines guardian scores using configurable weights. Default weights favor risk and quality over market conditions.

### 3. State Machine with Hysteresis
State transitions require sustained conditions (not momentary spikes). This prevents flapping between states.

### 4. Reuses Existing Components
- Health Score System (Change 1) → QualityGuardian
- Regime Classifier (Change 3) → MarketGuardian input
- Auto-Costs (Change 2) → ExecutionGuardian input

### 5. Action Hooks, Not Hard Actions
Guardians recommend actions (reduce capital, pause, flag) but do not execute them directly. This keeps the system auditable and safe.

## Dependencies
- **Health Score System (Change 1)**: QualityGuardian consumes per-strategy health scores
- **Auto-Costs (Change 2)**: ExecutionGuardian uses cost data for slippage/latency assessment
- **Regime Classifier (Change 3)**: MarketGuardian uses regime classification

## Risks
- **Complexity**: 6 guardians + orchestrator + state machines = significant codebase. May need chained PRs.
- **Threshold tuning**: Guardian thresholds need calibration per portfolio. Start with conservative defaults.
- **Integration surface**: Touching multiple existing modules increases regression risk.
- **No real-time execution**: MetaGuardian recommends, does not act. Production integration needed later.

## Workload Estimate
- Guardian modules: ~500 lines
- Orchestrator + state machine: ~200 lines
- DSL/Translator integration: ~100 lines
- Tests: ~300 lines
- **Total: ~1100 lines** — definitely needs chained PRs