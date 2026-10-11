# CFX Editor Specification

## Purpose

Read, modify, and write StrategyQuant `.cfx` files — Config CFX (`<Task>` root, single XML) and Project CFX (`<Project>` root, multi-file) — using Pydantic models that map 1:1 to the real CFX XML structure.

> **Relationship to `cfx-serialization`**: `cfx-editor` is the umbrella spec for
> the whole `.cfx` read/write/patch domain. The flat-lane key grammar and its
> invertible codec (reader↔writer round-trip) are specified in the narrower
> capability spec `sdd/specs/cfx-serialization/spec.md`; this spec does not
> restate them.

## Requirements

### Requirement: CFX Archive Read/Write

The system MUST read valid `.cfx` files (ZIP/DEFLATE archives) and produce typed Pydantic models for both Config and Project types. For BuildTask models, the expected sections include an optional CommissionCosts section alongside the existing 12 main sections, and a typed `RiskConfig` bridge for `risk_money_mgmt`. CrossChecks MUST be populated as typed Generic or AutomaticRetest models with `raw_xml` fallback for unknown elements. Written output MUST match SQX format: UTF-8 without XML declaration, ZIP/DEFLATE compression, no extraneous files.
(Previously: No commission/cost sections or typed RiskConfig bridge existed; CrossChecks was populated as raw_xml-only passthrough)

#### Scenario: Read config CFX produces typed RiskConfig
- GIVEN a valid config `.cfx` file with a Build task containing risk settings
- WHEN CfxReader reads it
- THEN typed Pydantic models are returned with Options, WhatToBuild, RiskMoneyManagement (as `RiskConfig`), Data, Rankings, PartsToImprove, CrossChecks (typed Generic or AutomaticRetest with raw_xml fallback), Notes, Blocks, ATMs, Databanks, Resources, and optionally CommissionCosts populated

#### Scenario: Read project CFX separates task files
- GIVEN a valid project `.cfx` with config.xml and Build-Task1.xml
- WHEN CfxReader reads it
- THEN a Project model is returned with separate config and Build-Task1 models

#### Scenario: Write round-trip preserves unmodified sections
- GIVEN a valid CFX read into models
- WHEN only `set_market()` is called and CfxWriter produces the archive
- THEN all untouched sections (WhatToBuild, Rankings, Blocks, ATMs) are byte-identical to the original

#### Scenario: Write CFX preserves RiskConfig fields
- GIVEN a BuildTask with a populated `RiskConfig` bridge
- WHEN CfxWriter produces the archive
- THEN the output XML contains the risk_money_mgmt elements with correct values
- AND round-trip deserialization recovers the original `RiskConfig`

### Requirement: Commission/Cost Sections

The BuildTask model MUST include optional commission and cost configuration sections corresponding to broker profile parameters in the CFX XML.

#### Scenario: Read CFX with commission settings

- GIVEN a CFX file containing commission and spread XML elements
- WHEN CfxReader reads it into BuildTask
- THEN the commission section is populated with commission type, value, and tier data

#### Scenario: Write CFX preserves commission fields

- GIVEN a BuildTask with populated commission section
- WHEN CfxWriter produces the archive
- THEN the output XML contains the commission elements with correct values

### Requirement: Domain Modification Methods

The system SHOULD provide domain methods — `set_market()`, `add_timeframe()`, `enable_block()`, `disable_block()`, `set_genetic()`, `set_date_range()`, `add_ranking_condition()`, `enable_crosscheck()` — that modify underlying models without manual XML construction. `enable_crosscheck()` MUST mutate `CrossChecksConfig.generic` typed fields.
(Previously: enable_crosscheck operated on raw_xml-only CrossChecks)

#### Scenario: set_market updates all symbol references
- GIVEN a CFX configured for EURUSD on H1
- WHEN `set_market("GBPUSD")` is called
- THEN Resources/Symbols, Setup/Chart symbol, and Data/Symbol fields all reflect GBPUSD

#### Scenario: enable_block activates a disabled block
- GIVEN a CFX with block key "MA.CrossOver" disabled (use=0)
- WHEN `enable_block("MA.CrossOver")` is called
- THEN the block's use flag is set to 1 and weight is defaulted to 100

#### Scenario: set_date_range uses correct format per section
- GIVEN a CFX with date range 2020.01.01-2024.12.31
- WHEN `set_date_range("2022.01.01", "2023.12.31")` is called
- THEN Data/Setups use YYYY.MM.DD and Resources/Symbols/Sessions use epoch milliseconds

#### Scenario: enable_crosscheck operates on typed Generic model
- GIVEN a CFX with CrossChecks in Generic dialect where `mc_enabled=False`
- WHEN `enable_crosscheck("MonteCarlo")` is called
- THEN `CrossChecksConfig.generic.mc_enabled` becomes `True` and the writer emits the updated typed XML

### Requirement: Typed CrossChecks Patcher Validation

The system MUST validate typed CrossChecks mutations through CfxPatcher. `SetCrossChecksInstruction` MUST update `CrossChecksConfig.generic` typed fields instead of replacing `raw_xml`. Invalid typed values MUST raise ValidationError without partial application.

