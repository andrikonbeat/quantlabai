# Proposal: OpenCode Harness Elevation

## Intent

QuantLab's harness lags gentle-ai prompt discipline: unversioned router prompts, drifted skills, no gatekeeping/lossless gates/4R docs, thin skills, no model policy. Reach gentle-ai parity across 8 items, versioned and repo-managed.

## Scope

### In Scope
1. Version `orchestrator.md` in repo; extend `sync_prompts.py` allowlist; retire `deploy.md`/`monitor.md` from live, absorb into skills (item 7); flip REQ-821 tests same change.
2. Sibling `sync_skills.py` mirroring sync discipline (deterministic, idempotent, allowlist, --dry-run/--check); repo-wins policy.
3. Repo-root `AGENTS.md` (stack, testing, harness conventions).
4. Post-phase gatekeeper in `campaign.md` (contract/artifact/drift/routing checks; exactly-once rerun, then stop).
5. Lossless gate discipline across `campaign.md`, 15 `phase-*.md`, `guardian-orchestrator.md` (exact-one answer, re-present + STOP).
6. `docs/guides/review-lifecycle.md` (4R consent envelope, stop-reason table, `repair --preflight` reference).
7. Thin-skill LLM-first rewrites for `quantlab-deploy-strategy` and `quantlab-monitor-status`; repo copies under `ai/opencode/skills/`; dedupe `quantlab-run-campaign` skill to pointer.
8. `model: "opencode/deepseek-v4-flash-free"` on every QuantLab agent in repo `opencode.json`; no split.

### Out of Scope
RDD enable/repair (user-owned); CI parity job (deferred); global-config edits (repo overrides instead); live hand-editing of synced prompts/skills.

## Capabilities

> This section is the CONTRACT between proposal and specs phases.

### New Capabilities
- `skills-sync`: allowlist sync `ai/opencode/skills/` → `~/.config/opencode/skills/`; repo-wins; dry-run/check.
- `post-phase-gatekeeper`: contract conformance, artifact read-back, no-hallucination, no-input-drift, routing coherence, exactly-once corrective re-run.

### Modified Capabilities
- `campaign-phase-agents`: REQ-821 — `orchestrator.md` added to managed allowlist; `deploy.md`/`monitor.md` retired from live; tests flipped same change.
- `campaign-orchestrator`: REQ-01 — gatekeeper loop added; REQ-37 preflight restored.
- `human-gates`: REQ-38/REQ-11 — lossless discipline (exact-one, re-present, STOP).
- `guardian-orchestrator`: REQ-824 — lossless replacement gate.
- `campaign-phase-delegation`: REQ-802 — gatekeeper validates `PhaseResult` envelope plus artifact/drift.
- `documentation`: ADDED repo-root `AGENTS.md` + `review-lifecycle.md` requirements.

## Approach

(a) Sync extension + test flips + thin skills + deploy/monitor retirement as one work unit. (b) Repo `AGENTS.md`. (c) Gatekeeper + lossless gates as one campaign-contract work unit with `campaign.md` canonical and skill deduped to pointer. (d) Review lifecycle docs. (e) Model assignments in repo `opencode.json`. Gentle-ai patterns: sibling `sync_skills.py`, consent-envelope lossless gates, Automatic Mode Gatekeeper, LLM-first skill format.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `ai/opencode/sync_prompts.py` | Modified | Allowlist add `orchestrator.md`/`deploy.md`/`monitor.md`; flip REQ-821 tests |
| `ai/opencode/sync_skills.py` | New | Sibling deterministic idempotent sync with allowlist, dry-run, check |
| `ai/opencode/agents/orchestrator.md` | New | Versioned router prompt (bound to `agent.quantlab-orchestrator`) |
| `ai/opencode/agents/deploy.md` | New | Retired from live; versioned as legacy in repo |
| `ai/opencode/agents/monitor.md` | New | Retired from live; versioned as legacy in repo |
| `ai/opencode/agents/campaign.md` | Modified | Gatekeeper loop; lossless gate protocol; canonical contract |
| `ai/opencode/agents/guardian-orchestrator.md` | Modified | Lossless replacement gate |
| `ai/opencode/agents/phase-*.md` (15) | Modified | Lossless gate sections |
| `ai/opencode/skills/quantlab-run-campaign/SKILL.md` | Modified | Restore preflight parity; dedupe to pointer |
| `ai/opencode/skills/quantlab-deploy-strategy/SKILL.md` | New | LLM-first rewrite |
| `ai/opencode/skills/quantlab-monitor-status/SKILL.md` | New | LLM-first rewrite |
| `AGENTS.md` | New | Repo-root technical English contract |
| `docs/guides/review-lifecycle.md` | New | 4R review for SDK changes |
| `opencode.json` | Modified | `model` on all QuantLab agents |
| `tests/campaign/test_prompt_sync.py` | Modified | Flip allowlist/parity tests; add skills-sync tests |
| `openspec/specs/` (6 deltas) | Modified | REQ-821, REQ-01, REQ-37, REQ-38, REQ-802, REQ-824, new skills-sync/gatekeeper/review reqs |

## Decision Log

| # | Decision |
|---|----------|
| D1 | `opencode/deepseek-v4-flash-free` on ALL QuantLab agents (no split). |
| D2 | `deploy.md`/`monitor.md` retired from live; versioned as legacy in repo; content absorbed into skills. |
| D3 | `campaign.md` is canonical; `quantlab-run-campaign` SKILL.md deduped to frontmatter + gates + pointer. |
| D4 | Repo-wins sync policy; live hand-editing of synced prompts/skills prohibited. |
| D5 | RDD mode stays off; this change only documents the 4R lifecycle. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Delta vs test-flip drift | Med | Same work unit |
| Live hand-edit silently reverted | Med | No-hand-edit contract documented |
| Agent-block merge semantics | Med | Validate in design |
| 400-line budget (8 items) | High | 5 chained work units |
| Orphaned router prompts | Low | Explicitly versioned as legacy in repo |

## Rollback Plan

Revert allowlist + test flips; delete `sync_skills.py` and live copies; git-revert prompt edits and re-sync; remove model keys from `opencode.json`; delete new docs/skills/AGENTS.md.

## Dependencies

Agent-block merge semantics validated in design phase; live `~/.config/opencode/` present at apply.

## Success Criteria

- [ ] Both `sync_prompts.py --check` and `sync_skills.py --check` pass; parity green.
- [ ] Live `quantlab-run-campaign` skill restored to repo parity (`assert_flow_segments` present).
- [ ] Gatekeeper re-runs a failed phase exactly once, then stops and reports.
- [ ] Gates reject zero/multiple answers; re-present complete envelope.
- [ ] Model on all 19 QuantLab agents; `default_agent` intact.

## Work Units

(a) sync + flips + thin skills + retirement → (b) AGENTS.md → (c) campaign contract → (d) review docs → (e) model assignments.
