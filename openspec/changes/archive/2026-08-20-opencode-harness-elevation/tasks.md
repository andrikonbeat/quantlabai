# Tasks: OpenCode Harness Elevation

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 900+ |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | Unit A (chained) → Unit B → Unit C (chained) → Unit D → Unit E |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| A | Sync extension + test flips + thin skills + retire | PR A1 / PR A2 | SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/test_prompt_sync.py | N/A — CI parity gate | Revert allowlist + delete sync_skills.py + remove new skills |
| B | Repo-root AGENTS.md | PR B | SQX_FORCE_MOCK=1 python3 -m pytest -q | N/A — doc-only | Delete AGENTS.md |
| C | Campaign contract — gatekeeper + lossless gates | PR C1 / PR C2 | SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/ | N/A — mock phase flow | Revert campaign.md + phase-*.md + guardian edits |
| D | Review lifecycle docs | PR D | N/A — doc-only | N/A — doc-only | Delete review-lifecycle.md |
| E | Model assignments | PR E | N/A — config-only | N/A — config-only | Revert model keys in opencode.json |

## Phase 1: Foundation

### Unit A
- [x] 1.1 Create `ai/opencode/sync_common.py` with `SyncDriver`.
- [x] 1.2 Modify `ai/opencode/sync_prompts.py` allowlist: add `orchestrator.md`, remove `deploy.md`/`monitor.md`.
- [x] 1.3 RED: test `orchestrator.md` managed, `guardian.md` untouched, retired files absent.
- [x] 1.4 GREEN: flip `tests/campaign/test_prompt_sync.py` for REQ-821.
- [x] 1.5 RED: test `sync_skills.py --check`/`--dry-run` drift reporting.
- [x] 1.6 GREEN: create `ai/opencode/sync_skills.py`.
- [x] 1.7 Create `ai/opencode/agents/orchestrator.md` versioned router prompt.
- [x] 1.8 Create retired `ai/opencode/agents/deploy.md` and `monitor.md`.
- [x] 1.9 Create `quantlab-deploy-strategy` and `quantlab-monitor-status` skill rewrites.
- [x] 1.10 Dedupe `quantlab-run-campaign` SKILL.md to pointer.
- [x] 1.11 Run `SQX_FORCE_MOCK=1 python3 -m pytest -q` to verify Unit A.

### Unit B
- [x] 2.1 Create `AGENTS.md` with stack, testing, harness, OpenSpec workflow.
- [x] 2.2 Verify no test regressions.

### Unit C
- [x] 3.1 RED: test gatekeeper envelope validation and exactly-once re-run.
- [x] 3.2 GREEN: add post-phase gatekeeper to `ai/opencode/agents/campaign.md`.
- [x] 3.3 RED: test lossless gate exact-one answer and re-present + STOP.
- [x] 3.4 GREEN: add lossless gate protocol to `campaign.md` and `guardian-orchestrator.md`.
- [x] 3.5 Add lossless gate sections to all 15 `phase-*.md` files.
- [x] 3.6 Run `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/` to verify Unit C.

### Unit D
- [x] 4.1 Create `docs/guides/review-lifecycle.md` with 4R envelope, stop-reason table, `repair --preflight`.
- [x] 4.2 Verify doc structure.

### Unit E
- [x] 5.1 Add `model: "opencode/deepseek-v4-flash-free"` to all QuantLab agents in `opencode.json`.
- [x] 5.2 Verify `default_agent` intact.
