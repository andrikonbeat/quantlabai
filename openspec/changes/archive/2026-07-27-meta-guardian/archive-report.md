# Archive Report: meta-guardian

## Change
**meta-guardian** — Status: **COMPLETE**

## Summary

Implemented the MetaGuardian governance layer that supervises all strategies, risk, and market conditions. The system provides 6 independent guardian modules, a central orchestrator with a 5-state machine, per-strategy state tracking, configurable action hooks, and full pipeline/DSL integration.

## Test Results

**47 passed** in 0.44s — all components fully covered:
- `test_models.py` — 8 tests (enums, models, GuardianResult, MetaGuardianConfig)
- `test_market.py` — 5 tests (initialization, scoring, exception handling)
- `test_risk.py` — 3 tests (initialization, scoring, edge cases)
- `test_portfolio.py` — 5 tests (correlation, ENOS, concentration, exceptions, edge cases)
- `test_capital.py` — 5 tests (allocation, valid data, exceptions)
- `test_quality.py` — 5 tests (health score reuse, exceptions, edge cases)
- `test_execution.py` — 7 tests (broker health, cost collector, disconnected broker, exceptions)
- `test_orchestrator.py` — 4 tests (initialization, evaluate with no/mock guardians, properties)
- `test_integration.py` — 5 tests (pipeline with guardian_enabled, DSL translator with guardian_state)

## Files Created/Modified

### New Module (`sdk/quantlab/guardian/`)
| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | ~20 | Public API exports |
| `models.py` | ~150 | GuardianType, GuardianStatus, GuardianResult, PortfolioState, StrategyState, MetaGuardianConfig |
| `base.py` | ~40 | Abstract BaseGuardian class |
| `market.py` | ~100 | MarketGuardian — regime, volatility, liquidity, session scoring |
| `risk.py` | ~90 | RiskGuardian — drawdown, Sharpe, exposure, Kelly monitoring |
| `portfolio.py` | ~110 | PortfolioGuardian — correlation, ENOS, concentration |
| `capital.py` | ~70 | CapitalGuardian — dynamic capital allocation |
| `quality.py` | ~70 | QualityGuardian — Health Score reuse |
| `execution.py` | ~130 | ExecutionGuardian — broker health, latency, slippage |
| `orchestrator.py` | ~250 | MetaGuardianOrchestrator — state machine, hooks, score aggregation |

### Modified Files
| File | Change |
|------|--------|
| `sdk/quantlab/agents/builder_agent.py` | Merges `guardian_state` from pipeline context into ResearchConfig |
| `sdk/quantlab/pipeline/runner.py` | Auto-inserts GuardianEvaluationStage when `guardian_enabled=True` |
| `sdk/quantlab/dsl/models.py` | Added `guardian_state` field to ResearchConfig |

### New Tests (`sdk/tests/test_guardian/`)
| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 0 | Package init |
| `test_models.py` | ~100 | Enum, model, and config tests |
| `test_market.py` | ~80 | MarketGuardian tests |
| `test_risk.py` | ~50 | RiskGuardian tests |
| `test_portfolio.py` | ~80 | PortfolioGuardian tests |
| `test_capital.py` | ~70 | CapitalGuardian tests |
| `test_quality.py` | ~70 | QualityGuardian tests |
| `test_execution.py` | ~100 | ExecutionGuardian tests |
| `test_orchestrator.py` | ~70 | MetaGuardianOrchestrator tests |
| `test_integration.py` | ~90 | Pipeline + DSL integration tests |

### New Specs (`openspec/specs/`)
| Spec | Purpose |
|------|---------|
| `meta-guardian/spec.md` | MetaGuardian system requirements and scenarios |

## Specs Synced

| Domain | Action | Details |
|--------|--------|---------|
| meta-guardian | Created | 6 requirements with scenarios for guardians, state machine, hooks, config |

## Deviations from Design

1. **`escalate_to` field NOT in GuardianConfig** — The original design referenced an `escalate_to` field in guardian config for alert escalation, but this was handled implicitly through action hooks rather than an explicit config field. Action hooks provide more flexibility.

2. **`HOLD` fallback not implemented** — The design mentioned HOLD as a state machine fallback, but the implementation uses ABORT/CONTINUE/ESCALATE only. HOLD was deemed unnecessary since the state machine already handles pausing through QUARANTINE state.

3. **ExecutionGuardian exception semantics** — Design called for graceful degradation on broker errors; implementation raises exceptions that propagate to RED status. This is more correct because silent degradation could mask critical broker issues.

## Lessons Learned

- The abstract `BaseGuardian` with `check()` + `guardian_type()` pattern proved clean and extensible — all 6 guardians follow the same contract.
- The state machine with hysteresis (5 consecutive checks for recovery) prevents state thrashing in volatile market conditions.
- Integrating guardian state into the pipeline via `GuardianEvaluationStage` auto-injection keeps the pipeline runner clean and the guardian logic decoupled.
- Action hooks as a list of callables is more flexible than a fixed hook system — consumers can register arbitrary actions on any state transition.

## Source of Truth Updated

The following specs now reflect the new meta-guardian behavior:
- `openspec/specs/meta-guardian/spec.md`

## SDD Cycle Complete

The change has been fully planned, implemented, verified (47/47 tests pass), and archived. Ready for the next change.
