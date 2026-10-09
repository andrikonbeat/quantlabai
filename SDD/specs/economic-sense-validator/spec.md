# Economic Sense Validator Specification

## Purpose

Validates indicator parameters against known SQX semantics and cross-parameter coherence before hypothesis generation, catching impossible configurations early.

## Requirements

### Requirement: REQ-F1-01 Indicator Range Validation

The system MUST validate indicator parameters against known safe ranges:
- RSI period ∈ [2, 200]
- Bollinger Bands deviation ∈ [0.1, 5.0]
- SMA/EMA period ∈ [2, 500]
- ATR period ∈ [2, 200]
- MACD fast/slow ∈ [2, 200], signal ∈ [2, 100]

Out-of-range values MUST emit a warning but not block hypothesis generation.

#### Scenario: RSI period out of range

- GIVEN a hypothesis with RSI period = 500
- WHEN EconomicSenseValidator.validate() runs
- THEN a warning is logged
- AND the hypothesis is returned with a validation flag

#### Scenario: All parameters in range

- GIVEN a hypothesis with RSI(14), BB(20, 2.0)
- WHEN EconomicSenseValidator.validate() runs
- THEN no warnings are emitted
- AND the hypothesis passes validation

### Requirement: REQ-F1-02 Cross-Parameter Coherence

The system MUST warn when related parameters diverge beyond reasonable bounds:
- BB period and SMA/EMA period: warn if ratio > 3× or < 0.33×
- MACD fast/slow/signal: warn if fast ≥ slow

#### Scenario: Coherent parameters

- GIVEN BB period = 20 and SMA period = 50
- WHEN cross-parameter check runs
- THEN no coherence warning is emitted

#### Scenario: Incoherent parameters

- GIVEN BB period = 10 and SMA period = 100
- WHEN cross-parameter check runs
- THEN a coherence warning is logged

### Requirement: REQ-F1-03 Pipeline Integration

The system MUST integrate EconomicSenseValidator into both RuleMode and LLMMode hypothesis generation. Validation MUST be non-blocking: warnings are appended to the hypothesis, and generation continues.

#### Scenario: RuleMode integration

- GIVEN ResearchAgent in RuleMode
- WHEN a hypothesis is generated
- THEN EconomicSenseValidator runs on the proposed parameters
- AND warnings are attached to the output

#### Scenario: LLMMode integration

- GIVEN ResearchAgent in LLMMode
- WHEN LLM returns parameter suggestions
- THEN EconomicSenseValidator runs on parsed parameters
- AND warnings are attached to the HypothesisConfig

### Requirement: REQ-F1-04 Non-Blocking Behavior

The system MUST never reject a hypothesis solely due to validation warnings. Warnings SHALL be advisory. Hard failures are reserved for malformed data or missing required fields.

#### Scenario: Warning does not block

- GIVEN a hypothesis with multiple parameter warnings
- WHEN validation completes
- THEN the hypothesis is still returned to the caller
- AND the caller can inspect warnings before proceeding
