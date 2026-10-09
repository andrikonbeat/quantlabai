# Apply Progress: data-range-parts-and-ranking-filters

**Mode**: Strict TDD
**Artifact store**: hybrid (Engram + OpenSpec)
**Delivery strategy**: auto-chain
**Chain strategy**: stacked-to-main

## Work Unit 1 — Typed models + advanced ranking patcher (PR 1) — COMPLETE

**Commit**: `4be6362` — `feat(cfx): typed models and patcher for advanced ranking filters`

### Start state

Uncommitted base already contained `ColumnValue`, `AdvancedRankingCondition`,
`AdvancedRankingsConfig`, the two advanced-ranking instructions, patcher
validators/appliers and 9 tests, but the models were unusable and 2 patcher
helpers referenced `ET` from a function-local import.

**Baseline at HEAD**: `tests/cfx/` = 9 failed, 80 passed (all 9 CrossChecks, pre-existing).
**Baseline with inherited WIP**: `tests/cfx/` = 17 failed, 86 passed (9 advanced ranking + 8 CrossChecks).

### End state

`tests/cfx/test_patcher.py -k Advanced` = **13 passed, 0 failed**.
`tests/cfx/` at the PR1 commit = **10 failed, 110 passed** (failures identical to the HEAD
baseline set; zero regressions introduced).

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 RED: model round-trip tests | `tests/cfx/test_patcher.py` | Unit | 9 failed/80 passed (HEAD baseline captured) | Tests written and failing on inherited models | 5 model tests pass | 5 cases (full, defaults, round-trip, minimal, config) | Docstrings record SQX alias rationale |
| 1.2 GREEN: `ColumnValue`, `AdvancedRankingCondition`, `AdvancedRankingsConfig` | `tests/cfx/test_patcher.py` | Unit | 9/80 baseline | 5 tests failed: `class_` rejected by alias-only pydantic v2 | 5 pass after `ConfigDict(populate_by_name=True)` + XML attribute aliases | 5 cases | Docstrings only; no behavior change |
| 2.1 RED: patcher behaviour tests | `tests/cfx/test_patcher.py` | Unit | 17/86 with WIP | 4 patcher tests failed (alias cascade + `ET` NameError) | 4 pass | +3 added: real-CFX attribute set, repeat-append retention, no-clobber guard | Extracted `_render_attributes` + `_CONDITION_ATTRS`/`_COLUMN_VALUE_ATTRS`; removed `_condition_to_element` (~50 lines) |
| 2.2 GREEN: `SetAdvancedRankingsInstruction`, `AddAdvancedRankingConditionInstruction` | `tests/cfx/test_patcher.py` | Unit + runtime | 17/86 | 4 failing | 13/13 pass | 3 added cases, all mutation-verified | Module-level `import xml.etree.ElementTree as ET`; parse→extend→re-render replaces the ET round-trip |

**Test summary**: 13 advanced-ranking tests total (10 inherited + 3 added triangulation),
13 passing. Layers: Unit 13, Integration 0, E2E 0. Approval tests: none (no refactor-only task).
Pure functions created: 1 (`_render_attributes`).

### Mutation verification (proof the tests are real)

| Mutation | Result |
|----------|--------|
| Remove the no-clobber guard (restore silent overwrite) | `test_add_advanced_ranking_condition_refuses_to_clobber_simple_rankings` FAILS |
| Revert to omit-defaults attribute emission (original broken policy) | `test_set_advanced_rankings_generates_nested_xml` + `test_column_value_matches_real_sqx_cfx_attribute_set` FAIL |

### Work Unit Evidence

