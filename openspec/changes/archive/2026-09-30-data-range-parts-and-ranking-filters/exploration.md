## Exploration: data-range-parts-and-ranking-filters

### Current State
- **Ranking conditions** are modeled by `AddRankingConditionInstruction` (metric, operator, value only) in `sdk/quantlab/cfx/models.py:642`. The patcher writes these as flat key-value pairs (`CriterionN@metric`, `CriterionN@operator`, `CriterionN@value`) into the `Rankings` `SettingsSection` (`patcher.py:478`).
- **SetRankingsInstruction** (`models.py:715`) only writes simple `<Rankings><MinTrades/><Metric name="..."/></Rankings>` XML via `raw_xml` in `patcher.py:591` and `writer.py:279`.
- **Advanced ranking filters** in SQX use deeply nested `<Condition>` elements with `<Column-Value>` attributes: `sampleType` (127=main, 10=WalkForwardOptimization, 20=WalkForwardMatrix, plus values for IST/ISV/OOS), `direction` (0=Both), `resultType` (main / RetestOnAdditionalMarkets / WalkForwardMatrix / WalkForwardOptimization / MonteCarloRetest / MonteCarloManipulation / RetestWithHigherPrecision), `pctRatio` (0/50/60/80/130/175/200), `columnType`, `format`, `plType`, `confidenceLevel`, `market`, `subresult`, `class`. Verified in golden CFX `sdk/assets/SQX_144_2953_linux_20260601/user/projects/sqx_4fdea2e7519c/project.cfx`.
- **Data range parts** (ISV1..ISV10, OOS1, ISC, IST, ISV-Every, OOS-Every) are mentioned in `docs/sqx-builder-config/SQX Builder Config.md:91` and `sdk/quantlab/knowledge/kb/seeder.py:803` as a known doc gap (`status: needs_review`). The golden CFX Data section only shows `<OutOfSample showGraph="false" />` — no explicit ISV/IST/OOS segment definitions were found in the repo's golden files.
- **Translator** (`translate/translator.py:173`) maps DSL `AcceptanceCriterion` directly to `add_ranking_condition`, so the DSL currently cannot express the missing fields either.

### Affected Areas
- `sdk/quantlab/cfx/models.py` — Add new instruction models for advanced ranking filters; add data range part models.
- `sdk/quantlab/cfx/patcher.py` — Add validators and appliers for new instructions; rankings currently use flat SettingsSection but need raw_xml complex section support for nested `<Condition>` XML.
- `sdk/quantlab/cfx/writer.py` — `_serialise_task` already supports complex sections via raw_xml passthrough; may need minor updates.
- `sdk/quantlab/cfx/dom.py` — Add high-level domain methods for new instructions.
- `sdk/quantlab/translate/translator.py` — Extend DSL-to-CFX translation to carry sample/direction/unit/pctRatio fields.
- `sdk/quantlab/phase4/templates.py` — Update retester/optimizer template builders if they need advanced ranking support.
- `sdk/quantlab/customproject/renderers.py` — Update renderers if custom project tasks need advanced ranking/data range parts.
- `sdk/quantlab/dsl/models.py` — Extend `AcceptanceCriterion` or add new models for advanced ranking filters and data range parts.
- `tests/cfx/test_patcher.py` — Add tests for new instructions.
- `tests/phase4/test_project_builder.py` — Add tests for advanced ranking XML generation.
- `tests/cfx/fixtures/` — May need golden CFX fixtures with advanced ranking filters.

### Approaches
1. **Extend existing ranking-condition models to carry sample/direction/unit fields**
   - Add `sample_type`, `direction`, `result_type`, `pct_ratio` fields to `AddRankingConditionInstruction`.
   - Add data range part fields to `SetDateRangeInstruction` or a new `SetDataRangePartsInstruction`.
   - **Pros**: Minimal new types; backward-compatible; fits existing patcher dispatch table.
   - **Cons**: The current patcher writes ranking conditions to a flat `SettingsSection` dict (`rankings.settings`), but advanced filters require deeply nested XML (`<Condition><Left-Side><Column-Value .../></Left-Side><Comparator...><Right-Side...`). A flat dict cannot express this. You would need to either (a) switch `task.rankings` to a complex raw_xml section, breaking existing simple-key behavior, or (b) invent a hybrid serialization that is fragile. Data range parts similarly need nested XML that a flat dict cannot express.
   - **Effort**: Medium — requires refactoring how Rankings/Data sections are stored and serialized.

