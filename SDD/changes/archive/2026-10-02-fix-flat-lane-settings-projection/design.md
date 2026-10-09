# Design: Fix flat lane SettingsSection projection

## Technical Approach

Make the flat lane a bijection by rewriting both halves around one grammar.

**Read** (`reader._parse_settings_element`): flatten from the section's *children*
with `prefix=""`, not from the section element. A child enters the flat lane only if
`_is_flat_lane_child(child, exclude)` — a **leaf** whose tag no sibling lane claims.
A leaf `<Setting key=… value=…/>` becomes **one** entry `settings[key] = value`; any
other leaf reuses `_flatten_element` unchanged → `Tag@attr`.

**Write** (`writer._append_settings_section`): iterate `settings` in dict order. A key
without `@` emits its own `<Setting key="K" value="V"/>` (REQ-FLAT-6). Keys with `@`
split once on `@` and are **grouped by tag**: one `<Tag attr="v" …/>` per tag, tags in
first-appearance order, attributes likewise. Grouping is what coalesces
`Setting@key`/`Setting@value` into a single `<Setting key= value=/>` (REQ-FLAT-2) and
keeps `Symbol@symbol` + `Symbol@name` as one `<Symbol symbol= name=/>` rather than
two half-elements.

**`<Data>` guard**: `_is_flat_lane_child` is the *single* predicate, called by
`_parse_settings_element` (admit) **and** `_parse_data_range_parts` (strip).
Re-implementing that rule in two places is how lane duplication returns. `<Data>`
passes `DATA_RANGE_PART_TAGS | _DATA_PASSTHROUGH_TAGS`; other flat sections pass
`frozenset()`.

A standalone harness confirmed byte-stability from cycle 1 — five-key `<Data>`, typed
exclusion, nested `<Setups>`, two databanks, legacy mangled `<Setting>`, `Criterion1`
— with no growth and no duplication.

### Legacy keys: tolerant on write, never produced on read

The reader does **not** special-case the literal names `Setting@key`/`Setting@value`;
it applies one structural rule to any `<Setting key= value=/>`. After a read the two
halves are indistinguishable from two legitimate bare keys, so name-matching is
undecidable and would corrupt valid data. The pairing survives in the *dict*, so
tolerance belongs on write: grouping rejoins the literals into
`<Setting key="EURUSD_H1" value="true"/>` (REQ-FLAT-2) from hand-built fixtures,
in-memory archives, or older QuantLab output. Legacy *files* are not repaired
losslessly — there the pair exists only as attribute values — but converge to one
stable form after a single cycle.

## Architecture Decisions

| # | Decision | Alternatives | Rationale |
|---|----------|--------------|-----------|
| 1 | Reader + writer change atomically in one work unit | Writer first, reader later | Either half alone ships an inversion: writer-only still collapses N elements on read; reader-only yields keys nothing consumes. |
| 2 | Keep `SettingsSection.settings: dict[str, str]` | Approach 3 — ordered `elements` list, 47 call sites | Grouping-by-tag is injective on the key→element map, so the dict is already lossless for every current producer. |
| 3 | Group `Tag@attr` keys by tag into one element | One element per key | Otherwise `Criterion1@metric/@operator/@value` becomes three sibling `<Criterion1>` elements — model-stable, but XML SQX reads as three criteria. |
| 4 | Bare keys keep `<Setting key= value=/>` (REQ-FLAT-6) | Convert bare keys to `Tag@attr` | `test_templates.py:281-282` and `test_writer_section_merge.py:147,168` stay green untouched. |
| 5 | Guard is a deny-list of lane-owned tags, shared by both reader lanes | Allow-list of known flat tags | `DataRangeParts.from_xml` is passthrough-by-default; an allow-list would silently drop a producer's new flat key. |

`SettingsSection.settings` keeps its type; only its docstring changes.

## Data Flow

    <Data>: Symbol@… Timeframe1@… IST  Setups
      │ reader: _is_flat_lane_child (leaf ∧ ∉ exclude)
      ├─ admit ─► settings: dict ─────┐ lanes disjoint,
      └─ strip ─► DataRangeParts ─────┘ one predicate
      ▼ writer: group by tag ─► <Symbol symbol= name=/>
      bare key ──────────────────► <Setting key= value=/>
      _append_data_range_parts appends typed children after flat ones

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/cfx/models.py` | Modify | Add `DATA_RANGE_PART_TAGS` derived from `_DATA_RANGE_PART_ELEMENTS`; state the `settings` grammar. |
| `sdk/quantlab/cfx/reader.py` | Modify | Add `_is_flat_lane_child` + `_DATA_PASSTHROUGH_TAGS`; iterate children in `_parse_settings_element`; reuse the predicate in `_parse_data_range_parts`. |
| `sdk/quantlab/cfx/writer.py` | Modify | `_append_settings_section` de-flattens + groups; fix the `_append_merged_complex_section` docstring (children are no longer all `<Setting>`). |
| `tests/cfx/test_flat_lane_round_trip.py` | Create | REQ-FLAT-1/2/3/5 codec and byte-stability tests. |
| `tests/cfx/test_reader_advanced_rankings.py` | Modify | 4 pinned assertions; both regression guards kept. |
| `tests/cfx/test_mixed_rankings_compatibility.py` | Modify | Docstring 22-28; assertions 277-282, 296. |
| `tests/cfx/test_writer_section_merge.py` | Modify | Assertions 85-91, 116. Lines 147/168 stay green. |
| `tests/phase4/test_translator_advanced_rankings.py` | Modify | Assertions 187, 226-231, 241-247. |
| `tests/phase4/test_project_builder_golden_rankings.py` | Modify | Docstring 283-287. |
| `tests/agents/test_adaptive_retest_agent.py` | Modify | Tighten the canary. |

No producer changes: patcher, translator, templates and risk_mapper already emit
`Tag@attr` or bare keys — exactly the grammar the writer now renders.

## Interfaces / Contracts

```python
# models.py — public constant; avoids importing a private name cross-module
DATA_RANGE_PART_TAGS: frozenset[str] = frozenset(el for _, el in _DATA_RANGE_PART_ELEMENTS)

