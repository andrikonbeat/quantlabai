# Proposal: typed-crosschecks-models

## Intent

CrossChecks handling in the QuantLab SDK CFX module currently relies on `CrossChecksConfig` with only a `raw_xml` passthrough field. There is no typed model abstraction for the CrossChecks XML section, which forces downstream consumers (`adaptive_retest_agent.py`, `project_builder.py`) to parse XML via regex and string manipulation. This change introduces typed Pydantic models for the two production CrossChecks dialects to eliminate regex parsing, improve IDE support, and reduce regression risk.

## Scope

### In Scope
- Typed Pydantic models for Generic (flat MonteCarlo/WalkForward/ConfidenceLevel) and AutomaticRetest (deep nested) CrossChecks dialects
- Update `CfxReader` to populate typed CrossChecks fields with `raw_xml` fallback for unknown elements
- Update `CfxWriter` to serialize typed CrossChecks fields while preserving `raw_xml` extras
- Update `CfxPatcher` to validate and modify typed CrossChecks fields
- Refactor `adaptive_retest_agent.py` and `project_builder.py` to consume typed fields instead of regex
- Reader/writer/patcher and consumer tests for both dialects

### Out of Scope
- Breaking removal of `raw_xml` fallback
- Typed models for other CFX sections beyond CrossChecks
- UI/API surface changes unrelated to CFX module

## Capabilities

> This section is the CONTRACT between proposal and specs phases.
> The sdd-spec agent reads this to know exactly which spec files to create or update.
> Research `openspec/specs/` before filling this in.

### New Capabilities
- `crosschecks-models`: Typed Pydantic models for Generic and AutomaticRetest CrossChecks dialects with raw_xml fallback preservation

### Modified Capabilities
- `cfx-editor`: CrossChecks section requirements change from raw_xml-only passthrough to typed model population with fallback

## Approach

Adopt **Dual-mode typed models with raw_xml fallback** (recommended from exploration). Introduce typed dataclasses for Generic and AutomaticRetest dialects. Reader populates typed fields when possible and preserves unknown XML in `raw_xml`. Writer serializes typed fields and merges `raw_xml` extras. This maintains backward compatibility while eliminating regex parsing in downstream consumers.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/cfx/models.py` | New/Modified | Add CrossChecks typed models |
| `sdk/quantlab/cfx/reader.py` | Modified | Populate typed CrossChecks fields |
| `sdk/quantlab/cfx/writer.py` | Modified | Serialize typed CrossChecks fields |
| `sdk/quantlab/cfx/patcher.py` | Modified | Validate typed CrossChecks modifications |
| `agents/adaptive_retest_agent.py` | Modified | Replace regex with typed field access |
| `sqx/project_builder.py` | Modified | Replace regex mappings with typed fields |
| `tests/cfx/` | Modified | Reader/writer/patcher tests for both dialects |
| `tests/agents/` | Modified | adaptive_retest_agent tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Regex consumers break if field names shift | Medium | Keep raw_xml fallback; refactor consumers incrementally |
| Unknown XML elements lost during round-trip | Medium | Preserve raw_xml extras in writer; round-trip tests |
| Writer serialization order affects XML diffs | Low | Match original element order in serialization |
| Incomplete dialect coverage | Medium | Test both Generic and AutomaticRetest goldens before release |

## Rollback Plan

If typed models cause regressions, revert `reader.py`, `writer.py`, and `patcher.py` to raw_xml-only passthrough behavior. The `raw_xml` field remains intact throughout, so consumers can fall back immediately. No schema migration is required because `raw_xml` is preserved.

## Dependencies

- Existing Pydantic model infrastructure in `sdk/quantlab/cfx/models.py`

## Success Criteria

- [ ] Generic dialect round-trips through reader/writer preserving typed fields and raw_xml extras
- [ ] AutomaticRetest dialect round-trips through reader/writer preserving typed fields and raw_xml extras
- [ ] `adaptive_retest_agent.py` and `project_builder.py` no longer use regex on raw_xml for known fields
- [ ] All existing CFX tests pass
- [ ] New tests cover both dialects and unknown-element fallback
