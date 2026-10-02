# Apply Progress: fix-flat-lane-settings-projection

Mode: **Strict TDD** (runner `SQX_FORCE_MOCK=1 python3 -m pytest -q`).
Delivery: **auto-chain**, chain strategy **stacked-to-main**, review budget 400 changed lines.

---

## PR 1 of 3 — codec inversion + invalidated test migrations (work unit 1)

**Start state.** `SettingsSection.settings` was a lossy projection. The reader
flattened a section from the *section element*, so every key carried the section
tag; a real SQX `<Setting key="K" value="V"/>` became two entries keyed by the
literals `Setting@key`/`Setting@value`; and the writer re-emitted every key as
`<Setting key= value=/>`, so N `<Setting>` children collapsed to one pair at read
time. `GBPUSD_H1` overwrote `EURUSD_H1` on a retester round trip.

**Finished state.** The flat lane is a bijection. Read flattens a section's
*children* with `prefix=""`; one shared predicate `_is_flat_lane_child` decides
lane membership for **both** the admit path (`_parse_settings_element`) and the
strip path (`_parse_data_range_parts`). A leaf `<Setting key= value=/>` becomes
ONE entry `settings[K] = V`. Write de-flattens: bare keys → `<Setting key= value=/>`,
`Tag@attr` keys split once on `@` and group by tag into one element per tag, in
first-appearance order.

### Completed Tasks

- [x] 0.1 *(pre-existing, gatekeeper)* REQ-FLAT-6 scenario-1 amendment landed.
- [x] 1.1 RED `test_flat_lane_holds_only_setting_children` → `{"Symbol@symbol": "EURUSD"}`
- [x] 1.2 RED `test_flat_settings_are_not_duplicated_into_the_typed_lane`; rescope `test_second_cycle_does_not_grow_the_data_section`
- [x] 1.3 GREEN `DATA_RANGE_PART_TAGS` in `cfx/models.py`; `settings` grammar stated in `SettingsSection`
- [x] 1.4 GREEN `_is_flat_lane_child` + `_DATA_PASSTHROUGH_TAGS` (+ `_DATA_OWNED_TAGS`); `setting_children_only` removed
- [x] 1.5 GREEN `_parse_settings_element` iterates children; `_parse_data_range_parts` reuses the predicate
- [x] 1.6 GREEN `_append_settings_section` groups by tag; `_append_merged_complex_section` docstring corrected
- [x] 1.7 RED→GREEN `test_writer_section_merge.py:85-91,116`
- [x] 1.8 RED→GREEN `test_mixed_rankings_compatibility.py`
- [x] 1.9 RED→GREEN `test_translator_advanced_rankings.py`, `test_project_builder_golden_rankings.py`
- [x] 1.10 RED→GREEN `sdk/tests/test_translator.py` (**unplanned** — see Deviations)

### Files Changed

| File | Action | What Was Done |
|------|--------|---------------|
| `sdk/quantlab/cfx/models.py` | Modified | `DATA_RANGE_PART_TAGS` derived from `_DATA_RANGE_PART_ELEMENTS`; `SettingsSection` docstring states both key grammars |
| `sdk/quantlab/cfx/reader.py` | Modified | `_is_flat_lane_child` + `_DATA_PASSTHROUGH_TAGS` + `_DATA_OWNED_TAGS`; `_parse_settings_element` rewritten (`exclude_tags` replaces `setting_children_only`); `_parse_data_range_parts` strips via the same predicate |
| `sdk/quantlab/cfx/writer.py` | Modified | `_append_settings_section` de-flattens and groups by tag; `_append_merged_complex_section` docstring no longer claims children are all `<Setting>` |
| `sdk/quantlab/phase4/templates.py` | Modified | Docstring records the emitted-XML dialect decision where the bare `{db: "true"}` keys are built |
| `sdk/tests/test_translator.py` | Modified | Two pinned `Setting[@key='Symbol@symbol']` lookups → `<Symbol>`/`<Timeframe1>` |
| `tests/cfx/test_reader_advanced_rankings.py` | Modified | 3 expectations + 3 docstrings |
| `tests/cfx/test_writer_section_merge.py` | Modified | `Criterion1` grouping at 85-91 and 116 |
| `tests/cfx/test_mixed_rankings_compatibility.py` | Modified | Module docstring + 6 assertions/docstrings |
| `tests/phase4/test_translator_advanced_rankings.py` | Modified | Tags at 180, 187, 226-231, 241-247 |
| `tests/phase4/test_project_builder_golden_rankings.py` | Modified | Docstring rescoped to both lanes |

### TDD Cycle Evidence

