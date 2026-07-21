# JForex Deploy Specification

## Purpose

Exports StrategyQuant strategies as JForex-compatible `.java` source files via HTTP `sourcecode/print` endpoint and deploys custom indicators to the JForex strategies directory.

## Requirements

### Requirement: Export Strategy as Java Source

The system MUST export a strategy by ID via SQX HTTP API `sourcecode/print` and save it as a valid `.java` file.

#### Scenario: Export strategy produces compilable Java file

- GIVEN SQX server running with strategy ID "strat-123"
- WHEN `JForexDeployer.export_strategy("strat-123", "/output/dir")` is called
- THEN HTTP GET `/sourcecode/print?id=strat-123` is called
- AND response is saved as `/output/dir/strat-123.java`
- AND the file contains valid JForex strategy structure (class extending Strategy, onStart/onTick/onBar methods)

#### Scenario: Export handles custom strategy name

- GIVEN strategy ID "strat-123" and custom name "MyStrategy"
- WHEN `export_strategy("strat-123", "/out", strategy_name="MyStrategy")` is called
- THEN output file is `/out/MyStrategy.java`
- AND class name in file matches "MyStrategy"

#### Scenario: Export creates output directory if missing

- GIVEN output directory does not exist
- WHEN `export_strategy("s1", "/new/dir")` is called
- THEN directory is created and file is written

### Requirement: Error Handling for HTTP Failures

The system MUST handle HTTP errors gracefully with typed exceptions.

#### Scenario: SQX server not running raises ConnectionError

- GIVEN no SQX server at configured host:port
- WHEN `export_strategy("s1", "/out")` is called
- THEN JForexConnectionError is raised with connection details

#### Scenario: Invalid strategy ID raises NotFoundError

- GIVEN SQX server responds 404 for strategy ID
- WHEN `export_strategy("invalid-id", "/out")` is called
- THEN JForexStrategyNotFoundError is raised with the strategy ID

#### Scenario: HTTP 500 raises ServerError

- GIVEN SQX server returns 500 for sourcecode/print
- WHEN `export_strategy("s1", "/out")` is called
- THEN JForexServerError is raised with status code and response body

### Requirement: Deploy Custom Indicators

The system MUST copy custom indicator files from SQX installation to JForex strategies directory.

#### Scenario: Deploy indicators copies all custom indicators

- GIVEN SQX installed at `/opt/SQX/` with custom indicators in `/opt/SQX/custom_indicators/JForex/`
- WHEN `JForexDeployer.deploy_indicators("/home/user/JForex/Strategies")` is called
- THEN all `.java` files from SQX custom_indicators/JForex/ are copied to target directory
- AND directory structure is preserved

#### Scenario: Deploy creates target directory

- GIVEN target JForex strategies directory does not exist
- WHEN `deploy_indicators("/new/path")` is called
- THEN directory is created and files are copied

#### Scenario: Deploy skips non-Java files

- GIVEN custom_indicators contains `.java`, `.txt`, `.md` files
- WHEN `deploy_indicators()` is called
- THEN only `.java` files are copied

### Requirement: Configuration via Settings

The system MUST be configurable for SQX server URL and JForex paths.

#### Scenario: Deployer uses configured SQX base URL

- GIVEN JForexDeployer configured with `sqx_base_url="http://localhost:8888"`
- WHEN `export_strategy("s1", "/out")` is called
- THEN HTTP request goes to `http://localhost:8888/sourcecode/print?id=s1`

#### Scenario: Deployer uses default paths when not configured

- GIVEN no config provided
- WHEN deployer is instantiated
- THEN SQX base URL defaults to `http://localhost:8888`
- AND SQX custom indicators path defaults to `assets/SQX_*/custom_indicators/JForex/`

### Requirement: Dry-Run Mode

The system MUST support dry-run mode for testing without SQX server.

#### Scenario: Dry-run creates mock Java file

- GIVEN JForexDeployer with dry_run=True
- WHEN `export_strategy("test-strat", "/tmp/out")` is called
- THEN no HTTP request is made
- AND a mock `.java` file is created at `/tmp/out/test-strat.java`
- AND file contains valid JForex boilerplate structure