# Design: Advanced Ranking Filters and Data Range Parts

## Technical Approach

Add typed Pydantic models and patcher instructions for two new CFX complex sections, following the existing `RankingsConfig`/`CrossChecksConfig`/`RetesterDataConfig` pattern: models hold typed fields plus a `raw_xml` bridge, patcher instructions build XML strings and assign them to `raw_xml`, and the writer serializes complex sections via `_append_complex_section` or inline rendering.

For **advanced ranking filters**, new `AdvancedRankingCondition` and `ColumnValue` models mirror the nested `<Rankings><Conditions><Condition use="..."><Column-Value .../></Condition></Conditions></Rankings>` structure verified in the SQX 144/2953 Retester CFX. A new `AdvancedRankingsConfig` holds either typed condition lists or `raw_xml`.

For **data range parts**, a new `DataRangeParts` model exposes stable typed fields for known sub-ranges (IST, ISC, ISV1..ISV10, OOS1, OOS-Every, ISV-Every, validation/test split ratios, date bounds) alongside a `raw_xml` bridge for unknown or proprietary ranges.

## Architecture Decisions

### Decision: New instruction path instead of extending flat ranking conditions

**Choice**: Introduce `AddAdvancedRankingConditionInstruction`, `SetAdvancedRankingsInstruction`, and `SetDataRangePartsInstruction` rather than mutating `AddRankingConditionInstruction`.

**Alternatives considered**: Extend `AddRankingConditionInstruction` with optional nested fields; overload `SetRankingsInstruction`.

**Rationale**: The existing flat path writes `CriterionN@metric/operator/value` key-value pairs into a `SettingsSection`. Advanced filters require deeply nested `<Condition>` → `<Left-Side>` → `<Column-Value>` XML with many attributes. Mixing both shapes in one instruction would force the patcher to branch on every field, increasing complexity and risk of breaking the simple path. Additive instructions keep backward compatibility byte-identical.

### Decision: `raw_xml` bridge for data range parts

**Choice**: `DataRangeParts` uses typed fields for known concepts plus a `raw_xml` string passthrough.

**Alternatives considered**: Fully typed model enumerating every possible `<Data>` sub-range; pure `raw_xml` passthrough like the current `Data` section.

**Rationale**: The Data schema has many optional/version-specific sub-ranges. A fully typed model would require constant updates as SQX evolves. The `raw_xml` bridge preserves unknown content verbatim while allowing QuantLab to populate stable fields (IST, ISC, split ratios) without schema drift.

### Decision: Backward compatibility strategy

**Choice**: Do not modify `AddRankingConditionInstruction`, `SetRankingsInstruction`, or the simple `rankings` `SettingsSection`.

**Alternatives considered**: Replace simple rankings with the new advanced model.

**Rationale**: Existing campaigns, agents, and golden tests depend on the simple path. The proposal explicitly scopes removal of the simple path as out-of-bounds. New instructions are additive; disabling them preserves existing behavior.

## Data Flow

    Agent/DSL prompt
        │
        ▼
    New DSL models (AdvancedRankingFilter, DataRangePartsDSL)
        │
        ▼
    Translator (generate_cfx_archive extended)
        │
        ▼
    New patcher instructions
        │
        ▼
    CfxPatcher._apply_* → BuildTask.rankings_section / retester_data
        │
        ▼
    CfxWriter._append_complex_section OR inline XML builder
        │
        ▼
    config.xml with nested <Rankings> / <Data> sub-ranges

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/cfx/models.py` | Modify | Add `ColumnValue`, `AdvancedRankingCondition`, `AdvancedRankingsConfig`, `DataRangeParts` models. |
| `sdk/quantlab/cfx/patcher.py` | Modify | Add `AddAdvancedRankingConditionInstruction`, `SetAdvancedRankingsInstruction`, `SetDataRangePartsInstruction` plus validators/appliers. |
| `sdk/quantlab/cfx/writer.py` | Modify | Extend `_append_complex_section` type union or add inline serializers for advanced rankings and data range parts. |
| `sdk/quantlab/cfx/dom.py` | Modify | Add `add_advanced_ranking_condition`, `set_data_range_parts` domain helpers. |
| `sdk/quantlab/translate/translator.py` | Modify | Map new DSL fields to advanced ranking instructions. |
| `sdk/quantlab/dsl/models.py` | Modify | Add `AdvancedRankingFilter` DSL model and extend `ResearchConfig` if needed. |
| `sdk/quantlab/phase4/templates.py` | Modify | Add template placeholders for advanced ranking filters. |
| `sdk/quantlab/customproject/renderers.py` | Modify | Render advanced filters in multi-task XML. |
| `tests/cfx/test_patcher.py` | New | Advanced ranking patcher tests. |
| `tests/phase4/test_project_builder.py` | New | Project builder golden tests. |
| `tests/cfx/fixtures/retester-advanced-rankings.cfx` | New | Real CFX golden extracted from SQX 144/2953 sample. |

## Interfaces / Contracts

```python
class ColumnValue(BaseModel):
    column: str
    column_type: str = "0"
    format: str
    result_type: str = "main"
    direction: str = "0"
    sample_type: str = "127"
    pl_type: str = "10"
    confidence_level: str = "50"
    market: str = "1"
    subresult: str = "30"
    pct_ratio: str = "0"
    class_: str = Field(alias="class")
    name: str | None = None

class AdvancedRankingCondition(BaseModel):
    use: bool = True
    result_type: str = "main"
    sample_type: str = "127"
    direction: str = "0"
    pct_ratio: str = "0"
    confidence_level: str = "50"
    market: str = "1"
    pl_type: str = "10"
    subresult: str = "30"
    class_: str | None = Field(default=None, alias="class")
    name: str | None = None
    column_values: list[ColumnValue] = Field(default_factory=list)

class AdvancedRankingsConfig(BaseModel):
    conditions: list[AdvancedRankingCondition] | None = None
    raw_xml: str = ""

class DataRangeParts(BaseModel):
    ist: str | None = None
    isc: str | None = None
    isv_1: str | None = None
    # ... ISV2..ISV10, OOS1, OOS_Every, ISV_Every ...
    validation_ratio: float | None = None
    test_ratio: float | None = None
    date_from: str | None = None
    date_to: str | None = None
    raw_xml: str = ""
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Model validation, round-trip serialization | Pydantic model_dump/parse round-trip for `AdvancedRankingCondition`, `ColumnValue`, `DataRangeParts`. |
| Integration | Patcher instructions | Apply new instructions to a `CfxArchive`, verify `raw_xml` matches expected nested XML. |
| Integration | Translator | DSL `AdvancedRankingFilter` → patcher instruction → CFX archive round-trip. |
| E2E / Golden | Real CFX fidelity | Parse `tests/cfx/fixtures/retester-advanced-rankings.cfx` (extracted from real Retester CFX), re-serialize, and diff against golden to ensure no attribute loss. |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

Additive change. Existing simple ranking instructions (`AddRankingConditionInstruction`, `SetRankingsInstruction`) remain untouched. New advanced filters are emitted only when new instructions are explicitly applied. If typed models cause a schema mismatch, fall back to `raw_xml` bridge without removing simple paths.

## Open Questions

None.
