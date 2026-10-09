# Proposal: Health Score System

## Intent

Normalise individual trading metrics (Sharpe, PF, drawdown, etc.) into a single
composable 0–100 health score with categorical bands, so strategies can be
compared, monitored automatically, and fed into downstream decision systems
(MetaGuardian, SEE).

## Scope

### In Scope
- `sdk/quantlab/health/` module: `HealthState` enum (6 bands), `HealthScore`
  model, `HealthWeights` model (frozen, defaults sum to 1.0), stateless
  `HealthScoreCalculator`
- Module-level normalisation functions with domain-tuned breakpoints
  (piecewise-linear), `inf → 1.0`, `None → 0.0` contribution
- Handoff/wiring so consumer paths (evolution fitness, MCP bridge/health tools,
  Guardian quality) can compute health scores

### Out of Scope
- Filtering StatsResult collections by time window — caller responsibility
  (design AD-3)
- CLI command for health scoring — consumers embed the calculator directly

## Capabilities

### New Capabilities
- `health-score`: Health state classification, weighted metric aggregation,
  and per-metric breakdown for `StatsResult`

## Approach

1. **`health/models.py`** — `HealthState` (6 bands, exact spec boundaries),
   `HealthScore` (overall_score 0–100, state, metric_scores, period),
   `HealthWeights` (frozen Pydantic, 7 metrics, sum-to-1.0 validator)
2. **`health/weights.py`** — `DEFAULT_WEIGHTS` and 7 module-level
   `normalize_*` functions with piecewise-linear breakpoint tables; `_NORMALIZERS`
   registry and `normalize_metric()` dispatch for loops
3. **`health/calculator.py`** — stateless `HealthScoreCalculator(weights=None)`
   with `compute(stats, period="all") -> HealthScore`; weights injected via
   constructor (default `DEFAULT_WEIGHTS`); `map_score_to_state()` maps 0–100
   to `HealthState`
4. **`health/__init__.py`** — public exports (mirrors `stats/__init__.py`)

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/health/` | New | 4 files: `__init__.py`, `models.py`, `weights.py`, `calculator.py` |
| `sdk/quantlab/evolution/fitness.py` | Modified | Health score available to fitness evaluation |
| `sdk/quantlab/mcp/{bridge,health_tools}.py` | Modified | Health score MCP surface |
| `sdk/quantlab/guardian/quality.py` | Modified | Guardian quality gate consumes health scores |
| `sdk/tests/test_health_score.py` | New | 89 tests, 13 classes (all 5 requirements) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Breakpoint drift vs domain expectations | Low | All breakpoints centralised in `weights.py` with named functions; tests lock key values |
| Weight sum ≠ 1.0 | Low | Frozen Pydantic model validates sum on construction |

## Verification Criteria

- All 5 spec requirements (HS-REQ-01..05) are implemented and scenario-covered
- `SQX_FORCE_MOCK=1 python3 -m pytest -q sdk/tests/test_health_score.py` → green
- Full SDK suite green — zero regressions