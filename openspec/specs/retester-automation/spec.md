# Retester Automation Specification

## Purpose

Automates StrategyQuant's Retester workflow via CFX template and `sqcli` with databank export. Configures Monte Carlo and Walk-Forward retesting, executes the retester, and exports Monte Carlo and Walk-Forward reports.

## Requirements

### Requirement: Retester Configuration Model

The system MUST provide a configuration class encapsulating all retester parameters including optional cost-related parameters.
(Previously: No cost parameters existed in RetesterConfig)

#### Scenario: RetesterConfig accepts all required parameters

- GIVEN `RetesterConfig(databanks=["EURUSD_H1", "GBPUSD_H1"], monte_carlo_runs=100, walkforward_cycles=5, confidence_level=0.95, min_trades=30)`
- WHEN the config is instantiated
- THEN all parameters are stored and validated
- AND `monte_carlo_runs` MUST be >= 10
- AND `walkforward_cycles` MUST be >= 1
- AND `confidence_level` MUST be in (0.5, 0.99]
- AND `databanks` MUST be non-empty list

#### Scenario: RetesterConfig uses sensible defaults

- GIVEN `RetesterConfig(databanks=["EURUSD_H1"])`
- WHEN instantiated with minimal args
- THEN defaults: monte_carlo_runs=100, walkforward_cycles=5, confidence_level=0.95, min_trades=30

#### Scenario: RetesterConfig with cost params

- GIVEN `RetesterConfig(strategy_id="s1", databanks=["EURUSD_H1"], broker_profile="ib")`
- WHEN instantiated
- THEN broker_profile is stored
- AND cost_config defaults to None

#### Scenario: RetesterConfig without cost params (backward compatible)

- GIVEN `RetesterConfig(strategy_id="s1", databanks=["EURUSD_H1"])`
- WHEN instantiated
- THEN broker_profile is None
- AND cost_config is None
- AND existing params (monte_carlo_runs, walkforward_cycles, etc.) are unchanged

### Requirement: Generate Retester CFX

The system MUST generate a CFX file configuring the Retester with Monte Carlo and Walk-Forward sections, optionally including commission/cost parameters when a broker profile is provided.

#### Scenario: CFX contains Rankings section with acceptance criteria

- GIVEN `RetesterConfig(monte_carlo_runs=100, walkforward_cycles=5)`
- WHEN `RetesterAutomation.generate_cfx(config, strategy_id="s1")` is called
- THEN CFX contains `Rankings` section with:
  - `MonteCarloRuns` = 100
  - `WalkForwardCycles` = 5
  - `AcceptanceCriteria` subsection with min_trades, confidence_level

#### Scenario: CFX includes CrossChecks section for Monte Carlo and Walk-Forward

- GIVEN any valid config
- WHEN CFX is generated
- THEN a `CrossChecks` section is included with:
  - `MonteCarlo` enabled with runs and confidence level
  - `WalkForward` enabled with cycles
  - `MonteCarloPercentile` = 95 (default)

#### Scenario: CFX includes Data section with databanks

- GIVEN databanks=["EURUSD_H1", "GBPUSD_H1"]
- WHEN CFX is generated
- THEN `Data` section lists both databanks with correct paths

#### Scenario: CFX with cost injection

- GIVEN `RetesterConfig(..., broker_profile="ib")`
- WHEN generating CFX
- THEN the CFX includes commission and spread settings matching the broker profile

#### Scenario: CFX without costs (backward compatible)

- GIVEN `RetesterConfig(..., broker_profile=None)`
- WHEN generating CFX
- THEN CFX has no commission/cost sections — identical to pre-change output

### Requirement: Run Retester via sqcli with Databank Export

The system MUST execute the retester through `sqcli`, exporting databanks and reports.

#### Scenario: Run retester completes full lifecycle with databank export

- GIVEN a valid retester CFX
- WHEN `RetesterAutomation.run(config, strategy_id="s1", output_dir="/tmp/out")` is called
- THEN sqcli daemon is started
- AND `loadconfig` loads the CFX
- AND `start` begins retesting
- AND `status` is polled until completion
- AND `export` saves Monte Carlo report, Walk-Forward report, and databank files
- AND daemon is stopped

#### Scenario: Export produces Monte Carlo report

- GIVEN retester completed with monte_carlo_runs=100
- WHEN results are exported
- THEN a Monte Carlo report file is created with percentile bands (5%, 25%, 50%, 75%, 95%)
- AND report format matches SQX GUI output

#### Scenario: Export produces Walk-Forward report

- GIVEN retester completed with walkforward_cycles=5
- WHEN results are exported
- THEN a Walk-Forward report is created with per-cycle metrics
- AND aggregate statistics (mean, std, worst) are included

### Requirement: Dry-Run Mode

The system MUST support dry-run mode for testing without SQX.

#### Scenario: Dry-run generates mock reports

- GIVEN RetesterAutomation with dry_run=True
- WHEN `run(config, "s1", "/tmp/out")` is called
- THEN no sqcli process is spawned
- AND mock Monte Carlo report is created at `/tmp/out/monte_carlo_report.html`
- AND mock Walk-Forward report is created at `/tmp/out/walkforward_report.html`
- AND mock databank exports are created