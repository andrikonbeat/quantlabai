# Exploration: Multi-Agent Autonomous Research System

**Change name**: `multi-agent-research-system`  
**Date**: 2026-07-19  
**Context**: QuantLab AI SDK (Phases 4-5 complete)

---

## Current State

QuantLab AI provides a quantitative research SDK with these key components:

| Module | Purpose | Lines |
|--------|---------|-------|
| `quantlab.pipeline` | Generic async pipeline framework (11 SQX stages) | ~600 |
| `quantlab.knowledge` | Knowledge Lake (store, query, indexer) | ~800 |
| `quantlab.stats` | Statistics engine (PF, Sharpe, Sortino, MDD, MAR, Recovery, Expectancy) | ~350 |
| `quantlab.phase4` | SQX automation: CampaignOrchestrator, Optimizer, Retester, PortfolioMaster, JForexDeployer, DaemonManager | ~2500 |
| `quantlab.cli` | Async CLI with daemon context, pipeline commands | ~1500 |
| `quantlab.reporting` | HTML/JSON reports with Plotly charts | ~530 |
| `quantlab.dsl` | ResearchConfig DSL (markets, timeframes, building blocks, criteria) | ~175 |
| `quantlab.translate` | ResearchConfig → CFX archive factory | ~340 |

**Real SQX**: `/home/ogzuz/Proyectos/QuantLab AI//home/ogzuz/Proyectos/SQX_144_2953_linux_20260601/sqcli`

---

## Agent ↔ SDK Mapping

| Agent | Primary SDK Modules | Responsibility |
|-------|---------------------|----------------|
| **1. Research Director** | `pipeline.runner`, `pipeline.registry`, `knowledge.store` | Orchestrates full cycle, decides research direction, manages pipeline execution |
| **2. Research Agent** | `knowledge.query`, `knowledge.indexer`, `dsl.models` | Investigates papers, formulates hypotheses, proposes experiments via ResearchConfig |
| **3. Builder Agent** | `translate.cfx.CfxArchiveFactory`, `dsl.parser`, `pipeline.stages.TranslateStage` | Translates hypotheses → ResearchConfig DSL → CFX → pipeline YAML |
| **4. Statistics Agent** | `stats.engine`, `stats.aggregation` (new), `knowledge.query` | Computes metrics, aggregates cross-campaign, detects degradation |
| **5. Reviewer Agent** | `phase4.optimizer`, `phase4.retester`, `phase4.portfolio_master`, `reporting.generator` | Adversarial review: walk-forward, Monte Carlo, overfitting checks |
| **6. Portfolio Agent** | `phase4.portfolio_master`, `phase4.portfolio_composer`, `stats.aggregation` | Optimizes strategy combination, correlation, risk allocation |
| **7. Deployment Agent** | `phase4.jforex_deploy`, `phase4.daemon`, `cli.daemon.DaemonContext` | Prepares JForex Java, deploys to JCloud/JForex (human approval gate) |
| **8. Monitoring Agent** | `knowledge.store`, `reporting.generator`, `stats.engine` | Tracks live performance, detects regime change, alerts |

---

## Architecture Options

### Option A: Centralized Orchestrator (Recommended)

**Pattern**: Research Director owns the main pipeline; other agents are pipeline stages or sub-pipelines.

```
Research Director (PipelineRunner)
    ├─► Research Agent → Knowledge Lake query
    ├─► Builder Agent → TranslateStage → CFX
    ├─► Statistics Agent → ComputeStatsStage
    ├─► Reviewer Agent → Retester/Optimizer sub-pipelines
    ├─► Portfolio Agent → PortfolioMaster sub-pipeline
    ├─► Deployment Agent → DaemonContext + JForexDeployer
    └─► Monitoring Agent → scheduled Knowledge Lake queries
```

**Communication**: Shared `PipelineContext.artifacts` dict + Knowledge Lake persistence

**Pros**:
- Single source of truth (PipelineContext)
- Natural human gates between stages
- Reuses existing 11-stage pipeline framework
- Engram for agent memory, Knowledge Lake for campaign history
- Clear audit trail via PipelineRun history

**Cons**:
- Research Director becomes a "god object"
- Coupling through shared context dict

---

### Option B: Message-Passing Actor Model

**Pattern**: Each agent is an independent async actor communicating via message queues.

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  Research   │   │  Knowledge  │   │  Builder    │
│   Director  │◄──│    Lake     │──►│    Agent    │
└─────────────┘   │  (Engram)   │   └─────────────┘
       │          └─────────────┘          │
       ▼                                   ▼
┌─────────────┐                     ┌─────────────┐
│ Statistics  │                     │  Reviewer   │
│   Agent     │                     │   Agent     │
└─────────────┘                     └─────────────┘
       │                                   │
       ▼                                   ▼
