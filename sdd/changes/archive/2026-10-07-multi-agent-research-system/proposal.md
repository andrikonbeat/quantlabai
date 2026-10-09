# Proposal: Multi-Agent Research System

## Intent

QuantLab AI currently executes research campaigns through a single-threaded, manually driven pipeline. Researchers must manually sequence SQX operations, interpret results, decide on strategy selection, and trigger portfolio optimization. This creates a bottleneck: human attention is the limiting factor, and institutional-grade research requires continuous, autonomous iteration across hundreds of campaigns.

This proposal introduces an **autonomous multi-agent research system** where 8 specialized agents collaborate through a centralized pipeline to execute end-to-end quantitative research campaigns with human oversight at 5 critical decision gates. The system leverages the existing QuantLab SDK (pipeline-core, campaign-orchestrator, knowledge-lake, stats-aggregation, reporting, portfolio-master, optimizer-automation) without replacing any capability — agents compose existing modules.

**Why now**: The SDK has matured to cover the full campaign lifecycle. The pipeline framework (11 stages) provides the orchestration backbone. Knowledge Lake + Engram provides dual-layer persistence. We can now compose these into an autonomous research engine.

## Scope

### In Scope

- **Research Director Agent**: Owns `PipelineRunner`, sequences 8 agents as pipeline stages, manages human gates
- **Research Agent**: Generates ResearchConfig DSL from objectives, market hypotheses, and knowledge lake queries
- **Builder Agent**: Translates DSL → CFX via `sqx-translator`, validates via `cfx-editor`, dispatches to SQX via `sqx-cli-wrapper`
- **Statistics Agent**: Computes campaign stats via `statistics-engine`, aggregates via `stats-aggregation`, runs Monte Carlo bands
- **Reviewer Agent**: Evaluates results against acceptance criteria, proposes iterations, triggers human gate #3
- **Portfolio Agent**: Runs Portfolio Master via `portfolio-master`, extracts selected strategies, builds combined portfolio CFX
- **Deployment Agent**: Packages for JForex via `jforex-deploy`, manages JCloud deployment configs
- **Monitoring Agent**: Tracks live performance via `result-reader`, computes rolling metrics, alerts on regime drift
- **Centralized Pipeline Orchestration**: `PipelineRunner` owns execution; agents are stages with `requires/provides` contracts
- **Dual-Layer Persistence**: Knowledge Lake (campaign artifacts, immutable) + Engram (agent memory, decisions, learned patterns)
- **5 Human Gates**: Async approval with configurable timeout (default 24h) and escalation
- **Configuration Extensions**: ResearchConfig DSL + pipeline YAML for agent sequencing and gate policies
- **Agent-to-SDK Mapping Table**: Explicit mapping of each agent to existing SDK modules

### Out of Scope

- New external dependencies (no new PyPI packages)
- Replacement of existing SDK capabilities — composition only
- Real-time streaming data feeds (batch research only)
- Custom SQX plugin development
- Web UI / dashboard (CLI-first, API-ready)
- Multi-user tenancy / RBAC
- Auto-ML hyperparameter optimization beyond Portfolio Master genetic search
- Cross-broker execution (Dukascopy/JForex only)

## Approach

### Architecture: Centralized Pipeline (Option A)

```
ResearchDirector (owns PipelineRunner)
    │
    ├── Stage 1: ResearchAgent      → generates ResearchConfig
    ├── Stage 2: BuilderAgent       → CFX translation + SQX dispatch
    ├── Stage 3: StatisticsAgent    → stats compute + aggregation
    ├── Gate 1: HUMAN_REVIEW_OBJECTIVES
    ├── Stage 4: ReviewerAgent      → criteria evaluation + iteration proposal
    ├── Gate 2: HUMAN_APPROVE_ITERATION
    ├── Stage 5: PortfolioAgent     → Portfolio Master + strategy selection
    ├── Gate 3: HUMAN_APPROVE_PORTFOLIO
    ├── Stage 6: DeploymentAgent    → JForex packaging + JCloud config
    ├── Gate 4: HUMAN_APPROVE_DEPLOY
    ├── Stage 7: MonitoringAgent    → live tracking + regime alerts
    ├── Gate 5: HUMAN_REVIEW_PERFORMANCE
    └── Stage 8: (loop back to ResearchAgent for next cycle)
```

