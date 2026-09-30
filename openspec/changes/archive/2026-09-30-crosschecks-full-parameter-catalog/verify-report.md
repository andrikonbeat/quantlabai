```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:4ccb4cbbeaad3e69c0f3bc75627ffa91083f32166cd02e1a4dd48f0c8a7d6bf2
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 6/6
scenarios: 6/6
test_command: SQX_FORCE_MOCK=1 python3 -m pytest -q tests/phase4 tests/cfx
test_exit_code: 0
test_output_hash: sha256:d29b2adbff216481c37670418d4f2bb334be2957992b1271f5518f4fdab9b5df
build_command: python3 -m compileall -q sdk/quantlab/cfx/models.py sdk/quantlab/sqx/project_builder.py sdk/quantlab/knowledge/kb/store.py sdk/quantlab/agents/builder_agent.py
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

# Verification Report

**Change**: `crosschecks-full-parameter-catalog`
**Capability**: `crosschecks-parameter-catalog`
**Spec version**: N/A (version-isolated to SQX `144.2953`)
**Mode**: Strict TDD (active)
**Date**: 2026-09-30
**Artifacts read**: `proposal.md`, `specs/crosschecks-parameter-catalog/spec.md`, `design.md`, `tasks.md`, `apply-progress.md` (hybrid store: OpenSpec files authoritative; Engram `sdd/crosschecks-full-parameter-catalog/apply-progress` agrees)

## Verdict Summary

**PASS WITH WARNINGS.** All 40/40 tasks are complete, all 6 spec requirements and all 6 spec scenarios have passing runtime evidence, and the change-scoped suites are green. 5 warnings are recorded — none of them is a blocker: 1 defect in the changed builder code (a misleading log line at scale), 1 spec/implementation count delta, 1 missing production caller for the drift hook, 1 untested sub-clause in the summary contract, and 1 pre-existing order-dependent flake outside this change's scope.

## Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 40 (1.1–1.10, 2.1–2.7, 3.1–3.5, 4.1–4.4, 5.1–5.3, 6.1–6.11) |
| Tasks complete | 40 |
| Tasks incomplete | 0 |
| Spec requirements | 6 |
| Spec scenarios | 6 |
| Files changed (per design + tasks) | `sdk/quantlab/cfx/models.py`, `sdk/quantlab/sqx/project_builder.py`, `sdk/quantlab/knowledge/kb/store.py`, 10 KB YAMLs, 4 test modules |

Task 3.3 is marked `[x]` with a struck-through original text and an explicit rationale: `_apply_acceptance_settings` was scoped out because `_CROSSCHECK_FIELD_SPECS` already expresses tab scoping, and the helper had no production caller. Verified: `hasattr(project_builder, "_apply_acceptance_settings") == False`, and the invariants its tests covered are now asserted through the real entry point `_apply_build_config` (`TestCrosscheckAcceptanceIsTabScoped`). This is a legitimate scope reduction, not an unchecked task.

## Build & Tests Execution

**Build**: ✅ Passed (exit 0, empty output)

```text
$ python3 -m compileall -q sdk/quantlab/cfx/models.py sdk/quantlab/sqx/project_builder.py \
    sdk/quantlab/knowledge/kb/store.py sdk/quantlab/agents/builder_agent.py
(no output; exit 0)

$ python3 -c "import quantlab.cfx.models, quantlab.sqx.project_builder, quantlab.knowledge.kb.store, quantlab.agents.builder_agent"
import smoke: OK   (exit 0)
```

`ruff` and `mypy` are **not installed** in the local venv (per project `AGENTS.md` they run in CI only), so lint/type evidence is ➖ not available locally, not a failure.

**Tests**: ✅ all change-scoped commands green; ⚠️ 1 pre-existing unrelated flake in the whole-tree run

| # | Command | Exit | Result | `sha256(output)` |
|---|---------|------|--------|------------------|
| 1 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/phase4/test_project_builder.py tests/knowledge/test_crosschecks_schema.py tests/cfx/test_crosschecks_models.py tests/cfx/test_reader_crosschecks.py` | 0 | **164 passed**, 1 warning | `78534e83…` |
| 2 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/test_crosschecks_models.py tests/phase4/test_project_builder.py` (exact task 4.4) | 0 | **144 passed**, 1 warning | `04beab0f…` |
| 3 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/phase4 tests/cfx` (proposal AC-5 / envelope `test_command`) | 0 | **854 passed**, 2 warnings | `d29b2adb…` |
| 4 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/agents sdk/tests` | 0 | **1781 passed**, 21 warnings | — |
| 5 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/` (whole tree) | 1 | 2662 passed, 9 skipped, **1 failed** (pre-existing flake, see W-5) | `6aa20426…` |

