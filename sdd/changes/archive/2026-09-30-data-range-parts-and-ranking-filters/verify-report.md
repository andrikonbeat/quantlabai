```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:67494b703675cd57667088fa8df82f3fa7a46bf29a5c92c77631ff5b431e4613
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 6/6
scenarios: 11/11
test_command: SQX_FORCE_MOCK=1 python3 -m pytest -q -rf
test_exit_code: 0
test_output_hash: sha256:c58fedfee8eab94d924a967f8a9f3287a9e95bd68395253ffb0f5a223c16cecc
build_command: python3 -m compileall -q sdk/quantlab/cfx sdk/quantlab/dsl sdk/quantlab/translate sdk/quantlab/phase4 sdk/quantlab/customproject
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

# Verification Report

**Change**: `data-range-parts-and-ranking-filters`
**Version**: N/A (OpenSpec delta spec, no version header)
**Mode**: **Strict TDD** (module `strict-tdd-verify.md` loaded and executed)
**HEAD under verification**: `ecabd1a` ("docs(sdd): record PR 3 completion and mark tasks 4.1-4.4, 5.1 done")
**Artifact store**: hybrid (OpenSpec file + Engram topic `sdd/data-range-parts-and-ranking-filters/verify-report`)
**Verified by**: dedicated `sdd-verify` sub-agent

---

## Completeness

| Metric | Value |
|--------|-------|
| Tasks in `tasks.md` | **18** (not 20 — see W-1) |
| Tasks marked `[x]` | **18** |
| Tasks marked `[ ]` | **0** |
| Requirements (both specs) | **6** |
| Scenarios (both specs) | **11** (5 + 6) |
| Artifacts present | proposal, exploration, design, 2 delta specs, tasks, apply-progress |

All 18 tasks are checked, so full verification was unblocked and run. Every task was then
independently re-verified against code on disk (see *Task-by-Task Verification*).

### Artifacts read before judging
`proposal.md`, `exploration.md`, `design.md`, `specs/advanced-ranking-filters/spec.md`,
`specs/data-range-parts/spec.md`, `tasks.md`, `apply-progress.md` (438 lines, full read).

### Task-by-Task Verification (18/18 — code + test exist and pass)

Every checkbox was re-verified against code on disk, not trusted from the checkmark.

| Task | Production code present (verified by grep/inspect) | Test present | Status |
|------|---------------------------------------------------|--------------|--------|
| 1.1 RED model round-trip tests | n/a (test task) | `test_patcher.py::TestAdvancedRankingModels` (5) | ✅ |
| 1.2 GREEN `ColumnValue`, `AdvancedRankingCondition`, `AdvancedRankingsConfig` | `models.py:121`, `:147`, `:170` | same 5 tests | ✅ |
| 1.3 RED `DataRangeParts` typed + raw_xml | n/a (test task) | `test_patcher.py::TestDataRangePartsModel` (6) | ✅ |
| 1.4 GREEN `DataRangeParts` | `models.py:209` + `_DATA_RANGE_PART_ELEMENTS:184` | same 6 tests | ✅ |
| 2.1 RED patcher behaviour (advanced) | n/a (test task) | `test_patcher.py::TestAdvancedRankingPatcher` (8) | ✅ |
| 2.2 GREEN `SetAdvancedRankings` + `AddAdvancedRankingCondition` instructions | `models.py:1150`, `:1157`; patchers `patcher.py:779`, `:786` | same 8 tests | ✅ |
| 2.3 RED patcher behaviour (data range) | n/a (test task) | `test_patcher.py::TestSetDataRangePartsPatcher` (5) | ✅ |
| 2.4 GREEN `SetDataRangePartsInstruction` | `models.py:1164`; applier `patcher.py:814` | same 5 tests | ✅ |
| 3.1 writer + dom wiring | `writer.py:532/535/568/611`; `dom.py:251/278` | `test_writer_section_merge.py` (12), `test_dom_advanced_ranking.py` (3) | ✅ |
| 3.2 RED DSL models | n/a (test task) | `test_advanced_ranking_dsl.py` (15) | ✅ |
| 3.3 GREEN DSL models | `dsl/models.py:124`, `:157`, `:189`, `:489`, `:494` | same 15 tests | ✅ |
| 3.4 translator mapping | `translator.py:87/90/122/142/250/263` | `test_translator_advanced_rankings.py` (11) | ✅ |
| 3.5 phase4 template + renderer | `templates.py:173/208/287`; `renderers.py:141` | `test_retester_template_rankings.py` (12), `test_advanced_rankings_renderers.py` (8) | ✅ |
| 4.1 RED golden CFX round-trip | n/a (test task) | `test_golden_advanced_rankings.py` (22) + fixture exists | ✅ |
| 4.2 GREEN fixture + round trip passes | fixture `retester-advanced-rankings.cfx` present (1155 B, valid ZIP) | same 22 tests pass | ✅ |
| 4.3 GREEN mixed simple + advanced | lazy-lane fix in `_apply_add_ranking_condition` | `test_mixed_rankings_compatibility.py` (10) | ✅ |
| 4.4 GREEN project-builder golden | phase4 emission cross-checked vs real SQX | `test_project_builder_golden_rankings.py` (12) | ✅ |
| 5.1 cleanup docstrings/scaffolding | no TODO/FIXME/XXX/HACK/scratch markers in any changed SDK file; no stray non-test files added | n/a (documentation task) | ✅ |

Test counts are `def test_` occurrences per file; totals reconcile with the 150 collected
change-owned cases.

---

## Build & Tests Execution

**Build / type-check**: ✅ Passed
```text
$ python3 -m compileall -q sdk/quantlab/cfx sdk/quantlab/dsl sdk/quantlab/translate sdk/quantlab/phase4 sdk/quantlab/customproject
(exit 0, zero bytes of output — no syntax/import-compile errors in any changed module)
```
`ruff` and `mypy` are **not installed** in the local `.venv` (they run in CI only, per
`AGENTS.md`), so lint/type-check evidence is limited to bytecode compilation.

**Declared test command (full suite)**: ✅ **4160 passed, 9 skipped, 0 failed** — exit `0`
```text
$ SQX_FORCE_MOCK=1 python3 -m pytest -q -rf
........................................................................ [100%]
4160 passed, 9 skipped, 36 warnings in 316.58s (0:05:16)
```
Run time: 5m16s. No failures, no errors, no collection errors.

**Change surface (project-builder golden path)**: ✅ **1085 passed, 4 skipped, 0 failed**
```text
$ SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/ tests/phase4/ tests/customproject/ tests/dsl/
1085 passed, 4 skipped, 2 warnings in 49.46s
```
Matches the orchestrator-supplied baseline (1085 passed / 4 skipped) exactly.

**Focused command named in `tasks.md` (PR 3 row)**: ✅ **188 passed** — exit `0`
```text
$ SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/test_patcher.py tests/phase4/test_project_builder.py
188 passed, 1 warning in 0.62s
```

**Change-owned test modules (the 10 new/extended files)**: ✅ **126 passed**
```text
$ SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/test_golden_advanced_rankings.py \
  tests/phase4/test_project_builder_golden_rankings.py tests/cfx/test_reader_advanced_rankings.py \
  tests/cfx/test_writer_section_merge.py tests/phase4/test_retester_template_rankings.py \
  tests/customproject/test_advanced_rankings_renderers.py tests/dsl/test_advanced_ranking_dsl.py \
  tests/cfx/test_dom_advanced_ranking.py
