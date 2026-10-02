# Proposal: Fix flat lane SettingsSection projection

## Intent

The flat `SettingsSection.settings` projection is write-only: QuantLab writes `Tag@attr` keys, but reading them back produces keys no producer or consumer recognises, causing silent data loss. The adaptive retest path (`adaptive_retest_agent.apply_adaptive_mutations`) reads and rewrites the same `.cfx` in place, so each retest cycle destroys market symbol, timeframe and date range data in the file under test. This is a correctness defect, not deferred cleanup.

## Scope

### In Scope
- **Reader de-flattening and prefix removal** (Approach 2 from exploration): stop flattening from the section element as root for non-`Data` sections; flatten from section children with `prefix=""` to eliminate section-prefix pollution.
- **Writer de-flattening with coalescing**: when emitting flat sections, de-flatten `Tag@attr` keys back to `<Tag attr="value"/>` elements. Special-case `Setting@key`/`Setting@value` pairs to emit a single `<Setting key="..." value="..."/>`.
- **`<Data>` guard reconciliation**: handle the `setting_children_only=True` case (introduced to prevent typed-lane duplication) so the fix doesn't re-introduce the lane-duplication growth bug.
- **Rewrite the 6 pinning tests** that currently assert the buggy mangled keys (e.g. `Setting@key`/`Setting@value` in flat dicts). These tests must be updated to match the correct invertible codec.
- **Tighten the adaptive-retest canary** in `tests/agents/test_adaptive_retest_agent.py` to assert more precisely that databank/symbol data survives read→write cycles.
- **Dialect decision for templates/translators**: explicitly choose the emitted XML form for cases like `templates.py` bare `{db:'true'}` keys; update affected expectations if needed.
- **Risk guard tests**: keep `test_flat_lane_holds_only_setting_children` and `test_nested_elements_do_not_leak_into_the_flat_lane` green by preserving their intent.

### Out of Scope
- Changing real-SQX `<Setting>` handling beyond what's required to make QuantLab's own output round-trip.
- Redesigning typed lanes (`RetesterDataConfig`, `CrossChecksConfig`, etc.).
- Introducing a new major model redesign across 47 call sites (Approach 3) unless a specific fixture proves repeated same-tag `<Setting>` elements must round-trip losslessly.
- Adding new flat sections or changing their semantics.

## Capabilities

> This section is the CONTRACT between proposal and specs phases.

### New Capabilities
- None

### Modified Capabilities
- **cfx-serialization**: Fix the flat-lane SettingsSection codec so reader→writer→reader cycles preserve all flat entries without prefix pollution or pair mangling.

## Approach