The single `test_command` in the envelope is command **#3** — the scope the proposal's own acceptance criteria name (`tests/cfx/ tests/phase4/` green) — because it is both the change's declared gate and the whole of the code the change touches. Command #5 is reported in full above rather than hidden; its one failure is classified and evidenced under W-5 and is not attributable to this change.

**Coverage**: ➖ Not available — `pytest-cov` is not installed and the `pytest.ini` rejects `--cov`. Coverage analysis skipped (informational, not a failure).

## Spec Compliance Matrix

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Catalog Completeness | Full tab coverage from CFX evidence | `tests/knowledge/test_crosschecks_schema.py > TestCrossChecksSchemaCompleteness::test_all_eight_robustness_tabs_are_covered`; `test_every_yaml_has_xml_path_and_element_name`; `tests/phase4/test_project_builder.py > TestCrosscheckSequentialOptimization` | ✅ COMPLIANT |
| Evidence-First Extraction | Evidence trace for every parameter | `test_evidence_refs_point_to_existing_files`; `test_every_yaml_has_required_evidence_fields`; `test_xml_paths_match_cfx_structure`; `TestCrossChecksSchemaTriangulation` (3 tests); `TestCrosscheckMappingsHaveEvidence` (6 tests) | ✅ COMPLIANT |
| Model Extension | Model extension preserves round-trip | `tests/cfx/test_crosschecks_models.py > TestWhatIfRoundTrip::test_whatif_method_params_roundtrip`; `TestMonteCarloMethods::test_mc_method_params_parsed`, `::test_mc_methods_survive_full_roundtrip`; `TestCrossChecksConfigSummary`; `tests/cfx/test_reader_crosschecks.py > TestWriterCrossChecksRoundTrip`, `TestReaderCrossChecksDialectDetection` | ✅ COMPLIANT |
| Builder Field Mapping | Builder mapping covers acceptance settings | `tests/phase4/test_project_builder.py > TestCrossChecksOverrides::test_wf_acceptance_threshold_pct`; `TestCrosscheckAcceptanceIsTabScoped`; `TestCrosscheckScopingIsolation`; `TestCrosscheckLegacyMappingsDoNotCorruptSiblings`; `TestBuildConfigMapCoverage` | ✅ COMPLIANT |
| Summary Contract | Summary contract dual output | `TestSummaryContract::test_summary_returns_json_and_text`; `TestCrossChecksConfigSummary::test_generic_summary`, `::test_automatic_retest_summary`, `::test_empty_config_summary` | ⚠️ PARTIAL — see W-4 |
| Versioning and Needs-Review | Needs-review survives version drift | `tests/knowledge/test_crosschecks_schema.py > TestVersionDriftInvalidation` (4 tests, all passing); `sdk/tests/test_pr2_builder_agent.py > …::test_builder_consult_missing_entry_raises_block` | ⚠️ PARTIAL — see W-3 |

**Compliance summary**: 4/6 scenarios fully compliant; 2/6 compliant in substance with an unproven/unwired sub-clause (W-3, W-4). No scenario is `UNTESTED` and none is `FAILING`.

### Independent runtime evidence (beyond the suite)

Run by the verifier against the **real shipped artifacts**, not the hand-written test fixtures:

