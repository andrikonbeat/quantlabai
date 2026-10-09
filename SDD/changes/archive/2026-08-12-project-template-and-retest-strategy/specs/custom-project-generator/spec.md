# Delta for Custom Project Generator

## ADDED Requirements

### Requirement: AutomaticRetest Dedicated Renderer (Traceability: `custom-project-generator`)

The system MUST provide a dedicated `AutomaticRetest` task renderer that produces task XML with AutomaticRetest-specific CrossChecks and parameters, distinct from generic Retest rendering. The renderer MUST be selected when a task declares `type=AutomaticRetest`.

**Acceptance Criteria:** AutomaticRetest tasks render dedicated XML; CrossChecks use AutomaticRetest-specific parameters; generic Retest rendering is unaffected.

#### Scenario: AutomaticRetest task renders dedicated XML

- GIVEN a CustomProject task with `type=AutomaticRetest`
- WHEN the generator renders the task
- THEN the task XML contains `<Task type="AutomaticRetest">`
- AND CrossChecks include AutomaticRetest-specific parameters
- AND no Retest-specific Monte Carlo or Walk-Forward sections are injected

#### Scenario: Generic Retest rendering is unchanged

- GIVEN a CustomProject task with `type=Retest`
- WHEN the generator renders the task
- THEN the task XML matches pre-change Retest structure
- AND Monte Carlo and Walk-Forward CrossChecks are present as before

### Requirement: Template-Aware Task XML Generation (Traceability: `custom-project-generator`)

The system MUST inject template-specific metadata into generated task XML when a project is generated from a named template. Each task XML MUST include `<Template name="{template_name}" profile="{profile}" />`. The generator MUST preserve all existing task attributes.

**Acceptance Criteria:** Generated CFX from a template includes metadata; non-template CFX does not; existing attributes preserved.

#### Scenario: Template metadata appears in generated tasks

- GIVEN a project generated from `standard_research`
- WHEN the archive is generated
- THEN every task XML contains `<Template name="standard_research" profile="standard_research" />`
- AND task type, name, and databank routing are unchanged

#### Scenario: Non-template project has no template metadata

- GIVEN a project generated from an ad-hoc CustomProject DSL model
- WHEN the archive is generated
- THEN no task XML contains a `<Template>` element
- AND output is structurally identical to pre-change generation
