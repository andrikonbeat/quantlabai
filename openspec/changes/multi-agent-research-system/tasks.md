# Tasks: Multi-Agent Research System

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 8000-12000 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 → PR 4 → PR 5 → PR 6 |
| Delivery strategy | auto-chain |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Foundation & Pipeline Core Extensions | PR 1 | Base branch: feature/multi-agent-foundation; tests/docs included |
| 2 | Core Agents (Research Director + Research Agent + Builder Agent) | PR 2 | Base: feature/multi-agent-foundation; depends on PR 1 |
| 3 | Analysis Agents (Statistics + Reviewer + Portfolio) | PR 3 | Base: PR 2 branch; depends on PR 2 |
| 4 | Gates & Deployment (HumanGateOrchestrator + DeploymentAgent) | PR 4 | Base: PR 3 branch; depends on PR 3 |
| 5 | Monitoring, Persistence & Reporting | PR 5 | Base: PR 4 branch; depends on PR 4 |
| 6 | CLI, Config, Integration Tests, Docs | PR 6 | Base: PR 5 branch; depends on PR 5; final integration |

## Phase 1: Foundation & Pipeline Core Extensions (PR 1)

### Pipeline Core Extensions
- [x] 1.1 Create `GateInterceptorStage` abstract class in `sdk/quantlab/pipeline/stages/gate_interceptor.py` with async callback protocol, timeout handling, fallback policies (ABORT/CONTINUE/ESCALATE), Engram recording
- [x] 1.2 Add 8 new abstract stage classes: `ResearchStage`, `BuilderStage`, `StatisticsStage`, `ReviewStage`, `PortfolioStage`, `DeployStage`, `MonitorStage` in `sdk/quantlab/pipeline/stages/agent_stages.py` with `requires`/`provides` contracts per spec
- [x] 1.3 Implement `PipelineRunner.validate_contracts()` method in `sdk/quantlab/pipeline/runner.py` to verify all stage `requires` satisfied by prior `provides` before execution
- [x] 1.4 Add `ContractValidationError` exception in `sdk/quantlab/pipeline/errors.py` with missing keys and stage names (already existed — verified)
- [x] 1.5 Update `PipelineRunner.run()` to register `GateInterceptorStage` instances as pipeline stages at configured gate positions (added `register_gate()`, `run_with_gates()`, gate injection in `build_from_config()`)

### Pipeline Configuration YAML Schema
- [x] 1.6 Create `MultiAgentPipelineConfig` Pydantic model in `sdk/quantlab/pipeline/config/models.py` with sections: `pipeline` (stages), `agents[]`, `gates[]`, `memory{}`, `risk{}` (enhanced existing model with nested pipeline section support)
- [x] 1.7 Add JSON Schema file `sdk/quantlab/pipeline/config/pipeline-config.schema.json` for YAML validation (enhanced with all new sections)
- [x] 1.8 Implement `MultiAgentPipelineConfig.load(path)` with environment variable overrides (`QUANTLAB_PIPELINE_*` prefix) in `sdk/quantlab/pipeline/config/loader.py`
- [x] 1.9 Add config version field and migration helper in `sdk/quantlab/pipeline/config/migration.py` (version field, v1→v2 migration, gate extraction)

### Pipeline Registry
- [x] 1.10 Create agent stage registry in `sdk/quantlab/pipeline/registry.py` mapping agent names to stage classes (7 agent + 5 gate alias stages registered alongside 11 SQX builtin stages)
- [x] 1.11 Implement `PipelineRunner.build_from_config(config: MultiAgentPipelineConfig)` that instantiates stages from registry using agent configs
- [x] 1.12 Add backward compatibility: ensure original 9 stages still work unchanged (regression test passes — 134 existing tests green)

### Tests (PR 1)
- [x] 1.13 Unit tests for `GateInterceptorStage`: mock callback, verify pause/resume/fallback/Engram recording
- [x] 1.14 Unit tests for all 8 new agent stages: verify `requires`/`provides` attributes match spec
- [x] 1.15 Unit test for `PipelineRunner.validate_contracts()`: valid pipeline passes, mismatched fails with correct error
- [x] 1.16 Integration test: load minimal pipeline YAML, build pipeline, verify stages in correct order
- [x] 1.17 Regression test: basic 9-stage SQX pipeline executes without new stages

