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
  - `ruff` and `mypy` come from the `dev` extra (`pip install -e "sdk[dev]"`), so
    they are available locally as well as in CI. `pytest-asyncio` is required
    too — root `pytest.ini` sets `asyncio_mode = auto`.
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
- The canonical order lives in `PHASES` at `sdk/quantlab/campaign/flow.py:33` and is mirrored in `ai/opencode/agents/campaign.md` (a test extracts the literal from the prompt and compares it to the tuple).
- **What is actually enforced in production:** exactly one call site — `assert_flow_segments()` at `sdk/quantlab/cli/campaign_commands.py:272`, run at the start of `campaign run-flow` *before* any stage executes. A dropped, reordered, or boundary-violating phase aborts the run with a non-zero exit.
- **What is not enforced at runtime:** `ResearchDirector.build_pipeline()` (`sdk/quantlab/agents/research_director.py:222`) performs no flow assertion, and the strict `assert_flow()` (exact 14-phase equality) has no production call site — only tests. There is no post-harness-change assertion hook. If you add a flow-affecting change, the tests in `tests/campaign/test_flow_integrity.py` and `tests/campaign/test_flow_segments.py` are what currently guard the invariant.

### Decision-File Gates
- Human gates use lossless blocking-prompt discipline: present the complete envelope, accept exactly one answer, and re-present + STOP on missing or invalid input.
- Auto-approval is prohibited. Unanswered gates fail closed.
- The registry of enforced gates is `DEFAULT_GATE_POLICIES` at `sdk/quantlab/gates/models.py`. It defines exactly nine: `HUMAN_REVIEW_OBJECTIVES`, `HUMAN_APPROVE_CONFIG`, `HUMAN_APPROVE_ITERATION`, `HUMAN_APPROVE_PORTFOLIO`, `HUMAN_APPROVE_DEPLOY`, `HUMAN_APPROVE_DEMO`, `HUMAN_APPROVE_ARCHIVE`, `HUMAN_REVIEW_PERFORMANCE`, `HUMAN_APPROVE_REPLACEMENT`. `HUMAN_GATE_IDS` is derived from its keys, so the two cannot drift.
- `README.md` documents the four that always block a dispatch (`HUMAN_APPROVE_CONFIG`, `HUMAN_APPROVE_DEPLOY`, `HUMAN_APPROVE_DEMO`, `HUMAN_APPROVE_ARCHIVE`).
- `HUMAN_APPROVE_REPLACEMENT` is registered with `fallback=ABORT`, so an unanswered live-replacement request aborts the Guardian loop instead of auto-approving. `CONTINUE` is the only fallback that resolves to `GateDecisionAction.APPROVE`, so it is never acceptable on this gate.
- ⚠️ Registering a policy is **not** the same as wiring a live block. `HUMAN_APPROVE_REPLACEMENT` has a registered policy but is still not a `build_pipeline` stage, so no prompt-blocking stage is injected by it. Do not rely on it for a deploy-time block; do rely on it when a Guardian path resolves the gate through `HumanGateOrchestrator.on_gate()`, which will fail closed with `ABORT`.

### Result Contract
Every phase or subagent result must conform to this envelope. `PhaseResult`
(`sdk/quantlab/campaign/delegation.py:77`) has **six required** fields and two
optional ones; `validate_phase_result()` (`delegation.py:684`) rejects an empty
`status`, `executive_summary`, or `phase_id`, and a `phase_id` that is not in
`PHASES`.

```json
{
  "phase_id": "research",
  "status": "success | failed | partial",
  "executive_summary": "one or two sentences",
  "artifacts": ["paths or keys"],
  "next_recommended": "next phase",
  "risks": ["risk notes"],
  "evidence": { "optional": "per-phase audit data" },
  "handoff_payload": null
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `phase_id` | yes | Must be non-empty **and** a member of `PHASES`; `delegation.py:703` raises `ValueError("PhaseResult.phase_id must be non-empty")`. |
| `status` | yes | `success`, `failed`, or `partial`. Anything other than `success` halts folding. |
| `executive_summary` | yes | Must be non-empty. |
| `artifacts` | yes | Must be a list. |
| `next_recommended` | yes | The gatekeeper checks it against the expected next phase. |
| `risks` | yes | Must be a list. |
| `evidence` | no | Defaults to `{}`. Per-phase audit data. |
| `handoff_payload` | no | Defaults to `null`. Shape for orchestrator-shell long ops: `command`, `log_path`, `expected`, `timeout` (>= 240), `cleanup`. |

### SDD Workflow
- SDD artifacts live under `sdd/changes/<change-name>/`. The convention is `proposal.md`, `design.md`, `tasks.md`, and one or more capability specs at `specs/<capability>/spec.md` — note there is no top-level `spec.md`.
- **Not every active change carries the full set.** A change that stops at an earlier phase legitimately has only part of it. As of this writing, 1 of 10 active changes has no `proposal.md`, and 2 have no `specs/` directory yet. Do not treat a missing artifact as a bug; read `tasks.md` and `apply-progress.md` to learn how far the change actually got.
- A change is complete when it reports `archive-report.md` **and** `verify-report.md`; it then moves to `sdd/changes/archive/YYYY-MM-DD-<slug>/` via `git mv`. A `research-agent-enhancements`-style `archive-report.md` that is scoped to "planning artifacts only" is **not** completion — check its stated implementation count.
- Progress is tracked in `apply-progress.md` and Engram topic `sdd/<change-name>/apply-progress`.
- Work units are kept reviewable: ≤400 changed lines when possible; chained PRs use stacked-to-main by default.
- Rollback boundary for each work unit is explicit and must be revertible without touching unrelated work.
