# Delta Specs — guardian-control-loop

## Domains

| Domain | Type | Requirements | Scenarios |
|--------|------|--------------|-----------|
| correction-bus | New | 2 | 5 |
| meta-guardian | Delta | 3 (2 added, 1 modified) | 7 |
| pipeline-orchestration | Delta | 2 (1 added, 1 modified) | 4 |
| custom-project-generator | Delta | 2 (1 added, 1 modified) | 5 |
| guardian-feedback | Delta | 2 (1 modified, 1 added) | 5 |
| knowledge-store | Delta | 2 (1 added, 1 modified) | 6 |
| cfx-editor | Delta | 2 (1 added, 1 modified) | 4 |

Total: 14 requirements, 36 scenarios.

---

# Delta for correction-bus

## ADDED Requirements

### Requirement: CorrectionBus Event Channel

The system MUST provide a lightweight in-process `CorrectionBus` that publishes `CorrectionEvent` objects from `GuardianEvaluationStage` and delivers them to `BuilderStage` before CFX generation. The bus SHALL be unidirectional: guardian → builder. No cyclic dependencies are permitted. Events MUST be typed, serializable, and observable.

#### Scenario: Risk delta reaches builder

- GIVEN `MetaGuardianOrchestrator` evaluates and produces a risk delta
- WHEN `GuardianEvaluationStage` publishes a `CorrectionEvent` on the bus
- THEN `BuilderStage` receives the event
- AND adjusts CFX `risk_money_mgmt` parameters before dispatch

#### Scenario: State transition blocks builder

- GIVEN portfolio transitions to `QUARANTINE`
- WHEN `GuardianEvaluationStage` publishes a state-transition event
- THEN `BuilderStage` blocks dispatch
- AND the pipeline halts until human override

#### Scenario: Bus decouples stages

- GIVEN `GuardianEvaluationStage` and `BuilderStage` are in the same pipeline
- WHEN an event is published
- THEN the stages remain decoupled via the bus interface
- AND no direct import cycles exist between guardian and builder modules

## ADDED Requirements

### Requirement: CorrectionEvent Schema

`CorrectionEvent` MUST be a typed dataclass with fields: `event_id` (UUID), `timestamp` (datetime UTC), `source` (str), `event_type` (Literal["risk_delta", "state_transition", "capital_adjustment"]), `payload` (dict[str, Any]), and `correlation_id` (str | None). The system SHALL validate events at publish time; invalid events MUST raise `CorrectionBusError`.

#### Scenario: Valid event accepted

- GIVEN a well-formed `CorrectionEvent`
- WHEN `CorrectionBus.publish(event)` is called
- THEN the event is queued
- AND subscribers receive it within one pipeline tick

#### Scenario: Invalid event rejected

- GIVEN a `CorrectionEvent` with an unknown `event_type`
- WHEN `CorrectionBus.publish(event)` is called
- THEN `CorrectionBusError` is raised
- AND no subscribers receive the event

---

# Delta for meta-guardian

## ADDED Requirements

### Requirement: Hard-Fail on Missing Providers (Issue 1)

`MetaGuardianOrchestrator` MUST require concrete data providers for all guardian modules at construction time. If any provider is `None` or absent, the constructor MUST raise `GuardianProviderError`. The system SHALL NOT fall back to `_NullDataProvider` or any silent pass-through. This requirement applies to `RiskGuardian`, `PortfolioGuardian`, `CapitalGuardian`, `QualityGuardian`, and `ExecutionGuardian`.

#### Scenario: Missing provider fails closed

- GIVEN a `MetaGuardianOrchestrator` instantiation with `RiskGuardian` provider set to `None`
- WHEN the constructor runs
- THEN `GuardianProviderError` is raised
- AND no guardian instance is created

#### Scenario: All providers present succeeds

- GIVEN concrete providers for all 5 guardian modules
- WHEN `MetaGuardianOrchestrator` is constructed
- THEN initialization completes
- AND each guardian receives its provider

#### Scenario: _NullDataProvider removed

- GIVEN the legacy `_NullDataProvider` class
- WHEN the module is imported
- THEN it is no longer available or raises `DeprecationError`
- AND all call sites in `_build_guardians` use concrete providers

## MODIFIED Requirements

### Requirement: State Machine Enforcement (Issue 3)

