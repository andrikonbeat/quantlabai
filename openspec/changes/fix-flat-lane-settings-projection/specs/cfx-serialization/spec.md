# CFX Serialization — Delta for `fix-flat-lane-settings-projection`

> Proposal marks `cfx-serialization` modified, but no main spec exists (parent
> domain: `cfx-editor`). Archive creates `openspec/specs/cfx-serialization/spec.md`.

## Purpose

Define the invertible codec between the `.cfx` flat lane
(`SettingsSection.settings: dict[str, str]`) and its emitted XML, so
reader→writer→reader cycles are lossless and byte-stable.

## Requirements

### Requirement: Flat Lane Key Grammar (REQ-FLAT-1)

The reader MUST flatten a flat section from its **children** with an empty prefix; no key MAY carry the section tag. Keys keep the `Tag@attr` grammar. The writer MUST invert it: `Tag@attr` → `<Tag attr="value"/>`.
(Previously: the section element was the flatten root, so keys were section-prefixed and every key was re-emitted as `<Setting key= value=/>`.)

#### Scenario: No section-prefix pollution

- GIVEN `<WhatToBuild><Setting key="BuildType@value" value="genetic"/></WhatToBuild>`
- WHEN read into a `SettingsSection` and rewritten
- THEN the only key is `BuildType@value`; none contains `WhatToBuild.`

#### Scenario: Producer keys become findable after a read

- GIVEN `patcher` wrote `Timeframe1@value` and the file is read back
- WHEN the patcher's `k.startswith("Timeframe")` scan runs
- THEN it matches, instead of matching nothing

### Requirement: Setting Pair Coalescing (REQ-FLAT-2)

`Setting@key`/`Setting@value` MUST coalesce into one `<Setting key="K" value="V"/>`, never two entries keyed by those literal strings.
(Previously: a real `<Setting>` re-read emitted `<Setting key="Setting@key" value="EURUSD_H1"/>`.)

#### Scenario: Pair coalesces into a single element

- GIVEN settings `{"Setting@key": "EURUSD_H1", "Setting@value": "true"}`
- WHEN the section is written
- THEN exactly one `<Setting key="EURUSD_H1" value="true"/>` is emitted

#### Scenario: Coalesced output is byte-stable over four cycles

- GIVEN a `.cfx` holding a real `<Setting key="EURUSD_H1" value="true"/>`
- WHEN reader→writer runs four times
- THEN every output is byte-identical to the first

### Requirement: Lossless Flat Round-Trip (REQ-FLAT-3)

A `<Data>` section with N distinct `Tag@attr` keys MUST survive reader→writer→reader with all N intact. The writer MUST NOT encode a `Tag@attr` entry as `<Setting key= value=/>`.
(Previously: N `<Setting>` children collapsed to ONE pair at read time — dict overwrite — destroying symbol, timeframe and date range.)

#### Scenario: Five-key Data section survives one cycle

- GIVEN `<Data>` with `Symbol@symbol`, `Symbol@name`, `Timeframe1@value`, `FromDate@value`, `ToDate@value`
- WHEN the file is written, read, and written again
- THEN all five keys remain with unchanged values (previously: one pair)

#### Scenario: Data section survives an in-place rewrite

- GIVEN those five keys plus a `<RetesterData>` sibling
- WHEN one read→write cycle runs
- THEN all five keys are readable again and the sibling is unchanged

### Requirement: Data Typed-Lane Guard Preserved (REQ-FLAT-4)

Only true flat-key entries may enter the `<Data>` flat lane. Typed-lane elements (`IST`, `OutOfSample`, `Setups`/`Setup`, `DataRangeParts`, `RetesterDataConfig`) MUST NOT enter it or `data_range_parts.raw_xml`, so element count stays constant across cycles.
(Previously: the guard existed but was asserted against mangled keys.)

#### Scenario: Typed sub-ranges stay out of the flat lane

- GIVEN `<Data><Setting key="Symbol@symbol" value="EURUSD"/><IST value="0.5"/><OutOfSample showGraph="false"/></Data>`
- WHEN read
- THEN `data.settings == {"Symbol@symbol": "EURUSD"}` and no `IST`/`OutOfSample` key

#### Scenario: Nested Setups subtree stays in the passthrough lane

- GIVEN `<Data><Setups><Setup dateFrom="2003.5.5"/></Setups></Data>`
- WHEN read
- THEN `data.settings == {}` and `raw_xml` contains `<Setups>`

#### Scenario: Second cycle does not grow the Data section

- GIVEN a `<Data>` holding one flat entry, one typed sub-range and `<Conditions>`
- WHEN a second read→write cycle runs
- THEN the `<Data>` child signature equals the first cycle's

#### Scenario: One shared predicate serves both `<Data>` lanes

- GIVEN `_is_flat_lane_child` is the single flat-lane predicate
- WHEN a `<Data>` carrying one flat child, one typed sub-range and one nested subtree is read
- THEN both the admit path (`_parse_settings_element`) and the strip path (`_parse_data_range_parts`) call `_is_flat_lane_child`
- AND neither body re-implements the leaf/exclude test inline, so a duplicated predicate fails this scenario

