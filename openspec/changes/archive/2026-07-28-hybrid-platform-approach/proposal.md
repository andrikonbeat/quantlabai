# Proposal: Hybrid Platform Approach — OpenCode Integration + Dashboard

## Intent

Introduce a `quantlab-orchestrator` agent in OpenCode that routes SDD, CLI, and dashboard requests through domain-aware paths using `gentle-ai`'s Adapter + Orchestrator + Runner patterns.

## Scope

### In Scope (Phase 1)
- `quantlab-orchestrator` agent in `opencode.json` with permissions
- Agent prompt at `~/.config/opencode/prompts/quantlab/orchestrator.md` with skill resolver
- CLI bridge invoking existing `sqcli` and SDK pipeline commands
- Intent routing: SDD → `gentle-orchestrator`, CLI → `sqcli`, dashboard → Phase 2
- Permission model: destructive ops require approval

### Out of Scope (Phase 1)
- Dashboard UI / web interface (Phase 2)
- New SDK modules or changes to existing agent classes
- Multi-user tenancy, RBAC, real-time streaming

## Approach

Modeled on `gentle-ai`'s `Orchestrator` + `Runner` pipeline. `quantlab-orchestrator` uses `Adapter` (`internal/agents/interface.go`), `Orchestrator` Prepare/Apply stages (`internal/pipeline/orchestrator.go`), `Runner` + `FailurePolicy` (`internal/pipeline/runner.go`), `StagePlan` (`internal/pipeline/stages.go`), `ExecutionResult` (`internal/pipeline/result.go`), `SkillRegistry` (`internal/skillregistry/registry.go`), and `AgentFactory` (`internal/agents/factory.go`).

### Routing Logic

| Intent Pattern | Route | gentle-ai Reference |
|---|---|---|
| `sdd-*` verbs | `gentle-orchestrator` via `task` | `Orchestrator.Execute(StagePlan)` |
| `run campaign`, `deploy` | `quantlab` CLI | `Runner.Run(StageApply)` |
| `dashboard`, `UI` | Phase 2 queue | `StagePrepare` placeholder |
| `what does`, `explain` | CodeGraph + read | `Adapter.Detect()` → context |

## Technical Design

**Created:** `~/.config/opencode/prompts/quantlab/orchestrator.md`; `openspec/changes/hybrid-platform-approach/spec.md`.

**Modified:** `~/.config/opencode/opencode.json` (add `quantlab-orchestrator` agent); `openspec/config.yaml` (add agent context rules).

## Dependencies
- `gentle-orchestrator` registered in `opencode.json`
- `quantlab` CLI accessible (`sdk/quantlab/cli/` with campaign/stats commands)
- `sqcli` binary at `assets/SQX_144_2953_linux_20260601/sqcli`

## Success Criteria
- [ ] `quantlab-orchestrator` in `opencode.json` with correct permission scope
- [ ] Agent prompt routes SDD/CLI/dashboard requests correctly
- [ ] SDD requests delegate to `gentle-orchestrator` without error
- [ ] CLI requests execute `sqcli` commands and return results
- [ ] Dashboard requests queued with clear user response
- [ ] No new SDK modules or changes to existing agent classes
- [ ] Permission scope prevents destructive ops without user approval

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Permission explosion | Medium | Scoped permissions; `question: "allow"` for bash; audit after Phase 1 |
| Routing misclassification | Medium | Keyword matching first; refine after usage |
| Scope creep | High | Explicit out-of-scope; dashboard deferred; no new SDK modules |
| ResearchDirector duplication | Low | Agent dispatches to existing SDK; does not reimplement logic |

## Rollback Plan
1. Remove `quantlab-orchestrator` from `opencode.json`
2. Delete `~/.config/opencode/prompts/quantlab/orchestrator.md`
3. Revert `openspec/config.yaml` via git

## Phase 2 Preview
Phase 2 adds `dashboard-ui` — web dashboard served by `quantlab` CLI. Phase 1 CLI bridge becomes the API layer. `Adapter` interface (`internal/agents/interface.go`) extended with `Serve()` method for the dashboard adapter. All dashboard UI work out of scope for Phase 1.
