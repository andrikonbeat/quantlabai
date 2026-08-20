# Custom Project Generator Specification

## Purpose

Generates StrategyQuant X (SQX) multi-task Custom Project `.cfx` archives from a DSL `CustomProject` model: ordered tasks, per-task databank source/target, filters, and GoToTask conditional loops. Validated against the verified SQX 144/2953 sample projects (`assets/SQX_144_2953_linux_20260601/`) as goldens. Data scope is Dukascopy-only (D5).

## Requirements

### Requirement: DSL CustomProject Model (REQ-22)

The system MUST provide a `CustomProject` DSL model with an ORDERED task list; each task MUST carry `type`, `name`, `active`, per-task `source_databank`/`target_databank`, optional `filters`, and an optional `taskXMLFile` reference. A `GoToTask` task MUST support a `condition` referencing prior task output to form loops. Task order MUST be preserved exactly as declared.

#### Scenario: Ordered tasks round-trip

- GIVEN a CustomProject declaring tasks Build, Filtering, Retest, Optimize in that order
- WHEN the model is serialized
- THEN task order in output matches the declaration exactly
- AND every task retains type, name, databank source/target, and active flag

#### Scenario: GoToTask conditional loop

- GIVEN a CustomProject with Filtering → Retest → GoToTask(Filtering) with condition `retest_failed`
- WHEN serialized
- THEN GoToTask references the earlier task by name
- AND its condition is preserved in the task XML

#### Scenario: Per-task databank routing

- GIVEN tasks with distinct source_databank/target_databank pairs
- WHEN serialized
- THEN each task XML references only its own databanks
- AND no databank is shared implicitly across tasks

### Requirement: Multi-Task CFX Generator (REQ-23)

The system MUST generate a `.cfx` ZIP archive containing `config.xml` plus one XML file per non-trivial task, routed from `<Task ... taskXMLFile="...">` entries, with `<Project name= version=>` root and `<Databanks><Databank name= view= syncType= position=>` section. Schema version MUST be `144.2953`. Single-task projects MUST produce output structurally identical to the existing generator.

#### Scenario: ZIP matches verified format

- GIVEN a 4-task CustomProject
- WHEN `generate_cfx_archive(project)` runs
- THEN the output is a ZIP containing config.xml
- AND one task XML file per task
- AND each `<Task taskXMLFile=...>` attribute matches the packaged file name
- AND `<Databanks>` lists every declared databank

#### Scenario: Single-task backward compatibility

- GIVEN a CustomProject with one Build task
- WHEN the archive is generated
- THEN output is structurally identical to the current single-task CFX
- AND existing consumers accept it unchanged

### Requirement: Golden Validation Against SQX Samples (REQ-24)

The generator MUST validate generated archives against the verified SQX 144/2953 format (`schema_version "144.2953"`), using `assets/SQX_144_2953_linux_20260601/` sample projects as goldens. Validation MUST reject archives whose structure deviates from the golden format. A readiness probe via `sqcli -h` SHALL run before validation.

#### Scenario: Generated CFX accepted by real SQX

- GIVEN a generated multi-task archive
- WHEN `sqcli -project action=loadconfig` loads it
- THEN sqcli accepts the archive without schema errors
- AND taskXMLFile routing resolves for every task

#### Scenario: Deviation fails closed

- GIVEN a generated archive with a malformed Tasks section
- WHEN golden validation runs
- THEN a ValidationError is raised naming the deviating element
- AND no dispatch is attempted

### Requirement: Task Catalog Coverage (REQ-25)

The generator SHALL support the verified 21-task catalog (Build, Retest, Optimize, AutomaticRetest, AutomaticPortfolioBuilder, Filtering, GoToTask, LoadFromFiles, SaveToFiles, ClearDatabanks, CreatePortfolio, CustomAnalysis, DeleteFile, CallExternalScript, LogDatabankStats, NeuralNetworkTrainer, Notification, StopAndStart, UpdateData, WaitFor, ApplyMassConfig). Walk-Forward SHALL be expressed inside Retest/Optimize `CrossChecks`, not as a standalone task. Unsupported task types MUST raise a clear error.

#### Scenario: All catalog tasks supported

- GIVEN any task type from the 21-task catalog
- WHEN the generator renders it
- THEN a task XML is produced with the correct taskXMLFile
- AND Walk-Forward settings render inside Retest/Optimize CrossChecks

#### Scenario: Unknown task type rejected

- GIVEN a task type outside the catalog
- WHEN the generator renders it
- THEN a TaskNotSupportedError is raised naming the type

## ADDED Requirements

### Requirement: Pipeline Builder Integration (G2)

The builder stage MUST render a `CustomProject` via `customproject/generator.py:45` (multi-task `.cfx`: `config.xml` + per-task XML, schema `144.2953`) when the `QUANTLAB_CUSTOM_PROJECT` flag is enabled, and MUST register a `custom_project` stage in `StageRegistry` (pipeline/registry.py). The flag MUST default to the legacy path until golden tests (`tests/customproject/`, `tests/cfx/`) are deliberately re-based; then it SHALL flip to CustomProject as the flow default. No silent breakage MAY occur.

#### Scenario: Flag on renders CustomProject

- GIVEN `QUANTLAB_CUSTOM_PROJECT=1` and re-based goldens
- WHEN the builder stage runs
- THEN the archive contains `config.xml` and per-task XML files
- AND the schema version is 144.2953

#### Scenario: Flag off keeps legacy output

- GIVEN the legacy default (or `QUANTLAB_CUSTOM_PROJECT=0`)
- WHEN the builder stage runs
- THEN the single-task dialect output is unchanged
- AND existing golden tests still pass byte-identically

### Requirement: CustomProject Stage Registration (G2)

`custom_project` MUST be a registered stage type in `StageRegistry` before the flag flips, so `build_pipeline` can instantiate it.

#### Scenario: Stage lookup succeeds

- GIVEN the updated registry
- WHEN `StageRegistry.lookup("custom_project")` is called
- THEN the CustomProject stage class is returned