**Communication**: Shared `PipelineContext.artifacts` (immutable, typed) + Knowledge Lake (campaign artifacts) + Engram (agent memory, decisions, cross-session learning).

**Human Gates**: Pipeline stage interceptors that pause execution, notify via callback, await async approval, support timeout with configurable fallback (abort / continue / escalate).

### Agent Roles & SDK Mapping

| Agent | Primary SDK Modules | Pipeline Stage Name | Key I/O (PipelineContext) |
|-------|---------------------|---------------------|---------------------------|
| Research Director | `pipeline-core` (PipelineRunner), `pipeline-error-types` | `director` (orchestrator) | Manages full context lifecycle |
| Research Agent | `research-dsl`, `knowledge-query` | `research` | writes: `research_config`, `objectives`, `hypotheses` |
| Builder Agent | `sqx-translator`, `cfx-editor`, `sqx-cli-wrapper`, `license-manager` | `build` | reads: `research_config`; writes: `cfx_bytes`, `campaign_id`, `sqcli_status` |
| Statistics Agent | `statistics-engine`, `stats-aggregation`, `result-reader` | `statistics` | reads: `export_paths`; writes: `statistics`, `aggregate_stats`, `monte_carlo_bands` |
| Reviewer Agent | `stats-aggregation`, `knowledge-query` | `review` | reads: `statistics`, `aggregate_stats`; writes: `review_decision`, `iteration_proposal` |
| Portfolio Agent | `portfolio-master`, `portfolio-composer`, `optimizer-automation` | `portfolio` | reads: `selected_strategies`; writes: `portfolio_cfx`, `portfolio_result` |
| Deployment Agent | `jforex-deploy`, `cfx-editor` | `deploy` | reads: `portfolio_cfx`; writes: `jforex_package`, `jcloud_config` |
| Monitoring Agent | `result-reader`, `stats-aggregation` (rolling), `knowledge-storage` | `monitor` | reads: `live_equity`; writes: `rolling_metrics`, `regime_alerts` |

### Communication Protocol

- **PipelineContext.artifacts**: Typed dict with Pydantic models for each stage output. Stages declare `requires`/`provides` keys — runner enforces contract.
- **Knowledge Lake**: Immutable campaign artifacts (CFX, exports, statistics, reports) at `knowledge/structured/{campaign_id}/`.
- **Engram**: Agent memories (decisions, learned patterns, cross-campaign insights) at topic `agent/{agent_name}/{campaign_id}`. Research Director aggregates for meta-learning.

### Human Gates (5 Gates)

| Gate ID | Trigger Stage | Decision | Timeout Default | Fallback on Timeout |
|---------|---------------|----------|-----------------|---------------------|
| `HUMAN_REVIEW_OBJECTIVES` | After ResearchAgent | Approve / Reject research objectives & hypotheses | 24h | Escalate to research lead |
| `HUMAN_APPROVE_ITERATION` | After ReviewerAgent | Approve iteration / Stop / Modify criteria | 24h | Stop campaign, archive |
| `HUMAN_APPROVE_PORTFOLIO` | After PortfolioAgent | Approve portfolio composition / Request rebalance | 24h | Escalate to portfolio manager |
| `HUMAN_APPROVE_DEPLOY` | After DeploymentAgent | Approve JForex deployment / Hold | 12h | Hold, queue for next window |
| `HUMAN_REVIEW_PERFORMANCE` | After MonitoringAgent | Continue / Retire / Re-optimize | 48h | Continue monitoring |

Gate implementation: `PipelineRunner` registers gate interceptors as special stages that check `HumanGateDecision` in context. Callback protocol: `on_gate(gate_id, context) -> Awaitable[GateDecision]`.

## Capabilities

### New Capabilities

Each new capability becomes `openspec/specs/<name>/spec.md`:

