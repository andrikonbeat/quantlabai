# Delta for Pipeline Core

## MODIFIED Requirements

### Requirement: Built-in Abstract Stages

The system MUST provide 17 abstract Stage subclasses (extended from 9): ValidateStage, TranslateStage, DaemonStartStage, CampaignStage, ExportStage, ReadStage, ComputeStatsStage, KnowledgeStoreStage, ReportStage, ResearchStage, BuilderStage, StatisticsStage, ReviewStage, PortfolioStage, DeployStage, MonitorStage, GateInterceptorStage. Each SHALL declare requires/provides context keys for its I/O contract.
(Previously: 9 abstract stages for basic SQX flow)

#### Scenario: ResearchStage I/O contract
- GIVEN ResearchStage
- WHEN inspecting its contract
- THEN requires = []
- AND provides = ["research_config", "objectives", "hypotheses", "iteration_config", "gate_policies"]

#### Scenario: BuilderStage I/O contract
- GIVEN BuilderStage
- WHEN inspecting its contract
- THEN requires = ["research_config"]
- AND provides = ["cfx_bytes", "campaign_id", "sqcli_status", "export_paths"]

#### Scenario: StatisticsStage I/O contract
- GIVEN StatisticsStage
- WHEN inspecting its contract
- THEN requires = ["export_paths"]
- AND provides = ["statistics", "aggregate_stats", "monte_carlo_bands", "rolling_metrics", "regime_alerts"]

#### Scenario: ReviewStage I/O contract
- GIVEN ReviewStage
- WHEN inspecting its contract
- THEN requires = ["statistics", "aggregate_stats", "monte_carlo_bands"]
- AND provides = ["review_decision", "iteration_proposal", "wf_degradation", "mc_overfit_flag", "benchmark_comparison"]

#### Scenario: PortfolioStage I/O contract
- GIVEN PortfolioStage
- WHEN inspecting its contract
- THEN requires = ["selected_strategies", "review_decision"]
- AND provides = ["portfolio_cfx", "portfolio_result", "correlation_matrix", "risk_allocation", "wf_aggregate_stats"]

#### Scenario: DeployStage I/O contract
- GIVEN DeployStage
- WHEN inspecting its contract
- THEN requires = ["portfolio_cfx", "gate_decision_HUMAN_APPROVE_PORTFOLIO"]
- AND provides = ["jforex_package", "jcloud_config", "deployment_result"]

#### Scenario: MonitorStage I/O contract
- GIVEN MonitorStage
- WHEN inspecting its contract
- THEN requires = ["live_equity", "deployment_result"]
- AND provides = ["rolling_metrics", "regime_alerts", "performance_alerts", "gate_decision_HUMAN_REVIEW_PERFORMANCE"]

#### Scenario: GateInterceptorStage I/O contract
- GIVEN GateInterceptorStage
- WHEN inspecting its contract
- THEN requires = [gate_specific_artifacts]
- AND provides = ["gate_decision_{gate_id}"]
- AND gate_id parameterizes the stage

#### Scenario: Full 17-stage chain contract
- GIVEN all 17 stages in pipeline order
- WHEN each stage executes sequentially
- THEN each stage's requires are satisfied by previous stages' provides
- AND no stage depends on external state outside PipelineContext

## ADDED Requirements

### Requirement: Gate Interceptor Stage Type

The system MUST provide a GateInterceptorStage abstract class that implements the human gate protocol: pauses pipeline, invokes async callback, handles timeout/fallback, records decision to Engram.

#### Scenario: GateInterceptorStage pauses and resumes
- GIVEN GateInterceptorStage for HUMAN_REVIEW_OBJECTIVES
- WHEN executed with gate callback returning APPROVE after 2h
- THEN pipeline pauses at stage, callback invoked with GateContext
- AND on APPROVE, stage returns GateDecision.APPROVE, pipeline continues
- AND decision recorded to Engram

#### Scenario: GateInterceptorStage timeout fallback
- GIVEN GateInterceptorStage with timeout=24h, fallback=ESCALATE
- WHEN 24h elapses with no callback response
- THEN stage executes fallback (escalate), records timeout decision
- AND pipeline continues or aborts per fallback policy

### Requirement: Stage Contract Validation

The system MUST provide PipelineRunner.validate_contracts() that verifies all stages' requires are satisfied by prior stages' provides before execution.

#### Scenario: Contract validation catches missing key
- GIVEN pipeline where StatisticsStage requires "export_paths" but BuilderStage provides "cfx_bytes"
- WHEN PipelineRunner.validate_contracts() called
- THEN ContractValidationError raised listing missing "export_paths" and stage names

#### Scenario: Valid contracts pass validation
- GIVEN correctly wired 17-stage pipeline
- WHEN PipelineRunner.validate_contracts() called
- THEN validation passes, no errors

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| 17 abstract stages with correct requires/provides | Unit test: inspect each stage class attributes |
| GateInterceptorStage implements gate protocol | Integration: mock callback, assert pause/resume/fallback |
| Contract validation catches mismatches | Unit test: mismatched pipeline, assert error details |
| Original 9 stages still work (backward compat) | Regression test: basic SQX pipeline unchanged |