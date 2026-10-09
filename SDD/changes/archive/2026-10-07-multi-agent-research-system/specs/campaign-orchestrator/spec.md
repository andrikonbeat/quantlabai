# Delta for Campaign Orchestrator

## MODIFIED Requirements

### Requirement: Campaign Lifecycle

The system MUST execute the full sequential campaign flow through the ResearchDirector's centralized pipeline instead of direct orchestration. CampaignOrchestrator becomes a single pipeline stage (`campaign_orchestrator_stage`) that wraps the existing translate→dispatch→poll→export→read→compute→store flow. The system SHALL integrate with ResearchDirector as higher-level orchestrator; CampaignOrchestrator becomes a stage.
(Previously: CampaignOrchestrator owned the full lifecycle directly)

#### Scenario: CampaignOrchestrator runs as pipeline stage
- GIVEN PipelineContext with research_config artifact from ResearchAgent
- WHEN campaign_orchestrator_stage executes
- THEN the full flow executes: translate → daemon start → loadconfig → run → poll → export → read → compute → store
- AND CampaignResult written to PipelineContext.artifacts["campaign_result"]
- AND progress callbacks fire via PipelineRunner stage hooks (not direct callbacks)

#### Scenario: Campaign fails at translation phase
- GIVEN a ResearchConfig that fails DSL-to-CFX translation
- WHEN campaign_orchestrator_stage executes
- THEN a CampaignError is raised at the translate phase
- AND PipelineRunner catches StageExecutionError, marks stage failed, skips subsequent stages
- AND no sqcli commands are dispatched

#### Scenario: Campaign times out during polling
- GIVEN a campaign that exceeds the configured poll timeout
- WHEN campaign_orchestrator_stage polls for status beyond the limit
- THEN a CampaignError with timeout detail is raised
- AND the sqcli project is stopped via `-project action=stop`
- AND PipelineResult captures the failure with stage_name="campaign_orchestrator"

### Requirement: Progress Callbacks

The system MUST fire progress callbacks via PipelineRunner's stage transition hooks instead of direct callback registration. The callback protocol SHALL be a callable accepting `(stage_name: str, status: StageStatus, detail: str | None)`.
(Previously: Direct callback per phase transition)

#### Scenario: All stages fire runner callbacks
- GIVEN a successful campaign run with PipelineRunner callback registered
- WHEN the pipeline executes all stages including campaign_orchestrator_stage
- THEN the runner callback fires for each stage transition
- AND campaign_orchestrator_stage fires internal phase callbacks mapped to stage sub-steps

#### Scenario: Error phase fires callback with error status
- GIVEN a campaign that fails at the export phase within campaign_orchestrator_stage
- WHEN the stage encounters the failure
- THEN the runner callback fires with stage_name="campaign_orchestrator", status=failed, detail containing error

### Requirement: Status Polling

The system MUST poll sqcli project status at a configurable interval (default 30s) until the project reaches a terminal state or the poll timeout is exceeded. Polling logic remains internal to the stage.
(Previously: Same behavior, now encapsulated in stage)

#### Scenario: Campaign completes within poll limit
- GIVEN a running campaign with 30s poll interval and 10min timeout
- WHEN the project completes after 3 polls
- THEN the stage detects the completed status and proceeds to export
- AND stage returns successfully with CampaignResult

#### Scenario: Poll timeout raises CampaignError
- GIVEN a running campaign with 30s poll interval and 2min timeout
- WHEN the project does not complete within 4 polls
- THEN a CampaignError with timeout detail is raised
- AND the project is stopped via `-project action=stop`
- AND PipelineRunner captures StageExecutionError

## ADDED Requirements

### Requirement: Pipeline Stage Contract

The system MUST declare requires/provides for the campaign_orchestrator_stage to integrate with PipelineRunner contract validation.

#### Scenario: Stage contract declared
- GIVEN campaign_orchestrator_stage
- WHEN inspecting its contract
- THEN requires = ["research_config", "gate_decision_HUMAN_REVIEW_OBJECTIVES"]
- AND provides = ["campaign_result", "export_paths", "campaign_id"]

---

## REMOVED Requirements

None — all existing behavior preserved, refactored into pipeline stage.

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| CampaignOrchestrator runs as pipeline stage | Integration: build pipeline with stage, assert execution |
| Progress callbacks via PipelineRunner | Unit test: mock runner callback, assert fired per stage |
| Stage contract validated by PipelineRunner | Unit test: missing requires → ContractValidationError |
| All original scenarios still pass | Regression test: full campaign via pipeline |