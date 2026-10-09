# Tasks: Hybrid Platform Approach — Phase 1

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~120–180 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Create orchestrator prompt with routing + skill resolver | PR 1 | `grep -c "sdd-\*" prompts/quantlab/orchestrator.md` | Read prompt; verify routing rules | Delete prompt + revert opencode.json |
| 2 | Register quantlab-orchestrator in opencode.json | PR 1 | `python3 -c "import json; d=json.load(open(opencode.json)); assert 'quantlab-orchestrator' in d['agent']"` | Validate JSON; verify agent entry | Revert opencode.json |

## Phase 1: Foundation (Config + Prompt)

- [x] 1.1 Create `openspec/config.yaml` with agent context rules for `quantlab-orchestrator` — routing config (SDD → gentle-orchestrator, CLI → sqcli, dashboard → Phase 2 queue), permission scope, sqcli path resolution [effort: small]
- [x] 1.2 Create `~/.config/opencode/prompts/quantlab/orchestrator.md` with `## Skills to load before work` (all 6 SDD skills), intent routing (SDD → `gentle-orchestrator` via `task`, CLI → `sqcli` subprocess, dashboard → Phase 2 queue, knowledge → CodeGraph + read), sqcli contract (path resolution: explicit → env → error, 300s timeout, structured result), permission model (destructive ops require `question: "allow"`, sensitive file denial) [effort: medium]

## Phase 2: Integration (opencode.json + Wiring)

- [ ] 2.1 Modify `~/.config/opencode/opencode.json` — add `quantlab-orchestrator` under `agent` with `mode: subagent`, description, prompt `{file:~/.config/opencode/prompts/quantlab/orchestrator.md}`, scoped permissions (`question: "allow"`, task for `gentle-orchestrator` and `sdd-*`), tools (`bash`, `edit`, `read`, `write`, `task`, `question`) [effort: small]
- [ ] 2.2 Wire intent routing in prompt — SDD verbs route to `gentle-orchestrator` via `task`; CLI patterns (`run campaign`, `deploy`, `sqcli`) route to `sqcli`; dashboard/UI queue for Phase 2; knowledge patterns route to CodeGraph + read; unknown SDD verb returns "Unknown SDD verb: {verb}" [effort: medium]

## Phase 3: Testing / Verification

- [ ] 3.1 Verify sqcli path resolution — explicit path, env fallback (`SQCLI_PATH`), missing binary error [effort: small]
- [ ] 3.2 Verify intent classification — each routing rule (SDD, CLI, dashboard, knowledge); unknown SDD verb rejection [effort: small]
- [ ] 3.3 Verify permission model — destructive bash triggers `question: "allow"`; project-scoped edits and SDK pipeline commands run without approval; sensitive file reads outside project denied [effort: medium]
- [ ] 3.4 Verify skill resolver — prompt contains `## Skills to load before work` listing all 6 SDD skills [effort: small]
- [ ] 3.5 E2E: SDD delegation — invoke `sdd-propose`, verify `task(gentle-orchestrator)` called with original message forwarded [effort: medium]

## Phase 4: Cleanup / Documentation

- [ ] 4.1 Verify rollback — remove `quantlab-orchestrator` from `opencode.json`, delete prompt file, revert `openspec/config.yaml` via git; confirm pre-change state restored [effort: small]