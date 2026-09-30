# Proposal: skill-format-negative-test

## Intent

Close the REQ-904 coverage gap left by `opencode-harness-elevation`: invalid QuantLab `SKILL.md` frontmatter is currently untested. The parent change fixed three skills but did not add the negative acceptance criterion ("Invalid format rejected").

## Scope

### In Scope
- Add negative pytest(s) in `tests/campaign/test_skill_sync.py` asserting that a `SKILL.md` missing required REQ-904 fields is rejected.
- Cover all required fields: `name`, `description`, `disable-model-invocation`, `user-invocable`, `license`, `metadata`.

### Out of Scope
- No production code changes.
- No invocation of the external `gentle-ai` binary.
- No new or modified `openspec/specs/` capability documents.

## Capabilities

### New Capabilities
None

### Modified Capabilities
None

## Approach

**Recommended: Option (a) — pure test-side frontmatter assertion.**

Add a `TestSkillFormatNegative` class in `tests/campaign/test_skill_sync.py`. Each test creates a temp `SKILL.md` missing one required frontmatter field, parses the YAML block, and asserts the missing field is detected. Use `tmp_path` for filesystem isolation.

Justification: This is an explicitly test-only follow-up. Option (a) closes the spec-contract gap with zero production surface area, zero external dependencies, and deterministic execution. Option (b) would depend on the external `gentle-ai` binary output format. Option (c) adds integration complexity for a non-goal.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `tests/campaign/test_skill_sync.py` | Modified | Add `TestSkillFormatNegative` class |
| `openspec/specs/skill-format/spec.md` | Unchanged | REQ-904 source of truth |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Test validates spec contract, not external `gentle-ai` binary rules | Low | Acceptable for test-only scope; binary drift can be caught separately if validation moves in-repo |

## Rollback Plan

Delete the `TestSkillFormatNegative` class from `tests/campaign/test_skill_sync.py`. No other files are modified.

## Dependencies

None.

## Success Criteria

- [ ] New `TestSkillFormatNegative` class added to `tests/campaign/test_skill_sync.py`.
- [ ] At least one negative test per required REQ-904 field.
- [ ] All new tests pass under `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/test_skill_sync.py`.
