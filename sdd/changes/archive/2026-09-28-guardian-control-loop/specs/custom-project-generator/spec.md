# Delta for custom-project-generator

## ADDED Requirements

### Requirement: Adaptive Template Selection by PortfolioState (Issue 4)

The system MUST provide a `TemplateSelector` that chooses or mutates `CustomProject` tasks based on `PortfolioState`. The selector SHALL be deterministic: same `PortfolioState` and `CustomProject` input MUST produce identical output. Template mutations MUST be logged with the triggering `portfolio_state` and `correlation_id`.

#### Scenario: QUARANTINE skips Optimize

- GIVEN `PortfolioState.QUARANTINE`
- WHEN `TemplateSelector.select(project)` is called with a project containing Optimize
- THEN Optimize is removed or disabled
- AND `AutomaticRetest` is added for validation

#### Scenario: VIGILANCE adds monitoring

- GIVEN `PortfolioState.VIGILANCE`
- WHEN `TemplateSelector.select(project)` is called
- THEN `AutomaticRetest` is inserted after `Retest`
- AND the mutation is logged

#### Scenario: NORMAL uses default template

- GIVEN `PortfolioState.NORMAL`
- WHEN `TemplateSelector.select(project)` is called
- THEN the project task list is unchanged
- AND no mutations are logged

#### Scenario: Deterministic output

- GIVEN the same `PortfolioState.NORMAL` and identical `CustomProject` input
- WHEN `TemplateSelector.select(project)` is called twice
- THEN both outputs are byte-identical

## MODIFIED Requirements

### Requirement: DSL CustomProject Model (REQ-22)

The system MUST provide a `CustomProject` DSL model with an ORDERED task list; each task MUST carry `type`, `name`, `active`, per-task `source_databank`/`target_databank`, optional `filters`, and an optional `taskXMLFile` reference. A `GoToTask` task MUST support a `condition` referencing prior task output to form loops. Task order MUST be preserved exactly as declared. The model MUST also accept an optional `portfolio_state` context that `TemplateSelector` uses to mutate the task list before serialization.

#### Scenario: Ordered tasks round-trip with adaptive context

- GIVEN a CustomProject declaring tasks Build, Filtering, Retest, Optimize in that order with `portfolio_state=QUARANTINE`
- WHEN the model is serialized via `TemplateSelector`
- THEN task order in output matches the declaration
- AND Optimize is disabled while AutomaticRetest is appended
- AND every task retains type, name, databank source/target, and active flag

(Previously: Ordered tasks round-trip without portfolio-state adaptation)
