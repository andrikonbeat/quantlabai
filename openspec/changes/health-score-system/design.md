# Design: Health Score System

## Technical Approach

New `sdk/quantlab/health/` module — pure computation layer that normalises
`StatsResult` metrics into a composable 0–100 health score with categorical
bands. Stateless calculator follows the same pattern as `StatisticsEngine`:
receive data + config, return model. Zero IO, zero side effects, zero changes
to existing code.

## Architecture Decisions

### Decision: Piecewise-linear over sigmoid normalisation

| Option | Tradeoff |
|--------|----------|
| Sigmoid (logistic) | Smooth but non-intuitive — hard to tune breakpoints |
| Piecewise-linear | Predictable, domain-expert-friendly, easy to debug |
| **Chosen: Piecewise-linear** | Trading metrics have domain-specific thresholds (e.g. PF=1.5 is meaningful) that map naturally to breakpoints |

### Decision: Weight defaults as a Pydantic model

| Option | Tradeoff |
|--------|----------|
| dict literal | No validation, no self-documenting schema |
| frozen dataclass | No field metadata |
| **Chosen: Pydantic BaseModel** | Consistent with `StatsResult`, validates sum-to-1.0, self-documenting |

### Decision: `period` as metadata string on HealthScore

| Option | Tradeoff |
|--------|----------|
| Internal time-windowing | Calculator needs state, couples to data layer |
| **Chosen: Pass-through string** | Caller already has filtered StatsResult lists; calculator just stamps the label |

## Data Flow

```
StatsResult ──→ HealthScoreCalculator.score() ──→ HealthScore
                    │                                   │
                    ├── normalize(profit_factor)         ├── overall_score (0–100)
                    ├── normalize(sharpe_ratio)          ├── state (HealthState)
                    ├── normalize(max_drawdown)          ├── metric_scores (dict)
                    └── weighted_average()               └── period (label)
```

Per-period scoring:
```
StatsResult[30d] ──→ score() ──→ HealthScore(period="30d")
StatsResult[90d] ──→ score() ──→ HealthScore(period="90d")
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/health/__init__.py` | Create | Public exports: HealthState, HealthScore, HealthWeights, HealthScoreCalculator |
| `sdk/quantlab/health/models.py` | Create | HealthState enum, HealthScore model, HealthWeights model |
| `sdk/quantlab/health/calculator.py` | Create | HealthScoreCalculator — normalise + weight + score |
| `sdk/quantlab/health/weights.py` | Create | DefaultWeightConfig, normalisation function map |
| `tests/test_health_score.py` | Create | Unit tests for all 5 requirements |

## Interfaces

```python
# models.py
class HealthState(str, Enum):
    EXCELLENT = "excellent"                # 90–100
    STABLE = "stable"                      # 75–89
    OBSERVATION = "observation"            # 60–74
    DEGRADING = "degrading"                # 45–59
    REPLACEMENT_RECOMMENDED = "replacement_recommended"  # 30–44
    IMMEDIATE_WITHDRAWAL = "immediate_withdrawal"        # 0–29

class HealthScore(BaseModel):
    overall_score: float = Field(ge=0, le=100)
    state: HealthState
    metric_scores: dict[str, float]
    period: str = "all"

class HealthWeights(BaseModel):
    profit_factor: float = 0.25
    sharpe_ratio: float = 0.20
    sortino_ratio: float = 0.10
    max_drawdown: float = 0.20
    recovery_factor: float = 0.10
    win_rate: float = 0.05
    expectancy_ratio: float = 0.10

    model_config = ConfigDict(frozen=True)
```

```python
# calculator.py
class HealthScoreCalculator:
    WEIGHT_TOTAL: ClassVar[float] = 1.0

    def score(
        self,
        stats: StatsResult,
        weights: HealthWeights | None = None,
        period: str = "all",
    ) -> HealthScore: ...

    def normalize_profit_factor(self, pf: float | None) -> float: ...
    def normalize_sharpe_ratio(self, sr: float | None) -> float: ...
    def normalize_sortino_ratio(self, sr: float | None) -> float: ...
    def normalize_max_drawdown(self, mdd: float | None) -> float: ...
    def normalize_recovery_factor(self, rf: float | None) -> float: ...
    def normalize_win_rate(self, wr: float | None) -> float: ...
    def normalize_expectancy_ratio(self, er: float | None) -> float: ...

    @staticmethod
    def map_score_to_state(score: float) -> HealthState: ...
```

Normalisation breakpoints (domain-tuned):

| Metric | None | Points |
|--------|------|--------|
| profit_factor | → 0.0 | (0.0,0.0), (1.0,0.3), (1.5,0.6), (2.0,0.8), (3.0,0.95), inf→0.95 |
| sharpe_ratio | → 0.0 | (0.0,0.3), (1.0,0.6), (2.0,0.85), (3.0,0.95), inf→0.95 |
| max_drawdown | → 0.0 | (0.0,1.0), (5.0,0.9), (10.0,0.7), (20.0,0.4), (30.0,0.1), (50.0,0.0) |
| win_rate | → 0.0 | (0.0,0.0), (80.0,0.95), (100.0,0.95), inf→0.95 |
| sortino_ratio | → 0.0 | Same as sharpe but shifted: (0.0,0.2), (1.0,0.5), (2.0,0.8), (3.0,0.95), inf→0.95 |
| recovery_factor | → 0.0 | (0.0,0.0), (1.0,0.3), (2.0,0.6), (5.0,0.85), (10.0,0.95), inf→0.95 |
| expectancy_ratio | → 0.0 | (0.0,0.0), (0.5,0.3), (1.0,0.6), (2.0,0.85), (5.0,0.95), inf→0.95 |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | HealthState band mapping | Boundary tests at every transition point (89→90, 29→30, etc.) |
| Unit | Normalisation functions | Each metric: 0, mid, inf, None; verify piecewise-linear interpolation |
| Unit | HealthScoreCalculator | Full score from known StatsResult; verify weighted average math |
| Unit | HealthWeights validation | Default sum = 1.0; custom override reflects correctly |
| Unit | Edge cases | All-None → score 0, IMMEDIATE_WITHDRAWAL; inf → max score |
| Unit | Time-windowing | Period label pass-through; empty list raises InsufficientDataError |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

Pure additive change. No migration, no feature flags, no rollout phases. New module is importable immediately. Existing tests must pass with zero regressions.

## Open Questions

None.

## Workload Forecast

Authored additions: ~350 lines across 5 files. Well within 400-line budget.
Delivery strategy: single PR acceptable.
Chained PRs not required.