Safety-net baseline captured **before** any edit:
`SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/` → **208 passed** (clean).

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1, 1.2 | `tests/cfx/test_reader_advanced_rankings.py` | Unit | ✅ 208/208 | ✅ 2 rewritten | ✅ passed | ✅ 3 cases (flat leaf / typed+passthrough excluded / nested subtree) | ✅ class + 2 docstrings rescoped |
| 1.3 | `sdk/quantlab/cfx/models.py` | Unit (constant) | ✅ 208/208 | ✅ tests reference the grammar | ✅ passed | ➖ derived constant, one definition | ✅ comment explains the cross-module coupling it avoids |
| 1.4, 1.5 | `sdk/quantlab/cfx/reader.py` | Unit | ✅ 208/208 | ✅ rewritten | ✅ passed | ✅ admit leaf, admit `Tag@attr`, exclude typed, exclude passthrough, exclude subtree | ✅ extracted `_is_flat_lane_child` + `_DATA_OWNED_TAGS` |
| 1.6 | `sdk/quantlab/cfx/writer.py` | Unit | ✅ 208/208 | ✅ `["Criterion1"]` / `<Symbol>` | ✅ passed | ✅ bare key, tagged group, non-contiguous tag, empty-tag edge | ✅ guard `not element_tag` added |
| 1.7 | `tests/cfx/test_writer_section_merge.py` | Integration | ✅ 208/208 | ✅ RED | ✅ passed | ✅ grouped attrs dict + tag list | ➖ none needed |
| 1.8 | `tests/cfx/test_mixed_rankings_compatibility.py` | Integration | ✅ 208/208 | ✅ RED | ✅ passed | ✅ `Criterion1`/`Criterion2` indexes, `<FromDate>`/`<ToDate>` | ✅ docstrings rescoped, no coverage dropped |
| 1.9 | `tests/phase4/*` | Integration | ✅ 208/208 | ✅ RED | ✅ passed | ✅ ranked `<Data>` with and without `raw_xml` | ✅ golden docstring rescoped |
| 1.10 | `sdk/tests/test_translator.py` | Integration | ➖ added after the full-suite run surfaced it | ✅ RED | ✅ passed | ➖ 2 sites, same codec | ➖ none needed |

**RED proof (focused, before any production change):**
`pytest -q tests/cfx/test_reader_advanced_rankings.py tests/cfx/test_writer_section_merge.py tests/cfx/test_mixed_rankings_compatibility.py tests/phase4/test_translator_advanced_rankings.py`
→ **14 failed, 40 passed**, e.g. `assert ['Setting','...','Setting'] == ['Symbol','Timeframe1']`.

**REFACTOR gate:** the empty-tag guard was added after the green run and the
full suite was re-executed — still 4120 passed / 0 failed.

### Test Summary

