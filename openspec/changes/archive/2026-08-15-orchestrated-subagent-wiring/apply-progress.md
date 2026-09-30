# Apply Progress — orchestrated-subagent-wiring

**Change**: `orchestrated-subagent-wiring`
**Phase**: apply (WU1/F1 + WU2/F2) — tasks 1.1–1.7 + 2.1–2.4
**Mode**: Strict TDD (`SQX_FORCE_MOCK=1 python3 -m pytest -q <path>`)
**Artifact store**: openspec + engram (both)
**Delivery**: auto-chain / feature-branch-chain — PR 1 (feature/tracker base) done; PR 2 (base PR1 branch) = WU2
**Status**: 11/18 tasks complete (WU1 7/7, WU2 4/4) — WU3 (F3) pending

## Task Status

- [x] 1.1 Add `PRODUCTION_EXECUTORS` registry and `PhaseExecutor` to `sdk/quantlab/campaign/delegation.py`
- [x] 1.2 Export `PRODUCTION_EXECUTORS` (+ `PhaseExecutor`) from `sdk/quantlab/campaign/__init__.py`
- [x] 1.3 Add hybrid delegation split (REQ-816) — reasoning/mechanical/retest/live-ops executors
- [x] 1.4 Update `execute_phase` resolution: explicit → registry → mock → deny-first raise (REQ-815 s2)
- [x] 1.5 Add `sdk/quantlab/campaign/phase_runner.py` CLI bridge (REQ-818)
- [x] 1.6 Green focused suite — `tests/campaign/test_delegation.py` + `tests/campaign/test_phase_runner.py`
- [x] 1.7 Retire `_run_campaign.py` (REQ-817) + README migration note to `campaign run-flow`