| Evidence | Value |
|----------|-------|
| Focused test command and exact result | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/test_patcher.py -k "Advanced"` → **13 passed, 37 deselected in 2.66s** (exit 0) |
| Runtime harness command/scenario and exact result | Real integration path: build `CfxArchive` → `CfxPatcher.set_advanced_rankings` + `add_advanced_ranking_condition` → `CfxWriter.write` to a real `.cfx` zip → `CfxReader.read` back. Result: 700-byte cfx, 2 `<Condition>` elements parsed from `Build-Task1.xml`, defaults + aliases intact, reader round-trip preserved both conditions. **PASS** |
| Rollback boundary | Revert commit `4be6362` only. Touches `sdk/quantlab/cfx/models.py` (4 advanced-ranking hunks only), `sdk/quantlab/cfx/patcher.py`, `tests/cfx/test_patcher.py`. CrossChecks work in the same `models.py` was deliberately **excluded from the commit** and remains unstaged, so reverting cannot remove unrelated CrossChecks work. |

### Deviations from design.md

1. **Field aliases added** (`column_type`→`columnType`, `result_type`→`resultType`,
   `sample_type`→`sampleType`, `pl_type`→`plType`, `confidence_level`→`confidenceLevel`,
   `pct_ratio`→`pctRatio`) plus `ConfigDict(populate_by_name=True)`. design.md's interface
   block declared these fields without aliases, but that would make
   `model_dump(by_alias=True)` emit Python field names and lose the real SQX attribute
   names. The spec's acceptance criterion is CFX fidelity, so the aliases are required.
2. **`writer.py` not modified** although design.md listed it. Verified unnecessary:
   `CfxWriter._serialise_task` already calls `_append_complex_section(root, "Rankings",
   task.rankings_section)` (writer.py:523), so the nested XML serialises unchanged.
   Task 3.1 belongs to PR 2.
3. **`SetDataRangePartsInstruction` / `DataRangeParts` not implemented.** Tasks 1.3, 1.4,
   2.3, 2.4 are the Data-range-parts half of PR 1's unit as written in tasks.md. They were
   **not** in the orchestrator's assigned PR1 slice (which named only the advanced-ranking
   models/patcher), so they remain open. See "Remaining Tasks".

### Issues found

1. **Writer emits duplicate `<Rankings>`** — `_append_settings_section(root, "Rankings", task.rankings)`
   (writer.py:507) and `_append_complex_section(root, "Rankings", task.rankings_section)`
   (writer.py:523) both fire. Verified **pre-existing**: the HEAD-owned `set_rankings`
   instruction produces the identical duplicate. Out of PR1 scope; relevant to task 3.1.
2. **Test assertion was objectively wrong** — `test_set_advanced_rankings_multiple_conditions`
   and `test_add_advanced_ranking_condition_appends_to_existing` asserted
   `xml.count("<Condition") == 2`, which also matches the `<Conditions>` wrapper that the
   same test file requires (`assert "<Conditions>" in xml`). The two assertions were
   mathematically incompatible. Corrected to `count("<Condition ")` (trailing space, matches
   only the opening element) and added an explicit `count("<Conditions>") == 1`. Intent preserved.
3. **Concurrent session in the same working tree** — `sdk/quantlab/guardian/orchestrator.py`,
   `sdk/quantlab/pipeline/errors.py`, `sdk/quantlab/pipeline/stages/agent_stages.py`,
   `sdk/tests/test_pipeline_agent_stages.py` became modified mid-session (mtime 01:24–01:26,
   before this batch's edits at 01:31) and `tests/cfx/test_crosschecks_catalog.py` appeared
   untracked. Belong to other changes. None were staged or committed.

### Remaining tasks

- [ ] 3.1–3.5 integration/wiring (PR 2): `dom.py`, DSL models, translator, phase4 templates, renderers
- [ ] 4.1–4.4 testing (PR 3): golden fixture round-trip, mixed simple+advanced, project builder
- [ ] 5.1 cleanup

### Status

4/17 tasks complete. PR 1 (advanced ranking foundation + patcher) is complete and
self-contained. Ready for the Data-range-parts remainder of the foundation unit, then PR 2.

---

## Work Unit 2 — DataRangeParts + patcher instruction (PR 1b) — COMPLETE

**Commit**: `e39bb96` — `feat(cfx): data range parts model and patcher instruction`
**Tasks**: 1.3, 1.4, 2.3, 2.4 (data-range-parts half of the PR 1 foundation unit)

### Start state

`tests/cfx/` baseline = **8 failed, 126 passed**. All 8 failures are pre-existing
concurrent CrossChecks work owned by another change
(`tests/cfx/test_patcher.py::TestSetCrossChecksTyped`,
`tests/cfx/test_reader_crosschecks.py::{TestReaderCrossChecksDialectDetection,
TestWriterCrossChecksRoundTrip,TestWriterSetCrosschecksTyped}`).

### End state

`tests/cfx/test_patcher.py -k "DataRangeParts"` = **11 passed, 50 deselected**.
`tests/cfx/` = **8 failed, 137 passed** — the same 8 pre-existing failures, +11 new
passing tests, zero regressions.

Commit-boundary proof (the commit was tested in isolation from a concurrent working tree):
`HEAD` alone = 9 failed/120 passed → `HEAD + staged PR1b` = 9 failed/131 passed. Identical
failure set, +11 passing. The 9th failure is the concurrent session's untracked
`tests/cfx/test_crosschecks_models.py`, which is untracked at HEAD and therefore part of
neither state.

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.3 RED | `tests/cfx/test_patcher.py` | Unit | 8 failed/126 passed captured | 6 model tests written; all 6 failed with `ImportError: cannot import name 'DataRangeParts'` | 6 pass after the model lands | 6 cases: typed round-trip, defaults, raw-only, typed+raw combined, unknown-child passthrough, multi-segment split | Extracted `_DATA_RANGE_PART_ELEMENTS` as the single source of truth shared by `to_xml`/`from_xml` so the directions cannot drift |
| 1.4 GREEN | `sdk/quantlab/cfx/models.py` | Unit | 8/126 | `ImportError` | 6/6 pass | 6 cases | 19-field mapping table replaces per-field branching in both directions |
| 2.3 RED | `tests/cfx/test_patcher.py` | Unit | 8/126 | 5 patcher tests written; failed on the same `ImportError` | 5 pass after the instruction lands | 5 cases: set instruction, raw-only set, ratio=1.0 rejected, ratio=0.0 rejected, no-clobber of `set_date_range`'s flat `Data` | Dispatch via `_VALIDATORS`/`_APPLIERS` maps rather than an `if/elif` chain |
| 2.4 GREEN | `sdk/quantlab/cfx/patcher.py` | Unit + runtime | 8/126 | 5 failing | 5/5 pass | 5 cases, all mutation-verified | Applier stores the typed `DataRangeParts` model, not a pre-rendered blob, so typed fields stay queryable for PR2 wiring |

**Test summary**: 11 data-range-parts tests total (6 model + 5 patcher), 11 passing.
Layers: Unit 10, Integration 1 (patcher-through-archive). Pure functions created: 1
(`_DATA_RANGE_PART_ELEMENTS` mapping; `to_xml`/`from_xml` are pure string/ET transforms).

### Mutation verification (proof the tests are real)

| Mutation | Result |
|----------|--------|
| Invert the element-name lookup in `from_xml` | 3 tests FAIL |
| Fold `ValidationRatio`/`TestRatio` into a training ratio | 3 tests FAIL |
| Drop the `raw_xml` verbatim passthrough in `to_xml` | 2 tests FAIL |
| Disable the `(0, 1)` ratio validator | 2 tests FAIL |

### Work Unit Evidence

| Evidence | Value |
|----------|-------|
| Focused test command and exact result | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/test_patcher.py -k "DataRangeParts"` → **11 passed, 50 deselected in 1.09s** (exit 0) |
| Runtime harness command/scenario and exact result | `/tmp/opencode/harness_drp.py` (untracked, not in the commit): builds a real `CfxArchive`, applies `set_date_range` → `set_advanced_rankings` → `set_data_range_parts`, round-trips `DataRangeParts.to_xml`/`from_xml`, writes via `CfxWriter.write` and re-reads. Result: valid 672-byte `.cfx`, 2 entries, advanced rankings and the flat `Data` SettingsSection coexisting, DataRangeParts model round-trip exact. **PASS**. Typed-section *persistence into the CFX* is not asserted here because writer emission is task 3.1 (PR 2) |
| Rollback boundary | Revert commit `e39bb96` only. Touches `sdk/quantlab/cfx/models.py` (4 data-range-parts hunks only), `sdk/quantlab/cfx/patcher.py` (30 additive lines), `tests/cfx/test_patcher.py` (11 additive tests). `tasks.md` check-marks and this progress file are SDD state, not in the commit. The 13 concurrent CrossChecks hunks in the same `models.py` were **excluded from the commit** and remain unstaged in the working tree, so reverting cannot remove unrelated work |