The `PortfolioState` state machine MUST enforce pipeline gating after `GuardianEvaluationStage`. `BuilderStage` MUST block when `portfolio_state` is `QUARANTINE` or `DEFENSIVE` unless an explicit human override is granted via the existing `HUMAN_APPROVE_DEPLOY` gate. The orchestrator MUST NOT silently proceed to builder execution in blocked states.

#### Scenario: QUARANTINE blocks builder

- GIVEN `portfolio_state` is `QUARANTINE`
- WHEN `GuardianEvaluationStage` completes
- THEN `BuilderStage` does not execute
- AND the pipeline waits for `HUMAN_APPROVE_DEPLOY`

#### Scenario: DEFENSIVE blocks builder

- GIVEN `portfolio_state` is `DEFENSIVE`
- WHEN the pipeline reaches `BuilderStage`
- THEN dispatch is blocked
- AND a CorrectionBus event is emitted

#### Scenario: NORMAL permits builder

- GIVEN `portfolio_state` is `NORMAL`
- WHEN `GuardianEvaluationStage` completes
- THEN `BuilderStage` executes normally

#### Scenario: Human override unblocks

- GIVEN `portfolio_state` is `QUARANTINE`
- WHEN human approves via `HUMAN_APPROVE_DEPLOY`
- THEN `BuilderStage` proceeds
- AND the override is recorded in the audit log

(Previously: state machine had no enforcement hooks; `_execute_state_transition` only logged and called hooks)

## ADDED Requirements

### Requirement: Guardian Metrics Persistence (Issue 6)

`MetaGuardianOrchestrator` MUST persist guardian evaluation metrics per campaign run: timestamped scores per guardian, portfolio state transitions, and risk metrics. The system SHALL write to `knowledge/guardian-feedback/{campaign_id}/metrics.jsonl` and expose a read API via `GuardianMetricsStore`.

#### Scenario: Metrics written per evaluation

- GIVEN a campaign run with id `camp_001`
- WHEN `MetaGuardianOrchestrator.evaluate()` completes
- THEN `knowledge/guardian-feedback/camp_001/metrics.jsonl` contains one JSON line per guardian score
- AND each line includes `timestamp`, `guardian_name`, `score`, `portfolio_state`, and `risk_metrics`

#### Scenario: Read API returns history

- GIVEN persisted metrics for campaigns `camp_001` and `camp_002`
- WHEN `GuardianMetricsStore.query(campaign_id="camp_001")` is called
- THEN a list of `GuardianMetricRecord` objects is returned
- AND records are ordered by timestamp ascending

---

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

---

# Delta for custom-project-generator

## ADDED Requirements

### Requirement: Adaptive Template Selection by PortfolioState (Issue 4)

The system MUST provide a `TemplateSelector` that chooses or mutates `CustomProject` tasks based on `PortfolioState`. The selector SHALL be deterministic: same `PortfolioState` and `CustomProject` input MUST produce identical output. Template mutations MUST be logged with the triggering `portfolio_state` and `correlation_id`.

#### Scenario: QUARANTINE skips Optimize

- GIVEN `PortfolioState.QUARANTINE`
- WHEN `TemplateSelector.select(project)` is called with a project containing Optimize
- THEN Optimize is removed or disabled
- AND `AutomaticRetest` is added for validation

#### Scenario: VIGILANCE adds monitoring

- GIVEN `PortfolioState.VIGILANCE`
- WHEN `TemplateSelector.select(project)` is called
- THEN `AutomaticRetest` is inserted after `Retest`
- AND the mutation is logged

#### Scenario: NORMAL uses default template

- GIVEN `PortfolioState.NORMAL`
- WHEN `TemplateSelector.select(project)` is called
- THEN the project task list is unchanged
- AND no mutations are logged

#### Scenario: Deterministic output

- GIVEN the same `PortfolioState.NORMAL` and identical `CustomProject` input
- WHEN `TemplateSelector.select(project)` is called twice
- THEN both outputs are byte-identical

## MODIFIED Requirements

### Requirement: DSL CustomProject Model (REQ-22)

The system MUST provide a `CustomProject` DSL model with an ORDERED task list; each task MUST carry `type`, `name`, `active`, per-task `source_databank`/`target_databank`, optional `filters`, and an optional `taskXMLFile` reference. A `GoToTask` task MUST support a `condition` referencing prior task output to form loops. Task order MUST be preserved exactly as declared. The model MUST also accept an optional `portfolio_state` context that `TemplateSelector` uses to mutate the task list before serialization.

#### Scenario: Ordered tasks round-trip with adaptive context

