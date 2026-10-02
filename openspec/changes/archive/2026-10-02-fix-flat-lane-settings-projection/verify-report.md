```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:fae5648d38d0602e64485e4cdd3f6b14b00a92ef8a80cc9fd2245b960836cb9b
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 7/7
scenarios: 14/14
test_command: SQX_FORCE_MOCK=1 python3 -m pytest -q
test_exit_code: 0
test_output_hash: sha256:38d6100dddd65e1fd768d79904261be81fc80b659b614942ac5a6565ca24b306
build_command: python3 -c "import compileall,sys; sys.exit(0 if compileall.compile_dir('sdk/quantlab/cfx', quiet=2) else 1)"
build_exit_code: 0
build_output_hash: sha256:5dc0316896d58ad9d32af796142f85fa948ffb8926100044c4a158bf88d9892f
```

# Verification Report: fix-flat-lane-settings-projection

**Change**: `fix-flat-lane-settings-projection`
**Verified HEAD**: `5cebb17`
**Mode**: Strict TDD (test runner `SQX_FORCE_MOCK=1 python3 -m pytest -q`)
**Artifact location**: `openspec/changes/archive/2026-10-02-fix-flat-lane-settings-projection/verify-report.md`
**Version**: `specs/cfx-serialization/spec.md`, sha256 `fae5648d38d0602e64485e4cdd3f6b14b00a92ef8a80cc9fd2245b960836cb9b`

> This report **closes follow-up F0** of the archived `archive-report.md`. The
> earlier `sdd-verify` run asserted it had produced this artifact; it had not. The
> change was archived without one. This run re-derives every claim from
> repository evidence rather than from any prior report, and materializes the
> missing audit record.

## Completeness

| Metric | Value | Source |
|--------|-------|--------|
| Tasks total | 22 | counted from `tasks.md` checkboxes |
| Tasks complete | 22 | `grep -c '^- \[x\]' tasks.md` → **22** |
| Tasks incomplete | 0 | `grep -c '^- \[ \]' tasks.md` → **0** |
| Requirements | 7 | `grep -c '^### Requirement:' spec.md` → **7** |
| Scenarios | 14 | `grep -c '^#### Scenario:' spec.md` → **14** |
| Plan artifacts | 4/4 | proposal, design, tasks, specs — all present and read |

Task breakdown from the checkbox source: Phase 0 (1) + Phase 1 (10) + Phase 2 (6)
+ Phase 3 (2) + Phase 4 (3) = **22 `[x]`, 0 `- [ ]`**. No unchecked task, so no
`blocked` gate applies and full verification was run.

## Build & Tests Execution

**Build**: ✅ Passed — exit **0**

```text
$ python3 -c "import compileall,sys; sys.exit(0 if compileall.compile_dir('sdk/quantlab/cfx', quiet=2) else 1)"
cfx compileall: OK
```

**Tests**: ✅ **4134 passed / 0 failed / 9 skipped** — exit **0**

```text
$ SQX_FORCE_MOCK=1 python3 -m pytest -q
4134 passed, 9 skipped, 36 warnings in 313.60s (0:05:13)
```

**Change-owned surface**: ✅ **2666 passed / 0 failed** — exit **0**

```text
$ SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/ tests/phase4/ tests/agents/ sdk/tests/
2666 passed, 22 warnings in 199.25s (0:03:19)
```

**Codec contract**: ✅ **14 passed**

```text
$ SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/test_flat_lane_round_trip.py
14 passed in 0.39s
```

**Dialect consumers + canary + regression guards**: ✅ **112 passed**

```text
$ SQX_FORCE_MOCK=1 python3 -m pytest -q tests/agents/test_adaptive_retest_agent.py \
    tests/cfx/test_reader_advanced_rankings.py tests/cfx/test_writer_section_merge.py \
    tests/phase4/test_templates.py tests/phase4/test_translator_advanced_rankings.py \
    sdk/tests/test_translator.py
112 passed, 1 warning in 1.42s
```