2. **Introduce a new CFX instruction/patcher path for advanced ranking filters (Phase 4 pattern)**
   - Create new typed models: `AddAdvancedRankingConditionInstruction` (with `sample_type`, `direction`, `result_type`, `pct_ratio`, `metric`, `operator`, `value`), `SetDataRangePartsInstruction`, etc.
   - Store advanced ranking filters in a new complex section (e.g., `rankings_section` as `RankingsConfig` with full nested XML) or extend `RankingsConfig` to support typed fields.
   - Use raw_xml passthrough for complex nested structures, following the Phase 4 pattern already used for `CrossChecksConfig`, `RankingsConfig`, `RetesterDataConfig`.
   - **Pros**: Clean separation from simple ranking conditions; follows established Phase 4 raw_xml pattern; handles arbitrarily complex nested XML without refactoring flat SettingsSection; easy to round-trip parse/serialize; agent prompts can choose between simple and advanced instructions.
   - **Cons**: More new types; need to define the exact XML schema for data range parts (currently a doc gap).
   - **Effort**: Medium-High — requires new models, patcher appliers, validators, domain methods, translator updates, and tests.

### Recommendation
**Approise 2: Introduce a new CFX instruction/patcher path for advanced ranking filters.**

The existing flat `SettingsSection` pattern cannot express the deeply nested `<Condition><Left-Side><Column-Value .../></Left-Side>` structure required for advanced ranking filters. The Phase 4 codebase already established the correct pattern: dedicated complex-section models (`CrossChecksConfig`, `RankingsConfig`, `RetesterDataConfig`) with `raw_xml` passthrough, plus typed patcher instructions (`SetRankingsInstruction`, `SetCrossChecksInstruction`, `SetRetesterDataInstruction`) that build the XML. Extending this pattern to advanced ranking filters and data range parts is the lowest-risk path.

For **data range parts**, because the exact SQX XML schema is a known doc gap, the initial implementation should use a `raw_xml` passthrough section (e.g., `DataRangePartsConfig`) so QuantLab can emit verified XML snippets without waiting for full schema modeling. Once the schema is verified from a real SQX export, it can be promoted to typed fields.

### Risks
- **CFX schema/version compatibility**: `sampleType`, `direction`, `resultType`, and `pctRatio` are SQX-internal numeric enums that may change between SQX versions. The codebase pins `PINNED_SQX_VERSION` but future SQX updates could break assumptions.
- **Test coverage gaps**: Complex nested XML generation needs golden-file or round-trip tests to catch attribute typos (e.g., `sampleType="127"` vs `127`).
- **Agent prompt complexity**: LLM agents must now choose among many new options (sample source: Full/IST/ISC/ISV1..ISV10/OOS1/ISV-Every/OOS-Every; direction: Both/Long/Short; result unit: Money/Percent/Pips; percent ratio). Prompts need clear decision trees and examples, or agents will default to simple conditions.
- **Data range parts schema gap**: The exact XML elements/attributes for ISV/IST/OOS segments are not documented in the repo. Implementation must either wait for user-provided CFX evidence or use raw_xml passthrough as a temporary bridge.

### Ready for Proposal
**Yes**, with one remaining ambiguity to resolve with the user before proposal:
- **Data range parts XML schema**: The user mentions ISV1..ISV10, OOS1, ISC, IST, ISV-Every, OOS-Every, but the repo's golden CFX and docs do not contain the exact SQX XML for these segments. The orchestrator should ask the user to provide a sample CFX export (or confirm the XML structure) from SQX Builder/Retester that shows how data range parts are configured, so the model design can be verified against real SQX output rather than inferred.
