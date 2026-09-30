# QuantLab AI — Project Agents Contract

## Stack

- **Language**: Python 3.11+ (local `.venv` 3.14.4; CI pins 3.11)
- **SDK**: `quantlab` (pydantic, pandas, numpy, httpx, mcp, openai)
- **External tools**: StrategyQuant X (`sqcli` CLI, `.cfx` config), JForex 4, Dukascopy-only data, JCloud deployment
- **Architecture**: AI-directed research engine — OpenCode as research director, SQX as computation engine. 14-phase campaign lifecycle: research → hypothesis → config → review → dispatch → monitor → retest → optimize → portfolio → compile → deploy → demo → archive → live-ops.

## Testing Conventions

- **Runner**: `pytest` (root `pytest.ini`, testpaths `tests` + `sdk/tests`, `asyncio_mode=auto`)
- **Full suite**: `SQX_FORCE_MOCK=1 python3 -m pytest -q`
  - `SQX_FORCE_MOCK=1` is required to avoid binding the real SQX daemon on port 5050.
  - Local `.venv` does not install `ruff` or `mypy`; they run in CI only.
- **Focused tests**: prefer the smallest meaningful path, e.g. `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/` or `sdk/tests/<path>`.
- **TDD**: Strict TDD is active. RED-first cycle enforced in apply phases: write failing test → make it pass → refactor. Do not skip the RED step.

## Harness Conventions

### Sync Contract
- Prompts and skills are managed by deterministic sync scripts (`sync_prompts.py`, `sync_skills.py`).
- Repo-wins policy: the repo copy is authoritative. Live copies under `~/.config/opencode/` are generated artifacts; hand-editing live prompts or skills is prohibited.
- Sync scripts support `--dry-run`, `--check`, and allowlist-based scoping. Retired files are actively removed from live.

### 14-Phase Flow (REQ-37)
- Campaign flow retains all 14 phases plus the Guardian live flow, in order.
- Each phase is gated by human confirmation.
- Simplification applies only to code/infrastructure; no phase may be removed, reordered, merged, or auto-approved.
- The REQ-37 invariant is asserted at campaign start, CLI run-flow start, and after any harness change.

### Decision-File Gates
- Human gates use lossless blocking-prompt discipline: present the complete envelope, accept exactly one answer, and re-present + STOP on missing or invalid input.
- Auto-approval is prohibited.
- Gates include `HUMAN_APPROVE_DEPLOY`, `HUMAN_APPROVE_DEMO`, `HUMAN_APPROVE_ARCHIVE`, and `HUMAN_APPROVE_REPLACEMENT` (fail-closed semantics).

### Result Contract
Every phase or subagent result must conform to this envelope:

```json
{
  "status": "success | failed | partial",
  "executive_summary": "one or two sentences",
  "artifacts": ["paths or keys"],
  "next_recommended": "next phase",
  "risks": ["risk notes"]
}
```

### OpenSpec Workflow
- SDD artifacts live under `openspec/changes/<change-name>/`: `proposal.md`, `spec.md`, `design.md`, `tasks.md`.
- Progress is tracked in `apply-progress.md` and Engram topic `sdd/<change-name>/apply-progress`.
- Work units are kept reviewable: ≤400 changed lines when possible; chained PRs use stacked-to-main by default.
- Rollback boundary for each work unit is explicit and must be revertible without touching unrelated work.