```text
# Spec scenario 4, on the bundled template (not the test fixture)
Build-Task1.xml  (sdk/quantlab/sqx/templates/default-project.sqx-template)
  wf_acceptance_threshold_pct=55 → thresholdPct values ['55', '80']   (WFO written, WFM untouched)
  wf_acceptance_threshold_pct=80 → thresholdPct values ['80', '80']   (postcondition holds — but see W-1)
  template defaults               → ['80', '80']

# Spec scenario 5, on the real CrossChecks block
summary() keys      : ['json', 'text']
summary()['json']   : dialect, enabled_tabs, typed_values, automatic_retest
  enabled_tabs      : RetestWithAdditionalMarkets, WalkForwardOptimization, RetestWithHigherPrecision,
                      MonteCarloRetest, MonteCarloManipulation, OptProfileSysParamPermutation,
                      WalkForwardMatrix, WhatIf
  typed_values      : {mc_number_of_simulations: 10, wf_period: '10', wf_optimization: '15'}
  text single-line  : True (no \n, no \r; 260 chars)

# Catalog completeness, all 10 KB YAMLs
required fields present (name, tab, type, xml_path, element_name, default, range,
                        what_it_does, how_it_works_in_sqx, quant_trading_role,
                        status, sqx_version, evidence_ref) → NONE missing
status counts: verified=9, needs_review=1 ("Cross Checks vs Retester", doc-gap markers present)

# Real .cfx evidence (assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx)
top-level <CrossChecks> children: 9
  RetestOnAdditionalMarkets, WalkForwardOptimization, RetestWithHigherPrecision,
  MonteCarloRetest, WalkForwardMatrix, MonteCarloManipulation,
  OptProfileSysParamPermutation, WhatIf, SequentialOptimization

# Builder invariants
BuildConfig fields                 : 213
_BUILD_CONFIG_MAP entries          : 213   (parity: no unmapped field, no extra key)
_CROSSCHECK_FIELD_SPECS entries    : 112   (tab-scoped: {tab}/Settings, {tab}/AcceptanceSettings, {tab}/Methods)
_invalidate_on_version_drift in store.py : present; _apply_acceptance_settings in project_builder.py : absent (by design)
```

## Correctness (Static Evidence)

| Requirement | Status | Notes |
|-------------|--------|-------|
| Catalog Completeness | ✅ Implemented | 10 KB YAMLs under `knowledge/structured/sqx-kb/144.2953/parameters/Cross checks/`, each a single evidence-backed entry with all 13 required fields. 9 `verified` + 1 `needs_review`. |
| Evidence-First Extraction | ✅ Implemented | Every entry carries `evidence_ref`; each resolved target exists on disk; `xml_path` resolves to a real element in its cited evidence. `Cross Checks vs Retester.yaml` points at `docs/sqx-builder-config/…#Cross checks` and stays `needs_review` with explicit "doc gap" markers in both `what_it_does` and `how_it_works_in_sqx` — no invented semantics. |
| Model Extension | ✅ Implemented | `CrossChecksMethod` (`use`/`type`/`params`) at `models.py:347`; `WhatIfConfig` (`use` + `methods`) at `models.py:371`; `MonteCarloRetest.methods: list[CrossChecksMethod] \| None` at `models.py:338`; `CrossChecksAutomaticRetest.what_if` wired at `models.py:475`; `_parse_methods`/`_parse_method_params` used by both tabs. `raw_xml` fallback intact. |
| Builder Field Mapping | ✅ Implemented | 112 tab-scoped specs carrying XML regex (scope + leaf) and a format type, all resolved against real evidence by `TestCrosscheckMappingsHaveEvidence`; tab classification asserted by `TestCrosscheckTabClassification`; 213/213 map parity by `TestBuildConfigMapCoverage`. Unknown/composite parameters fall back to `raw_xml` (WalkForwardMatrix + OptProfileSysParamPermutation models keep `raw_xml`; unknown `<CrossChecks>` children land in `CrossChecksConfig.raw_xml`). |
| Summary Contract | ✅ Implemented | `CrossChecksConfig.summary()` at `models.py:675` returns `{"json": dict, "text": str}`. `json` carries `dialect`, `enabled_tabs`, `typed_values` and the typed sub-model dumps; `text` is a space-joined single line. |
| Versioning and Needs-Review | ⚠️ Implemented, not wired | `KbStore.invalidate_on_version_drift()` at `store.py:291` demotes non-`needs_review` entries to `needs_review` for the pinned bucket, returns `VersionDriftResult(drifted=True, invalidated=N, blocked=False, warnings=[…])`, never raises, and short-circuits to a no-op when versions match. `builder_agent._consult_kb` collects `"KB tab '<tab>' has entries needing review"` and raises only under `strict_kb`. But no production code calls the drift hook — see W-3. |

