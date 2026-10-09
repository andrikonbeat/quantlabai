# Delta for campaign-phase-agents

## MODIFIED Requirements

### Requirement: Repo-Canonical Prompt Source (REQ-806)

The repo directory `AI/opencode/agents/` MUST be the single source of truth for the campaign prompt, all phase prompts, `orchestrator.md`, and `guardian-orchestrator.md`. The live `~/.config/opencode/prompts/quantlab/` copies MUST be generated from it by a sync script; hand-editing live prompts is not permitted. The sync MUST merge the existing guardian delegation into the repo canonical copy. `deploy.md` and `monitor.md` are retired from live and versioned as legacy in repo only.
(Previously: the allowlist covered only `campaign.md`, `phase-*.md`, and `guardian-orchestrator.md`; `orchestrator.md` was not managed, and `deploy.md`/`monitor.md` were live orphans.)

#### Scenario: Sync propagates to live

- GIVEN an edited repo campaign.md
- WHEN the sync script runs
- THEN the live copy matches the repo bytes
- AND the guardian delegation drift is resolved in the repo canonical copy

#### Scenario: Live prompt never hand-edited

- GIVEN a live prompt that differs from repo canonical
- WHEN the parity check runs
- THEN the difference is attributed to a sync miss, not a manual edit
- AND the sync script is the only update path

#### Scenario: guardian-orchestrator.md is managed

- GIVEN a repo edit to `guardian-orchestrator.md`
- WHEN the sync script runs
- THEN the live copy matches the repo bytes
- AND `guardian.md` / `orchestrator.md` stay non-managed

#### Scenario: orchestrator.md syncs

- GIVEN a repo edit to `orchestrator.md`
- WHEN the sync script runs
- THEN the live copy matches the repo bytes

#### Scenario: deploy.md/monitor.md retired from live

- GIVEN live copies of `deploy.md` and `monitor.md`
- WHEN the sync script runs
- THEN those files are removed from live
- AND the repo retains versioned legacy copies

### Requirement: Prompt Parity Test (REQ-807)

A parity test MUST assert byte-equality between every repo prompt under `AI/opencode/agents/` and its live generated counterpart. A mismatch MUST fail the test and identify the drifted file.

#### Scenario: Parity holds

- GIVEN synced prompts
- WHEN the parity test runs
- THEN all repo ⇄ live pairs are byte-equal

#### Scenario: Drift detected

- GIVEN a live prompt that was regenerated or altered
- WHEN the parity test runs
- THEN the test fails
- AND the drifted file path is reported

#### Scenario: Parity holds after allowlist change

- GIVEN the extended allowlist including `orchestrator.md` and excluding `deploy.md`/`monitor.md`
- WHEN the parity test runs
- THEN all managed repo ⇄ live pairs are byte-equal
- AND retired files are absent from live

### Requirement: Test Coupling (REQ-810)

Existing campaign tests MUST keep passing: `assert_flow`/`assert_flow_segments`, the exact-path assertions in `tests/test_orchestrator_prompt.py`, and mock-vs-real behavior gated by `SQX_FORCE_MOCK` MUST remain intact. New per-phase assertions MUST extend, not replace, these tests. Allowlist flips MUST be reflected in the same change's tests.

#### Scenario: Existing asserts pass

- GIVEN the delegation layer and phase agents in place
- WHEN the campaign test suite runs
- THEN all pre-existing flow and prompt assertions pass unchanged
- AND SQX_FORCE_MOCK paths still mock

#### Scenario: Mock-vs-real preserved

- GIVEN SQX_FORCE_MOCK set
- WHEN a dispatch-phase test runs
- THEN the mock path executes without real sqcli calls

#### Scenario: Flipped allowlist tests pass

- GIVEN the updated allowlist including `orchestrator.md` and excluding `deploy.md`/`monitor.md`
- WHEN `test_prompt_sync.py` runs
- THEN the updated sync tests pass
- AND no stale non-managed assertion fails

### Requirement: Sync Contract Test Update (REQ-821)

`tests/campaign/test_prompt_sync.py` SHALL be updated in this change: `orchestrator.md` becomes a managed prompt (REQ-806), while `guardian.md` and `orchestrator.md` (non-managed) MUST NOT be written or deleted by the sync script. Tests SHALL assert the new boundary.
(Previously: `guardian-orchestrator.md` became managed; `guardian.md`/`orchestrator.md` were not explicitly bounded.)

#### Scenario: Allowlist extends

- GIVEN the updated sync script
- WHEN `managed_prompt_names()` runs
- THEN it includes `orchestrator.md`
- AND the updated test asserts `guardian.md`/`orchestrator.md` are untouched

#### Scenario: Parity test updated in same change

- GIVEN the allowlist change
- WHEN the test suite runs
- THEN the updated sync tests pass
- AND no stale non-managed assertion fails

## ADDED Requirements

### Requirement: Skills Sync Discipline (REQ-822)

A sibling `sync_skills.py` MUST sync `ai/opencode/skills/` → `~/.config/opencode/skills/` with the same discipline as prompt sync: deterministic, idempotent, allowlist-based, `--dry-run`/`--check` modes, and repo-wins policy. Live hand-editing of synced skills is prohibited.

#### Scenario: Skills sync mirrors prompt sync

- GIVEN a repo skill edit under `ai/opencode/skills/`
- WHEN `sync_skills.py --check` runs
- THEN it reports drift if live differs from repo
- AND `sync_skills.py` would overwrite live with repo bytes

#### Scenario: Dry-run is safe

- GIVEN a repo skill edit
- WHEN `sync_skills.py --dry-run` runs
- THEN no live file is modified
- AND the report shows what would change

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | `orchestrator.md` appears in managed prompt allowlist |
| 2 | `deploy.md`/`monitor.md` absent from live after sync |
| 3 | `guardian.md`/`orchestrator.md` untouched by sync |
| 4 | Parity test passes with extended allowlist |
| 5 | `sync_skills.py` exists with `--check`/`--dry-run` and allowlist |

## Affected Files

| File | Change |
|------|--------|
| `ai/opencode/sync_prompts.py` | Allowlist add `orchestrator.md`; remove `deploy.md`/`monitor.md` |
| `ai/opencode/sync_skills.py` | New sibling sync script |
| `tests/campaign/test_prompt_sync.py` | Flip allowlist/parity tests; add skills-sync tests |
| `ai/opencode/agents/orchestrator.md` | New versioned router prompt |
| `ai/opencode/agents/deploy.md` | Retired to repo legacy |
| `ai/opencode/agents/monitor.md` | Retired to repo legacy |
