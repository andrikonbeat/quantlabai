# Broker Cost Models Specification

## Purpose

Pydantic models for broker-related costs: commissions, swaps, slippage, market sessions, and spreads.

## Requirements

### Requirement: Commission Models

The system MUST provide a CommissionSchema supporting `fixed`, `percent`, and `tiered` commission types.

#### Scenario: Fixed commission
- GIVEN CommissionSchema(type="fixed", value=5.0)
- WHEN computing cost for 1 lot
- THEN total commission = 5.0

#### Scenario: Tiered commission
- GIVEN CommissionSchema(type="tiered", tiers=[(0, 100_000, 3.0), (100_000, 1e9, 2.0)])
- WHEN computing for 200k notional
- THEN first 100k at 3.0, remainder at 2.0

### Requirement: Swap Rules

The system MUST provide SwapRule with long/short rates, triple-swap day, and currency.

#### Scenario: Overnight swap
- GIVEN SwapRule(long_rate=0.5, short_rate=-1.2, triple_day="Wednesday")
- WHEN computing for a LONG position held overnight on Tuesday
- THEN rate = 0.5 pips

#### Scenario: Triple swap
- GIVEN same SwapRule, position held overnight Wednesday
- THEN rate = 1.5 pips (3x)

### Requirement: Slippage Profiles

The system MUST support `static` and `session` slippage modes.

#### Scenario: Static slippage
- GIVEN SlippageProfile(mode="static", fixed_pips=0.5)
- WHEN queried
- THEN returns 0.5 pips regardless of session

### Requirement: Market Sessions

The system MUST define MarketSession with name, open/close, and spread_multiplier.

#### Scenario: London session
- GIVEN MarketSession(name="London", spread_multiplier=1.0)
- WHEN used in spread calc
- THEN base spread is unmodified

### Requirement: Spread Config

The system MUST provide SpreadConfig(base_spread, session_overrides, asset_defaults).

#### Scenario: Session-aware spread
- GIVEN SpreadConfig(base_spread=1.2, session_overrides={"London": 0.8})
- WHEN queried for London
- THEN effective spread = 1.2 * 0.8 = 0.96
