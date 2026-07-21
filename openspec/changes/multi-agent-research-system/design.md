# Design: Multi-Agent Research System

## Technical Approach

Centralized pipeline orchestration with 8 specialized agent stages, 5 human gate interceptors, and dual-layer persistence (Knowledge Lake + Engram). Existing 9-stage pipeline stages are preserved as sub-components; the `CampaignOrchestrator` becomes a stage under `ResearchDirector` ownership. Agents are abstract `Stage` subclasses with `requires/provides` contracts validated at build time. No new external dependencies — all agents compose existing SDK modules.

## Architecture Decisions

| Decision | Options | Tradeoffs | Choice |
|----------|---------|-----------|--------|
| Pipeline ownership | Centralized (ResearchDirector) vs. distributed | Centralized gives single lifecycle control, rollback, gate sequencing | Centralized — ResearchDirector owns PipelineRunner |
| Agent stage base | New `AgentStage` ABC vs. reuse `Stage` | New ABC risks hierarchy bloat; reuse misses agent-specific hooks | Extend `Stage` with `requires/provides` and optional `GateInterceptorStage` as a special sibling |
| Gate impl | Pipeline-level interceptor vs. embedded in runner | Interceptor is testable, runner stays generic | `GateInterceptorStage` as pipeline stage (special `GATE` type in registry) |
| Knowledge Lake agent dirs | New `agent-memory/` vs. reuse `structured/` | Separate dir isolates agent artifacts, clean TTL management | New `agent-memory/{agent_name}/{campaign_id}/` subdirectory |
| Engram topic scheme | `agent/{agent_name}/{campaign_id}` vs. flat | Hierarchical allows per-agent retention, cross-campaign queries | Hierarchical with `topic_key: "agent/{agent_name}/{campaign_id}"` |
| Config version | Pydantic `MultiAgentPipelineConfig` vs. union of old+new | Union creates type confusion; separate model is cleaner | `MultiAgentPipelineConfig` extends `ResearchConfig` with pipeline YAML |
| Async gate protocol | Polling vs. callback with await | Callback avoids busy-wait; Engram records decision for audit | `on_gate(gate_id, ctx) -> Awaitable[GateDecision]` |

## Data Flow

```
ResearchDirector (owns PipelineRunner, campaign lifecycle)
  │
  │ 1. research-agent (ResearchStage)
  │    └─ writes: research_config, objectives, hypotheses, iteration_config, gate_policies
  │ ← GATE: HUMAN_REVIEW_OBJECTIVES [timeout 24h → ESCALATE]
  │
  │ 2. builder-agent (BuilderStage) — consumes research_config
  │    ├─ DSL → CFX via sqx_translator → validate via cfx_editor → dispatch via sqcli
  │    └─ writes: cfx_bytes, campaign_id, sqcli_status, export_paths
  │
  │ 3. statistics-agent (StatisticsStage) — consumes export_paths
  │    ├─ compute_all() → aggregate_campaigns() → monte_carlo_bands()
  │    └─ writes: statistics, aggregate_stats, monte_carlo_bands
  │ ← GATE: HUMAN_APPROVE_ITERATION [timeout 24h → ABORT]
  │
  │ 4. reviewer-agent (ReviewStage) — consumes statistics, aggregate_stats
  │    ├─ evaluate() → check_wf_overfitting() → check_mc_overfitting() → compare_benchmark()
  │    └─ writes: review_decision, iteration_proposal, wf_degradation, mc_overfit_flag
  │ ← GATE: HUMAN_APPROVE_PORTFOLIO [timeout 24h → ESCALATE]
  │
  │ 5. portfolio-agent (PortfolioStage) — consumes review_decision, selected_strategies
  │    ├─ build_cfx() → run() → analyze_correlation() → compute_risk_budget() → compose()
  │    └─ writes: portfolio_cfx, portfolio_result, correlation_matrix, risk_allocation
  │ ← GATE: HUMAN_APPROVE_DEPLOY [timeout 12h → HOLD]
  │
  │ 6. deployment-agent (DeployStage) — consumes portfolio_cfx
  │    ├─ package() → generate_jcloud_config() → validate() → deploy(dry_run=True)
  │    └─ writes: jforex_package, jcloud_config, deployment_result
  │ ← GATE: HUMAN_REVIEW_PERFORMANCE [timeout 48h → CONTINUE]
  │
  │ 7. monitoring-agent (MonitorStage) — consumes deployment_result, live_equity
  │    ├─ stream_live() → compute_rolling_metrics() → detect_regime_change() → check_alerts()
  │    └─ writes: rolling_metrics, regime_alerts, performance_alerts
  │
  │ 8. (loop) — if iteration_config.max_iterations not reached → ResearchStage
  │
  Artifacts flow via PipelineContext.artifacts (typed dict).
  Knowledge Lake: knowledge/structured/{campaign_id}/ (campaign artifacts, immutable)
  Engram: agent/{agent_name}/{campaign_id} (decisions, memory, patterns)
```