- `research-director`: PipelineRunner ownership, agent sequencing, gate management, campaign lifecycle control
- `research-agent`: ResearchConfig generation from objectives, knowledge-lake query integration, hypothesis formulation
- `builder-agent`: CFX translation orchestration, SQX dispatch, license validation, campaign monitoring
- `statistics-agent`: StatisticsEngine integration, StatisticsAggregator orchestration, Monte Carlo execution
- `reviewer-agent`: Criteria evaluation, iteration proposal generation, acceptance gate logic
- `portfolio-agent`: PortfolioMaster orchestration, strategy selection, portfolio CFX composition
- `deployment-agent`: JForex packaging, JCloud config generation, deployment validation
- `monitoring-agent`: Live equity ingestion, rolling metrics computation, regime detection, alerting
- `human-gate`: Gate interceptor framework, async approval protocol, timeout/escalation policies
- `agent-memory`: Engram integration for agent memory, cross-session learning, decision audit trail

### Modified Capabilities

Existing capabilities whose REQUIREMENTS change (delta specs needed):

- `pipeline-core`: Add built-in abstract stages for each agent (extends 9 → 17 stages), add gate interceptor stage type
- `campaign-orchestrator`: Integrate with ResearchDirector as higher-level orchestrator; CampaignOrchestrator becomes a stage
- `knowledge-storage`: Add agent-memory directory structure (`knowledge/agent-memory/{agent_name}/`)
- `knowledge-query`: Add agent-memory query support, cross-campaign pattern queries
- `research-dsl`: Extend DSL with agent-specific fields (hypotheses, iteration_config, gate_policies)
- `stats-aggregation`: Add rolling metrics for monitoring agent, regime detection metrics
- `reporting`: Add multi-campaign aggregate reports, agent decision audit reports

## Integration Points: Agent ↔ SDK Mapping Table

| Agent | SDK Module | Function / Class Used | Purpose |
|-------|------------|----------------------|---------|
| Research Director | `pipeline_core.runner.PipelineRunner` | `run()`, `register_gate()` | Owns execution, sequences stages |
| Research Director | `pipeline_core.errors.PipelineError` | Exception handling | Error isolation per stage |
| Research Agent | `research_dsl.parser.parse_research_config()` | Parse YAML → Pydantic | Validate objectives DSL |
| Research Agent | `research_dsl.models.ResearchConfig` | Config model | Type-safe objectives |
| Research Agent | `knowledge_query.builder.QueryBuilder` | Fluent query API | Query historical campaigns |
| Builder Agent | `sqx_translator.translate()` | DSL → CFX bytes | CFX generation |
| Builder Agent | `cfx_editor.validate()` | CFX validation | Pre-flight checks |
| Builder Agent | `sqx_cli_wrapper.dispatch()` | `loadconfig`, `start`, `status`, `stop` | SQX lifecycle |
| Builder Agent | `license_manager.validate()` | License check | Gate SQX execution |
| Statistics Agent | `statistics_engine.compute_all()` | Trades/equity → StatsResult | Per-campaign stats |
| Statistics Agent | `stats_aggregation.StatisticsAggregator` | `aggregate_campaigns()`, `monte_carlo_bands()` | Cross-campaign aggregation |
| Statistics Agent | `result_reader.read_export()` | Export → trades/equity | Data ingestion |
| Reviewer Agent | `stats_aggregation.AggregateStats` | Percentile comparison | Criteria evaluation |
| Reviewer Agent | `knowledge_query.QueryBuilder` | Historical benchmarking | Context-aware review |
| Portfolio Agent | `portfolio_master.build_cfx()` | Strategy list → CFX | Portfolio Master CFX |
| Portfolio Agent | `portfolio_master.run()` | Genetic search execution | Optimization |
| Portfolio Agent | `portfolio_composer.compose()` | Multi-portfolio CFX | Combined deployment |
| Portfolio Agent | `optimizer_automation.walk_forward()` | WF optimization | Robustness validation |
| Deployment Agent | `jforex_deploy.package()` | CFX → JAR/WAR | JForex artifact |
| Deployment Agent | `jforex_deploy.jcloud_config()` | Deployment manifest | Cloud deployment |
| Deployment Agent | `cfx_editor.modify()` | CFX tuning | Deploy-time adjustments |
| Monitoring Agent | `result_reader.stream_live()` | Live equity feed | Real-time ingestion |
| Monitoring Agent | `stats_aggregation.rolling_sharpe()` | Rolling metrics | Regime detection |
| Monitoring Agent | `stats_aggregation.rolling_drawdown()` | Rolling drawdown | Risk monitoring |
| Monitoring Agent | `knowledge_storage.store()` | Artifact persistence | Live metrics archive |

