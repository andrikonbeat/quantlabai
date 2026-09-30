# Archive Report: Project Template Engine and Adaptive Retest Strategy

**Change**: project-template-and-retest-strategy
**Archived**: 2026-08-12
**Mode**: openspec
**Verdict**: intentional-with-warnings

## Final State Authority

Sources read for this archive (OpenSpec filesystem mode):
- `openspec/changes/project-template-and-retest-strategy/proposal.md`
- `openspec/changes/project-template-and-retest-strategy/specs/custom-project-generator/spec.md`
- `openspec/changes/project-template-and-retest-strategy/specs/retester-automation/spec.md`
- `openspec/changes/project-template-and-retest-strategy/design.md`
- `openspec/changes/project-template-and-retest-strategy/tasks.md`
- `openspec/changes/project-template-and-retest-strategy/verify-report.md`

No review artifacts were discovered (`reviewGate` structurally absent). Archive proceeds under ordinary repository policy.

## Task Final State

| Task | Phase | Status | Notes |
|------|-------|--------|-------|
| T-1.1 | WU-1 / PR-1 | Complete | `template_registry.py` with `TemplateDefinition` and `DuplicateTemplateError` |
| T-1.2 | WU-1 / PR-1 | Complete | Case-insensitive dict registry with `register()` and `resolve()` |
| T-1.3 | WU-1 / PR-1 | Complete | `standard_research`, `quick_validation`, `deep_robustness` templates defined |
| T-1.4 | WU-1 / PR-1 | Complete | Golden validation tests for all 3 templates against SQX 144/2953 |
| T-2.1 | WU-2 / PR-2 | Complete | `render_automatic_retest()` added to `renderers.py` |
| T-2.2 | WU-2 / PR-2 | Complete | Template metadata injection in `generator.py` |
| T-2.3 | WU-2 / PR-2 | Complete | Generic Retest rendering regression verified |
| T-3.1 | WU-3 / PR-3 | Complete | `adaptive_retest_agent.py` with `RetestSignals`, `inspect_cfx_signals`, `select_retest_mode`, `apply_adaptive_mutations` |
| T-3.2 | WU-3 / PR-3 | Complete | Table-driven unit tests for `select_retest_mode` |
| T-3.3 | WU-3 / PR-3 | Complete | Unit tests for `inspect_cfx_signals` read-only behavior |
| T-3.4 | WU-3 / PR-3 | Complete | `RetesterConfig.from_cfx` constructor in `retester.py` |
| T-3.5 | WU-3 / PR-3 | Complete | `RetesterStage` accepts optional CFX path with DSL fallback |
| T-3.6 | WU-3 / PR-3 | Complete | Integration test for CFX → patch → re-read round-trip |
| T-3.7 | WU-3 / PR-3 | Complete | Integration test for DSL fallback when CFX is absent |
| T-4.1 | Cleanup | Incomplete (non-blocking) | Module docstrings and `__all__` exports in touched files |
| T-4.2 | Cleanup | Incomplete (non-blocking) | Remove temporary test fixtures and debug logging |

**Archive-time reconciliation**: The orchestrator explicitly approved archive with T-4.1 and T-4.2 incomplete. These are cleanup tasks, not implementation tasks. Verification passed with warnings (0 critical findings, 1052 tests pass). The archive is marked `intentional-with-warnings`.

## Delivery Summary

### Pull Requests Merged
1. **WU-1 — Template Engine**: Template registry, 3 built-in templates, golden validation
2. **WU-2 — AutomaticRetest renderer + metadata**: Dedicated renderer, template metadata injection
3. **WU-3 — Adaptive Retest Agent + CFX config**: Agent logic, CFX-sourced config, RetesterStage integration

### Files Created
- `sdk/quantlab/customproject/templates.py`
- `sdk/quantlab/phase4/template_registry.py`
- `sdk/quantlab/agents/adaptive_retest_agent.py`
- `tests/customproject/test_templates.py`
- `tests/agents/test_adaptive_retest_agent.py`

### Files Modified
- `sdk/quantlab/customproject/__init__.py`
- `sdk/quantlab/customproject/renderers.py`
- `sdk/quantlab/customproject/generator.py`
- `sdk/quantlab/customproject/validator.py`
- `sdk/quantlab/phase4/retester.py`
- `sdk/quantlab/pipeline/stages/retester_stage.py`
- `sdk/quantlab/cfx/writer.py`
- `sdk/quantlab/cfx/reader.py`
- `tests/cfx/test_writer.py`
- `tests/phase4/test_retester.py`

## Test Results Summary

- **Total tests**: 1052 passed, 0 failed, 4 skipped
- **Build**: All modified files compile successfully (`python3 -m py_compile` exits 0)
- **Spec compliance**: 21/21 scenarios compliant
- **Requirements coverage**: 10/10 requirements verified
- **Verdict**: `pass_with_warnings` (per `verify-report.md`)
- **Critical findings**: 0
- **Blockers**: 0

## Specs Synced

| Domain | Action | Details |
|--------|--------|---------|
| `custom-project-generator` | Updated | 2 requirements added (AutomaticRetest Dedicated Renderer, Template-Aware Task XML Generation) |
| `retester-automation` | Updated | 2 requirements added (CFX-Sourced Configuration, Adaptive Retest Selection Hooks) |

Main specs now reflect the new behavior:
- `openspec/specs/custom-project-generator/spec.md`
- `openspec/specs/retester-automation/spec.md`

## Known Follow-ups

1. **T-4.1**: Update module docstrings and `__all__` exports in touched files.
2. **T-4.2**: Remove temporary test fixtures and debug logging.

These are non-blocking cleanup items. The core functionality is complete and verified.

## Migration / Rollback Notes

- **Migration**: No migration required. DSL path remains default; CFX config is opt-in via explicit CFX path argument. Template metadata is additive and ignored by pre-existing generators.
- **Rollback**: Remove new modules (`templates.py`, `template_registry.py`, `adaptive_retest_agent.py`). Templates remain as static CFX files importable via `sqcli`. RetesterStage falls back to DSL-only config path.

## Lessons Learned

1. Template metadata injection via `<Template>` element is additive and backward-compatible with pre-existing generators.
2. CFX metadata override precedence (metadata > signals > default) proved clean to implement as a pure function.
3. Golden validation with injected `sqcli -h` readiness probe caught format deviations early.
4. Untracked change directories require `mv` fallback instead of `git mv` during archive.
5. Cleanup tasks (docstrings, fixture cleanup) should be tracked separately from implementation tasks to avoid blocking archive on cosmetic work.
