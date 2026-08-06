# Delta for optimizer-automation

## ADDED Requirements

### Requirement: Chained Optimize Task (REQ-44)

The Optimizer MUST be invocable as a task within a multi-task Custom Project (REQ-22/REQ-23), chained after retest in ONE project load (REQ-27). Standalone `Optimizer.run` SHALL remain unchanged.

#### Scenario: Optimize as chained task

- GIVEN a multi-task project with Optimize after Retest
- WHEN the generator emits the project
- THEN the Optimize task XML carries parameter ranges and Walk-Forward settings
- AND SQX executes it chained in one load

#### Scenario: Standalone path preserved

- GIVEN Optimizer invoked standalone
- WHEN `run(config)` is called
- THEN behavior is identical to pre-change output