## Phase 2: Core Agents (Research Director + Research Agent + Builder Agent) (PR 2)

### Research Director Agent
- [x] 2.1 Create `ResearchDirector` class in `quantlab/agents/research_director.py` owning `PipelineRunner`, managing campaign lifecycle (create, run, pause, resume, rollback)
- [x] 2.2 Implement `ResearchDirector.execute_campaign(config: ResearchConfig)` that builds pipeline from config, runs it, handles gate callbacks
- [x] 2.3 Add `ResearchDirector.rollback_campaign(campaign_id)` deleting Knowledge Lake artifacts and Engram topics for campaign
- [x] 2.4 Implement objective optimization loop: after monitoring gate, evaluate convergence, modify hypotheses, loop back to ResearchAgent

### Research Agent
- [x] 2.5 Create `ResearchAgent` class in `quantlab/agents/research_agent.py` with `generate_config(objectives, market_context)` method
- [x] 2.6 Implement hypothesis generation from objectives using `knowledge_query.QueryBuilder` to fetch historical patterns
- [x] 2.7 Extend `ResearchConfig` DSL in `quantlab/research/dsl/models.py` with fields: `hypotheses[]`, `iteration_config{}`, `gate_policies{}`
- [x] 2.8 Add DSL parser support for new fields in `quantlab/research/dsl/parser.py`
- [x] 2.9 Implement `ResearchAgent.run(context: PipelineContext)` writing `research_config`, `objectives`, `hypotheses`, `iteration_config`, `gate_policies` to context

### Builder Agent
- [x] 2.10 Create `BuilderAgent` class in `quantlab/agents/builder_agent.py` orchestrating CFX translation + SQX dispatch
- [x] 2.11 Implement `BuilderAgent.run(context)`: read `research_config`, call `sqx_translator.translate()`, validate via `cfx_editor.validate()`, check license via `license_manager.validate()`, dispatch via `sqx_cli_wrapper.dispatch()`
- [x] 2.12 Write `cfx_bytes`, `campaign_id`, `sqcli_status`, `export_paths` to PipelineContext
- [x] 2.13 Add retry logic (configurable, default 2) and timeout (default 60 min) for SQX execution

### Extended ResearchConfig DSL + Pipeline YAML
- [x] 2.14 Create example `research-config.yaml` with full DSL: objectives, hypotheses, iteration_config, gate_policies

- [x] 2.15 Create example `pipeline.yaml` with 7 agent stages + 5 gate interceptors in correct order
### Tests (PR 2)
- [x] 2.16 Unit test: ResearchDirector builds 17-stage pipeline from config, executes mock stages
- [x] 2.17 Unit test: ResearchAgent generates valid ResearchConfig with hypotheses from objectives
- [x] 2.18 Unit test: BuilderAgent translates DSL → CFX → validates → dispatches (mock SQX)
- [x] 2.19 Integration test: ResearchDirector + ResearchAgent + BuilderAgent end-to-end with mock SQX
- [x] 2.20 DSL parsing test: extended ResearchConfig YAML loads with all new fields

## Phase 3: Analysis Agents (Statistics + Reviewer + Portfolio) (PR 3)

### Statistics Agent
- [ ] 3.1 Create `StatisticsAgent` in `quantlab/agents/statistics_agent.py` with `run(context)` method
- [ ] 3.2 Implement statistics computation: call `statistics_engine.compute_all()` on exports, write `statistics`, `aggregate_stats`, `monte_carlo_bands`
- [ ] 3.3 Add `StatisticsAggregator` integration for cross-campaign aggregation and Monte Carlo bands (configurable n_sims, percentiles)
- [ ] 3.4 Implement rolling metrics computation for monitoring agent consumption