- GIVEN a CustomProject declaring tasks Build, Filtering, Retest, Optimize in that order with `portfolio_state=QUARANTINE`
- WHEN the model is serialized via `TemplateSelector`
- THEN task order in output matches the declaration
- AND Optimize is disabled while AutomaticRetest is appended
- AND every task retains type, name, databank source/target, and active flag

(Previously: Ordered tasks round-trip without portfolio-state adaptation)

---

# Delta for guardian-feedback

## MODIFIED Requirements

### Requirement: Live Feedback into Generation (REQ-34)

The system MUST feed MetaGuardian live evaluations (degradation, drawdown, regime, cost, parameter matrix delta) into the generation flow: the feedback SHALL inform reconfiguration decisions and next-cycle research inputs, and SHALL be persisted as a feedback record per campaign. Feedback MUST NOT alter the 14-phase flow order (REQ-37) or bypass human gates. The system MUST also stream live demo-account equity/positions/costs to MetaGuardian for real-time state transitions. Feedback persistence MUST use a structured schema (`GuardianMetricRecord`) written to `knowledge/guardian-feedback/{campaign_id}/metrics.jsonl`; a `GuardianMetricsStore` read API MUST expose query-by-campaign and query-by-state-range capabilities.

#### Scenario: Live degradation feeds next cycle

- GIVEN MetaGuardian reports a strategy DEGRADING during the demo window
- WHEN the campaign archives
- THEN the feedback record is attached to the campaign archive
- AND next-cycle generation receives the degradation signal as input
- AND a `GuardianMetricRecord` is appended to `metrics.jsonl`

#### Scenario: Feedback never bypasses gates

- GIVEN live drawdown data arriving
- WHEN the generation flow consumes it
- THEN all human gates remain in force
- AND flow phase order is unchanged

#### Scenario: Metrics persist for next-cycle work

- GIVEN a completed campaign run
- WHEN `GuardianMetricsStore.query(campaign_id=...)` is called
- THEN all guardian scores, state transitions, and risk metrics are returned
- AND the data is available for next-cycle research

(Previously: feedback persisted as a feedback record per campaign; no structured schema or read API)

## ADDED Requirements

### Requirement: Guardian Feedback Schema

`GuardianMetricRecord` MUST be a typed Pydantic model with fields: `record_id` (UUID), `campaign_id` (str), `timestamp` (datetime UTC), `guardian_name` (str), `score` (float | None), `portfolio_state` (PortfolioState), `risk_metrics` (dict[str, Any] | None), `correlation_id` (str | None), and `source` (Literal["evaluation", "live_stream", "manual"]). The system SHALL validate records before writing; invalid records MUST raise `GuardianFeedbackError`.

#### Scenario: Valid record written

- GIVEN a well-formed `GuardianMetricRecord`
- WHEN `GuardianFeedbackStore.write(record)` is called
- THEN the record is appended to `metrics.jsonl`
- AND the write is atomic

#### Scenario: Invalid record rejected

- GIVEN a `GuardianMetricRecord` with an out-of-range `score`
- WHEN `GuardianFeedbackStore.write(record)` is called
- THEN `GuardianFeedbackError` is raised
- AND no partial write occurs

---

# Delta for knowledge-store

## ADDED Requirements

### Requirement: Guardian Metrics Query API (Issue 6)

`TimeSeriesStore` MUST expose a guardian-facing query API: `query_guardian_metrics(campaign_id, guardian_name=None, start=None, end=None)` returning `list[GuardianMetricRecord]`. The system SHALL index records by `campaign_id` and `timestamp` for efficient range queries. The API MUST be read-only; writes SHALL flow exclusively through `GuardianFeedbackStore`.

#### Scenario: Query by campaign returns all metrics

- GIVEN persisted metrics for campaigns `camp_001` and `camp_002`
- WHEN `query_guardian_metrics(campaign_id="camp_001")` is called
- THEN all records for `camp_001` are returned
- AND results are ordered by timestamp

#### Scenario: Query by guardian filters

- GIVEN metrics from `RiskGuardian` and `PortfolioGuardian`
- WHEN `query_guardian_metrics(campaign_id="camp_001", guardian_name="RiskGuardian")` is called
- THEN only `RiskGuardian` records are returned

#### Scenario: Range query enforces boundaries

- GIVEN metrics spanning 2025-01-01 to 2025-06-01
- WHEN `query_guardian_metrics(campaign_id="camp_001", start="2025-03-01", end="2025-04-01")` is called
- THEN only records within the range are returned

#### Scenario: Empty campaign returns empty list

