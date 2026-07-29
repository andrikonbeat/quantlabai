# Research DSL Specification

## Purpose

YAML-based Domain Specific Language for defining quantitative research campaigns. Enables researchers to describe markets, timeframes, building blocks (indicators, entry/exit rules), and acceptance criteria in a structured, versionable format.

## Requirements

### Requirement: DSL Parsing

The system MUST parse a valid YAML research definition into a structured Pydantic model. The DSL MUST support markets, timeframes, strategy building blocks, acceptance criteria, and an optional `costs` section with broker profile and cost parameters.
(Previously: Supported markets, timeframes, building blocks, and acceptance criteria only — no costs section)

#### Scenario: Complete campaign definition parses successfully

- GIVEN a YAML file defining a valid research campaign with market, timeframe, building blocks, acceptance criteria, and a `costs` section
- WHEN the system parses the file
- THEN a structured Pydantic model is returned with the costs field populated

#### Scenario: Invalid YAML raises parse error

- GIVEN a YAML file with syntax errors (malformed indentation, invalid types)
- WHEN the system attempts to parse the file
- THEN a descriptive ParseError is raised identifying the location and nature of the syntax error

#### Scenario: Costs section is optional

- GIVEN a YAML file without a `costs` section
- WHEN parsed
- THEN the research model is valid with costs=None

### Requirement: DSL Validation

The system MUST validate semantic constraints: market/timeframe combinations MUST be recognized, building blocks MUST reference known indicators, acceptance criteria MUST use valid metric names, and costs MUST reference a known broker profile.

#### Scenario: Unknown market reference is rejected

- GIVEN a YAML file referencing an unrecognized market identifier
- WHEN the system validates the parsed model
- THEN a ValidationError is raised listing the unknown market as the cause

#### Scenario: Unknown broker profile in costs section

- GIVEN a YAML file with `costs: {broker: unknown_broker}`
- WHEN the system validates
- THEN a ValidationError is raised indicating the broker profile is unknown

#### Scenario: Duplicate strategy names are detected

- GIVEN a YAML file defining two strategies with the same name
- WHEN the system validates the parsed model
- THEN a ValidationError is raised indicating the duplicate name conflict

### Requirement: Cross-Platform Path Resolution

The system MUST resolve paths in DSL definitions using platform-agnostic separators. Paths SHALL use forward slashes (POSIX) or backslashes (Windows) according to the host OS.

#### Scenario: Paths resolve correctly on Linux

- GIVEN a DSL definition with a relative path `knowledge/raw/data.csv` on Linux
- WHEN the system resolves the path
- THEN the path uses POSIX forward slashes and is absolute from the project root

#### Scenario: Paths resolve correctly on Windows

- GIVEN a DSL definition with path `knowledge/raw/data.csv` on Windows
- WHEN the system resolves the path
- THEN the path uses Windows backslashes from the project root

### Requirement: DSL Serialization

The system MUST serialize a research model back to YAML, preserving all fields and structure, to enable round-trip editing.

#### Scenario: Model serializes to valid YAML

- GIVEN a populated research model
- WHEN the system serializes it to YAML
- THEN the output is valid YAML that can be re-parsed to an identical model
