# skill-registry Specification

## Purpose

Skills sync contract: deterministic, idempotent, repo-wins synchronization of OpenCode skills from repo to live, with allowlist control and registry refresh.

## Requirements

### Requirement: Skills Sync Contract (REQ-901)

The system MUST provide a `sync_skills.py` that syncs `ai/opencode/skills/` → `~/.config/opencode/skills/` with repo-wins policy. Sync MUST be deterministic and idempotent, MUST use an explicit allowlist, MUST support `--dry-run` and `--check` modes, and MUST refresh the skill registry after sync. Live hand-editing of synced skills is prohibited.

#### Scenario: Repo-wins overwrites live

- GIVEN a live skill that differs from repo
- WHEN sync runs
- THEN the live copy is replaced with repo bytes

#### Scenario: --check reports drift without modifying

- GIVEN drifted live skills
- WHEN `sync_skills.py --check` runs
- THEN drift is reported
- AND no live file is modified

#### Scenario: Allowlist limits sync scope

- GIVEN an allowlist containing only `quantlab-*` skills
- WHEN sync runs
- THEN only matching skills are synced
- AND others are untouched

#### Scenario: Dry-run is safe

- GIVEN a repo skill edit
- WHEN `sync_skills.py --dry-run` runs
- THEN no live file is modified
- AND the report shows what would change

#### Scenario: Registry refresh order

- GIVEN a successful sync
- WHEN the registry refresh runs
- THEN the skill index reflects the synced state
- AND no stale entries remain

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | `sync_skills.py --check` reports drift without modifying |
| 2 | `sync_skills.py --dry-run` reports changes without modifying |
| 3 | Allowlist limits sync scope |
| 4 | Registry refresh follows sync |

## Affected Files

| File | Change |
|------|--------|
| `ai/opencode/sync_skills.py` | New deterministic idempotent sync |
| `ai/opencode/skills/quantlab-run-campaign/SKILL.md` | Deduped to pointer |
| `ai/opencode/skills/quantlab-deploy-strategy/SKILL.md` | New LLM-first rewrite |
| `ai/opencode/skills/quantlab-monitor-status/SKILL.md` | New LLM-first rewrite |