- **Tests written/updated**: 17 assertions across 6 files (0 deleted — coverage preserved or widened).
- **Focused (change-owned):** `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/ tests/phase4/ tests/agents/` → **1168 passed, 0 failed**.
- **Full suite:** `SQX_FORCE_MOCK=1 python3 -m pytest -q` → **4120 passed, 9 skipped, 0 failed**.
- **Layers used**: Unit (2), Integration (4). Approval tests: n/a — the RED layer *is* the approval layer (expectations rewritten before code).
- **Pure functions created**: 1 (`_is_flat_lane_child`).

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/ tests/phase4/ tests/agents/` → exit 0, **1168 passed**. Full suite `SQX_FORCE_MOCK=1 python3 -m pytest -q` → exit 0, **4120 passed, 9 skipped**. |
| Runtime harness command/scenario and exact result | `build_retester_cfx(databanks=['EURUSD_H1','GBPUSD_H1'], data_range_parts=DataRangeParts(ist='0.15'))` → write → read → write ×4. Result: `<Data>` children `['Setting','Setting','IST']` at every cycle; `Setting[@key='EURUSD_H1']` and `Setting[@key='GBPUSD_H1']` both `value="true"` (**previously `EURUSD_H1` was lost**); flat lane `{'EURUSD_H1':'true','GBPUSD_H1':'true'}`; `data_range_parts.ist == '0.15'`; **4-cycle byte identity: True**. Direct codec probe: bare `"@value"` stays a `<Setting>` (no invalid empty tag), legacy `Setting@key`/`Setting@value` coalesce to one `<Setting key="EURUSD_H1" value="true"/>`, non-contiguous `Criterion1@*` merges into one `<Criterion1>` at first appearance. |
| Rollback boundary | Revert this single commit. It is self-contained: `sdk/quantlab/cfx/{models,reader,writer}.py`, `sdk/quantlab/phase4/templates.py` (docstring only), and the 6 migrated test files. No producer, schema, CLI or persistence code changed; no data migration; no feature flag. |

### Zero-Regression Proof (failure-SET comparison)

| Tree | Failure set |
|------|-------------|
| This change | **∅** — 4120 passed, 9 skipped, 0 failed |
| Baseline `HEAD` (isolated `git worktree`, no shared index) | 7 failures, all environment-only: `tests/cfx/test_reader.py::TestTypeDetection::test_{single_task_detected_as_config,multi_file_detected_as_project}`, `tests/cfx/test_writer.py::TestRoundTrip::test_{read_write_config_preserves_version,write_project_then_read_preserves_version}`, `tests/sqx/test_mock_guard.py::…test_orchestrated_blocks_validation_fixture_fallback`, `sdk/tests/sqx/test_blocks_bridge.py::…test_fixture_fallback_remains_available`, `sdk/tests/test_kb_educational.py::…test_real_template_resolves_from_repo` |

Root cause of the 7 baseline failures, verified individually:
`CfxNotFoundError: CFX file not found: …/tests/cfx/fixtures/NQ_CFD_H1.cfx` — those
`.cfx` fixtures are untracked local files absent from a fresh worktree. None of
the 7 files is touched by this change. **The change's failure set is a strict
subset of baseline (empty), so zero regressions.**

Guards confirmed **untouched** (diff hunks verified by `git diff -U0`):
`test_nested_elements_do_not_leak_into_the_flat_lane`, `tests/phase4/test_templates.py:281-282`,
`tests/cfx/test_writer_section_merge.py:147,168`.

### Deviations from Design

- **`_DATA_OWNED_TAGS` added (design listed only `_DATA_PASSTHROUGH_TAGS`).**
  The design defines `<Data>`'s exclusion as
  `DATA_RANGE_PART_TAGS | _DATA_PASSTHROUGH_TAGS`. That expression is needed
  identically at *two* call sites (admit and strip), so it is bound once as a
  module constant. Same value, one fewer chance for the two to drift — which is
  the exact failure the single-predicate invariant exists to prevent.
- **Empty-tag guard in `_append_settings_section` (not in the design).** A key of
  `"@value"` partitions to an empty tag and would emit `<  value="x"/>`, which is
  invalid XML and makes the file unreadable on the next cycle. Treated as a bare
  key instead. Not reachable from any current producer; the design lists
  hand-built fixtures as a tolerance surface, so the writer is made total there.
  **Pinned in PR 2** as task 2.6.
- **`sdk/tests/test_translator.py` migrated (not in the task list).** Tasks 1.7–1.9
  enumerate 6 test files; the codec inversion also changed the *emitted* dialect
  that two SDK-level translator tests pin. They failed in the full-suite run, so
  leaving them would have shipped a red suite. Migrated (task 1.10), coverage
  preserved. **Tasks.md under-enumerated the invalidated set** — the enumerated
  line lists missed `test_mixed_rankings_compatibility.py:105-110,126,170-175,238-239`
  and this file. **RESOLVED in PR 2**: `tasks.md` tasks 1.7–1.10 now carry the
  verified hunk ranges from `git show 374a2cf --unified=0`.

### Issues Found

- The enumerated per-line migration lists in `tasks.md` were incomplete (above).
  Everything that broke was migrated; nothing was deleted.
- `_SETTINGS_SECTIONS` omits `Rankings` and `CrossChecks`, so the reader never
  populates those flat lanes. Pre-existing asymmetry, already recorded as out of
  scope in `design.md` Open Questions; untouched.
- The `openspec/changes/fix-flat-lane-settings-projection/` directory is
  **untracked** on this branch. Committing design/spec/tasks alongside PR 1 would
  push the diff past the 400-line review budget, so this work unit commits code
  and tests only. **The orchestrator must decide** whether the planning
  artifacts land as their own docs commit.

---

## PR 2 of 3 — codec round-trip coverage + shared-predicate guard (work unit 2)

**Start state.** PR 1 (`374a2cf`) inverted the codec and migrated every
expectation it invalidated, but the new behaviour itself had no direct test: the
five-key `<Data>` survival, the two-databank pairing and the four-cycle byte
identity existed only as claims in `design.md`, verified by a throwaway
harness. A shared-predicate invariant had no guard, so a second drifting copy of
the rule would have reintroduced lane duplication silently. The empty-tag writer
guard added in PR 1 was an undocumented deviation with no pin.

**Finished state.** `tests/cfx/test_flat_lane_round_trip.py` — 14 tests, every
spec scenario of REQ-FLAT-1..6 named in a docstring, **zero production code
changed**. The file is proof, not behaviour: it fails 11/14 against the
pre-inversion codec and passes 14/14 against `374a2cf`.

### Completed Tasks

- [x] 2.1 no section prefix; the patcher `Timeframe` scan matches after a read
- [x] 2.2 5-key `<Data>` survival; in-place sibling preservation; 2-databank pairing
- [x] 2.3 legacy `Setting@key`/`Setting@value` coalesce; 4-cycle byte identity
- [x] 2.4 emitted dialect: bare keys → `["Setting","Setting"]`; `Tag@attr` keys stay grouped; `Setting[@key=…]` addressable
- [x] 2.5 `inspect.getsource` shared-predicate guard + behavioural triangulation
- [x] 2.6 (unplanned) empty-tag edge pinned

Artifact correction, done first as the orchestrator required: `tasks.md` Phase 1
under-enumerated the invalidated set. Tasks 1.7–1.9 now carry the **verified**
hunk ranges from `git show 374a2cf --unified=0`, and 1.8 states explicitly that
its original list was wrong.

### Files Changed

| File | Action | What Was Done |
|------|--------|---------------|
| `tests/cfx/test_flat_lane_round_trip.py` | Created | 14 tests; every case drives `CfxReader`/`CfxWriter` over a real archive on disk, so the observable is the XML a campaign would load |
| `openspec/changes/fix-flat-lane-settings-projection/tasks.md` | Modified | Corrected PR 1's migrated-hunk enumeration; Phase 2 marked complete with per-test scenario mapping |
| `openspec/changes/fix-flat-lane-settings-projection/apply-progress.md` | Modified | This section (PR 1 content preserved above) |

**Zero production code touched** — `git diff -U0 HEAD` over
`sdk/quantlab/cfx/{reader,writer}.py` is empty.

### TDD Cycle Evidence

Safety-net baseline captured **before** any edit:
`SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/ tests/phase4/ tests/agents/ sdk/tests/`
→ **2652 passed, 0 failed**.

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 2.1 | `tests/cfx/test_flat_lane_round_trip.py` | Integration | ✅ 2652/2652 | ✅ 3/4 fail pre-inversion | ✅ passed | ✅ `<WhatToBuild>` + `<Options>`, Setting-wrapped and leaf keys | ✅ two tests → one patcher call |
| 2.2 | same | Integration | ✅ 2652/2652 | ✅ 2/2 fail pre-inversion | ✅ passed | ✅ standalone `<Data>` and in-place rewrite with `<RetesterData>` sibling | ➖ none needed |
| 2.3 | same | Unit + Integration | ✅ 2652/2652 | ✅ 2/4 fail pre-inversion | ✅ passed | ✅ coalesce-on-write vs never-produce-on-read; bytes vs `<Data>` signature | ✅ `_data_task` helper reused |
| 2.4 | same | Integration | ✅ 2652/2652 | ✅ 1/2 fail pre-inversion | ✅ passed | ✅ in-memory task + real `build_retester_cfx` output | ✅ `_retester_cfx` extracted from a duplicated 7-line call |
| 2.5 | same | Unit + Source | ✅ 2652/2652 | ✅ 2/2 fail pre-inversion | ✅ passed | ✅ source guard + behavioural `_is_flat_lane_child` probe | ➖ none needed |
| 2.6 | same | Unit | ✅ 2652/2652 | ➖ **not producible** (see below) | ✅ passed | ✅ write assertion + full read/write cycle re-read | ➖ none needed |

**RED proof — the whole file run against the pre-inversion codec.**
Isolated `git worktree` at `8515e77` (PR 1's parent), new test file copied in,
no shared index, no stash:
`SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/test_flat_lane_round_trip.py`
→ **11 failed, 3 passed**. The failures are the defects this change exists to
remove, not incidental errors:

- `assert {} == {'Symbol@symbol': 'EURUSD', 'Symbol@name': 'Euro/USD', 'Timeframe1@value': 'H1', 'FromDate@value': '2015.01.01', 'ToDate@value': '2024.12.31'}` — the five-key collapse.
- `assert {'WhatToBuild.Setting@key': 'BuildType@value', …} == {'BuildType@value': 'genetic', …}` — section-prefix pollution.
- `AttributeError: module 'quantlab.cfx.reader' has no attribute '_is_flat_lane_child'` — the shared predicate did not exist.

**The 3 that pass pre-inversion are honest negatives**, not gaps: byte-stability,
`<Data>`-signature idempotence, and bare-key `["Setting","Setting"]` all already
held before the inversion, because the un-inverted codec was *stable but wrong*.
Stability alone cannot detect a codec that faithfully preserves the wrong shape —
which is exactly why 2.2/2.4/2.1 exist alongside it.

**Task 2.6 has no producible RED, and the record says so.** The empty-tag guard
only exists on the grouping path, which the pre-inversion writer did not have;
pre-inversion, `{"@value": …}` also emitted a valid `<Setting>`. The test is a
pin on PR 1's documented deviation, not a RED→GREEN cycle. It is not marked FAILED
in the table above because it was written before any code existed in this work
unit — there simply was no code in this work unit.

### Test Summary

- **Tests written**: 14 (0 deleted, 0 modified — pure addition).
- **Focused:** `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/test_flat_lane_round_trip.py` → **14 passed**, 0.40s.
- **Change-owned:** `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/ tests/phase4/ tests/agents/ sdk/tests/` → **2666 passed, 0 failed** (2652 + 14).
- **Full suite:** `SQX_FORCE_MOCK=1 python3 -m pytest -q` → **4134 passed, 9 skipped, 0 failed**. PR 1 closed at 4120; the delta is exactly the 14 new tests, so nothing else moved.
- **Layers used**: Unit (4), Integration (10). Pure functions created: 0. Approval tests: n/a.
- **Assertion quality**: every assertion calls production code and compares a concrete value. The `inspect.getsource` guard is the only non-value assertion, and it is deliberate — the spec makes it source-level — so 2.5 ships a behavioural probe alongside it.

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/test_flat_lane_round_trip.py` → exit 0, **14 passed in 0.40s**. Change-owned `tests/cfx/ tests/phase4/ tests/agents/ sdk/tests/` → exit 0, **2666 passed**. Full suite → exit 0, **4134 passed, 9 skipped**. |
| Runtime harness command/scenario and exact result | Real archive on disk via `CfxWriter.write` / `CfxReader.read`, no mocks. Scenario: `build_retester_cfx(strategy_id="strat-1", databanks=["EURUSD_H1","GBPUSD_H1"])` → write → read → write. Result: `data.settings == {"EURUSD_H1": "true", "GBPUSD_H1": "true"}`; `<Data>` children `["Setting","Setting"]`; both `Setting[@key=…]` `value="true"` (**previously `EURUSD_H1` was lost**). Second scenario: hand-built 4-flat-child `<Data>` + `<IST>` + nested `<Setups>` + `<RetesterData>` sibling through 4 read/write cycles → `len(pass) == 6` elements and all four signatures identical. Third: real `CfxPatcher.add_timeframe("M15")` on a read-back file → `{"Timeframe1@value": "H1", "Timeframe2@value": "M15"}`. |
| Rollback boundary | Revert the single commit. It adds one file and touches nothing else: `tests/cfx/test_flat_lane_round_trip.py` (+399). No production module, schema, CLI, fixture or persistence code is in the commit, so reverting cannot remove unrelated work. The `tasks.md` / `apply-progress.md` edits are documentation and remain untracked with the rest of the change directory. |

