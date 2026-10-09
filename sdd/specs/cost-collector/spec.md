# Cost Collector Specification

## Purpose

CostCollector implementing the interface expected by ExecutionGuardian and MarketGuardian for real-time cost data.

## Requirements

### Requirement: ExecutionGuardian Interface

The CostCollector MUST provide `get_recent_slippage(symbol) -> float` and a `.slippage` property that returns slippage estimates.

#### Scenario: Slippage query
- GIVEN CostCollector with active broker profile
- WHEN get_recent_slippage("EURUSD") is called
- THEN returns current slippage in pips (static or session-based)

### Requirement: MarketGuardian Interface

The CostCollector MUST provide `spread_pips(symbol)`, `collect_all()`, and session-scoring functions for MarketGuardian.

#### Scenario: Spread collection
- GIVEN CostCollector with London session
- WHEN spread_pips("EURUSD")
- THEN returns current spread including session multiplier

#### Scenario: Full collection
- GIVEN CostCollector initialized for EURUSD, GBPUSD
- WHEN collect_all() is called
- THEN returns dict per symbol with spread_pips, slippage_pips, session_name, session_score

### Requirement: Default State

The CostCollector MUST initialize with sensible defaults when no broker profile is configured.

#### Scenario: No-profile fallback
- GIVEN CostCollector()
- WHEN spread_pips("EURUSD")
- THEN returns a conservative default (e.g., 1.5 pips) without throwing
