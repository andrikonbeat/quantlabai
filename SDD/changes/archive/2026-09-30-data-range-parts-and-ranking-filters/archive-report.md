# Archive Report: data-range-parts-and-ranking-filters

**Change**: `data-range-parts-and-ranking-filters`
**Artifact store**: hybrid (OpenSpec file + Engram)
**Archived**: 2026-09-30
**Archived to**: `openspec/changes/archive/2026-09-30-data-range-parts-and-ranking-filters/`
**Verified HEAD**: `ecabd1a`
**Verdict**: **PASS WITH WARNINGS** — 0 CRITICAL, 0 blockers

This report is the terminal record of the SDD cycle. It describes the state of the
change **at close**. `apply-progress.md` and `verify-report.md` are intermediate
snapshots and are preserved verbatim in this archive as the history they are; where
they disagree with the final state, the disagreement is recorded below rather than
silently resolved.

---

## 1. Intent

QuantLab could emit only *simple* ranking conditions. SQX's real Retester CFX schema
supports advanced nested `<Rankings><Conditions><Condition use="…"><Column-Value …/></Condition></Conditions></Rankings>`
blocks carrying `resultType`, `sampleType`, `direction`, `pctRatio`, `confidenceLevel`,
`market`, `plType`, `subresult`, and `class` attributes. Without typed models QuantLab
could neither express nor write advanced ranking custom filters, and data-range parts
existed only as raw passthrough.

The change closes both gaps so generated CFXs match the verified SQX 144/2953 schema,
as an **additive** change: the simple `AddRankingConditionInstruction` /
`SetRankingsInstruction` path was never touched.

## 2. What Shipped

Five delivery slices, all committed on `main` (`stacked-to-main`, auto-chain):

| Slice | Scope | Commits | Tasks |
|-------|-------|---------|-------|
| PR 1 | Typed models + advanced-ranking patcher (`ColumnValue`, `AdvancedRankingCondition`, `AdvancedRankingsConfig`) | `4be6362` | 1.1, 1.2, 2.1, 2.2 |
| PR 1b | `DataRangeParts` model + `SetDataRangePartsInstruction` | `e39bb96` | 1.3, 1.4, 2.3, 2.4 |
| PR 2 | Integration/wiring: writer merge, `dom.py`, DSL, translator, renderer, phase4 template | `63232a9` `8629da7` `d19e693` `52c0dcf` `815c0c0` `79b7496` `3768a89` | 3.1–3.5 |
| reader wiring | `CfxReader` populates typed advanced rankings + disjoint `<Data>` lanes | `da527ba` `ff6336f` | (prerequisite for 4.1) |
| PR 3 | Golden round-trip, mixed-lane compatibility, phase4 emission judged against real SQX, cleanup | `228ec63` `54735cd` `826659a` `89a38bb` `58283c2` | 4.1–4.4, 5.1 |
| SDD state | Change artifacts, progress, task marks | `7892618` `ecabd1a` | — |

### Production surfaces shipped

| File | Change |
|------|--------|
| `sdk/quantlab/cfx/models.py` | `ColumnValue` (:121), `AdvancedRankingCondition` (:147), `AdvancedRankingsConfig` (:170), `_DATA_RANGE_PART_ELEMENTS` (:184), `DataRangeParts` (:209), three instructions (:1150–:1164) |
| `sdk/quantlab/cfx/patcher.py` | Three instructions + validators/appliers (:779–:814), shared `build_conditions_xml` / `_render_attributes` |
| `sdk/quantlab/cfx/reader.py` | `_parse_advanced_rankings` (:465), `_parse_advanced_condition` (:497), `_column_value_elements` (:517) |
| `sdk/quantlab/cfx/writer.py` | `_append_merged_complex_section` (:532), `_append_data_range_parts` (:535) — one merged `<Rankings>` and one `<Data>` per `<Settings>` |
| `sdk/quantlab/cfx/dom.py` | `add_advanced_ranking_condition` (:251), `set_data_range_parts` (:278), chainable |
| `sdk/quantlab/dsl/models.py` | `ColumnValueFilter` (:124), `AdvancedRankingFilter` (:157), `DataRangePartsDSL` (:189) |
| `sdk/quantlab/translate/translator.py` | `_to_cfx_ranking_condition` (:122) + dispatch |
| `sdk/quantlab/phase4/templates.py` | `_build_retester_rankings_xml` (:173) |
| `sdk/quantlab/customproject/renderers.py` | `render_advanced_rankings` (:141) |

