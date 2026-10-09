# Delta for pipeline-orchestration

## ADDED Requirements

### Requirement: GuardianEvaluationStage Gate Contract

`GuardianEvaluationStage` MUST declare `requires: ["research_config", "data_providers"]` and `provides: ["guardian_state", "portfolio_state", "correction_events"]`. The stage SHALL raise `GuardianProviderError` if any required provider is missing. The stage SHALL publish `CorrectionEvent` objects to the `CorrectionBus` after evaluation.

#### Scenario: Stage contract validation

- GIVEN a pipeline with `GuardianEvaluationStage`
- WHEN the stage is registered
- THEN its `requires` include `data_providers`
- AND its `provides` include `correction_events`

#### Scenario: Missing providers fail at stage execution

- GIVEN `GuardianEvaluationStage` with incomplete provider set
- WHEN `execute()` is called
- THEN `GuardianProviderError` is raised
- AND no partial guardian state is produced

## MODIFIED Requirements

### Requirement: Built-in Abstract Stages

The system MUST provide 18 abstract Stage subclasses: ValidateStage, TranslateStage, DaemonStartStage, CampaignStage, ExportStage, ReadStage, ComputeStatsStage, KnowledgeStoreStage, ReportStage, CostInjectionStage, PortfolioStage, CompileStage, DeployStage, DemoStage, ArchiveStage, LiveOpsStage, GuardianEvaluationStage, and BuilderStage. Each SHALL declare requires/provides context keys for its I/O contract. `GuardianEvaluationStage` MUST run before `BuilderStage`; `BuilderStage` MUST require `portfolio_state` and `correction_events`.

| Stage | requires | provides |
|-------|----------|----------|
| ValidateStage | config.sqx_install_path, config.sqx_license | license_validated |
| TranslateStage | config.research_config_path | cfx_bytes |
| DaemonStartStage | config.sqx_install_path, config.sqx_port | daemon_url |
| CampaignStage | daemon_url, cfx_bytes | campaign_status |
| ExportStage | campaign_status | export_paths |
| ReadStage | export_paths | trades, equity, summary |
| ComputeStatsStage | trades, equity | statistics |
| KnowledgeStoreStage | statistics, export_paths, cfx_bytes | artifact_paths |
| ReportStage | statistics | report_data |
| CostInjectionStage | config.broker_profile | cost_config |
| PortfolioStage | daemon_url, portfolio_config | portfolio_status |
| CompileStage | cfx_bytes, jdk_path | jfx_path |
| DeployStage | jfx_path, deploy_target | deployment_status |
| DemoStage | deployment_status, demo_account_config | demo_status |
| ArchiveStage | demo_status, guardian_feedback | archive_status |
| LiveOpsStage | archive_status, maintenance_plan | live_ops_status |
| GuardianEvaluationStage | research_config, data_providers | guardian_state, portfolio_state, correction_events |
| BuilderStage | portfolio_state, correction_events, cfx_bytes | build_status |

(Previously: 16 abstract stages; BuilderStage only required research_config)

#### Scenario: Guardian-to-builder handshake

- GIVEN a pipeline with `GuardianEvaluationStage` followed by `BuilderStage`
- WHEN `GuardianEvaluationStage` completes
- THEN `BuilderStage` receives `portfolio_state` and `correction_events`
- AND the stage chain validates end-to-end

#### Scenario: Builder blocks on QUARANTINE

- GIVEN `portfolio_state` is `QUARANTINE`
- WHEN `BuilderStage.execute()` is invoked
- THEN the stage raises `PortfolioStateBlockedError`
- AND no CFX dispatch is attempted
