# Delta for SQX Parameter KB

## ADDED Requirements

### Requirement: Doc Provider Interface

SQX Parameter KB MUST expose a doc-provider consumption interface: get_valid_range(tab, param), get_enum_values(tab, param), get_description(tab, param). These methods SHALL read from the existing YAML files and MUST NOT invent data.

#### Scenario: Doc provider returns range

- GIVEN a seeded parameter YAML with range: [2, 200]
- WHEN get_valid_range("Ranking", "Ranking Criterium") is called
- THEN (2, 200) is returned
- AND no data is invented

### Requirement: Validation Hooks

SQX Parameter KB MUST provide validation hooks that ParameterValidator can call: validate_indicator_name(name) → bool, validate_parameter_value(tab, param, value) → ValidationResult.

#### Scenario: Validation hook rejects unknown indicator

- GIVEN ParameterValidator calls validate_indicator_name("UnknownIndicator")
- WHEN the hook runs
- THEN False is returned
- AND the validator rejects the hypothesis