## Persistence Strategy: Dual-Layer

| Layer | Technology | Content | Access Pattern |
|-------|------------|---------|----------------|
| **Knowledge Lake** | Filesystem (Git-versioned) | Campaign artifacts: CFX, exports, statistics, reports, portfolio CFX, JForex packages | Immutable append-only; read by agents, query by KnowledgeQuery |
| **Engram** | Persistent memory (SQLite + FTS5) | Agent memories: decisions, hypotheses, learned patterns, cross-campaign insights, gate decisions | Agent-scoped topics; read/write by owning agent; Research Director reads all |

**Engram Topic Keys**:
- `agent/research-director/{campaign_id}` — gate decisions, sequencing logic
- `agent/research-agent/{campaign_id}` — hypotheses, objectives, query patterns
- `agent/builder-agent/{campaign_id}` — CFX variants, dispatch configs
- `agent/statistics-agent/{campaign_id}` — metric computations, aggregation configs
- `agent/reviewer-agent/{campaign_id}` — criteria evaluations, iteration logic
- `agent/portfolio-agent/{campaign_id}` — selection rationale, portfolio configs
- `agent/deployment-agent/{campaign_id}` — deployment configs, validation results
- `agent/monitoring-agent/{campaign_id}` — regime models, alert thresholds

## Configuration: ResearchConfig Extensions + Pipeline YAML

### ResearchConfig DSL Extensions (YAML)

```yaml
# research-config.yaml (extends existing ResearchConfig)
research:
  objectives:
    - "Find mean-reversion strategies on EURUSD H1"
    - "Validate robustness across 2020-2024"
  hypotheses:
    - id: "h1"
      description: "RSI(14) < 30 + Bollinger lower band touch"
      confidence: 0.7
  iteration_config:
    max_iterations: 5
    convergence_threshold: 0.02  # Sharpe improvement
  gate_policies:
    HUMAN_REVIEW_OBJECTIVES:
      timeout_hours: 24
      fallback: "escalate"
      required_approvers: ["research_lead"]
    HUMAN_APPROVE_ITERATION:
      timeout_hours: 24
      fallback: "stop"
    HUMAN_APPROVE_PORTFOLIO:
      timeout_hours: 24
      fallback: "escalate"
      required_approvers: ["portfolio_manager"]
    HUMAN_APPROVE_DEPLOY:
      timeout_hours: 12
      fallback: "hold"
    HUMAN_REVIEW_PERFORMANCE:
      timeout_hours: 48
      fallback: "continue"
```

### Pipeline YAML (Agent Sequencing)

