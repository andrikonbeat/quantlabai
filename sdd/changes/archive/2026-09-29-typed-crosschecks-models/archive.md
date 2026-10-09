# Archive: Typed CrossChecks Models

## Change

`typed-crosschecks-models`

## Status

Complete

## Summary

Implemented dual-dialect typed Pydantic models for the CFX `CrossChecks` section, replacing the previous `raw_xml` passthrough with parseable `Generic` and `AutomaticRetest` structures while preserving backward compatibility.

### Completed Work

- Added `CrossChecksGeneric`, `CrossChecksAutomaticRetest`, and nested sub-models in `sdk/quantlab/cfx/models.py`.
- Updated `CrossChecksConfig` with dialect detection, typed population, `from_xml()`, `to_xml()`, and `summary()`.
- Updated reader/writer to serialize typed CrossChecks and merge unknown extras into `raw_xml`.
- Migrated patcher, renderers, translator, phase4 templates, and adaptive retest agent to typed fields with `raw_xml` fallback.
- Updated consumer tests to verify typed model assertions instead of raw XML content.
- Completed this session: `inspect_cfx_signals` in `adaptive_retest_agent.py` reads typed fields (`generic.mc_enabled` / `generic.wf_enabled`) with raw_xml regex fallback; consumer mutation tests assert typed fields instead of raw XML substrings.

### Post-archive re-audit (2026-09-30)

Archiving originally recorded all 25 tasks as complete. A follow-up audit found tasks 4.2, 4.3 and
4.5 were checked off without meeting their contract — the adaptive retest builders and
`render_automatic_retest` still built `CrossChecksConfig` from a bare `raw_xml` string, and
`project_builder.get_template_default` still probed CrossChecks by regex only. All three are now
genuinely implemented, and the audit surfaced four latent serializer/parser asymmetries that would
have corrupted output once builders emitted typed sections (see `apply-progress.md` for the full
list and the fidelity mechanism). Task 4.5 also cited the wrong file: `render_automatic_retest`
lives in `customproject/renderers.py`, not `customproject/templates.py`.

The mechanism that makes partial modeling safe: every CrossChecks sub-model carries the original
element markup in `raw_xml`, and `to_xml()` re-emits it verbatim instead of rebuilding the element.
This resolved design.md's open question — only consumed elements are modeled.

## Verification

- Test command: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/ tests/agents/test_adaptive_retest_agent.py tests/phase4/test_cfx_extensions.py tests/phase4/test_project_builder.py tests/customproject/test_templates.py tests/phase4/test_translator_extensions.py`
- Result: **448 passed, 0 failed**
- After debt closure, full suite: `SQX_FORCE_MOCK=1 python3 -m pytest -q` → **4111 passed, 9 skipped, 0 failed**

## Artifacts

- `openspec/changes/typed-crosschecks-models/proposal.md`
- `openspec/changes/typed-crosschecks-models/design.md`
- `openspec/changes/typed-crosschecks-models/specs/crosschecks-models/spec.md`
- `openspec/changes/typed-crosschecks-models/specs/cfx-editor/spec.md`
- `openspec/changes/typed-crosschecks-models/tasks.md`
- `openspec/changes/typed-crosschecks-models/archive.md`

## Delta Specs Applied

- `crosschecks-models`: new capability
- `cfx-editor`: modified capability

## Rollback

Revert the three PR slices in reverse order:
- PR 3: revert consumer and test changes
- PR 2: revert patcher and consumer changes
- PR 1: revert models, reader, writer, and core tests

All slices preserve `raw_xml` fallback, so partial revert is safe.