### Zero-Regression Proof (failure-SET comparison)

Isolated clean-HEAD `git worktree` at `374a2cf` (no shared index, no stash),
same command, same interpreter:

| Tree | `tests/cfx/ tests/phase4/ tests/agents/ sdk/tests/` |
|------|-------------------------------------------------|
| This work unit (dirty tree, concurrent session active) | **∅** — 2666 passed, 0 failed |
| Baseline `374a2cf` (isolated worktree) | 6 failed, 2643 passed, 3 skipped |

The 6 baseline failures, with root cause verified individually by re-running
them: `CfxNotFoundError: CFX file not found: …/tests/cfx/fixtures/NQ_CFD_H1.cfx`
(`tests/cfx/test_reader.py::TestTypeDetection` ×2,
`tests/cfx/test_writer.py::TestRoundTrip` ×2,
`sdk/tests/sqx/test_blocks_bridge.py::…test_fixture_fallback_remains_available`)
and `missing real template: …/assets/…/tpl_build.xml`
(`sdk/tests/test_kb_educational.py::…test_real_template_resolves_from_repo`).
Those `.cfx` fixtures and the `assets/` tree are **untracked local files absent
from a fresh worktree** — environment, not code. **Not one of the 6 files is
touched by this work unit, so the change's failure set is a strict subset of
baseline (empty): zero regressions.**

