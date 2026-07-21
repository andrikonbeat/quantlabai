# Portfolio Master Specification

## Purpose

Automates StrategyQuant's Portfolio Master (genetic portfolio builder) via CFX template and `sqcli`. Generates genetic portfolio CFX from strategy list, runs optimization via sqcli, and extracts selected strategies from the result.

## Requirements

### Requirement: Portfolio Master CFX Generation

The system MUST generate a valid Portfolio Master CFX with genetic algorithm configuration.

#### Scenario: CFX contains AutomaticPortfolioBuilder section

- GIVEN `PortfolioMasterConfig(strategies=["s1", "s2", "s3"], generations=50, population=200)`
- WHEN `PortfolioMaster.build_cfx(config)` is called
- THEN CFX contains `<AutomaticPortfolioBuilder>` section with:
  - `Generations` = 50
  - `PopulationSize` = 200
  - `StrategyCount` = 3

#### Scenario: CFX includes PortfolioSettings

- GIVEN any valid config
- WHEN CFX is generated
- THEN `<PortfolioSettings>` section includes:
  - `FitnessFunction` (default: "NetProfit")
  - `MinStrategies` (default: 1)
  - `MaxStrategies` (default: strategy count)
  - `RebalancingPeriod` (default: "Monthly")

#### Scenario: CFX includes selected strategies

- GIVEN config with strategies=["s1", "s2", "s3"]
- WHEN CFX is generated
- THEN each strategy is referenced in `<Strategies>` subsection with correct ID

### Requirement: Run Portfolio Master via sqcli

The system MUST execute the portfolio master through sqcli and extract results.

#### Scenario: Run completes genetic search and exports selected strategies

- GIVEN valid portfolio master CFX
- WHEN `PortfolioMaster.run(config)` is called
- THEN sqcli loadconfig/start/status/stop lifecycle is executed
- AND results are exported
- AND method returns list of selected strategy IDs from the genetic run

#### Scenario: Run returns empty list if no strategies selected

- GIVEN genetic run completes but selects no strategies
- WHEN `run()` is called
- THEN empty list is returned (not an error)

#### Scenario: Run handles sqcli timeout

- GIVEN genetic search exceeds timeout
- WHEN `run()` is called
- THEN sqcli stop is sent
- AND PortfolioMasterTimeoutError is raised with partial results

### Requirement: Extract Selected Strategies from Results

The system MUST parse the sqcli export to identify which strategies were selected.

#### Scenario: Extract returns strategy IDs from portfolio result

- GIVEN sqcli exported portfolio result XML
- WHEN `PortfolioMaster.extract_selected_strategies(result_path)` is called
- THEN list of selected strategy IDs is returned in order of selection

#### Scenario: Extract handles missing result file

- GIVEN result path does not exist
- WHEN `extract_selected_strategies()` is called
- THEN PortfolioMasterResultError is raised

### Requirement: Dry-Run Mode

The system MUST support dry-run for CFX inspection without SQX.

#### Scenario: Dry-run generates CFX and returns mock selected strategies

- GIVEN PortfolioMaster with dry_run=True
- WHEN `run(config)` is called
- THEN CFX is generated at expected path
- AND mock selected strategies list is returned (first N strategies from input)
- AND no sqcli process is spawned