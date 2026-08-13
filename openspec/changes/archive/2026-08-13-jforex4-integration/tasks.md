# JForex4 Integration Tasks

## Ciclo 1: Preconditions + JForexBrokerAdapter
- [x] T1.1: Add `JForexCredentials` model (`sdk/quantlab/jforex/config.py`)
- [x] T1.2: Define broker adapter protocol/interface (`sdk/quantlab/broker/protocol.py`)
- [x] T1.3: Implement `JForexBrokerAdapter` (`sdk/quantlab/broker/jforex_adapter.py`)
- [x] T1.4: Unit tests for adapter health/slippage/connection mocks
- [x] T1.5: Integration test wiring adapter into `ExecutionGuardian`

## Ciclo 2: JForexLiveFeed + StrategyBridge
- [x] T2.1: Define live feed models (`EquityPoint`, `OrderEvent`) if missing
- [x] T2.2: Implement `JForexLiveFeed` (`sdk/quantlab/jforex/live_feed.py`)
- [x] T2.3: Implement `JForexStrategyBridge` (`sdk/quantlab/jforex/strategy_bridge.py`)
- [x] T2.4: Wire `LiveEvaluation` to consume `JForexLiveFeed`
- [x] T2.5: Tests for live feed and strategy bridge with mocked JForex state

## Ciclo 3: DataManager Extensibility
- [x] T3.1: Refactor `DataManager` to registry-based datasource selection
- [x] T3.2: Add `JForexProvider` for historical data
- [x] T3.3: Keep `dukascopy` sqcli path backward compatible
- [x] T3.4: Tests for datasource switching and fallback

## Ciclo 4: LLM Indicator Export
- [x] T4.1: Java indicator export helper (`IndicatorExporter.java`)
- [x] T4.2: `LLMTechnicalAgent` to read and summarize exported indicators
- [x] T4.3: Pipeline step to inject indicator export into generated `.jfx`
- [x] T4.4: Tests for export round-trip and LLM prompt construction

## Ciclo 5: Pipeline Integration
- [x] T5.1: Add deploy stage after SQX build (`jforex_deploy_stage.py`, JForexDeployStage fail-closed)
- [x] T5.2: Update `ExecutionMonitor` to support JForex progress source (`jforex_progress_fn` factory + ExecutionMonitorStage wiring)
- [x] T5.3: End-to-end pipeline test: build → deploy → monitor → live evaluation (`test_jforex_pipeline_e2e.py`, 11 tests)
- [x] T5.4: Documentation and operator runbook for demo automation (`docs/jforex-demo-runbook.md`)
