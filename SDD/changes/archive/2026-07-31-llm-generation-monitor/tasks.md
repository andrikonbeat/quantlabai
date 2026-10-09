# Tasks: LLM Generation Monitor

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1050 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Core module + unit tests | PR 1 | `python3 -m pytest tests/phase4/test_llm_generation_monitor.py` | N/A — deps injected | Delete module + test file |
| 2 | Databank observ + mock rejection | PR 2 | `python3 -m pytest tests/phase4/ -k "databank or integration"` | MockSQXServer rejection mode | Revert campaign_monitor.py + mock diff |
| 3 | cli_wrapper hook + E2E | PR 3 | `python3 -m pytest tests/phase4/ -k e2e` | E2E dispatch(force_mock=True, llm_config, fake llm_caller) | Drop llm_config/on_llm_verdict params |

## Phase 1: Core module (sdk/quantlab/sqx/llm_generation_monitor.py)

- [x] 1.1 Define `Verdict` pydantic (Literal continue|stop, confidence 0–1) + `MonitorSnapshot` (status_text, generated, databank_counts|None, elapsed_s, baseline)
- [x] 1.2 `parse_verdict(raw)` — strip ```json fences, validate; invalid/missing/bad confidence → warn + None (continue)
- [x] 1.3 `build_prompt` — status + databank counts + baseline (generations, population, WF/MC, criteria) + JSON schema
- [x] 1.4 `ActionExecutor` — stop → `monitor.cancel()` + HTTP `-project action=stop name=<campaign>`; continue → no-op
- [x] 1.5 `_call_llm` — raw LLM call, existing agent pattern
- [x] 1.6 `LLMGenerationMonitor` — ctor (snapshot_provider, llm_config, llm_caller, circuit_breaker, confirm_stop, threshold=0.7, poll_every_n=5, on_verdict); N-th tick loop; gate; stop → confirm_stop → ActionExecutor; errors → continue
- [x] 1.7 Use `LLMCircuitBreaker.call`; catch CircuitOpenError → continue

## Phase 2: Observability (sdk/quantlab/sqx/campaign_monitor.py)

- [x] 2.1 `parse_databank_counts(text)` — `Results, Records: N` + colon variants; failure → None + log
- [x] 2.2 Poll `-databank action=list` in `_poll_tick`; store counts; tolerate failure; heuristic events unchanged
- [x] 2.3 `current_snapshot()` — status, generated, databank_counts, elapsed, baseline (compute_baseline)

## Phase 3: Wiring (sdk/quantlab/sqx/cli_wrapper.py)

- [x] 3.1 Add `llm_config`/`on_llm_verdict` params to `dispatch_campaign`, `_dispatch_real`, `_dispatch_mock`
- [x] 3.2 llm_config set → spawn monitor task beside CampaignMonitor (both paths, `current_snapshot` provider); None → prior behavior, zero LLM calls
- [x] 3.3 Wire `on_llm_verdict` → monitor `on_verdict`; stop path joins `monitor.cancel()`

## Phase 4: Mock + Tests

- [x] 4.1 `mock_sqx_server.py` rejection mode: growing generated count, static databank 0, never completes until `action=stop`
- [x] 4.2 Unit: parse_databank_counts (formats + garbage → None); build_prompt (counts/baseline/schema); parse_verdict (valid/fenced/invalid/missing → continue + warn)
- [x] 4.3 Unit: gate (0.65 vs 0.7 → no dispatch); ActionExecutor (stop → cancel+HTTP once; continue → no-op); circuit open (no exception, logged)
- [x] 4.4 Integration: fake llm_caller + rejection mode → stop + confirm True → HTTP stop; low confidence → nothing; LLM raising → heuristics still collect
- [x] 4.5 E2E: dispatch(force_mock=True, llm_config, llm_caller=fake) → stops before completion; no llm_config → zero LLM calls, identical result
- [x] 4.6 Full suite: `python3 -m pytest tests/ -q --tb=short`