### Real bug found and fixed (task 4.3)

`_apply_add_ranking_condition()` was guarded by `if self._task.rankings`, so on any task
that had not pre-seeded that lane the instruction was discarded **silently — no error, no
trace**. The phase4 retester template seeds only the complex `rankings_section` lane, so
**every** mixed simple + advanced build lost its simple half. Fixed in `826659a` by
creating the lane on demand. Behaviour-preserving wherever the lane already existed.

## 3. Verification Outcome

| Metric | Final value |
|--------|-------------|
| Verdict | **PASS WITH WARNINGS** |
| CRITICAL findings | **0** |
| Blockers | **0** |
| Requirements compliant | **6 / 6** |
| Scenarios compliant | **11 / 11** (5 advanced-ranking + 6 data-range-parts) |
| Tasks in `tasks.md` | **18**, all marked `[x]`, **0 unchecked** |
| Change-owned tests | **150** (126 in 10 dedicated modules + 24 new in `test_patcher.py`) |
| Full suite | **4160 passed, 9 skipped, 0 failed** — exit `0` (5m16s) |
| Change surface (`tests/cfx/ tests/phase4/ tests/dsl/ tests/customproject/`) | **1085 passed, 4 skipped, 0 failed** |
| Build (`compileall`, 5 packages) | exit `0` |

All 9 full-suite skips and all 4 change-surface skips are the same pre-existing set
(`tests/customproject/test_e2e_loadconfig.py`, requiring a real JVM `sqcli`). No change-owned
test carries a `skip`/`xfail` marker; nothing was disabled to make the suite green.

The golden oracle is a **real SQX 144/2953 export** (`tests/cfx/fixtures/retester-advanced-rankings.cfx`,
a real `Build-Task1.xml`, version `141.2219`) parsed by the same reader as QuantLab's own
output — so a self-consistent dialect mistake cannot pass.

**Attribution caveat (S-2)**: the green full-suite result attests the **working tree**, which
included a concurrent session's uncommitted `CrossChecksConfig` edits — not a clean `ecabd1a`
checkout. A result provable from committed history alone would require a re-run in a
`git worktree` at `ecabd1a`.

**Tooling**: `ruff` and `mypy` are absent from the local `.venv` (CI-only per `AGENTS.md`),
so lint/type-check evidence is limited to bytecode compilation. `pytest-cov` absent, so
coverage was not measured.

## 4. Warnings and Suggestions (all non-blocking)

**W-1 — Task count is 18, not 20.** `tasks.md` defines 18 tasks (Phase 1: 4, Phase 2: 4,
Phase 3: 5, Phase 4: 4, Phase 5: 1) and all 18 are checked. The `apply-progress.md` Work
Unit 4 status line asserts "**20/20 tasks complete**". This is a **counting error in the
reporting, not missing work** — verified here directly against `tasks.md`: 18 checkbox
identifiers (`1.1–1.4`, `2.1–2.4`, `3.1–3.5`, `4.1–4.4`, `5.1`), 18 `[x]`, 0 `[ ]`.
`tasks.md` was **not** edited; it is already correct.

**W-2 — `apply-progress.md` transposes its own 4.2/4.3 labels.** `tasks.md` has
4.2 = create fixture, 4.3 = mixed simple+advanced, 4.4 = project-builder golden.
`apply-progress.md` WU4 reads 4.2 = mixed, 4.3 = writer merge-order check. The work is
complete under either numbering; only the labels disagree. Documentation consistency only.

**W-3 — Two commits exceeded the 400-line review budget.**

