# Delta for pipeline-orchestration

## ADDED Requirements

### Requirement: Portfolio Stage

The system MUST register `"portfolio"` as a valid stage type in `StageRegistry`, mapping to `PortfolioStage`. PortfolioStage SHALL require `daemon_url` and `portfolio_config`, and SHALL provide `portfolio_status`.

#### Scenario: Portfolio stage registered

- GIVEN StageRegistry
- WHEN looking up "portfolio"
- THEN PortfolioStage class is returned
- AND the stage is available for pipeline composition

#### Scenario: Portfolio stage executes

- GIVEN a pipeline with PortfolioStage after OptimizeStage
- WHEN the pipeline executes
- THEN PortfolioStage receives daemon_url and portfolio_config
- AND produces portfolio_status

### Requirement: Compile Stage

The system MUST register `"compile"` as a valid stage type in `StageRegistry`, mapping to `CompileStage`. CompileStage SHALL require `cfx_bytes` and `jdk_path`, and SHALL provide `jfx_path`. If `jdk_path` is absent, CompileStage SHALL raise `CompilerConfigError` before attempting compilation.

#### Scenario: Compile stage registered

- GIVEN StageRegistry
- WHEN looking up "compile"
- THEN CompileStage class is returned
- AND the stage is available for pipeline composition

#### Scenario: Missing JDK fails closed

- GIVEN a compile stage without jdk_path configured
- WHEN CompileStage.execute() is invoked
- THEN CompilerConfigError is raised
- AND no partial .jfx is produced

### Requirement: Deploy Stage

The system MUST register `"deploy"` as a valid stage type in `StageRegistry`, mapping to `DeployStage`. DeployStage SHALL require `jfx_path` and `deploy_target`, and SHALL provide `deployment_status`.

### Requirement: Demo Stage

The system MUST register `"demo"` as a valid stage type in `StageRegistry`, mapping to `DemoStage`. DemoStage SHALL require `deployment_status` and `demo_account_config`, and SHALL provide `demo_status`. DemoStage MUST enforce the 14-business-day demo window; expiry SHALL block advancement past HUMAN_APPROVE_DEMO.

### Requirement: Archive Stage

The system MUST register `"archive"` as a valid stage type in `StageRegistry`, mapping to `ArchiveStage`. ArchiveStage SHALL require `demo_status` and `guardian_feedback`, and SHALL provide `archive_status`. ArchiveStage MUST gate on HUMAN_APPROVE_ARCHIVE.

### Requirement: Live-Ops Stage

The system MUST register `"live_ops"` as a valid stage type in `StageRegistry`, mapping to `LiveOpsStage`. LiveOpsStage SHALL require `archive_status` and `maintenance_plan`, and SHALL provide `live_ops_status`.

## MODIFIED Requirements

### Requirement: Built-in Abstract Stages

The system MUST provide 16 abstract Stage subclasses: ValidateStage, TranslateStage, DaemonStartStage, CampaignStage, ExportStage, ReadStage, ComputeStatsStage, KnowledgeStoreStage, ReportStage, CostInjectionStage, PortfolioStage, CompileStage, DeployStage, DemoStage, ArchiveStage, and LiveOpsStage. Each SHALL declare requires/provides context keys for its I/O contract.
(Previously: 10 abstract stages)

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

#### Scenario: Full stage chain contract

- GIVEN all 16 stages in pipeline order
- WHEN each stage executes sequentially
- THEN each stage's requires are satisfied by previous stages' provides
- AND new stages integrate with existing artifact flow