## Work Unit Evidence (WU1)

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/test_delegation.py tests/campaign/test_phase_runner.py` → **61 passed, 1 warning in 1.85s**; broader `tests/campaign` + `tests/gates` → **142 passed** |
| Runtime harness command/scenario and exact result | `python3 sdk/quantlab/campaign/phase_runner.py --phase <name> --directive '<json>'`: research → success envelope (`research_llm`), dispatch → `LongOpSpec` handoff + `/tmp/opencode/dispatch.report.md` written; error paths exit 1 with JSON envelope (unknown phase / malformed JSON / forbidden scope `mutate flow.py`). `campaign run-flow` mock loop: research-stage failure is **pre-existing at HEAD** (proven in a clean worktree — identical `"failed": "research"`); WU1 code is not on the run-flow path (F2/F3 wiring is later work) |
| Rollback boundary | All WU1 changes are confined to `sdk/quantlab/campaign/` (delegation.py, `__init__.py`, new phase_runner.py), `_run_campaign.py` (deleted — recoverable via `git restore --source=<parent> _run_campaign.py` or revert of commit 3), and `README.md` migration note. Unrelated dirty files (.env.example, app_movil/*, docs/STATE.md, openspec/config.yaml, dsl/models.py, dsl tests) were never staged. Reverting commits 1–3 restores the pre-WU1 tree |

## TDD Cycle Evidence

| Task | RED (test first) | GREEN (impl passes) | REFACTOR |
|---|---|---|---|
| 1.1 registry + PhaseExecutor | `test_registry_covers_every_phase`, `test_registry_has_fourteen_executors` (collection error: `PRODUCTION_EXECUTORS` missing) | 61 passed — registry built from `PHASES` | `_build_production_executors()` factory keeps the dict immutable by construction |
| 1.3 hybrid split | `TestHybridDelegationSplit` (reasoning never hands off / mechanical hands off / retest conditional / live-ops guardian report) | 61 passed — all split tests green | Mechanical executor parametrized per phase; `_retest_executor` reuses both paths |
| 1.4 resolution order | `test_registry_executor_takes_precedence_over_mock` (renamed from mock-only test with objectives payload) | 61 passed — registry checked before mock | Scope check stays deny-first before executor resolution |
| 1.5 phase_runner bridge | `tests/campaign/test_phase_runner.py` (collection error: module missing) | 61 passed — `TestBuildDirective`/`TestRun`/`TestMain` (14 tests) | `main()` factors `run()` so tests exercise the async path; report writer separate |
| 1.7 retire + migration | — (doc/deletion, no test) | README migration note; sweep clean (only historical exploration record + note itself) | Deletion via `git rm` |

## Deviations from Design

1. **D4 sweep classification**: the only remaining `_run_campaign.py` references are the intentional README migration note and a historical exploration record in `openspec/changes/llm-generation-monitor/exploration.md` (an unrelated, non-archived change's planning artifact — classified as non-live per D4; editing it would falsify a historical record).
2. **Pre-existing run-flow research failure**: `campaign run-flow` mock loop fails at the research stage ("Cannot determine market from objective: 'Research'") because `cmd_campaign_run_flow` builds a `PipelineContext` without `objectives`/`market_context`. Proven pre-existing at HEAD via a clean worktree. Not caused by WU1; the run-flow path does not consume `PRODUCTION_EXECUTORS`/`phase_runner` yet (F2/F3 wiring is later work). Flagged for verify/review; harness evidence above records the exact behavior.
3. **Existing mock test adapted**: `test_mock_executor_available_when_force_mock` renamed `test_registry_executor_takes_precedence_over_mock` with objectives payload (`["Research EURUSD H1"]`) — classic `ResearchAgent._parse_objective` raises ValueError on the default "Research" objective, so the success-asserting test must feed a market-bearing objective.

## Issues Found

- Classic `ResearchAgent._parse_objective` raises `ValueError` for objectives without an explicit market; reasoning executors convert stage failures into `status="failed"` envelopes (REQ-802), never into crashes.
- `quantlab.analysis.frame` is a gitignored local file — a clean worktree lacks it, so harness comparisons must copy it (provenance recorded for the baseline proof).
- No further issues — implementation matches the design elsewhere.

## Files Changed

| File | Action | What Was Done |
|---|---|---|
| `sdk/quantlab/campaign/delegation.py` | Modified | `PRODUCTION_EXECUTORS` registry (14 executors), `PhaseExecutor` type, `_stage_name_for_phase`, `_get_stage_registry`, `_run_sdk_stage`, `_json_safe`, `_next_phase_id`, reasoning/mechanical/retest/live-ops executors, `run_stage_for_handoff`, resolution-order update in `execute_phase` |
| `sdk/quantlab/campaign/phase_runner.py` | Created | REQ-818 CLI bridge: `build_directive`/`run`/`main`, `_write_report` to `/tmp/opencode/{phase}.report.md`, error envelopes exit 1 |
| `sdk/quantlab/campaign/__init__.py` | Modified | Export `PRODUCTION_EXECUTORS` + `PhaseExecutor` |
| `tests/campaign/test_delegation.py` | Modified | Registry + hybrid split test classes; renamed mock-precedence test |
| `tests/campaign/test_phase_runner.py` | Created | `TestBuildDirective`/`TestRun`/`TestMain` (14 tests) |
| `_run_campaign.py` | Deleted | REQ-817 retirement (via `git rm`) |
| `README.md` | Modified | Migration note: legacy `_run_campaign.py` → `campaign run-flow` (REQ-817) |
| `openspec/changes/orchestrated-subagent-wiring/apply-progress.md` | Created | This artifact |

## Workload / PR Boundary

- Mode: chained PR slice (feature-branch-chain, PR 1 → feature/tracker)
- Current work unit: WU1/F1 — registry + hybrid delegation + phase_runner bridge + retirement
- Boundary: starts at `execute_phase` resolution and `PRODUCTION_EXECUTORS`; ends with `_run_campaign.py` retirement and README migration. F2 (agent wiring of executor→phase subagent) and F3 (harness integration) are later work units.
- Estimated review budget impact: ~470 changed lines across 3 commits (registry/delegation ~380, phase_runner ~130, tests ~330, README + deletion). Split into 3 reviewable commits per work-unit-commits; each commit keeps tests green.

---

# WU2 — F2: Prompt Enrichment + Sync (PR 2)

**Phase**: apply (WU2/F2) — tasks 2.1–2.4
**Mode**: Strict TDD (`SQX_FORCE_MOCK=1 python3 -m pytest -q <path>`)
**Status**: 4/4 tasks complete

## Task Status

- [x] 2.1 RED `tests/campaign/test_prompt_sync.py`: `test_guardian_live_prompt_never_synced` — `guardian-orchestrator.md` IS managed; `guardian.md`/`orchestrator.md` untouched; allowlist-shape updated (REQ-821)
- [x] 2.2 GREEN `ai/opencode/sync_prompts.py`: `MANAGED_NAMES` adds `guardian-orchestrator.md` (managed = campaign.md + phase-*.md + guardian-orchestrator.md)
- [x] 2.3 GREEN 14 `ai/opencode/agents/phase-*.md`: `## Reasoning`+`## SDK Examples` per REQ-819 map; `edit:false, write:false` boundary (REQ-820)
- [x] 2.4 Run `sync_prompts.py`; `--check` parity green

