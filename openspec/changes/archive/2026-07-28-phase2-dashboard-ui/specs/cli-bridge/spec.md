# Delta for CLI Bridge

## ADDED Requirements

### Requirement: Flask HTTP routes serve structured JSON from CLI bridge

The system MUST extend the CLI bridge with Flask HTTP routes that expose existing `sqcli` and SDK pipeline commands as structured JSON endpoints. The routes MUST delegate to existing bridge invocation logic without duplicating command construction.

#### Scenario: Campaign list endpoint delegates to sqcli
- GIVEN the dashboard API is running
- WHEN `GET /api/campaigns` is called
- THEN the bridge invokes the existing sqcli command for campaign listing
- AND the result is returned as structured JSON with exit_code, stdout, stderr, duration_ms
- AND the JSON is parsed and normalized into the campaign list format

#### Scenario: Pipeline run endpoint delegates to SDK pipeline
- GIVEN the dashboard API is running
- WHEN `GET /api/pipeline` is called
- THEN the bridge invokes the existing SDK pipeline listing interface
- AND the result is returned as structured JSON with run summaries

#### Scenario: Report generation endpoint delegates to ReportGenerator
- GIVEN the dashboard API is running
- WHEN `POST /api/reports/generate` is called with a campaign_id
- THEN the bridge invokes the existing `ReportGenerator` with the campaign data
- AND the `ReportResult` is returned as JSON including `to_json()` output

### Requirement: CLI bridge serves dashboard subcommand

The system MUST register a `quantlab dashboard` CLI subcommand with `start` and `stop` actions. `start` launches the Flask server; `stop` gracefully shuts it down.

#### Scenario: Dashboard start launches Flask server
- GIVEN `quantlab dashboard start` is invoked
- WHEN the command runs
- THEN the Flask app starts on the configured port (default 8080)
- AND the process runs in the foreground until interrupted

#### Scenario: Dashboard stop shuts down Flask server
- GIVEN the dashboard server is running
- WHEN `quantlab dashboard stop` is invoked
- THEN the Flask server gracefully shuts down
- AND no orphan processes remain
