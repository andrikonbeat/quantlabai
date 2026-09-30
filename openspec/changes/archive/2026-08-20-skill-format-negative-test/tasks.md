# Tasks: skill-format-negative-test

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 80-120 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: stacked-to-main
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Negative REQ-904 frontmatter tests | PR 1 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/test_skill_sync.py` | N/A — pure unit tests, no external harness | Delete `TestSkillFormatNegative` class from `tests/campaign/test_skill_sync.py` |

## Phase 1: RED

- [x] 1.1 Write failing `TestSkillFormatNegative.test_missing_disable_model_invocation` in `tests/campaign/test_skill_sync.py` asserting a `SKILL.md` missing `disable-model-invocation` is flagged invalid.

## Phase 2: GREEN

- [x] 2.1 Add `_parse_skill_frontmatter` helper to `tests/campaign/test_skill_sync.py` and make the RED test pass.
- [x] 2.2 Add `test_missing_user_invocable` and `test_missing_both_fields` negative cases to `TestSkillFormatNegative`.

## Phase 3: Verification

- [x] 3.1 Run `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/test_skill_sync.py` and verify all tests pass.
