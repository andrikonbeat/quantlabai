# Delta for CFX Editor

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: CFX Archive Read/Write

The system MUST read valid `.cfx` files and produce typed Pydantic models. For BuildTask models, the expected sections now include an optional CommissionCosts section alongside the existing 12 main sections.
(Previously: No commission/cost sections existed in BuildTask)

#### Scenario: Read config CFX produces typed models (updated)

- GIVEN a valid config `.cfx` with a Build task containing commission settings
- WHEN CfxReader reads it
- THEN typed models are returned with Options, WhatToBuild, RiskMoneyManagement, Data, Rankings, PartsToImprove, CrossChecks, Notes, Blocks, ATMs, Databanks, Resources, and optionally CommissionCosts populated

#### Scenario: CFX without commission reads cleanly

- GIVEN a CFX file without any commission XML elements
- WHEN CfxReader reads it
- THEN CommissionCosts is None
- AND all other sections populate normally