# reader.py
_DATA_PASSTHROUGH_TAGS: frozenset[str] = frozenset({"Setups", "OutOfSample"})

def _is_flat_lane_child(child: Element, exclude: frozenset[str]) -> bool:
    """True when child belongs to the flat lane (leaf, unclaimed by a sibling lane)."""

def _parse_settings_element(el: Element, *, exclude_tags: frozenset[str] = frozenset()) -> SettingsSection:
    """Replaces `setting_children_only: bool`; <Data> passes the exclusion set."""

# unchanged signatures
def _flatten_element(el, acc: dict[str, str], prefix: str) -> None
def _append_settings_section(parent, tag, section) -> Element | None   # body rewritten
```

`setting_children_only` is removed, not kept: both call sites need the
typed/passthrough split, which a bool cannot express.

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Codec inversion | New `test_flat_lane_round_trip.py`: no section prefix; five-key `<Data>` survives; legacy pair coalesces; two databanks survive; 4-cycle byte identity. |
| Regression | Guards stay green | `test_flat_lane_holds_only_setting_children`, `test_nested_elements_do_not_leak_into_the_flat_lane` — intent preserved, expected keys change. |
| Integration | `<Data>` disjointness | `test_second_cycle_does_not_grow_the_data_section`; `test_flat_settings_are_not_duplicated_into_the_typed_lane` (`{"Setting@key",…}` → `{"Symbol@symbol": "EURUSD"}`). |
| Integration | Emitted dialect | Phase4 + writer-merge tags updated; `test_templates.py:281-282` and `test_writer_section_merge.py:147,168` must remain untouched and green. |

Canary — replace `tests/agents/test_adaptive_retest_agent.py:409-413`.
`any("EURUSD" in v for v in …values())` passes on any single-key section and cannot
detect mangling. Replace with exact equality:

```python
assert task.data.settings == {"Symbol@symbol": "EURUSD"}
assert task.what_to_build.settings == {"StrategyType@type": "simple"}
assert task.notes.settings == {"Note@text": "keep me"}
```

Gate: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/` (208 passed).

## Risks

| Risk | Mitigation |
|------|------------|
| `<Data>` guard regression — a second, drifting copy of the predicate reintroduces duplication | One predicate, one call site each for admit/strip; `test_second_cycle_does_not_grow_the_data_section` is a hard guard. |
| Emitted-XML churn beyond the spec's list | `Criterion` grouping also hits `test_writer_section_merge.py:116` and `test_mixed_rankings_compatibility.py:296`, which the spec does not name; both are in the File Changes table. |
| Dict collapse | Eliminated by construction — grouping is injective on distinct keys. Two same-tag/same-attr entries remain unrepresentable, but such keys already overwrote each other on the way into the dict. |
| Ordering stability | Dict insertion order drives emission; tags use first-appearance order. Verified byte-stable from cycle 1, including the non-contiguous-tag case. |
| Concurrency | None introduced; `adaptive_retest_agent` still rewrites one archive in place, now without corrupting it. |
| Deny-list drift as the typed lane grows | New typed tags must be added to `DATA_RANGE_PART_TAGS`; `from_xml` parking them in `raw_xml` keeps that the single source of truth. |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file
classification, or process-integration boundary.

## Migration / Rollout

No data migration. Single work unit (reader + writer + tests together), revertible by
restoring `_parse_settings_element`, `_append_settings_section` and the tests. No
feature flag: a half-fixed codec is unreadable in both directions and must never ship.

## Open Questions

- [x] **Spec amendment required.** REQ-FLAT-6's first scenario asserts translator
      `<Rankings>`/`<Data>` tags are `["Setting","Setting","Setting"]`, contradicting
      REQ-FLAT-1 — translator output carries `Criterion1@…` and `Symbol@…`, so tags
      become `["Criterion1"]` and `["Symbol","Timeframe1"]`. REQ-FLAT-6's *normative
      text* is right; the scenario must be rescoped to the retester template's bare
      `{db: "true"}` keys, and `test_templates.py:281-282` reclassified from
      "modified" to "regression guard". Tasks must not implement it literally.
      **(RESOLVED: spec corrected in the gatekeeper re-run — the scenario now asserts
      the correct tags and the reclassification note is in the spec.)**
- [ ] Recorded, out of scope: `_SETTINGS_SECTIONS` omits `Rankings` and
      `CrossChecks`, so the reader never populates those flat lanes. Pre-existing
      asymmetry, untouched here.