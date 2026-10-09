# Design: Hybrid Platform Approach — OpenCode Integration (Phase 1)

## Technical Approach

Introduce `quantlab-orchestrator` as a subagent in OpenCode that routes SDD, CLI, and dashboard intents through domain-aware paths. It delegates SDD work to `gentle-orchestrator` via `task`, invokes `sqcli` for CLI operations, and queues dashboard requests for Phase 2. The design follows `gentle-ai`'s Adapter + Orchestrator + Runner patterns. Skill resolution follows the `skill-resolver.md` protocol before delegation.

## Architecture Decisions

| # | Decision | Tradeoff | Rationale |
|---|----------|----------|-----------|
| 1 | `mode: subagent` | vs `primary` — subagent has isolated context | Prevents inheriting gentle-orchestrator's SDD workflow state; each delegation gets fresh context per skill-resolver protocol |
| 2 | `question: "allow"` for bash, scoped task permissions | vs open bash | Matches permission-model spec: destructive bash requires approval, project-scoped ops auto-approve |
| 3 | Keyword matching for intent classification | vs ML classifier | Simpler, auditable, no training data needed. Matches routing spec scenarios |
| 4 | `sqcli` at explicit path | vs PATH lookup | Explicit path ensures reproducibility; `SQCLI_PATH` env is the fallback |
| 5 | Prompt file at `~/.config/opencode/prompts/quantlab/orchestrator.md` | vs inline prompt | File-based allows versioning and reuse; matches quantlab-orchestrator spec |
| 6 | No new SDK modules or agent class changes | vs extending SDK | Explicit out-of-scope; CLI bridge uses existing `sdk/quantlab/pipeline/` interface only |

## Data Flow

```
User message → quantlab-orchestrator → classify (keyword match) → route → execute → return result

SDD:    task(gentle-orchestrator) → Orchestrator.Execute(StagePlan) → Prepare(skill resolution) → Apply(delegation)
CLI:    Runner.Run(StageApply, [sqcli]) → resolve path → execute 300s timeout → {exit_code, stdout, stderr, duration_ms}
DASHBOARD: "queued for Phase 2"
KNOWLEDGE: codegraph_explore → read relevant files
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `~/.config/opencode/opencode.json` | Modify | Add `quantlab-orchestrator` entry under `agent` key |
| `~/.config/opencode/prompts/quantlab/orchestrator.md` | Create | Agent prompt with skill resolver, routing rules, delegation instructions |

## Interfaces / Contracts

### opencode.json agent entry

```json
"quantlab-orchestrator": {
  "mode": "subagent",
  "description": "QuantLab orchestrator - routes SDD, CLI, and dashboard intents",
  "prompt": "{file:~/.config/opencode/prompts/quantlab/orchestrator.md}",
  "permission": {
    "question": "allow",
    "task": { "*": "deny", "gentle-orchestrator": "allow", "sdd-*": "allow" }
  },
  "tools": { "bash": true, "edit": true, "read": true, "write": true, "task": true, "question": true }
}
```

### sqcli invocation contract

- Path resolution: `assets/SQX_144_2953_linux_20260601/sqcli` → `SQCLI_PATH` env → error
- Timeout: 300s default
- Args: `key=value` pairs as separate subprocess arguments; spaces preserved in quoted values
- Result: `{exit_code, stdout, stderr, duration_ms}`

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Intent classification | Test each routing rule: SDD → gentle-orchestrator, CLI → sqcli, dashboard → Phase 2, knowledge → CodeGraph |
| Integration | sqcli path resolution & execution | Test resolution order (explicit → env → error), timeout enforcement, structured result format |
| Integration | Permission model | Test `rm`/`git push --force` trigger `question: "allow"`, project-scoped edits and SDK pipeline commands do not |
| E2E | Full SDD delegation | Invoke with `sdd-propose` intent, verify `task(gentle-orchestrator)` called with original message forwarded |
| E2E | Skill resolver directive | Verify `## Skills to load before work` lists all 6 SDD skills (sdd-spec through sdd-archive) |

## Threat Matrix

| Boundary | Minimum adversarial cases | Applicability | Design response | Planned RED tests |
|---|---|---|---|---|
| Shell commands (sqcli) | Malformed args, missing binary, timeout | Applicable | Path resolution with fallback; 300s timeout; structured error on non-zero exit | One test per resolution path (explicit, env, missing) |
| Routing / intent classification | Unrecognized SDD verb, ambiguous keyword | Applicable | Unknown SDD verb returns explicit error; keyword matching first | Test unknown verb rejection; test each routing rule |
| Permission escalation | Destructive bash via CLI bridge, file read outside project | Applicable | `question: "allow"` for destructive ops; deny reads of `**/.env*`, `**/*.pem`, `**/.ssh/**` | Test destructive flagging; test sensitive file denial |
| Subprocess execution | sqcli hangs, non-zero exit, binary output | Applicable | Timeout termination; non-zero → error result; stdout/stderr captured as text | Test timeout, error exit, binary output handling |
| PR / VCS automation | N/A | N/A — no VCS/PR automation in Phase 1 | No tasks or tests required | — |
| Executable-file classification | N/A | N/A — sqcli path is explicit | No tasks or tests required | — |

## Migration / Rollback

1. Remove `quantlab-orchestrator` from `opencode.json`
2. Delete prompt file
3. Revert `openspec/config.yaml` via git

## Open Questions

- [ ] How does `gentle-orchestrator` handle `quantlab-orchestrator` as a caller — does it need a new task permission entry?
