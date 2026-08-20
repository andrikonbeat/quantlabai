# SQX Doc Provider Specification

## Purpose

Reads structured SQX parameter documentation from `structured/sqx-kb/` and exposes a programmatic interface for indicator descriptions, valid ranges, and enum values, replacing hardcoded config maps.

## Requirements

### Requirement: REQ-F2-01 YAML Schema Loading

The system MUST read parameter metadata from `structured/sqx-kb/{sqx_version}/parameters/{tab}/{param}.yaml` and expose:
- get_valid_range(param) → (min, max) | None
- get_enum_values(param) → list[str] | None
- get_description(param) → str

YAML files MUST include fields: name, type, range, enum_values, description, default.

#### Scenario: Valid YAML loads

- GIVEN `structured/sqx-kb/144.2953/parameters/Trading options/Maximum Trades Per Day.yaml`
- WHEN SQXDocProvider.load_parameter() runs
- THEN get_valid_range(), get_enum_values(), and get_description() return the YAML values

#### Scenario: Missing YAML falls back

- GIVEN no YAML exists for a parameter
- WHEN SQXDocProvider.load_parameter() runs
- THEN it probes _BUILD_CONFIG_MAP for type and range hints
- AND logs a warning that YAML is missing

### Requirement: REQ-F2-02 Version Awareness

The system MUST isolate documentation by SQX version. The provider SHALL accept sqx_version in all lookups and MUST NOT serve parameter data from a different version.

#### Scenario: Version isolation

- GIVEN docs exist for 144.2953 and 145.0
- WHEN SQXDocProvider.get_description("RSI", sqx_version="144.2953") runs
- THEN the 144.2953 description is returned
- AND the 145.0 description is not returned

### Requirement: REQ-F2-03 Fallback Probing

When YAML is missing, the system MUST probe _BUILD_CONFIG_MAP (if available) to infer:
- type: int | float | bool | str
- range: (min, max) from known config constraints
- enum_values: from known option sets

Probing MUST be transparent and MUST NOT invent parameter semantics.

#### Scenario: Fallback infers type

- GIVEN _BUILD_CONFIG_MAP contains {"Maximum Trades Per Day": {"type": "int", "min": 0, "max": 100}}
- WHEN YAML is missing for that parameter
- THEN SQXDocProvider returns type=int, range=(0, 100)
- AND a fallback warning is logged
