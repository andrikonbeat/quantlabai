# Tasks: Per-Phase Sub-Agent Delegation

Cmd: `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q <files> --tb=short`

## Review Workload Forecast

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

1. **PR 1 (~220)** — canonical prompts + sync + parity. Test: `prompt_sync flow_integrity orchestrator_prompt`. Harness: `sync --check`. Rollback: revert merge.
2. **PR 2 (~350)** — registry 7 + judgment prompts. Test: `orchestrator_prompt prompt_sync`. Harness: task-smoke. Rollback: revert registry.
3. **PR 3 (~290)** — registry 7 + routing. Test: `orchestrator_prompt`. Harness: `run campaign`. Rollback: revert notes.
4. **PR 4 (~390)** — delegation glue + envelope. Test: `campaign/test_delegation`. Harness: execute_phase. Rollback: revert glue.
5. **PR 5 (~250)** — gates + loop + integrity. Test: `campaign/ orchestrator_prompt`. Harness: mock e2e. Rollback: revert gates.

## PR 1 — Prompts + sync + parity

- [x] 1.1 Merge live guardian delegation into `AI/opencode/agents/campaign.md`; preserve REQ-104/203-205 + `PHASES = (...)` (parsed by `_doc_phases`). REQ-806/804.
- [x] 1.2 Create `AI/opencode/sync_prompts.py`: sorted allowlist `campaign.md`+`phase-*.md`, byte copy, idempotent, `--dry-run`/`--check`, non-managed files untouched. REQ-806.
- [x] 1.3 Create `tests/campaign/test_prompt_sync.py`: idempotency, parity, non-managed ignored, drift names file — RED on drift; sync → green. REQ-807/810.

## PR 2 — Registry 7 + judgment prompts

- [ ] 2a.1 Register `quantlab-phase-{research,hypothesis,review,retest,optimize,portfolio,dispatch}` in `~/.config/opencode/opencode.json`: subagent; prompt ref; perms `{"question":"allow","task":{"*":"deny","quantlab-*":"allow"}}`; bash `pipeline/*`+`campaign/*`. Names = PHASES ids verbatim. REQ-805/808/812/813.
- [ ] 2a.2 Create 6 full prompts (research/hypothesis/review/retest/optimize/portfolio) + thin dispatch. Skeleton: bounded authority (no flow.py/gate-skip/long-op waits), gate protocol, Result Contract; full prompts add glue calls + SDK examples. REQ-805/809.
- [ ] 2a.3 Extend `tests/test_orchestrator_prompt.py` (never replace): 7 registrations, mode, deny-first, prompt refs. REQ-805/808/810.

## PR 3 — Registry 7 + routing

- [ ] 2b.1 Register `quantlab-phase-{config,monitor,compile,deploy,demo,archive,live-ops}` (same deny-first shape). REQ-805/808.
- [ ] 2b.2 Create 7 thin prompts; only live-ops delegates (→ `quantlab-guardian`); none wait on long ops. REQ-805/809.
- [ ] 2b.3 REQ-814 note in live `orchestrator.md`: CAMPAIGN → quantlab-campaign; no direct phase routing; long ops on orchestrator shell. REQ-814/809.
- [ ] 2b.4 `campaign.md` delegation map: task `quantlab-phase-<phase>` in PHASES order; no inline fallback (fold mechanics in PR 5). REQ-811.
- [ ] 2b.5 Extend tests: 14 registrations == PHASES; routing-note + map asserts. REQ-814/811/810.

## PR 4 — Delegation glue

- [ ] 3a.1 RED `tests/campaign/test_delegation.py`: envelope; unknown phase rejected; `status!=success` halts; authority violation; long-op script no-wait; `PHASE_AGENTS==PHASES`; `validate_phase_result()`. REQ-801-804/809.
- [ ] 3a.2 Create `sdk/quantlab/campaign/delegation.py`: frozen `PhaseDirective`/`PhaseResult` (Result Contract + phase_id/evidence/handoff_payload); `PHASE_AGENTS` from PHASES; `execute_phase()` validate → scope-check → envelope; long op → script spec `{command, log_path, expected, timeout>=240, cleanup}`; alias guard (`substrate/executor`, `phase4/models`). REQ-801-804/809.
- [ ] 3a.3 Re-export in `sdk/quantlab/campaign/__init__.py`. Non-goal: no flow.py/agents/ changes.

## PR 5 — Gates + loop + integrity

- [ ] 3b.1 `research_director.py`: wire HUMAN_APPROVE_ARCHIVE interceptor on archive `pending_gate` (`phase4/campaign_archive.py`); DEMO stays fail-closed. MOD REQ-38/REQ-11.
- [ ] 3b.2 `campaign.md` loop rewrite: fold each PhaseResult before next dispatch; failure halts; no inline long ops; no inline fallback. REQ-01/811/802.
- [ ] 3b.3 Extend `test_flow_integrity.py`/`test_flow_segments.py`: `PHASE_AGENTS` keys == PHASES; asserts unchanged. REQ-804/810.
- [ ] 3b.4 Extend e2e: dispatch order == PHASES; SQX_FORCE_MOCK intact. REQ-810/811.

## Non-Goals

No flow.py PHASES mutation (REQ-37); no `agents/` re-arch; no phase/gate changes; sync never deletes non-managed files.
