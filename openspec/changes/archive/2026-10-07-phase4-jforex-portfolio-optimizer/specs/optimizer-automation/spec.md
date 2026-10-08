# Optimizer Automation Specification

## Purpose

Automate SQX walk-forward optimization over the HTTP API: build an optimizer CFX
from an `OptimizerConfig`, dispatch it through sqcli, poll to completion, export
the optimization CSV, and parse it into a structured result.

## Requirements

### OPT-REQ-01: Optimizer configuration

The system SHALL accept an `OptimizerConfig` carrying the strategy ID,
optimization method, objective, and related tuning knobs used to build the
optimizer CFX.

#### Scenario: Config drives CFX build

- GIVEN a configured `OptimizerConfig` for a strategy
- WHEN `Optimizer.run()` builds the CFX
- THEN the generated CFX embeds the configured method and objective

### OPT-REQ-02: Run optimization

The system SHALL run the optimizer end-to-end: build CFX, load config, start the
project, poll until complete (or timeout), export the optimization results CSV,
and parse it. The temporary CFX SHALL be removed on exit.

#### Scenario: Successful run returns parsed result

- GIVEN a daemon that completes successfully
- WHEN `run(config, campaign_name, output_dir)` is called
- THEN a parsed optimization result is returned and the temp CFX is removed

#### Scenario: Timeout raises

- GIVEN the project does not complete within the timeout
- WHEN polling exceeds the bound
- THEN `OptimizerRunError` is raised ("Timeout after ...")

#### Scenario: Export failure raises

- GIVEN the export step fails
- WHEN `run` reaches export
- THEN `OptimizerRunError` is raised

### OPT-REQ-03: CSV parsing contract

The system SHALL parse the optimization CSV requiring the fixed columns
`cycle`, `insamplestart`, `insampleend`, `outsamplestart`, `outsampleend`
(case-insensitive headers), and SHALL reject missing, empty, or malformed files.

#### Scenario: Parse valid export

- GIVEN a CSV with all five required column headers and data rows
- WHEN `parse_csv(path, strategy_id)` is called
- THEN a structured result with the cycle rows is returned

#### Scenario: Missing file raises

- GIVEN a non-existent path
- WHEN `parse_csv` is called
- THEN `OptimizerRunError` is raised ("CSV file not found")

#### Scenario: Empty file raises

- GIVEN an empty file or header-only file
- WHEN `parse_csv` is called
- THEN `OptimizerRunError` is raised ("no header row" / "no data rows")

#### Scenario: Missing required columns raises

- GIVEN a header lacking one of the five fixed columns
- WHEN `parse_csv` is called
- THEN `OptimizerRunError` is raised naming the missing columns