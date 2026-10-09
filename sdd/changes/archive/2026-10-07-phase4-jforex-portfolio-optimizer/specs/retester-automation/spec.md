# Retester Automation Specification

## Purpose

Automate SQX retesting with Monte Carlo analysis over the HTTP API: build a
retest CFX from a `RetesterConfig`, dispatch it, poll to completion, export the
HTML and CSV reports, and parse the CSV into a structured `RetestResult` with
normalised metric names.

## Requirements

### RET-REQ-01: Retester configuration

The system SHALL accept a `RetesterConfig` carrying the strategy ID, databanks,
Monte Carlo run count, and related settings used to build the retest CFX.

#### Scenario: Config drives CFX build

- GIVEN a configured `RetesterConfig` for a strategy
- WHEN `Retester.run()` builds the CFX
- THEN the generated CFX embeds the databanks and Monte Carlo settings

### RET-REQ-02: Run retest

The system SHALL run the retest end-to-end: build CFX, load config, start the
project, poll until complete (or timeout), export the HTML report and the CSV,
parse the CSV, and attach `html_path`, `csv_path`, and `strategy_id` to the
result. The temporary CFX SHALL be removed on exit.

#### Scenario: Successful run returns full result

- GIVEN a daemon that completes successfully
- WHEN `run(config, campaign_name, output_dir)` is called
- THEN a `RetestResult` is returned with parsed metrics and report paths set
- AND the temp CFX is removed

#### Scenario: Timeout raises

- GIVEN the project does not complete within the timeout
- WHEN polling exceeds the bound
- THEN `RetesterRunError` is raised ("Timeout after ...")

#### Scenario: Run failure wraps

- GIVEN an unexpected error during the run
- WHEN `run` fails
- THEN `RetesterRunError` is raised with the underlying message (re-raised unchanged if already typed)

### RET-REQ-03: CSV parsing with normalised metrics

The system SHALL parse the retest CSV into a metrics dict using canonical,
case-insensitive metric keys with documented aliases (e.g. `MC_MAX_DRAWDOWN` →
`MC_Drawdown`, `CI_LOWER_BOUND` → `CI_Lower`, `MC_NET_PROFIT` → `MC_NetProfit`),
and SHALL reject unreadable or metric-less files.

#### Scenario: Parse valid CSV with aliases

- GIVEN a retest CSV whose headers use alias spellings
- WHEN `parse_csv(path)` is called
- THEN a `RetestResult` with canonical metric keys is returned

#### Scenario: Missing file raises

- GIVEN a non-existent path
- WHEN `parse_csv` is called
- THEN `RetesterRunError` is raised ("CSV file not found")

#### Scenario: No parseable metrics raises

- GIVEN a file with no recognisable metric columns
- WHEN `parse_csv` is called
- THEN `RetesterRunError` is raised