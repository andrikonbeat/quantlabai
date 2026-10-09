# Delta for Research Agent

## ADDED Requirements

### Requirement: EconomicSenseValidator Integration

ResearchAgent MUST run EconomicSenseValidator on all generated hypotheses in both RuleMode and LLMMode. Validation warnings SHALL be attached to the HypothesisConfig object.

#### Scenario: RuleMode validates parameters

- GIVEN ResearchAgent in RuleMode generates RSI(500)
- WHEN EconomicSenseValidator.validate() runs
- THEN a warning is logged
- AND HypothesisConfig.validation_warnings contains the range error

### Requirement: TagCalibrator Integration

ResearchAgent MUST invoke TagCalibrator after Knowledge Lake queries and before returning hypotheses. Calibrated confidence SHALL replace the base confidence in HypothesisConfig.

#### Scenario: Confidence calibrated by tag

- GIVEN a trend hypothesis with strategy=trend tag
- WHEN TagCalibrator.calibrate() runs
- THEN HypothesisConfig.confidence reflects tag Sharpe percentile
- AND the calibrated value is persisted
