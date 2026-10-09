# Tasks: Broker Cost Engine

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~950–1050 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 → PR 4 |
| Delivery strategy | force-chained |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Cost models + broker profiles | PR 1 | `pytest tests/unit/costs/test_models.py tests/unit/costs/test_profiles.py -v` | N/A — pure Pydantic, no runtime deps | `git revert` of costs/ models + profiles |
| 2 | CostEngine + CostCollector | PR 2 | `pytest tests/unit/costs/test_engine.py tests/unit/costs/test_collector.py -v` | `from quantlab.costs import CostEngine, CostCollector; c=CostEngine(p); c.compute("EURUSD",100000,"LONG")` | `git revert` of engine + collector |
| 3 | DSL costs + CostInjectionStage | PR 3 | `pytest tests/unit/dsl/test_costs_parsing.py tests/unit/pipeline/test_cost_stage.py -v` | `from quantlab.dsl.parser import parse_yaml_string; parse_yaml_string("costs:{broker:dukascopy}")` | `git revert` of dsl/ + pipeline/ changes |
| 4 | Guardian wiring + CFX injection | PR 4 | `pytest tests/unit/guardian/ tests/unit/cfx/test_commission.py tests/unit/phase4/ -v` | N/A — requires SQX runtime for CFX E2E; unit tests prove contract | `git revert` of guardian/ + cfx/ + phase4/ + sqx/ changes |

## Phase 1: Cost Models + Broker Profiles

- [x] 1.1 Create `costs/__init__.py` with public re-exports for models + profiles
- [x] 1.2 Create `costs/models.py` with CommissionSchema, SwapRule, SlippageProfile, MarketSession, SpreadConfig, CostBreakdown, CostsConfig
- [x] 1.3 Create `costs/profiles.py` with BrokerProfile dataclass + factory methods (dukascopy, interactive_brokers, oanda)
- [x] 1.4 Write unit tests: models coverage (all commission types, swaps, slippage modes, session-aware spreads per spec)

## Phase 2: Cost Engine + Collector

- [x] 2.1 Create `costs/engine.py` with CostEngine: `compute()`, `compute_symbol()`, `set_profile()`
- [x] 2.2 Create `costs/collector.py` with CostCollector: `get_recent_slippage()`, `spread_pips()`, `collect_all()`, `.slippage`
- [x] 2.3 Write unit tests: engine per-broker known-cost assertions, collector duck-type protocol conforming to guardian hasattr checks

## Phase 3: DSL + Pipeline Integration

- [x] 3.1 Add `costs: Optional[CostsConfig]` to `dsl/models.py` ResearchConfig + import CostsConfig
- [x] 3.2 Add `KNOWN_BROKERS` set + `costs.broker` validation to `dsl/parser.py` `_build_config()`
- [x] 3.3 Create `CostInjectionStage` in `pipeline/_stages.py` (requires: config.broker_profile, provides: cost_config)
- [x] 3.4 Update `pipeline/base.py` PipelineContext docstring documenting cost_config and broker_profile
- [x] 3.5 Write integration tests: DSL parse with valid/invalid broker, stage I/O contract verification

## Phase 4: Guardian Wiring + CFX Injection

- [x] 4.1 Add `CommissionCosts` optional SettingsSection to `cfx/models.py` BuildTask
- [x] 4.2 Add `set_commission_settings()` + `set_spread_settings()` domain methods to `cfx/dom.py` + update `__all__`
- [x] 4.3 Wire real CostCollector in `guardian/execution.py` — remove stub fallback, use self.cost_collector when set
- [x] 4.4 Wire real CostCollector in `guardian/market.py` — use cost_collector.collect_all() directly, remove stub
- [x] 4.5 Accept optional `BrokerProfile` in `sqx/project_builder.py` create_project(), replacing `_JFOREX_COMMISSION/SLIPPAGE/SPREAD` defaults
- [x] 4.6 Add `broker_profile` and `cost_config` params to `phase4/retester.py` RetesterConfig.__init__()
- [x] 4.7 Inject commission/spread in `phase4/templates.py` build_retester_cfx() when broker_profile is set
- [x] 4.8 Write tests: CFX round-trip with CommissionCosts, guardian collector integration