## Coherence (Design)

| Design decision | Followed? | Notes |
|-----------------|-----------|-------|
| Typed scalar leaves + `raw_xml` for Conditions (chosen over fully recursive Condition model) | ✅ Yes | `WalkForwardMatrix` / `OptProfileSysParamPermutation` keep `raw_xml`; acceptance `Condition` trees are untouched. Consistent with spec "Out of Scope: breaking removal of `raw_xml` fallback". |
| KB YAML as single source of truth | ✅ Yes | The builder's mapping table is asserted *against* the shipped artifacts (real template + real saved config `DJ CFD H1.cfx`), so docs and code cannot drift silently. |
| Separate catalog service rejected | ✅ Yes | Catalog logic lives in the existing `KbStore`; no new service. |
| Builder gains ~80+ `_BUILD_CONFIG_MAP` entries + helper functions for nested Settings/AcceptanceSettings | ⚠️ Partially | 213 map entries and 112 `_CROSSCHECK_FIELD_SPECS` far exceed ~80+. The nested-handling helper `_apply_acceptance_settings` was **removed** (task 3.3, 5.2, 6.11) because tab scoping is expressed in the specs table itself. Documented in `tasks.md` and re-verified: no dangling references, invariants re-asserted via `_apply_build_config`. |
| Summary contract shape from design (`json` + `text`) | ✅ Yes | Matches the design's `Summary contract` block key-for-key (`dialect`, `enabled_tabs`, `typed_values`). |
| Version drift handler as the last implementation step | ⚠️ Partially | The handler exists and is unit-tested, but no production caller was added — see W-3. |
| `sdk/tests/test_cfx.py` + `sdk/tests/sqx/test_project_builder.py` as the new test homes (design "File Changes") | ⚠️ Deviation | Tests landed in `tests/cfx/test_crosschecks_models.py`, `tests/cfx/test_reader_crosschecks.py`, `tests/phase4/test_project_builder.py`, `tests/knowledge/test_crosschecks_schema.py` instead. Consistent with the repo's actual `pytest.ini` (`testpaths = tests + sdk/tests`) and with the focused commands recorded in `tasks.md`. The design's file table is stale, not the implementation. |
| Open Questions left open (WhatIf names under SQX 145.x; `OptProfileSysParamPermutation` scalars) | ✅ Yes | Both remain deferred, and `OptProfileSysParamPermutation` is indeed still `raw_xml` — matching the open question rather than pre-empting it. |

## TDD Compliance

| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | ⚠️ Partial | `apply-progress.md` has an "PR3 Work Units Completed" evidence table (RED test name → GREEN implementation → command) and a "Follow-up Pass" defect/fix table, but **no** table literally titled "TDD Cycle Evidence" with RED/GREEN/TRIANGULATE/SAFETY NET/REFACTOR columns. RED-before-GREEN is asserted per task and is consistent with the on-disk tests, but the canonical 5-column artifact is absent. |
| All tasks have tests | ✅ | All 6 capability areas have dedicated, currently-passing test classes. |
| RED confirmed (test files exist) | ✅ 4/4 | All four test modules named in `apply-progress.md` exist on disk and were executed by the verifier. |
| GREEN confirmed (tests pass now) | ✅ 4/4 | 164 passed across the four modules; the 40 named tests/classes in `tasks.md` are all inside that set. |
| Triangulation adequate | ✅ | Genuine variance: per-field writes, cross-tab isolation, inert no-ops, template-default probing, dialect round-trips, log assertions. `TestCrosscheckLegacyMappingsDoNotCorruptSiblings` uses `@pytest.mark.parametrize` over two flag fields; `TestCrosscheckWalkForwardMatrixSettings` over 5. |
| Safety Net for modified files | ✅ | Reverting risk is bounded: `_INERT` is size-pinned to 4, map/field parity is asserted at 213/213, and `TestCrosscheckTemplateDefaults` pins scoped-default probing. |

**TDD Compliance**: 5/6 checks passed (1 WARNING: canonical evidence table shape).

### Test Layer Distribution

| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 164 | 4 | `pytest` |
| Integration | included above (catalog extraction reads real `.cfx`/template zips) | 1 (`tests/knowledge/test_crosschecks_schema.py`) | `pytest` |
| E2E | 0 | 0 | not installed |
| **Total (change-scoped)** | **164** | **4** | |

All four modules are unit/integration tests driving real production entry points (`_apply_build_config`, `CrossChecksConfig.from_xml/to_xml/summary`, `KbStore.invalidate_on_version_drift`) against real shipped artifacts. No rendering/HTTP/browser tooling is in play, so no capability mismatch. The design's "E2E | Summary contract" row is realised as a unit test in this project — SUGGESTION-level only.

### Changed File Coverage

Coverage analysis skipped — no coverage tool detected (`pytest-cov` not installed; `pytest.ini` rejects `--cov`). Not a failure.

### Assertion Quality

| File | Line | Assertion | Issue | Severity |
|------|------|-----------|-------|----------|
| `tests/phase4/test_project_builder.py` | 1326 | `assert "unchanged" in caplog.text or "ProfitOptPct" not in caplog.text` | **Unfalsifiable disjunction.** If nothing is logged, the right disjunct is trivially true, so the test passes without proving any log was emitted. The sibling `test_missing_tab_warns_and_preserves` (L1332–1338) does it correctly with `assert "so_use" in caplog.text` + `assert "unchanged" in caplog.text`. The `xml == template_build_xml` half still carries real value. | WARNING |
| `tests/knowledge/test_crosschecks_schema.py` | 163, 167, 177, 179 | bare `continue` when the evidence file is missing / not a zip / carries no `<CrossChecks>` | **Potentially vacuous loop body.** `test_xml_paths_match_cfx_structure` can assert nothing for an entry whose evidence cannot be read. Partly mitigated: `test_evidence_refs_point_to_existing_files` (L120) hard-asserts every `evidence_ref` target exists, so the main vacuity path is closed — the residual hole is "exists but is not a readable CFX". | WARNING |
| `tests/knowledge/test_crosschecks_schema.py` | 17–26 | `_KNOWLEDGE_ROOT`, `_PROJECT_ROOT`, `_CFX_PATH`, `_TEMPLATE_PATH` are **hardcoded absolute paths** including `/home/ogzuz/Proyectos/QuantLab AI` and `/home/ogzuz/Proyectos/QuantLab AI/sdk/assets/…` | **Not path-portable.** This module will fail outright in CI, in a container, or on any other checkout path. `tests/phase4/test_project_builder.py` derives the same artifacts correctly via `Path(__file__).resolve().parents[2]`. | WARNING |
| `tests/knowledge/test_crosschecks_schema.py` | 200 | `assert _EXPECTED_TABS.issubset(present_tabs)` | Subset, not equality — the real `.cfx` has 9 tabs but only 8 are asserted, so the 9th (`SequentialOptimization`) is not *pinned* by this test. It is covered elsewhere (`TestCrosscheckSequentialOptimization`, `test_sequential_optimization_scope_hits_a_real_config`, `test_known_prefixes_map_to_their_tab` all assert `so_use`/`SequentialOptimization` explicitly), so this is a completeness nit, not a hole. | SUGGESTION |

**Assertion quality**: 0 CRITICAL, 3 WARNING, 1 SUGGESTION. No tautologies (`assert True`), no ghost loops over possibly-empty query results, no smoke-only render tests, no CSS/implementation-detail coupling. The dominant pattern is strong: tests resolve a tab-scoped region out of the **real** `Build-Task1.xml` and assert both the written value *and* that the sibling tabs kept their own values.

### Quality Metrics

**Linter**: ➖ Not available (`ruff` not installed locally; CI-only per project contract)
**Type Checker**: ➖ Not available (`mypy` not installed locally; CI-only per project contract)

## Issues Found

### CRITICAL
None.

### WARNING

**W-1 · `_apply_in_scope` emits a false "field does not exist" warning on every idempotent write.**
`project_builder.py:1874-1878` decides "no match" by `patched == region.group(0)`, which is also true when the requested value **equals the value already present** — a successful no-op write. Reproduced on the shipped template:

