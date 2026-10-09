# Design: Typed CrossChecks Models

## Technical Approach

Introduce typed Pydantic models for the two production CrossChecks dialects (Generic and AutomaticRetest) while preserving `raw_xml` as a backward-compatible fallback. The reader detects the dialect from XML structure, populates typed fields, and preserves unknown elements in `raw_xml`. The writer serializes typed fields and merges `raw_xml` extras. Downstream consumers (`adaptive_retest_agent.py`, `project_builder.py`) replace regex parsing with direct typed field access.

## Architecture Decisions

### Decision: Dual dialect models with discriminator

**Choice**: Add `CrossChecksGeneric`, `CrossChecksAutomaticRetest`, and nested sub-models. Update `CrossChecksConfig` to hold `dialect: str`, `generic`, `automatic_retest`, and `raw_xml`.

**Alternatives considered**: Full typed replacement (breaking), regex-only hardening (fragile).

**Rationale**: Matches the existing `CrossChecksConfig(raw_xml=...)` pattern used across reader/writer/patcher/consumers. Keeps backward compatibility because `raw_xml` remains intact. Dialect discriminator lets consumers branch safely.

### Decision: Reader populates typed fields with raw_xml fallback

**Choice**: In `_make_complex_section` and `_parse_settings_element_tree`, detect CrossChecks dialect by inspecting child tags (`MonteCarlo`/`WalkForward` → Generic; `RetestWithHigherPrecision`/`MonteCarloRetest` → AutomaticRetest). Populate typed model; stash unrecognized XML in `raw_xml`.

**Alternatives considered**: Parse everything into raw_xml only, or fully parse all elements.

**Rationale**: Unknown SQX elements survive round-trip via `raw_xml`. Typed fields cover the known 95% of production usage. Matches existing `_make_complex_section` pattern.

### Decision: Writer serializes typed fields then merges raw_xml extras

**Choice**: `_serialise_task` emits typed CrossChecks XML (Generic or AutomaticRetest) from the typed model, then appends `raw_xml` extras as unknown child elements.

**Alternatives considered**: Replace raw_xml entirely, or append typed after raw_xml.

**Rationale**: Preserves order-independent round-trip. Extra unknown elements are not lost. Matches existing `_append_complex_section` passthrough pattern.

### Decision: Patcher validates and mutates typed CrossChecks

**Choice**: `_apply_set_crosschecks` sets `generic` typed fields instead of replacing `raw_xml`. Validation already checks ranges; extend to validate typed model constraints.

**Alternatives considered**: Continue replacing raw_xml, add new instruction type.

**Rationale**: `SetCrossChecksInstruction` already carries the Generic dialect fields. Keeping the same instruction type avoids breaking the patcher API. AutomaticRetest gets a new instruction or direct model assignment.

### Decision: Consumer refactoring (adaptive_retest_agent, project_builder)

**Choice**: Replace regex on `raw_xml` with direct attribute access on typed models. Fall back to `raw_xml` regex only for fields not yet modeled.

**Alternatives considered**: Leave consumers unchanged.

**Rationale**: Eliminates the fragility that motivated this change. `adaptive_retest_agent.py` reads `cross_checks_section.generic.mc_enabled` instead of regex. `project_builder.py` reads `cross_checks_section.generic.wf_cycles` instead of regex. Unknown fields still available via `raw_xml`.

## Data Flow

    CFX XML (ZIP)
        │
        ▼
    CfxReader.read()
        │  _make_complex_section detects dialect
        │  populates CrossChecksConfig(generic=... | automatic_retest=..., raw_xml=...)
        ▼
    CfxArchive / BuildTask
        │
        ├──▶ CfxPatcher.apply(SetCrossChecksInstruction)  → mutates generic fields
        │
        ├──▶ adaptive_retest_agent.py                     → reads generic.mc_enabled
        │                                                  → writes automatic_retest
        │
        └──▶ CfxWriter._serialise_task()
                   │  emits typed XML from generic/automatic_retest
                   │  merges raw_xml extras
                   ▼
             CFX XML (ZIP)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/cfx/models.py` | Modify | Add `CrossChecksGeneric`, `CrossChecksAutomaticRetest`, nested sub-models, update `CrossChecksConfig` |
| `sdk/quantlab/cfx/reader.py` | Modify | Detect dialect in `_make_complex_section`, populate typed fields, preserve extras in `raw_xml` |
| `sdk/quantlab/cfx/writer.py` | Modify | Serialize typed CrossChecks fields, merge `raw_xml` extras |
| `sdk/quantlab/cfx/patcher.py` | Modify | `_apply_set_crosschecks` mutates typed fields instead of replacing `raw_xml` |
| `sdk/quantlab/agents/adaptive_retest_agent.py` | Modify | Replace regex extractors with typed field access; add typed AutomaticRetest builder |
| `sdk/quantlab/sqx/project_builder.py` | Modify | Replace CrossChecks regex mappings with typed field reads |
| `tests/cfx/test_crosschecks_models.py` | Create | Unit tests for both dialects, round-trip, unknown-element fallback |
| `tests/cfx/test_reader_crosschecks.py` | Create | Reader integration tests for Generic and AutomaticRetest goldens |
| `tests/agents/test_adaptive_retest_agent.py` | Modify | Verify typed field access, remove regex-based assertions |

## Interfaces / Contracts

```python
class CrossChecksGeneric(BaseModel):
    mc_enabled: bool = False
    mc_runs: int = 100
    mc_percentile: int = 95
    wf_enabled: bool = False
    wf_cycles: int = 5
    confidence_level: float = 0.95

