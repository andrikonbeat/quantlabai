# Skill Format Negative Test Specification

## Purpose

Close the REQ-904 coverage gap by adding deterministic negative tests for invalid `SKILL.md` frontmatter. These tests validate the format contract without changing production behavior.

## Requirements

### Requirement: SKILL.md Negative Format Validation (TST-SKILL-01)

The test suite MUST include negative tests that create temporary `SKILL.md` fixtures missing required REQ-904 frontmatter fields and assert the format validator rejects them.

#### Scenario: Valid frontmatter passes

- GIVEN a `SKILL.md` with all required frontmatter fields
- WHEN the format validator runs
- THEN the skill passes validation

#### Scenario: Missing `disable-model-invocation` is rejected

- GIVEN a `SKILL.md` missing the `disable-model-invocation` field
- WHEN the format validator runs
- THEN the skill is flagged invalid

#### Scenario: Missing `user-invocable` is rejected

- GIVEN a `SKILL.md` missing the `user-invocable` field
- WHEN the format validator runs
- THEN the skill is flagged invalid

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | `tests/campaign/test_skill_sync.py` contains `TestSkillFormatNegative` with at least one test per required REQ-904 field |
| 2 | Each test creates a temp `SKILL.md` fixture via `tmp_path` and asserts rejection |
| 3 | All new tests pass under `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/test_skill_sync.py` |
| 4 | Existing skill-sync tests remain green |

## Affected Files

| File | Change |
|------|--------|
| `tests/campaign/test_skill_sync.py` | Add `TestSkillFormatNegative` class |
