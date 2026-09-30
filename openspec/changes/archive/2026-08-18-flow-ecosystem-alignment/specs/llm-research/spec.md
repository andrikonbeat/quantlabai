# Delta for llm-research

## ADDED Requirements

### Requirement: Dukascopy Market Context (G3)

`LLMResearchAgent.build_prompt` MUST include a Dukascopy-backed market context block: normalized M1/M5/H1 Bars from `DataManager`/`JForexProvider` plus compact indicator zones from `IndicatorEngine`. When the provider is unavailable, the block MUST be omitted and the agent MUST continue with the remaining providers.

#### Scenario: Market block with bars and zones

- GIVEN Dukascopy H1 bars available for the target symbol
- WHEN `build_prompt` assembles the prompt
- THEN the prompt contains a market block with timeframe and zone labels
- AND the block cites its data source

#### Scenario: Provider unavailable degrades

- GIVEN JForex history missing for the symbol
- WHEN `build_prompt` assembles the prompt
- THEN the market block is omitted
- AND no exception is raised

#### Scenario: Zones reflect market conditions

- GIVEN a high-volatility session on the fetched bars
- WHEN the market block is rendered
- THEN the volatility zone reads "high"
- AND the oscillator zones reflect the session values