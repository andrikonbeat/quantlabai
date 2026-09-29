# Tasks: Advanced Ranking Filters and Data Range Parts

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 450–550 |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: foundation + patcher → PR 2: integration → PR 3: golden + cleanup |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Typed models + advanced ranking patcher | PR 1 | SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/ | N/A (unit tests only) | Revert sdk/quantlab/cfx/models.py and patcher changes |
| 2 | Data range bridge + translator/DSL/renderer | PR 2 | SQX_FORCE_MOCK=1 python3 -m pytest -q tests/dsl/ tests/phase4/ | N/A (unit tests only) | Revert translator, DSL, template, renderer changes |
| 3 | Golden round-trip + integration verification | PR 3 | SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/test_patcher.py tests/phase4/test_project_builder.py | N/A (golden fixture validation) | Revert fixture + golden test additions |

Threat-matrix RED tests: N/A

## Phase 1: Foundation / Infrastructure

- [x] 1.1 RED: test AdvancedRankingCondition + ColumnValue model round-trip
- [x] 1.2 GREEN: implement ColumnValue, AdvancedRankingCondition, AdvancedRankingsConfig in sdk/quantlab/cfx/models.py
- [x] 1.3 RED: test DataRangeParts model with typed fields + raw_xml fallback
- [x] 1.4 GREEN: implement DataRangeParts in sdk/quantlab/cfx/models.py

## Phase 2: Core Patcher

- [x] 2.1 RED: test AddAdvancedRankingConditionInstruction patcher behavior
- [x] 2.2 GREEN: implement AddAdvancedRankingConditionInstruction + SetAdvancedRankingsInstruction in sdk/quantlab/cfx/patcher.py
- [x] 2.3 RED: test SetDataRangePartsInstruction patcher behavior
- [x] 2.4 GREEN: implement SetDataRangePartsInstruction in sdk/quantlab/cfx/patcher.py

## Phase 3: Integration / Wiring

- [x] 3.1 GREEN: extend CfxWriter and dom.py for nested conditions and data parts
- [x] 3.2 RED: test DSL AdvancedRankingFilter + DataRangePartsDSL models
- [x] 3.3 GREEN: add DSL models to sdk/quantlab/dsl/models.py
- [x] 3.4 GREEN: extend translator.py mapping to new DSL fields
- [x] 3.5 GREEN: add phase4 template placeholders and renderer support

## Phase 4: Testing / Verification

- [ ] 4.1 RED: golden CFX round-trip test using retester-advanced-rankings.cfx
- [ ] 4.2 GREEN: create fixture and make round-trip pass
- [ ] 4.3 GREEN: mixed simple + advanced conditions compatibility test
- [ ] 4.4 GREEN: project builder golden test for phase4 emission

## Phase 5: Cleanup

- [ ] 5.1 Update docstrings/comments and remove temporary scaffolding
