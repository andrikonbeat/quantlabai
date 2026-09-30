# Apply Progress: Typed CrossChecks Models

## Status

Complete — implementation verified against the change contract, all 25 tasks implemented and checked.
Re-audited 2026-09-30: tasks 4.2, 4.3 and 4.5 were originally checked without meeting their
contract and have since been implemented for real; see "Debt closure 4.2 / 4.3 / 4.5" below.

## Implementation Notes

### Core (Phase 1-3): Committed PR slices

- `CrossChecksGeneric`, `CrossChecksAutomaticRetest`, and nested sub-models added in `sdk/quantlab/cfx/models.py`.
- `CrossChecksConfig` holds `dialect`, `generic`, `automatic_retest`, and backward-compatible `raw_xml`, with `from_xml()`, `to_xml()`, and `summary()`.
- Reader detects Generic vs AutomaticRetest dialect in `_make_complex_section` and populates typed fields; unknown elements preserved in `raw_xml`.
- Writer serializes typed CrossChecks XML (`_append_complex_section`) and merges `raw_xml` extras; `CfxWriter.set_crosschecks` builds `CrossChecksGeneric`.
- Patcher `_apply_set_crosschecks` mutates `CrossChecksConfig.generic` typed fields with validation.

### Consumer refactoring (Phase 4) — completed this session

- `sdk/quantlab/agents/adaptive_retest_agent.py`: replaced regex-only extraction in `inspect_cfx_signals` with typed field access (`generic.mc_enabled` / `generic.wf_enabled`), keeping the raw_xml regex path as fallback for raw-only CrossChecks. This surfaced as 3 failing tests in the full suite: the reader now populates typed fields, so `raw_xml` is empty for known tags and regex extraction returned `None`.
- `tests/agents/test_adaptive_retest_agent.py`: updated mutation assertions from raw XML substring checks (`"RetestWithHigherPrecision" in raw_xml`) to typed field access (`cc.automatic_retest.retest_with_higher_precision is not None`, `cc.generic.mc_enabled is True`).
- `sdk/quantlab/sqx/project_builder.py`, renderers, translator, and phase4 templates already consume typed fields.

### Debt closure 4.2 / 4.3 / 4.5 — 2026-09-30

A follow-up audit found that 4.2, 4.3 and 4.5 were checked off without meeting their contract: the
adaptive retest builders and `render_automatic_retest` still constructed `CrossChecksConfig` from a
bare `raw_xml` string, and `project_builder.get_template_default` still probed CrossChecks purely
by regex. This section records what actually closed them.

**Mechanism.** Partial modeling is only safe if serialization cannot lose what the models skip, so
every CrossChecks sub-model now carries a `raw_xml` field holding the original element markup, and
`to_xml()` re-emits that markup verbatim instead of rebuilding the element. Typed consumers get
modeled fields; the dialect round-trips without loss. This resolved design.md's open question about
modeling every nested element: we model only what is consumed.

- **4.2** `_apply_automatic_retest` / `_apply_retest` now build the section through
  `CrossChecksConfig.from_xml()`, so the emitted section is typed. Verified that the rendered output
  keeps every element and value, including the unmodeled `<Methods>`, `<Param1>`/`<Param2>` and
  `<OptimizeExitTypes>`. Contract locked in `TestTypedCrossChecksBuilders`.
- **4.3** `get_template_default` reads `wf_period`, `wf_optimization` and `wf_optimize_periods`
  from the typed model, falling back to the regex probe otherwise. The remaining CrossChecks fields
  are intentionally still regex: `<Param1>`/`<Param2>`, `<MaxTests>`, the `wf_acceptance_*` family
  and `rc_spread` (a `<Chart>` attribute) are not modeled. Verified the typed path is actually taken
  on the real template and agrees with the regex it replaces.
- **4.5** The task cited `customproject/templates.py`; the function actually lives in
  `customproject/renderers.py`. It now returns a typed section, parsed per call so no mutable model
  is shared across renders.

**Serializer/parser asymmetries found and fixed** (all were latent, and would have corrupted output
once builders emitted typed sections):

- `to_xml()` re-synthesized recognized children, rewriting `<ConfidenceLevel>0.95</ConfidenceLevel>`
  into `<ConfidenceLevel value="0.95"/>` and emitting empty `<Param1 value="" />` for values it had
  no field for. Now re-emitted verbatim.
- The generic dialect serializer wrote `simulations=` while `_parse_generic` read `runs=`, so a
  serialized config silently reverted `mc_runs` to its default. Serializer now writes the canonical
  `runs=`; the parser accepts both spellings because `renderers.py::_crosschecks_section` has
  historically emitted `simulations=`.
- `auto_tags` was out of sync with `_parse_automatic_retest`, so `MonteCarloManipulation`,
  `RetestOnAdditionalMarkets`, `WalkForwardMatrix` and `OptProfileSysParamPermutation` were parsed
  into their typed sub-model *and* kept in `raw_xml`, serializing each element twice.
- `_parse_generic` read `ConfidenceLevel` only from a `value` attribute, silently discarding the
  child form that the adaptive retest builder emits. Both spellings are now read.

**Tests updated, not weakened.** `tests/customproject/test_templates.py` asserted on
`cross_checks_section.raw_xml`, which is the internal storage field and is legitimately empty once
children are typed. Those assertions now read `to_xml()`, the rendered output, and additionally
assert the typed sub-models.

## Verification

- Focused verification: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/ tests/agents/test_adaptive_retest_agent.py tests/phase4/test_cfx_extensions.py tests/phase4/test_project_builder.py tests/customproject/test_templates.py tests/phase4/test_translator_extensions.py`
- Result: **448 passed, 0 failed, 0 skipped**
- Extended block: `tests/cfx/ tests/agents/ tests/phase4/ tests/customproject/ sdk/tests/test_pipeline_agent_stages.py` → 7 failed (4× pre-existing `test_research_agent_f1` out of scope, 3× flaky E2E campaign monitor timing) / 1315 passed; campaign monitor file passes 79/79 standalone.
- Full suite: 4085+ passed; the 10 failures were 3× adaptive_retest (fixed this session), 4× research_agent_f1 (pre-existing, out of scope), 2× chained_tasks (timing flaky, passes standalone), 1× test_knowledge (pre-existing, out of scope).
- After debt closure (2026-09-30): `tests/cfx/` → **208 passed**; `tests/cfx/ tests/agents/test_adaptive_retest_agent.py tests/phase4/ tests/customproject/` → **1042 passed, 4 skipped**; `tests/phase4/test_project_builder.py` → **83 passed**; `tests/customproject/` → **156 passed, 4 skipped**; `tests/agents/test_adaptive_retest_agent.py` → **30 passed** (was 27).
- Full suite after debt closure: **4111 passed, 9 skipped, 0 failed** (427s). The previously flaky
  `test_chained_tasks` passed in this run. The `research_agent_f1` and knowledge-count gaps recorded
  above were closed earlier the same day.

## Rollback Boundary

Revert in reverse PR order (3 → 2 → 1). `raw_xml` fallback is preserved throughout, so partial revert is safe.