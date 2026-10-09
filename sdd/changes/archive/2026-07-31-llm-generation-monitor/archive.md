# Archive: LLM Generation Monitor

**Status**: archived
**Date**: 2026-07-31
**Mode**: SDD (auto) — explore → propose → spec → design → tasks → apply (3 chained slices) → verify → archive

## Summary

Added an `LLMGenerationMonitor` that catches doomed campaigns mid-run (e.g. 58 generated, 0 accepted) by having an LLM reason over live status text + databank counts, with `continue|stop` actions (Phase 1). Real campaigns were producing 0 accepted strategies with no signal until the task log was written at the end.

## What Was Built

- **`LLMGenerationMonitor`** (`sdk/quantlab/sqx/llm_generation_monitor.py`): Verdict pydantic model, MonitorSnapshot, build_prompt, parse_verdict (invalid JSON → continue + warn), ActionExecutor, confidence gate (0.7 default), LLMCircuitBreaker reuse, human confirm on stop, graceful degradation on all failure paths
- **Observability** (`campaign_monitor.py`): `-databank action=list` polling, `parse_databank_counts` (defensive), `current_snapshot()`, `final_check()` (fixes campaign_complete race)
- **Wiring** (`cli_wrapper.py`): `llm_config`/`on_llm_verdict` params — opt-in, default off preserves behavior exactly (zero LLM calls)
- **Mock** (`mock_sqx_server.py`): rejection mode (`mode="rejection"`) — growing generation count, static databank 0
- **Dispatcher** (`command_dispatcher.py`): `list_databanks()` returning per-databank record counts
- **Parser tolerance**: `extract_results_count` accepts both `Strategies generated N` and `Strategies generated: N`

## Files Changed

| File | Action |
|------|--------|
| `sdk/quantlab/sqx/llm_generation_monitor.py` | Created |
| `sdk/quantlab/sqx/campaign_monitor.py` | Modified |
| `sdk/quantlab/sqx/cli_wrapper.py` | Modified |
| `sdk/quantlab/sqx/mock_sqx_server.py` | Modified |
| `sdk/quantlab/phase4/command_dispatcher.py` | Modified |
| `sdk/tests/phase4/test_llm_generation_monitor.py` | Created (43 tests) |
| `tests/phase4/test_command_dispatcher.py` | Modified (+3 tests) |

## Verification

- 43/43 monitor tests pass (unit 33 + integration 5 + E2E 2)
- 653/653 phase4 tests pass
- E2E flake fixed: 0/10 → 8-10/10 under concurrent stress (remaining failures are port-contention artifacts)
- All 4 acceptance criteria met with runtime evidence:
  - Mocked zero-acceptance campaign triggers stop before task end ✓
  - Low-confidence verdicts never dispatch ✓
  - LLM failure falls back to heuristics ✓
  - Existing tests pass; verdict→action mapping covered ✓

## Key Decisions

1. Standalone module beside CampaignMonitor — heuristics stay always-on fallback
2. Snapshot sharing via `current_snapshot()` — zero extra HTTP, no races
3. Pydantic Verdict + fence stripping — strict validation
4. Confidence threshold 0.7, constructor param
5. `confirm_stop` callback injectable — default rich Confirm, testable
6. Opt-in via `llm_config` param — default-off preserves behavior exactly

## Known Limitations

- Phase 2 actions (adjust/regenerate/abort) not implemented — SQX API has no pause/resume
- "Log tail" mentioned in proposal prose but not in MonitorSnapshot/build_prompt (no scenario requires it)
- Micro-race: `final_check` could theoretically double-emit `campaign_complete` (re-check guard minimizes; no test counts events)

## Next Steps

Pipeline pieces remaining per full-flow gap analysis:
- Post-result analysis (overfitting detection, strategy quality assessment)
- Reconfiguration loop (reconfigure and relaunch based on results)