Regression guards confirmed **byte-identical to `374a2cf`** by
`git diff -U0 HEAD` (empty output) over `tests/phase4/test_templates.py`,
`tests/cfx/test_writer_section_merge.py`, `tests/cfx/test_reader_advanced_rankings.py`
and both codec modules. The guard line numbers are unmoved:
`test_templates.py:281-282` still hold the two `Setting[@key=…]` assertions and
`test_writer_section_merge.py:147,168` the `<IST>`/`<OOS1>`/`<Setting>` ones.

### Deviations from Design

- **`tests/cfx/test_flat_lane_round_trip.py` landed at 399 lines, not ~200.**
  The forecast sized the unit by production code, which is zero here; a test file
  cannot be gamed smaller without dropping spec scenarios. It still fits one
  commit under the 400-line budget, so no `size:exception` was needed — but the
  forecast line was measuring the wrong thing and Phase 3's ~40 estimate should
  be read as unmeasured until it is written.
- **`test_five_key_data_survives_a_full_round_trip` folds in one extra scenario.**
  `design.md` predicted one pair where five keys went in; the test asserts the
  full `(tag, attributes)` signature as well as the dict, so it pins the emitted
  element form rather than only the key set. Same scenario, stronger assertion.
- **`test_a_producer_timeframe_key_is_findable_after_a_read` drives the real
  `CfxPatcher`** instead of re-implementing its `k.startswith("Timeframe")` scan
  in the test. Task 2.1 described the scan as the observable; copying it into the
  test would have made it a tautology that a reader change could not break.

