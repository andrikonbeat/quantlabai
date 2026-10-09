# Project Template Engine Specification

## Purpose

Generates pre-configured CustomProject CFX archives from named templates with consistent task ordering and databank routing.

## Requirements

### Requirement: Template Registry and Resolution (Traceability: `project-template-engine`)

The system MUST maintain a registry of named templates (`standard_research`, `quick_validation`, `deep_robustness`). Each template MUST declare a unique name, ordered task list, per-task databank routing, and CrossChecks preset. Resolution MUST be case-insensitive. Duplicate names MUST raise DuplicateTemplateError.

**Acceptance Criteria:** All three templates resolve; duplicate registration fails; case-insensitive lookup works.

#### Scenario: Registry loads all three templates

- GIVEN the Template Engine initializes
- WHEN the registry loads built-in templates
- THEN `standard_research`, `quick_validation`, and `deep_robustness` are registered
- AND each exposes its task list and databank routing

#### Scenario: Duplicate template name is rejected

- GIVEN `standard_research` is already registered
- WHEN a second registration with the same name is attempted
- THEN DuplicateTemplateError is raised
- AND the original template remains unchanged

### Requirement: Template Serialization to CFX (Traceability: `project-template-engine`)

The system MUST serialize a named template into a multi-task `.cfx` ZIP using the existing CustomProject DSL and CfxPatcher. Archives MUST include `config.xml`, one task XML per non-trivial task, and a `<Databanks>` section. Schema version MUST be `144.2953`. Serialization MUST NOT mutate the template definition.

**Acceptance Criteria:** Generated CFX passes golden validation; archive contains one XML per task; schema version is 144.2953; template unchanged after serialization.

#### Scenario: standard_research generates valid CFX

- GIVEN `standard_research` template is selected
- WHEN `serialize_template(template_name, output_path)` runs
- THEN a `.cfx` ZIP is written
- AND `sqcli -project action=loadconfig` accepts it without schema errors

#### Scenario: deep_robustness preserves databank routing

- GIVEN `deep_robustness` declares EURUSD_H1 and GBPUSD_H1
- WHEN serialized
- THEN `<Databanks>` lists both databanks
- AND each task XML references only its own databanks

### Requirement: Template Validation Against SQX Goldens (Traceability: `project-template-engine`)

The system MUST validate generated archives against verified SQX 144/2953 sample projects. Validation MUST run before returning the archive. A `sqcli -h` readiness probe SHALL execute before validation.

**Acceptance Criteria:** Validation catches structural deviations; readiness probe failure aborts validation; all three templates pass.

#### Scenario: Validation catches missing task XML

- GIVEN a template archive missing one task XML
- WHEN validation runs
- THEN ValidationError names the missing task
- AND no archive is returned

#### Scenario: sqcli unavailability aborts validation

- GIVEN `sqcli` is not in PATH or `SQCLI_PATH`
- WHEN validation is triggered
- THEN EnvironmentError indicates sqcli is unavailable
- AND no validation is attempted
