# Apply Progress: Hypothesis-Builder

## State

**IMPLEMENTED + H2 FIXED (2026-10-07)** — 15/15 tasks verified during the audit; the
audit's two findings were re-investigated at close: H1 dismissed with evidence (feature-flag
contract, no duplication), H2 fixed with strict TDD (RED → GREEN). Archived.

## Progress

| Area | Status | Evidence |
|------|--------|----------|
| Rule mode (RB-4) | ✅ | `rule.py` keyword mapping; tests in `sdk/tests/agents/test_hypothesis_builder.py::TestRuleMode` |
| Validator (RB-5) | ✅ | `validate.py` BuildingBlockValidator strict contract; `TestBuildingBlockValidator` 10 tests |
| Facade dispatch + fallback (RB-6) | ✅ | `__init__.py` dual-mode; LLM → rule fallback tested |
| LLM mode (prompt/parse) | ✅ | `llm.py`; prompt/JSON-parse tests |
| WU8a pipeline config (8/12 phases, fature flag) | ✅ | `builder_agent.py:1094+`; `tests/agents/test_builder_agent.py` (8-phase default, 12-phase with `QUANTLAB_14PHASE=1`) |
| H2: validation propagation | ✅ FIXED | `__init__.py:172-183` re-raises ValueError; 2 new tests (`TestMergeValidatePropagates`) |

## Audit Findings Resolution (2026-10-07)

1. **H1 (rejected — not a defect):** `generate_pipeline_config()` emits 8 stages by default /
   12 with `QUANTLAB_14PHASE=1`, while `build_pipeline()` (ResearchDirector) builds an
   11+ stage multi-agent pipeline. Investigation proved this is **two deliberately separate
   mechanisms**: the BuilderAgent config feeds the campaign flow (feature-flagged for backward
   compatibility, locked by `tests/agents/test_builder_agent.py` WU8a), while
   `build_pipeline` injects `hypothesis_builder`/`refutation` as internal engine stages.
   "Adding" those stages to the generated config would duplicate the engine mechanism and
   break the registered feature-flag contract. No code change. (Minor note: the
   `research_director.build_pipeline` docstring lists 9 agent stages but code emits 11 —
   doc-only, flagged for a later doc pass.)
2. **H2 (fixed):** `_merge_and_validate()` swallowed `ValueError`
   (`logger.exception` + continue), shipping unvalidated blocks/strategies downstream while
   the validator's own contract (RB-5) is strict raising. Fix: re-raise after logging.
   Contract docstring updated ("validation failures propagate; unvalidated output is never
   returned"). Tests: RED (2 failed) → GREEN (68 passed in file).

## Test Evidence

- `sdk/tests/agents/test_hypothesis_builder.py` — 68 passed (66 + 2 new)
- `tests/agents/test_hypothesis_builder_f2.py` + `tests/test_hypothesis_builder_wiring.py` + `tests/integration/test_smoke.py` — 15 passed (no upstream regression)
- Full suite: 4100 passed / 51 pre-existing env/config failures (unchanged classification)

## Next Action

Archived as `archive/2026-10-07-hypothesis-builder/`.