105 passed in 0.56s   (+21 in test_mixed_rankings_compatibility.py = 126 total)
```

**Coverage**: ➖ Not available — `pytest-cov`, `ruff`, and `mypy` are all absent from the
local environment. Per `strict-tdd-verify.md` this is reported, never flagged as a failure.

### Skip accounting (no change-owned test was silently disabled)
All 9 full-suite skips and all 4 change-surface skips are the same pre-existing set:
```text
tests/customproject/test_e2e_loadconfig.py:144,167,196,222:
  real sqcli boots a JVM (~2.5 min); set SQX_RUN_E2E=1 to run
```
`grep -rn "skip\|xfail"` across all 10 change test files returns **no** `skip`/`xfail`
marker (the single hit is the word "skips" inside a docstring). Nothing was disabled to
make the suite green.

### Regression attribution — none required
The brief anticipated failures in `tests/agents/test_adaptive_retest_agent.py`,
`sdk/tests/phase4/test_llm_generation_monitor.py`, `tests/substrate/test_executor.py`,
`tests/agents/test_research_agent_f1.py`, and `sdk/tests/test_knowledge.py`. **All of these
pass in the current run.** The full suite is green, so there is no failure to attribute and
no isolation worktree was needed. The likely reason is that the concurrent session's
`CrossChecksConfig` typed-model edits are present as *uncommitted working-tree changes*, so
the suite exercised HEAD **plus** those edits **plus** this change. This is worth stating
plainly: the green result attests the **working tree**, not a clean `ecabd1a` checkout.

Consequently:
- **(a) Caused by this change**: none. `0` CRITICAL.
- **(b) Pre-existing/unowned**: none observed.
- **(c) Concurrent-session CrossChecks work**: no longer producing failures.
- **Flat-lane `<Setting>` projection defect** (`_parse_settings_element` splitting one
  `<Setting>` into two, then holding at two): confirmed present in code, **not** regressed
  by this change, and correctly scoped out of
  `tests/phase4/test_project_builder_golden_rankings.py::test_data_range_parts_survive_the_reader_writer_cycle`
  with a docstring naming it as pre-existing. Correctly deferred to its own change.

---

## Requirements Compliance Matrix

### `specs/advanced-ranking-filters/spec.md` — 3 requirements, 5 scenarios

| Req | Scenario | Covering test (runtime-verified PASSED) | Result |
|-----|----------|----------------------------------------|--------|
| AR-1 Advanced Ranking Condition Model | Full attribute round-trip | `tests/cfx/test_patcher.py::TestAdvancedRankingModels::test_advanced_ranking_condition_round_trip_full` and `::test_column_value_round_trip_full_attributes` | ✅ COMPLIANT |
| AR-1 | Minimal valid condition | `tests/cfx/test_patcher.py::TestAdvancedRankingModels::test_advanced_ranking_condition_minimal` | ✅ COMPLIANT |
| AR-1 | CrossCheck block compatibility | `tests/cfx/test_patcher.py::TestAdvancedRankingPatcher::test_set_advanced_rankings_multiple_conditions` (`count("<Condition ") == 2` **and** `count("<Conditions>") == 1`); `test_reader_advanced_rankings.py::TestAdvancedRankingsParsing::test_multiple_conditions_keep_source_order`; the 3-`<Condition>` real SQX fixture; **plus a scenario-exact runtime probe (see S-4)** that round-trips a real `<Conditions CrossCheck="…">` archive through `CfxReader` → `CfxWriter` → `CfxReader` | ✅ COMPLIANT |
| AR-2 Simple Ranking Compatibility | Mixed simple and advanced conditions | `tests/cfx/test_mixed_rankings_compatibility.py::TestNeitherLaneIsDropped::test_simple_condition_survives_next_to_an_advanced_one`; `tests/phase4/test_translator_advanced_rankings.py::TestSimpleRankingCompatibility::test_simple_and_advanced_lanes_land_in_one_rankings_element` | ✅ COMPLIANT |
| AR-3 DSL Expression | DSL round-trip | `tests/phase4/test_translator_advanced_rankings.py::TestAdvancedRankingMapping` (7 tests incl. `test_filter_reaches_the_task_as_a_typed_conditions_block`, `test_every_filter_attribute_reaches_the_xml`, `test_nested_column_filter_attributes_reach_the_xml`); `tests/dsl/test_advanced_ranking_dsl.py` (15 tests) | ✅ COMPLIANT |

### `specs/data-range-parts/spec.md` — 3 requirements, 6 scenarios

| Req | Scenario | Covering test (runtime-verified PASSED) | Result |
|-----|----------|----------------------------------------|--------|
| DR-1 Typed Data Range Parts Model | Fully populated data range | `tests/cfx/test_patcher.py::TestDataRangePartsModel::test_data_range_parts_typed_fields_round_trip` | ✅ COMPLIANT |
| DR-1 | Partial typed fields with raw_xml fallback | `::TestDataRangePartsModel::test_data_range_parts_typed_and_raw_xml_coexist` | ✅ COMPLIANT |
| DR-1 | Unknown range passthrough | `::TestDataRangePartsModel::test_data_range_parts_unknown_range_lands_in_raw_xml`; `tests/cfx/test_reader_advanced_rankings.py::TestDataRangePartsParsing::test_unknown_subranges_are_parked_in_raw_xml` | ✅ COMPLIANT |
| DR-2 Configurable raw_xml Bridge | raw_xml override | `::TestDataRangePartsModel::test_data_range_parts_raw_xml_only_is_verbatim` | ✅ COMPLIANT |
| DR-2 | raw_xml combined with typed fields | `::TestDataRangePartsModel::test_data_range_parts_typed_and_raw_xml_coexist`; `tests/phase4/test_translator_advanced_rankings.py::TestDataRangePartsMapping::test_raw_xml_bridge_survives_translation`; `tests/cfx/test_writer_section_merge.py::TestDataRangePartsEmission::test_raw_xml_bridge_is_preserved_verbatim` | ✅ COMPLIANT |
| DR-3 Validation and Test Split Semantics | Split ratio preservation | `::TestDataRangePartsModel::test_data_range_parts_split_ratios_are_not_training_ratios`; `tests/cfx/test_reader_advanced_rankings.py::TestDataRangePartsParsing::test_split_ratios_stay_floats_and_distinct`; `tests/dsl/test_advanced_ranking_dsl.py::…::test_validation_and_test_ratios_stay_distinct` | ✅ COMPLIANT |

**Compliance summary**: **11/11 scenarios COMPLIANT**. **6/6 requirements** have
implementation plus at least one passing covering test.

Each scenario above was executed individually with `-v` and observed `PASSED` — not merely
found in the source tree.

### Scenario-exact runtime probe (AR-1 "CrossCheck block compatibility")

Because that scenario names an attribute the renderer's own signature cannot express, I
built the scenario literally and ran it against real archives rather than reasoning from the
source:

```text
input:  <Rankings><Conditions CrossCheck="WalkForwardOptimization" thresholdPct="50">
          <Condition use="true"> … ProfitFactor … </Condition>
          <Condition use="true"> … ReturnDDRatio … </Condition>
        </Conditions></Rankings>

