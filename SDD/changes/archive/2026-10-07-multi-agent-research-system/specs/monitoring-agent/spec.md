# Monitoring Agent Specification

## Purpose

Tracks live strategy performance via result-reader streaming equity, computes rolling metrics (Sharpe, drawdown), detects regime changes, and emits alerts. Archives live metrics to Knowledge Lake and Engram.

---

## Requirements

### Requirement: Live Equity Ingestion

The system MUST stream live equity data from deployed strategies via result-reader.stream_live().

#### Scenario: Equity stream consumed
- GIVEN deployed strategy with JCloud endpoint, result-reader configured
- WHEN MonitoringAgent.start_monitoring(campaign_id) called
- THEN result-reader.stream_live() yields EquityPoint(timestamp, equity) in real-time
- AND equity points appended to internal buffer, persisted to Knowledge Lake every 100 points

#### Scenario: Stream reconnection on disconnect
- GIVEN network interruption during streaming
- WHEN stream raises ConnectionError
- THEN MonitoringAgent retries with exponential backoff (max 5 retries, 30s base)
- AND missed period backfilled from JCloud history endpoint

### Requirement: Rolling Metrics Computation

The system MUST compute rolling Sharpe and drawdown using stats-aggregation.rolling_sharpe() and rolling_drawdown().

#### Scenario: Rolling Sharpe computed on live equity
- GIVEN live equity buffer (1000 points), window=252 (daily equivalent)
- WHEN MonitoringAgent.compute_rolling_metrics() called
- THEN RollingMetrics with rolling_sharpe[251:] as floats, first 251 None
- AND rolling_drawdown aligned, values in [0, 100]%

#### Scenario: Rolling metrics update incrementally
- GIVEN new equity point appended
- WHEN MonitoringAgent.update_rolling_metrics() called
- THEN only latest window recomputed, O(window) not O(n)

### Requirement: Regime Change Detection

The system MUST detect regime shifts using rolling metric statistical tests.

#### Scenario: Regime shift from trending to choppy detected
- GIVEN rolling_sharpe drops from 1.8→0.3 over 50 periods, rolling_drawdown doubles
- WHEN MonitoringAgent.detect_regime_change() called
- THEN RegimeAlert: type="REGIME_SHIFT", from_regime="TRENDING", to_regime="CHOPPY"
- AND confidence=0.82 (based on Sharpe z-score + drawdown magnitude)
- AND suggested_actions: ["Reduce position size 50%", "Switch to mean-reversion filters"]

#### Scenario: Volatility regime change
- GIVEN rolling_volatility (20-period) spikes 3x from baseline
- WHEN MonitoringAgent.detect_regime_change() called
- THEN RegimeAlert: type="VOLATILITY_SPIKE", severity="HIGH"
- AND suggested_actions: ["Widen stops 2x", "Pause new entries until vol normalizes"]

### Requirement: Alerting and Notification

The system MUST emit alerts via callback for: regime change, drawdown breach, Sharpe degradation, connectivity loss.

#### Scenario: Max drawdown breach alert
- GIVEN current drawdown=18%, threshold=15%
- WHEN MonitoringAgent.check_alerts() called
- THEN Alert: type="DRAWDOWN_BREACH", severity="CRITICAL", current=18%, threshold=15%
- AND callback invoked with alert, escalation to human gate HUMAN_REVIEW_PERFORMANCE

#### Scenario: Sharpe degradation alert
- GIVEN 30-day rolling Sharpe dropped from 1.5 to 0.8 (>40% degradation)
- WHEN MonitoringAgent.check_alerts() called
- THEN Alert: type="SHARPE_DEGRADATION", severity="WARNING", degradation_pct=47%
- AND suggested_action: "Review strategy parameters, consider re-optimization"

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| Live equity stream yields EquityPoint objects | Integration: mock stream, assert type and fields |
| Rolling Sharpe first N-1 are None | Unit test: 100 points, window=30 → first 29 None |
| Regime alert includes from/to regimes | Unit test: assert alert.from_regime, alert.to_regime |
| Alert callback invoked with correct payload | Unit test: mock callback, assert called with Alert |
| Reconnection backfill works | Integration: simulate disconnect, assert gap filled |

---

## Non-Functional Requirements

- **Performance**: Rolling metrics update < 10ms per point; regime detection < 50ms
- **Dependencies**: result-reader, stats-aggregation, knowledge-storage (for archival)
- **Persistence**: Live metrics archived to Knowledge Lake every 100 points; regime alerts to Engram
- **Reliability**: Stream handler runs in background task; crashes restart with state recovery