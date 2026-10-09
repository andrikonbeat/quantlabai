# Design: skill-format-negative-test

## Technical Approach

Add a `TestSkillFormatNegative` class to the existing `tests/campaign/test_skill_sync.py`. Because no in-repo REQ-904 frontmatter validator exists, each test owns its validation logic as a pure test-side helper. Tests write temporary `SKILL.md` fixtures via `tmp_path`, parse the YAML frontmatter block, and assert presence of required fields. No production code is touched.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Add new test file `test_skill_format.py` | Clean separation, but duplicates module-level setup already present in `test_skill_sync.py` | Extend `tests/campaign/test_skill_sync.py` |
| Introduce an in-repo validator module | Centralizes logic, but adds production surface area for a test-only requirement | Keep validation inline in the test class |
| Use `pytest.mark.parametrize` | Compact, but obscures per-field acceptance criteria in spec TST-SKILL-01 | One test method per required field |

## Data Flow

    tmp_path fixture
         │
         ▼
   Write SKILL.md (valid or missing fields)
         │
         ▼
   Parse YAML frontmatter (test-side helper)
         │
         ▼
   Assert required fields present / absent

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `tests/campaign/test_skill_sync.py` | Modify | Add `TestSkillFormatNegative` class with 4 tests |

## Interfaces / Contracts

**Helper signature**:
```python
def _parse_skill_frontmatter(skill_md_text: str) -> dict[str, object]:
    """Extract the YAML frontmatter block from a SKILL.md string.

    Returns the parsed metadata dict, or raises ValueError if the frontmatter
    block is missing or malformed.
    """
```

**Required REQ-904 field set**:
```python
REQUIRED_FRONTMATTER_FIELDS = {
    "name": str,
    "description": str,
    "disable-model-invocation": bool,
    "user-invocable": bool,
    "license": str,
    "metadata": dict,
}
```

Validation rule: a `SKILL.md` passes only if every key in `REQUIRED_FRONTMATTER_FIELDS` exists and the value type matches.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Frontmatter parsing helper | Direct call with valid/invalid strings |
| Unit | Negative field coverage | `tmp_path` + write SKILL.md + assert rejection |
| Regression | Existing sync tests | Run full `tests/campaign/test_skill_sync.py` suite |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required.

## Open Questions

None.
