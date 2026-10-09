# Campaign Orchestrator Specification

## Purpose

End-to-end pipeline runner that orchestrates the full campaign lifecycle: translate DSL → dispatch sqcli → poll status → export results → read → compute stats → store artifacts. Sequential execution with progress callbacks.

## Requirements

### Requirement: Campaign Lifecycle

The system MUST execute the full sequential campaign flow: translate ResearchConfig to CFX, start sqcli daemon, load CFX into a project, run the project, poll for completion, export results, read exports, compute statistics, and store artifacts.

#### Scenario: Full campaign completes successfully

- GIVEN a valid ResearchConfig and a licensed SQX environment
- WHEN the orchestrator runs a campaign
- THEN the flow executes: translate → daemon start → loadconfig → run → poll → export → read → compute → store
- AND a CampaignResult with all phases marked complete is returned

#### Scenario: Campaign fails at translation phase

- GIVEN a ResearchConfig that fails DSL-to-CFX translation
- WHEN the orchestrator runs the campaign
- THEN a CampaignError is raised at the translate phase
- AND no sqcli commands are dispatched

#### Scenario: Campaign times out during polling

- GIVEN a campaign that exceeds the configured poll timeout
- WHEN the orchestrator polls for status beyond the limit
- THEN a CampaignError with timeout detail is raised
- AND the sqcli project is stopped via `-project action=stop`

### Requirement: Progress Callbacks

The system MUST fire a progress callback at each phase transition with the phase name, status, and optional detail. The callback protocol SHALL be a callable accepting `(phase: CampaignPhase, status: PhaseStatus, detail: str | None)`.

#### Scenario: All phases fire callbacks

- GIVEN a successful campaign run with a registered callback
- WHEN the orchestrator executes all phases
- THEN the callback fires 7 times: translate, daemon_start, load_config, run, poll, export, store

#### Scenario: Error phase fires callback with error status

- GIVEN a campaign that fails at the export phase
- WHEN the orchestrator encounters the failure
- THEN the callback fires with phase=export, status=error, and detail containing the error message

### Requirement: Status Polling

The system MUST poll sqcli project status at a configurable interval (default 30s) until the project reaches a terminal state (completed, failed, stopped) or the poll timeout is exceeded.

#### Scenario: Campaign completes within poll limit

- GIVEN a running campaign with 30s poll interval and 10min timeout
- WHEN the project completes after 3 polls
- THEN the orchestrator detects the completed status and proceeds to export

#### Scenario: Poll timeout raises CampaignError

- GIVEN a running campaign with 30s poll interval and 2min timeout
- WHEN the project does not complete within 4 polls
- THEN a CampaignError with timeout detail is raised
- AND the project is stopped via `-project action=stop`
