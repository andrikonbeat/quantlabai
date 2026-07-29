# Broker Profiles Specification

## Purpose

Preset broker profiles with real cost parameters for Dukascopy, Interactive Brokers, and OANDA.

## Requirements

### Requirement: Preset Profiles

The system MUST provide BrokerProfile factory methods for Dukascopy, IB, and OANDA with published commission, swap, spread, and slippage parameters per asset class.

| Profile | Commission (EURUSD) | Spread (pips) | Swap Long/Short |
|---------|-------------------|---------------|-----------------|
| Dukascopy | $3.0/100k, tiered | 0.8 | -0.5 / -1.2 |
| IB | $0.50-2.00/contract | 0.6 | -0.3 / -0.9 |
| OANDA | 0 (spread-only) | 1.2 | -0.4 / -1.0 |

#### Scenario: Dukascopy profile
- GIVEN BrokerProfile.dukascopy()
- WHEN inspecting commission for 100k EURUSD
- THEN commission = $3.0

#### Scenario: IB profile
- GIVEN BrokerProfile.interactive_brokers()
- WHEN inspecting EURUSD commission
- THEN returns tiered rate by volume tier

### Requirement: Custom Profiles

The system SHOULD allow creating custom profiles from a preset with selective overrides.

#### Scenario: Override commission only
- GIVEN BrokerProfile(base="dukascopy", commission=CommissionSchema(type="fixed", value=2.0))
- WHEN inspecting
- THEN all params inherit from Dukascopy except commission = $2.0