### Reviewer Agent
- [ ] 3.5 Create `ReviewerAgent` in `quantlab/agents/reviewer_agent.py` with criteria evaluation logic
- [ ] 3.6 Implement `evaluate(statistics, aggregate_stats, monte_carlo_bands)` returning `review_decision` (ACCEPT/ITERATE/REJECT) and `iteration_proposal`
- [ ] 3.7 Add walk-forward degradation detection, Monte Carlo overfitting flags, benchmark comparison using `knowledge_query.QueryBuilder`
- [ ] 3.8 Write `review_decision`, `iteration_proposal`, `wf_degradation`, `mc_overfit_flag`, `benchmark_comparison` to context

### Portfolio Agent
- [ ] 3.9 Create `PortfolioAgent` in `quantlab/agents/portfolio_agent.py`
- [ ] 3.10 Implement `run(context)`: read `selected_strategies` + `review_decision`, call `portfolio_master.build_cfx()`, run genetic optimization via `portfolio_master.run()`, compose portfolio CFX via `portfolio_composer.compose()`
- [ ] 3.11 Add correlation analysis, risk budgeting, Kelly fraction capping using risk config from pipeline YAML
- [ ] 3.12 Integrate walk-forward validation via `optimizer_automation.walk_forward()`
- [ ] 3.13 Write `portfolio_cfx`, `portfolio_result`, `correlation_matrix`, `risk_allocation`, `wf_aggregate_stats` to context

### Tests (PR 3)
- [ ] 3.14 Unit test: StatisticsAgent computes stats, aggregates, runs MC bands (mock exports)
- [ ] 3.15 Unit test: ReviewerAgent evaluates criteria, returns correct decision + proposal
- [ ] 3.16 Unit test: PortfolioAgent runs Portfolio Master, applies risk limits, composes CFX
- [ ] 3.17 Integration test: Statistics → Reviewer → Portfolio agent chain with shared context

## Phase 4: Gates & Deployment (PR 4)

### Human Gate Orchestrator
- [ ] 4.1 Create `HumanGateOrchestrator` in `quantlab/gates/orchestrator.py` managing 5 gates: `HUMAN_REVIEW_OBJECTIVES`, `HUMAN_APPROVE_ITERATION`, `HUMAN_APPROVE_PORTFOLIO`, `HUMAN_APPROVE_DEPLOY`, `HUMAN_REVIEW_PERFORMANCE`
- [ ] 4.2 Implement async approval protocol: `on_gate(gate_id, context) -> Awaitable[GateDecision]` callback
- [ ] 4.3 Add configurable timeout per gate (default 24h, deploy 12h, performance 48h) with fallback policies (ESCALATE/STOP/HOLD/CONTINUE)
- [ ] 4.4 Implement notification hooks: email, Slack webhook, file-based callback (configurable per gate)
- [ ] 4.5 Integrate with `GateInterceptorStage`: on gate stage execution, invoke orchestrator, await decision, record to Engram

### Gate Interceptor Stage Injection
- [ ] 4.6 Update `PipelineRunner` to inject `GateInterceptorStage` instances at `gate_after` positions defined in pipeline YAML
- [ ] 4.7 Ensure gate decision (`gate_decision_{gate_id}`) written to context for downstream stages

### Deployment Agent
- [ ] 4.8 Create `DeploymentAgent` in `quantlab/agents/deployment_agent.py`
- [ ] 4.9 Implement `run(context)`: read `portfolio_cfx`, call `jforex_deploy.package()` for JAR/WAR, generate JCloud config via `jforex_deploy.jcloud_config()`
- [ ] 4.10 Add dry-run mode: validate CFX via `cfx_editor.validate()`, simulate packaging without upload
- [ ] 4.11 Write `jforex_package`, `jcloud_config`, `deployment_result` to context

### Tests (PR 4)
- [ ] 4.12 Unit test: HumanGateOrchestrator triggers callback, handles timeout, executes fallback
- [ ] 4.13 Unit test: GateInterceptorStage pauses pipeline, resumes on approval, records to Engram
- [ ] 4.14 Unit test: DeploymentAgent packages CFX, generates JCloud config, dry-run validation
- [ ] 4.15 Integration test: Full pipeline with all 5 gates, mock async approvals, verify context flow

