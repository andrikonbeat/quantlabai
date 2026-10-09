# Delta for cfx-editor

## ADDED Requirements

### Requirement: Typed RiskConfig → CFX risk_money_mgmt Mapping (Issue 2)

The system MUST provide a `RiskConfigMapper` that serializes a typed `RiskConfig` Pydantic model into `BuildTask.risk_money_mgmt` `SettingsSection` entries with known SQX XML keys. The mapper SHALL validate field types and ranges before serialization; invalid values MUST raise `RiskConfigError`. The round-trip (CFX → RiskConfig → CFX) MUST preserve all non-conflicting fields.

#### Scenario: RiskConfig round-trips through CFX

- GIVEN a `RiskConfig` with `max_portfolio_drawdown=0.15`, `kelly_fraction_cap=0.25`
- WHEN `RiskConfigMapper.to_cfx(risk_config)` is called
- THEN `BuildTask.risk_money_mgmt` contains the corresponding SQX XML keys
- AND deserializing back produces an equivalent `RiskConfig`

#### Scenario: Invalid range fails closed

- GIVEN a `RiskConfig` with `max_portfolio_drawdown=2.0` (out of [0,1])
- WHEN `RiskConfigMapper.to_cfx(risk_config)` is called
- THEN `RiskConfigError` is raised
- AND no partial CFX section is written

#### Scenario: SQX version safety

- GIVEN a CFX with unsupported schema version
- WHEN `RiskConfigMapper.from_cfx(build_task)` is called
- THEN `VersionError` is raised
- AND the mapper does not produce a partial `RiskConfig`

## MODIFIED Requirements

### Requirement: CFX Archive Read/Write

The system MUST read valid `.cfx` files (ZIP/DEFLATE archives) and produce typed Pydantic models for both Config and Project types. For BuildTask models, the expected sections include an optional CommissionCosts section alongside the existing 12 main sections, and a typed `RiskConfig` bridge for `risk_money_mgmt`. Written output MUST match SQX format: UTF-8 without XML declaration, ZIP/DEFLATE compression, no extraneous files.

(Previously: No commission/cost sections or typed RiskConfig bridge existed)

#### Scenario: Read config CFX produces typed RiskConfig

- GIVEN a valid config `.cfx` file with a Build task containing risk settings
- WHEN CfxReader reads it
- THEN typed Pydantic models are returned with Options, WhatToBuild, RiskMoneyManagement (as `RiskConfig`), Data, Rankings, PartsToImprove, CrossChecks, Notes, Blocks, ATMs, Databanks, Resources, and optionally CommissionCosts populated

#### Scenario: Write CFX preserves RiskConfig fields

- GIVEN a BuildTask with a populated `RiskConfig` bridge
- WHEN CfxWriter produces the archive
- THEN the output XML contains the risk_money_mgmt elements with correct values
- AND round-trip deserialization recovers the original `RiskConfig`