class MonteCarloRetest(BaseModel):
    use: bool = False
    number_of_simulations: int = 100
    methods: list[MonteCarloMethod] = []
    acceptance_settings: AcceptanceSettings | None = None

class CrossChecksAutomaticRetest(BaseModel):
    use: bool = True
    retest_with_higher_precision: RetestWithHigherPrecision | None = None
    monte_carlo_retest: MonteCarloRetest | None = None
    monte_carlo_manipulation: MonteCarloManipulation | None = None
    retest_on_additional_markets: RetestOnAdditionalMarkets | None = None
    walk_forward_optimization: WalkForwardOptimization | None = None
    walk_forward_matrix: WalkForwardMatrix | None = None
    opt_profile_sys_param_permutation: OptProfileSysParamPermutation | None = None

class CrossChecksConfig(BaseModel):
    raw_xml: str = ""
    dialect: str = "generic"
    generic: CrossChecksGeneric | None = None
    automatic_retest: CrossChecksAutomaticRetest | None = None
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Model parsing/validation | Pydantic validators for both dialects |
| Unit | Reader dialect detection | Golden XML fixtures for Generic and AutomaticRetest |
| Unit | Writer round-trip | Read → write → read preserves typed fields + raw_xml extras |
| Unit | Patcher typed mutation | `SetCrossChecksInstruction` updates `generic` fields |
| Integration | adaptive_retest_agent | Verify `inspect_cfx_signals` reads typed fields without regex |
| Integration | project_builder | Verify CrossChecks config reads typed fields |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required. `raw_xml` remains intact throughout. Consumers fall back to `raw_xml` regex if typed fields are absent, so rollout is incremental.

## Open Questions

- [ ] Should `SetCrossChecksInstruction` be extended with an `AutomaticRetest` variant, or should AutomaticRetest mutations go through a separate instruction type?
- [ ] Should `CrossChecksConfig` use a Pydantic discriminated union (`Literal["generic" | "automatic_retest"]`) instead of optional fields?
- [x] Do we need to model every nested AutomaticRetest element, or only the ones currently consumed by `adaptive_retest_agent.py` and `project_builder.py`?
      — Resolved 2026-09-30: only the consumed ones. Nested content that no consumer reads
      (`<Methods>`, `<Param1>`/`<Param2>`, `<OptimizeExitTypes>`, `<MaxTests>`, acceptance settings)
      is deliberately left unmodeled. To keep that safe, every sub-model carries a `raw_xml` field
      holding the original element markup, and `to_xml()` re-emits it verbatim in preference to
      re-synthesizing the element. Typed consumers get modeled fields; the dialect round-trips
      without loss; and no schema is invented for content nobody reads. This is what makes partial
      modeling safe to ship, and it is the mechanism task 4.2/4.3/4.5 rely on.

## Round-trip fidelity guarantees (2026-09-30)

Closing 4.2/4.3/4.5 required fixing serializer/parser asymmetries that would otherwise have
corrupted output once builders started emitting typed sections. These are now guarantees:

- `to_xml()` re-emits a parsed element from `raw_xml` instead of rebuilding it. Re-synthesizing
  was lossy: it rewrote `<ConfidenceLevel>0.95</ConfidenceLevel>` into
  `<ConfidenceLevel value="0.95"/>`, and emitted empty `<Param1 value="" />` for values it had no
  field for.
- `auto_tags` is kept in sync with `_parse_automatic_retest`. A recognized tag missing from
  `auto_tags` was parsed into its typed sub-model *and* kept in `raw_xml`, serializing the element
  twice. `MonteCarloManipulation`, `RetestOnAdditionalMarkets`, `WalkForwardMatrix` and
  `OptProfileSysParamPermutation` were all affected.
- The generic dialect serializer writes `runs=` (the spelling the writer, patcher, templates and
  translator all emit) instead of `simulations=`, which its own parser never read — a serialized
  config silently reverted `mc_runs` to the default. The parser accepts both spellings, because
  `renderers.py::_crosschecks_section` has historically emitted `simulations=`.
- `ConfidenceLevel` is read from the `value` attribute *or* element text. Reading only the
  attribute silently discarded the child form that the adaptive retest builder emits.
