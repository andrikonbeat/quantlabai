# Result Reader Specification

## Purpose

Parses StrategyQuant Databank exports (CSV and XLSX formats) into structured Pydantic models. Supports reading individual trades, equity curves, and summary statistics from backtest results, decoupling analysis from SQX file formats.

## Requirements

### Requirement: CSV Trade Reading

The system MUST parse a Databank CSV file into a list of trade Pydantic models containing entry/exit time, direction, lots, profit, and drawdown fields.

#### Scenario: CSV with valid trade data parses correctly

- GIVEN a Databank CSV export containing 50 trades with all required columns
- WHEN the reader parses the file
- THEN a list of 50 trade Pydantic models is returned with all fields populated

#### Scenario: CSV with missing columns raises error

- GIVEN a CSV file missing required columns (e.g., no "Profit" column)
- WHEN the reader attempts to parse
- THEN a ParseError is raised identifying the missing column

### Requirement: XLSX Trade Reading

The system MUST parse a Databank XLSX export into the same trade models, with format-agnostic output.

#### Scenario: XLSX parses to identical model structure

- GIVEN a Databank XLSX export with the same data as a CSV
- WHEN the reader parses both
- THEN both produce identical Pydantic model structures (same fields, same values)

#### Scenario: Corrupted XLSX file raises error

- GIVEN a corrupted XLSX file (invalid ZIP structure)
- WHEN the reader attempts to parse
- THEN a ParseError is raised without crashing

### Requirement: Equity Curve Reading

The system MUST parse equity curve data from Databank CSVs/XLSX into a list of (timestamp, equity) points with consistent ordering.

#### Scenario: Equity curve with 1000+ points parses

- GIVEN a Databank export with 1500 equity curve data points
- WHEN the reader parses the equity curve
- THEN a list of 1500 ordered equity points is returned with valid timestamps

#### Scenario: Empty equity curve returns empty list

- GIVEN a Databank export with zero equity curve entries
- WHEN the reader parses it
- THEN an empty list is returned (not an error)

### Requirement: Summary Statistics Reading

The system MUST parse summary statistics from Databank exports into a flat Pydantic model with net profit, total trades, win rate, max drawdown, profit factor, and Sharpe ratio fields.

#### Scenario: Complete summary parses correctly

- GIVEN a Databank export with full summary statistics
- WHEN the reader parses the summary
- THEN a statistics model is returned with all numeric fields populated

#### Scenario: Missing statistics field defaults to None

- GIVEN a Databank export missing the Sharpe ratio field
- WHEN the reader parses the summary
- THEN the missing field is set to None rather than raising an error