## File Changes by PR

### PR 1: Foundation & Pipeline Core Extensions

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/pipeline/stages.py` | Modify | Add 8 new abstract stages: `ResearchStage`, `BuilderStage`, `StatisticsStage`, `ReviewStage`, `PortfolioStage`, `DeployStage`, `MonitorStage` |
| `sdk/quantlab/pipeline/stages/gate_interceptor.py` | Create | `GateInterceptorStage` — async callback protocol, timeout, fallback, Engram recording |
| `sdk/quantlab/pipeline/stages/agent_stages.py` | Create | Concrete contracts for all 8 agent stages with `requires`/`provides` |
| `sdk/quantlab/pipeline/runner.py` | Modify | Add `validate_contracts()`; add gate stage injection after each `gate_after` position |
| `sdk/quantlab/pipeline/errors.py` | Modify | `ContractValidationError` already exists — verify `missing_keys`/`stage_names` work |
| `sdk/quantlab/pipeline/config/models.py` | Modify | Ensure `MultiAgentPipelineConfig` has `pipeline` (stages), `agents[]`, `gates[]`, `memory{}`, `risk{}` sections |
| `sdk/quantlab/pipeline/config/pipeline-config.schema.json` | Create | JSON Schema for YAML validation |
| `sdk/quantlab/pipeline/config/loader.py` | Modify | Add `QUANTLAB_PIPELINE_*` env override support already exists — ensure covers all new fields |
| `sdk/quantlab/pipeline/config/migration.py` | Modify | Already has `migrate_v1_to_v2` — verify migration covers new agent/gate/memory/risk fields |
| `sdk/quantlab/pipeline/registry.py` | Modify | Extend `StageRegistry` with agent stage names and `GATE` stage types |

### PR 2: Core Agents

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/research_director.py` | Create | `ResearchDirector` — owns `PipelineRunner`, campaign lifecycle, gate callbacks, rollback |
| `sdk/quantlab/agents/research_agent.py` | Create | `ResearchAgent` — `generate_config()`, `query_knowledge_lake()`, `formulate_hypotheses()` |
| `sdk/quantlab/agents/builder_agent.py` | Create | `BuilderAgent` — translate → validate → license → dispatch → monitor → export |
| `sdk/quantlab/agents/__init__.py` | Create | Agent package init |
| `sdk/quantlab/dsl/models.py` | Modify | Already has `HypothesisConfig`, `IterationConfig`, `GatePolicyConfig` — verify fields match spec |
| `sdk/quantlab/dsl/parser.py` | Modify | Already parses new fields — add validation for `confidence ∈ [0,1]`, `timeout_hours > 0` |

### PR 3: Analysis Agents

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/statistics_agent.py` | Create | `StatisticsAgent` — `compute_statistics()`, `aggregate_campaigns()`, `monte_carlo_bands()`, `assess_robustness()` |
| `sdk/quantlab/agents/reviewer_agent.py` | Create | `ReviewerAgent` — `evaluate()`, `check_wf_overfitting()`, `check_mc_overfitting()`, `compare_benchmark()`, `generate_iteration_proposal()` |
| `sdk/quantlab/agents/portfolio_agent.py` | Create | `PortfolioAgent` — `run_portfolio_master()`, `analyze_correlation()`, `compute_risk_budget()`, `compose_portfolio_cfx()`, `run_walk_forward()` |

### PR 4: Gates & Deployment

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/gates/orchestrator.py` | Create | `HumanGateOrchestrator` — async approval protocol, notification hooks, Engram audit |
| `sdk/quantlab/gates/notifiers.py` | Create | Email/Slack/webhook notification adapters |
| `sdk/quantlab/agents/deployment_agent.py` | Create | `DeploymentAgent` — `package_for_jforex()`, `generate_jcloud_config()`, `deploy()`, dry-run |
| `sdk/quantlab/pipeline/runner.py` | Modify | Gate stage injection at `gate_after` positions |