```text
BuildConfig(wf_acceptance_threshold_pct=55) → no warning,  thresholdPct ['55','80']   ← correct write
BuildConfig(wf_acceptance_threshold_pct=80) → WARNING,     thresholdPct ['80','80']   ← misleading warning
BuildConfig(wf_acceptance_threshold_pct=90) → no warning,  thresholdPct ['90','80']   ← correct write
```

Sweep: of 107 catalog fields that resolve a template default, **98 emit this false warning** when set to their own default value. Impact is diagnosability, not correctness — no XML is ever corrupted, and the spec scenario's postcondition (`<Conditions thresholdPct="80">`) still holds — but an agent that explicitly sets a field to the template default is told the field "does not exist in this SQX build", which is the opposite of the truth. Note this is exactly the value the spec scenario names, and it is why W-1 is the highest-severity item here. Not fixed by this verification (implementation code untouched), per the phase contract.

**W-2 · Spec says 8 robustness tabs; proposal, design, tasks, catalog and evidence all say 9.**
`spec.md` L6 enumerates 8 and omits `SequentialOptimization`; `spec.md` L28 and L65 say "all 8". The real `.cfx` has **9** top-level `<CrossChecks>` children, and the catalog ships 9 `verified` entries including `Sequential Optimization.yaml`. The implementation is ahead of the spec here, and the spec is the stale artifact. The KB test constant `_EXPECTED_TABS` still encodes the 8-element set (and its docstring says "8 robustness tabs extracted from CFX evidence (spec requirement)"). Recommend amending `spec.md` to 9 and widening `_EXPECTED_TABS` to an equality assertion, so the spec stops under-constraining the catalog.

**W-3 · `invalidate_on_version_drift()` has no production caller.**
Repo-wide search for the symbol outside tests returns exactly one hit: the definition at `sdk/quantlab/knowledge/kb/store.py:291`. The mechanism is correct and fully unit-tested (4 passing tests: demotion, actionable warning naming both versions, matching-version no-op, tab scoping), and the consumer half of the spec scenario is satisfied by a *separate* path — `builder_agent._consult_kb` (`agents/builder_agent.py:203`) inspects `entry["status"] == "needs_review"` and appends a warning, raising only under `strict_kb`. But the two halves are not connected: on a real 145.x install nothing calls the hook, so no entry is ever actually demoted, and the `builder_agent` warning would only fire for entries already marked `needs_review` in the seed data. The end-to-end chain drift → demotion → consumer warning is therefore unproven in production. Needs one call site (e.g. at KB load or builder-agent startup).

**W-4 · The "single-line text" clause of the summary contract has no covering test.**
`spec.md` L18 requires `summary()` text to be "a single-line string for log envelopes". The four summary tests assert only the presence of the `json`/`text` keys, their types, and selected `json` values — none asserts the absence of newlines. Verified independently by the verifier (`"\n" not in text and "\r" not in text` → `True` on real template input, 260 chars), so the behavior is correct today, but nothing would catch a regression that started embedding newlines. One `assert "\n" not in summary["text"]` closes it.

**W-5 · Pre-existing, order-dependent flake in `TestDispatchWithMonitorE2E` — unrelated to this change.**
Observed once in the whole-tree run (`tests/` → exit 1) and once in a `tests/phase4`-only run (2 failures), then not reproduced: the test **passes in isolation**; `tests/phase4` passed **3/3** on repeat runs (683 passed each); `tests/phase4 tests/cfx` passed (854); and a **different** member of the same class failed on each failing run — the signature of a timing/ordering problem, not a deterministic assertion. The test exercises `quantlab.sqx.cli_wrapper.dispatch_campaign` against the mock SQX watcher with `poll_interval=0.2, timeout=30.0`; it shares no code path with `CrossChecksConfig`, `_BUILD_CONFIG_MAP`, `_CROSSCHECK_FIELD_SPECS`, or the KB catalog. Classified **pre-existing and out of scope**; not fixed, per instructions.

### SUGGESTION