### Deviations from design.md

1. **Staged via index blob, not hunk-level `git apply`.** `models.py` is interleaved with
   13 concurrent CrossChecks hunks, and `git apply --cached --recount` rejected the filtered
   patch (`error: patch with only garbage at line 5`) on a dirty index. Built the intended
   `models.py` content by replaying only the 4 own hunks onto `HEAD:models.py`, verified it
   parses and contains zero CrossChecks-session content, then wrote it with
   `git hash-object -w` + `git update-index --cacheinfo`. The staged blob was diffed against
   the worktree file to prove the exclusion.
2. **`tasks.md` not committed.** The repo tracks only *some* `openspec/changes/` content, and
   committing the 60-line checklist pushed the slice to 514 changed lines. Kept the commit at
   454 insertions / 1 deletion and left `tasks.md` as working state, consistent with how the
   PR 1 commit was scoped.
3. **`validation_ratio` and `test_ratio` remain distinct fields** and are never folded into a
   training ratio, per the explicit user constraint, even though it means the two-part split
   and the IS split express overlapping information.

### Issues found

1. **PR1b-only diff was ~453 lines before slicing, over the 400-line review budget.** Reduced
   by excluding the SDD checklist and, more importantly, by keeping the element mapping in one
   shared table instead of 19 pairs of per-field branches in each direction. Final commit is
   454 insertions / 1 deletion across 3 files; only the two one-line corrections to existing
   assertions account for the deletion.
