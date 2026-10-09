# Tasks: Typed CrossChecks Models

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 800–1000 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Models + Reader/Writer → PR 2: Patcher + Consumers → PR 3: Tests + Integration |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Add typed CrossChecks models and update CrossChecksConfig | PR 1 | `pytest tests/cfx/test_crosschecks_models.py -x` | Generic + AutomaticRetest model instantiation + defaults | Revert models.py; raw_xml fallback intact |
| 2 | Reader dialect detection + typed population; Writer typed serialization + raw_xml merge | PR 1 | `pytest tests/cfx/test_reader_crosschecks.py -x` | Generic + AutomaticRetest round-trip via pytest | Revert reader.py, writer.py; models.py stays |
| 3 | Patcher validates and mutates typed Generic fields instead of replacing raw_xml | PR 2 | `pytest tests/cfx/test_patcher.py::TestPatcherPhase4Instructions::test_set_crosschecks -x` | CfxPatcher apply + ValidationError atomicity via pytest | Revert patcher.py; models/reader/writer stay |
| 4 | adaptive_retest_agent reads typed fields; project_builder replaces CrossChecks regex | PR 2 | `pytest tests/agents/test_adaptive_retest_agent.py tests/phase4/test_project_builder.py -x` | Adaptive retest mutation + build config override via pytest | Revert consumer files; core stays typed |
| 5 | Update renderers, templates, translator, phase4/templates to typed CrossChecks | PR 3 | `pytest tests/customproject/test_templates.py tests/phase4/test_cfx_extensions.py -x` | Template generation + round-trip via pytest | Revert consumer files; core stays typed |
| 6 | New + updated tests covering both dialects, round-trip, unknown-element fallback, patcher validation | PR 3 | `pytest tests/cfx/ tests/agents/ tests/phase4/ tests/customproject/ -x` | Full CFX test suite via pytest | Revert test files only |

## Phase 1: Foundation (Typed Models)

- [x] 1.1 Add `CrossChecksGeneric`, nested sub-models, and `CrossChecksAutomaticRetest` to `sdk/quantlab/cfx/models.py`
- [x] 1.2 Update `CrossChecksConfig` with `dialect`, `generic`, `automatic_retest`, and backward-compatible `raw_xml`
- [x] 1.3 Write failing RED tests for model defaults and parsing in `tests/cfx/test_crosschecks_models.py`

## Phase 2: Reader / Writer (Serialization)

- [x] 2.1 Update `sdk/quantlab/cfx/reader.py` `_make_complex_section` to detect Generic vs AutomaticRetest dialect and populate typed fields
- [x] 2.2 Preserve unrecognized XML in `raw_xml` during reader population
- [x] 2.3 Update `sdk/quantlab/cfx/writer.py` `_append_complex_section` to emit typed CrossChecks XML and merge `raw_xml` extras
- [x] 2.4 Update `CfxWriter.set_crosschecks` to build `CrossChecksGeneric` instead of raw XML string
- [x] 2.5 Write RED tests for reader dialect detection and writer round-trip in `tests/cfx/test_reader_crosschecks.py`

## Phase 3: Patcher (Typed Mutation)

- [x] 3.1 Update `sdk/quantlab/cfx/patcher.py` `_apply_set_crosschecks` to mutate `CrossChecksConfig.generic` typed fields
- [x] 3.2 Update `_validate_set_crosschecks` to enforce typed model constraints (Pydantic ValidationError)
- [x] 3.3 Ensure invalid typed values raise ValidationError without partial application
- [x] 3.4 Update patcher tests for typed mutation and atomic validation in `tests/cfx/test_patcher.py`

## Phase 4: Consumer Refactoring

- [x] 4.1 Replace regex extractors in `sdk/quantlab/agents/adaptive_retest_agent.py` `inspect_cfx_signals` with typed field access
- [x] 4.2 Update `_apply_automatic_retest` / `_apply_retest` to construct typed `CrossChecksAutomaticRetest` / `CrossChecksGeneric`
      — Closed 2026-09-30. Builders now emit a typed section via `CrossChecksConfig.from_xml()`. Each
      parsed child keeps its original markup in the sub-model's `raw_xml`, so `to_xml()` re-emits the
      builder's content instead of a lossy re-synthesis. Contract locked in
      `tests/agents/test_adaptive_retest_agent.py::TestTypedCrossChecksBuilders`.
- [x] 4.3 Replace CrossChecks regex mappings in `sdk/quantlab/sqx/project_builder.py` `_apply_build_config` with typed field reads
      — Closed 2026-09-30 with a deliberate partial boundary, per design.md (typed for modeled fields,
      regex for the rest). `get_template_default` reads `wf_period`, `wf_optimization` and
      `wf_optimize_periods` from the typed model; the other CrossChecks fields (`wf_param1`,
      `wf_param2`, `wf_optimize_exit_types`, `wf_max_tests`, the `wf_acceptance_*` family, `rc_spread`
      and `main_test_values`) are not modeled yet and still use the regex probe. Verified that the
      typed path is exercised on the real template and returns values identical to the regex.
- [x] 4.4 Update `sdk/quantlab/customproject/renderers.py` `_crosschecks_section` to use typed models
- [x] 4.5 Update `render_automatic_retest` to use typed models
      — Closed 2026-09-30. Path corrected: the function lives in
      `sdk/quantlab/customproject/renderers.py`, not `templates.py`. It now returns a typed section
      via `CrossChecksConfig.from_xml()`, parsed per call to avoid sharing one mutable model.
- [x] 4.6 Update `sdk/quantlab/translate/translator.py` retester generator to use typed CrossChecks
- [x] 4.7 Update `sdk/quantlab/phase4/templates.py` `_build_retester_task` to use typed CrossChecks
- [x] 4.8 Update adaptive_retest_agent tests to verify typed field access in `tests/agents/test_adaptive_retest_agent.py`
- [x] 4.9 Update project_builder tests for typed CrossChecks overrides in `tests/phase4/test_project_builder.py`

## Phase 5: Integration / Verification

- [x] 5.1 Add template integration tests for AutomaticRetest typed CrossChecks in `tests/customproject/test_templates.py`
- [x] 5.2 Add retester round-trip tests for typed models in `tests/phase4/test_cfx_extensions.py`
- [x] 5.3 Run full CFX test suite and verify zero regressions
- [x] 5.4 Verify both Generic and AutomaticRetest goldens pass round-trip with unknown-element fallback