### PR 5: Monitoring, Persistence & Reporting

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/monitoring_agent.py` | Create | `MonitoringAgent` — live equity ingestion, rolling metrics, regime detection, alerting |
| `sdk/quantlab/agents/memory.py` | Create | `AgentMemoryManager` — Engram save/load/cross-agent query with TTL |
| `sdk/quantlab/knowledge/store.py` | Modify | Add `agent-memory/` to `KNOWLEDGE_DIRS`; add `store_agent_memory()`, `load_agent_memory()` |
| `sdk/quantlab/knowledge/query.py` | Modify | Add `filter_by_agent()`, `search_agent_memory()`, `search_similar_campaigns()` |
| `sdk/quantlab/knowledge/models.py` | Modify | Add `AgentMemoryEntry`, index version → 3 |
| `sdk/quantlab/reporting/generator.py` | Modify | Add agent audit sections, multi-campaign comparison views |
| `sdk/quantlab/reporting/models.py` | Modify | Add `ReportConfig` fields: `include_agent_decisions`, `include_comparison_view` |

### PR 6: CLI, Integration Tests, Docs

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/cli/pipeline_commands.py` | Modify | Add `quantlab pipeline validate`, `quantlab pipeline run` |
| `sdk/quantlab/cli/knowledge_commands.py` | Modify | Add `quantlab agent memory inspect`, `quantlab agent memory query` |
| `sdk/quantlab/cli/main.py` | Modify | Register new commands |
| `tests/integration/test_full_pipeline.py` | Create | E2E dry-run with mock SQX, mock gates, 17 stages |
| `tests/integration/test_smoke.py` | Create | Full smoke test with auto-approve gates |

## Interfaces / Contracts

```python
# GateInterceptorStage — special stage type
class GateInterceptorStage(Stage):
    name: str = "gate"
    gate_id: str  # e.g. "HUMAN_REVIEW_OBJECTIVES"
    requires: list[str] = ["gate_context_artifacts"]
    provides: list[str] = ["gate_decision_{gate_id}"]
    timeout_hours: float
    fallback: str  # ESCALATE | ABORT | HOLD | CONTINUE

    async def execute(self, ctx: PipelineContext) -> GateDecision: ...

# PipelineRunner additions
class PipelineRunner:
    async def run(self, pipeline: Pipeline, ctx: PipelineContext) -> PipelineResult: ...
    def validate_contracts(self, pipeline: Pipeline) -> None:  # NEW
        """Raises ContractValidationError if any stage.requires not satisfied."""

# ResearchDirector
class ResearchDirector:
    def build_pipeline(self, config: ResearchConfig) -> Pipeline: ...
    async def run_campaign(self, campaign_id: str, config: ResearchConfig) -> PipelineResult: ...
    def rollback_campaign(self, campaign_id: str) -> None: ...
    def check_convergence(self) -> bool: ...

# AgentMemoryManager
class AgentMemoryManager:
    def save_decision(self, agent: str, campaign: str, decision: dict) -> None: ...
    def load_memory(self, agent: str, campaign: str) -> list[dict]: ...
    def query_cross_agent(self, pattern: str) -> dict[str, list[dict]]: ...

# HumanGateOrchestrator
class HumanGateOrchestrator:
    async def on_gate(self, gate_id: str, ctx: GateContext) -> GateDecision: ...
    def register_notifier(self, channel: str, notifier: Notifier) -> None: ...
```

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | 8 agent stages: requires/provides match spec | Inspect class attributes — no mocking needed |
| Unit | GateInterceptorStage: pause/resume/fallback/Engram | Mock callback, async timer mock |
| Unit | PipelineRunner.validate_contracts() | Valid pipeline passes, invalid raises ContractValidationError |
| Unit | ResearchDirector.build_pipeline() | Assert 17 stages in correct order |
| Unit | ResearchAgent: generate_config, formulate_hypotheses | Seed knowledge lake, assert ResearchConfig fields |
| Unit | BuilderAgent: translate→validate→dispatch | Mock sqx_translator, cfx_editor, license_manager, sqcli |
| Unit | StatisticsAgent: stats computation, MC bands | Known trades/equity, assert deterministic MC |
| Unit | ReviewerAgent: evaluate, WF overfit, MC breach | Known stats/criteria, assert decision correct |
| Unit | PortfolioAgent: correlation, Kelly, mean-variance | Synthetic returns, assert weights sum to 1 |
| Unit | DeploymentAgent: package, JCloud config, dry-run | Mock jforex_deploy, assert no upload on dry-run |
| Unit | MonitoringAgent: rolling metrics, regime detect | Synthetic equity, assert regime alert fields |
| Unit | AgentMemoryManager: save/load/cross-query | Mock Engram, assert topic keys format |
| Integration | ResearchDirector + 3 agent stages (PR2) | Mock SQX, assert context artifacts flow |
| Integration | Statistics→Reviewer→Portfolio chain (PR3) | Shared PipelineContext, assert each reads prior provides |
| Integration | Full 17-stage pipeline with mock gates | Auto-approve all gates, assert all stages complete |
| Integration | Gate timeout fallback | Async timer fires, assert fallback action |
| Integration | Knowledge Lake agent-memory dirs | Assert 8 agent subdirs created on initialize() |
| E2E | Complete campaign with mock SQX (PR6) | ResearchConfig → deploy simulation → all artifacts |