2. **Patcher originally stored rendered XML in `raw_xml`.** That made the typed fields
   unreachable to the DSL/renderer wiring planned for PR 2. Corrected during apply so the
   instruction stores the `DataRangeParts` model; `to_xml()` is called at serialisation time.
3. **DataRangeParts element names are a QuantLab convention, not verified SQX output.** SQX's
   data-range sub-range schema is a documented gap with no verified export in this repo. This
   is recorded in the module comment and is the reason `raw_xml` passthrough exists: callers
   holding genuine SQX evidence emit it verbatim. The flat design.md interface uses
   `str | None` per segment rather than a nested name/role/ratio model; reconcile with the
   broader "name / sample type / segment role" prompt wording at design time if that model is
   wanted.
4. **Self-inflicted working-tree disruption during commit-boundary verification.** Using
   `git stash --keep-index` / `git stash pop` / `git stash drop` to isolate the commit
   inadvertently removed the concurrent session's uncommitted work, including 13 CrossChecks
   hunks in `models.py`. Recovered in full from the dangling stash commit
   `aeb7b1c27d4a60683e85da9ee734c05abbfc6373`; all 9 affected files verified **byte-identical**
   to the snapshot, the two `openspec/changes/orchestrated-subagent-wiring/` deletions
   (moved to `archive/2026-08-15-`) re-deleted, and `tests/cfx/` returned to 8 failed/137
   passed. **No data lost, but this was avoidable**: the next isolation attempt must use
   `git worktree` or `git archive` into a temp dir, never `stash`, when another session is
   writing to the same tree.

### Remaining tasks

- [ ] 3.1–3.5 integration/wiring (PR 2): `dom.py`, DSL models, translator, phase4 templates, renderers
- [ ] 4.1–4.4 testing (PR 3): golden fixture round-trip, mixed simple+advanced, project builder
- [ ] 5.1 cleanup