### Issues Found

- **`tasks.md` Phase 1 was wrong about its own history**, now corrected. The
  recorded per-line migration lists were guesses made before the full-suite run
  surfaced the real set; 1.8 in particular named 3 ranges where 10 hunks were
  migrated. Every one of those sites *was* migrated in PR 1 — nothing was left
  red — but the artifact could not be trusted to review PR 1. The corrected
  ranges are taken from `git show 374a2cf --unified=0`, not from memory.
- **Three of the fourteen tests cannot fail pre-inversion** (stability without
  correctness). Noted above rather than hidden: a reviewer comparing "11/14 RED"
  against "14/14 GREEN" should know the 3 are stability guards, and why stability
  alone is not evidence of a correct codec.
- **The `openspec/changes/fix-flat-lane-settings-projection/` directory is still
  untracked** (624 lines across 5 files, now more). Committing planning artifacts
  inside PR 2 would blow the 400-line budget, so PR 2 stays code+tests only.
  **The orchestrator still owes a decision**: land the planning artifacts as
  their own docs commit, or leave the change undocumented in git.

---

## PR 3 of 3 — adaptive-retest canary + docstring sweep (work unit 3)

**Start state.** REQ-FLAT-7's canary was the one defence still asserting the
*old* codec's tolerances. `test_preserves_unrelated_cfx_content` ran
`apply_adaptive_mutations` over a single-key `<Data>` and probed
`any("EURUSD" in v for v in ...)`. A substring match cannot observe either way
the flat lane failed: a collapsed key set, or a mangled key name. Worse, one key
hides both. Stale `Setting@key` docstrings may also have survived PR 1.

**Finished state.** The canary carries all four REQ-FLAT-7 keys and asserts
exact dict equality, per-section; the mangled literals are excluded by name. It
**fails against the pre-inversion codec** — the defect it was written to catch —
which the old version demonstrably did not. The docstring sweep found **nothing
stale to fix**: PR 1 had already corrected every one. Zero production code
changed.

### Completed Tasks

- [x] 3.1 RED: 4-key `<Data>` (Symbol/Timeframe1/FromDate/ToDate); `any(...)` → exact equality
- [x] 3.2 GREEN: proved `apply_adaptive_mutations` already satisfies it; no behaviour change
- [x] 4.1 docstring sweep → **zero stale docstrings found**; both guards re-verified
- [x] 4.2 full-suite gate → **4134 passed / 9 skipped / 0 failed**, exit 0
- [x] 4.3 *(unplanned)* `openspec/config.yaml` strict-TDD drift reconciled

### Files Changed

| File | Action | What Was Done |
|------|--------|---------------|
| `tests/agents/test_adaptive_retest_agent.py` | Modified | `test_preserves_unrelated_cfx_content` only: 4-key `<Data>`, exact equality on all three sections, mangled-literal exclusion (+23/−9) |
| `openspec/config.yaml` | Modified | `testing.strict_tdd` and `rules.apply.tdd` → `true`; `testing.runner` → `pytest`; `rules.apply.test_command` populated (+7/−5) |

Committed as two work units: `fa81b31` (canary), `6a4a4c9` (config). **44 changed
lines total — 11% of the 400 budget.** Planning artifacts remain untracked (below).

**Zero production code touched** — `git diff -U0 1b035c5 HEAD` over
`sdk/quantlab/` is empty. `adaptive_retest_agent.py` needed no change, as task 3.2 predicted.

