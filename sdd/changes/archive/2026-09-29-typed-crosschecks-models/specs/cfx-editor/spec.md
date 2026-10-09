# Delta for cfx-editor

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: CFX Archive Read/Write

The system MUST read valid `.cfx` files (ZIP/DEFLATE archives) and produce typed Pydantic models for both Config and Project types. For BuildTask models, the expected sections include an optional CommissionCosts section alongside the existing 12 main sections. Written output MUST match SQX format: UTF-8 without XML declaration, ZIP/DEFLATE compression, no extraneous files. CrossChecks MUST be populated as typed Generic or AutomaticRetest models with `raw_xml` fallback for unknown elements.
(Previously: CrossChecks was populated as raw_xml-only passthrough)

#### Scenario: Read config CFX produces typed models
- GIVEN a valid config `.cfx` file with a Build task containing commission settings
- WHEN CfxReader reads it
- THEN typed Pydantic models are returned with Options, WhatToBuild, RiskMoneyManagement, Data, Rankings, PartsToImprove, CrossChecks (typed Generic or AutomaticRetest with raw_xml fallback), Notes, Blocks, ATMs, Databanks, Resources, and optionally CommissionCosts populated

#### Scenario: Read project CFX separates task files
- GIVEN a valid project `.cfx` with config.xml and Build-Task1.xml
- WHEN CfxReader reads it
- THEN a Project model is returned with separate config and Build-Task1 models

#### Scenario: Write round-trip preserves unmodified sections
- GIVEN a valid CFX read into models
- WHEN only `set_market()` is called and CfxWriter produces the archive
- THEN all untouched sections (WhatToBuild, Rankings, Blocks, ATMs) are byte-identical to the original

### Requirement: Domain Modification Methods

The system SHOULD provide domain methods — `set_market()`, `add_timeframe()`, `enable_block()`, `disable_block()`, `set_genetic()`, `set_date_range()`, `add_ranking_condition()`, `enable_crosscheck()` — that modify underlying typed models without manual XML construction. `enable_crosscheck()` MUST mutate `CrossChecksConfig.generic` typed fields.
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