## Work Unit Evidence (WU2)

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/test_prompt_sync.py` → **12 passed** (baseline 11; +1 new `test_guardian_orchestrator_allowlisted`); broader `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign` → **101 passed, 1 warning** |
| Runtime harness command/scenario and exact result | `python3 ai/opencode/sync_prompts.py` → `updated (14): phase-archive.md … phase-review.md` (live copies pushed); `python3 ai/opencode/sync_prompts.py --check` → `parity ok` (exit 0), re-run idempotent. Live `~/.config/opencode/prompts/quantlab/` now byte-identical to repo canonical for all managed prompts; `guardian.md`/`orchestrator.md` live files untouched (non-managed, REQ-821) |
| Rollback boundary | Prompt edits confined to `ai/opencode/agents/phase-*.md` (revert commit `4a52cb6` + re-run sync restores live bytes); allowlist change in `ai/opencode/sync_prompts.py` (revert `ca069e1`); test contract in `tests/campaign/test_prompt_sync.py` (revert `e4c81ed`). Live copies are regenerable from repo canonical (REQ-806). Unrelated dirty files (.env.example, app_movil/*, docs/STATE.md, openspec/config.yaml, dsl/models.py, dsl tests, repo-root opencode.json) never staged |

## TDD Cycle Evidence (WU2)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 2.1 sync contract test | `tests/campaign/test_prompt_sync.py` | Unit | ✅ 11/11 baseline | ✅ Written — 3 failing (`guardian-orchestrator.md` absent from allowlist) | ✅ 12 passed | ✅ 3 cases (allowlisted name; sync propagates; guardian.md/orchestrator.md untouched) | ✅ Clean — vacuous loop removed from allowlist-shape test |
| 2.2 allowlist extension | `tests/campaign/test_prompt_sync.py` | Unit | ✅ (from 2.1) | ✅ Written (2.1 RED covers) | ✅ 12 passed | ✅ via 2.1 cases (temp-repo allowlist + sync propagation) | ✅ Clean — `managed_prompt_names` filters to repo-present names |
| 2.3 14 prompt enrichment | `tests/campaign/test_prompt_sync.py` (parity) | Integration | ✅ 12/12 | ✅ Structure contract verified by grep across all 14 (Reasoning=1, SDK Examples=1, REQ-820 line=1 each); sync tests assert byte propagation | ✅ 12 passed; broader 101 passed | ➖ Single — content change, verified by sync parity + live-parity tests | ✅ Clean — uniform section shape across prompts |
| 2.4 sync + parity | `tests/campaign/test_prompt_sync.py` | Integration | ✅ 12/12 | N/A (operational step) | ✅ `parity ok`; 12 passed; 101 passed | ➖ Single | ✅ Clean — idempotent re-check |

## Deviations from Design

1. **`managed_prompt_names` filters to repo-present names** (D7 nuance): `MANAGED_NAMES` registers the `guardian-orchestrator.md` family constant, but the resolved allowlist omits names without a repo copy — `ai/opencode/agents/guardian-orchestrator.md` is created in WU3. This keeps `test_every_managed_repo_prompt_has_byte_equal_live_copy` green before the file exists; allowlist inclusion is asserted via a temp repo (`test_guardian_orchestrator_allowlisted`). When WU3 creates the file, the allowlist automatically includes it.
2. **Monitor class naming**: REQ-819 maps monitor→`CampaignMonitor`/`LLMGenerationMonitor`; the design F2 table says `CampaignMonitor`/`ExecutionMonitor`. Prompt Reasoning + SDK Examples cover BOTH (stall diagnosis via `LLMGenerationMonitor`, fail-closed HOLD semantics via `ExecutionMonitor` for the `execution_monitor` stage) — REQ-819 authoritative.
3. **Vacuous loop removed** from `test_non_managed_live_prompts_outside_allowlist` (`assert name in managed or name not in managed` is a tautology — banned by strict-TDD assertion rules); the 3-family allowlist-shape assertion is the real contract, with the dedicated guardian test covering the boundary.
4. **SDK examples corrected to real APIs** discovered during grounding: monitor (`CampaignMonitor(campaign_id, base_url, baseline)` + `LLMGenerationMonitor(snapshot_provider=…)`), deploy (`DeploymentAgent(dry_run=True).run(ctx)`), config (`BuilderAgent.run(ctx)`), research (`LLMResearchAgent.generate_config(objectives, market_context, llm_config)`), hypothesis (`LLMMode(llm_config).build(hyp)`).

## Issues Found

- The two `TestLiveParity` failures mid-WU2 (after prompt edits, before sync) were the EXPECTED REQ-806 sync-miss drift — repo canonical edited ahead of live copies; resolved by running the sync script (task 2.4). Not a defect; it is the contract the parity tests enforce.
- No further issues — implementation matches the design elsewhere.

## Files Changed (WU2)

| File | Action | What Was Done |
|---|---|---|
| `tests/campaign/test_prompt_sync.py` | Modified | REQ-821 contract: `test_guardian_live_prompt_never_synced` now asserts `guardian-orchestrator.md` IS managed while `guardian.md`/`orchestrator.md` stay untouched; new `test_guardian_orchestrator_allowlisted`; allowlist-shape assertion → 3 managed families (commit `e4c81ed`) |
| `ai/opencode/sync_prompts.py` | Modified | `MANAGED_NAMES` += `guardian-orchestrator.md`; `managed_prompt_names` seeds from all constants + phase glob, filtered to repo-present names (commit `ca069e1`) |
| `ai/opencode/agents/phase-*.md` (14) | Modified | `## Reasoning` + `## SDK Examples` per REQ-819 mapping; REQ-820 artifact boundary (`edit:false, write:false`) in every prompt (commit `4a52cb6`) |
| `~/.config/opencode/prompts/quantlab/phase-*.md` (14) | Modified (live, outside VCS) | Synced byte-exact from repo canonical (REQ-806); `--check` parity ok |
| `openspec/changes/orchestrated-subagent-wiring/apply-progress.md` | Modified | This artifact (WU1 merged + WU2 appended) |
| `openspec/changes/orchestrated-subagent-wiring/tasks.md` | Modified | WU2 tasks 2.1–2.4 marked `[x]` |

