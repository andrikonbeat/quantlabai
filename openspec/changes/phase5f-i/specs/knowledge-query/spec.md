# Delta Spec: Knowledge Query (Modified Capability)

## Change Summary

Minor modification to existing `knowledge-query` capability (see `openspec/specs/knowledge-query/spec.md`). The smoke test (`e2e-smoke-test`) uses `--sharpe ">1.0"` filter to validate end-to-end flow. No functional changes to query engine — only confirms existing query CLI works as specified.

---

## ADDED Requirements

### Requirement: Smoke Test Integration Validation (FR-001)

The existing `knowledge query --sharpe` CLI command SHALL work correctly when invoked from the E2E smoke test with a temporary Knowledge Lake.

**No code changes required** — this validates existing behavior in isolated test environment.

#### Scenario: Query works with temp Knowledge Lake
- GIVEN temp Knowledge Lake with campaign `sharpe: 1.5` in index
- WHEN `quantlab knowledge query --sharpe ">1.0" --json` runs with `QUANTLAB_KNOWLEDGE_ROOT` pointing to temp dir
- THEN JSON output contains campaign with `sharpe >= 1.0`
- AND exit code 0

---

## MODIFIED Requirements

None. The existing `knowledge-query` spec fully covers the query functionality used by the smoke test.

---

## REMOVED Requirements

None.

---

## RENAMED Requirements

None.

---

## Acceptance Criteria (Delta)

| Criterion | Verification |
|-----------|--------------|
| `knowledge query --sharpe` works in smoke test | E2E smoke test passes query step |
| Temp Knowledge Lake isolation works | Smoke test fixture creates isolated index |
| No regression in existing query features | All existing knowledge-query tests pass |

---

## Notes

This delta exists solely to document that `knowledge-query` is a **Modified Capability** in the proposal (used by smoke test). The existing spec at `openspec/specs/knowledge-query/spec.md` is complete and requires no changes for Phase 5f-5i.