# Builder Agent Specification

## Purpose

Translates ResearchConfig DSL → CFX via sqx-translator, validates CFX via cfx-editor, dispatches to SQX via sqcli-wrapper, validates license, and monitors campaign execution. Produces campaign_id and export paths for downstream agents.

---

## Requirements

### Requirement: DSL to CFX Translation

The system MUST translate a validated ResearchConfig into StrategyQuant CFX bytes using sqx-translator, with pre-flight validation via cfx-editor.

#### Scenario: Valid ResearchConfig translates to CFX
- GIVEN ResearchConfig with market=EURUSD, timeframe=H1, building_blocks=[RSI(14), BB(20,2)], acceptance_criteria
- WHEN BuilderAgent.translate_to_cfx() called
- THEN CFX bytes returned containing <Strategy> with correct market, timeframe, indicator parameters
- AND cfx-editor.validate(cfx_bytes) returns valid=True

#### Scenario: Translation error surfaced
- GIVEN ResearchConfig with invalid indicator parameter (RSI period=0)
- WHEN BuilderAgent.translate_to_cfx() called
- THEN TranslationError raised with field path and constraint violation

### Requirement: SQX Dispatch and Campaign Monitoring

The system MUST dispatch CFX to SQX via sqcli-wrapper (loadconfig → start → poll status → stop), manage license via license-manager, and return campaign_id and export paths.

#### Scenario: Campaign dispatched and monitored
- GIVEN valid CFX bytes, licensed SQX environment
- WHEN BuilderAgent.dispatch_and_monitor(cfx_bytes) called
- THEN sqcli loadconfig executed, campaign starts, status polled every 30s
- AND on completion: exports generated, campaign_id returned, export_paths list populated

#### Scenario: License validation gates dispatch
- GIVEN license-manager.validate() returns invalid/expired
- WHEN BuilderAgent.dispatch_and_monitor() called
- THEN LicenseError raised, no sqcli process spawned

#### Scenario: Campaign timeout handled
- GIVEN campaign exceeds max_runtime_hours (default 4h)
- WHEN polling detects timeout
- THEN sqcli stop sent, CampaignTimeoutError raised, partial exports collected

### Requirement: Campaign Config Generation

The system MUST generate pipeline YAML configuration for the ResearchDirector, including agent parameters, gate policies, and stage ordering.

#### Scenario: Pipeline YAML generated from ResearchConfig
- GIVEN ResearchConfig with iteration_config.max_iterations=3, gate_policies
- WHEN BuilderAgent.generate_pipeline_config() called
- THEN YAML contains: stages list with 8 agents, gates with timeout_hours, agent config per stage
- AND stage ordering matches ResearchDirector pipeline architecture

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| CFX validates against cfx-editor schema | Unit test: translate → validate → assert valid |
| sqcli lifecycle executed in order | Integration test: mock sqcli, assert call sequence |
| License check blocks unlicensed execution | Unit test: mock invalid license, assert LicenseError |
| Campaign timeout stops sqcli and collects partials | Integration: mock long-running, assert stop called |
| Pipeline YAML includes all 8 agents + 5 gates | Unit test: parse YAML, assert stage count and names |

---

## Non-Functional Requirements

- **Performance**: CFX translation < 2s; campaign dispatch overhead < 5s
- **Reliability**: sqcli process cleaned up on any error (try/finally)
- **Dependencies**: sqx-translator, cfx-editor, sqcli-wrapper, license-manager
- **Observability**: Structured logs per phase: translate, validate, dispatch, poll, export