## Workload / PR Boundary (WU2)

- Mode: chained PR slice (feature-branch-chain, PR 2 → PR 1's branch, i.e. `feat/per-phase-subagent-delegation-pr5`)
- Current work unit: WU2/F2 — prompt enrichment + sync contract
- Boundary: starts at the sync-allowlist contract test; ends with live parity (`--check` ok) after the 14-prompt enrichment. WU3 (guardian-orchestrator prompt + live JSON wiring + replacement gate) is the next work unit.
- Estimated review budget impact: ~430 changed lines across 4 commits (test contract 52, sync.py 27, 14 prompts 349, SDD artifacts ~40); each commit keeps its own tests green except the parity window between the prompt commit and the sync run (documented REQ-806 behavior).

---

# WU3 — F3: Guardian-Orchestrator (PR 3)

**Phase**: apply (WU3/F3) — tasks 3.1–3.7
**Mode**: Strict TDD (`SQX_FORCE_MOCK=1 python3 -m pytest -q <path>`)
**Status**: 7/7 tasks complete

## Task Status

- [x] 3.1 RED `tests/test_orchestrator_prompt.py`: repo `guardian-orchestrator.md`; live JSON entry primary, visible, deny-first mirroring `quantlab-orchestrator`; GUARDIAN-LIVE row→task; alert/replacement allowlisted (REQ-822/823/825)
- [x] 3.2 GREEN `guardian-orchestrator.md` (managed): Role, Routing, Delegates, Gates, NO-phase rule (REQ-37), long-run policy
- [x] 3.3 GREEN live `opencode.json`: `guardian-orchestrator` (primary; bash `sdk/quantlab/*`,`knowledge/*`,`/tmp/opencode/*`; task `quantlab-guardian`/`-alert`/`quantlab-replacement`); delegates alert+replacement: subagent, hidden, inline (D10/D11)
- [x] 3.4 GREEN live `orchestrator.md`: GUARDIAN-LIVE row → `guardian-orchestrator` via `task` (REQ-823; non-managed)
- [x] 3.5 RED `tests/gates/test_run_flow_gates.py`: `HUMAN_APPROVE_REPLACEMENT` fail-closed — approve→allow; HOLD/missing/non-approve→block; never auto-replace (REQ-824)
- [x] 3.6 GREEN gate: decision-file `/tmp/sqx-gates/{campaign_id}/` (`pending.json`→`decision.json`), `action==approve` only, reuses `DecisionsFileGateCallback` (D9). This gate lives in the GUARDIAN DOMAIN, not the run-flow gate loop (REQ-37 protection) — confirm placement.
- [x] 3.7 Sync `guardian-orchestrator.md` live; parity `--check`; `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign tests/gates tests/test_orchestrator_prompt.py` (assert_flow still 14)

## Work Unit Evidence (WU3)

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/test_orchestrator_prompt.py tests/gates/test_run_flow_gates.py tests/campaign` → **208 passed, 1 warning**; broader `tests/campaign tests/gates tests/test_orchestrator_prompt.py tests/guardian` → **258 passed** |
| Runtime harness command/scenario and exact result | `python3 ai/opencode/sync_prompts.py` → `updated (1): guardian-orchestrator.md`; `python3 ai/opencode/sync_prompts.py --check` → `parity ok` (exit 0). Live `~/.config/opencode/prompts/quantlab/guardian-orchestrator.md` now byte-identical to repo canonical. Live `~/.config/opencode/opencode.json` updated with guardian-orchestrator + delegates. Live `~/.config/opencode/prompts/quantlab/orchestrator.md` updated with GUARDIAN-LIVE routing row. |
| Rollback boundary | WU3 changes are confined to `ai/opencode/agents/guardian-orchestrator.md` (new managed prompt), `~/.config/opencode/opencode.json` (live agent entries), `~/.config/opencode/prompts/quantlab/orchestrator.md` (live routing row), `tests/test_orchestrator_prompt.py` (1 test fix + WU3 contract tests), `tests/gates/test_run_flow_gates.py` (6 new replacement-gate tests), `openspec/changes/orchestrated-subagent-wiring/tasks.md` (WU3 checkboxes). Live config edits are outside VCS and recorded here for rollback. Reverting the live edits removes the guardian-orchestrator surface without affecting WU1/WU2 code. |

## TDD Cycle Evidence (WU3)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 3.1 orchestrator prompt tests | `tests/test_orchestrator_prompt.py` | Integration | ✅ 56 passed (WU1/WU2 baseline) | ✅ 19 failing (prompt absent, JSON missing, routing absent) | ✅ 59 passed — prompt + JSON + routing implemented | ➖ Single — test contract fixed for impossible assertion | ✅ Clean — fixed `quantlab-orchestrator` tautology in routing-row test |
| 3.2 guardian-orchestrator prompt | `tests/test_orchestrator_prompt.py` | Integration | ✅ (from 3.1) | ✅ Written (3.1 RED covers) | ✅ 59 passed | ➖ Single | ✅ Clean — prompt matches design D8/D10/D11 |
| 3.3 live opencode.json | `tests/test_orchestrator_prompt.py` | Integration | ✅ (from 3.1) | ✅ Written (3.1 RED covers) | ✅ 59 passed | ➖ Single | ✅ Clean — deny-first perms mirror quantlab-orchestrator |
| 3.4 live orchestrator.md | `tests/test_orchestrator_prompt.py` | Integration | ✅ (from 3.1) | ✅ Written (3.1 RED covers) | ✅ 59 passed | ➖ Single | ✅ Clean — GUARDIAN-LIVE row added without disturbing existing routes |
| 3.5 replacement gate tests | `tests/gates/test_run_flow_gates.py` | Unit | ✅ 16 passed (baseline) | ✅ 5 written (approve, hold, missing, reject, missing-file) | ✅ 22 passed — `DecisionsFileGateCallback` generic for any gate_id | ➖ Single — callback is generic; new gate_id proves reuse | ✅ Clean — no callback changes needed |
| 3.6 gate placement confirm | `tests/gates/test_run_flow_gates.py` | Unit | ✅ (from 3.5) | ✅ 1 written (`HUMAN_APPROVE_REPLACEMENT` not in `DEFAULT_GATE_POLICIES`) | ✅ 22 passed — confirms guardian-domain placement | ➖ Single | ✅ Clean — placement confirmed, no run-flow modification |
| 3.7 sync + parity + suite | `tests/test_orchestrator_prompt.py` | Integration | ✅ 59 passed | N/A (operational step) | ✅ 208 passed; 258 passed (incl. guardian tests) | ➖ Single | ✅ Clean — parity ok, idempotent |

## Deviations from Design

1. **Test assertion fix in `test_guardian_live_row_does_not_replace_guardian_row`**: the original test asserted `"quantlab-orchestrator" not in text` over the entire orchestrator prompt — impossible because the file IS the `quantlab-orchestrator` prompt. Fixed to assert `"guardian-orchestrator" in text`, preserving the intent that GUARDIAN-LIVE routes to the second orchestrator, not to `quantlab-orchestrator` as its target.
2. **Task 3.6 placement confirmation**: no new Python code was required because `DecisionsFileGateCallback` is already generic and `HUMAN_APPROVE_REPLACEMENT` is already absent from `DEFAULT_GATE_POLICIES` and `research_director.py` pipeline stages. The GREEN step is the test confirming guardian-domain placement.

## Issues Found

- None — implementation matches the design elsewhere. All 258 focused tests pass.

## Files Changed

| File | Action | What Was Done |
|---|---|---|
| `ai/opencode/agents/guardian-orchestrator.md` | Created | Managed prompt: Role, Routing, Delegates, Gates, NO-phase rule, long-run policy, Result Contract (REQ-822/823/824/825) |
| `~/.config/opencode/opencode.json` | Modified (live, outside VCS) | Added `guardian-orchestrator` (primary, visible, deny-first), `quantlab-guardian-alert` (hidden subagent, inline), `quantlab-replacement` (hidden subagent, inline); updated `quantlab-orchestrator` task allowlist |
| `~/.config/opencode/prompts/quantlab/orchestrator.md` | Modified (live, non-managed) | Added GUARDIAN-LIVE routing row → `guardian-orchestrator` via `task` (REQ-823) |
| `tests/test_orchestrator_prompt.py` | Modified | Fixed tautological assertion in `test_guardian_live_row_does_not_replace_guardian_row`; WU3 contract tests now 59/59 green |
| `tests/gates/test_run_flow_gates.py` | Modified | Added `TestHumanApproveReplacementGate` (5 fail-closed cases) + `TestReplacementGatePlacement` (guardian-domain confirmation) |
| `~/.config/opencode/prompts/quantlab/guardian-orchestrator.md` | Modified (live, outside VCS) | Synced byte-exact from repo canonical via `sync_prompts.py` |
| `openspec/changes/orchestrated-subagent-wiring/tasks.md` | Modified | WU3 tasks 3.1–3.7 marked `[x]` |
| `openspec/changes/orchestrated-subagent-wiring/apply-progress.md` | Modified | This artifact (WU1 + WU2 + WU3 merged) |

## Live Config Rollback Notes

- `~/.config/opencode/opencode.json`: remove `guardian-orchestrator`, `quantlab-guardian-alert`, `quantlab-replacement` entries; remove `guardian-orchestrator`, `quantlab-guardian-alert`, `quantlab-replacement` from `quantlab-orchestrator` task allowlist.
- `~/.config/opencode/prompts/quantlab/orchestrator.md`: remove the GUARDIAN-LIVE routing row.
- `~/.config/opencode/prompts/quantlab/guardian-orchestrator.md`: will be regenerated from repo canonical on next sync; deleting the live file is safe because it is a managed prompt.

## Workload / PR Boundary (WU3)

- Mode: chained PR slice (feature-branch-chain, PR 3 → PR 2's branch, i.e. `feat/per-phase-subagent-delegation-pr5`)
- Current work unit: WU3/F3 — guardian-orchestrator prompt + live JSON wiring + replacement gate
- Boundary: starts at the guardian-orchestrator managed prompt; ends with live parity (`--check` ok) after GUARDIAN-LIVE routing row and replacement gate tests. All 18 tasks across WU1+WU2+WU3 are complete.
- Estimated review budget impact: ~290 changed lines across prompt + live config + tests; within the 400-line budget for PR 3.

## Test Summary

- **Total tests in focused suite**: 208 passed
- **Total tests in broader guardian suite**: 258 passed
- **assert_flow**: still 14 phases (verified by existing tests)
- **Layers used**: Integration (orchestrator prompt + live config), Unit (gate callback + placement)
