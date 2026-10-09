# Proposal: Advanced Ranking Filters and Data Range Parts

## Intent

QuantLab can currently emit simple ranking conditions, but SQX's real Retester CFX schema supports advanced nested `<Rankings><Conditions><Condition use="..."><Column-Value .../></Condition></Conditions></Rankings>` blocks with attributes like `resultType`, `sampleType`, `direction`, `pctRatio`, `confidenceLevel`, `market`, `plType`, and `subresult`. Without typed models for these, QuantLab cannot express or write advanced ranking custom filters, nor can it model Data range parts as structured config instead of raw passthrough. This change closes that gap so generated CFXs match the verified SQX 144/2953 schema.

## Scope

### In Scope
- Advanced ranking filter models: nested `Condition` → `ColumnValue` Pydantic structures mirroring real CFX attributes (`resultType`, `sampleType`, `direction`, `pctRatio`, `confidenceLevel`, `market`, `plType`, `subresult`, `class`, `name`).
- New patcher instructions for advanced ranking filters (add/update advanced conditions, direction, sample selector, percent ratio, result unit).
- DSL additions for advanced ranking filter expression.
- Translator mapping from DSL to advanced ranking models.
- Data range parts modeling: typed bridge for `<Data>` sub-ranges/configurable `raw_xml`, enabling future typed fields while preserving unknown ranges.
- Tests and at least one golden/round-trip fixture from real Retester CFX proving advanced filters emit correctly.

### Out of Scope
- Removing or replacing the existing simple `AddRankingConditionInstruction`.
- Building a GUI for filter selection.
- Implementing SQX execution/runner behavior changes.

## Capabilities

> This section is the CONTRACT between proposal and specs phases.

### New Capabilities
- `advanced-ranking-filters`: Typed models and patcher support for nested `<Rankings><Conditions>` structures with `Column-Value` attributes.
- `data-range-parts`: Typed/configurable `raw_xml` bridge for Data range parts, preserving extensibility for future typed fields.

### Modified Capabilities
- None (simple ranking conditions remain untouched).

## Approach

Follow the existing Phase 4 complex-section pattern already used by `RankingsConfig`, `CrossChecksConfig`, and `RetesterDataConfig`:
1. Add new typed models in `sdk/quantlab/cfx/models.py` for advanced ranking conditions and data range parts.
2. Extend `CfxPatcher` with validators/appliers for the new instructions.
3. Update `CfxWriter` and `DOM` helpers to serialise nested conditions and data sub-ranges.
4. Extend DSL models and the translator mapping in `sdk/quantlab/translate/translator.py`.
5. Add phase4 template/renderer support so generated projects emit the new structures.
6. Add unit tests, patcher tests, and at least one golden CFX fixture extracted from the real Retester sample.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/cfx/models.py` | New/Modified | Advanced ranking condition models; data range parts bridge |
| `sdk/quantlab/cfx/patcher.py` | New/Modified | Validators/appliers for advanced ranking instructions |
| `sdk/quantlab/cfx/writer.py` | Modified | Serialise nested `<Conditions>` blocks |
| `sdk/quantlab/cfx/dom.py` | Modified | DOM helpers for advanced condition elements |
| `sdk/quantlab/translate/translator.py` | Modified | DSL → advanced ranking mapping |
| `sdk/quantlab/dsl/models.py` | Modified | DSL fields for advanced ranking filters |
| `sdk/quantlab/phase4/templates.py` | Modified | Template placeholders for advanced filters |
| `sdk/quantlab/customproject/renderers.py` | Modified | Render advanced filters in multi-task XML |
| `tests/cfx/test_patcher.py` | New | Advanced ranking patcher tests |
| `tests/phase4/test_project_builder.py` | New | Project builder golden tests |
| `tests/cfx/fixtures/...` | New | Real CFX golden with advanced filters |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| CFX enum/version drift for `sampleType`, `resultType`, `pctRatio` | Medium | Model as open strings with enums for known values; fixture-based regression tests |
| Test coverage gaps for nested XML | Low | Add round-trip golden tests using real Retester CFX |
| Agent prompt complexity when choosing options | Medium | Provide sensible defaults and validation constraints in DSL/patcher |

## Rollback Plan

- Simple ranking conditions remain untouched and continue to work.
- New advanced filters are additive: disabling the new instruction path keeps existing behavior unchanged.
- If typed models cause schema mismatch, fall back to `raw_xml` bridge for the affected section without removing simple paths.

## Dependencies

- Verified SQX 144/2953 sample CFX files in `assets/SQX_144_2953_linux_20260601/` as golden references.

## Success Criteria

- [ ] QuantLab can emit a `<Rankings>` block with advanced `<Conditions>` matching the real Retester CFX schema.
- [ ] Unit/golden tests pass for at least one main/crosscheck combination.
- [ ] DSL/translator round-trip preserves advanced fields.
