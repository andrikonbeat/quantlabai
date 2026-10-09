# Cost Engine Specification

## Purpose

Computes total trade cost per symbol — commissions, swaps, slippage, and spreads — for static and session-aware pricing.

## Requirements

### Requirement: Per-Trade Cost Computation

The CostEngine MUST compute total cost for a single trade given symbol, volume, direction, and session.

#### Scenario: Complete trade cost
- GIVEN CostEngine with Dukascopy profile, EURUSD, 1 lot
- WHEN compute(symbol="EURUSD", volume=100000, direction="LONG", session="London")
- THEN total_cost = commission + spread_cost + (swap if held overnight)

#### Scenario: No swap for intraday
- GIVEN same engine, trade closed same day
- WHEN compute with held_overnight=False
- THEN swap component = 0

### Requirement: Per-Symbol Aggregation

The CostEngine MUST aggregate costs across multiple trades per symbol.

#### Scenario: Multi-trade aggregation
- GIVEN CostEngine with 3 trades on EURUSD
- WHEN compute_symbol("EURUSD")
- THEN returns total_cost, avg_cost_per_trade, min/max per component

### Requirement: Structured Cost Breakdown

The CostEngine MUST return a CostBreakdown with per-component values.

#### Scenario: Breakdown inspection
- GIVEN CostEngine.calculate(trade_data)
- WHEN inspecting result
- THEN result.breakdown contains commission, swap, slippage, spread with individual values

### Requirement: Profile Switching

The CostEngine MUST allow switching the active BrokerProfile at runtime.

#### Scenario: Switch broker mid-session
- GIVEN CostEngine with Dukascopy profile
- WHEN set_profile("ib") is called
- THEN subsequent calculations use IB parameters
