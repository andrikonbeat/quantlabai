# Archive Report: Research-Agent-Improvements

## Archive Status

**COMPLETE**

## Summary

research-agent-improvements is closed with all 12 tasks verified. F1 and F2 were
implemented and independently verified; the previous FAIL verdict (F1-03 partial, F1-05
partial, F3 absent) was resolved at close: both partials completed with tests, F3
implemented via strict TDD (RED → GREEN). Regression: 615 passed across all three test
roots with zero failures.

## Artifacts

| Artifact | Status |
|----------|--------|
| `proposal.md`, `design.md` | ✅ pre-existing |
| `specs/` (4 delta specs: knowledge-query, llm-research, research-agent, sqx-parameter-kb) | ✅ pre-existing |
| `tasks.md` | ✅ 12/12 checked against HEAD |
| `apply-progress.md` | ✅ written |
| `verify-report.md` | ✅ `verdict: pass` (replaces prior FAIL) |
| `archive-report.md` | ✅ this report |
| Code (this close) | ✅ `feedback_writer.py` new; `rule.py`, `llm.py`, `tag_calibrator.py`, `knowledge/models.py` modified |

## Verification Evidence

- Targeted: 122 passed (hypothesis_builder 68+2, tag_calibrator 2, feedback_writer 2, F1 suites, parameter validator)
- Regression: 615 passed in `tests/agents/` + `tests/knowledge/` + `sdk/tests/agents/`
- Source-mutating normalization completed before verification; no post-normalization edits

## Follow-ups (not blockers)

1. Doc-only: `research_director.build_pipeline` docstring lists 9 agent stages; code emits 11.
2. `sdk/quantlab/knowledge/sqx_doc_provider.py` has an uncommitted pre-existing fix
   (`_registry_key` normalization, alias `bb`) from an earlier task — left out of this close,
   tracked separately from this change.