| Commit | Changed lines | Budget |
|--------|---------------|--------|
| `4be6362` (PR 1) | 795 + 4 = **799** | over by 399 (never acknowledged in apply-progress) |
| `e39bb96` (PR 1b) | 454 + 1 = **455** | over by 55 (acknowledged, partially mitigated) |
| `228ec63` (PR 3) | 400 | at budget |
| all others | ≤ 370 | within budget |

Reviewer-load concern, not a correctness defect.

**S-4 — The advanced-ranking *re-render* path drops unknown `<Conditions>` parent
attributes** (the most substantive carry-forward item). `build_conditions_xml(conditions, indent="  ")`
hardcodes `f"{indent}<Conditions>"` with no attribute parameter. Consequence, proven at
runtime:
- read → write → read **preserves** a parent's `CrossCheck`/`thresholdPct` via the verbatim
  `raw_xml` lane — this is the path the spec scenario exercises, and it is correct;
- but *applying* an `AddAdvancedRankingConditionInstruction` / `SetAdvancedRankingsInstruction`
  re-renders via `build_advanced_rankings_xml`, which **drops** those parent attributes.

No scenario asserts this and the real SQX 144/2953 `<Rankings>` export carries no
`CrossCheck` attribute, so nothing is broken today. Needs either a characterization test
or an explicit documented decision that re-rendering normalises the parent.

**S-1 — `DataRangeParts` typed element names have no verified SQX counterpart.** The model
writes `<IST>` / `<OOSEvery>`; real SQX writes `<Setups>` / `<OutOfSample>`. Correctly
disclosed in the model docstring and deliberately excluded from the 4.4 parity assertions,
so nothing is wrong today — but emitting `<IST>` into a config SQX must consume is a latent
interop risk.

**S-3 — `sdk/quantlab/cfx/patcher.py` grew ~376 lines and is now the densest module in the
ranking lane.** The extracted `build_conditions_xml` / `_render_attributes` helpers already
prevent a second dialect copy. Flagged so a duplicate renderer does not appear there.

## 5. Recorded Contradictions (not silently resolved)

**Commit count.** Three sources disagree, and they cannot be ranked against each other —
the launch brief and `verify-report.md` W-3 each state "14 commits", yet the launch brief's
own hash list enumerates **18**. Measured directly from git (`git show --shortstat`):

| Set | Commits | Insertions | Deletions |
|-----|---------|-----------|-----------|
| All commits listed in the launch brief | **18** | **5618** | **91** |
| Implementation only (excluding SDD/doc commits `7892618`, `58283c2`, `ecabd1a`) | **15** | **4697** | **84** |
| `verify-report.md` W-3 claim | 14 | 4704 | 56 |
| Launch brief claim | 14 | 4704 | 56 |

The repository measurement is authoritative for the commit **count** (18 hashes, all
present on `main`); the W-3/launch line totals do not reconcile with any commit set.
Neither figure is a correctness issue — no code is missing. Recorded here so a future
reader does not treat "14 commits / 4704 lines" as a verified figure.

## 6. Delta Spec Sync

Both domain main specs were **created** (neither existed before), so each delta was a
full spec rather than a merge. Mechanical shell copy with `diff -r` readback:

| Domain | Action | sha256 (source == destination) | `diff -r` |
|--------|--------|-------------------------------|-----------|
| `advanced-ranking-filters` | Created `openspec/specs/advanced-ranking-filters/spec.md` (3 requirements, 5 scenarios) | `76bcaae30787f807336ea5050c8498c38a6c2be5abc16b8190cf118e1efd0dd1` | empty |
| `data-range-parts` | Created `openspec/specs/data-range-parts/spec.md` (3 requirements, 6 scenarios) | `068a52ae6c0a2536c34476b2ec4686bc8a4fb72fdca7c0f39315123b5421d696` | empty |

These are now the source of truth for the advanced ranking filter and data range parts
behaviours.

## 7. Deviations from design.md (all recorded, none spec-breaking)