### Status

8/17 tasks complete. PR 1a (advanced ranking) and PR 1b (data range parts) are both
committed and self-contained. Next: PR 2 (3.1–3.5), which also owns the
`writer.py`/`dom.py` wiring that makes the typed sections persist into the CFX.

---

## Work Unit 3 — Integration / wiring (PR 2), tasks 3.1–3.5 — COMPLETE

**Mode**: Strict TDD (RED first, mutation-verified per work unit)
**Delivery**: `auto-chain` / `stacked-to-main`. Seven commits, each a self-contained
deliverable with its tests, every one inside the 400-changed-line review budget.

| Commit | Unit | Changed lines |
|--------|------|---------------|
| `63232a9` | 3.1 writer merges `<Rankings>`/`<Data>` | 307 |
| `8629da7` | 3.1 dom.py chainable helpers | 138 |
| `d19e693` | 3.2–3.3 DSL models | 370 |
| `52c0dcf` | writer raw_xml re-wrap bugfix | 62 |
| `815c0c0` | 3.4 translator mapping | 357 |
| `79b7496` | 3.5 renderer support | 232 |
| `3768a89` | 3.5 phase4 template placeholders | 179 |

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 3.1 (writer) | `tests/cfx/test_writer_section_merge.py` | Unit + runtime | 8 failed/127 passed | 6 failures | 14 pass | merge both lanes, data-range, empty placeholder, multi-sibling raw_xml, single `<Rankings>`/`<Data>` | `_append_merged_complex_section` / `_append_data_range_parts` split from the flat path |
| 3.1 (dom) | `tests/cfx/test_dom_advanced_ranking.py` | Unit | 8/127 | `ImportError` | 31 pass (with 3.2) | append-to-existing, set-replaces, chain order, defaults | chainable methods returning the archive, matching `add_timeframe` style |
| 3.2–3.3 | `tests/dsl/test_advanced_ranking_dsl.py` | Unit | 260 passed/4 skipped | 6 failures | 31 pass | defaults, validation, field-set drift guard vs CFX model, snake_case construction | `DataRangePartsDSL` maps by `**splat`; a test asserts both field sets are identical so the splat cannot silently drop one |
| 3.4 | `tests/phase4/test_translator_advanced_rankings.py` | Integration | 260/4 | 9 failed, 1 passed | 11 pass | every condition attr, **every nested ColumnValue attr**, multi-filter, simple-only unchanged, simple+advanced in one `<Rankings>`, raw_xml bridge, absent parts | validation that every filter names ≥1 column (a `<Condition>` with no `<Column-Value>` constrains nothing) |
| 3.5 (renderer) | `tests/customproject/test_advanced_rankings_renderers.py` | Unit + integration | 248 passed/4 skipped | `ImportError` | 8 pass | nested block, element order, empty list, **byte-identical to the patcher renderer**, no-op without filters | `build_conditions_xml` extracted to `cfx.patcher` and shared by all three consumers instead of a second copy of a verified dialect |
| 3.5 (template) | `tests/phase4/test_retester_template_rankings.py` | Unit + E2E | 1020 passed/4 skipped | 8 failed, 4 passed | 12 pass | no-placeholder block pinned **byte for byte**, element order, multi-filter, single `<Rankings>`/`<Data>`, typed parts, full archive round trip | `_build_retester_rankings_xml` extracted; scalars stay ahead of `<Conditions>` per SQX order |

### Mutation verification (every mutant was killed)

Writer: merge branches, data-range branch, empty-placeholder branch. DSL: missing
snake_case construction. Translator: dropped `column_values` validation, list truncation,
skipped simple criteria, and two attribute-mapping mutants. Renderer: dropped
`rankings_section`, emit-on-empty, wrong element order, truncated conditions. Template:
element order, unattached `data_range_parts`, unconditional empty `<Conditions>`, dropped
thread-through argument.

Two mutants initially **survived** and both were investigated rather than waived:

1. **Translator nested `ColumnValue` attributes** — real gap. The condition's attributes
   were asserted but the nested column's were not, so a silently defaulted column filter
   (wrong direction/subresult) passed. Added
   `test_nested_column_filter_attributes_reach_the_xml`; mutant then killed.
2. **Renderer condition-attribute mapping** — *not* a gap. The mutant edits the shared
   `build_conditions_xml`; verified it **is** killed by `tests/cfx/test_patcher.py`
   (2 failures). The renderer's own contract is composition, guarded by the
   byte-identical assertion, so no redundant test was added.

### Deviations from design

None. One deliberate hardening beyond the literal spec: the translator rejects an
advanced filter with no `column_values`, because SQX would accept such a `<Condition>`
and silently rank on nothing.

### Issues found

- **Writer bug (`52c0dcf`)**: `DataRangeParts.to_xml()` returns `raw_xml` verbatim when no
  typed field is set, so a single raw element parsed to a childless non-`<Data>` element
  that the writer appended directly under `<Settings>`. The pre-existing empty-placeholder
  guard was also over-broad (it keyed on child count alone and would have dropped that
  same block). Found by the translator's raw_xml test — the writer suite only covered a
  multi-sibling raw_xml, which takes the re-parse branch.
- **Test-authoring errors, not product bugs** (corrected, not worked around): guessed
  `<IS>` where the model emits `<IST>`; and assumed the base `<Data>` held one `<Setting>`
  when it legitimately holds three (Symbol@symbol, Symbol@name, Timeframe1@value).
- **Architectural boundary preserved**: `customproject/models.py` documents itself as free
  of a runtime `cfx` dependency. `advanced_ranking_filters` uses a `TYPE_CHECKING` import
  and was asserted at runtime (`import quantlab.customproject.models` pulls in **no**
  `quantlab.cfx` module).

### End state and failure attribution

Full suite: **10 failed, 4079 passed, 10 skipped, 5 errors**. Zero regressions from this
work unit, proven three ways:

| Failure set | Count | Cause | Proof |
|---|---|---|---|
| `test_research_agent_f1` (4), `test_knowledge` (1) | 5 | pre-existing | fails identically in the `e39bb96` baseline worktree |
| `test_adaptive_retest_agent` (3), `test_llm_generation_monitor` (1 + 5 errors), `test_executor` (1) | 10 | **concurrent session's uncommitted** `CrossChecksConfig` typed-model edits | all pass in a clean `HEAD` worktree (no uncommitted edits); the failures show `CrossChecksConfig(raw_xml='', dialect='generic', generic=…)`, which this change never touches |
| `test_executor::TestMockParity` | 1 | order-dependent flake | passes isolated at both `e39bb96` and `HEAD` |

The 8 pre-existing `tests/cfx/` CrossChecks failures that gated this batch are now fixed
(1020 passed across `phase4`/`customproject`/`cfx`/`dsl`).

### Runtime harness (real archive path, not mocks)

Template entry point → real CFX ZIP: `rankings=1 data=1 conditions=2`,
order `['MinTrades', 'ConfidenceLevel', 'Conditions']`, `Data` typed
`['IST', 'OOSEvery', 'ValidationRatio']`.
DSL → translator entry point: `rankings=1 data=1 conditions=1`, `IST=0.15`,
`OOSEvery=0.25`, and simple `Criterion` settings + advanced `Conditions` coexisting in
the single merged `<Rankings>`.

### Remaining tasks

- [ ] 4.1–4.4 testing (PR 3): golden fixture round-trip, mixed simple+advanced, project builder
- [ ] 5.1 cleanup

### Status

13/17 tasks complete. PR 1a, PR 1b and PR 2 are committed and self-contained. Next: PR 3
(4.1–4.4), which owns the golden `retester-advanced-rankings.cfx` round trip. Note for
PR 3: `CfxReader` does not yet populate `BuildTask.data_range_parts`, so a typed
round-trip assertion will need the reader wired first — deliberately left out of PR 2 to
keep the stacked boundaries clean.

