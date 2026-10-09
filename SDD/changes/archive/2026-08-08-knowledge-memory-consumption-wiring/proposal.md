# Proposal: Knowledge Memory Consumption Wiring

## Intent

Wire the deferred consumption hooks from `knowledge-memory-system` into production agents. REQ-204 requires `builder_agent.py` to consult `KbStore.consult()` before configuring builder parameters and warn or block on missing entries. This closes the gap between a tested KB surface and the agent that should consume it.

## Scope

### In Scope
- REQ-204 wiring in `builder_agent.py`: call `KbStore.consult()` before parameter configuration; emit warning or block per missing-entry contract
- Unit tests for wiring (mock `KbStore.consult`, verify warnings/blocks)
- CLI surfacing if blocking behavior requires it
- Delta spec for the new `builder-kb-consult` capability

### Out of Scope
- REQ-205 (config_reviewer teaching-table wiring) — BLOCKED by concurrent uncommitted edits on `config_reviewer.py`; documented as follow-up
- Task 6.3 (building-blocks KB tab + changelog polling) — explicitly deferred per original change
- `compiler.py`, `jforex_deploy.py`, `project_builder.py`, `test_project_builder.py` — do-not-touch per constraints

## Capabilities

### New Capabilities
- `builder-kb-consult`: contract requiring builder_agent to consult KbStore before parameter configuration, warning or blocking on missing KB entries

### Modified Capabilities
- None

## Approach

1. Identify the parameter set extracted from `ResearchConfig` in `builder_agent.py`
2. Call `KbStore.consult()` for each parameter before translation/validation
3. If consult returns empty for a parameter, append a KB warning to the build envelope; if REQ-204 mandates blocking, raise a `ConfigurationError` with missing-entry context
4. Add unit tests with a mocked `KbStore` covering: all params found, partial missing, all missing
5. If warnings/blocking need CLI visibility, extend `sq_commands.py` with a `--kb-warnings` flag on the build path

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/builder_agent.py` | Modified | Add KbStore.consult() call before parameter configuration |
| `sdk/tests/test_builder_agent.py` | New | Unit tests for KB consult wiring (mock KbStore) |
| `sdk/quantlab/cli/sq_commands.py` | Modified (conditional) | Add --kb-warnings flag if blocking behavior requires CLI surfacing |
| `openspec/specs/builder-kb-consult/spec.md` | New | Delta spec for the new builder-kb-consult capability |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Blocking behavior breaks existing build flows | Medium | Default to warning mode in first slice; block mode behind opt-in flag |
| REQ-205 wiring deferred indefinitely | Low | Documented as blocked; follow-up micro-change tracks unblocking |
| Concurrent edits on config_reviewer.py grow stale | Medium | Do not touch; separate change picks up REQ-205 once edits committed |

## Rollback Plan

Revert the `builder_agent.py` changes (KB consult call + warning/block logic) and remove new tests. The agent's original parameter configuration path is restored without side effects. No schema or data migrations are involved.

## Dependencies

- None external. `KbStore` and `build_teaching_table` are already implemented and tested in `sdk/tests/test_context.py`.

## Success Criteria

- [ ] `builder_agent.py` calls `KbStore.consult()` for configured parameters before translation
- [ ] Missing KB entry emits a warning or block per REQ-204 contract
- [ ] Unit tests cover: all params found, partial missing, all missing (mocked KbStore)
- [ ] REQ-205 documented as blocked follow-up
- [ ] Task 6.3 documented as deferred follow-up
