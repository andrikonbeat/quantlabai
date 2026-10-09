# Archive Report: Hypothesis-Builder

## Archive Status

**COMPLETE**

## Summary

Hypothesis-builder (rule + LLM dual-mode hypothesis → validated blocks/strategies) was
verified at close with all 15 tasks green. The two audit findings were dispositioned:
**H1 rejected** (feature-flag emission contract tested by WU8a; building it further would
duplicate the ResearchDirector engine) and **H2 fixed** (validation errors now propagate —
strict TDD RED→GREEN, 2 new tests, no regressions upstream).

## Artifacts

| Artifact | Status | Notes |
|----------|--------|-------|
| `proposal.md`, `design.md` | ✅ | Pre-existing |
| `specs/pipeline-core/spec.md` | ✅ | Pre-existing delta |
| `tasks.md` (15/15) | ✅ | Verified during audit |
| `apply-progress.md` | ✅ | Findings resolution (H1/H2) + evidence |
| `verify-report.md` | ✅ | `verdict: pass`; 68 tests + 15 upstream green |
| `archive-report.md` | ✅ | This report |
| **Code fix (this close)** | ✅ | `sdk/quantlab/agents/hypothesis_builder/__init__.py` re-raise + docstring; 2 new tests in `sdk/tests/agents/test_hypothesis_builder.py` |

## Verification Evidence

- `sdk/tests/agents/test_hypothesis_builder.py`: RED (2 failed) → GREEN (68 passed)
- Upstream (F2/wiring/smoke): 15 passed — no regression from the propagation change
- Full suite context: 4100 passed; 51 pre-existing env/config failures (unchanged)

## Follow-ups (not blockers)

1. Doc pass: `research_director.build_pipeline` docstring (9 vs 11 agent stages) — cosmetic.
2. WU8a remains the contract for 8/12-phase emission; do not add engine-internal stages
   (hypothesis_builder/refutation) to `generate_pipeline_config` without a feature decision —
   that would duplicate the engine mechanism.