# Delta for hypothesis-builder

## ADDED Requirements

### Requirement: Parametric Diversification

`HypothesisBuilder` MUST generate parametric variants for each input hypothesis. For indicator-based hypotheses, the builder SHALL produce variants with alternative parameter values (e.g., RSI periods: 7, 14, 21; BB deviations: 1.5, 2.0, 2.5). The number of variants per hypothesis MUST be configurable via `diversity_factor` in `HypothesisBuilder` config. Variants MUST be deduplicated by parameter tuple before validation.

#### Scenario: Mean-reversion hypothesis diversifies RSI and BB parameters

- GIVEN a hypothesis with `parameters={rsi_period: 14, bb_period: 20, bb_deviation: 2.0}`
- WHEN `build()` runs with `diversity_factor=2`
- THEN at least 3 RSI period variants and 2 BB deviation variants are generated
- AND duplicate parameter tuples are removed

#### Scenario: Diversity factor of 1 preserves single hypothesis

- GIVEN `diversity_factor=1`
- WHEN `build()` runs
- THEN exactly the original parameter set is returned with no variants

### Requirement: Pre-Hypothesis Validation

`HypothesisBuilder` MUST validate each hypothesis before building blocks:
- Indicator names MUST exist in the known SQX indicator registry
- Parameter values MUST fall within documented SQX ranges
- Entry/exit conditions MUST be semantically coherent (e.g., mean-reversion entry MUST NOT use overbought threshold without a trend filter)

Validation failures MUST be logged with the hypothesis name and reason, and the hypothesis MUST be skipped (not built).

#### Scenario: Invalid indicator name is rejected

- GIVEN a hypothesis referencing indicator "RSI_X"
- WHEN validation runs
- THEN the hypothesis is skipped with a log entry "unknown indicator RSI_X"

#### Scenario: Semantically incoherent condition is rejected

- GIVEN a mean-reversion hypothesis with entry `rsi(14) > 70`
- WHEN validation runs
- THEN the hypothesis is skipped with a log entry "incoherent entry for mean-reversion"

## MODIFIED Requirements

### Requirement: RB-2 — Dual Mode Operation

The builder MUST support two modes: `"rule"` and `"llm"`. In `"llm"` mode, the builder MUST inject additional context: similar historical hypotheses from Knowledge Lake (semantic search results), tag-based Sharpe calibration data, and a validation requirements block into the LLM prompt. The mode MAY be overridden per-call.

(Previously: LLM mode used only llm_rationale, source_urls, data_sources)

#### Scenario: LLM mode receives Knowledge Lake context

- GIVEN semantic search returns 2 similar historical hypotheses with tag "mean_reversion" and avg_sharpe=1.4
- WHEN `build()` runs in LLM mode
- THEN the LLM prompt includes the similar hypotheses and calibration data

### Requirement: RB-5 — Output Validation

The builder MUST validate every produced building block. Additionally, the builder MUST validate that generated parameter variants fall within SQX documented ranges and that strategy direction matches hypothesis intent (e.g., "long opportunities" MUST produce LONG or BOTH strategies, never SHORT-only).

(Previously: Validation checked only indicator names, required params, and strategy references)

#### Scenario: Strategy direction matches hypothesis intent

- GIVEN a hypothesis with description "find long opportunities"
- WHEN LLM mode produces a SHORT-only strategy
- THEN validation fails and falls back to Rule mode
