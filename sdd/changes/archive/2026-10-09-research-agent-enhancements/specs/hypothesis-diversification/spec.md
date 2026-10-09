# Hypothesis Diversification Specification

## Purpose

Parametric variant generation and pre-validation pipeline for research hypotheses. Ensures the LLM or rule engine explores multiple indicator configurations per hypothesis and filters out incoherent proposals before they reach the builder stage.

## Requirements

### Requirement: Variant Generation

For each `HypothesisConfig` with indicator parameters, the diversification engine MUST generate variants by perturbing parameters within documented SQX ranges. The number of variants MUST be controlled by `diversity_factor`:
- `1`: original only
- `2`: original + 1 variant per parameter
- `3`: original + 2 variants per parameter

The engine MUST NOT generate duplicate parameter tuples. Parameters without documented ranges MUST use ±20% of the original value as bounds.

#### Scenario: RSI period diversifies to 7, 14, 21

- GIVEN a hypothesis with `parameters={rsi_period: 14}` and `diversity_factor=2`
- WHEN variant generation runs
- THEN variants include `{rsi_period: 7}` and `{rsi_period: 21}`

#### Scenario: BB deviation diversifies within range

- GIVEN a hypothesis with `parameters={bb_period: 20, bb_deviation: 2.0}` and documented range `[1.0, 3.0]`
- WHEN variant generation runs with `diversity_factor=2`
- THEN `bb_deviation` variants are 1.5 and 2.5 (within bounds)

### Requirement: Pre-Validation Pipeline

Before any hypothesis is accepted, the system MUST run a validation pipeline:
1. **Indicator existence**: all indicator names MUST exist in the SQX registry
2. **Parameter range**: all parameter values MUST fall within documented SQX ranges (or ±20% heuristic if undocumented)
3. **Semantic coherence**: entry/exit conditions MUST match strategy type
   - Mean-reversion: entry MUST use oversold threshold; exit MUST use overbought or middle band
   - Breakout: entry MUST use upper resistance / lower support break
   - Trend-following: MUST include trend filter (EMA, ADX, etc.)
4. **Direction consistency**: strategy direction MUST align with hypothesis description keywords

Failures MUST be logged with `hypothesis_name`, `validation_stage`, and `reason`. The hypothesis MUST be skipped, not built.

#### Scenario: Unknown indicator rejected

- GIVEN a hypothesis with indicator "RSI_X"
- WHEN pre-validation runs
- THEN the hypothesis is skipped with log: "unknown indicator RSI_X"

#### Scenario: Mean-reversion without oversold entry rejected

- GIVEN a mean-reversion hypothesis with entry `rsi(14) > 70`
- WHEN semantic coherence check runs
- THEN the hypothesis is skipped with log: "incoherent entry for mean-reversion"

### Requirement: Validation Configuration

The validation rules MUST be configurable via `ResearchConfig.validation_policy`:
- `strict`: all checks MUST pass; any failure skips the hypothesis
- `lenient`: indicator existence and parameter range MUST pass; semantic coherence is a warning
- `off`: no pre-validation; all hypotheses proceed to builder

#### Scenario: Lenient mode warns but builds

- GIVEN validation_policy="lenient" and a semantically incoherent hypothesis
- WHEN pre-validation runs
- THEN a warning is logged and the hypothesis is still built
