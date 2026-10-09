# Apply Progress: Phase 5 — Pipeline Core & Campaign Orchestrator Refactor

## State

**IMPLEMENTED (33/36)** — phases 1-2 verified in earlier audit; phases 3-6 re-verified at
close: orchestrator refactor, exceptions, DaemonContext, CLI and test files all exist with
direct evidence. 3 tasks recorded as gaps (4.3 metric, 6.4, 6.7). Archived.

## Progress

| Task | Status | Evidence |
|------|--------|----------|
| 1.1–1.6 pipeline core module | ✅ | `pipeline/{__init__,base,models,runner,_stages}.py`; zero SQX imports |
| 2.1–2.10 SQX stage implementations | ✅ | `phase4/stages/__init__.py` (13 classes, 18.1K); SQXReportStage delegate at :475-512 |
| 3.1 orchestrator builds Pipeline + delegates | ✅ | `campaign_orchestrator.py:41-45,161,304` |
| 3.2 public exports preserved | ✅ | `phase4/__init__.py:102,112`; 657 phase4 tests green |
| 3.3 progress callbacks | ✅ | `campaign_orchestrator.py:110,222,267-268` |
| 3.4 dry-run path | ✅ | Smoke: `pipeline run --dry-run` green |
| 3.5 re-exports unchanged | ✅ | Backcompat suite 657 passed |
| 4.1 exception hierarchy | ✅ | `tools/exceptions.py:90,104,119` |
| 4.2 DaemonContext | ✅ | `cli/daemon.py`; exported in `cli/__init__.py` |
| 4.3 boilerplate ≥60% metric | ❌ not measured | Follow-up |
| 5.1 pipeline subcommand | ✅ | run/list/history wired (smoke-proven) |
| 5.2 `pipeline run <yaml>` | ✅ | Smoke dry-run path |
| 5.3 `pipeline status` | ✅ as `history` | `cli/pipeline_commands.py:352,359`; spec amended AD-pipe-1 |
| 5.4 `pipeline list` | ✅ | Module docstring :3 |
| 5.5 YAML stage registry | ✅ | `pipeline/registry.py` mapping + yaml parse |
| 6.1 test_pipeline_base.py | ✅ | Exists 6.8K |
| 6.2 test_pipeline_runner.py | ✅ | Exists 2.2K |
| 6.3 test_pipeline_stages | ✅ as `contracts` | `test_pipeline_contracts.py` 8.0K (naming drift) |
| 6.4 test_phase4_stages.py | ❌ | Not created; integration coverage via smoke/full_pipeline |
| 6.5 orchestrator backcompat | ✅ | Phase4 suite 657 passed (supersedes 436 estimate) |
| 6.6 test_cli_pipeline | ✅ as `pipeline_cli` | `test_pipeline_cli.py` 12.0K (naming drift) |
| 6.7 test_daemon_context.py | ❌ | Not created; DaemonContext covered indirectly |

## Re-verification Findings (2026-10-07 close)

1. **Phases 3-5 fully implemented despite unchecked tasks** — the orchestrator already
   delegates to `PipelineRunner` (`:161,:304`), exceptions and DaemonContext exist, and the
   CLI smoke-proves run/list/history. Checkboxes never marked during implementation; realigned
   at close with path:line evidence.
2. **`pipeline status` shipped as `pipeline history`** — cmd_pipeline_history (`:352`) with
   status filter (`:359`). Registered spec fixed via amendment AD-pipe-1 (like HS-REQ-05 in
   health-score); shipped CLI naming wins.
3. **Test-file naming drift persists across this change**: `test_pipeline_stages` → 
   `test_pipeline_contracts.py`; `test_cli_pipeline` → `test_pipeline_cli.py`. Content exists
   under different names.
4. **Two dedicated SQX-phase test files never created** (6.4) and no DaemonContext unit file
   (6.7) — behavior covered integrationally; recorded as follow-ups, not marked done.
5. **Backcompat evidence stronger than the plan**: 657 phase4 tests pass (plan estimated 436).

## Test Evidence

- Full suite: **4100 passed / 51 failed / 29 skipped** (fails = pre-existing prompt-sync drift,
  live-sqcli cfx/compiler, windows-naming — none in pipeline/orchestrator areas)
- Phase4 area: 657 passed; smoke: 1 passed 1.24s

## Next Action

Archived as `archive/2026-10-07-phase5-pipeline-core/` (follow-ups: 4.3, 6.4, 6.7).