#### Scenario: SetCrossChecksInstruction updates typed Generic fields
- GIVEN a CfxPatcher with a CFX containing `CrossChecksConfig(generic=CrossChecksGeneric(mc_runs=100))`
- WHEN `apply(SetCrossChecksInstruction(mc_runs=200))` is executed
- THEN `CrossChecksConfig.generic.mc_runs` is `200` and `raw_xml` is regenerated to include the updated element

#### Scenario: Invalid typed value raises ValidationError
- GIVEN a CfxPatcher with a CFX containing typed CrossChecks
- WHEN `apply(SetCrossChecksInstruction(mc_runs=-1))` is executed
- THEN a ValidationError is raised and no fields are modified

### Requirement: CfxPatcher High-Level API

The system MUST provide a CfxPatcher that accepts sequential modification instructions for LLM-driven editing. Each instruction MUST be validated before application; invalid instructions MUST raise ValidationError without applying partial changes.

#### Scenario: Sequential modifications applied in order
- GIVEN a CFX loaded into CfxPatcher
- WHEN applying `[set_market("GBPUSD"), add_timeframe("H4"), enable_block("MA.CrossOver")]`
- THEN all three modifications are validated and the resulting models reflect all changes

#### Scenario: Invalid block key rejected
- GIVEN a CfxPatcher with loaded CFX
- WHEN an instruction references an unrecognized block key
- THEN a ValidationError is raised and no instruction in the sequence is applied

### Requirement: Version Safety

The system MUST parse the schema version from CFX files and reject unsupported versions with a descriptive VersionError.

#### Scenario: Unsupported version raises error
- GIVEN a CFX with schema version 200.0000
- WHEN CfxReader attempts parsing
- THEN a VersionError is raised indicating the supported range

### Requirement: Typed Error Handling

The system MUST raise CfxNotFoundError for missing files, CfxCorruptError for invalid ZIP/XML, and CfxParseError for schema violations — with descriptive messages including the file path.

#### Scenario: Missing file raises CfxNotFoundError
- GIVEN a non-existent file path
- WHEN CfxReader.open() is called
- THEN a CfxNotFoundError is raised with the path

#### Scenario: Corrupt ZIP raises CfxCorruptError
- GIVEN a `.cfx` file that is not a valid ZIP
- WHEN CfxReader attempts to read it
- THEN a CfxCorruptError is raised describing the parse failure

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

### Requirement: Robustness Tab Typed Coverage and Dual-Output Summary

(Added by `crosschecks-full-parameter-catalog`, archived 2026-09-30.)

The `CrossChecks` typed models MUST cover the robustness tabs whose parameters are cataloged as `BuildConfig`-reachable. `CrossChecksAutomaticRetest` MUST expose `what_if` as a typed `WhatIfConfig` (`use` + `methods`) and `monte_carlo_retest` MUST expose `methods` as `list[CrossChecksMethod]`, where each `CrossChecksMethod` carries `use`, `type` and `params`. Unrecognized `<CrossChecks>` children and unmodeled sub-structures MUST continue to fall back to `raw_xml`; dialect detection and `raw_xml` behavior for the Generic and AutomaticRetest dialects MUST be preserved unchanged by these additions.

`CrossChecksConfig` MUST provide a `summary()` method returning both a machine-readable dict and a human-readable string. The dict MUST carry `dialect`, `enabled_tabs`, `typed_values` and the typed sub-model dumps. The string MUST be a single line — no newline or carriage-return characters — so it can be embedded directly in a log envelope.

#### Scenario: WhatIf method parameters round-trip
- GIVEN a `<WhatIf>` element whose `<Settings><Methods>` block declares methods with `use`, `type` and `<Params>`
- WHEN the CFX is parsed into `CrossChecksConfig` and re-serialized
- THEN `automatic_retest.what_if.use` and `automatic_retest.what_if.methods` are populated
- AND re-parsing the serialized output recovers the same method list

#### Scenario: MonteCarloRetest method parameters round-trip
- GIVEN a `<MonteCarloRetest>` element declaring `<Methods>` alongside its scalar settings
- WHEN the CFX is parsed and re-serialized
- THEN `automatic_retest.monte_carlo_retest.methods` is populated with one `CrossChecksMethod` per `<Method>` element
- AND the tab's scalar settings are unchanged by the round-trip

#### Scenario: Dialect behavior is preserved by the added coverage
- GIVEN a CFX in either the Generic or the AutomaticRetest dialect
- WHEN it is parsed and re-serialized
- THEN the detected `dialect` is the same before and after
- AND any unrecognized `<CrossChecks>` child is still preserved in `raw_xml`

#### Scenario: Summary returns JSON and a single-line text envelope
- GIVEN a populated `CrossChecksConfig`
- WHEN `summary()` is called
- THEN the result has both a `json` and a `text` key
- AND `json` contains `dialect`, `enabled_tabs` and `typed_values`
- AND `text` contains no newline or carriage-return character

