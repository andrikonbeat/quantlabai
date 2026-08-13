# JForex4 Integration Design

## Architecture

QuantLab remains the research/LLM/guardian brain. JForex4 remains the execution/visualization platform. Integration happens through local filesystem and process-level bridge, not REST.

```
QuantLab
  ├── SQX build → .java → compile → .jfx
  ├── JForexStrategyBridge → deploy/start/stop .jfx in JForex4
  ├── JForexBrokerAdapter → health/slippage/connection for ExecutionGuardian
  ├── JForexLiveFeed → equity/orders → LiveEvaluation
  └── IndicatorExporter → strategy-local JSON → LLMTechnicalAgent
```

## Components

### JForexBrokerAdapter
- Reads JForex4 local state: account info, orders history, connection status
- Implements `get_health_score()`, `get_recent_slippage()`, `is_connected()`
- Fail-closed on missing data

### JForexLiveFeed
- Polls JForex4 local reports/state for equity and order events
- Produces `EquityPoint` and `OrderEvent` streams
- Used by `LiveEvaluation` and `ExecutionMonitor`

### JForexStrategyBridge
- Wraps JForex4 SDK/client for `.jfx` lifecycle
- `compile()`, `deploy()`, `start()`, `stop()`, `status()`
- Reads process/strategy state from JForex4

### DataManager Extension
- New datasource key: `jforex`
- New provider: `JForexProvider`
- Existing `dukascopy` sqcli path untouched

### IndicatorExporter
- Java helper class packaged into `.jfx`
- Writes indicator values to `~/JForex4/exports/quantlab-indicators-<strategy>.json`
- QuantLab LLM agent reads same path

## State Machine

No new portfolio states. JForex integration feeds existing `MetaGuardianOrchestrator` and `LiveEvaluation` with real data.

## Failure Modes

- JForex4 not running → broker adapter returns 0.0 health, live feed empty, fail-closed
- Strategy compile error → deployment blocked, pipeline halts
- Indicator export missing → LLM agent receives empty summary, no crash
