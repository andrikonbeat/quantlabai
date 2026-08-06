# Optimizer Automation Specification

## Purpose

Automates walk-forward optimization via StrategyQuant CLI (`sqcli`). Generates Optimizer CFX templates with parameter spaces, walk-forward settings, and databanks; executes optimization via sqcli; exports results to CSV/DataFrame.

## Requirements

### Requirement: Optimizer CFX Template Generation

The system MUST generate a valid Optimizer CFX XML from an `OptimizerConfig` specification.

#### Scenario: Generate CFX with parameter space

- GIVEN `OptimizerConfig` with parameter_ranges={"Period": [10, 50, 5], "Threshold": [0.1, 1.0, 0.1]}
- WHEN `OptimizerTemplateBuilder.build(config)` is called
- THEN CFX contains `<Optimization>` section with Parameters for Period and Threshold
- AND each parameter has Min, Max, Step attributes

#### Scenario: Generate CFX with walk-forward cycles

- GIVEN `OptimizerConfig(walkforward_cycles=5, walkforward_oot_ratio=0.3)`
- WHEN `build()` is called
- THEN CFX contains `<WalkForward>` section with Cycles=5 and OutOfSampleRatio=0.3

#### Scenario: Generate CFX with databanks

- GIVEN `OptimizerConfig(databanks=["EURUSD_H1", "GBPUSD_H1"])`
- WHEN `build()` is called
- THEN CFX contains `<Databanks>` section with both symbols

#### Scenario: Generate CFX with objective function

- GIVEN `OptimizerConfig(objective_function="NetProfit")`
- WHEN `build()` is called
- THEN CFX contains `<ObjectiveFunction>` set to NetProfit

### Requirement: OptimizerConfig Validation

The system MUST validate `OptimizerConfig` before CFX generation.

#### Scenario: Missing parameter_ranges raises ValidationError

- GIVEN `OptimizerConfig` with empty parameter_ranges
- WHEN `OptimizerConfig.model_validate(config)` is called
- THEN ValidationError is raised: "parameter_ranges must contain at least one parameter"

#### Scenario: Invalid walkforward_cycles raises ValidationError

- GIVEN `OptimizerConfig(walkforward_cycles=0)`
- WHEN validation runs
- THEN ValidationError: "walkforward_cycles must be >= 1"

#### Scenario: Valid config passes validation

- GIVEN complete config with all required fields
- WHEN validation runs
- THEN no error is raised

### Requirement: SQX CLI Lifecycle Management

The system MUST execute optimizer via sqcli with proper lifecycle: loadconfig → start → status polling → stop → export.

#### Scenario: Run optimizer completes full lifecycle

- GIVEN valid optimizer CFX at "/tmp/optimizer.cfx"
- WHEN `Optimizer.run(config)` is called
- THEN sqcli loadconfig is called with the CFX
- AND sqcli start is called
- AND status is polled until "completed"
- AND results are exported to CSV
- AND method returns path to results CSV

#### Scenario: Run optimizer handles timeout

- GIVEN optimization exceeds configured timeout (default 1 hour)
- WHEN `run()` is called
- THEN sqcli stop is sent
- AND OptimizationTimeoutError is raised with partial results path

#### Scenario: Run optimizer handles sqcli failure

- GIVEN sqcli returns exit code != 0
- WHEN `run()` is called
- THEN OptimizerExecutionError is raised with stderr

### Requirement: Results Export to CSV

The system MUST export optimization results to CSV with expected columns.

#### Scenario: Export produces CSV with required columns

- GIVEN optimization completed
- WHEN `Optimizer.export_results(output_path="/tmp/results.csv")` is called
- THEN CSV is created with columns: ParameterSet, NetProfit, SharpeRatio, MaxDrawdown, TradesCount, WalkForwardScore

#### Scenario: Export handles empty results

- GIVEN optimization completed but no valid parameter sets
- WHEN `export_results()` is called
- THEN CSV is created with header only (0 data rows)

### Requirement: Dry-Run Mode

The system MUST support dry-run for testing CFX generation without sqcli.

#### Scenario: Dry-run returns mock results

- GIVEN Optimizer with dry_run=True
- WHEN `run(config)` is called
- THEN no sqcli is invoked
- AND a mock CSV is created with sample parameter sets
- AND CFX file is generated at expected path for inspection

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