## Phase 5: Monitoring, Persistence & Reporting (PR 5)

### Monitoring Agent
- [ ] 5.1 Create `MonitoringAgent` in `quantlab/agents/monitoring_agent.py`
- [ ] 5.2 Implement `run(context)`: stream live equity via `result_reader.stream_live()`, compute rolling Sharpe/drawdown via `stats_aggregation.rolling_sharpe()` and `rolling_drawdown()`
- [ ] 5.3 Add regime detection: minimum 252-period window, multi-metric confirmation (Sharpe, drawdown, win rate shift)
- [ ] 5.4 Implement alerting: write `rolling_metrics`, `regime_alerts`, `performance_alerts` to context; trigger gate 5
- [ ] 5.5 Add Knowledge Lake persistence for live metrics via `knowledge_storage.store()`

### Knowledge Lake: Agent Memory Directories
- [ ] 5.6 Extend `knowledge_storage` in `quantlab/knowledge/storage.py` with `agent-memory/` directory structure: `knowledge/agent-memory/{agent_name}/{campaign_id}/`
- [ ] 5.7 Add `store_agent_memory(agent_name, campaign_id, artifact)` and `load_agent_memory(agent_name, campaign_id)` methods

### Engram Per-Agent Topic Persistence
- [ ] 5.8 Create `AgentMemoryManager` in `quantlab/agents/memory.py` wrapping Engram: `save_decision(agent, campaign, decision)`, `load_memory(agent, campaign)`, `query_cross_agent(pattern)`
- [ ] 5.9 Configure Engram topic keys: `agent/{agent_name}/{campaign_id}` per agent, Research Director reads all
- [ ] 5.10 Add TTL policies per agent topic (configurable via pipeline YAML memory.retention_days)

### Reporting Extensions
- [ ] 5.11 Extend `reporting` module in `quantlab/reporting/generator.py` with agent decision audit sections
- [ ] 5.12 Add multi-campaign aggregate report: compare campaigns, show agent decision patterns
- [ ] 5.13 Add comparison views: iteration progression, gate decisions timeline, portfolio composition evolution

### Knowledge Query: Cross-Agent Queries
- [ ] 5.14 Extend `knowledge_query.QueryBuilder` with `query_agent_memory(agent_pattern, campaign_filter)`, `query_campaign_similarity(target_campaign)`
- [ ] 5.15 Implement campaign similarity: match on objectives, market regime, strategy types

### Tests (PR 5)
- [ ] 5.16 Unit test: MonitoringAgent computes rolling metrics, detects regime change (synthetic data)
- [ ] 5.17 Unit test: AgentMemoryManager saves/loads Engram topics, cross-agent queries work
- [ ] 5.18 Unit test: Knowledge Lake agent-memory directory structure created, artifacts stored
- [ ] 5.19 Integration test: MonitoringAgent → Knowledge Lake → Engram persistence chain
- [ ] 5.20 Unit test: Reporting generator produces agent audit section + multi-campaign comparison

## Phase 6: CLI, Config, Integration Tests, Docs (PR 6)

### CLI Commands
- [ ] 6.1 Add `quantlab pipeline validate <config.yaml>` command in `quantlab/cli/commands/pipeline.py` — loads PipelineConfig, runs contract validation, outputs errors
- [ ] 6.2 Add `quantlab pipeline run <config.yaml>` command — instantiates ResearchDirector, executes campaign
- [ ] 6.3 Add `quantlab agent memory inspect <agent> <campaign_id>` — queries Engram for agent memory
- [ ] 6.4 Add `quantlab agent memory query <pattern>` — cross-agent pattern search
- [ ] 6.5 Add `quantlab campaign rollback <campaign_id>` — invokes ResearchDirector.rollback_campaign()