┌─────────────────────────────────────────────────┐
│           Deployment / Monitoring Agents        │
└─────────────────────────────────────────────────┘
```

**Communication**: Async message bus (Redis/NATS or in-memory asyncio.Queue) with topics per agent

**Pros**:
- True isolation between agents
- Horizontal scaling possible
- Fault isolation (one agent crash doesn't kill others)

**Cons**:
- Significant new infrastructure (message bus)
- Complex distributed tracing
- Overkill for single-workstation SQX automation
- Loses the natural PipelineContext artifact flow

---

### Option C: Hybrid (Pipeline + Events)

**Pattern**: Main workflow = pipeline stages; agents emit events for async side effects (monitoring, alerting).

```
Pipeline Stages (synchronous, ordered):
  validate → translate → daemon_start → load_config → run_campaign → poll → export → read → compute_stats → knowledge_store → report

Event Bus (async, parallel):
  ├─► campaign.completed → Monitoring Agent (alert on degradation)
  ├─► stats.computed → Statistics Agent (cross-campaign aggregation)
  └─► strategy.selected → Portfolio Agent (rebalance trigger)
```

**Pros**:
- Best of both worlds
- Monitoring/alerting don't block main pipeline
- Uses existing pipeline framework as backbone

**Cons**:
- Adds event bus complexity
- Two execution models to reason about

---

## Recommended Communication Pattern

**Use Option A (Centralized Pipeline) with Option C's event bus for monitoring/alerting only.**

### Rationale

1. **PipelineContext is already the shared artifact bus** — each stage declares `requires`/`provides`; the runner validates at build time
2. **Human gates are natural pipeline boundaries** — `PollCampaignStage` waits for completion; between stages we can insert approval callbacks
3. **Knowledge Lake is the persistent shared memory** — all agents read/write campaign history, metrics, tags, links
4. **Engram provides agent-specific memory** — each sub-agent persists its own decisions, hypotheses, learnings
4. **PipelineRun history gives full audit trail** — stored in Knowledge Lake automatically

### Agent Communication Contract

```python
# Each agent receives a typed PipelineContext slice
class AgentContext:
    config: CampaignConfig           # immutable input
    artifacts: dict[str, Any]        # mutable shared state
    knowledge: KnowledgeStore        # persistent query/store
    engram: EngramClient             # agent-specific memory
    event_bus: EventBus              # for async notifications
    
# Example: Builder Agent
async def builder_agent(ctx: AgentContext) -> dict:
    research_config = ctx.artifacts["research_hypothesis"]
    cfx_result = CfxArchiveFactory.from_model(research_config)
    return {"cfx_bytes": cfx_result.path.read_bytes(), "cfx_path": cfx_result.path}
```

---

## Human-in-the-Loop Gates

| Gate | Location | Agent Triggering | Approval Required |
|------|----------|------------------|-------------------|
| **Hypothesis Approval** | After Research Agent proposes experiments | Research Agent → Director | Human reviews ResearchConfig DSL before CFX generation |
| **Campaign Launch** | Before `RunCampaignStage` | Builder Agent → Director | Human confirms CFX parameters, databanks, risk limits |
| **Strategy Selection** | After Portfolio Master completes | Portfolio Agent → Director | Human reviews selected strategies, weights, correlations |
| **JForex Deployment** | Before `JForexDeployer.export_strategy()` | Deployment Agent → Director | **Mandatory** human approval (live capital risk) |
| **Regime Change Alert** | Monitoring Agent detects drift | Monitoring Agent → Director | Human decides: retrain, pause, or continue |

### Implementation Pattern

```python
# In CampaignConfig
approval_gates: list[str] = [
    "hypothesis_approval",
    "campaign_launch", 
    "strategy_selection",
    "deployment_approval",
]

# In PipelineRunner (or CampaignOrchestrator)
async def _run_with_gates(self, pipeline, ctx):
    for stage in pipeline.stages:
        if stage.name in self.config.approval_gates:
            approved = await self._request_human_approval(stage.name, ctx)
            if not approved:
                raise CampaignError(f"Gate '{stage.name}' rejected by human")
        await stage.execute(ctx)
```

---

## State Persistence Strategy

### Dual-Layer Persistence

| Layer | Technology | Scope | TTL | Purpose |
|-------|------------|-------|-----|---------|
| **Campaign History** | Knowledge Lake (YAML/CSV) | Project-level | Permanent | Campaign results, metrics, artifacts, pipeline runs, tags, links |
| **Agent Memory** | Engram (SQLite + FTS5) | Per-agent | Permanent | Hypotheses, decisions, learnings, patterns, preferences |
| **Runtime State** | PipelineContext.artifacts (in-memory) | Per-pipeline-run | Run duration | Inter-stage artifact passing (CFX bytes, trades, equity, stats) |

### Engram Topic Keys per Agent

```
research-director/research-direction     # Active research themes, priority markets
research-agent/hypotheses                # Proposed hypotheses with rationale
research-agent/paper-notes               # Literature review notes
builder-agent/cfx-templates              # Reusable CFX patterns
statistics-agent/benchmarks              # Historical metric baselines
statistics-agent/degradation-patterns    # Detected degradation signatures
reviewer-agent/overfitting-rules         # Adversarial check criteria
portfolio-agent/correlation-matrices     # Strategy correlation history
deployment-agent/approved-strategies     # Human-approved deployment configs
monitoring-agent/alert-rules             # Regime detection thresholds
```

### Knowledge Lake Integration

```python
# CampaignOrchestrator already does this via SQXKnowledgeStoreStage
store = KnowledgeStore(root=knowledge_root)
store.initialize()

