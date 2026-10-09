# Dukascopy Research Data Specification

## Purpose

Brings broker-native Dukascopy market data (M1/M5/H1 bars) and indicator-derived zones into research, closing the broker-data gap. Data scope is Dukascopy-only (D5); supported timeframes are M1, M5, and H1.

## Requirements

### Requirement: Dukascopy Market Data Provider

The system MUST provide a Dukascopy-backed research data path reusing `DataManager` (data/data_manager.py:183) and `JForexProvider.fetch_history` (jforex/provider.py:23) to return normalized OHLC Bars for M1/M5/H1. No fabricated data MAY be introduced.

#### Scenario: Bars fetched for research

- GIVEN a Dukascopy symbol with downloaded JForex history at H1
- WHEN the research data path fetches bars
- THEN normalized Bars are returned for the requested timeframe
- AND market conditions (symbol, timeframe) are explicit in the result

#### Scenario: Missing JForex history fails closed

- GIVEN the platform has not downloaded the symbol
- WHEN the provider fetches
- THEN it returns no data without raising
- AND the caller treats the absence as a soft gap

### Requirement: Indicator Zones in Research Prompt

The system MUST inject IndicatorEngine output as compact zone labels (not series) into the research prompt zones (llm_research_agent.py:366-382).

#### Scenario: Zones appear in prompt

- GIVEN fetched H1 bars for EURUSD
- WHEN `build_prompt` includes the market block
- THEN the prompt contains indicator zone labels (e.g., overbought/high/trending)
- AND raw series values are omitted

#### Scenario: Insufficient data yields insufficient_data

- GIVEN bars too few for RSI(14)
- WHEN IndicatorEngine computes
- THEN the zone is "insufficient_data"
- AND the prompt still renders the block

### Requirement: Dataset Sample Caching

Fetched samples MUST be cached under `knowledge/datasets/` and recorded in the index. Tests MUST mock the provider (SQX_FORCE_MOCK precedent).

#### Scenario: Samples cached after fetch

- GIVEN a successful fetch
- WHEN the cache path runs
- THEN `knowledge/datasets/{symbol}/` contains the sample
- AND index.yaml records it