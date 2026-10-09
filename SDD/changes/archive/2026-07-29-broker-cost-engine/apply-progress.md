# Apply Progress — PR 1: Cost Models + Broker Profiles

**Change**: broker-cost-engine
**PR**: 1 (stacked-to-main)
**Batch**: Tasks 1.1-1.4
**Mode**: Strict TDD
**Date**: 2026-07-29

## Completed Tasks

- [x] 1.1 Create `costs/__init__.py` with public re-exports for models + profiles
- [x] 1.2 Create `costs/models.py` with CommissionSchema, SwapRule, SlippageProfile, MarketSession, SpreadConfig, CostBreakdown, CostsConfig
- [x] 1.3 Create `costs/profiles.py` with BrokerProfile dataclass + factory methods (dukascopy, interactive_brokers, oanda)
- [x] 1.4 Write unit tests: models coverage (all commission types, swaps, slippage modes, session-aware spreads per spec)

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/costs/__init__.py` | **Created** | Public re-exports for CommissionSchema, SwapRule, SlippageProfile, MarketSession, SpreadConfig, CostBreakdown, CostsConfig, BrokerProfile, CommissionType, SlippageMode |
| `sdk/quantlab/costs/models.py` | **Created** | Pydantic models: CommissionSchema (fixed/percent/tiered with compute()), SwapRule (long/short, triple day), SlippageProfile (static/session), MarketSession, SpreadConfig (session-aware), CostBreakdown, CostsConfig |
| `sdk/quantlab/costs/profiles.py` | **Created** | BrokerProfile dataclass with factory methods: dukascopy() ($3/100k tiered), interactive_brokers() ($0.50-2.00/contract tiered), oanda() (spread-only). with_overrides() for selective customisation |
| `tests/costs/__init__.py` | **Created** | Test package marker |
| `tests/costs/test_models.py` | **Created** | 36 tests: CommissionSchema (fixed 3, percent 3, tiered 4, validation 2), SwapRule (6), SlippageProfile (6), MarketSession (3), SpreadConfig (5), CostBreakdown (2), CostsConfig (2) |
| `tests/costs/test_profiles.py` | **Created** | 19 tests: Dukascopy (5), IB (5), OANDA (4), Sessions (2), Custom overrides (4) |

### Changed Lines Budget

- Created files total: ~340 lines (well within the 400-line budget)
- No existing files modified in this PR

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | N/A (structural) | Structural | N/A (new) | N/A (structural) | ✅ Created | ➖ Skipped (structural) | ✅ Clean |
| 1.2 | `tests/costs/test_models.py` | Unit | N/A (new) | ✅ Written (36 tests) | ✅ Passed | ✅ 3-6 cases per behavior | ✅ Clean |
| 1.3 | `tests/costs/test_profiles.py` | Unit | N/A (new) | ✅ Written (19 tests) | ✅ Passed | ✅ 4-5 cases per profile | ✅ Clean |
| 1.4 | Both test files | Unit | N/A (new) | ✅ Written (55 tests) | ✅ Passed | ✅ All spec scenarios | ✅ Clean |

## Work Unit Evidence

| Evidence | Required value |
|----------|---------------|
| Focused test command and exact result | `python3 -m pytest tests/costs/test_models.py tests/costs/test_profiles.py -v` → 55 passed, 0 failed |
| Runtime harness command/scenario and exact result | N/A — pure Pydantic models and dataclass profiles, no runtime dependencies or I/O boundary |
| Rollback boundary | `git revert` of `sdk/quantlab/costs/` (4 files) + `tests/costs/` (3 files) — 7 files total, no existing code affected |

### Test Summary

- **Total tests written**: 55
- **Total tests passing**: 55
- **Layers used**: Unit (55)
- **Approval tests**: None — no refactoring tasks
- **Pure functions created**: 5 (`CommissionSchema.compute`, `SwapRule.compute`, `SlippageProfile.get_slippage`, `SpreadConfig.effective_spread`, `BrokerProfile.with_overrides`)

## Deviations from Design

None — implementation matches design specification exactly.

The design called for 4 files (models, profiles, engine, collector) in the `costs/` module. Tasks 1.1-1.4 cover the first two of those plus tests, as specified for PR 1.

## Issues Found

None.

## Remaining Tasks (for PR 2+)

- [ ] 2.1 Create `costs/engine.py` with CostEngine: `compute()`, `compute_symbol()`, `set_profile()`
- [ ] 2.2 Create `costs/collector.py` with CostCollector: `get_recent_slippage()`, `spread_pips()`, `collect_all()`, `.slippage`
- [ ] 2.3 Write unit tests: engine per-broker known-cost assertions, collector duck-type protocol conforming to guardian hasattr checks
- [ ] 3.1-4.8 (DSL + Pipeline + Guardian + CFX)

## Workload / PR Boundary

- Mode: stacked-to-main (PR 1 of 4)
- Current work unit: Unit 1 — Cost models + broker profiles
- Boundary: Creates `costs/` module (models + profiles only) + matching tests. Zero modifications to existing files.
- Estimated review budget: ~340 lines (within 400-line limit)

## Status

4/4 tasks complete. Ready for verify.
