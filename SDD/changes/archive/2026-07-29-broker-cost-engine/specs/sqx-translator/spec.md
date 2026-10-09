# Delta for SQX Translator

## MODIFIED Requirements

### Requirement: DSL-to-CFX Translation

The system MUST translate a valid research DSL model into a CFX archive using cfx-editor typed Pydantic models. The translation MUST encode market, timeframe, strategy parameters, entry/exit rules, AND cost configuration (broker profile, commission, slippage) via cfx-editor domain methods, then produce the final archive through CfxWriter.
(Previously: Did not encode cost configuration)

#### Scenario: Complete translation with costs

- GIVEN a research model with market EURUSD, timeframe H1, one strategy, and a costs section (broker: ib)
- WHEN the system translates it
- THEN the CFX archive contains commission and spread settings matching IB profile

#### Scenario: Translation without costs (backward compatible)

- GIVEN a research model without a costs section
- WHEN translated
- THEN CFX output is identical to pre-change — no cost sections present

### Requirement: Translation Validation

The system MUST validate that the input DSL model contains all required fields for CFX generation (market, timeframe, at least one strategy). If a costs section is present, it MUST reference a known broker profile. Missing required fields MUST produce a TranslationError.

#### Scenario: Unknown broker profile rejected

- GIVEN a research model with costs referencing an unknown broker
- WHEN translating
- THEN a TranslationError is raised specifying the unknown broker profile
