# Proposal: Hypothesis Builder

## Intent

Pipeline gap: research produces qualitative hypotheses with market rationale (`llm_rationale`, `source_urls`, `data_sources`) but `BuilderAgent` requires `ResearchConfig.building_blocks` with `IndicatorConfig` + `EntryRule`/`ExitRule`. Classic `ResearchAgent` uses naive keyword matching (RSI→oversold, BB→20,2) that can't leverage LLM rationale. `HypothesisBuilder` bridges this: hypotheses → validated building blocks + strategies.

## Scope

### In Scope
- `HypothesisBuilder`: `list[HypothesisConfig] + market_context → list[BuildingBlock] + list[Strategy]`
- **LLM mode**: prompt from hypothesis rationale → LLM generates specific blocks + rules
- **Rule mode**: deterministic mapper from `hypothesis.description` + `parameters` to indicator configs
- `HypothesisBuilderStage`: new pipeline stage between research and builder
- Generated blocks pass `ResearchConfig._validate_building_block_references()`
- Strategies combine blocks by direction (LONG/SHORT/BOTH)

### Out of Scope
- Modifying `ResearchAgent` keyword mapping
- Pipeline gates or gate policies
- UI, DB persistence, `LLMResearchAgent` prompt changes

## Capabilities

### New Capabilities
- `hypothesis-builder`: Translates qualitative `HypothesisConfig` (with `llm_rationale`, `source_urls`, `data_sources`) into validated `BuildingBlock`/`Strategy` instances

### Modified Capabilities
- `pipeline-core`: Stage registry must include `HypothesisBuilderStage` between research and builder

## Approach

**Two-mode dispatch via strategy pattern:**

1. **LLM mode**: Build focused prompt per hypothesis using its rationale + data_sources → LLM emits indicator configs + entry/exit rules → validate against Pydantic models
2. **Rule mode**: Map `hypothesis.description` + `parameters` to indicator configs. Supports RSI, BB, Donchian, EMA, ATR with parameter extraction from hypothesis fields (period, thresholds, ticker)
3. **Strategy gen**: Combine blocks by direction parameter → emit one `Strategy` per direction
4. **Stage**: `Stage` subclass with `requires=["research_config"]`, overrides building_blocks before passing to `BuilderAgent`
5. **Pipeline**: `generate_pipeline_config()` inserts stage after research

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `agents/hypothesis_builder.py` | New | Builder with LLM + Rule modes |
| `agents/hypothesis_builder_stage.py` | New | Stage subclass |
| `agents/builder_agent.py` | Modified | Stage list insertion |
| `dsl/models.py` | None | Reuses existing models |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM hallucinates indicator params | Med | Validate against `IndicatorConfig`; restrict to known indicator names |
| Rule mode misses nuance | Med | LLM mode is primary; Rule is deterministic fallback |
| Stage order breaks existing runs | Low | Insertion-only; backward-compat via stage defaults |

## Rollback Plan

Revert `generate_pipeline_config()` stage list. Delete `hypothesis_builder.py` and `hypothesis_builder_stage.py`.

## Dependencies

- OpenAI SDK (same as `LLMResearchAgent`)
- `HypothesisConfig`, `BuildingBlock`, `Strategy` models (unchanged)

## Success Criteria

- [ ] LLM mode generates valid blocks with `IndicatorConfig` + rules from rationale-bearing hypothesis
- [ ] Rule mode maps description + params without keyword-match fallthrough to default RSI
- [ ] Stage insertion produces strategies consumed by `BuilderAgent`
- [ ] All generated blocks pass `_validate_building_block_references()`
- [ ] All existing pipeline tests pass unchanged