CfxReader.read(src)  → conditions parsed: 2  ['ProfitFactor', 'ReturnDDRatio']
CfxWriter.write(...) → Rankings/Conditions/Condition count: 2
                        both nested under the SAME parent: True
                        parent attribs after round trip:
                          {'CrossCheck': 'WalkForwardOptimization', 'thresholdPct': '50'}
CfxReader.read(dst)  → conditions: 2  ['ProfitFactor', 'ReturnDDRatio']
```

Every clause of the scenario holds: the `CrossCheck`-bearing parent with multiple conditions
is accepted, each condition is rendered, and each remains nested under that same parent —
with the parent's attributes surviving the cycle via the `raw_xml` verbatim bridge. Scenario
is **COMPLIANT**. The narrower re-render limitation this surfaced is tracked separately as
S-4, because no scenario asserts it.

---

## Correctness (Static Evidence)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| AR-1 `AdvancedRankingCondition` model | ✅ Implemented | `sdk/quantlab/cfx/models.py:147`. All 10 required typed fields (`resultType`, `sampleType`, `direction`, `pctRatio`, `confidenceLevel`, `market`, `plType`, `subresult`, `class`, `name`) plus `column_values: list[ColumnValue]`. `ColumnValue` at `models.py:121`. XML attribute aliases + `populate_by_name=True` make `model_dump(by_alias=True)` reproduce real SQX names. |
| AR-2 Simple path untouched | ✅ Implemented | `AddRankingConditionInstruction` / `SetRankingsInstruction` unmodified. `test_simple_only_campaign_is_unchanged` and `test_simple_condition_is_kept_when_the_flat_lane_exists` pin it. |
| AR-3 DSL → model → XML | ✅ Implemented | `dsl/models.py:124,157` (`ColumnValueFilter`, `AdvancedRankingFilter`); `translate/translator.py:122 _to_cfx_ranking_condition`, `:87` loop, `:90` rejection of a filter with no `column_values`. |
| DR-1 `DataRangeParts` typed fields | ✅ Implemented | `models.py:209`; 19 typed fields (IST, ISC, ISV1–ISV10, OOS1, ISVEvery, OOSEvery, ValidationRatio, TestRatio, DateFrom, DateTo) driven by the single `_DATA_RANGE_PART_ELEMENTS` table (`models.py:184`) shared by `to_xml`/`from_xml` so the two directions cannot drift. Every field `| None = None` → omittable. |
| DR-2 `raw_xml` bridge | ✅ Implemented | `to_xml()` (`models.py:259`) returns `raw_xml` verbatim when it is the only populated lane, else concatenates typed elements + `raw_xml`. `from_xml()` (`models.py:279`) parks unrecognised children in `raw_xml`. |
| DR-3 Split semantics | ✅ Implemented | `validation_ratio` / `test_ratio` are distinct `float | None` fields, guarded by `_RATIO_FIELDS` (`models.py:206`) so `from_xml` coerces only ratios and never folds them into a training ratio. Patcher rejects ratios outside `(0,1)`. |
| Reader wiring | ✅ Implemented | `cfx/reader.py:465 _parse_advanced_rankings`, `:497 _parse_advanced_condition`, `:517 _column_value_elements`. Commits `da527ba` / `ff6336f`. |
| Writer wiring | ✅ Implemented | `cfx/writer.py:532 _append_merged_complex_section`, `:535 _append_data_range_parts`, `:568`, `:611` — one merged `<Rankings>` and one `<Data>` per `<Settings>`. |
| Dom helpers | ✅ Implemented | `cfx/dom.py:251 add_advanced_ranking_condition`, `:278 set_data_range_parts` — chainable, return the archive. |
| Template / renderer | ✅ Implemented | `phase4/templates.py:173 _build_retester_rankings_xml`, `:208`, `:287`; `customproject/renderers.py:141` `render_advanced_rankings`. |
| Golden fixture | ✅ Implemented | `tests/cfx/fixtures/retester-advanced-rankings.cfx` — a real SQX `Build-Task1.xml` (version `141.2219`) with 3 native-dialect `<Condition use="true">` children carrying `<Left-Side>/<Column-Value>`, `<Comparator>`, `<Right-Side>`, plus a real `<Data>` with `<Setups>/<OutOfSample>`. |

**Golden-fixture fidelity verified by direct inspection** (the fixture is a ZIP, so I
unzipped and read it): SQX writes the full 12-attribute set on `<Column-Value>` and **only**
`use` on `<Condition>`. The implementation's `build_conditions_xml` emits the full set on
both, which `test_condition_attributes_equal_sqx_exactly` proves *equivalent* because every
extra `<Condition>` attribute carries the value SQX's omission implies. This corroborates
the apply-progress correction recorded in `58283c2` — the code was right, the earlier comment
was wrong.

---

## Coherence (Design)

| Decision (from `design.md`) | Followed? | Notes |
|----------------------------|-----------|-------|
| New instruction path instead of extending flat ranking conditions | ✅ Yes | `AddAdvancedRankingConditionInstruction`, `SetAdvancedRankingsInstruction`, `SetDataRangePartsInstruction` are additive; `AddRankingConditionInstruction` untouched. |
| `raw_xml` bridge for data range parts | ✅ Yes | `DataRangeParts` = typed fields + verbatim passthrough, exactly as designed. |
| Backward compatibility strategy | ✅ Yes | `test_simple_only_campaign_is_unchanged`, `test_task_without_filters_is_unchanged`, `test_no_filters_keeps_the_previous_rankings_block` pin byte-compatible no-op behaviour. |
| File-change table: `models.py`, `patcher.py`, `writer.py`, `dom.py`, `translator.py`, `dsl/models.py`, `phase4/templates.py`, `customproject/renderers.py` | ✅ Yes | All 8 modified. Diff touches exactly these plus `cfx/reader.py` (added by the reader-wiring commits, required by 4.1). |
| Test files: `tests/cfx/test_patcher.py`, `tests/phase4/test_project_builder.py`, `tests/cfx/fixtures/retester-advanced-rankings.cfx` | ✅ Yes / ⚠️ amended | The fixture exists. `test_project_builder.py` was **not** rewritten; 4.4 was added as a new module `tests/phase4/test_project_builder_golden_rankings.py` (318 lines) instead. Deviation documented in apply-progress and justified (it also avoids the file the concurrent session owned). Not a spec break. |
| Design interface block field aliases | ⚠️ Deviation (justified) | `design.md` declared fields without XML aliases; without them `model_dump(by_alias=True)` would emit Python names and lose real SQX attribute names, breaking the spec's CFX-fidelity criterion. Aliases added + recorded. |
| `DataRangeParts` typed element names | ⚠️ Deviation (disclosed) | `<IST>` / `<OOSEvery>` are a QuantLab convention; real SQX writes `<Setups>` / `<OutOfSample>`. Disclosed in the model docstring, in `apply-progress`, and deliberately excluded from the 4.4 parity assertions. Honest, documented, and the reason `raw_xml` exists. |

---

## TDD Compliance (Strict TDD module)

`apply-progress.md` contains a **TDD Cycle Evidence** table in each of its four work units.

| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | ✅ | Present in all 4 work units (lines 28–40, 129–140, 234–243, 336–344). |
| All tasks have tests | ✅ | 18/18 tasks map to shipped tests; 150 change-owned test cases exist (126 in the 10 dedicated modules + 24 new in `test_patcher.py`). |
| RED confirmed (test files exist) | ✅ | 18/18 named test files exist and were executed in this run. |
| GREEN confirmed (tests pass) | ✅ | 150/150 change-owned tests pass; change surface 1085 passed / 0 failed; full suite 4160 passed / 0 failed. |
| Triangulation adequate | ✅ | No behaviour rests on a single case. Examples: multiple conditions × 2 (`test_set_advanced_rankings_multiple_conditions`, `test_multiple_conditions_keep_source_order`), ratio validation × 3 (`rejects_ratio_outside_unit_interval`, `rejects_zero_ratio`, `split_ratios_are_not_training_ratios`), mixed lanes × 2. |
| Safety Net for modified files | ✅ | Every work unit records a captured pre-change baseline (`9 failed/80 passed`, `8 failed/126 passed`, `8/127`, `260/4`) before modifying `models.py`, `patcher.py`, `writer.py`, `dom.py`. |

**TDD Compliance**: **6/6 checks passed.**

Additional evidence beyond the protocol: the apply phase ran **mutation verification** on
every work unit and reports the two initially-surviving mutants, both investigated rather
than waived (a real gap in the translator's nested `ColumnValue` assertions, fixed by
`test_nested_column_filter_attributes_reach_the_xml`). I independently confirmed the
strongest of these claims is a genuine cross-oracle, not self-agreement:
`test_emission_reads_back_identically_to_the_real_sqx_export` builds a QuantLab CFX and the
real SQX export, parses both with the **same** reader, and asserts the typed models are
equal — a self-consistent dialect mistake cannot pass it.

---

## Test Layer Distribution

| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | ~118 | 7 | pytest |
| Integration | ~30 | 5 | pytest (real `CfxArchive` → `CfxWriter.write` → real `.cfx` ZIP → `CfxReader.read`) |
| E2E / Golden | ~2 | 2 | pytest + real SQX fixture |
| **Total (change-owned)** | **150** | **11** | |

There is no browser, `page.`, `userEvent`, or HTTP dependency anywhere in this change's
tests. The "integration" layer is genuinely end-to-end for this domain: it writes and
re-reads real `.cfx` ZIP archives with no SQX daemon or mock boundary. The golden layer is
the strongest form available — a **real** SQX 144/2953 export as the independent oracle.
Informational only (SUGGESTION-level per the module).

---

## Changed File Coverage

**Coverage analysis skipped — no coverage tool detected** (`pytest-cov` not installed).
Informational, not a failure, per `strict-tdd-verify.md` Step 5d. Proxies were used instead
and all are strong: every changed SDK module has a dedicated test module, and all 150
change-owned tests pass.

---

## Assertion Quality Audit (Step 5f — MANDATORY)

Scanned all 10 dedicated test files plus the 24 added cases in `tests/cfx/test_patcher.py`.

| Banned pattern | Findings |
|----------------|----------|
| Tautologies (`assert True`, `assert 1 == 1`) | **0** |
| Assertions that never call production code | **0** — every test drives real archive/reader/writer or model code |
| Ghost loops over possibly-empty collections | **0** |
| Incomplete TDD cycle (preconditions prevent the path) | **0** — the two loop-based assertions are non-vacuous by construction: `test_condition_attributes_equal_sqx_exactly` iterates `emitted.attrib` guarded by `assert sqx <= set(emitted.attrib)`, and `test_a_non_default_condition_attribute_is_actually_emitted` exists **specifically** as the vacuity guard for it |
| Smoke-test-only ("renders without crash") | **0** |
| Implementation-detail coupling (mock call counts, CSS classes) | **0** |
| Mock-heavy files (mocks > 2× assertions) | **0** — this change introduces **no mocks at all** |
| Empty-collection asserts without a non-empty companion | **0** — all 4 (`test_data_range_parts_defaults_emit_no_typed_elements`, `task.data.settings == {}`, `len(root.find("Conditions")) == 0`, `column_values == []`, `advanced_ranking_filters == []`) are paired with populated-path tests in the same file |
| Type-only asserts used alone | **0** — all 25 `is not None` / `isinstance` hits are pre-condition guards followed by value assertions |

Notable quality strengths worth recording:
- `test_simple_condition_survives_next_to_an_advanced_one` docstring states the exact
  historical bug (`if self._task.rankings` guard silently discarding the simple half on the
  phase4 retester template) — the test documents *why* it exists, not just *what* it asserts.
- `test_flat_settings_land_after_the_verified_native_prefix` asserts the **absence** of an
  SQX-defined position (0 flat `<Setting>`s and 0 `Criterion*@` keys in both real exports)
  and pins the merge order as a deliberate, documented choice rather than an assumption.
- Docstrings consistently record rejected alternatives and measured traces (e.g. the
  four-cycle `1 <Setting> → 2, then holds at 2` projection trace).

**Assertion quality**: ✅ **All assertions verify real behavior. 0 CRITICAL, 0 WARNING.**

---

## Quality Metrics

**Linter**: ➖ Not available — `ruff` not installed locally (CI-only per `AGENTS.md`).
**Type Checker**: ➖ Not available — `mypy` not installed locally (CI-only).
**Compile check**: ✅ `python3 -m compileall` exit 0 across all 5 changed packages.
Informational only; never flagged as failures.

---

## Issues Found

### CRITICAL — None (0)

No requirement is unimplemented, no scenario is untested or failing, no task is unchecked,
every declared command exits `0`, and the full suite is green.

### WARNING (3)

**W-1 — Task count is 18, not 20.** `tasks.md` defines 18 tasks (Phase 1: 4, Phase 2: 4,
Phase 3: 5, Phase 4: 4, Phase 5: 1) and all 18 are checked. The `apply-progress.md` Work
Unit 4 status line asserts "**20/20 tasks complete**", and the orchestrator brief repeated
20/20. This is a **counting error in the reporting, not missing work** — every numbered
task in `tasks.md` is checked and independently re-verified below. Per instructions I did
**not** edit `tasks.md`; flagging for the orchestrator to decide whether the apply-progress
status line should be corrected.

**W-2 — `apply-progress.md` Work Unit 4 task numbering contradicts `tasks.md`.**
`tasks.md` has 4.1 = golden round-trip test, 4.2 = create fixture, **4.3 = mixed
simple+advanced compatibility**, **4.4 = project builder golden**. The apply-progress "Task
status" list reads 4.2 = mixed simple+advanced, 4.3 = writer merge-order check — i.e. 4.2
and 4.3 are transposed relative to `tasks.md`, and relative to apply-progress's *own* TDD
table, which correctly ties `test_simple_condition_survives_next_to_an_advanced_one` to 4.3.
The **work** is complete under either numbering; only the labels disagree. Documentation
consistency issue only.

**W-3 — Two commits exceeded the 400-line review budget.** Measured via
`git show --shortstat`:
| Commit | PR | Changed lines | Budget |
|---|---|---|---|
| `4be6362` | PR 1 | 795 + 4 = **799** | ❌ +399 |
| `e39bb96` | PR 1b | 454 + 1 = **455** | ❌ +55 |
| `228ec63` | PR 3 | 400 | ✅ at budget |
| all 11 others | | ≤ 370 | ✅ |
`e39bb96` was acknowledged and partially mitigated in apply-progress ("~453 lines before
slicing, over the budget", reduced to 454/1) but still ends at 455. `4be6362` at 799 lines
was never acknowledged. `tasks.md` forecast 450–550 lines with "400-line budget risk:
Medium"; actual total is 4704 insertions / 56 deletions across 14 commits. Reviewer-load
concern under `sdd-phase-common.md` §E, not a correctness defect.

### SUGGESTION (4)

**S-4 — The advanced-ranking *re-render* path drops unknown `<Conditions>` parent
attributes** (found while verifying AR-1; not asserted by any scenario, so it does not affect
compliance). `build_conditions_xml(conditions, indent="  ")` hardcodes
`f"{indent}<Conditions>"` with no attribute parameter. Consequence, proven at runtime:
- read → write → read **preserves** a parent's `CrossCheck`/`thresholdPct` (via the verbatim
  `raw_xml` lane) — this is the path the spec scenario exercises, and it is correct;
- but *applying* an `AddAdvancedRankingConditionInstruction` / `SetAdvancedRankingsInstruction`
  re-renders the block through `build_advanced_rankings_xml`, which **drops** those parent
  attributes. I reproduced this: `build_advanced_rankings_xml(cfg.conditions)` on a
  `CrossCheck="WalkForward"` block emits a bare `<Conditions>`.
No test covers this, and the real SQX 144/2953 `<Rankings>` export carries no `CrossCheck`
attribute (the only `CrossCheck=` usages in this codebase sit under `<AcceptanceSettings>`,
a different lane owned by a different change), so nothing is broken today. Worth a
characterization test — or an explicit documented decision that re-rendering normalises the
parent — before an agent edits rankings on a file that does carry such an attribute.

**S-1** — `DataRangeParts` typed element names (`<IST>`, `<OOSEvery>`, …) have **no verified
SQX counterpart**; real SQX writes `<Setups>`/`<OutOfSample>`. Correctly disclosed in the
model docstring and excluded from the 4.4 parity assertions, so nothing is wrong today. But
emitting `<IST>` into a config SQX must consume is a latent interop risk. Worth a
follow-up that ingests a real SQX export carrying IS/OOS sub-ranges and reconciles the
mapping — that evidence is exactly what would justify replacing the convention with verified
names.

**S-2** — The green full-suite result attests the **working tree**, which includes a
concurrent session's uncommitted `CrossChecksConfig` edits, not a clean `ecabd1a` checkout.
If archive needs a result provable from the committed history alone, re-run in a
`git worktree` at `ecabd1a`. (I did not need one: a green suite admits no attribution.)

**S-3** — `sdk/quantlab/cfx/patcher.py` grew by 376 lines across this change and is now the
single densest module in the ranking lane. The extracted `build_conditions_xml` /
`_render_attributes` helpers already prevent the second dialect copy. No action needed now;
flagging so the module does not become the next place a duplicate renderer appears.

---

## Verdict

**PASS WITH WARNINGS**

All 6 requirements are implemented with passing covering tests and **all 11 scenarios are
compliant**; all 18 tasks are genuinely satisfied (re-verified against code, not just
checkmarks); the full suite passes 4160/4160 with zero failures attributable to this change.

The warnings are not correctness defects: W-1 and W-2 are reporting-hygiene mismatches
(the real task count is 18, and apply-progress transposes its own 4.2/4.3 labels), and W-3 is
review-budget history on two commits. The most substantive item is S-4 — the
advanced-ranking *re-render* path drops unknown `<Conditions>` parent attributes — which no
scenario asserts and which does not affect the verified SQX dialect. Nothing here blocks
archive; S-4 and the S-1 element-name convention are the items worth carrying forward.
