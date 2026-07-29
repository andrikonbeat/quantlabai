# Design: Broker Cost Engine

## Technical Approach

New `sdk/quantlab/costs/` module (models → profiles → engine → collector), following the `stats/` pattern: Pydantic models, pure computation via `CostEngine`, stateless aggregation via `CostCollector`. CostInjectionStage sits before BuilderStage in the 8-agent pipeline, injecting `cost_config` into PipelineContext for SQX/CFX translation. Guardian cost protocol is duck-typed, matching the existing `hasattr` checks in `execution.py` and `market.py`.

## Architecture Decisions

| Decision | Options | Tradeoffs | Choice |
|----------|---------|-----------|--------|
| Module structure | (a) monolithic models.py vs (b) models + engine + profiles + collector | (a) simpler but bloated — `stats/` uses split pattern | **(b) 4 files**: `models.py`, `profiles.py`, `engine.py`, `collector.py` |
| Broker profile storage | (a) Python dicts in-code vs (b) YAML files vs (c) DB | (a) matches `project_builder.py` `_JFOREX_COMMISSION` pattern — no config infra needed; (b) over-engineered for 3 presets; (c) adds deps | **(a) Python dicts in `profiles.py`** — presets as `@classmethod` factories, overrides via `model_copy(update=...)` |
| CFX commission injection | (a) new `CommissionCosts` section in BuildTask [XML] vs (b) post-backtest adjustment | `project_builder.py` confirms SQX does **not** support `type="Money"` in Commissions XML element — commission must be post-processed; spread/slippage already set via Data section attributes | **(b) Commission tracked in artifact for post-processing; spread/slippage injected directly into CFX** via existing Data section attributes |
| Guardian protocol | (a) Formal ABC/Protocol vs (b) duck-typed | Guardians already use `hasattr` + `getattr` (execution.py L247-255, market.py L121-124) — a formal ABC adds ceremony without benefit | **(b) Duck-typed protocol** — implement `get_recent_slippage(symbol)`, `.slippage`, `spread_pips(symbol)`, `collect_all()` |
| Pipeline stage position | (a) Before BuilderStage vs (b) After research, before guardian | Cost config must be available **before** CFX translation (BuilderStage). GuardianEvaluationStage reads `research_config` — cost data is orthogonal | **(a) CostInjectionStage after GuardianEvaluationStage, before BuilderStage** |
| DSL `costs` section | (a) Pydantic model integration vs (b) free-form dict | Pydantic gives validation (known broker profiles), dict gives flexibility. Matching existing `ResearchConfig` pattern (typed models) | **(a) `CostsConfig` Pydantic model**, optional field on `ResearchConfig` |

## Data Flow

```
ResearchConfig (YAML)
       │ costs.broker="dukascopy"
       ▼
PipelineContext.config
       │ config["broker_profile"] = "dukascopy"
       ▼
CostInjectionStage.execute(ctx)
       │ reads config.broker_profile
       │ writes ctx.artifacts["cost_config"] = {engine, collector}
       ▼
GuardianEvaluationStage         BuilderStage (CFX translation)
  │                                │
  │ reads cost_collector           │ reads cost_config
  │ from artifacts["cost_config"]   │ injects spread/slippage
  ▼                                ▼
ExecutionGuardian +               CFX Archive (spread+pips)
MarketGuardian                      │ cost_commission → artifact
                                    ▼
                              SQX Backtest / Retester
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/costs/__init__.py` | Create | Public API re-exports |
| `sdk/quantlab/costs/models.py` | Create | CostModels: CommissionSchema, SwapRule, SlippageProfile, MarketSession, SpreadConfig, CostBreakdown, CostsConfig |
| `sdk/quantlab/costs/profiles.py` | Create | BrokerProfile presets (Dukascopy, IB, OANDA) with real fee schedules |
| `sdk/quantlab/costs/engine.py` | Create | CostEngine: per-trade `compute()`, per-symbol `compute_symbol()`, profile switching |
| `sdk/quantlab/costs/collector.py` | Create | CostCollector: `get_recent_slippage()`, `spread_pips()`, `collect_all()`, session scoring |
| `sdk/quantlab/cfx/models.py` | Modify | Add optional `CommissionCosts: SettingsSection | None = None` to `BuildTask` |
| `sdk/quantlab/cfx/dom.py` | Modify | Add `set_commission_settings()`, `set_spread_settings()` domain methods |
| `sdk/quantlab/dsl/models.py` | Modify | Add `costs: Optional[CostsConfig] = None` to `ResearchConfig` |
| `sdk/quantlab/dsl/parser.py` | Modify | Add `KNOWN_BROKERS` set, validate `costs.broker` in `_build_config()` |
| `sdk/quantlab/pipeline/_stages.py` | Modify | Add `CostInjectionStage` (10th built-in stage) with `requires=["config.broker_profile"]`, `provides=["cost_config"]` |
| `sdk/quantlab/pipeline/base.py` | Modify | Document `cost_config` and `broker_profile` in PipelineContext config |
| `sdk/quantlab/guardian/execution.py` | Modify | Remove stub fallback — use `self.cost_collector` directly when set |
| `sdk/quantlab/guardian/market.py` | Modify | Remove stub fallback — use `cost_collector.collect_all()` directly |
| `sdk/quantlab/sqx/project_builder.py` | Modify | Accept optional `BrokerProfile`, replace hardcoded `_JFOREX_COMMISSION/_SLIPPAGE/_SPREAD` |
| `sdk/quantlab/phase4/retester.py` | Modify | Add `broker_profile` and `cost_config` to `RetesterConfig.__init__()` |
| `sdk/quantlab/phase4/templates.py` | Modify | Inject commission/spread in retester CFX when `broker_profile` is set |