**Coverage**: ➖ **Not available** — `coverage` is not installed in the local
`.venv` (`AGENTS.md`: linters and type checkers run in CI only). Informational
only; not a failure.

## Requirements Compliance Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| REQ-FLAT-1 — Flat Lane Key Grammar | ✅ COMPLIANT | `reader.py:452-460` flattens `el`'s **children** with `prefix=""`; `writer.py:579-589` inverts via `key.partition("@")`. 2/2 scenarios green. |
| REQ-FLAT-2 — Setting Pair Coalescing | ✅ COMPLIANT | `writer.py:587` groups `Setting@key`/`Setting@value` into one `<Setting>`; `reader.py:456-458` makes a leaf `<Setting>` **one** dict entry. 2/2 scenarios green. |
| REQ-FLAT-3 — Lossless Flat Round-Trip | ✅ COMPLIANT | 5-key `<Data>` survives read→write→read with all keys intact; no `Tag@attr` key is emitted as `<Setting>`. 2/2 scenarios green. |
| REQ-FLAT-4 — Data Typed-Lane Guard Preserved | ✅ COMPLIANT | `_is_flat_lane_child` (`reader.py:411-429`) is the single predicate, called by `_parse_settings_element` (admit, line 454) **and** `_parse_data_range_parts` (strip). 4/4 scenarios green, including the source-level duplication guard. |
| REQ-FLAT-5 — Databank Pairing | ✅ COMPLIANT | `build_retester_cfx(databanks=['EURUSD_H1','GBPUSD_H1'])` keeps both across one cycle. 1/1 scenario green. |
| REQ-FLAT-6 — Emitted Dialect for Bare Flat Keys | ✅ COMPLIANT | `writer.py:584-585` — a key with no separator or empty tag part emits `<Setting key= value=/>`; `Tag@attr` keys group by tag. Bare keys keep the `Setting` form, so `test_templates.py:281-282` stays untouched and green. 2/2 scenarios green. |
| REQ-FLAT-7 — Adaptive-Retest In-Place Safety | ✅ COMPLIANT | `test_preserves_unrelated_cfx_content` asserts exact dict equality over a 4-key `<Data>` plus negative exclusion of the mangled literals. 1/1 scenario green. |

**Compliance summary**: **7/7 requirements, 14/14 scenarios compliant, 0 untested, 0 failing.**

## Scenario Compliance (14/14)

| # | Requirement | Scenario | Covering test(s) | Result |
|---|-------------|----------|------------------|--------|
| 1 | REQ-FLAT-1 | No section-prefix pollution | `test_flat_lane_round_trip.py::test_no_section_tag_pollutes_a_non_data_flat_section` | ✅ COMPLIANT |
| 2 | REQ-FLAT-1 | Producer keys findable after a read | `…::test_a_producer_timeframe_key_is_findable_after_a_read` (runs the real `CfxPatcher` + `AddTimeframeInstruction`) | ✅ COMPLIANT |
| 3 | REQ-FLAT-2 | Pair coalesces into a single element | `…::test_legacy_pair_coalesces_into_one_setting_element` | ✅ COMPLIANT |
| 4 | REQ-FLAT-2 | Coalesced output byte-stable over four cycles | `…::test_a_real_setting_element_is_byte_stable_over_four_cycles` | ✅ COMPLIANT |
| 5 | REQ-FLAT-3 | Five-key `Data` survives one cycle | `…::test_five_key_data_survives_a_full_round_trip` | ✅ COMPLIANT |
| 6 | REQ-FLAT-3 | `Data` survives an in-place rewrite | `…::test_five_key_data_survives_an_in_place_rewrite` | ✅ COMPLIANT |
| 7 | REQ-FLAT-4 | Typed sub-ranges stay out of the flat lane | `test_reader_advanced_rankings.py::test_flat_lane_holds_only_setting_children` + `…::test_the_shared_predicate_decides_both_halves_of_the_test` | ✅ COMPLIANT |
| 8 | REQ-FLAT-4 | Nested `Setups` subtree stays in passthrough | `test_reader_advanced_rankings.py::test_nested_elements_do_not_leak_into_the_flat_lane` (**untouched guard**) | ✅ COMPLIANT |
| 9 | REQ-FLAT-4 | Second cycle does not grow the `Data` section | `test_reader_advanced_rankings.py::test_second_cycle_does_not_grow_the_data_section` + `…::test_the_data_signature_is_idempotent_across_four_cycles` | ✅ COMPLIANT |
| 10 | REQ-FLAT-4 | One shared predicate serves both `<Data>` lanes | `…::test_both_reader_lanes_call_it_and_neither_reimplements_it` (`inspect.getsource` guard) | ✅ COMPLIANT |
| 11 | REQ-FLAT-5 | Two databanks survive one cycle | `…::test_two_databanks_survive_a_read_write_cycle` | ✅ COMPLIANT |
| 12 | REQ-FLAT-6 | Bare keys keep `Setting`; `Tag@attr` keys do not | `…::test_a_tagged_key_is_never_emitted_as_a_setting_element` | ✅ COMPLIANT |
| 13 | REQ-FLAT-6 | `Setting` elements addressable by key | `…::test_bare_keys_emit_setting_elements_that_stay_addressable` | ✅ COMPLIANT |
| 14 | REQ-FLAT-7 | Exact key/value assertion after in-place rewrite | `test_adaptive_retest_agent.py::test_preserves_unrelated_cfx_content` | ✅ COMPLIANT |

