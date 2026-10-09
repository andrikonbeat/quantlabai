# Proposal: Broker Cost Engine

## Intent

Broker costs (commissions, swaps, slippage, spreads) are hardcoded in `sqx/project_builder.py` and absent from backtests, simulations, and guardians. Without a dedicated cost engine, strategy performance is unrealistic and guardian risk assessments ignore trading costs — invalidating both optimization and live execution.

## Scope

### In Scope
- **Cost Models**: Commission (fixed, %, tiered), Swap (long/short, triple), Slippage (volatility/liquidity/session), Spread models
- **Broker Profiles**: Configurable profiles for Dukascopy, IB, OANDA with real cost parameters
- **Cost Engine**: Per-trade and per-symbol cost computation
- **Cost Collector**: Implementation for ExecutionGuardian + MarketGuardian
- **DSL Extension**: `costs` section in ResearchConfig YAML
- **Pipeline Integration**: CostInjectionStage in multi-agent pipeline
- **Retester Integration**: Cost-aware Monte Carlo and Walk-Forward via CFX injection

### Out of Scope
- Real-time data feed for variable slippage
- Cost dashboard / visualization UI
- Automatic broker API commission fetching

## Capabilities

### New Capabilities
- `broker-cost-models`: Pydantic models for CommissionSchema, SwapRule, SlippageProfile, MarketSession, SpreadConfig
- `broker-profiles`: Preset profiles for Dukascopy, IB, OANDA with real commission/swap/spread/slippage params
- `cost-engine`: CostEngine computing total trade cost per symbol, static and volatility-based pricing, session-aware spreads
- `cost-collector`: CostCollector implementing the interface expected by ExecutionGuardian (get_recent_slippage, .slippage) and MarketGuardian (collect_all, spread_pips, session scoring)
- `cost-pipeline-integration`: CostInjectionStage for pipeline, `costs` section in ResearchConfig DSL, cost params in RetesterConfig

### Modified Capabilities
None

## Approach

Create `sdk/quantlab/costs/` module (models → engine → profiles → collector). Follow patterns from `guardian/` and `stats/`. Connect via pipeline stage; inject costs into CFX before SQX backtest. Guardians receive real CostCollector instead of stub.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/costs/` | New | Full module structure |
| `guardian/execution.py` | Modified | Wire real CostCollector |
| `guardian/market.py` | Modified | Use collector for spreads + session |
| `dsl/models.py` | Modified | costs section in ResearchConfig |
| `dsl/parser.py` | Modified | Parse costs YAML section |
| `sqx/project_builder.py` | Modified | Accept BrokerProfile, drop hardcoded defaults |
| `pipeline/base.py` | Modified | Carry cost config in PipelineContext |
| `phase4/retester.py` | Modified | Cost params in RetesterConfig |
| `cfx/models.py` | Modified | Commission fields in BuildTask |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| CFX commission format undocumented | Med | Research SQX template; fallback to post-backtest adjustment |
| Guardian interface divergence | Low | Define ABC/protocol before implementation |
| Volatility data dependency | Med | Static slippage by default; dynamic mode deferred |

## Rollback Plan

Remove `costs/` module. Restore `project_builder.py` hardcoded defaults. Revert guardian wiring. DSL parser ignores unknown `costs` section gracefully.

## Dependencies

- SQX CFX commission XML format (research in design phase)
- DataManager interface for volatility-based slippage (optional for v1)

## Success Criteria

- [ ] Cost models pass tests for all commission types, swaps, slippage profiles
- [ ] Broker profiles match published fee schedules
- [ ] Guardians receive real CostCollector with correct spread/slippage
- [ ] DSL parses `costs` section and applies to pipeline config
- [ ] 90%+ test coverage on new `costs/` module
- [ ] Zero regression in existing 531 tests