```yaml
# pipeline.yaml
version: "1.0"
stages:
  - name: "research"
    agent: "research-agent"
    requires: []
    provides: ["research_config", "objectives", "hypotheses"]
    gate_after: "HUMAN_REVIEW_OBJECTIVES"

  - name: "build"
    agent: "builder-agent"
    requires: ["research_config"]
    provides: ["cfx_bytes", "campaign_id", "sqcli_status"]
    retry: 2
    timeout_minutes: 60

  - name: "statistics"
    agent: "statistics-agent"
    requires: ["export_paths"]
    provides: ["statistics", "aggregate_stats", "monte_carlo_bands"]

  - name: "review"
    agent: "reviewer-agent"
    requires: ["statistics", "aggregate_stats"]
    provides: ["review_decision", "iteration_proposal"]
    gate_after: "HUMAN_APPROVE_ITERATION"

  - name: "portfolio"
    agent: "portfolio-agent"
    requires: ["selected_strategies"]
    provides: ["portfolio_cfx", "portfolio_result"]
    gate_after: "HUMAN_APPROVE_PORTFOLIO"

  - name: "deploy"
    agent: "deployment-agent"
    requires: ["portfolio_cfx"]
    provides: ["jforex_package", "jcloud_config"]
    gate_after: "HUMAN_APPROVE_DEPLOY"

  - name: "monitor"
    agent: "monitoring-agent"
    requires: ["live_equity"]
    provides: ["rolling_metrics", "regime_alerts"]
    gate_after: "HUMAN_REVIEW_PERFORMANCE"
    loop_back_to: "research"
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Pipeline deadlock at human gate (no response) | Medium | High | Configurable timeout with explicit fallback; escalation path to lead |
| Agent stage contract violation (missing requires) | Low | High | PipelineRunner validates `requires`/`provides` before stage execution; unit tests for each stage |
| Knowledge Lake corruption (concurrent writes) | Low | Medium | Single-writer per campaign (Research Director); file locking; Git versioning |
| Engram memory growth unbounded | Medium | Medium | TTL policies per agent topic; periodic compaction; Research Director manages lifecycle |
| SQX license exhaustion during parallel campaigns | Medium | High | LicenseManager validates before dispatch; queue with priority; max concurrent campaigns config |
| Monte Carlo computation timeout (1000 sims) | Low | Medium | Configurable `n_simulations`; progress callback; early termination on gate timeout |
| Regime detection false positives | Medium | Medium | Minimum observation window (252 periods); multi-metric confirmation; human gate #5 review |
| JForex deployment package incompatibility | Low | High | Dry-run mode in DeploymentAgent; CFX validation; integration test in CI |
| Cross-agent memory inconsistency | Low | Medium | Engram topic isolation; Research Director validates cross-agent reads; audit trail |

## Rollback Plan

1. **Pipeline Rollback**: `PipelineRunner` captures `PipelineResult` with all `StageResult`s. On failure, re-run from last successful stage using stored artifacts in Knowledge Lake.
2. **Campaign Rollback**: Delete `knowledge/structured/{campaign_id}/` and Engram topics for that campaign. Research Director provides `rollback_campaign(campaign_id)` method.
3. **Agent Memory Rollback**: Engram supports `mem_update`/`mem_delete` per topic. Research Director can revert agent memory to prior checkpoint.
4. **Configuration Rollback**: Git-tracked `research-config.yaml` and `pipeline.yaml` — standard `git revert`.
5. **JForex Deployment Rollback**: DeploymentAgent maintains previous package version; `redeploy_previous()` switches JCloud config.
6. **Full System Rollback**: Disable multi-agent pipeline; fall back to `campaign-orchestrator` direct usage (existing, tested path). Feature flag `multi_agent_enabled: false`.

## Dependencies

- **Existing SDK modules** (all internal, no new deps):
  - `quantlab.pipeline` (core, runner, errors, stages)
  - `quantlab.campaign.orchestrator`
  - `quantlab.knowledge` (storage, query)
  - `quantlab.research.dsl`
  - `quantlab.stats` (engine, aggregation)
  - `quantlab.reporting`
  - `quantlab.portfolio` (master, composer, optimizer)
  - `quantlab.sqx` (translator, cli_wrapper, cfx_editor)
  - `quantlab.license.manager`
  - `quantlab.jforex.deploy`
  - `quantlab.result.reader`
- **No new external dependencies** — confirmed by exploration
- **Python 3.11+** (existing requirement)
- **SQX / sqcli** (existing runtime dependency)

## Success Criteria

- [ ] Research Director executes 8-agent pipeline end-to-end on a test campaign
- [ ] All 5 human gates trigger correctly with async approval flow
- [ ] Timeout/fallback behavior verified for each gate
- [ ] Knowledge Lake stores all campaign artifacts immutably
- [ ] Engram captures agent memories for all 8 agents
- [ ] Configuration DSL validates and drives pipeline execution
- [ ] Rollback procedures tested: campaign, agent memory, deployment
- [ ] No new external dependencies introduced
- [ ] All agent-to-SDK mappings implemented and unit tested
- [ ] Pipeline YAML drives agent sequencing without code changes

## Next Step

Ready for specs phase (`sdd-spec`) to create 10 new capability specs and 7 delta specs for modified capabilities.