- **Reader (`sdk/quantlab/cfx/reader.py:403-462`)**: For non-`Data` flat sections, flatten starting from children with empty prefix (killing `SectionTag.` prefix). For `Data`, preserve existing semantics while allowing correct de-flattened children when the guard is reconciled. Special handling for `Setting@key`/`Setting@value` pair reconstruction if needed during the transition; prefer fixing the write-side to emit canonical form.
- **Writer (`sdk/quantlab/cfx/writer.py:549-565`)**: When writing flat sections, iterate `settings` dict and de-flatten keys: if both `Setting@key` and `Setting@value` pairs exist for the same logical entry, coalesce into a single `<Setting key=K value=V/>`. For `Tag@attr` keys, emit `<Tag attr="value"/>`. Avoid creating `Setting@*` keys on read.
- **`<Data>` guard reconciliation**: Explicitly test the interaction between `setting_children_only=True` and de-flattened elements; preserve the regression guards `test_flat_lane_holds_only_setting_children` and `test_nested_elements_do_not_leak_into_the_flat_lane`. Only allow de-flattened elements into the flat lane when they are true flat-key entries, never typed-lane elements.
- **Producers unchanged**: Patcher/translator/risk_mapper/templates already produce `Tag@attr` keys; this fix makes the reader/writer symmetric without requiring producer migration.
- **Test migration**: Update the 6 pinning tests to the correct codec behavior. Update XML expectation churn in `tests/phase4/test_templates.py:281-282` and `tests/phase4/test_translator_advanced_rankings.py:180-241` only after the dialect decision is explicit.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/cfx/reader.py:403-462` | Modified | `_parse_settings_element`, `_flatten_element` — stop prefixing from section root; fix flat-lane parsing. |
| `sdk/quantlab/cfx/writer.py:549-565` | Modified | `_append_settings_section` — de-flatten `Tag@attr` keys, coalesce `Setting@key`/`Setting@value` pairs. |
| `sdk/quantlab/cfx/models.py:35-39` | Modified | `SettingsSection.settings` semantics clarified; no structural model expansion unless needed. |
| `sdk/quantlab/cfx/patcher.py` | Modified (minimal) | Read-side assumptions validated (no change to write keys if not necessary). |
| `sdk/quantlab/translate/translator.py` | Modified (minimal) | Verify flat keys round-trip correctly. |
| `sdk/quantlab/phase4/templates.py` | Modified (minimal) | Dialect for bare `{db:'true'}` keys clarified. |
| `sdk/quantlab/agents/adaptive_retest_agent.py` | Modified (canary/tests) | Tighten test assertions to prevent silent loss; no behavior change required if fix works. |
| `tests/cfx/test_reader_advanced_rankings.py` | Modified | Update tests that pin mangled keys; preserve regression guard tests. |
| `tests/cfx/test_mixed_rankings_compatibility.py` | Modified | Update to correct codec behavior. |
| `tests/phase4/test_project_builder_golden_rankings.py` | Modified | Update expectations as needed. |
| `tests/phase4/test_templates.py`, `tests/phase4/test_translator_advanced_rankings.py` | Modified | Update XML tag expectations per dialect decision. |
| `tests/agents/test_adaptive_retest_agent.py` | Modified | Tighten canary to catch in-place data loss. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| **`<Data>` guard regression** — relaxing `setting_children_only=True` reintroduces typed-lane duplication growth. Affects `test_flat_lane_holds_only_setting_children` and `test_nested_elements_do_not_leak_into_the_flat_lane`. | Medium | Treat these two as hard regression guards in every change; add explicit tests for `Data` de-flatten case; only de-flatten true flat keys. |
| **XML churn** — expectations in `test_templates.py:281-282` and `test_translator_advanced_rankings.py:180-241` assert `['Setting','Setting','Setting']`. | Medium | Make dialect decision explicit early; update tests together; document chosen emitted form in spec. |
| **Production in-place destruction persists** until fix lands (adaptive_retest rewrites same .cfx every cycle). | Low (if fixed) | This is the reason to treat as correctness incident; verify with targeted round-trip tests before broader suite. |
| **Breaking other consumers** that might depend on section prefix. | Low | Prefix pollution is undocumented and prevents reading own output; patcher lookups (e.g. `k.startswith('Timeframe')`) currently miss prefixed keys — fix aligns reader with producer intent. |
| **Dict key uniqueness** limits lossless round-trip for repeated same-tag `<Setting>` elements. | Low | Current model (`dict[str,str]`) cannot represent N duplicates; Approach 2 is correct for existing producers. Escalate to Approach 3 only if fixtures require it. |

## Rollback Plan

- Revert changes in `reader.py` and `writer.py` to restore previous flatten/emit behavior.
- Revert affected test changes.
- Adaptive-retest canary change is additive/assertion tightening; can be reverted independently without breaking behavior.
- Flat sections remain functionally equivalent for write paths that don't rely on read-back symmetry; rollback restores known (defective) read behavior.

## Dependencies

- None external. Uses existing fixtures and tests.

## Success Criteria

- [ ] Reader→writer→reader cycles preserve all flat keys for `Data` sections with multiple keys (no collapse to single pair).
- [ ] Non-`Data` flat sections round-trip without section prefix (`WhatToBuild.Setting@key` does not appear).
- [ ] `adaptive_retest_agent` round-trips databanks/symbols without loss across cycles.
- [ ] All regression guards (`test_flat_lane_holds_only_setting_children`, `test_nested_elements_do_not_leak_into_the_flat_lane`) remain green.
- [ ] Baseline: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/` remains green after fix (208 passed baseline).
- [ ] Targeted tests: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/test_reader_advanced_rankings.py tests/cfx/test_mixed_rankings_compatibility.py tests/agents/test_adaptive_retest_agent.py` pass with updated expectations.

## Priority

**Correctness incident — high priority.** The in-place data destruction in `adaptive_retest_agent` affects every retest cycle. The fix addresses the root codec inversion (writer/reader disagree) and prevents silent corruption of generated `.cfx` files.