# Save pipeline run (already implemented)
store.save_pipeline_run(run)

# Query for Statistics Agent
campaigns = store.query() \
    .filter_by_sharpe(min_val=1.0) \
    .filter_by_tags(["production", "eurusd"]) \
    .sort_by("sharpe", ascending=False) \
    .limit(20) \
    .execute()
```

---

## Configuration DSL for Research Objectives

Extend existing `ResearchConfig` DSL:

```yaml
# research-objective.yaml
campaign: "Q3-2026-EURUSD-MeanReversion"
objective:
  type: "discover"          # discover | optimize | validate | monitor
  market: "EURUSD"
  timeframe: "H1"
  risk_budget: 0.02         # 2% per trade
  max_drawdown: 0.10        # 10% portfolio DD limit
  min_sharpe: 1.5
  min_profit_factor: 1.3
  min_trades: 100

hypotheses:
  - name: "RSI-MeanReversion"
    building_blocks:
      - name: "RSI-14"
        indicator: {name: "RSI", params: {period: 14}}
        entry: {conditions: ["RSI < 30", "Close > EMA(200)"]}
        exit: {conditions: ["RSI > 70"]}
    acceptance:
      - {metric: "profit_factor", op: ">", value: 1.5}
      - {metric: "sharpe", op: ">", value: 1.5}

pipeline:
  stages:
    - validate
    - translate
    - daemon_start
    - load_config
    - run_campaign
    - poll_campaign
    - export
    - read
    - compute_stats
    - knowledge_store
    - report

gates:
  - hypothesis_approval
  - campaign_launch
  - strategy_selection
  - deployment_approval
```

---

## Integration Points with Existing SDK

| Agent | Entry Point | Key SDK Calls |
|-------|-------------|---------------|
| Research Director | `PipelineRunner.run(pipeline, ctx)` | `CampaignOrchestrator.run()`, `PipelineRegistry.build_pipeline()` |
| Research Agent | `KnowledgeStore.query()` | `QueryBuilder.filter_by_*()`, `Indexer.enhance_index()` |
| Builder Agent | `CfxArchiveFactory.from_model(config)` | `parse_yaml()`, `ResearchConfig` validation |
| Statistics Agent | `StatisticsEngine.compute_all()` | `StatisticsAggregator.aggregate_campaigns()` (new) |
| Reviewer Agent | `Retester.run()`, `Optimizer.run()` | `RetesterConfig`, `OptimizerConfig`, `Retester.parse_csv()` |
| Portfolio Agent | `PortfolioMaster.build_portfolio()` | `PortfolioMasterConfig`, `PortfolioMasterResult` |
| Deployment Agent | `DaemonContext`, `JForexDeployer` | `AsyncSQXClient`, `CommandDispatcher` |
| Monitoring Agent | `KnowledgeStore.query()`, `ReportGenerator` | Scheduled queries, `StatisticsEngine.compute_all()` on live data |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **PipelineContext artifact dict becomes unstructured "god object"** | High | Medium | Enforce typed `requires`/`provides` contracts; add schema validation |
| **Human gates become bottlenecks** | Medium | High | Async approval with timeout; default to "reject" on timeout; Slack/email notifications |
| **Engram memory grows unbounded** | Medium | Low | Implement lifecycle: `mem_review` with decay policies; periodic summarization |
| **Knowledge Lake query performance degrades** | Medium | Medium | Start with YAML index; migrate to SQLite/DuckDB when >10k files |
| **Agent coordination deadlocks** | Low | High | Strict pipeline ordering; no circular dependencies; timeouts on all stages |
| **SQX daemon instability breaks long pipelines** | Medium | High | `SQXDaemonManager` already has auto-restart; add circuit breaker in PipelineRunner |
| **Overfitting detection false positives/negatives** | Medium | High | Reviewer Agent uses multiple orthogonal checks (WF, MC, permutation, noise testing) |

---

## Ready for Proposal

**Yes** — the exploration reveals:

1. **Clear SDK-to-Agent mapping** — every agent has a natural home in existing modules
2. **Pipeline framework is the backbone** — 11 stages cover the full campaign lifecycle
3. **Knowledge Lake + Engram = complete memory system** — persistent campaign history + per-agent learning
4. **Human gates are implementable** — as pipeline stage interceptors with async approval
5. **No new dependencies needed** — all agents use existing SDK; only Engram (already available) for agent memory
6. **Configuration DSL exists** — `ResearchConfig` + pipeline YAML cover research objectives

---

## Next Steps

1. Run `sdd-propose multi-agent-research-system` to create the change proposal
2. Define each agent as an OpenCode sub-agent with focused skill/trigger
3. Implement `StatisticsAggregator` (Phase 5e) as prerequisite for Statistics Agent
4. Add approval gate callbacks to `PipelineRunner` / `CampaignOrchestrator`
5. Create `research-objective.yaml` schema extending `ResearchConfig`