## Work Unit 4 — Golden round-trip + mixed compatibility (PR 3), tasks 4.1–4.4 + 5.1 — COMPLETE

Five commits, each a self-contained reviewable unit. `chained-to-main`, targeting
`ff6336f` (the reader prerequisite).

| Commit | Unit | Authored lines |
|---|---|---|
| `228ec63` | Golden fixture + writer round trip (4.1, 4.2) | 400 (fixture is binary, excluded) |
| `54735cd` | Reader-fidelity half of the golden (4.1, 4.2) | 183 |
| `826659a` | Mixed compatibility + real silent-drop fix (4.3) | 336 |
| `89a38bb` | phase4 emission judged against real SQX (4.4) | 326 |
| `58283c2` | Docstring corrections + gap records (5.1) | 39 |

### TDD Cycle Evidence

| Task | RED | GREEN | REFACTOR |
|---|---|---|---|
| 4.1, 4.2 | Golden written first; it failed until the writer preserved `<Comparator>` / `<Right-Side>` via `raw_xml` and stopped duplicating `<Data>` on save | 19 passed (C1), 22 passed (C1+C2) | Split into two classes so a 400-line review slice and a 183-line slice each stand alone |
| 4.1 reader half | 9 of 12 `<Column-Value>` attributes carry exactly the model default, so a defaulting reader is indistinguishable from a correct one | Perturbed-archive tests pass only if the reader reads the file | Perturb the whole attribute set, not two attributes — a spot check leaves the rest reachable by a hard-coded constant |
| 4.3 | `test_simple_condition_survives_next_to_an_advanced_one` failed with `KeyError: 'Criterion1@metric'` at HEAD | 10 passed; `tests/cfx/` 193 → 202 | One assertion initially demanded fixing the unrelated `SettingsSection` projection defect; narrowed to this change's contract |
| 4.4 | Characterization tests for behaviour shipped in PR 2 — no genuine defect in the emission. Mutation testing is the non-vacuity proof, and it found a real weakness in the first draft (below) | 12 passed | Added `_sqx_all_attribute_names` as an independent name oracle |
| 5.1 | Documentation only | 9 failures before and after, identical set | — |

### The RED that found a real bug (4.3)

`_apply_add_ranking_condition()` was guarded by `if self._task.rankings`, so on any
task that had not pre-seeded that section the instruction was discarded with no error
and no trace. The phase4 retester template seeds only the complex
`rankings_section` lane, so **every** mixed simple + advanced build lost its simple
half. The lane is now created on demand. Behaviour-preserving wherever the lane
already exists, which is every pre-existing caller.

### Mutation verification

All mutants applied in isolated clean-HEAD worktrees, never against the shared index.
Each run asserted the target string occurred exactly once, so a silently-unapplied
mutation can never be miscounted as a survivor.

| Suite | Mutants | Killed | Survivors |
|---|---|---|---|
| Golden (C1) | 6 relevant + 1 equivalent | 6/6 | 0 |
| Reader-fidelity (C2) | 6 (`class_`, `name`, `resultType`, `column`, `format`, `use`) | 6/6 | 0 |
| Mixed compatibility (4.3) | 8 (lazy-lane removal, criterion index, unmerged `<Rankings>`, duplicate `<Data>`, prepended flat settings, …) | 8/8 | 0 |
| phase4 golden (4.4) | 9 | 9/9 | 0 |

**The 4.4 survivor that was not a weak mutant.** The first draft derived the default
`<Condition>` attribute values from the renderer itself, then compared the emission
against them. SQX writes only `use` on `<Condition>`, so renaming an attribute moved
both sides of the comparison and the test passed. The name dimension was
tautological. Fixed by anchoring the name check on the global set of attribute names
SQX writes anywhere in the export — the only independent record of which names it
understands. A survivor there is a real gap, not a weak mutant.

### Work Unit Evidence

