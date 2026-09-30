# Tasks: Project Template Engine and Adaptive Retest Strategy

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 1300–2100 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | PR | Focused test | Runtime harness | Rollback boundary |
|------|------|----|--------------|-----------------|-------------------|
| 1 | Template registry + 3 templates + golden validation | 1 | `pytest tests/phase4/test_template_*.py` | `sqcli -h` probe / SQX 144/2953 | Remove `template_registry.py` |
| 2 | AutomaticRetest renderer + template metadata injection | 2 | `pytest tests/customproject/test_renderers.py` | N/A — pure XML | Revert `renderers.py`, `generator.py` |
| 3 | Adaptive Retest Agent + RetesterStage CFX config | 3 | `pytest tests/phase4/test_adaptive_retest.py` | CFX patch round-trip | Revert `adaptive_retest_agent.py`, `retester.py`, `retester_stage.py` |

## Phase 1: Foundation (WU-1 — PR 1)

- [x] **T-1.1** | WU-1 / PR-1 | Create `sdk/quantlab/phase4/template_registry.py` with `TemplateDefinition` and `DuplicateTemplateError`. | Unit: registry instantiation, resolve/reject | Depends: none
- [x] **T-1.2** | WU-1 / PR-1 | Implement case-insensitive dict registry with `register()` and `resolve()`. | Unit: case-insensitive lookup | Depends: T-1.1
- [x] **T-1.3** | WU-1 / PR-1 | Define `standard_research`, `quick_validation`, `deep_robustness` templates. | Unit: all three resolve | Depends: T-1.2
- [x] **T-1.4** | WU-1 / PR-1 | Write golden validation tests for all 3 templates against SQX 144/2953. | Golden: `validate_golden` passes | Depends: T-1.3

## Phase 2: Core Implementation (WU-2 — PR 2)

- [x] **T-2.1** | WU-2 / PR-2 | Add `render_automatic_retest()` to `sdk/quantlab/customproject/renderers.py`. | Unit: `type="AutomaticRetest"`, no MC/WF CrossChecks | Depends: none
- [x] **T-2.2** | WU-2 / PR-2 | Modify `sdk/quantlab/customproject/generator.py` to inject `<Template>` metadata when `template_name` is set. | Unit: template CFX has metadata; ad-hoc does not | Depends: T-2.1
- [x] **T-2.3** | WU-2 / PR-2 | Verify generic Retest rendering is unchanged. | Unit: Retest XML matches pre-change structure | Depends: T-2.1

## Phase 3: Adaptive Retest Agent (WU-3 — PR 3)

- [x] **T-3.1** | WU-3 / PR-3 | Create `sdk/quantlab/agents/adaptive_retest_agent.py` with `RetestSignals`, `inspect_cfx_signals`, `select_retest_mode`, `apply_adaptive_mutations`. | Unit: module imports and public API | Depends: none
- [x] **T-3.2** | WU-3 / PR-3 | Write table-driven unit tests for `select_retest_mode` covering all spec rules and metadata override precedence. | Unit: all scenarios return expected mode | Depends: T-3.1
- [x] **T-3.3** | WU-3 / PR-3 | Write unit tests for `inspect_cfx_signals` read-only behavior and missing-field defaults. | Unit: hash unchanged; missing fields are None | Depends: T-3.1
- [x] **T-3.4** | WU-3 / PR-3 | Modify `sdk/quantlab/phase4/retester.py` to add `select_retest_mode` hook and `from_cfx` constructor. | Unit: `from_cfx` returns valid config | Depends: T-3.1
- [x] **T-3.5** | WU-3 / PR-3 | Modify `sdk/quantlab/pipeline/stages/retester_stage.py` to accept optional CFX path and parse config from CFX. | Integration: CFX config read; DSL fallback works | Depends: T-3.4
- [x] **T-3.6** | WU-3 / PR-3 | Write integration test for CFX → patch → re-read round-trip. | Integration: mutated archive valid | Depends: T-3.1, T-3.4
- [x] **T-3.7** | WU-3 / PR-3 | Write integration test for RetesterStage DSL fallback when CFX is absent. | Integration: DSL path unchanged | Depends: T-3.5

## Phase 4: Cleanup

- [ ] **T-4.1** | All | Update module docstrings and `__all__` exports in touched files. | Manual review | Depends: all
- [ ] **T-4.2** | All | Remove temporary test fixtures and debug logging. | Manual review | Depends: all