**S-1 · `apply-progress.md` L84 overstates pre-existing breakage.** It records "tests/agents + sdk/tests: 5 failures, all pre-existing". Independent run: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/agents sdk/tests` → **1781 passed, 0 failed**, exit 0. Those failures no longer exist; the note is stale and should be corrected so a future reader does not discount a real regression as "known pre-existing".

**S-2 · `design.md` "File Changes" table is stale.** It lists `sdk/tests/test_cfx.py` (modify) and `sdk/tests/sqx/test_project_builder.py` (create); neither exists. The real homes are `tests/cfx/test_crosschecks_models.py`, `tests/cfx/test_reader_crosschecks.py`, `tests/phase4/test_project_builder.py`, `tests/knowledge/test_crosschecks_schema.py`. The implementation is right and the table is wrong; task 5.3 ("verify design alignment") checked the *decisions* but not this table.

**S-3 · `WalkForwardMatrix` and `OptProfileSysParamPermutation` parse a `use` flag they cannot store.** `_parse_automatic_retest` (`models.py:848, 852`) calls `WalkForwardMatrix(use=…, raw_xml=…)` and `OptProfileSysParamPermutation(use=…, raw_xml=…)`, but both models declare only `raw_xml` (`model_fields == ['raw_xml']`, verified at runtime), so pydantic's default `extra='ignore'` silently drops `use`. Consequence: `summary()["json"]["enabled_tabs"]` lists those two tabs whenever the element *exists*, regardless of its `use` value — a mild imprecision in the summary contract for exactly 2 of 9 tabs. Pre-existing model shape rather than something this change introduced, but the summary contract is in this change's scope, so it belongs on the record.

**S-4 · Non-obvious positive: the catalog is held honest by evidence, not by convention.** `TestCrosscheckMappingsHaveEvidence` resolves every one of the 112 scopes *and* leaves against the real `Build-Task1.xml` and fails on any that matches nothing, and pins `_INERT` to exactly 4 members so the exception list cannot grow silently. That mechanism is what converted the phase-6 audit from opinion into evidence, and it is worth preserving verbatim in future catalog work.

## Coverage Verdict Per Requirement

| Requirement | Verdict |
|-------------|---------|
| Catalog Completeness | **PASS** (exceeds spec: 9 tabs vs 8) |
| Evidence-First Extraction | **PASS** |
| Model Extension | **PASS** |
| Builder Field Mapping | **PASS** (defect W-1 is diagnostic-only, postconditions all hold) |
| Summary Contract | **WARN** (W-4: single-line clause untested; behavior verified at runtime) |
| Versioning and Needs-Review | **WARN** (W-3: unit-level complete, production wiring missing) |

## Known Deltas Acknowledged by Design

| Delta | Status |
|-------|--------|
| Spec "8 robustness tabs" vs proposal/design/tasks "9" (`SequentialOptimization` is the 9th) | Accepted — implementation follows the 9-tab evidence; `spec.md` is the stale artifact (W-2). |
| WhatIf per-method toggles stay `raw_xml` (7 weekdays + 24 hours + 12 months) | Accepted — deferred API decision; a typed list/dict shape is required first. Recorded in `tasks.md` "Not Done" and `design.md` "Open Questions". |
| `rc_pf_min` / `wf_acceptance_pf_min` registered as inert | Accepted — SQX 144.2953 never emits `minValue` on a `<Column-Value>` (checked across `Build-Task1.xml`, 2 saved configs, 123 sampled real project configs: 0 occurrences). Registered in `TestCrosscheckMappingsHaveEvidence._INERT`, asserted as no-ops on real XML, and kept in the table so 213/213 parity still holds. Task 5.2 correctly dropped the fabricated `Column-Value minValue` fixture. |
| Acceptance `Condition` trees stay `raw_xml` | Accepted — the chosen design decision; PF minimums are reachable through `CrossChecksConfig`, not `BuildConfig`. |
| `wf_acceptance_min_conditions` / `wf_acceptance_min_markets` unreachable | Accepted — WFO declares neither node; kept for API compatibility, scoped to WFO acceptance, asserted as no-ops. Task 6.4. |

## Verdict

**PASS WITH WARNINGS** — 40/40 tasks complete; 6/6 requirements and 6/6 scenarios carry passing runtime evidence; the change-scoped gate (`tests/phase4 tests/cfx`) is green at 854 passed; no blockers and no critical findings. Archive is safe. The orchestrator should decide on W-1 (a one-line fix in `_apply_in_scope`: compare the *match* rather than the rewritten region) and W-3 (add one drift-hook call site) as follow-up work, and amend `spec.md` for W-2 so the spec stops under-constraining the catalog.
