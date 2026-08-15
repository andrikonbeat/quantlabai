# Tasks: Orchestrated Subagent Wiring

## Review Workload Forecast

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1300 (F1 ~650, F2 ~340, F3 ~290) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 SDK core → PR2 prompts/sync → PR3 guardian-orchestrator |

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| WU1 | Real runner wiring | PR 1 (base: tracker) | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/test_delegation.py tests/campaign/test_phase_runner.py` | `SQX_FORCE_MOCK=1 python3 -m quantlab.cli campaign run-flow --json` mock loop | Revert `phase_runner.py`+registry; restore `_run_campaign.py` |
| WU2 | Prompt enrichment + sync | PR 2 (base PR1) | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/test_prompt_sync.py` | `python3 ai/opencode/sync_prompts.py --check` | Revert prompt edits; re-run sync |
| WU3 | Guardian-orchestrator | PR 3 (base PR2) | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/test_orchestrator_prompt.py tests/gates/test_run_flow_gates.py` | decision-file gate on `/tmp/sqx-gates`: approve vs hold | Remove JSON entry+routing row; revert allowlist/tests |

## WU1 — F1: Real Runner Wiring (PR 1)

- [x] 1.1 RED `tests/campaign/test_delegation.py`: registry completeness (`PRODUCTION_EXECUTORS.keys() == PHASES`); gap fails closed (`AuthorityViolationError`, no stage); mock intact (REQ-815/810)
- [x] 1.2 GREEN `sdk/quantlab/campaign/delegation.py`: `PRODUCTION_EXECUTORS` registry; resolution explicit→registry→mock→raise; export `__init__.py`
- [x] 1.3 RED `tests/campaign/test_delegation.py`: hybrid split — reasoning phases no handoff; mechanical `LongOpSpec` (log `/tmp/opencode`, timeout≥240, cleanup); retest conditional; live-ops folds `GuardianReport` (REQ-816)
- [x] 1.4 GREEN `delegation.py`: 14 executors via `STAGE_FOR_PHASE` → `PhaseResult`; archive→`archive` (REQ-815)
- [x] 1.5 RED `tests/campaign/test_phase_runner.py` (new): round-trip JSON→`PhaseResult`; unknown phase → `PhaseNotFoundError`; malformed JSON rejected; out-of-scope → no stage (REQ-818)
- [x] 1.6 GREEN `sdk/quantlab/campaign/phase_runner.py`: `build_directive`/`run`/`main` (`--phase`, `--directive`); handoff `/tmp/opencode`, timeout≥240, cleanup, per-phase report (D5)
- [x] 1.7 Delete `_run_campaign.py`; README note → `campaign run-flow` (REQ-817; `cmd_campaign_run_flow` sole entry)

## WU2 — F2: Prompt Enrichment + Sync (PR 2)

- [x] 2.1 RED `tests/campaign/test_prompt_sync.py`: `test_guardian_live_prompt_never_synced` — `guardian-orchestrator.md` IS managed; `guardian.md`/`orchestrator.md` untouched; allowlist-shape updated (REQ-821)
- [x] 2.2 GREEN `ai/opencode/sync_prompts.py`: `MANAGED_NAMES` adds `guardian-orchestrator.md` (managed = campaign.md + phase-*.md + guardian-orchestrator.md)
- [x] 2.3 GREEN 14 `ai/opencode/agents/phase-*.md`: `## Reasoning`+`## SDK Examples` — research→`LLMResearchAgent` KB; hypothesis→`hypothesis_builder/llm.py`; config→`BuilderAgent`; review→verdict; monitor→`LLMGenerationMonitor`; optimize→`OptimizerStage`; portfolio→`PortfolioComposer`; archive→`ArchivePhase`; mechanical 6→grounded (REQ-819); `edit:false, write:false` (REQ-820)
- [x] 2.4 Run `sync_prompts.py`; `--check` parity green

## WU3 — F3: Guardian-Orchestrator (PR 3)

- [ ] 3.1 RED `tests/test_orchestrator_prompt.py`: repo `guardian-orchestrator.md`; live JSON entry primary, visible, deny-first mirroring `quantlab-orchestrator`; GUARDIAN-LIVE row→task; alert/replacement allowlisted (REQ-822/823/825)
- [ ] 3.2 GREEN `guardian-orchestrator.md` (managed): Role, Routing, Delegates, Gates, NO-phase rule (REQ-37), long-run policy
- [ ] 3.3 GREEN live `opencode.json`: `guardian-orchestrator` (primary; bash `sdk/quantlab/*`,`knowledge/*`,`/tmp/opencode/*`; task `quantlab-guardian`/`-alert`/`quantlab-replacement`); delegates alert+replacement: subagent, hidden, inline (D10/D11)
- [ ] 3.4 GREEN live `orchestrator.md`: GUARDIAN-LIVE row → `guardian-orchestrator` via `task` (REQ-823; non-managed)
- [ ] 3.5 RED `tests/gates/test_run_flow_gates.py`: `HUMAN_APPROVE_REPLACEMENT` fail-closed — approve→allow; HOLD/missing/non-approve→block; never auto-replace (REQ-824)
- [ ] 3.6 GREEN gate: decision-file `/tmp/sqx-gates/{campaign_id}/` (`pending.json`→`decision.json`), `action==approve` only, reuses `DecisionsFileGateCallback` (D9)
- [ ] 3.7 Sync `guardian-orchestrator.md` live; parity `--check`; `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign tests/gates tests/test_orchestrator_prompt.py` (assert_flow still 14)