12 of the 14 scenarios are covered by `test_flat_lane_round_trip.py`; scenarios 7–9 are
covered by the four tests in `test_reader_advanced_rankings.py` that the spec names
as the REQ-FLAT-4 modification targets. Two codec tests exceed the spec and are
credited as bonus coverage, not as scenario evidence:
`test_the_reader_never_produces_setting_key_or_value_keys` (reinforces REQ-FLAT-2) and
`test_a_key_with_an_empty_tag_part_is_treated_as_a_bare_key` (unplanned task 2.6).

### Shared-Predicate Guard — independently confirmed

The REQ-FLAT-4 scenario-4 guard is not merely asserted by the plan; it was
re-derived from source and then executed.

- `reader.py:411-429` — `_is_flat_lane_child` is the single predicate, returning
  `len(child) == 0 and child.tag not in exclude`. Its docstring states the
  admit/strip duality explicitly.
- `reader.py:454` — `_parse_settings_element` calls it to **admit**.
- `_parse_data_range_parts` calls it to **strip** (confirmed by the call graph).
- Neither body re-implements the leaf/exclude test inline.
- `test_both_reader_lanes_call_it_and_neither_reimplements_it` passes, and is
  triangulated by the behavioural `test_the_shared_predicate_decides_both_halves_of_the_test`
  so the source guard is not the only proof.
- `_DATA_OWNED_TAGS = DATA_RANGE_PART_TAGS | _DATA_PASSTHROUGH_TAGS` (`reader.py:87`),
  with `DATA_RANGE_PART_TAGS` derived from `_DATA_RANGE_PART_ELEMENTS`
  (`models.py:225-227`), so the flat-lane exclusion and the writer's typed lane
  cannot drift.
- `setting_children_only` has **zero** occurrences in production code — it was
  removed, not kept, as design decision requires.

## Task Verification (22 tasks)

Counted from the persisted `tasks.md`, not from `apply-progress` prose.

| Phase | Tasks | Verified against |
|-------|-------|------------------|
| 0 — Pre-apply gate | 1/1 | REQ-FLAT-6 scenario amendment landed before apply; `spec.md:113-118` asserts the corrected tags `["Criterion1"]` / `["Symbol","Timeframe1"]`, so tasks were not implemented literally. |
| 1 — Core codec | 10/10 | `374a2cf`. Reader flattens children with `prefix=""`; writer groups by tag; `setting_children_only` removed; 6 migrated test files green. Task 1.8's corrected hunk list was taken from `git show 374a2cf --unified=0`. |
| 2 — Codec coverage | 6/6 | `1b035c5`. `test_flat_lane_round_trip.py` exists with **14 tests**, zero production code. Each task's named tests are present by name (see Scenario Compliance). |
| 3 — Canary | 2/2 | `fa81b31`. `test_preserves_unrelated_cfx_content` carries the 4-key `<Data>` and asserts exact equality, replacing the substring `any("EURUSD" in v …)` that could not detect mangling. |
| 4 — Cleanup | 3/3 | 4.1 verified as a **no-op** (zero stale `Setting@key` docstrings remain; the two survivors describe legacy *input*); 4.2 full suite exit 0; 4.3 config TDD drift reconciled in `6a4a4c9`. |

