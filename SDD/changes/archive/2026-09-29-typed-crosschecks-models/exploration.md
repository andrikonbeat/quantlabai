# Exploration: typed-crosschecks-models

## Current State
CrossChecks handling in the QuantLab SDK CFX module currently relies on `CrossChecksConfig` with only a `raw_xml` passthrough field. There is no typed model abstraction for the CrossChecks XML section, which forces downstream consumers to parse XML via regex and string manipulation.

## Affected Areas
- `sdk/quantlab/cfx/models.py` — defines `CrossChecksConfig`; needs typed model fields
- `sdk/quantlab/cfx/reader.py` — reads CFX XML; must populate typed models
- `sdk/quantlab/cfx/writer.py` — writes CFX XML; must serialize typed models
- `sdk/quantlab/cfx/patcher.py` — patches CFX XML; must work with typed fields
- `customproject/renderers.py` — renders project files; affected by model shape changes
- `translate/translator.py` — translates CFX structures; needs typed input/output
- `phase4/templates.py` — templates may reference CrossChecks fields
- `agents/adaptive_retest_agent.py` — uses regex on `raw_xml` to extract signals
- `sqx/project_builder.py` — maps 16 BuildConfig fields to CrossChecks XML via regex
- `tests/cfx/` — reader/writer/patcher tests for CFX module
- `tests/phase4/` — template and translation tests
- `tests/agents/` — adaptive retest agent tests

## Approaches
1. **Dual-mode typed models with raw_xml fallback**
   - Introduce typed dataclasses/pydantic models for Generic and AutomaticRetest dialects
   - Keep `raw_xml` field for backward compatibility and unknown elements
   - Reader populates typed fields when possible, falls back to raw_xml
   - Writer serializes typed fields, preserves raw_xml extras
   - Pros: Backward compatible, minimal breaking changes, safe rollout
   - Cons: Slightly more complex than pure typed model, two sources of truth during transition
   - Effort: Medium

2. **Full typed replacement (breaking change)**
   - Replace `raw_xml` entirely with strongly typed models
   - All consumers updated to use typed fields
   - Pros: Cleanest architecture, no dual parsing, full IDE support
   - Cons: Breaking change across all consumers, high regression risk, larger review surface
   - Effort: High

3. **Regex-only hardening**
   - Keep current raw_xml approach but centralize and type regex patterns
   - Add typed regex extractors for known dialects
   - Pros: Smallest change, no model churn
   - Cons: Does not solve the root problem, fragile, hard to maintain
   - Effort: Low

## Recommendation
Adopt **Dual-mode typed models with raw_xml fallback** (Approach 1). Two production dialects are confirmed: Generic (flat MonteCarlo/WalkForward/ConfidenceLevel) and AutomaticRetest (deep nested with RetestWithHigherPrecision, MonteCarloRetest, MonteCarloManipulation, RetestOnAdditionalMarkets, WalkForwardOptimization, WalkForwardMatrix, OptProfileSysParamPermutation). A dual-mode model lets us type the known structure while keeping `raw_xml` as a safety valve for edge cases and backward compatibility. This matches the current coupling pattern in `project_builder.py` and `adaptive_retest_agent.py`.

## Risks
- Regex consumers in `adaptive_retest_agent.py` and `project_builder.py` may break if field names shift
- Unknown/unsupported XML elements must survive round-trip through raw_xml fallback
- Writer serialization order may affect downstream XML diff behavior
- Test coverage for both dialects is required before release

## Ready for Proposal
Yes — proceed to `sdd-propose` to define scope, acceptance criteria, and rollback plan for the typed CrossChecks model migration.
