# Tag Calibrator Specification

## Purpose

Computes Sharpe and win-rate distributions by strategy tag and adjusts HypothesisConfig confidence scores using percentile calibration, improving hypothesis quality for known strategy archetypes.

## Requirements

### Requirement: REQ-F1-05 Tag Distribution Calculation

The system MUST query Knowledge Lake for campaigns matching a hypothesis's strategy tags and compute:
- avg_sharpe_by_tag: mean Sharpe per tag
- win_rate_by_tag: mean win rate per tag
- sample_count_by_tag: number of campaigns per tag

Results SHALL be cached per tag set to avoid repeated queries.

#### Scenario: Known tag has distributions

- GIVEN Knowledge Lake contains 50 campaigns tagged strategy=trend
- WHEN TagCalibrator.calibrate() runs for a trend hypothesis
- THEN avg_sharpe_by_tag and win_rate_by_tag are returned with sample_count ≥ 1

#### Scenario: Unknown tag returns empty

- GIVEN no campaigns match the hypothesis tags
- WHEN TagCalibrator.calibrate() runs
- THEN distributions are empty
- AND calibration degrades gracefully

### Requirement: REQ-F1-06 Confidence Adjustment

The system MUST adjust HypothesisConfig.confidence based on tag-matched historical percentiles:
- confidence = base_confidence × tag_sharpe_percentile
- percentile ∈ [0.1, 1.0] based on where the tag's mean Sharpe falls in the global distribution

#### Scenario: High-performing tag boosts confidence

- GIVEN tag=trend has avg_sharpe=1.8 (90th percentile globally)
- WHEN confidence is calibrated
- THEN confidence is multiplied by 0.9
- AND the adjusted value is stored in HypothesisConfig

#### Scenario: Low-performing tag reduces confidence

- GIVEN tag=scalping has avg_sharpe=0.3 (20th percentile globally)
- WHEN confidence is calibrated
- THEN confidence is multiplied by 0.2
- AND the hypothesis is flagged for additional review

### Requirement: REQ-F1-07 Graceful Degradation

The system MUST handle untagged or sparsely tagged campaigns without failing:
- If no tags match, use global historical averages
- If sample count < 5, apply Bayesian smoothing (prior = global mean)

#### Scenario: Sparse tag data uses prior

- GIVEN tag=mean_reversion has only 2 campaigns
- WHEN calibration runs with minimum_samples=5
- THEN Bayesian smoothing blends tag mean with global prior
- AND no exception is raised

#### Scenario: No tags fallback to global

- GIVEN a hypothesis with no strategy tags
- WHEN TagCalibrator.calibrate() runs
- THEN global mean Sharpe and win rate are used
- AND the hypothesis confidence is adjusted conservatively