## Interfaces / Contracts

```python
# costs/engine.py
class CostEngine:
    def __init__(self, profile: BrokerProfile) -> None: ...
    def compute(self, symbol: str, volume: float, direction: str,
                session: str | None = None, held_overnight: bool = False) -> CostBreakdown: ...
    def compute_symbol(self, symbol: str) -> dict: ...
    def set_profile(self, profile: str | BrokerProfile) -> None: ...

# costs/collector.py
class CostCollector:
    def __init__(self, engine: CostEngine | None = None, default_spread: float = 1.5) -> None: ...
    def get_recent_slippage(self, symbol: str) -> float: ...
    def spread_pips(self, symbol: str) -> float: ...
    def collect_all(self, symbols: list[str]) -> dict[str, dict]: ...

# pipeline/_stages.py
class CostInjectionStage(Stage):
    name = "cost_injection"
    requires = ["config.broker_profile"]
    provides = ["cost_config"]
    async def execute(self, ctx: PipelineContext) -> dict: ...

# dsl/models.py (new model)
class CostsConfig(BaseModel):
    broker: str  # "dukascopy" | "ib" | "oanda"
    commission_override: CommissionSchema | None = None
    slippage_mode: str = "static"  # static | session
    spread_config: SpreadConfig | None = None
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | All CostModels, 4 commission types, swap calc, slippage | Pure Pydantic — table-driven parameterized tests |
| Unit | CostEngine.compute() for each broker profile | Known-input → expected-output for 3 presets |
| Unit | CostCollector duck-typed protocol methods | Test against mock profile, verify signature |
| Unit | CostInjectionStage I/O contract | Test that requires/provides keys are correct |
| Integration | DSL parser with costs section (valid + invalid broker) | Parse YAML string → verify CostsConfig |
| Integration | Pipeline with CostInjectionStage + BuilderStage | Verify cost_config flows to CFX translation |
| E2E | Full pipeline with cost-aware retester | (Deferred — requires SQX runtime) |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. Cost computation is pure data transformation and pipeline context injection.

## Migration / Rollout

Phase 1: Create `costs/` module (models + profiles + engine) — no changes to existing code. Phase 2: Wire CostCollector into guardians (backward-compatible — existing flow falls back to defaults if no collector). Phase 3: CostInjectionStage + DSL `costs` section (backward-compatible — `costs: None`). Phase 4: CFX injection + project_builder profile acceptance (replace hardcoded defaults with profile-driven). Feature flag: no flag needed — each phase is backward-compatible; existing campaigns without `costs:` continue unchanged.

## Open Questions

- [ ] What is SQX's actual XML format for commission? `project_builder.py` says type="Money" is unsupported — needs research on SQX plugin/CLI-based commission models. Mitigation: commission is a pass-through artifact, applied post-backtest.
- [ ] Volatility-based slippage: depends on DataManager interface — defer dynamic mode to v2; static default for v1.