Commit chain confirmed present at HEAD `5cebb17`:
`374a2cf` → `1b035c5` → `fa81b31` → `6a4a4c9` → `5cebb17`.

## Full-Suite Attribution

| Bucket | Count | Basis |
|--------|-------|-------|
| Change-owned surface (`tests/cfx/` `tests/phase4/` `tests/agents/` `sdk/tests/`) | **2666 passed, 0 failed** | executed this run, exit 0 |
| Outside the change-owned surface (gates, robustness, CLI, orchestration, …) | **1468 passed** | 4134 − 2666, arithmetic from the two executed runs |
| Net new tests added by this change | **+14** | `1b035c5` created 14 tests; `fa81b31` modified one method's body and added no test count |
| Pre-existing failures | **0** | no failure on either scope; nothing to attribute |
| Skipped | **9** | unchanged across apply (`4120/9` → `4134/9` → `4134/9`) |

**Concurrent working-tree edits cannot affect these results.** The uncommitted work
in `.atl/skill-registry.md` and `openspec/changes/research-agent-enhancements/*` is
Markdown only; no executable source, fixture, or `pytest.ini` is modified, so the
2666 and 4134 figures are attributable to HEAD `5cebb17` alone.

## TDD Compliance (Strict TDD)

| Check | Result | Details |
|-------|--------|---------|
| TDD evidence reported | ✅ | 3 `### TDD Cycle Evidence` tables in `apply-progress.md` (lines 54, 188, 347) — one per PR |
| All tasks have tests | ✅ | 22/22 tasks map to a test file or an explicitly non-behavioural sweep/config action |
| RED confirmed (tests exist) | ✅ | Codec file exists with 14 tests; RED proofs recorded at pre-inversion `8515e77` → **11 failed, 3 passed**; canary → **1 failed** |
| GREEN confirmed (tests pass) | ✅ | 12/12 codec tests + 4/4 reader guards pass on execution this run |
| Triangulation adequate | ✅ | Every scenario with multiple facets has distinct-value tests; REQ-FLAT-4 scenario 4 has **both** a source guard and a behavioural probe |
| Safety net for modified files | ✅ | 208/208 → 2652/2652 → 30/30 baselines captured before each edit |

**TDD Compliance**: **6/6 checks passed.**

The 3 codec tests that cannot fail pre-inversion are the byte/signature stability
guards (`test_a_real_setting_element_is_byte_stable_over_four_cycles`,
`test_the_data_signature_is_idempotent_across_four_cycles`, and the 4th of the
11-failed set). This is acknowledged in `archive-report.md` deviation 5 and is
correctly characterised: stability alone is not evidence of a correct codec, and
the other 11 failing pre-inversion tests carry that weight.

### Test Layer Distribution

| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | ~12 | 3 | pytest |
| Integration | ~18 | 3 | pytest |
| E2E | 0 | 0 | not installed |
| **Total (change-owned)** | **30** | **6** | |

No tool outside the cached capabilities was used, so there is no
tools-vs-capabilities deviation.

### Changed File Coverage

Coverage analysis **skipped — no coverage tool detected** (`coverage` not
installed). Informational only; never a failure.

### Assertion Quality

Scanned all change-owned test files for tautologies, orphan empty checks,
ghost loops, assertion-free tests, smoke-only tests, and implementation-detail
coupling.

