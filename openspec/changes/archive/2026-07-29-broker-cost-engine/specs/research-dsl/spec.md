# Delta for Research DSL

## MODIFIED Requirements

### Requirement: DSL Parsing

The system MUST parse a valid YAML research definition into a structured Pydantic model. The DSL MUST support markets, timeframes, strategy building blocks, acceptance criteria, and an optional `costs` section with broker profile and cost parameters.
(Previously: Supported markets, timeframes, building blocks, and acceptance criteria only — no costs section)

#### Scenario: Complete campaign definition parses successfully

- GIVEN a YAML file defining a valid research campaign with market, timeframe, building blocks, acceptance criteria, and a `costs` section
- WHEN the system parses the file
- THEN a structured Pydantic model is returned with the costs field populated

#### Scenario: Invalid YAML raises parse error

- GIVEN a YAML file with syntax errors
- WHEN the system attempts to parse
- THEN a descriptive ParseError is raised

#### Scenario: Costs section is optional

- GIVEN a YAML file without a `costs` section
- WHEN parsed
- THEN the research model is valid with costs=None

### Requirement: DSL Validation

The system MUST validate semantic constraints: market/timeframe combinations MUST be recognized, building blocks MUST reference known indicators, acceptance criteria MUST use valid metric names, and costs MUST reference a known broker profile.

#### Scenario: Unknown market reference is rejected

- GIVEN a YAML file referencing an unrecognized market
- WHEN the system validates
- THEN a ValidationError is raised

#### Scenario: Unknown broker profile in costs section

- GIVEN a YAML file with `costs: {broker: unknown_broker}`
- WHEN the system validates
- THEN a ValidationError is raised indicating the broker profile is unknown

#### Scenario: Duplicate strategy names are detected

- GIVEN a YAML file with two strategies sharing a name
- WHEN validated
- THEN a ValidationError indicates duplicate names