### Requirement: Databank Pairing in Retester Templates (REQ-FLAT-5)

`build_retester_cfx` MUST preserve every requested databank across one read→write cycle.
(Previously: `GBPUSD_H1` overwrote `EURUSD_H1`, both becoming `Setting@key`/`Setting@value`.)

#### Scenario: Two databanks survive one cycle

- GIVEN `build_retester_cfx(databanks=['EURUSD_H1','GBPUSD_H1'])` written, read, rewritten
- WHEN the emitted `<Data>` children are inspected
- THEN both databank `<Setting>` elements are present (previously: `EURUSD_H1` lost)

### Requirement: Emitted Dialect for Bare Flat Keys (REQ-FLAT-6)

A flat key without `@` (`templates.py`'s `{'EURUSD_H1': 'true'}`, `translator.py`'s `{db: 'true'}`) MUST be emitted as `<Setting key="K" value="V"/>`. **Decision:** bare keys keep the `<Setting>` form; only `Tag@attr` keys change form.
(Previously: undecided, which blocked the expectation updates in `tests/phase4/test_templates.py:281-282` and `test_translator_advanced_rankings.py:187,241`.)

> The decision is now made, so `test_templates.py:281-282` is **not** churn: bare databank keys keep the `<Setting>` form and those assertions stay green untouched.

#### Scenario: Bare keys keep `Setting`; `Tag@attr` keys do not

- GIVEN a translated `<Rankings>` holding `Criterion1@metric/@operator/@value`, a translated `<Data>` holding `Symbol@symbol`, `Symbol@name`, `Timeframe1@value`, and a retester `<Data>` holding bare `EURUSD_H1`/`GBPUSD_H1`
- WHEN the child tags of each section are listed
- THEN the retester `<Data>` tags are `["Setting", "Setting"]`, the translated `<Rankings>` is `["Criterion1"]`, and the translated `<Data>` is `["Symbol", "Timeframe1"]`
- AND no `Tag@attr` key is emitted as a `Setting` element

#### Scenario: Setting elements are addressable by key

- GIVEN `<Data>` from `build_retester_cfx(databanks=['EURUSD_H1','GBPUSD_H1'])`
- WHEN `data.find("Setting[@key='GBPUSD_H1']").get("value")` is evaluated
- THEN the result is `"true"`

### Requirement: Adaptive-Retest In-Place Safety (REQ-FLAT-7)

`apply_adaptive_mutations` MUST leave market symbol, timeframe and date range semantically unchanged after rewriting the same `.cfx` in place.
(Previously: the canary asserted only `any("EURUSD" in v ...)`, which passes for a single-key section and cannot detect mangling.)

#### Scenario: Exact key/value assertion after in-place rewrite

- GIVEN `<Data>` holds `Symbol@symbol=EURUSD`, `Timeframe1@value=H1`, `FromDate@value=2015.01.01`, `ToDate@value=2024.12.31`
- WHEN `apply_adaptive_mutations(cfx, RetestMode.AUTOMATIC_RETEST)` runs on that same path
- THEN re-reading yields those four exact keys/values and no `Setting@key`/`Setting@value` key

## Test Mapping

| Requirement | Test file | Action |
|-------------|-----------|--------|
| REQ-FLAT-1,2,3,5 | `tests/cfx/test_flat_lane_round_trip.py` | create |
| REQ-FLAT-4 guard | same new file | create — shared-predicate scenario |
| REQ-FLAT-4 | `tests/cfx/test_reader_advanced_rankings.py` (4 tests below) | modify expectations, keep guards |
| REQ-FLAT-6 | same new file; `tests/phase4/test_translator_advanced_rankings.py:187,226-231,241-247` | create; modify tags/keys |
| REQ-FLAT-7 | `tests/agents/test_adaptive_retest_agent.py::test_preserves_unrelated_cfx_content` | tighten canary to exact equality |
| REQ-FLAT-1 | `tests/cfx/test_writer_section_merge.py:85-91,116` | modify — `Criterion1@*` now groups into `<Criterion1>` |
| REQ-FLAT-6 | `tests/cfx/test_mixed_rankings_compatibility.py:296` | modify — same `Criterion1` grouping |
| regression | `tests/cfx/test_mixed_rankings_compatibility.py:22-28,277-282`, `tests/phase4/test_project_builder_golden_rankings.py:283-287` | rewrite stale docstrings |
| regression guard | `tests/phase4/test_templates.py:281-282`, `tests/cfx/test_writer_section_merge.py:147,168` | **untouched** — MUST stay green |

`tests/cfx/test_reader_advanced_rankings.py` targets:
`test_flat_lane_holds_only_setting_children`, `test_nested_elements_do_not_leak_into_the_flat_lane`,
`test_second_cycle_does_not_grow_the_data_section`, `test_flat_settings_are_not_duplicated_into_the_typed_lane`.

Baseline `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/` = 208 passed; MUST stay green.