| Evidence | Result |
|---|---|
| Focused command (tasks.md PR3 row) | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/test_patcher.py tests/phase4/test_project_builder.py` → **188 passed** |
| Change surface | `tests/cfx/ tests/phase4/ tests/dsl/ tests/customproject/` → **1085 passed, 4 skipped, 0 failed** (baseline 1063 passed, 4 skipped) |
| Runtime harness | Real archive path, no mocks: every golden builds and re-reads an actual `.cfx` zip through `CfxReader`/`CfxWriter`; the 4.4 golden cross-checks the phase4 emission against the real SQX export through the same reader. There is no mock/SQX-daemon boundary in this unit. |
| Rollback boundary | Each commit reverts independently. `228ec63`+`54735cd` are test-only (revert both and no production behaviour changes). `826659a` reverts to a silent drop on mixed builds. `89a38bb` is test-only. `58283c2` is documentation-only. |

### Regression attribution

The concurrent session's CrossChecks work (typed `cross_checks_section` in
`models.py`, and `tests/phase4/test_project_builder.py` +650/-40) was **uncommitted**
throughout PR 3, so a clean HEAD worktree fails 8 `tests/cfx/` + 1 `tests/phase4/`
CrossChecks tests that pass in the main working tree. Every isolation run therefore
compared failure *sets*, never counts, before and after each staged change:

- clean HEAD: `tests/cfx/` 8 failed / 163 passed → HEAD+4.3 8 failed / 173 passed — **identical failure set**
- clean HEAD: `tests/phase4/` 1 failed / 638 passed → HEAD+4.4 1 failed / 650 passed — **identical failure set**
- clean HEAD: `tests/cfx/ tests/phase4/` 9 failed → HEAD+5.1 9 failed — **identical failure set**

With that work present in the working tree: **898 passed, 0 failed**.

### Deviations from design.md

- **Merge order (4.3).** Real Retester *and* Builder SQX exports contain zero flat
  `<Setting>` elements inside `<Rankings>` and zero `Criterion*@` keys. The flat lane
  is a QuantLab extension with no SQX-defined position, so "preserve SQX order" has
  no meaning for it. The merge leaves SQX's verified child order untouched and
  appends the flat lane last. Recorded as a test rather than assumed.
- **4.4 is additive, not a rewrite of `tests/phase4/test_project_builder.py`.** Task
  3.5's hand-written expectations are correct for our own output but cannot answer
  "would SQX understand it?" — every expectation in them is one this project chose, so
  a wrong dialect chosen consistently passes all of them. The new module adds the
  second oracle rather than re-deciding the first. It also avoids the file the
  concurrent session owns.

### Issues found

1. **Flat lane destroys a real `<Setting>`** — pre-existing, affects every section,
   now documented in `_parse_settings_element` with a measured four-cycle trace:
   1 `<Setting>` → 2, then holds at 2. Data loss (the databank pairing is gone), not
   unbounded growth — the weaker and more accurate of the two failure descriptions I
   had been carrying. Separate change; not fixed here.
2. **`DataRangeParts` typed element names have no verified SQX counterpart.** SQX
   writes `<Setups>` / `<OutOfSample>`; the model writes `<IST>` / `<OOSEvery>`. Noted
   in the model, and deliberately excluded from the 4.4 parity assertions.
3. **A comment presented an assumption as evidence** — `_CONDITION_ATTRS` claimed SQX
   "always writes the full attribute set". It writes the full set on `<Column-Value>`
   and only `use` on `<Condition>`. The code was right; the stated reason was wrong.
   Corrected in `patcher.py` and `build_conditions_xml`.

### Task status

- [x] 4.1 golden fixture `retester-advanced-rankings.cfx` + round trip
- [x] 4.2 mixed simple + advanced conditions compatibility
- [x] 4.3 writer merge-order check against native SQX
- [x] 4.4 project builder golden
- [x] 5.1 cleanup (docstrings, scaffolding, corrected claims)

### Status

**20/20 tasks complete.** PR 3 is done. Next: `sdd-verify`.
