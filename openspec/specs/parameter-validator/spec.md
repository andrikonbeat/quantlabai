# Parameter Validator Specification

## Purpose

Validates hypothesis parameters against SQXDocProvider constraints before strategy building, rejecting invalid configurations early in the pipeline.

## Requirements

### Requirement: REQ-F2-04 SQX Constraint Validation

The system MUST validate each hypothesis parameter against SQXDocProvider:
- Indicator name must exist in the provider
- Numeric values must be within get_valid_range()
- Enum values must be in get_enum_values()
- Type must match the provider's declared type

Invalid parameters MUST cause the hypothesis to be rejected before building.

#### Scenario: Valid parameters pass

- GIVEN parameters: RSI period=14, BB deviation=2.0
- WHEN ParameterValidator.validate_hypothesis() runs
- THEN validation passes
- AND the hypothesis proceeds to building

#### Scenario: Out-of-range value rejected

- GIVEN RSI period=500
- WHEN ParameterValidator.validate_hypothesis() runs
- THEN validation fails with a range error
- AND the hypothesis is rejected

### Requirement: REQ-F2-05 Pipeline Integration

The system MUST integrate ParameterValidator into:
- LLMMode._parse_response(): validate after parsing JSON
- RuleMode._apply_parameter_overrides(): validate before applying defaults

Integration MUST be blocking: invalid hypotheses are rejected immediately.

#### Scenario: LLMMode blocks invalid parameters

- GIVEN LLM returns {"indicator": "RSI", "period": 500}
- WHEN LLMMode._parse_response() runs
- THEN ParameterValidator rejects the hypothesis
- AND no BuildingBlock is produced

#### Scenario: RuleMode validates overrides

- GIVEN RuleMode proposes ATR period=0
- WHEN _apply_parameter_overrides() runs
- THEN ParameterValidator rejects the override
- AND the default value is retained
