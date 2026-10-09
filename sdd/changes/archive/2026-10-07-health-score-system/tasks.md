# Tasks: Health Score System

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~350 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |
| Chain strategy | size-exception |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

## Phase 1: Foundation

- [x] 1.1 Create `sdk/quantlab/health/models.py` — HealthState enum (6 bands 0–100), HealthScore model (overall_score, state, metric_scores, period), HealthWeights model (7 metrics, frozen, defaults sum to 1.0)
- [x] 1.2 Create `sdk/quantlab/health/weights.py` — piecewise-linear breakpoint tables for PF, Sharpe, Sortino, MDD, RecoveryFactor, WinRate, Expectancy; `DEFAULT_WEIGHTS` (frozen HealthWeights) + 7 module-level `normalize_*` functions (implemented as `weights.py:17`, `weights.py:66–142`)

## Phase 2: Core Implementation

- [x] 2.1 Create `sdk/quantlab/health/calculator.py` — HealthScoreCalculator with 7 normalize_* methods; piecewise-linear interpolation, inf→1.0, None→0.0
- [x] 2.2 Implement `compute(stats, period)` with weights injected via constructor — iterate StatsResult metrics, normalize, weighted average → 0–100, `map_score_to_state()` → HealthState (implemented as `calculator.py:43,54`)

## Phase 3: Integration

- [x] 3.1 Create `sdk/quantlab/health/__init__.py` — export HealthState, HealthScore, HealthWeights, HealthScoreCalculator; match stats/__init__.py pattern

## Phase 4: Testing

- [x] 4.1 Create `sdk/tests/test_health_score.py` — HealthState boundary tests (89→STABLE, 90→EXCELLENT), model validation (score>100 raises); 89 tests across 13 classes (repo test layout, not `tests/`)
- [x] 4.2 Add normalize tests — each of 7 metrics: zero, midpoint, inf, None; verify piecewise-linear output
- [x] 4.3 Add calculator tests — full score from known StatsResult, weighted average math, all-None→0/IMMEDIATE_WITHDRAWAL, inf→max
- [x] 4.4 Add time-windowing tests — period label pass-through (2026-10-07: HS-REQ-05 amended — empty-collection raising is caller responsibility per AD-3; `InsufficientDataError` lives only in `stats/engine.py`)
