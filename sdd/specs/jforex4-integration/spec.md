# JForex4 Integration Specification

## REQ-01: JForex Broker Adapter
The system MUST provide a `JForexBrokerAdapter` implementing the broker interface expected by `ExecutionGuardian`.

### Scenario: Health score from JForex local state
- GIVEN JForex4 is running and connected
- WHEN `JForexBrokerAdapter.get_health_score()` is called
- THEN it returns a float in [0.0, 1.0] derived from connection/account state

### Scenario: Slippage from recent fills
- GIVEN JForex4 has filled orders in local history
- WHEN `JForexBrokerAdapter.get_recent_slippage()` is called
- THEN it returns slippage in bps computed from order fills

### Scenario: Connection status
- GIVEN JForex4 client is disconnected
- WHEN `JForexBrokerAdapter.is_connected()` is called
- THEN it returns False

## REQ-02: JForex Live Feed
The system MUST provide a `JForexLiveFeed` that produces `EquityPoint` and `OrderEvent` sequences from JForex4 local state.

### Scenario: Equity stream
- GIVEN JForex4 account equity updates are available
- WHEN `JForexLiveFeed.stream_equity()` is called
- THEN it yields `EquityPoint` instances in timestamp order

### Scenario: Order events stream
- GIVEN JForex4 orders history is readable
- WHEN `JForexLiveFeed.stream_orders()` is called
- THEN it yields order fill/close events with timestamps

## REQ-03: JForex Strategy Bridge
The system MUST provide a `JForexStrategyBridge` for `.jfx` lifecycle.

### Scenario: Compile Java to JFX
- GIVEN a `.java` strategy source exists
- WHEN `JForexStrategyBridge.compile(source_path)` is called
- THEN a `.jfx` artifact is produced in the same directory

### Scenario: Start strategy
- GIVEN a compiled `.jfx` exists
- WHEN `JForexStrategyBridge.start(jfx_path, params)` is called
- THEN JForex4 loads and starts the strategy

### Scenario: Stop strategy
- GIVEN a strategy is running
- WHEN `JForexStrategyBridge.stop(process_id)` is called
- THEN the strategy is stopped

## REQ-04: DataManager Extensibility
The system MUST support JForex4 as an alternative datasource in `DataManager` without breaking existing sqcli/dukascopy paths.

### Scenario: JForex datasource selection
- GIVEN `DataManager` is configured with `datasource="jforex"`
- WHEN `ensure_symbol("EURUSD", datasource="jforex")` is called
- THEN it uses the JForex data path instead of sqcli

### Scenario: Default sqcli path unchanged
- GIVEN no datasource override
- WHEN `ensure_symbol("EURUSD")` is called
- THEN sqcli/dukascopy path is used as before

## REQ-05: LLM Indicator Export
The system MUST export indicator values computed inside `.jfx` strategies to a local format readable by QuantLab LLM agents.

### Scenario: Indicator JSON export
- GIVEN a strategy computes indicators
- WHEN the strategy calls the indicator export helper
- THEN a JSON file with timestamped indicator values is written

### Scenario: LLM agent reads indicators
- GIVEN an indicator JSON file exists
- WHEN `LLMTechnicalAgent.analyze()` reads it
- THEN it produces a technical analysis summary for the LLM

## REQ-06: Pipeline Integration
The system MUST integrate JForex deploy and live feed into the QuantLab pipeline.

### Scenario: Post-SQX deploy stage
- GIVEN SQX build produced a `.jfx`
- WHEN the pipeline reaches the deploy stage
- THEN `JForexStrategyBridge` deploys it to JForex4

### Scenario: Live ops monitoring
- GIVEN a strategy is running in JForex4
- WHEN `ExecutionMonitor` polls progress
- THEN it uses `JForexLiveFeed` instead of SQX HTTP status