- No tautology (`assert True`, `assert 1 == 1`) found in any file.
- No ghost loops over possibly-empty collections.
- Every test exercises production code through a real reader→writer cycle.
- The 3 `is not None` occurrences (`test_adaptive_retest_agent.py:364,386`,
  `test_reader_advanced_rankings.py:271`) are guard clauses immediately followed
  by value assertions on the same object, so none is a bare type-only check.
- Mock-to-assertion ratio in `test_flat_lane_round_trip.py`: **0 mocks, 40
  assertions** — the exact inverse of a mock-heavy file, and appropriate for a
  codec contract that must be proven against real XML.

**Assertion quality**: ✅ **All assertions verify real behavior.** 0 CRITICAL, 0 WARNING.

### Quality Metrics

**Linter**: ➖ Not available (`ruff` not installed locally; CI-only per `AGENTS.md`)
**Type Checker**: ➖ Not available (`mypy` not installed locally; CI-only)

## Correctness (Static Evidence)

| Requirement | Status | Notes |
|-------------|--------|-------|
| REQ-FLAT-1 | ✅ Implemented | `reader.py:459` `prefix=""`; `writer.py:580` `key.partition("@")`. No key carries the section tag. |
| REQ-FLAT-2 | ✅ Implemented | `reader.py:456-458` one entry per leaf `<Setting>`; `writer.py:587` grouping rejoins the pair. |
| REQ-FLAT-3 | ✅ Implemented | No collapse on read; the writer never emits `Tag@attr` as `<Setting>`. |
| REQ-FLAT-4 | ✅ Implemented | One predicate, one call site per lane; `DATA_RANGE_PART_TAGS` derived so the lanes cannot drift. |
| REQ-FLAT-5 | ✅ Implemented | `build_retester_cfx` template output preserves both databanks; no name-matching heuristic was added, per the design's undecidability argument. |
| REQ-FLAT-6 | ✅ Implemented | Bare-key branch at `writer.py:584`; the empty-tag guard also prevents malformed XML for a key like `"@value"`. |
| REQ-FLAT-7 | ✅ Implemented | No behaviour change was needed — `apply_adaptive_mutations` was already correct once the codec was a bijection. The defect was the codec, not the agent. |

## Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| #1 Reader + writer ship atomically | ✅ Yes | Both halves in `374a2cf`; neither exists in an intermediate commit. |
| #2 Keep `settings: dict[str, str]` | ✅ Yes | Type unchanged; grouping-by-tag is injective on distinct keys. |
| #3 Group `Tag@attr` by tag | ✅ Yes | `writer.py:588-589`, first-appearance order via `dict` insertion. |
| #4 Bare keys keep `<Setting>` | ✅ Yes | `test_templates.py:281-282` untouched and green, as required. |
| #5 Guard is a shared deny-list | ✅ Yes | `_DATA_OWNED_TAGS`; allow-list alternative correctly rejected as silently lossy. |
| No producer changes | ✅ Yes | `patcher`, `translator`, `templates`, `risk_mapper` untouched in production; they already emitted the target grammar. |

**Threat matrix**: N/A — no routing, shell, subprocess, VCS automation, or
process-integration boundary was introduced.

## Issues Found

### CRITICAL

**None open.** 0 blockers, 0 untested requirements, 0 failing tests, 0 incomplete
tasks.

One finding was CRITICAL and is **closed by this report**:

- **F0 — missing `sdd-verify` artifact (process gap, CLOSED).** At archive time no
  `verify-report.md` existed on disk and no
  `sdd/fix-flat-lane-settings-projection/verify-report` observation existed in
  Engram, while `apply-progress.md:479` still read "Ready for `sdd-verify`". An
  earlier `sdd-verify` run had claimed to produce the report; it had not. The
  behavioural claims turned out to be true, but the audit record was absent. **This
  file is that record.** F0 is closed; the code required no re-work.

### WARNING

- **W1 — Design naming deviation.** `design.md:24` says `<Data>` passes
  `DATA_RANGE_PART_TAGS | _DATA_PASSTHROUGH_TAGS`. The shipped code composes that
  union into a named constant, `_DATA_OWNED_TAGS` (`reader.py:87`), and passes it.
  Both `_DATA_PASSTHROUGH_TAGS` (line 83) and `DATA_RANGE_PART_TAGS` exist as
  specified. **Naming only — the decision is followed and no spec is affected.**
  `apply-progress.md` records the extraction in the 1.4/1.5 REFACTOR column.
