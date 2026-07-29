# Pipeline Core Specification

## Purpose

Generic, reusable pipeline execution framework decoupled from any SQX domain. Stages compose via fluent builder. Runner provides sequential execution, per-stage timing, error isolation, and structured results.

## Requirements

### Requirement: Stage ABC

The system MUST provide a `Stage` abstract base class with `name: str`, `requires: list[str]`, `provides: list[str]`, and `async execute(ctx: PipelineContext) -> Any`.

#### Scenario: Stage subclass contract

- GIVEN a concrete Stage subclass
- WHEN executed via execute(ctx)
- THEN name, requires, provides are accessible
- AND execute() accepts PipelineContext and returns Any

#### Scenario: Missing required context key

- GIVEN a stage that requires "cfx_bytes" not in PipelineContext
- WHEN execute() is invoked
- THEN StageExecutionError is raised with the stage_name

### Requirement: Pipeline Composition

The system MUST provide `Pipeline` as a dataclass with `stages: list[Stage]` and a `.then(stage) -> Pipeline` fluent builder.

#### Scenario: Fluent chaining

- GIVEN Pipeline()
- WHEN .then(A()).then(B()).then(C())
- THEN stages list is [A, B, C]

### Requirement: PipelineContext

The system MUST provide `PipelineContext(config: dict, artifacts: dict, metadata: dict, error: Exception | None)`. Stages SHALL read from config, write to artifacts.

#### Scenario: Context passthrough

- GIVEN Stage A writes "cfx_bytes" to artifacts
- WHEN Stage B requires "cfx_bytes" and runs after A
- THEN B receives the artifact from A

### Requirement: PipelineRunner

The system MUST execute stages sequentially, capture per-stage timing, catch per-stage errors, and produce `PipelineResult`.

#### Scenario: Successful pipeline

- GIVEN 3 valid stages
- WHEN PipelineRunner.run()
- THEN 3 StageResults with status=completed
- AND total_duration > 0

#### Scenario: Error isolation

- GIVEN stage 2 raises StageExecutionError
- WHEN runner executes
- THEN stage 1 completed, stage 2 failed, stage 3 skipped
- AND PipelineResult.is_successful is False

### Requirement: Result Models

The system MUST provide `StageResult(stage_name, status, duration, error, output)` and `PipelineResult(stages, total_duration, is_successful, error)` as dataclasses.

#### Scenario: Failed pipeline result

- GIVEN a pipeline with a failed stage
- WHEN inspecting PipelineResult
- THEN stages list contains all StageResults
- AND error contains the StageExecutionError

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

### Requirement: PipelineError Exceptions

The system MUST define `PipelineError(QuantLabError)` and `StageExecutionError(PipelineError)` with `stage_name: str`.

#### Scenario: StageExecutionError carries context

- GIVEN a failing "ValidateStage"
- WHEN catching StageExecutionError
- THEN error.stage_name == "ValidateStage"
- AND it is catchable as PipelineError or QuantLabError

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

#### Scenario: ValidateStage I/O contract

- GIVEN ValidateStage
- WHEN inspecting its contract
- THEN requires list includes "config.sqx_install_path"
- AND provides list includes "license_validated"

#### Scenario: Full stage chain contract

- GIVEN all 10 stages in pipeline order (CostInjectionStage before TranslateStage)
- WHEN each stage executes sequentially
- THEN each stage's requires are satisfied by previous stages' provides
- AND CostInjectionStage injects cost_config before translation needs it

### Requirement: Stage Registry — research_llm

The system MUST register `"research_llm"` as a valid stage type in `StageRegistry`, mapping to `LLMResearchStage`.

#### Scenario: research_llm is registered

- GIVEN StageRegistry
- WHEN looking up "research_llm"
- THEN the registry returns LLMResearchStage class
- AND the stage is available for pipeline composition

#### Scenario: Unknown stage gracefully handled

- GIVEN a stage name that is not registered
- WHEN StageRegistry.lookup() is called
- THEN RegistryError is raised
- AND the existing classic stages remain unaffected

### Requirement: ResearchDirector Routing

`ResearchDirector` MUST route between `"research"` and `"research_llm"` stages based on `AgentConfig.model`. If `model != ""`, the director SHALL use `LLMResearchAgent`; if `model == ""`, it SHALL use the classic `ResearchAgent`.

#### Scenario: LLM configured routes to LLM agent

- GIVEN AgentConfig.model = "gpt-4"
- WHEN ResearchDirector resolves the research stage
- THEN "research_llm" stage is selected
- AND the pipeline uses LLMResearchAgent

#### Scenario: Empty model routes to classic

- GIVEN AgentConfig.model = ""
- WHEN ResearchDirector resolves the research stage
- THEN "research" stage is selected
- AND the pipeline uses classic ResearchAgent

#### Scenario: LLM fallback on failure

- GIVEN LLMResearchAgent fails with timeout
- WHEN ResearchDirector receives the failure
- THEN the director falls back to classic ResearchAgent
- AND the pipeline completes without LLM