1. **XML attribute aliases added** to `ColumnValue`/`AdvancedRankingCondition` plus
   `populate_by_name=True`. design.md's interface block declared fields without aliases;
   without them `model_dump(by_alias=True)` would emit Python names and lose real SQX
   attribute names, breaking the spec's CFX-fidelity criterion.
2. **Task 4.4 is additive, not a rewrite of `tests/phase4/test_project_builder.py`.** Task
   3.5's hand-written expectations are correct for our own output but cannot answer "would
   SQX understand it?" — every expectation in them is one this project chose, so a wrong
   dialect chosen consistently passes all of them. The new module
   `tests/phase4/test_project_builder_golden_rankings.py` adds the second oracle. It also
   avoided a file the concurrent session owned.
3. **`DataRangeParts` typed element names** are a QuantLab convention, not verified SQX
   output (see S-1).
4. **`validation_ratio` and `test_ratio` remain distinct fields** and are never folded into
   a training ratio, per explicit constraint, even though that means the two-part split and
   the IS split express overlapping information.
5. **One deliberate hardening beyond the literal spec**: the translator rejects an advanced
   filter with no `column_values`, because SQX would accept such a `<Condition>` and
   silently rank on nothing.
6. **`cfx/reader.py` was added** to the change surface (not in design.md's file table),
   required by task 4.1 to make a typed round-trip assertion possible.

## 8. Follow-Ups (each needs its own SDD change)

1. **Flat-lane `<Setting>` projection defect** — PRE-EXISTING, **not** part of this change
   and not regressed by it. `_parse_settings_element` splits one `<Setting>` into two, keyed
   `Setting@key`, causing data loss on re-emit (the databank pairing is gone). Measured
   four-cycle trace: `1 <Setting> → 2`, then holds at `2`. Data loss, not unbounded growth.
   Affects **every** section, not just rankings. Correctly scoped out of
   `test_data_range_parts_survive_the_reader_writer_cycle` with a docstring naming it as
   pre-existing. Deferred to its own change.
2. **S-4** — `<Conditions>` parent-attribute preservation on the re-render path.
3. **S-1** — reconcile `DataRangeParts` element names against a real SQX export carrying
   IS/OOS sub-ranges; that evidence is what would justify replacing the convention.

## 9. Concurrency Note

A parallel session worked the `CfxReader` wiring (`da527ba`/`ff6336f`) and still holds
uncommitted `CrossChecksConfig` edits in the working tree. Those are **not** part of this
change. All four work units used hunk-level staging (`git hash-object -w` +
`git update-index --cacheinfo`) or clean-`HEAD` `git worktree` isolation specifically to keep
the concurrent session's hunks out of these commits, and compared failure **sets** rather
than counts when a dirty tree was unavoidable.

Recorded process lesson from PR 1b: using `git stash --keep-index` to isolate a commit
removed a concurrent session's uncommitted work. It was recovered in full from the dangling
stash commit `aeb7b1c27d4a60683e85da9ee734c05abbfc6373` with all 9 affected files verified
byte-identical — **no data lost**, but isolation must use `git worktree` or `git archive`
into a temp dir, never `stash`, when another session writes to the same tree.

## 10. Traceability

**Engram observations read** (hybrid store):

| Artifact | Observation ID |
|----------|----------------|
| `sdd/…/proposal` | #1074 |
| `sdd/…/exploration` | #1068 |
| `sdd/…/spec` | #1076 |
| `sdd/…/design` | #1077 |
| `sdd/…/tasks` | #1079 |
| `sdd/…/verify-report` | #1097 |
| `sdd/…/archive-report` | (this report) |

**Archived contents**: `proposal.md`, `exploration.md`, `design.md`, `specs/` (2 domains),
`tasks.md` (18/18 checked), `apply-progress.md`, `verify-report.md`, `archive-report.md`.

**Rollback boundary**: every commit reverts independently. `228ec63`+`54735cd` are
test-only; `89a38bb` is test-only; `58283c2` is documentation-only. Reverting `826659a`
restores the silent mixed-lane drop. Reverting `da527ba`/`ff6336f` removes reader typing.

**SDD cycle complete**: planned, implemented, verified, and archived.