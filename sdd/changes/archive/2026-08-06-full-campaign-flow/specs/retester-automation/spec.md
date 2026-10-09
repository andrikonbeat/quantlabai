# Delta for retester-automation

## ADDED Requirements

### Requirement: Chained Retest Task (REQ-43)

The Retester MUST be invocable as a task within a multi-task Custom Project (REQ-22/REQ-23), allowing retest to run chained with optimize in ONE project load (REQ-27). Standalone `RetesterAutomation` generation/execution SHALL remain unchanged.

#### Scenario: Retest as chained task

- GIVEN a multi-task project declaring Filtering → Retest → Optimize
- WHEN the generator emits the project
- THEN the Retest task XML carries its CrossChecks (Monte Carlo, Walk-Forward)
- AND SQX executes it chained in one load

#### Scenario: Standalone path preserved

- GIVEN RetesterAutomation invoked standalone
- WHEN `run(config, strategy_id, output_dir)` is called
- THEN behavior is identical to pre-change output