## Error Handling & Recovery

| Scenario | Mechanism |
|----------|-----------|
| Stage execution failure | Runner catches `StageExecutionError`, marks stage FAILED, skips remaining, returns `PipelineResult.error` |
| Contract validation failure | `PipelineRunner.validate_contracts()` raises before any execution |
| Gate timeout | `GateInterceptorStage` fires fallback (ESCALATE/ABORT/HOLD/CONTINUE), records to Engram |
| SQX license exhaustion | `BuilderAgent` checks before dispatch — `LicenseError` blocks pipeline |
| Campaign timeout (SQX) | `BuilderAgent` sends `sqcli stop`, collects partial exports |
| Knowledge Lake write conflict | Single-writer per campaign (ResearchDirector owns), Git versioning |
| Monitoring stream disconnect | Exponential backoff retry (max 5, 30s base), backfill from JCloud history |
| Full rollback | `ResearchDirector.rollback_campaign()` deletes Knowledge Lake + Engram topics; feature flag `multi_agent_enabled: false` falls back to standalone `CampaignOrchestrator` |

## Migration / Rollout

- **Backward compatibility**: Existing 9-stage pipeline runs unchanged — `StageRegistry` still maps SQX stages, `PipelineRunner` unchanged for non-agent pipelines. Feature flag `multi_agent_enabled` gates the ResearchDirector path.
- **Config migration**: `migration.migrate_v1_to_v2()` converts legacy `PipelineConfig` (dataclass) → `MultiAgentPipelineConfig` (Pydantic) with default gate policies, memory, and risk configs.
- **Knowledge Lake index**: Rebuild needed for `agent-memory/` entries — `rebuild_index()` handles missing fields with `null` defaults (version 2→3).
- **Engram**: No migration needed — new topics use `agent/{agent_name}/{campaign_id}` scheme, disjoint from existing topics.

## Risks

- **Pipeline complexity**: 17 stages with interdependent contracts creates tight coupling — mitigated by `validate_contracts()` run before any stage executes.
- **Async gate deadlock**: Human gate timeout with no configured fallback still blocks pipeline — mitigated by non-optional fallback per gate with default.
- **Knowledge Lake index performance**: Index rebuild over 10k campaigns with agent-memory entries may be slow — mitigated by lazy rebuild and filesystem-as-source-of-truth.
- **SQX process lifecycle**: BuilderAgent must guarantee `sqcli stop` on any error path — mitigated by try/finally in dispatch wrapper.
