# Tasks: Fix flat lane SettingsSection projection

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 480–560 |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 codec + test migration → PR 2 codec coverage → PR 3 canary |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

Reader+writer ship atomically (design decision #1), with every test they
invalidate. PR 1 migrated more sites than tasks 1.7–1.9 enumerated (task 1.10,
plus the corrected 1.8 list); PR 2's first action was to make the artifact match
the commit.

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Invert codec; migrate pinned expectations | PR 1 (landed, `374a2cf`) | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/ tests/phase4/` | `build_retester_cfx(['EURUSD_H1','GBPUSD_H1'])` → read → write; both survive | Revert the 3 modules + 6 migrated test files |
| 2 | Codec coverage + shared-predicate guard | PR 2 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/test_flat_lane_round_trip.py` | 4-cycle byte identity on a hand-built `<Data>` | Delete the new test file; zero production code |
| 3 | Adaptive-retest canary + stale docstrings | PR 3 (landed, 32 lines) | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/agents/test_adaptive_retest_agent.py` | `apply_adaptive_mutations` on a 4-key `<Data>`; re-read and diff | Revert the canary body; assertion-only |

Threat-matrix RED tests: N/A. PRs 2+3 may merge as one (~240).

## Phase 0: Pre-apply gate

- [x] 0.1 BLOCKING: land the REQ-FLAT-6 scenario-1 amendment (design Open Question) — translator tags → `["Criterion1"]`/`["Symbol","Timeframe1"]`. Never implement the spec literally.

## Phase 1: Core codec (PR 1)

- [x] 1.1 RED: `test_reader_advanced_rankings.py::test_flat_lane_holds_only_setting_children` → `{"Symbol@symbol": "EURUSD"}`; leave `test_nested_elements_do_not_leak_into_the_flat_lane` untouched.
- [x] 1.2 RED: rewrite `::test_flat_settings_are_not_duplicated_into_the_typed_lane`; rescope `::test_second_cycle_does_not_grow_the_data_section` docstring.
- [x] 1.3 GREEN: add `DATA_RANGE_PART_TAGS` to `cfx/models.py`; state the `settings` grammar in `SettingsSection`.
- [x] 1.4 GREEN: add `_is_flat_lane_child` + `_DATA_PASSTHROUGH_TAGS` to `cfx/reader.py`, drop `setting_children_only`; `<Data>` excludes `DATA_RANGE_PART_TAGS | _DATA_PASSTHROUGH_TAGS`.
- [x] 1.5 GREEN: `_parse_settings_element` iterates children (`prefix=""`); leaf `<Setting>` → one `settings[key]`; `_parse_data_range_parts` reuses the predicate.
- [x] 1.6 GREEN: `_append_settings_section` emits bare keys as `<Setting key= value=/>`, groups `Tag@attr` by tag in first-appearance order; fix `_append_merged_complex_section` docstring.
- [x] 1.7 RED→GREEN: `test_writer_section_merge.py:5,85-91,116` → one `<Criterion1>`; 147/168 stay green.
- [x] 1.8 RED→GREEN: `test_mixed_rankings_compatibility.py` — **corrected in PR 2**: the enumerated set (`22-28,277-282,296`) was incomplete. Verified against `git show 374a2cf --unified=0`, the real migrated hunks are `23-25, 105-107, 126, 149-153, 158-160, 172-173, 180, 238-239, 278-282, 296`.
- [x] 1.9 RED→GREEN: `test_translator_advanced_rankings.py:180,187,227-228,241-245`; `test_project_builder_golden_rankings.py:283-287` docstring.
- [x] 1.10 (unplanned, forced) `sdk/tests/test_translator.py:89-98,173-175` — the emitted translator dialect changed, so these pinned the old `<Setting[@key='Symbol@symbol']>` form. Migrated to `<Symbol>`/`<Timeframe1>`; coverage preserved.

## Phase 2: Codec coverage (PR 2)

Landed as `tests/cfx/test_flat_lane_round_trip.py` — **14 tests, zero production
code changed**. Tasks 2.1–2.4 are folded into one file; the spec scenarios are
named in each test's docstring.

- [x] 2.1 No section prefix; the patcher `Timeframe` scan matches after a read.
      → `test_no_section_tag_pollutes_a_non_data_flat_section`,
      `test_a_producer_timeframe_key_is_findable_after_a_read`
      (runs the real `CfxPatcher` + `AddTimeframeInstruction`, not a copied scan).
- [x] 2.2 5-key `<Data>` survival, in-place sibling preservation, 2-databank pairing.
      → `test_five_key_data_survives_a_full_round_trip`,
      `test_five_key_data_survives_an_in_place_rewrite`,
      `test_two_databanks_survive_a_read_write_cycle`
- [x] 2.3 Legacy `Setting@key`/`Setting@value` coalesce + 4-cycle byte identity.
      → `test_legacy_pair_coalesces_into_one_setting_element`,
      `test_the_reader_never_produces_setting_key_or_value_keys`,
      `test_a_real_setting_element_is_byte_stable_over_four_cycles`,
      `test_the_data_signature_is_idempotent_across_four_cycles`
- [x] 2.4 Dialect: bare keys → `["Setting","Setting"]`; no `Tag@attr` key becomes a
      `Setting`; `Setting[@key='GBPUSD_H1']` addressable.
      → `test_bare_keys_emit_setting_elements_that_stay_addressable`,
      `test_a_tagged_key_is_never_emitted_as_a_setting_element`
- [x] 2.5 `inspect.getsource` guard: both lanes call `_is_flat_lane_child`; neither
      re-implements it inline.
      → `test_both_reader_lanes_call_it_and_neither_reimplements_it` (source-level,
      per spec) + `test_the_shared_predicate_decides_both_halves_of_the_test`
      (behavioural triangulation, so the guard is not the only proof).
- [x] 2.6 (unplanned, from PR 1's "PR 2 should pin this" note) Empty-tag edge:
      a key like `"@value"` partitions to an empty tag and must stay a bare
      `<Setting key="@value"/>`, otherwise the file is not well-formed XML.
      → `test_a_key_with_an_empty_tag_part_is_treated_as_a_bare_key`

## Phase 3: Canary (PR 3)

- [x] 3.1 RED: `test_adaptive_retest_agent.py::test_preserves_unrelated_cfx_content` gains a 4-key `<Data>` (Symbol/Timeframe1/FromDate/ToDate); replace `any("EURUSD" in v ...)` with exact equality.
- [x] 3.2 GREEN: prove `apply_adaptive_mutations` already satisfies it; no behaviour change.

## Phase 4: Cleanup

- [x] 4.1 Sweep remaining `Setting@key` docstrings; confirm `test_templates.py:281-282` untouched and green.
      **Result: zero stale docstrings found** — PR 1 already corrected all of them. The only two
      surviving `Setting@key` mentions (`reader.py:444`, `writer.py:568`) both describe *legacy
      input*, not a produced form, and are accurate: PR 2 pins that path. `setting_children_only`
      has **no** occurrence in production code; the remaining hits are SDD planning artifacts
      describing its removal. Both guards re-verified byte-identical to `374a2cf`;
      `tests/phase4/test_templates.py` → 22 passed.
- [x] 4.2 Run `SQX_FORCE_MOCK=1 python3 -m pytest -q` (baseline `tests/cfx/` = 208 passed).
      PR 1 = 4120/9 · PR 2 = 4134/9 · **PR 3 = 4134/9, 0 failed, exit 0** — identical to PR 2,
      which is the required result: PR 3 changed no test *count* and no production code.
- [x] 4.3 (unplanned, orchestrator-flagged) Reconcile the `openspec/config.yaml` TDD drift:
      `testing.strict_tdd: false` and `rules.apply.tdd: false` both contradicted AGENTS.md's
      "Strict TDD is active". Corrected to `true`, along with the contradictory
      `testing.runner: none` and the empty `rules.apply.test_command` that would each have kept
      the drift in effect.