# Archive Report: fix-flat-lane-settings-projection

**Change**: `fix-flat-lane-settings-projection`
**Mode**: hybrid (OpenSpec + Engram)
**Archived**: 2026-10-02
**Verified HEAD**: `5cebb17`
**Archive status**: **intentional-with-warnings** — see [Missing verification artifact](#1-missing-verification-artifact-process-gap)

---

## Intent

`SettingsSection.settings: dict[str, str]` was a **write-only projection**. QuantLab wrote
`Tag@attr` keys; reading them back produced keys no producer or consumer recognised, so
reader→writer→reader cycles silently destroyed data. The worst case was
`adaptive_retest_agent.apply_adaptive_mutations`, which rewrites the *same* `.cfx` in place
on every retest cycle — every cycle compounding the loss of market symbol, timeframe, and
date range in the file under test.

Treated as a correctness incident, not deferred cleanup. The fix makes the flat lane a
**bijection** by rewriting both halves of the codec around one grammar.

## What Shipped

| Commit | Subject | Changed lines | Content |
|--------|---------|---------------|---------|
| `374a2cf` | `fix(cfx): invert the flat lane codec so SettingsSection round-trips` | 10 files, +199/−135 | Reader flattens a section's **children** with `prefix=""`; one shared predicate `_is_flat_lane_child` decides lane membership for **both** the admit path (`_parse_settings_element`) and the strip path (`_parse_data_range_parts`); a leaf `<Setting key= value=/>` becomes **one** entry `settings[K] = V`; writer de-flattens, splitting `Tag@attr` once on `@` and **grouping by tag** into one element per tag in first-appearance order. `setting_children_only` removed, replaced by `exclude_tags`. |
| `1b035c5` | `test(cfx): pin the flat lane's round-trip contract` | 1 file, +400 | New `tests/cfx/test_flat_lane_round_trip.py` — 14 tests, one per spec scenario. Zero production code. Landed at exactly the 400-line budget. |
| `fa81b31` | `test(cfx): make the adaptive-retest canary detect the flat-lane collapse` | 1 file, +23/−9 | `test_preserves_unrelated_cfx_content` carries a 4-key `<Data>` and asserts exact dict equality per section, plus exclusion of the mangled literals. Zero production code. |
| `6a4a4c9` | `chore(sdd): declare the strict-TDD gate the runner already enforces` | 1 file, +7/−5 | `openspec/config.yaml` TDD drift reconciled (unplanned task 4.3). |
| `5cebb17` | `docs(openspec): track fix-flat-lane-settings-projection change artifacts` | 5 files, +993 | The planning artifacts, finally landed after three deferrals. |

No producer changed. `patcher`, `translator`, `templates` and `risk_mapper` already emit
`Tag@attr` or bare keys — exactly the grammar the writer now renders.

## Task Completion

**22 of 22 implementation tasks complete.** Counted directly from the persisted
`tasks.md` checkbox state, not from `apply-progress` prose: Phase 0 (1) + Phase 1 (10) +
Phase 2 (6) + Phase 3 (2) + Phase 4 (3) = 22 `[x]`, **0 `- [ ]`**. No archive-time
reconciliation was performed.

## 1. Missing verification artifact (process gap)

> **The `sdd-verify` artifact does not exist.** There is no `verify-report.md` in this
> change folder and no `sdd/fix-flat-lane-settings-projection/verify-report` observation in
> Engram. `apply-progress.md:479-480` closes with "**Ready for `sdd-verify`**", so the
> phase had not run when apply finished.

The archive launch prompt asserted "`verify-report.md` exists; 7/7 requirements and 14/14
scenarios COMPLIANT with passing test evidence". **That claim is false** and is recorded
here rather than resolved silently: the launch prompt (rank 3 in the Final-State Authority
hierarchy) is contradicted by repository evidence, and no higher-ranked source corroborates
it.

Because the substantive claim was checkable, archive **re-attested it independently** rather
than blocking on a missing file or trusting the prompt. Run at archive time, HEAD `5cebb17`:

| Check | Command | Result |
|-------|---------|--------|
| Change-owned surface | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/agents/ tests/cfx/ tests/phase4/ sdk/tests/` | **2666 passed**, 0 failed (200.58s) |
| Full suite | `SQX_FORCE_MOCK=1 python3 -m pytest -q` | **4134 passed, 9 skipped, 0 failed** (313.12s) |
| Codec contract | `… pytest -q tests/cfx/test_flat_lane_round_trip.py` | **14 passed** |
| Dialect consumers + canary + guards | `… pytest -q tests/agents/test_adaptive_retest_agent.py tests/cfx/test_reader_advanced_rankings.py tests/cfx/test_writer_section_merge.py tests/phase4/test_templates.py tests/phase4/test_translator_advanced_rankings.py sdk/tests/test_translator.py` | **112 passed** |
| Spec shape | 7 `### Requirement:` blocks, 14 `#### Scenario:` blocks | matches 7 REQ-FLAT requirements / 14 scenarios |

So the *behavioural* verdict is **PASS**: every requirement's scenarios have passing tests
and nothing regresses. What is missing is the **audit record** — no signed verdict, no
requirement-by-requirement compliance table, no recorded `verify-result/v1` envelope. This
archive is therefore `intentional-with-warnings`, not `success`.

**Follow-up F0 (highest priority): re-run `sdd-verify` for this change to materialize
`verify-report.md` in the archive folder.** The code does not need re-verification; the
artifact does.

## 2. Test-count contradiction, resolved

The launch prompt stated "change surface 2666/2666 passed; **full suite** 2666/2666
passed". Those two figures are the same number applied to two different scopes. Measured
and corroborated three ways:

- `tasks.md` 4.2 (persisted task artifact, rank 2): "**PR 3 = 4134/9, 0 failed, exit 0**"
- `apply-progress.md:397,405,416`: "**4134 passed, 9 skipped, 0 failed**", change-owned "**2666 passed**"
- My own runs above: change-owned **2666**, full suite **4134 passed / 9 skipped**

**2666 is the change-owned surface. The full suite is 4134 passed / 9 skipped / 0 failed.**
The tasks artifact outranks the launch prompt, and 4134 > 2666 makes 2666-as-full-suite
arithmetically impossible. Zero failures on either scope; nothing to attribute.

## 3. Stale Engram tasks observation

`#1123` (`sdd/fix-flat-lane-settings-projection/tasks`) is the **pre-apply** snapshot: 21
tasks, all `- [ ]`, no task 4.3. The post-apply completion state exists **only in the
file** `tasks.md` (22/22 `[x]`). A future reader who finds #1123 by topic search will see
zero completed work. Read the file, not the observation.

## Specification Sync

| Domain | Action | Detail |
|--------|--------|--------|
| `cfx-serialization` | **Created** | No main spec existed. The parent domain is `cfx-editor`; per the precedent set by the archived sibling `data-range-parts-and-ranking-filters`, the delta is treated as a **full spec** and copied verbatim. |

`openspec/specs/cfx-serialization/spec.md` — mechanical shell copy, sha256-identical to the
change's delta, `diff -r` empty:

```
fae5648d38d0602e64485e4cdd3f6b14b00a92ef8a80cc9fd2245b960836cb9b  openspec/changes/fix-flat-lane-settings-projection/specs/cfx-serialization/spec.md
fae5648d38d0602e64485e4cdd3f6b14b00a92ef8a80cc9fd2245b960836cb9b  openspec/specs/cfx-serialization/spec.md
```

### Known capability overlap — `cfx-serialization` vs `cfx-editor`

Recorded again here because it survives into the source of truth: `cfx-serialization` now
exists as a peer of `cfx-editor`, and the two describe adjacent concerns in the same
`sdk/quantlab/cfx/` package. The overlap was flagged during the spec phase and is
**unresolved by design** — this change did not attempt a merge, because splitting or
merging capability boundaries is not this change's mandate. See follow-up F4.

## Deviations from `design.md`

All recorded during apply; carried here so the archived trail matches what shipped.

1. **`test_flat_lane_round_trip.py` landed at 400 lines, not the ~200 forecast.** The
   forecast sized the unit by production code, which is zero here. A test file cannot be
   gamed smaller without dropping spec scenarios. It fits one commit at the 400 budget, so
   no `size:exception` was needed.
2. **Task 4.1 shipped as a verified no-op.** The docstring sweep found nothing stale — PR 1
   had already corrected every one. The two surviving `Setting@key` mentions
   (`reader.py:444`, `writer.py:568`) describe **legacy input**, not a produced form, and are
   accurate. `setting_children_only` has zero occurrences in production code. Reported as a
   finding rather than padded with edits to already-correct text.
3. **Two unplanned tasks were forced by reality, not by preference:**
   - **1.10** — `sdk/tests/test_translator.py:89-98,173-175` pinned the *old* emitted dialect
     (`Setting[@key='Symbol@symbol']`). The dialect change invalidated them; migrated to
     `<Symbol>`/`<Timeframe1>` with coverage preserved.
   - **2.6** — an empty-tag key edge (`"@value"` partitions to an empty tag) would emit
     malformed XML; pinned by `test_a_key_with_an_empty_tag_part_is_treated_as_a_bare_key`.
   - **4.3** — `openspec/config.yaml` declared `strict_tdd: false` / `rules.apply.tdd: false`
     while AGENTS.md mandates Strict TDD. Corrected as one coherent unit: flipping the two
     flags alone would have left `testing.runner: none` and an empty
     `rules.apply.test_command` re-establishing the same contradiction elsewhere.
4. **`tasks.md` Phase 1 was wrong about its own history.** The per-line migration lists were
   guesses written before the full-suite run revealed the real invalidated set — task 1.8
   named 3 ranges where 10 hunks were migrated. Every site *was* migrated, so nothing was
   left red, but the artifact could not be trusted to review PR 1. Corrected ranges were
   taken from `git show 374a2cf --unified=0`, not from memory. (Engram `#1126`.)
5. **3 of the 14 codec tests cannot fail pre-inversion.** They are stability guards
   (byte-identity across 4 cycles). Stated rather than hidden: a reviewer reconciling "11/14
   RED" against "14/14 GREEN" should know that 3 are guards, and that stability alone is not
   evidence of a correct codec.

## Rollback Boundary

Each commit reverts independently. No commit contains data migration, a feature flag, a
schema change, or a CLI surface, so no revert can remove unrelated work.

| Commit | Revert removes | Leaves intact |
|--------|----------------|---------------|
| `374a2cf` | Codec inversion (reader + writer + models + 6 migrated test files) | Producer keys; the codec returns to its known-defective read behaviour. **Reader and writer must revert together** — design decision #1: either half alone ships an inversion. |
| `1b035c5` | The 14-test contract file | Zero production code; reverting loses coverage only. |
| `fa81b31` | One test method's body | Zero production code; reverting restores the weak substring canary. |
| `6a4a4c9` | The config TDD declaration | Zero production code. |
| `5cebb17` | This change's SDD artifacts | All behaviour commits. |

Recommended rollback order is reverse-chronological (`5cebb17` → `6a4a4c9` → `fa81b31` →
`1b035c5` → `374a2cf`); `374a2cf` is the only one that changes runtime behaviour.

## Follow-Ups (each needs its own SDD change)

| # | Item | Note |
|---|------|------|
| **F0** | **Re-run `sdd-verify`** to produce the missing `verify-report.md` for this change | Process gap, section 1. No re-verification of code needed; the audit record is what's absent. |
| **F1** | `rules.verify.*` fields in `openspec/config.yaml` remain unset (`test_command: ""`, `build_command: ""`, `coverage_threshold: 0`) | Left alone during 6a4a4c9 deliberately: populating them would assert CI capability this change did not verify. |
| **F2** | `_SETTINGS_SECTIONS` omits `Rankings` and `CrossChecks`, so the reader never populates those flat lanes | Pre-existing asymmetry, untouched. Recorded as `design.md` Open Question #2. |
| **F3** | The emitted-XML dialect is a **breaking change** for external consumers that looked up `Setting[@key='Tag@attr']` | Design decision: legacy files are **not** repaired losslessly (there the pair exists only as attribute values) but **converge to one stable form after a single cycle**. Stale older `.cfx` files are re-written by QuantLab into the new form; they are not migrated back. |
| **F4** | Decide whether `cfx-serialization` merges into `cfx-editor` or stays a peer | Known capability overlap; unresolved by design. |

## Engram Observations

| ID | Title | Role here |
|----|-------|-----------|
| `#1118` | `sdd/fix-flat-lane-settings-projection/explore` | Problem framing (write-only projection) |
| `#1120` | `sdd/fix-flat-lane-settings-projection/proposal` | Intent, scope, capability contract, rollback plan |
| `#1121` | `sdd/fix-flat-lane-settings-projection/spec` | The 7 REQ-FLAT requirements / 14 scenarios synced to `openspec/specs/cfx-serialization/spec.md` |
| `#1122` | `sdd/fix-flat-lane-settings-projection/design` | Architecture decisions #1–5, one-predicate rule |
| `#1123` | `sdd/fix-flat-lane-settings-projection/tasks` | **Stale (pre-apply)** — see section 3 |
| `#1125` | `sdd/fix-flat-lane-settings-projection/apply-progress` | PR 3 record; 22/22, 4134/9/0, the `8515e77` RED proof |
| `#1126` | `Corrected tasks.md under-enumeration for flat-lane PR 1` | Deviation 4 |

**Absent**: `sdd/fix-flat-lane-settings-projection/verify-report` — see section 1.

## Archive Contents

| Artifact | Present |
|----------|---------|
| `proposal.md` | yes (91 lines) |
| `design.md` | yes (162 lines) |
| `tasks.md` | yes (105 lines, 22/22 `[x]`) |
| `specs/cfx-serialization/spec.md` | yes (155 lines) |
| `apply-progress.md` | yes (480 lines) |
| `verify-report.md` | **no — see section 1** |
| `archive-report.md` | this file |

`tasks.md` and `apply-progress.md` are archived **verbatim** as history, including
`tasks.md`'s original per-line migration lists that deviation 4 corrected in `apply-progress.md`.

## Proposal Success Criteria

`proposal.md:82-87` carries six unchecked `- [ ]` success criteria. Those boxes are
proposal-phase artifacts and are archived as written — archive does not rewrite upstream
phase artifacts. For the record, all six are satisfied by the evidence in this report:

1. Multi-key `<Data>` round-trips without collapse → REQ-FLAT-3, `test_five_key_data_survives_a_full_round_trip`
2. Non-`Data` sections round-trip without section prefix → REQ-FLAT-1, `test_no_section_tag_pollutes_a_non_data_flat_section`
3. `adaptive_retest_agent` round-trips databanks/symbols losslessly → REQ-FLAT-7, `test_preserves_unrelated_cfx_content`
4. Regression guards stay green → `test_flat_lane_holds_only_setting_children`, `test_nested_elements_do_not_leak_into_the_flat_lane`
5. `tests/cfx/` baseline (208) stays green → 2666 change-owned / 4134 full, 0 failed
6. Targeted codec tests pass with updated expectations → 14 codec + 112 consumer/guard tests

## SDD Cycle

Implementation and behavioural verification are complete and independently re-attested.
The `sdd-verify` **artifact** is missing and is follow-up F0. Cycle is closed with warnings.