- **W2 — Stale Engram tasks snapshot (`#1123`).** The observation
  `sdd/fix-flat-lane-settings-projection/tasks` is the **pre-apply** state: 21 tasks,
  all `- [ ]`, no task 4.3. The authoritative completion state (22/22) exists only in
  the file `tasks.md`. A future reader who finds `#1123` by topic search will see
  zero completed work. **Read the file, not the observation.** Carried forward from
  `archive-report.md` §3; correcting it needs its own SDD change.
- **W3 — Archive follow-up F1: `rules.verify.*` unset.** `openspec/config.yaml:37-40`
  leaves `test_command: ""`, `build_command: ""`, `coverage_threshold: 0`. This report
  therefore declared an **ad-hoc** test command and an `compileall` build command
  rather than reading them from config. Populating the config would assert a CI
  capability this change did not verify, so `6a4a4c9` left it deliberately.
- **W4 — Archive follow-up F2: `_SETTINGS_SECTIONS` omits `Rankings`/`CrossChecks`.**
  `reader.py:53-60` contains only `Options`, `RiskMoneyManagement`, `WhatToBuild`,
  `Data`, `PartsToImprove`, `Notes`, so those two flat lanes are never populated by
  the reader. Pre-existing asymmetry, explicitly out of scope
  (`design.md` Open Question #2, still unchecked) and untouched by this change. It
  does **not** affect any REQ-FLAT requirement.
- **W5 — Archive follow-up F3: external-consumer dialect break.** The emitted XML
  changed form: a consumer that looked up `Setting[@key='Tag@attr']` no longer
  finds it. Per design decision, legacy files converge to one stable form after a
  single cycle rather than being repaired losslessly. Intentional, but it is a
  breaking change for any consumer outside this repository and deserves release-note
  visibility.
- **W6 — 3 of 14 codec tests are stability guards that cannot fail pre-inversion.**
  Confirmed and correctly disclosed in `archive-report.md` deviation 5. 11 of 14 fail
  against the pre-inversion codec at `8515e77`, which is the load-bearing RED proof.

### SUGGESTION

- **S1 — Archive follow-up F4: `cfx-serialization` vs `cfx-editor` overlap.** The two
  capabilities now describe adjacent concerns in the same `sdk/quantlab/cfx/` package.
  Unresolved by design; splitting capability boundaries is not this change's mandate.
  Decide merge-or-peer in a dedicated change.
- **S2 — `proposal.md:82-87` carries six unchecked `- [ ]` success criteria.** These
  are proposal-phase artifacts and are archived as written. For the record all six are
  satisfied by the evidence above. Checking them retroactively would rewrite an
  upstream phase artifact, so archive correctly left them alone.
- **S3 — Coverage is unmeasurable locally.** Installing `coverage` (and, in CI,
  `ruff`/`mypy`) would let a future verify phase report changed-file line and branch
  coverage instead of `➖ Not available`.

## Verdict

# PASS WITH WARNINGS — 0 CRITICAL, 6 WARNING, 3 SUGGESTION

All **22/22** tasks are complete, all **7/7** REQ-FLAT requirements and **14/14**
scenarios are backed by tests that passed at runtime, the change-owned surface is
**2666 passed / 0 failed**, and the full suite is **4134 passed / 9 skipped /
0 failed, exit 0**, on HEAD `5cebb17`. Strict TDD compliance is 6/6 with zero
trivial assertions.

The warnings are all *open follow-ups or disclosures*, not defects in this change's
deliverable: a design naming deviation with no behavioural effect, a stale Engram
snapshot, and the four archive-flagged follow-ups (F1–F4) that each need their own
SDD change. Follow-up **F0 — the missing verification artifact — is closed by this
report**, which was the sole process gap blocking a clean archive.