### Full Integration Test
- [ ] 6.6 Create end-to-end test in `tests/integration/test_full_pipeline.py`: 17-stage dry-run with mock SQX, mock gates, verify all stages execute, context artifacts flow correctly
- [ ] 6.7 Add end-to-end smoke test with mock SQX: ResearchAgent → BuilderAgent → StatisticsAgent → ReviewerAgent → PortfolioAgent → DeploymentAgent → MonitoringAgent, all gates auto-approve
- [ ] 6.8 Verify Knowledge Lake artifacts written at each stage, Engram topics created for all 8 agents

### Documentation
- [ ] 6.9 Update `docs/architecture/multi-agent-system.md` with agent roles, pipeline flow, gate protocol
- [ ] 6.10 Update `docs/configuration/pipeline-config.md` with full YAML schema, examples, env overrides
- [ ] 6.11 Update `docs/guides/running-campaigns.md` with multi-agent campaign workflow
- [ ] 6.12 Add CHANGELOG entry for multi-agent research system release

### Polish
- [ ] 6.13 Run full test suite, fix any regressions in existing 9-stage pipeline
- [ ] 6.14 Verify no new external dependencies added (pip check)
- [ ] 6.15 Code review pass: type hints, docstrings, structured logging throughout

## Dependency Graph

```
PR 1 (Foundation)
    │
    ├── PR 2 (Core Agents) ──→ PR 3 (Analysis Agents) ──→ PR 4 (Gates & Deploy)
    │                                                         │
    └─────────────────────────────────────────────────────────┘
                                                    │
                                                PR 5 (Monitoring/Persistence/Reporting)
                                                    │
                                                PR 6 (CLI/Integration/Docs)
```

## Implementation Order

1. **PR 1** — Foundation: Pipeline core extensions, config schema, registry. Everything depends on this.
2. **PR 2** — Core Agents: Research Director owns pipeline; Research Agent + Builder Agent are first two stages.
3. **PR 3** — Analysis Agents: Statistics → Reviewer → Portfolio chain depends on Builder output.
4. **PR 4** — Gates & Deployment: Human gates integrate with PipelineRunner; DeploymentAgent consumes Portfolio output.
5. **PR 5** — Monitoring/Persistence/Reporting: Cross-cutting concerns, Engram integration, reporting extensions.
6. **PR 6** — CLI/Integration/Docs: Final integration, validation, user-facing commands.

## Acceptance Checklist

- [ ] All 17 pipeline stages defined with correct requires/provides contracts
- [ ] GateInterceptorStage implements async approval with timeout/fallback/Engram recording
- [ ] PipelineRunner.validate_contracts() catches contract violations
- [ ] ResearchDirector executes full 8-agent pipeline end-to-end
- [ ] All 5 human gates trigger with async approval, timeout, fallback
- [ ] ResearchConfig DSL extended with hypotheses, iteration_config, gate_policies
- [ ] Pipeline YAML drives agent sequencing without code changes
- [ ] Knowledge Lake stores campaign artifacts immutably at `knowledge/structured/{campaign_id}/`
- [ ] Engram captures agent memories at `agent/{agent_name}/{campaign_id}`
- [ ] Builder Agent: DSL → CFX → SQX dispatch → export paths flow works
- [ ] Statistics Agent: stats + aggregation + Monte Carlo bands computed
- [ ] Reviewer Agent: criteria evaluation + iteration proposal + walk-forward + MC overfit detection
- [ ] Portfolio Agent: Portfolio Master + correlation + risk budgeting + Kelly + walk-forward
- [ ] Deployment Agent: JForex packaging + JCloud config + dry-run validation
- [ ] Monitoring Agent: live equity → rolling metrics → regime alerts → Knowledge Lake
- [ ] Agent memory: cross-agent queries, campaign similarity search
- [ ] Reporting: agent audit sections, multi-campaign comparison
- [ ] CLI: validate, run, memory inspect, memory query, campaign rollback
- [ ] 17-stage integration test passes with mock SQX
- [ ] No new external dependencies introduced
- [ ] Backward compatibility: original 9-stage pipeline unchanged
- [ ] Documentation updated
- [ ] CHANGELOG entry added