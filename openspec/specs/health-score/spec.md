# Health Score Specification

## Purpose

Normalise individual trading metrics (Sharpe, PF, drawdown, etc.) into a single
composable 0–100 health score with categorical bands. Enables strategy
comparison, automated monitoring, and downstream decision systems
(MetaGuardian, SEE).

## Requirements

### HS-REQ-01: HealthState Enum

The system SHALL define a `HealthState` enum with six bands:

| Band | Range |
|------|-------|
| EXCELLENT | 90–100 |
| STABLE | 75–89 |
| OBSERVATION | 60–74 |
| DEGRADING | 45–59 |
| REPLACEMENT_RECOMMENDED | 30–44 |
| IMMEDIATE_WITHDRAWAL | 0–29 |

#### Scenario: Rank a high-performing strategy

- GIVEN an overall_score of 95
- WHEN mapped to HealthState
- THEN the resulting state is EXCELLENT

#### Scenario: Boundary at 90 maps to EXCELLENT

- GIVEN an overall_score of 90
- WHEN mapped to HealthState
- THEN the resulting state is EXCELLENT

#### Scenario: Boundary at 89 maps to STABLE

- GIVEN an overall_score of 89
- WHEN mapped to HealthState
- THEN the resulting state is STABLE

### HS-REQ-02: HealthScore Model

The system SHALL provide a `HealthScore` model containing:

- `overall_score`: float, range 0–100
- `state`: HealthState
- `metric_scores`: dict[str, float] — individual normalised metric contributions
- `period`: str — window label (`"30d"`, `"90d"`, `"1y"`, `"all"`)

#### Scenario: Create a valid HealthScore

- GIVEN overall_score=82, state=STABLE, metric_scores with Sharpe=0.85 and PF=0.78, period="90d"
- WHEN a HealthScore is constructed
- THEN all fields match the input values

#### Scenario: Out-of-range score raises validation

- GIVEN an overall_score of 150
- WHEN a HealthScore is constructed
- THEN a validation error is raised

### HS-REQ-03: HealthScoreCalculator

The system SHALL provide a `HealthScoreCalculator` that:

- Accepts a `StatsResult` (or list for time windows)
- Normalises each metric to 0–1 via configurable functions (sigmoid for ratio
  metrics centred on 1.0, piecewise-linear for capped metrics)
- Applies weighted average → 0–100 overall score
- Returns `HealthScore` with per-metric breakdown
- Infinity maps to max normalised score (1.0); None maps to zero contribution

#### Scenario: Score a single StatsResult

- GIVEN a valid StatsResult with profit_factor=2.5 and sharpe_ratio=1.8
- WHEN the calculator scores it with default weights
- THEN a HealthScore is returned with overall_score in 0–100 and metric_scores containing every non-None metric

#### Scenario: Handle None metrics gracefully

- GIVEN a StatsResult where all fields are None
- WHEN the calculator scores it
- THEN overall_score is 0 and state is IMMEDIATE_WITHDRAWAL

#### Scenario: Handle infinity metrics gracefully

- GIVEN a StatsResult with profit_factor=inf and max_drawdown=0
- WHEN the calculator scores it
- THEN profit_factor contributes max normalised score (1.0) with no error

### HS-REQ-04: HealthWeights

The system SHALL support a configurable `HealthWeights` model with sensible
defaults:

| Metric | Default Weight |
|--------|---------------|
| profit_factor | 0.25 |
| sharpe_ratio | 0.20 |
| sortino_ratio | 0.10 |
| max_drawdown | 0.20 |
| recovery_factor | 0.10 |
| win_rate | 0.05 |
| expectancy_ratio | 0.10 |

#### Scenario: Default weights sum to 1.0

- GIVEN default HealthWeights
- WHEN weights are summed
- THEN the total is 1.0

#### Scenario: Custom override

- GIVEN custom HealthWeights with profit_factor=0.35 and sharpe_ratio=0.10
- WHEN the calculator uses these weights
- THEN the computed score reflects the custom weighting

### HS-REQ-05: Time Windowing

The system SHALL support scoring over different time periods — 30 days, 90
days, 1 year, and all-time — by accepting filtered lists of StatsResult.

#### Scenario: Score each period

- GIVEN StatsResult collections for "30d", "90d", and "1y" periods
- WHEN the calculator scores each period
- THEN a HealthScore with the matching period label is returned for each

#### Scenario: Empty collection raises error

- GIVEN an empty list of StatsResult for "30d"
- WHEN the calculator scores it
- THEN an InsufficientDataError is raised
