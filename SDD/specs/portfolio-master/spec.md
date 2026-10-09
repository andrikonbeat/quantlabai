# Portfolio Master Specification

## Purpose

Run the SQX Portfolio Master genetic builder end-to-end: build a portfolio CFX
from selected strategies, dispatch it through sqcli, poll to completion, and
extract the selected strategies with their allocated weights.

## Requirements

### PMA-REQ-01: Selected strategy model

The system SHALL represent a genetic-builder selection as `SelectedStrategy`
(strategy_id, weight, rank by descending weight, optional fitness) and a run
result as `PortfolioMasterResult` (strategies sorted by rank, total_count,
source format "csv"/"xml").

#### Scenario: Build a result object

- GIVEN parsed strategies from a builder export
- WHEN a `PortfolioMasterResult` is constructed
- THEN strategies are ordered by rank (1 = highest weight) and `total_count` matches

### PMA-REQ-02: Build portfolio run

The system SHALL build a portfolio CFX from strategy IDs, load and start the
project via sqcli, poll until completion (or fail), export the results, and
return the extracted selections. Empty strategy input SHALL be rejected.

#### Scenario: Empty strategy list raises

- GIVEN an empty strategies list
- WHEN `build_portfolio([])` is called
- THEN `PortfolioMasterError` is raised ("At least one strategy ID is required")

#### Scenario: Successful build returns selections

- GIVEN strategy IDs and a daemon that completes successfully
- WHEN `build_portfolio(ids, campaigns, generations, population)` is called
- THEN a `PortfolioMasterResult` with extracted strategies is returned
- AND the temporary CFX file is removed on exit

#### Scenario: Failed campaign raises

- GIVEN the project reaches a failed status
- WHEN polling completes
- THEN `PortfolioMasterError` is raised with the campaign error message

#### Scenario: Timeout raises

- GIVEN the project does not finish within the timeout
- WHEN polling exceeds the bound
- THEN `PortfolioMasterError` is raised ("Timeout waiting for ...")

#### Scenario: Export failure raises

- GIVEN the export step fails
- WHEN `build_portfolio` reaches export
- THEN `PortfolioMasterError` is raised

### PMA-REQ-03: Extract selections from results

The system SHALL parse Portfolio Master export results in XML or CSV format
(auto-detected, XML preferred on ambiguity), resolving strategy/weight/rank/
fitness columns case-insensitively through documented aliases.

#### Scenario: Parse simple CSV

- GIVEN a CSV export with strategy/weight columns using known aliases
- WHEN `_extract_selected_strategies` is called
- THEN a `PortfolioMasterResult` with `source_format="csv"` is returned

#### Scenario: Parse simple XML

- GIVEN an XML export
- WHEN `_extract_selected_strategies` is called
- THEN a `PortfolioMasterResult` with `source_format="xml"` is returned

#### Scenario: Empty export raises

- GIVEN an empty result payload
- WHEN extraction is attempted
- THEN `PortfolioMasterError` is raised

#### Scenario: Invalid header raises

- GIVEN a CSV with a non-numeric weight value or missing strategy column
- WHEN extraction is attempted
- THEN `PortfolioMasterError` is raised

#### Scenario: Mixed formats resolve safely

- GIVEN payload content that looks like both CSV and XML
- WHEN extraction is attempted
- THEN the XML interpretation is used first