### TDD Cycle Evidence

Safety-net baseline captured **before** any edit:
`SQX_FORCE_MOCK=1 python3 -m pytest -q tests/agents/test_adaptive_retest_agent.py` → **30 passed**.

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 3.1, 3.2 | `tests/agents/test_adaptive_retest_agent.py` | Integration | ✅ 30/30 | ✅ **fails vs `8515e77`** | ✅ 30 passed | ✅ 3 sections × distinct key grammar + a negative exclusion | ✅ `data_keys` named once; `dict()` copy so the expectation is not aliased to the object under test |
| 4.1 | — (docstrings) | Source | ✅ n/a | ➖ not a behaviour change | ✅ nothing to change | ➖ sweep is the test | ➖ none needed |
| 4.3 | — (SDD config) | Config | ✅ 70/70 `test_orchestrator_prompt.py` | ➖ not runtime code | ✅ YAML parses, values read back correct | ➖ scalar flags | ➖ none needed |

**RED proof — the strengthened canary against the pre-inversion codec.**
Isolated `git worktree` at `8515e77` (PR 1's parent), no shared index, no stash.
`tests/agents/` was byte-identical to `HEAD`, so copying the new test file in was
the only delta:

`SQX_FORCE_MOCK=1 python3 -m pytest -q …::test_preserves_unrelated_cfx_content`
→ **1 failed**:

```
assert {'Setting@key': 'Setting@value', 'Setting@value': '2024.12.31'}
    == {'Symbol@symbol': 'EURUSD', 'Timeframe1@value': 'H1',
        'FromDate@value': '2015.01.01', 'ToDate@value': '2024.12.31'}
Left contains 2 more items:  {'Setting@key': …, 'Setting@value': …}
Right contains 4 more items: {'Symbol@symbol': …, …}
```

Symbol, timeframe and FromDate were **destroyed**; two mangled literals survived.

**The same worktree ran the OLD assertion: `1 passed`.** That is the whole point
of this work unit — the canary was green *through* the defect. A direct probe of
both codecs, on both fixtures:

| Codec | `<Data>` fixture | keys after in-place rewrite | `any("EURUSD" in v)` | mangled intersection |
|---|---|---|---|---|
| `8515e77` pre-inversion | 1-key (old fixture) | `Setting@key`, `Setting@value` | **True → test passed** | `Setting@key`, `Setting@value` |
| `8515e77` pre-inversion | 4-key (new fixture) | `Setting@key`, `Setting@value` | False | `Setting@key`, `Setting@value` |
| `1b035c5` inverted | 1-key | `Symbol@symbol` | True | ∅ |
| `1b035c5` inverted | 4-key | all 4 `Tag@attr` keys | True | ∅ |

Two things this proves, which a "it passes now" claim would not:
1. the substring probe was blind to total key mangling on a 1-key section;
2. the **mangled-literal exclusion is a live assertion, not decoration** — it
   evaluates non-empty on the pre-inversion codec and empty on the fixed one.

### Test Summary

- **Tests written**: 0 added, 0 removed, **1 strengthened**. Count is unchanged at 30 by construction.
- **Focused:** `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/agents/test_adaptive_retest_agent.py` → **30 passed**.
- **Change-owned:** `tests/agents/ tests/cfx/ tests/phase4/ sdk/tests/` → **2666 passed**, identical to PR 2.
- **Full suite:** `SQX_FORCE_MOCK=1 python3 -m pytest -q` → **4134 passed, 9 skipped, 0 failed**, exit 0.
- **Layers used**: Integration (1). Pure functions created: 0. Approval tests: the pre-inversion run above is the approval baseline for the *defective* behaviour.
- **Assertion quality**: 4 assertions, all comparing a concrete production dict to a literal. No substring probes, no ghost loops, no empty-collection assertions without an explaining companion.

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/agents/test_adaptive_retest_agent.py` → exit 0, **30 passed**. Change-owned `tests/agents/ tests/cfx/ tests/phase4/ sdk/tests/` → exit 0, **2666 passed**. Full suite → exit 0, **4134 passed, 9 skipped**. |
| Runtime harness command/scenario and exact result | Real `.cfx` archive on disk through `apply_adaptive_mutations(cfx, RetestMode.AUTOMATIC_RETEST)` → `CfxWriter.write` → `CfxReader.read`, no mocks. Scenario: 4-key `<Data>` + `<WhatToBuild>` + `<Notes>` + empty `<CrossChecks>` rewritten **in place on the same path**. Result: `data.settings == {Symbol@symbol: EURUSD, Timeframe1@value: H1, FromDate@value: 2015.01.01, ToDate@value: 2024.12.31}`; `what_to_build == {StrategyType@type: simple}`; `notes == {Note@text: keep me}`; mangled intersection empty. Contrast scenario on `8515e77`: same call returns `{Setting@key: Setting@value, Setting@value: 2024.12.31}`. |
| Rollback boundary | Two independently revertible commits. `fa81b31` touches one test method's body and nothing else — reverting restores the weak canary without touching production behaviour or any other test. `6a4a4c9` touches only `openspec/config.yaml` and is revertible on its own. No producer, schema, CLI, fixture or persistence code is in either commit; no data migration; no feature flag. |

### Zero-Regression Proof (full-suite attribution)

Same command, same interpreter, full tree:

| Tree | Result |
|------|--------|
| `1b035c5` (PR 2 close, recorded) | 4134 passed, 9 skipped, 0 failed |
| `fa81b31` + `6a4a4c9` (PR 3) | **4134 passed, 9 skipped, 0 failed**, exit 0 |

**Identical counts are the required result, not a suspicious one.** PR 3 changed
zero production code and moved zero tests between added/removed, so any count
delta would have signalled an unintended edit. `tests/agents/ tests/cfx/
tests/phase4/ sdk/tests/` also held at 2666 across both. **Attribution: no
failure to attribute — the failure set is empty on both sides.**

The isolated-`8515e77` failure set (1 failed) is the *intended* RED for task 3.1,
observed in a throwaway worktree that has since been removed
(`git worktree list` back to a single entry). It is not present on this branch.

Regression guards re-verified **byte-identical to `374a2cf`**:
`git diff -U0 374a2cf HEAD -- tests/phase4/test_templates.py tests/cfx/test_writer_section_merge.py`
→ empty. `tests/phase4/test_templates.py:281-282` still carries both
`Setting[@key=…]` assertions; `test_templates.py` → 22 passed.

`tests/test_orchestrator_prompt.py` reads `openspec/config.yaml`, so the config
commit was gated on it separately: **70 passed**, and the diff touches no key under
`agents:` or `routing:`.

### Deviations from Design

- **Task 4.1 landed as a verified no-op.** The sweep was specified as "sweep
  remaining `Setting@key` docstrings", implying some existed. None did. The only
  two surviving mentions (`reader.py:444`, `writer.py:568`) both describe **legacy
  input**, not a produced form, and are accurate: PR 2 pins that coalescing path
  with `test_legacy_pair_coalesces_into_one_setting_element`.
  `setting_children_only` has **zero** occurrences in production code — remaining
  hits are SDD planning artifacts describing its removal. Reported as a finding
  rather than padded with edits to already-correct text.
- **`rules.apply.tdd` is the real key; `apply.tdb` does not exist** (the
  orchestrator's prompt carried that typo). Reported back with the correct name.
- **Config correction is 5 lines, not 2.** Flipping both TDD flags alone would
  leave `strict_tdd: true` beside `testing.runner: none` — the same contradiction
  in a new position — and `rules.apply.test_command` is the override
  `strict-tdd.md` reads, so an empty value keeps the drift in effect. Corrected
  as one coherent unit. `rules.verify.*` and the remaining `testing:` capability
  flags left alone: populating them would assert CI capability this change did
  not verify.

### Issues Found

- **The planning artifacts are still untracked — third PR running.** Three
  commits of codec behaviour have landed on this branch with `proposal.md`,
  `design.md`, `tasks.md`, `specs/` and `apply-progress.md` all outside git —
  **988 lines across 5 files**. The repo would gain an inverted codec with no
  recorded contract. Committing them blows the 400-line budget, which is why each
  PR deferred it — but deferring it three times is now the largest outstanding
  risk in this change, and it is an **orchestrator decision, not an apply-phase
  one**.
- **`_SETTINGS_SECTIONS` omits `Rankings` and `CrossChecks`**, so the reader never
  populates those flat lanes. Pre-existing, already recorded as out of scope in
  `design.md` Open Questions; untouched by all three PRs.
- **The forecast's `~40` for Phase 3 was accurate** (32 lines), which the PR 2
  deviation note had doubted. PR 2's file landed at 399 because it carried 14
  spec scenarios; a single-codec-assertion unit scales as forecast.

---

## Remaining Phases

None. Phases 0–4 are complete: **22 of 22 tasks**, 3 of 3 PRs landed
(`374a2cf` → `1b035c5` → `fa81b31` + `6a4a4c9`). **Ready for `sdd-verify`**,
carrying the untracked-planning-artifacts risk above.