# Delta for Campaign Orchestrator

## ADDED Requirements

### Requirement: Internal Pipeline Composition

The system MUST compose a `Pipeline` from 9 built-in stages inside `run()`. The `PipelineResult` SHALL be mapped to `CampaignResult` preserving all existing fields (campaign_name, phase_results, cfx_path, cfx_bytes, campaign_status, export_paths, trades, equity, summary, statistics, artifact_paths, total_duration, error, is_successful).

#### Scenario: run() maps pipeline to campaign result

- GIVEN a valid CampaignConfig
- WHEN run() executes
- THEN internally a Pipeline is built from [ValidateStage, TranslateStage, DaemonStartStage, CampaignStage, ExportStage, ReadStage, ComputeStatsStage, KnowledgeStoreStage, ReportStage]
- AND the returned CampaignResult has the same structure as pre-refactor

#### Scenario: Dry-run bypasses pipeline

- GIVEN CampaignOrchestrator with dry_run=True
- WHEN run() is called
- THEN no Pipeline is executed
- AND all phases are simulated via dry-run path as before
- AND CampaignResult matches the pre-refactor format

## MODIFIED Requirements

### Requirement: Campaign Lifecycle

The system MUST execute the full sequential campaign flow: translate ResearchConfig to CFX, start sqcli daemon, load CFX into a project, run the project, poll for completion, export results, read exports, compute statistics, and store artifacts.
(Previously: phases executed inline via `_run_phase()` — now composed as Pipeline stages)

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
(Previously: fired from `_run_phase` — now fired from stage wrapper inside pipeline mapping)

#### Scenario: All phases fire callbacks

- GIVEN a successful campaign run with a registered callback
- WHEN the orchestrator executes all phases
- THEN the callback fires 11 times: validate, translate, daemon_start, load_config, run, poll, export, read, compute, store, complete

#### Scenario: Error phase fires callback with error status

- GIVEN a campaign that fails at the export phase
- WHEN the orchestrator encounters the failure
- THEN the callback fires with phase=export, status=error, and detail containing the error message
