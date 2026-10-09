# Delta for Pipeline Core

## ADDED Requirements

### Requirement: CostInjectionStage

The system MUST provide CostInjectionStage as a built-in abstract Stage subclass. It SHALL read `config.broker_profile` from PipelineContext and write `cost_config` to artifacts.

#### Scenario: CostInjectionStage contract

- GIVEN CostInjectionStage
- WHEN inspecting requires/provides
- THEN requires includes "config.broker_profile"
- AND provides includes "cost_config"

#### Scenario: CostInjectionStage in full chain

- GIVEN CostInjectionStage inserted before TranslateStage
- WHEN the pipeline executes
- THEN downstream translation stages can read cost_config from artifacts

## MODIFIED Requirements

### Requirement: Built-in Abstract Stages

The system MUST provide 10 abstract Stage subclasses: ValidateStage, TranslateStage, DaemonStartStage, CampaignStage, ExportStage, ReadStage, ComputeStatsStage, KnowledgeStoreStage, ReportStage, and CostInjectionStage. Each SHALL declare requires/provides context keys for its I/O contract.
(Previously: 9 stages, no CostInjectionStage)

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
| **CostInjectionStage** | **config.broker_profile** | **cost_config** |

#### Scenario: Full stage chain contract

- GIVEN all 10 stages in pipeline order (CostInjectionStage before TranslateStage)
- WHEN each stage executes sequentially
- THEN each stage's requires are satisfied by previous stages' provides
- AND CostInjectionStage injects cost_config before translation needs it