- GIVEN no metrics for `camp_nonexistent`
- WHEN `query_guardian_metrics(campaign_id="camp_nonexistent")` is called
- THEN an empty list is returned
- AND no error is raised

## MODIFIED Requirements

### Requirement: Directory Initialization

The system MUST create the Knowledge Lake skeleton: `raw/`, `structured/`, `graph/`, `embeddings/`, `datasets/`, `pipeline-runs/`, `agent-memory/`, `campaign-phases/`, `parameter-matrix/`, `guardian-feedback/`, `maintenance/`. `structured/` SHALL host the reconciled sub-layouts `structured/{campaign_id}/` (configs, metrics, results, envelopes), `structured/sqx-kb/{sqx_version}/parameters/{tab}/`, and `structured/sqx-version/{old}→{new}/`. Each directory SHALL contain a `.gitkeep` or metadata file. `campaign-phases/` MUST contain `{campaign_id}/{phase_name}/envelope.json` for every completed phase. `guardian-feedback/` MUST contain `{campaign_id}/metrics.jsonl` for every campaign with guardian evaluation.

(Previously: 11-directory skeleton without guardian-feedback/ requirement)

#### Scenario: Fresh initialization creates all directories

- GIVEN a `knowledge/` path that does not exist
- WHEN the system initializes the Knowledge Lake
- THEN 11 top-level subdirectories are created
- AND `guardian-feedback/` exists with a `.gitkeep` marker file

#### Scenario: Re-initialization on existing structure is idempotent

- GIVEN an already-initialized Knowledge Lake with files present
- WHEN the system initializes again
- THEN no existing files are modified or deleted
- AND no error is raised

---

# Delta for cfx-editor

## ADDED Requirements

### Requirement: Typed RiskConfig → CFX risk_money_mgmt Mapping (Issue 2)

The system MUST provide a `RiskConfigMapper` that serializes a typed `RiskConfig` Pydantic model into `BuildTask.risk_money_mgmt` `SettingsSection` entries with known SQX XML keys. The mapper SHALL validate field types and ranges before serialization; invalid values MUST raise `RiskConfigError`. The round-trip (CFX → RiskConfig → CFX) MUST preserve all non-conflicting fields.

#### Scenario: RiskConfig round-trips through CFX

- GIVEN a `RiskConfig` with `max_portfolio_drawdown=0.15`, `kelly_fraction_cap=0.25`
- WHEN `RiskConfigMapper.to_cfx(risk_config)` is called
- THEN `BuildTask.risk_money_mgmt` contains the corresponding SQX XML keys
- AND deserializing back produces an equivalent `RiskConfig`

#### Scenario: Invalid range fails closed

- GIVEN a `RiskConfig` with `max_portfolio_drawdown=2.0` (out of [0,1])
- WHEN `RiskConfigMapper.to_cfx(risk_config)` is called
- THEN `RiskConfigError` is raised
- AND no partial CFX section is written

#### Scenario: SQX version safety

- GIVEN a CFX with unsupported schema version
- WHEN `RiskConfigMapper.from_cfx(build_task)` is called
- THEN `VersionError` is raised
- AND the mapper does not produce a partial `RiskConfig`

## MODIFIED Requirements

### Requirement: CFX Archive Read/Write

The system MUST read valid `.cfx` files (ZIP/DEFLATE archives) and produce typed Pydantic models for both Config and Project types. For BuildTask models, the expected sections include an optional CommissionCosts section alongside the existing 12 main sections, and a typed `RiskConfig` bridge for `risk_money_mgmt`. Written output MUST match SQX format: UTF-8 without XML declaration, ZIP/DEFLATE compression, no extraneous files.

(Previously: No commission/cost sections or typed RiskConfig bridge existed)

#### Scenario: Read config CFX produces typed RiskConfig

- GIVEN a valid config `.cfx` file with a Build task containing risk settings
- WHEN CfxReader reads it
- THEN typed Pydantic models are returned with Options, WhatToBuild, RiskMoneyManagement (as `RiskConfig`), Data, Rankings, PartsToImprove, CrossChecks, Notes, Blocks, ATMs, Databanks, Resources, and optionally CommissionCosts populated

#### Scenario: Write CFX preserves RiskConfig fields

- GIVEN a BuildTask with a populated `RiskConfig` bridge
- WHEN CfxWriter produces the archive
- THEN the output XML contains the risk_money_mgmt elements with correct values
- AND round-trip deserialization recovers the original `RiskConfig`
