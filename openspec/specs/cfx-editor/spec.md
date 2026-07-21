# CFX Editor Specification

## Purpose

Read, modify, and write StrategyQuant `.cfx` files — Config CFX (`<Task>` root, single XML) and Project CFX (`<Project>` root, multi-file) — using Pydantic models that map 1:1 to the real CFX XML structure.

## Requirements

### Requirement: CFX Archive Read/Write

The system MUST read valid `.cfx` files (ZIP/DEFLATE archives) and produce typed Pydantic models for both Config and Project types. Written output MUST match SQX format: UTF-8 without XML declaration, ZIP/DEFLATE compression, no extraneous files.

#### Scenario: Read config CFX produces typed models
- GIVEN a valid config `.cfx` file with a Build task containing all 12 settings sections
- WHEN CfxReader reads it
- THEN typed Pydantic models are returned with Options, WhatToBuild, RiskMoneyManagement, Data, Rankings, PartsToImprove, CrossChecks, Notes, Blocks, ATMs, Databanks, and Resources populated

#### Scenario: Read project CFX separates task files
- GIVEN a valid project `.cfx` with config.xml and Build-Task1.xml
- WHEN CfxReader reads it
- THEN a Project model is returned with separate config and Build-Task1 models

#### Scenario: Write round-trip preserves unmodified sections
- GIVEN a valid CFX read into models
- WHEN only `set_market()` is called and CfxWriter produces the archive
- THEN all untouched sections (WhatToBuild, Rankings, Blocks, ATMs) are byte-identical to the original

### Requirement: Domain Modification Methods

The system SHOULD provide domain methods — `set_market()`, `add_timeframe()`, `enable_block()`, `disable_block()`, `set_genetic()`, `set_date_range()`, `add_ranking_condition()`, `enable_crosscheck()` — that modify underlying models without manual XML construction.

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
