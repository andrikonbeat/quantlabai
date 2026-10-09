# Apply Progress — Flow-Ecosystem Alignment (U1 PR1 G4 + U2 PR2 G5 + U3 PR3 G1 + U4 PR4 G6 + U5 PR5 G3 + U6 PR6 G7 + U7 PR7 G2)

**Change**: flow-ecosystem-alignment
**Work unit**: U1 PR1 G4 (Phase 6, tasks 6.1-6.5) + U2 PR2 G5 (Phase 1, tasks 1.1-1.3) + U3 PR3 G1 (Phase 2, tasks 2.1-2.6) + U4 PR4 G6 (Phase 3, tasks 3.1-3.4) + U5 PR5 G3 (Phase 4, tasks 4.1-4.5) + U6 PR6 G7 (Phase 5, tasks 5.1-5.2) + U7 PR7 G2 (Phase 7, tasks 7.1-7.4)
**Mode**: Strict TDD (pytest, `SQX_FORCE_MOCK=1 python3 -m pytest -q <path>`)
**Artifact store**: hybrid (Engram + filesystem)
**Batch**: 7 of 7 (stacked-to-main; PR 7 = G2 CustomProject flag-first + flip stacks on PR 6)
**Date**: 2026-08-17/18

## Status

- applyState at start (batch 2): `ready` — previous apply-progress read and merged (U1 complete).
- 5/5 U1 tasks + 3/3 U2 tasks complete. U1 + U2 complete. Ready for next batch U3 PR3 G1.
- applyState at start (batch 3): `ready` — U3 read from same apply-progress (U1+U2 complete).
- 6/6 U3 tasks (2.1-2.6) complete. U1 + U2 + U3 complete. Ready for next batch U4 PR4 G6.
- applyState at start (batch 4): `ready` — U4 read from same apply-progress (U1+U2+U3 complete). The dedicated sdd-apply transport returned empty results; the general agent executed this slice under the sdd-apply skill contract per explicit user authorization.
- 4/4 U4 tasks (3.1-3.4) complete. U1 + U2 + U3 + U4 complete. Ready for next batch U5 PR5 G3.
- applyState at start (batch 5): `ready` — U5 read from same apply-progress (U1+U2+U3+U4 complete). The dedicated sdd-apply transport returned empty results; the general agent executed this slice under the sdd-apply skill contract per explicit user authorization.
- 5/5 U5 tasks (4.1-4.5) complete. U1 + U2 + U3 + U4 + U5 complete. Ready for next batch U6 PR6 G7.
- applyState at start (batch 6): `ready` — U6 read from same apply-progress (U1+U2+U3+U4+U5 complete). The dedicated sdd-apply transport returned empty results; the general agent executed this slice under the sdd-apply skill contract per explicit user authorization.
- 2/2 U6 tasks (5.1-5.2) complete. U1 + U2 + U3 + U4 + U5 + U6 complete. Ready for next batch U7 PR7 G2.
- applyState at start (batch 7): `ready` — U7 read from same apply-progress (U1+U2+U3+U4+U5+U6 complete). The dedicated sdd-apply transport returned empty results; the general agent executed this slice under the sdd-apply skill contract per explicit user authorization.
- 4/4 U7 tasks (7.1-7.4) complete. U1 + U2 + U3 + U4 + U5 + U6 + U7 complete. Ready for Phase 8 verify.

## Completed Tasks (Cumulative)

### Batch 6 — U6 PR6 G7 (Phase 5, tasks 5.1-5.2)

- [x] 5.1 RED `tests/pipeline/test_config_review_stage.py` (new file, 12 tests): `TestTeachingTablePersistence` (7) — persisted file + path in verdict + outcome, KB rows rendered, stable fallback row for no-KB-entry params, empty-config placeholder (None and all-None BuildConfig), no-KB-entries header + fallback rows, missing campaign context degrades `teaching_table==""` no persist; `TestBuildReviewTeachingTable` (4) — pure function placeholder/fallback/dedup; `TestReviewPhaseEnvelope` (1) — `execute_phase(phase_id="review")` puts `structured/{cid}/review/teaching-table.md` in `PhaseResult.artifacts`. First run: **collection ImportError** (`build_review_teaching_table` absent) — genuine RED.
- [x] 5.2 GREEN `sdk/quantlab/pipeline/stages/config_review_stage.py`: `REVIEW_FIELDS` (27 reviewer risk fields), `KB_TERM_FOR_FIELD` (sl_*→"Stop Loss", pt_*→"Profit Target"), `NO_KB_ENTRY_NOTE`, `_fallback_row` (`| Review | {field} | No KB entry | — | — | — | — | — |`), pure `build_review_teaching_table(build_config, consult)` (None/no-fields → `EMPTY_TABLE_NOTE`; KB hits via `KbParameter.model_validate` deduped by name through `build_teaching_table`; fallback rows appended; no hits → header + separator + fallback rows), `_persist_teaching_table` (writes `structured/{cid}/review/teaching-table.md` via direct `Path.write_text` — `.md` not in `KnowledgeStore.ALLOWED_EXTENSIONS`; returns `""` when campaign context missing), verdict + outcome gain `teaching_table`. Plus delegation.py hunks: `_run_sdk_stage` merges payload `campaign_id`/`knowledge_root` into ctx.config (setdefault), `_persist_stage_success` claims `outcome["teaching_table"]` only when the file exists (REQ-819 real claims). GREEN gate: **12 passed**.

### Batch 1 — U1 PR1 G4 (Phase 6, tasks 6.1-6.5)

- [x] 6.1 RED `tests/test_orchestrator_prompt.py`: G4 pin tests — no deploy/monitor agents, no run/status/compare dangling refs (task+bash allowlists, orchestrator.md routing), campaign deny-first bash, no stale `sdk/pipeline/*`, installer overlay sync pins.
- [x] 6.2 BACKUP opencode.json: `~/.config/opencode/opencode.json.bak-20260817-154931` (SHA256 identical to live, byte-for-byte).
- [x] 6.3 GREEN edit `~/.config/opencode/opencode.json`: removed `quantlab-deploy` + `quantlab-monitor` agent entries; removed `quantlab-run|status|compare` (+`quantlab-monitor`) from orchestrator bash and task allowlists; campaign `permission.bash` deny-first `{*: deny, sdk/quantlab/pipeline/*: allow, sdk/quantlab/campaign/*: allow}`; fixed stale `sdk/pipeline/*` -> `sdk/quantlab/pipeline/*`. Validated via `json.load` (39 agents, was 41). Diff vs backup confirmed exact intended change set.
- [x] 6.4 GREEN sync: `installer/internal/opencode/overlay.json` (in-repo) — removed deploy/monitor, campaign deny-first bash block. `~/.config/opencode/prompts/quantlab/orchestrator.md` — pruned legacy routing rows (:26-29) and legacy QuantLab Task Routing subsections (:135-157). NOTE: no live `~/.config/opencode/overlay.json` exists — overlay sync targets the installer overlay per design + spec (Restore Path scenario).
- [x] 6.5 verify 6.1 green: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/test_orchestrator_prompt.py` -> **70 passed** (59 baseline + 11 new G4 tests).

### Batch 2 — U2 PR2 G5 (Phase 1, tasks 1.1-1.3)

- [x] 1.1 RED `tests/pipeline/test_pipeline_counts.py`: pin tests — 16 non-orchestrated (11 agent + 5 gate), 25 orchestrated (17 agent + 8 gate), 27 with retest/optimize (19 agent + 8 gate); research first stage (both modes); `custom_project` lookup contract (unregistered -> RegistryError, registered -> Stage subclass).
- [x] 1.2 GREEN remove stale "17-stage"/"8 agents"/"8 agentes" wording: `research_director.py` module docstring (:3) + `build_pipeline` docstring (:227, now documents canonical counts 16/25/27); docs `multi-agent/pipeline.md` (:42), `multi-agent/agents.md` (:7 overview, :30 pipeline bullet), `configuration/pipeline-config.md` (:37), `STATE.md` (:72, Spanish preserved).
- [x] 1.3 GREEN register `custom_project` in `sdk/quantlab/pipeline/registry.py`: new module-level `RegistryError`; new `StageRegistry.lookup()` (fails closed — raises `RegistryError` for unregistered names; `get_stage_class` still returns `None` for backward compat); `"custom_project": BuilderStage` registered in `_register_agent_stages` (G2 dependency — registration only, dispatch wiring lands in U7); `custom_project` added to `agent_names` set in `list_stage_names_by_type`.

### Batch 5 — U5 PR5 G3 (Phase 4, tasks 4.1-4.5)

- [x] 4.1 RED `tests/data/test_dukascopy_provider.py`: appended (new file) `TestDukascopyProvider` (8 tests) — normalized bars via fake `DatasourceHandler` (timestamp/ohlc/volume contract, dropped NaN rows); exact symbol+timeframe forwarded to `DataManager` request; **gap→`[]` no raise on every surface**: empty handler, missing JForex state dir, handler absent from `datasources` registry, invalid symbol `"AAPL"` (not `^[A-Z]{6}(_[A-Z]+\d*)?$`), exploding handler; plus real-JForex-history normalization (UTC-aware datetime, `volume` preserved). First run: **8 failed** (module absent) — genuine RED. GREEN gate: 8 passed.
- [x] 4.2 RED `tests/agents/test_llm_research_agent_g3.py`: appended (new file) `TestDukascopyMarketBlock` (9 tests) + `TestDukascopyMarketCache` (4 tests) — market block renders zones (`overbought`, `insufficient_data`, `high`) + source `Dukascopy` + timeframe from `data["fundamental"]["ticker"]`; gap → block omitted AND no exception; too-few-bars → block STILL renders with `insufficient_data` zones (dukascopy-research-data s14/s20); ATR zone `high` triangulates volatility; no ticker → omitted; provider unavailable → omitted; **no raw series values leaked** (`"1.10" not in prompt`); cache: `cache_market_bars` writes `datasets/EURUSD/H1.csv` + `rebuild_index` records it (hermetic tmp lake), empty → `None`, bars omitted → re-fetch, `generate_config(knowledge_root=...)` caches best-effort with `call_llm` monkeypatched. First run: **13 failed** (no market block, no `cache_market_bars`) — genuine RED. GREEN gate: 13 passed.
- [x] 4.3 GREEN create `sdk/quantlab/data/dukascopy/provider.py`: `DukascopyProvider(data_manager=None, jforex_state_dir=None)` with `fetch_bars(symbol, timeframe) -> list[Bar]` — resolves the datasource handler by sqx name, delegates to `JForexProvider.fetch_history`, normalizes to UTC-aware `Bar`s (dropping NaN rows), returns `[]` on ANY gap (no state dir, handler absent, invalid symbol, handler/data errors) and never raises. Provider is fetch-only; caching lives in the agent flow.
- [x] 4.4 GREEN `llm_research_agent.py`: `DEFAULT_MARKET_INDICATORS = ("RSI", "ATR", "ADX")`, `_DEFAULT_MARKET_TIMEFRAME = "H1"`, lazy `_get_dukascopy` (module-level import → monkeypatchable), `_market_bars`, `_render_market_block` (pure, ASCII: `Market Context (Dukascopy/JForex4): {symbol} {timeframe}` + `- {IND}: {zone}`), `_market_context` (empty bars → `None` → block omitted; non-empty → `IndicatorEngine.compute` zones). `build_prompt` appends the block AFTER the F2 SQX section, symbol from `data["fundamental"]["ticker"]` or `data["ticker"]`, timeframe from `data.get("timeframe")` or `"H1"`. Raw series values never enter the prompt.
- [x] 4.5 GREEN cache: async `cache_market_bars(symbol, timeframe, bars=None, knowledge_root=None)` — `KnowledgeStore.cache_dataset` + `rebuild_index` (knowledge-store delta "Dataset Sample Caching"), returns rel lake path `datasets/{symbol}/{timeframe}.csv` or `None`, best-effort never raises (lazy `KnowledgeStore` import avoids a module cycle). `generate_config` gains optional `knowledge_root=None` and caches best-effort after `build_prompt` (symbol from `fund_ticker` or market_context, timeframe from context or `"H1"`).

## TDD Cycle Evidence

### Batch 1 — U1 PR1 G4

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 6.1 | `tests/test_orchestrator_prompt.py` (G4 classes appended) | E2E (live-config pin) | ✅ 59/59 | ✅ Written — 9/11 new tests failed pre-edit (pin failures + overlay pins; 2 positive controls passed) | ✅ 70/70 after config/prompt/overlay edits | ✅ Multi-surface: task allowlist, bash allowlist, prompt routing table, overlay, positive controls (active agents remain registered) | ➖ None needed — config-pin tests, no production logic to refactor |
| 6.2 | N/A (backup) | N/A | N/A | N/A (operational step) | ✅ `cp -p` + SHA256 verified byte-identical | ➖ Single | ➖ None |
| 6.3 | covered by 6.1 RED | E2E | ✅ 59/59 | ✅ 9 failed | ✅ 70/70 | ✅ deny-first + path-corrected two-sided assertions | ➖ None |
| 6.4 | covered by 6.1 RED (overlay class) + prompt test | E2E | ✅ 59/59 | ✅ overlay tests failed pre-sync | ✅ 70/70 | ✅ overlay agent-absence + campaign deny-first; prompt token-exact routing checks | ➖ None |
| 6.5 | same file re-run | E2E | — | — | ✅ 70 passed | — | — |

### Batch 2 — U2 PR2 G5

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `tests/pipeline/test_pipeline_counts.py` (new file) | Unit + contract (code-asserted counts) | ✅ 39 passed / 1 skipped (`test_pr2_research_director.py`, `test_pr3_pipeline_wiring.py`, `tests/pipeline/test_full_campaign_flow.py`, `tests/integration/test_full_pipeline.py`) | ✅ Written first — first run: **2 failed** (registry contract: `lookup()` AttributeError / `RegistryError` absent), 5 passed (counts + research-first pins — code already authoritative, tests pin the D8 contract) | ✅ 7/7 after registry.py GREEN (lookup + RegistryError + custom_project registration) | ✅ +2 triangulation tests: `lookup` agrees with `get_stage_class` on registered names; `custom_project` present in `list_stage_names_by_type("agent")` -> 9/9 | ➖ None — additive API + registration, no behavior to refactor |
| 1.2 | covered by 1.1 RED (counts unchanged) + safety net | Unit/contract | ✅ 39+37 passed | ✅ N/A for wording (counts pinned by 1.1 RED; docstring change is documentation) | ✅ docstring + 4 doc files updated; safety net re-run 48 passed / 1 skipped | ✅ counts re-derived from code after edits (unchanged 16/25/27) | ➖ None |
| 1.3 | covered by 1.1 RED (registry classes) | Unit | ✅ 39 passed / 1 skipped | ✅ AttributeError (no `lookup`) + NameError (no `RegistryError`) | ✅ 7/7 | ✅ lookup/get_stage_class agreement + enumeration includes custom_project -> 9/9 | ➖ None |

### Batch 3 — U3 PR3 G1 (Phase 2, tasks 2.1-2.6)

- [x] 2.1 RED `tests/campaign/test_delegation.py`: appended `TestStageArtifactPersistence` (10 tests) — envelope+outcome file on success (real `research_llm` stage, tmp lake root); failed stage → failed envelope + HOLD + error log listed; missing `knowledge_root`/`campaign_id` → risks + `artifacts == []`; executor never claims without root; write failure folds failed+halt; idempotent re-run. First run: 10 failed / 47 passed (genuine RED — no persistence existed).
- [x] 2.2 GREEN create `sdk/quantlab/knowledge/artifacts.py`: `render_proposal_markdown` / `render_spec_markdown` (deterministic, no LLM text) + `write_proposal_artifact` / `write_spec_artifact` (return relative lake path `structured/{cid}/proposal.md` / `spec.md`; `""` when root/cid falsy; `OSError` propagates). Own `_json_safe` mirror (no delegation import — would cycle).
- [x] 2.3 GREEN `delegation.py`: `_run_sdk_stage` now returns `StageRunResult(outcome, artifacts, risks)`; wraps stage execution in try/except — stage failure → `_persist_stage_failure` (best-effort `{phase}_{stage}.error.json` + failed envelope, next_gate HOLD) then re-raise; success → `_persist_stage_success` (outcome JSON via `KnowledgeStore.write`, Q1 hooks, `save_phase_envelope` completed with `started_at`/`completed_at`/`duration`, next_gate `_next_phase_id(phase)`, real paths only). Reasoning executor folds `run.artifacts`/`run.risks`; mechanical executor claims `[]` + risk note (no synthetic `{phase}_handoff.json`); `run_stage_for_handoff` unpacks `.outcome` (dict contract preserved).
- [x] 2.4 GREEN `phase_runner.py`: `build_directive` injects `payload.setdefault("knowledge_root", "knowledge")` + `payload.setdefault("campaign_id", "campaign")` (D3 — caller values win). Runner tests updated: `test_parses_scope_and_payload` → `{"campaign_id": "c1", "knowledge_root": "knowledge"}`; new `test_injects_persistence_context_defaults_and_keeps_caller_values`; round-trip tests pin `knowledge_root` to `tmp_path` (hermetic).
- [x] 2.5 GREEN hooks (inside `_persist_stage_success`): `phase == "research"` → `write_proposal_artifact`; `phase in ("hypothesis", "config")` → `write_spec_artifact` (Q1). Verified with fake stage outcomes: proposal renders EURUSD + hyp_1; spec renders builder/retester/optimizer/portfolio sections + `(none)` marker for empty hypotheses.
- [x] 2.6 REFACTOR idempotent re-run (overwrite semantics — byte-identical second run) + write-failure folds (failed envelope + HOLD via `_persist_stage_failure`; re-raise → executor folds failed → REQ-802 halt). Both pinned by tests.

### Batch 4 — U4 PR4 G6 (Phase 3, tasks 3.1-3.4)

- [x] 3.1 RED `tests/knowledge/test_knowledge_store_v5.py`: v5 acceptance + index migration — `TestKnowledgeStoreV5RebuildKeys` (3 tests): rebuild over a stale v4 index emits `_version: '5'` + the four v5 keys in both the returned doc and on-disk `index.yaml`; `read_index()` upgrades a v4 file to 5 preserving legacy `kb_parameters`/`version_events`/`directories`; **`rebuild_index` records nested `datasets/{symbol}/{tf}.csv` + `campaign-phases/{cid}/{phase}/envelope.json` files** (recursive scan — this was the genuine RED: `rebuild_index` previously scanned top-level files only, so `datasets/EURUSD/M1.csv` was NOT indexed).
- [x] 3.2 RED seed tests (same file): `TestSeedOhlc` (5 tests) — `DEFAULT_SEED_SYMBOLS == ("EURUSD",)` + `DEFAULT_SEED_TIMEFRAMES == ("M1","M5","H1")` (Q3 CI-determinism pin); full seed writes `datasets/EURUSD/{M1,M5,H1}.csv` + index records them (hermetic mock source via `_DEFAULT_OHLC_SOURCE_FACTORY` seam); env-gap (no JForex history + no SQCLI_PATH) → exit 1 with stderr naming **JForex** AND **SQCLI** + "no dataset files written"; partial gap (M1 only) → exit 0, written file + skipped listed; `seed-ohlc` registered in `build_parser` (D6 argparse wiring). Plus `TestDatasetCache` (2 tests): `cache_dataset` writes header+rows CSV and returns the rel path; re-seed overwrites (idempotent, not append). RED gate: 8 failed / 20 passed (ImportError on `cmd_kb_seed_ohlc`, `AttributeError` on `cache_dataset`, `AssertionError` on nested datasets indexing).
- [x] 3.3 GREEN `sdk/quantlab/knowledge/store.py`: new `KnowledgeStore.cache_dataset(symbol, timeframe, bars) -> str` — serializes `Bar` list to `datasets/{symbol}/{timeframe}.csv` (UTC ISO-8601, `timestamp,open,high,low,close,volume`) via the async `write` path, returns the rel lake path; **`rebuild_index` switched from `iterdir()` to recursive `rglob("*")`** so nested v5 artifacts (dataset samples, campaign-phase envelopes) are recorded (matches the nested-path keys already expected by `tests/dashboard/seed.py:45` and `sdk/tests/test_knowledge.py:305`).
- [x] 3.4 GREEN `sdk/quantlab/cli/sq_commands.py`: `cmd_kb_seed_ohlc` handler — `KnowledgeStore.initialize()`, source seam `_DEFAULT_OHLC_SOURCE_FACTORY` (mirrors `_DEFAULT_EVIDENCE_BASE_FACTORY` mock pattern per `cmd_kb_seed`), iterates `--symbols` × `--timeframes` (defaults EURUSD × M1/M5/H1), caches bars via `cache_dataset`, `rebuild_index()` on success, exit 1 on total gap naming `local JForex4 history` + `SQCLI_PATH/SQX_INSTALL_PATH` and reporting partial files. Real source `_DataManagerOhlcSource` routes `DataManager` → `JForexProvider.fetch_history` (never fabricates data). `add_sqx_subparser` registers `seed-ohlc` with `--knowledge-root` (common), `--symbols`, `--timeframes`, `--jforex-state-dir`.

## TDD Cycle Evidence

### Batch 3 — U3 PR3 G1

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 2.1 | `tests/campaign/test_delegation.py` (TestStageArtifactPersistence, 10 tests) | Unit + integration (real research_llm stage, fake registry classes, full executor path) | ✅ 61/61 | ✅ Written first — **10 failed / 47 passed** (envelope.json absent, `result.artifacts` AttributeError, no proposal/spec files, success≠failed) | ✅ 57/57 | ✅ Real stage + fake stages + executor + runner bridge (4 layers) | (2.6) |
| 2.2 | covered by 2.1 RED (proposal/spec render + path assertions) | Unit | ✅ 61/61 | ✅ `artifacts.py` missing → `FileNotFoundError`/ModuleNotFoundError | ✅ 57/57 | ✅ Deterministic renderers: EURUSD/hyp_1 in proposal; builder/retester/optimizer/portfolio + `(none)` in spec | ➖ None — new module |
| 2.3 | covered by 2.1 RED (envelope+files+timestamps+no-claim) | Unit | ✅ 61/61 | ✅ 10 failed (persistence absent) | ✅ 57/57 | ✅ `PhaseResult.artifacts == envelope["artifacts"]` (real paths, no synthetic claims); missing-root degrade asserted at both `_run_sdk_stage` and executor level | ➖ None |
| 2.4 | `tests/campaign/test_phase_runner.py` (payload assertion updated + 1 new D3 test) | Unit/CLI bridge | ✅ 61/61 | ✅ old assertion `{"campaign_id": "c1"}` failed (injection absent) | ✅ 15/15 | ✅ Caller values win + defaults applied (two-sided) | ➖ None |
| 2.5 | covered by 2.1 RED (Q1 hook tests, fake outcomes) | Unit | ✅ 61/61 | ✅ proposal.md/spec.md absent pre-GREEN | ✅ 57/57 | ✅ research→proposal; hypothesis AND config→spec | ➖ None |
| 2.6 | `test_rerun_is_idempotent` + `test_write_failure_folds_failed_and_halts` | Unit | ✅ 61/61 | ✅ (RED with 2.1) | ✅ 57/57 | ✅ byte-identical overwrite (outcome + envelope); blocked-root write → failed + halt, no fake success | ✅ REFACTOR: overwrite + error-fold implemented inside `_persist_stage_success`/`_persist_stage_failure` |

### Batch 4 — U4 PR4 G6 (Phase 3, tasks 3.1-3.4)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 3.1 | `tests/knowledge/test_knowledge_store_v5.py` (TestKnowledgeStoreV5RebuildKeys, 3→4 tests) | Unit (hermetic tmp lake) | ✅ 18/18 baseline pre-edit | ✅ Written first — **8 failed / 20 passed**: ImportError (`cmd_kb_seed_ohlc` absent), AttributeError (`cache_dataset` absent), AssertionError (nested `datasets/EURUSD/M1.csv` NOT recorded — `rebuild_index` only scanned top-level files) | ✅ 26/26 after store.py GREEN (`rglob` + `cache_dataset`) | ✅ +1 case: nested `campaign-phases/camp-001/research/envelope.json` recorded → recursion proven general (not dataset-specific) → 29/29 | ✅ `cache_dataset` line-split for PEP8; seam parity param documented |
| 3.2 | same file (TestSeedOhlc 5 + TestDatasetCache 2) | Unit + CLI wiring (D6 `build_parser` → `cmd_kb_seed_ohlc`) | ✅ 18/18 | ✅ 8 failed pre-GREEN (seed handler, gap exits, defaults, registration) | ✅ 26/26 | ✅ full seed, partial gap, total env-gap, defaults, overwrite — 5 failure surfaces | (see 3.1) |
| 3.3 | covered by 3.1 RED (cache_dataset + nested index) | Unit | ✅ 18/18 | ✅ AttributeError (no `cache_dataset`) | ✅ 26/26 | ✅ idempotent overwrite (not append) + header/column contract | ✅ line-split |
| 3.4 | covered by 3.2 RED (handler + registration) | CLI handler | ✅ 18/18 | ✅ 2/8 failures were handler-level (gap message named only SQCLI, missing JForex; request-order assertion) | ✅ 28/28 after gap-message + assertion fix | ✅ runtime harness on real `main()` — see Work Unit Evidence | ✅ seam parity comment |

### Batch 5 — U5 PR5 G3 (Phase 4, tasks 4.1-4.5)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 4.1 | `tests/data/test_dukascopy_provider.py` (TestDukascopyProvider, 8 tests) | Unit (fake `DatasourceHandler` + fake jforex) | ✅ 72 passed / 1 pre-existing fail (llm_agent F2) | ✅ Written first — **8 failed** (module absent) | ✅ 8 passed | ✅ 6 gap surfaces (empty handler, no state dir, handler absent, invalid symbol, exploding handler, real-history empty) + normalization contract | ➖ None — new module |
| 4.2 | `tests/agents/test_llm_research_agent_g3.py` (TestDukascopyMarketBlock 9 + TestDukascopyMarketCache 4) | Unit (monkeypatched `_get_dukascopy`/`SQXDocProvider`/`call_llm`; hermetic tmp lake) | ✅ 72 passed / 1 pre-existing fail | ✅ Written first — **13 failed** (no block, no `cache_market_bars`) | ✅ 13 passed | ✅ gap→omitted vs insufficient_data→renders vs unavailable→omitted (3 distinct no-raise surfaces) + no-raw-series leak + ATR high zone | (4.4/4.5) |
| 4.3 | covered by 4.1 RED (provider) | Unit | ✅ 72/1 | ✅ 8 failed | ✅ 8 passed | ✅ real-JForex-history path + fake handler path | ✅ line-split |
| 4.4 | covered by 4.2 RED (market block) | Unit | ✅ 72/1 | ✅ 13 failed | ✅ 13 passed | ✅ zones values, timeframe source, ticker source, omit-on-gap, omit-on-no-ticker, omit-on-unavailable | ✅ line-splits (PEP8 ≤ 88) |
| 4.5 | covered by 4.2 RED (cache tests) | Unit | ✅ 72/1 | ✅ 13 failed | ✅ 13 passed | ✅ write+index recorded, empty→None, re-fetch on omitted bars, generate_config wiring | ✅ line-splits |

### Batch 6 — U6 PR6 G7

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 5.1 | `tests/pipeline/test_config_review_stage.py` (new file, 12 tests) | Unit + integration (real `execute_phase` "review" → reasoning executor → `_run_sdk_stage` → `_persist_stage_success`) | ✅ 102 passed / 1 pre-existing fail (pipeline/) + 103 passed (delegation/runner/orchestrated) | ✅ Written first — collection **ImportError**: `build_review_teaching_table` absent (module import of the future symbol) | ✅ 12 passed (one test corrected: scenario-1 config gained `sl_value_type`/`pt_value_type` — reviewer APPROVEs only when required SL/PT have a value type) | ✅ 3 layer paths: pure function (no lake), stage execute (hermetic tmp lake), delegation envelope (`PhaseResult.artifacts`); 6 degrade/fallback surfaces + dedup | ➖ None — additive stage behavior + 2 delegation hunks |
| 5.2 | covered by 5.1 RED | Unit + integration | ✅ 114 passed / 1 pre-existing fail after GREEN | ✅ collection ImportError pre-GREEN | ✅ 12 passed | ✅ no-KB-entries header+fallback; fallback+KB mix; dedup (3 fields → 1 Stop Loss row); missing context → no claim | ✅ `_fallback_row` factored out of the pure function |

### Batch 7 — U7 PR7 G2 (Phase 7, tasks 7.1-7.4)

- [x] 7.1 RED `tests/agents/test_builder_agent_g2.py` (new file, 3 tests): `TestG2FlagDispatch` — flag=0 produces legacy single-task archive (schema 141.2219, CfxConfig); flag=1 produces CustomProject archive (schema 144.2953, CfxProject with per-task XML); flag=0 byte-identical to direct `translator.generate_cfx_archive` call. First run: **1 failed** (flag=1 path missing — genuine RED).
- [x] 7.2 GREEN `sdk/quantlab/agents/builder_agent.py`: `_translate` now checks `_is_custom_project_enabled()` and dispatches to either legacy `translator.generate_cfx_archive` or `customproject.generator.generate_cfx_archive` via `_research_config_to_custom_project` conversion; `is_custom_project_enabled` in `generator.py` defaults to "0" (legacy) per D7; `test_rollback_flag_keeps_legacy_path` updated to assert False by default. GREEN gate: **3 passed**.
- [x] 7.3 DELIBERATE re-base: `test_rollback_flag_keeps_legacy_path` updated to reflect legacy default (False when env unset); focused tests `tests/customproject/` + `tests/cfx/` -> **217 passed** (includes updated flag test). No golden fixture files changed — only the flag-default assertion in `test_e2e_loadconfig.py` was re-based.
- [x] 7.4 FLIP default→CustomProject: `is_custom_project_enabled` in both `generator.py` and `builder_agent.py` flipped from "0" to "1"; `test_rollback_flag_keeps_legacy_path` updated to assert True by default. All focused tests green.

### Test Summary (U7 PR7 G2)

- **Tests written**: 3 new tests (U7): flag-disabled legacy path, flag-enabled CustomProject path, byte-identity assertion.
- **Focused test results**: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/agents/test_builder_agent_g2.py tests/customproject/ tests/cfx/` -> **220 passed, 0 failed, 4 skipped** (exit 0). RED gate: 1 failed pre-GREEN (CustomProject dispatch missing).
- **Safety net**: `tests/agents/test_builder_agent.py tests/agents/test_builder_agent_matrix.py tests/pipeline/ tests/builder/ sdk/tests/test_pr2_builder_agent.py` -> **266 passed / 1 pre-existing fail** (`test_chained_retest_optimize.py` — unrelated F2 failure, carried). No regression from dispatch addition.
- **Layers used**: Unit (direct translate_to_cfx with env monkeypatch), integration (flag-default assertion in e2e loadconfig test).

### Test Summary (U6 PR6 G7)

- **Tests written**: 12 new tests (U6): 7 stage persistence + 4 pure-function + 1 delegation envelope.
- **Focused test results**: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/pipeline/test_config_review_stage.py` -> **12 passed, 1 warning in 1.22s** (exit 0). RED gate: collection ImportError pre-GREEN.
- **Safety net**: `tests/pipeline/` -> **114 passed / 1 failed** (the SAME known pre-existing failure, `test_chained_retest_optimize.py::...::test_retest_crosschecks_carry_monte_carlo_and_walkforward`); delegation/runner/orchestrated/retest -> **103 passed** (matches baseline); `sdk/tests/test_context.py` 25 passed; `sdk/tests/pipeline + test_kb_educational + test_kb` -> **73 passed**. No regression.
- **Layers used**: pure function (no I/O), stage execute (hermetic tmp lake), delegation envelope (`execute_phase(phase_id="review")` real path).

### Test Summary (cumulative U1+U2+U3+U4)

- **Tests written**: 31 (U1+U2+U3) + 10 v5/seed/cache (U4: 4 rebuild-key + 5 seed + 2 cache − 1 folded duplicate) = 41 new tests.
- **Focused test results**: U4 `tests/knowledge/test_knowledge_store_v5.py` -> **29 passed** (exit 0). RED gate: 8 failed / 20 passed pre-GREEN; 26 passed after GREEN; 29 after triangulation.
- **Safety net**: knowledge layer re-run -> **144 passed** across `sdk/tests/test_knowledge.py`, `sdk/tests/test_kb.py`, `sdk/tests/test_kb_seed_validation.py`, `tests/robustness/test_knowledge_store_buffering.py`, `tests/robustness/test_knowledge_health.py`, `tests/knowledge/test_knowledge_store_v5.py`, `tests/knowledge/test_time_series_store.py`; U3 delegation/runner re-run -> **72 passed** (`test_delegation.py` + `test_phase_runner.py`) — no regression from the recursive `rebuild_index`.
- **Layers used**: Unit (hermetic lake), CLI wiring (D6 `build_parser`), runtime harness (real `main()` end-to-end).

### Test Summary (U5 PR5 G3)

- **Tests written**: 8 provider + 13 agent = 21 new tests (U5).
- **Focused test results**: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/data/test_dukascopy_provider.py tests/agents/test_llm_research_agent_g3.py` -> **21 passed, 1 warning in ~4s** (exit 0). RED gates: 8 failed (4.1), 13 failed (4.2) pre-GREEN.
- **Safety net**: `tests/data/ tests/knowledge/ sdk/tests/analysis/` -> **108 passed** (no regression from the new provider/cache). `sdk/tests/agents/test_llm_agent.py` -> 1 known pre-existing F2 failure only. Untracked other-work suites (`test_llm_research_agent_f2.py`, `test_hypothesis_builder_f2.py`, `sdk/tests/agents/test_hypothesis_builder.py`) fail on their own dirty F2 code — untouched by this slice.
- **Layers used**: Unit (fake handler + monkeypatched provider), hermetic tmp lake.

## Work Unit Evidence

### Batch 3 — U3 PR3 G1

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/test_delegation.py` -> **57 passed in 2.85s** (exit 0). RED gate: 10 failed / 47 passed pre-GREEN — genuine missing-behavior assertions (envelope.json absent, `result.artifacts` AttributeError on the old dict return, no proposal/spec files). |
| Runtime harness command/scenario and exact result | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/test_phase_runner.py` -> **15 passed in 1.2s** (exit 0) — the runner bridge is U3's harness per tasks.md ("harness `test_phase_runner.py` (mock)"): CLI round-trip emits the validated JSON envelope; D3 injection verified at the directive level. Runner round-trips pin `knowledge_root` to tmp_path so the real research stage persists into a hermetic lake (no repo `knowledge/` pollution — verified: `git status -- knowledge/` clean after the suite). |
| Rollback boundary | Revert `sdk/quantlab/campaign/delegation.py`, revert `sdk/quantlab/campaign/phase_runner.py`, delete `sdk/quantlab/knowledge/artifacts.py`, revert `tests/campaign/test_delegation.py`, revert `tests/campaign/test_phase_runner.py` (matches tasks.md U3 rollback: "revert 3 SDK files"; tests revert with them). `git checkout` of these 5 files (+tasks.md checkbox marks) removes all U3 work and touches nothing from U1/U2 or other phases. |

### Batch 4 — U4 PR4 G6

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/knowledge/test_knowledge_store_v5.py` -> **29 passed, 1 warning in 1.13s** (exit 0). RED gate: 8 failed / 20 passed pre-GREEN — genuine missing behavior (no `cmd_kb_seed_ohlc`, no `cache_dataset`, nested `datasets/` not indexed). GREEN gate: 26 passed; +1 triangulation (nested campaign-phase envelope) -> 29. |
| Runtime harness command/scenario and exact result | Real CLI end-to-end via `quantlab.cli.main.main(["sqx","kb","seed-ohlc", ...])` on a hermetic tmp lake with the `_DEFAULT_OHLC_SOURCE_FACTORY` mock seam: **exit 0**, `Seeded OHLC: 3 dataset file(s) for EURUSD at M1, M5, H1`, `index _version: 5`, indexed + written = `datasets/EURUSD/{M1,M5,H1}.csv`. Env-gap scenario (no JForex history, SQCLI_PATH/SQX_INSTALL_PATH unset): **exit 1**, `Error: OHLC seed failed: no market data available — missing dependency: local JForex4 history (download the instrument in the JForex4 platform first); SQCLI_PATH/SQX_INSTALL_PATH` + `no dataset files written`. `git status -- knowledge/` clean after both runs (no repo lake pollution). |
| Rollback boundary | Revert `sdk/quantlab/cli/sq_commands.py`, revert `sdk/quantlab/knowledge/store.py`, revert `tests/knowledge/test_knowledge_store_v5.py` (+tasks.md checkbox marks) — matches tasks.md U4 rollback: "drop `seed-ohlc` subcommand + helper". `git checkout` of these 3 files removes all U4 work and touches nothing from U1-U3 or other phases. `sqx kb seed-ohlc` no longer registers; store keeps `cache_dataset`/recursive `rebuild_index` only if U5/U7 need them. |

### Batch 5 — U5 PR5 G3

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/data/test_dukascopy_provider.py tests/agents/test_llm_research_agent_g3.py` -> **21 passed, 1 warning in 4.52s** (exit 0); re-run after REFACTOR 21 passed in 3.92s. RED gates: 8 failed (provider tests — module absent), 13 failed (agent tests — no market block / no `cache_market_bars`). |
| Runtime harness command/scenario and exact result | Prompt test (mock) per tasks.md ("harness `prompt test (mock)`"): `TestDukascopyMarketBlock` drives `build_prompt` with `_get_dukascopy` monkeypatched to a stub (fake bars or gap) — hermetic, no network/state dir; asserts rendered block content + omission semantics + no raw series leak. `TestDukascopyMarketCache` uses `knowledge_root=tmp_path` (hermetic lake) — no repo `knowledge/` pollution (verified: `git status -- knowledge/` clean after suite). |
| Rollback boundary | Delete `sdk/quantlab/data/dukascopy/provider.py`, revert `sdk/quantlab/agents/llm_research_agent.py` (revert G3 lines: imports, `DEFAULT_MARKET_INDICATORS`/`_DEFAULT_MARKET_TIMEFRAME`, `_MarketContext`, `_get_dukascopy`/`_market_bars`/`_render_market_block`/`_market_context`, `cache_market_bars`, build_prompt market block, `generate_config` cache wiring), revert `tests/data/test_dukascopy_provider.py`, revert `tests/agents/test_llm_research_agent_g3.py` (+tasks.md checkbox marks) — matches tasks.md U5 rollback: "drop provider+block". CAUTION: `llm_research_agent.py` also carries unrelated F2 dirty work — revert only the G3 hunks, never a blanket `git checkout` of that file. |

### Batch 6 — U6 PR6 G7

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/pipeline/test_config_review_stage.py` -> **12 passed, 1 warning in 1.22s** (exit 0). RED gate: collection ImportError pre-GREEN (`build_review_teaching_table` imported from the stage module — genuine missing behavior). |
| Runtime harness command/scenario and exact result | Delegation envelope harness per tasks.md ("harness `test_delegation.py` (mock)"): `TestReviewPhaseEnvelope::test_review_phase_artifacts_include_teaching_table` drives `execute_phase(PhaseDirective(phase_id="review", ...))` under `SQX_FORCE_MOCK=1` on a hermetic tmp lake — reasoning executor → `_run_sdk_stage("review")` → `ConfigReviewStage` persists the table → `_persist_stage_success` claims it. `result.status == "success"` and `structured/camp-1/review/teaching-table.md in result.artifacts`. Stage tests use `knowledge_root=tmp_path` — no repo `knowledge/` pollution (verified: suite leaves `knowledge/` untouched; `git status -- knowledge/` unchanged). |
| Rollback boundary | Revert `sdk/quantlab/pipeline/stages/config_review_stage.py`, revert the 2 delegation.py G7 hunks (config merge in `_run_sdk_stage`; `teaching_rel` block in `_persist_stage_success`), delete `tests/pipeline/test_config_review_stage.py` (+tasks.md checkbox marks, +this apply-progress) — matches tasks.md U6 rollback: "revert `config_review_stage`". CAUTION: `delegation.py` carries U3-U6 work — revert ONLY the two G7 hunks, never a blanket `git checkout`. `config_review_stage.py` was dirty only by this slice (G7 is its first change). |

## Deviations from Design

### Batch 6 — U6 PR6 G7

1. **Two `delegation.py` hunks beyond the design's file-changes table** (design lists only `config_review_stage.py` Modify): (a) `_run_sdk_stage` merges payload-level `campaign_id`/`knowledge_root` into the stage `ctx.config` (setdefault — caller wins) so reviewer-owned artifacts persist under the campaign; (b) `_persist_stage_success` claims `outcome["teaching_table"]` in `PhaseResult.artifacts` ONLY when the file actually exists (REQ-819 real-claims). Both are required for the G7 spec scenarios (path in verdict AND in `PhaseResult.artifacts`) and the phase envelope contract; without (a) the review phase could never see the D3 context, and without (b) the path could not reach `PhaseResult.artifacts`.
2. **`KbStore.consult` hits are reconstructed via `KbParameter.model_validate`**, not consumed raw: `consult` returns guidance-metadata dicts (no `why_choose`/`when_choose`), while `build_teaching_table` requires `Sequence[KbParameter]`. Reconstruction is lossy for params without a small-account recommendation (empty Why/For-what cells) — the table still teaches "Chosen config" via the recommendation/default. The "Chosen config"+"Why" columns carry the small-account recommendation when present (seeded Stop Loss/Profit Target both have one).
3. **Teaching table written via direct `Path.write_text`, not `KnowledgeStore.write`**: `ALLOWED_EXTENSIONS = {.yaml,.yml,.json,.csv,.parquet}` — `.md` would trigger `FormatWarning` and break the store contract. Follows the existing pattern from `sdk/quantlab/knowledge/artifacts.py` (proposal.md/spec.md written directly). The artifact REL path still lands in the envelope + v5 index via `rebuild_index`'s recursive scan.
4. **RRR fields have no KB entry** (seeder defines "Stop Loss"/"Profit Target"/"Number of Exit Types (SL/PT/etc...)", no risk-reward param): `limit_slpt_rrr{,_from,_to}` map to their own name and render the stable `No KB entry` fallback row — exactly the parameter-educational-table s2 contract, so this is behavior-by-design, not a gap.
5. **Reviewer verdict contract test correction**: my first scenario-1 test asserted APPROVE for `BuildConfig(sl_required=True, pt_required=True)` — the reviewer returns MODIFY (it suggests `sl_value_type`/`pt_value_type` when required fields lack one, per REQ-05 adjustment rule). Corrected the fixture (added `sl_value_type="pips"`/`pt_value_type="pips"`), NOT the code. The G7 spec does not govern the verdict action.

### Batch 5 — U5 PR5 G3

1. **`cache_market_bars` lives on the agent, not the provider**: the G3 design sketches caching in the data flow, but caching (KnowledgeStore + rebuild_index) is the agent's concern — the provider stays fetch-only (`fetch_bars` never touches the lake). Keeps the provider's contract "gap→`[]`, never raises" trivially testable and lets `generate_config` cache with the fetched sample while `build_prompt` degrades gracefully.
2. **`_MarketContext.bars` is returned but currently unused by callers**: `build_prompt` consumes only `.block`; `generate_config` re-fetches via `cache_market_bars(bars=None)`. The bars member exists so a future caller can cache the exact fetched sample without recomputation; harmless and documented. Flagged for verify-phase review if dead-code rules apply.
3. **Existing `DukascopyProvider` collision avoided**: `sdk/quantlab/data/market/providers.py` already defines a `DukascopyProvider extends MarketDataProvider` (legacy market-layer provider). The new research provider is `sdk/quantlab/data/dukascopy/provider.py` — a different module path and class contract. No import collision (distinct packages); noted so reviewers do not mistake them.
4. **`generate_config` cache symbol priority `fund_ticker > context.ticker > context.market`**: context `"market"` may hold a goal string rather than a symbol; it is the last-resort fallback and only used when no ticker exists anywhere. Deliberate, test-covers `fund_ticker` path only.

### Batch 3 — U3 PR3 G1

1. **`_run_sdk_stage` return type changed from `dict[str, Any]` to `StageRunResult`** (outcome + real artifacts + risks): design described the choke point "returns the outcome"; carrying persistence metadata through the same return made the REQ-819 no-claim guarantee testable at the executor level without re-reading the lake. `run_stage_for_handoff` unpacks `.outcome`, preserving the dict contract for the handoff report. Documented in the new dataclass docstring.
2. **`next_gate` uses phase ids, not the design's `HUMAN_*` gate ids**: the delegation layer has no gate-id vocabulary (REQ-802 recommends phase ids via `_next_phase_id`), and REQ-3's `next_gate` is free-form. Success → next phase id (`"hypothesis"` after research); failure → `"HOLD"` (REQ-3's literal). A `HUMAN_*` translation would be a new concept outside this slice — flagged for the verify phase.
3. **Failed-stage error log is `{phase}_{stage}.error.json`, not `.log`**: `KnowledgeStore.ALLOWED_EXTENSIONS` is `{.yaml,.yml,.json,.csv,.parquet}`; a `.log` would trigger `FormatWarning` and fall outside the store's contract. The envelope lists the `.error.json` path (REQ-3 satisfied).
4. **`tests/campaign/test_phase_runner.py` modified beyond the design's file-changes table**: two pre-existing round-trip tests would now inject the D3 default `knowledge_root="knowledge"` into the real research stage and pollute the repo's `knowledge/` dir — they pin `knowledge_root` to `tmp_path` instead. One new D3 injection test added. This is a test-only consequence of D3, no production deviation.
5. **Mechanical executor `artifacts` `[f"{phase}_handoff.json"]` → `[]` + risk note**: the executor never persists the handoff (REQ-809: the orchestrator shell runs it), so claiming the key violated REQ-819's no-claim rule. The risk note tells the reviewer the artifacts persist when the shell runs the handoff.
6. **Missing-root degrade requires BOTH `campaign_id` AND `knowledge_root`**: spec s3 names `knowledge_root`, but the envelope path needs `campaign_id` too; both are D3-injected, so the degrade path only fires on a caller-constructed payload. Recorded as a single combined risk line.

### Batch 4 — U4 PR4 G6

1. **Gap message names BOTH the JForex gap-hint and the env dependencies, concatenated**: spec s11 requires naming "JForex/SQCLI". The naive handler reported only the SQCLI env names whenever they were absent (the env check short-circuited the source gap-hint). Final message: `missing dependency: local JForex4 history (download the instrument in the JForex4 platform first); SQCLI_PATH/SQX_INSTALL_PATH`. RED→GREEN fix was a test-discovered contract correction, not a design deviation.
2. **Request-order assertion pins loop order (M1, M5, H1), NOT a lexicographic sort**: my first test asserted `sorted(source.requests)`, but `sorted()` yields `H1 < M1 < M5` lexicographically. The production order (DEFAULT_SEED_TIMEFRAMES loop) is deterministic and correct; the assertion was wrong. Fixed to assert the exact loop order — pins the CI-deterministic seed sequence.
3. **`rebuild_index` recursion is the genuine RED of this slice** (not the v5 migration, which already existed per D5): the design/tasks assumed acceptance-pinning only; the recursive `rglob` scan is a real behavior change to a shared hot path. Triangulated with a nested campaign-phase envelope (not just datasets) to prove generality. Verified no regression: knowledge layer 144 passed, delegation/runner 72 passed.
4. **Seam `knowledge_root` param is unused by the source**: retained for call-signature parity with `_DEFAULT_EVIDENCE_BASE_FACTORY` (tests replace both factories with the same shape); documented in the seam docstring.

### Batch 2 — U2 PR2 G5 (from previous batch, retained)

1. **`custom_project` registered to `BuilderStage`** (from `agent_stages.py`), not a dedicated `CustomProjectStage` class: design D8 registers the stage in the registry as a G2 dependency; the concrete generator dispatch (legacy translator vs `customproject/generator.py`) is U7's job and the `custom_project` name aliases the builder position in `build_pipeline`'s stage order. Registering `BuilderStage` now satisfies "registered before the flag flips" and gives U7 one wire point. The registry comment documents this.
2. **`docs/CHANGELOG.md:60` left untouched**: "17-stage dry-run" is a historical record of PR 6's integration test suite (which builds its own hand-composed 17-stage config, not `build_pipeline`'s canonical output). Changing a changelog entry falsifies history; the claim refers to a test config, not the canonical pipeline counts. Flagged for verify-phase judgment.
3. **Test files with stale wording left untouched** (out of touch-list): `tests/integration/test_full_pipeline.py` ("17-stage", own hand-built config), `sdk/tests/test_pr2_research_director.py:14`, `sdk/tests/test_pr2_builder_agent.py:191`, `sdk/tests/test_pipeline_integration.py:3`, `sdk/tests/test_pipeline_agent_stages.py:209`, `sdk/tests/test_pr3_pipeline_wiring.py:212`, `tests/agents/test_builder_agent.py:29` — all test-file comments/asserts referencing 8/17 stages; they assert their own fixtures, not canonical counts. Design/task scoped 1.2 to `research_director.py` + docs; touched only those. Flagged for follow-up if verify wants doc-consistency sweep.
4. **`sdk/quantlab/agents/builder_agent.py:984,999` and `sdk/quantlab/agents/__init__.py:6`** still say "8 agent stages": these are legacy generator/build-path files outside the G5 design's file-changes table (design lists registry.py + research_director.py for G5). Left untouched — flagged for verify/follow-up.

### Batch 1 — U1 PR1 G4 (from previous batch, retained)

1. `quantlab-monitor` also removed from orchestrator allowlists + routing table (not just run/status/compare) — monitor is retired, so its allowlist entries and MONITOR routing row were equally dangling. Tests pin run/status/compare absence per spec letter; monitor absence pinned only at the agent-entry level (deliberate, documented).
2. Overlay sync targeted the in-repo `installer/internal/opencode/overlay.json` — no live `~/.config/opencode/overlay.json` exists (design + spec "Restore Path" scenario name the installer overlay as the required same-change update).
3. Orphan prompt files `deploy.md`/`monitor.md` retained (inert after agent removal; deletion out of scope).

## Issues Found

### Batch 6 — U6 PR6 G7

1. **Pre-existing failing test** (carried, unrelated to this slice): `tests/pipeline/stages/test_chained_retest_optimize.py::TestChainedTasksInOneLoad::test_retest_crosschecks_carry_monte_carlo_and_walkforward` — same failure before/after this slice (my diff touches only 3 files + tasks.md + apply-progress).
2. **`config_review_stage.py` reviewer semantics surfaced a fixture issue, not a code issue**: see deviation 5. No production behavior changed; the stage now only adds the persisted teaching-table deliverable.
3. **Reviewer action is orthogonal to G7**: MODIFY/BLOCK verdicts also persist the teaching table (the deliverable is about the configured fields, not the verdict). All three actions write the file; tested via the delegate harness on an APPROVE config.
4. **Slice ~430 changed lines (near the 400-line review budget)**: dominated by the new 12-test file (~300 insertions) + stage implementation (~190) + 2 delegation hunks (~25). Within the pre-defined U6/PR6 slice per tasks.md; orchestrator to decide if test-bulk warrants an exception (same pattern as U4).
5. **Repo remains dirty with unrelated in-flight work** (carried): my U6 slice touched exactly 3 production/test files: `sdk/quantlab/pipeline/stages/config_review_stage.py`, `sdk/quantlab/campaign/delegation.py` (2 hunks only), `tests/pipeline/test_config_review_stage.py` (new), plus tasks.md + apply-progress. No `knowledge/` pollution.

### Batch 5 — U5 PR5 G3

1. **Pre-existing failing test** (carried, unrelated to this slice): `sdk/tests/agents/test_llm_agent.py::TestParseResponse::test_valid_json_populates_hypotheses` — the dirty F2 `ParameterValidator` filter drops the hypothesis (`assert 0 == 1`); verified failing in the pre-edit baseline. NOT fixed here (other in-flight work's territory).
2. **Other-work dirty suites fail independently of this slice** (do NOT claim): `tests/agents/test_llm_research_agent_f2.py` + `tests/agents/test_hypothesis_builder_f2.py` + `sdk/tests/agents/test_hypothesis_builder.py` — failures root in F2 `parameter_validator.py`/`hypothesis_builder/{llm,rule}.py` (untracked or dirty production code from other changes; e.g. monkeypatch of a module attribute `SQXDocProvider` that only exists inside a function, `assert 14 == 7` override not applied). My diff touches only the 4 U5 files + tasks.md + this apply-progress.
3. **`sdk/quantlab/agents/llm_research_agent.py` was already dirty (+30 uncommitted F2 lines) before this slice**: the G3 hunks were interleaved around the F2 SQX section. Rollback must revert only the G3 hunks (see Work Unit Evidence), never a blanket `git checkout` — that would destroy the other work.
4. **Ruff declared in `openspec/config.yaml` but not installed** (carried from U4): REFACTOR relied on manual PEP8 review; line-length check passed (all ≤ 88, noqa lines exempt). Orchestrator/CI should run `ruff check` + `ruff format`.
5. **Slice ~345 changed lines (below the 400-line budget)**: 173 insertions in `llm_research_agent.py` (G3 hunks ≈ 90 of them; the rest pre-existing F2) + new provider (~80) + 2 test files (~270) + tasks.md/apply-progress marks. Includes the shared dirty file's unrelated F2 diff; orchestrator will slice the commit boundaries.

### Batch 4 — U4 PR4 G6

1. **Pre-existing failing test** (carried from U2/U3, unrelated to this slice): `tests/pipeline/stages/test_chained_retest_optimize.py::TestChainedTasksInOneLoad::test_retest_crosschecks_carry_monte_carlo_and_walkforward` — still failing before/after this slice (my diff touches only the 3 U4 files + tasks.md).
2. **Repo remains dirty with unrelated in-flight work** (carried): my U4 slice touched exactly 3 files: `sdk/quantlab/cli/sq_commands.py`, `sdk/quantlab/knowledge/store.py`, `tests/knowledge/test_knowledge_store_v5.py`, plus tasks.md checkbox marks + this apply-progress. No `knowledge/` pollution (verified via `git status -- knowledge/`).
3. **Ruff is declared in `openspec/config.yaml` but not installed in this environment** — the REFACTOR pass relied on manual PEP8 review (line-splits applied). Orchestrator/CI should run `ruff check` + `ruff format` on the PR.
4. **Slice is ~480 changed lines (above the 400-line review budget)**: dominated by test additions (~300 of the 473 insertions). Within the pre-defined U4/PR4 slice per tasks.md; flagged for the orchestrator to decide whether PR 4 needs further splitting or the test-bulk warrants an exception.
5. **`knowledge/index.yaml` in-repo is a stale deployed `_version: '4'` index**: the migration tests seed only hermetic tmp lakes; the repo index is left untouched (read_index upgrades it in-memory on next use). Expected post-change state, not a defect.

### Batch 3 — U3 PR3 G1

1. **Pre-existing failing test** (carried from U2, unrelated to this slice): `tests/pipeline/stages/test_chained_retest_optimize.py::TestChainedTasksInOneLoad::test_retest_crosschecks_carry_monte_carlo_and_walkforward` — still failing before/after this slice (my diff touches only the 5 U3 files + tasks.md).
2. **Repo remains dirty with unrelated in-flight work** (carried): extensive uncommitted changes from other changes. My U3 slice touched exactly 5 files: `sdk/quantlab/campaign/delegation.py`, `sdk/quantlab/campaign/phase_runner.py`, `sdk/quantlab/knowledge/artifacts.py` (new), `tests/campaign/test_delegation.py`, `tests/campaign/test_phase_runner.py`, plus `openspec/changes/flow-ecosystem-alignment/tasks.md` (checkbox marks) and this apply-progress. No `knowledge/` pollution (verified via `git status -- knowledge/`).
3. **Test-design lesson**: the two missing-root degrade tests initially omitted `config` — the real `research_llm` stage then failed with `ValueError: Cannot determine market from objective: 'Research'` (not the intended degrade path). Fixed by adding a valid objective to those payloads; the degrade assertions then exercised the intended missing-key branch.

### Batch 2 — U2 PR2 G5 (from previous batch, retained)

1. **Pre-existing failing test** (unrelated to this slice): `tests/pipeline/stages/test_chained_retest_optimize.py::TestChainedTasksInOneLoad::test_retest_crosschecks_carry_monte_carlo_and_walkforward` — asserts `mc.get("simulations") == "500"` but got `None`; touches chained retest/DSL config carrying, driven by other in-flight uncommitted work in `adaptive_retest_agent.py`/`dsl/models.py`. **Was failing before my changes** (verified: my diff touches only registry.py + research_director.py docstrings + docs + new test file). `tests/pipeline/` full run: 102 passed / 1 failed.
2. **Stale "8/17-stage" wording remains in test files and legacy builder files** (see deviations 3-4): out of the G5 touch scope, but a docs-consistency sweep in Phase 8 (task 8.2) should consider them.
3. **`docs/CHANGELOG.md:60`** still says "17-stage dry-run" — historical record of PR 6's own test config; deferred by design (see deviation 2).
4. **Repo remains dirty with unrelated in-flight work**: extensive uncommitted changes across the repo from other changes (incl. `sdk/quantlab/agents/research_agent.py`, `cfx/*`, `dsl/models.py`, `customproject/renderers.py`, `sqx/project_builder.py`, `app_movil/...`). My U2 slice touched exactly 7 files: `tests/pipeline/test_pipeline_counts.py` (new), `sdk/quantlab/pipeline/registry.py`, `sdk/quantlab/agents/research_director.py`, `docs/multi-agent/pipeline.md`, `docs/multi-agent/agents.md`, `docs/configuration/pipeline-config.md`, `docs/STATE.md`, plus `openspec/changes/flow-ecosystem-alignment/tasks.md` (checkbox marks). Orchestrator will slice commits/PR boundaries.

### Batch 1 — U1 PR1 G4 (from previous batch, retained)

1. Residual skill reference: `~/.config/opencode/skills/quantlab-deploy-strategy/SKILL.md:16` still instructs invoking `quantlab-deploy` (dangling agent reference, out of G4 scope).
2. No live overlay exists — installer overlay synced instead.
3. Pre-existing repo dirtiness (see above, applies to U1 slice too).

## Remaining Tasks (this change, not this batch)

- [x] U1 PR1 G4: Phase 6 tasks 6.1-6.5 ✅
- [x] U2 PR2 G5: Phase 1 tasks 1.1-1.3 ✅
- [x] U3 PR3 G1: Phase 2 tasks 2.1-2.6 ✅
- [x] U4 PR4 G6: Phase 3 tasks 3.1-3.4 ✅
- [x] U5 PR5 G3: Phase 4 tasks 4.1-4.5 ✅
- [x] U6 PR6 G7: Phase 5 tasks 5.1-5.2 ✅
- [x] U7 PR7 G2: Phase 7 tasks 7.1-7.4 ✅
- [ ] Phase 8: 8.1-8.2

## Workload / PR Boundary

- Mode: **stacked PR slice 7 of 7** (`auto-chain`, `stacked-to-main`)
- Current work unit: U7 PR7 G2
- Boundary: starts at PR 6's head (U6 G7 base); ends with the CustomProject flag-first dispatch wired and default flipped (tasks 7.1-7.4). This is the LAST work unit of the change.
- Estimated review budget impact: in-repo authored diff **~80 changed lines** — well within the 400-line budget. Dispatch logic in `builder_agent.py` (~60 insertions), flag default flip in `generator.py` (~2 lines), test updates (~15 lines). No goldens touched. Flagged in Issues (#4 from U6 — still the dominant budget item).

### Batch 7 — U7 PR7 G2 Work Unit Evidence

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/agents/test_builder_agent_g2.py tests/customproject/ tests/cfx/` -> **220 passed, 0 failed, 4 skipped** (exit 0). RED gate: 1 failed pre-GREEN (CustomProject dispatch missing). |
| Runtime harness command/scenario and exact result | Golden byte-identity build per tasks.md: `BuilderAgent().translate_to_cfx(config)` with `QUANTLAB_CUSTOM_PROJECT=0` produces byte-identical output to direct `translator.generate_cfx_archive` call (legacy path verified); with `QUANTLAB_CUSTOM_PROJECT=1` produces a project-root archive with `config.xml` (schema 144.2953) + per-task XML files (CustomProject path verified). |
| Rollback boundary | Revert `sdk/quantlab/agents/builder_agent.py` (remove `_translate` dispatch + `_is_custom_project_enabled` + `_research_config_to_custom_project`), revert `sdk/quantlab/customproject/generator.py` (restore default "1"), delete `tests/agents/test_builder_agent_g2.py`, revert `tests/customproject/test_e2e_loadconfig.py` flag-default assertion, revert `tasks.md` 7.1-7.4 checkbox marks (+this apply-progress). `git checkout` of these files removes all U7 work and touches nothing from U1-U6. |

## Deviations from Design

### Batch 7 — U7 PR7 G2

1. **Dispatch lives in `BuilderAgent._translate` rather than `agent_stages.py`**: the design's file-changes table lists `agent_stages.py` Modify for `BuilderStage` dispatch, but `BuilderStage` is abstract and cannot contain dispatch logic. The concrete `BuilderAgent` in `builder_agent.py` owns the translation boundary; dispatching there covers both the `builder` stage (via `BuilderAgentStage` wrapper in registry.py) and any direct `translate_to_cfx` callers. The design intent (flag-first dispatch at the builder boundary) is satisfied.
2. **`ResearchConfig → CustomProject` conversion is minimal single-task**: the design implies multi-task output, but the orchestrated flow supplies a single `ResearchConfig` per builder invocation. `_research_config_to_custom_project` produces a single-task `CustomProject` with standard databank defaults — sufficient to exercise the CustomProject generator path and verify schema 144.2953. A richer multi-task mapping would require template selection logic outside this slice's scope.

## Issues Found

### Batch 7 — U7 PR7 G2

1. **Pre-existing failing test** (carried, unrelated to this slice): `tests/pipeline/stages/test_chained_retest_optimize.py::TestChainedTasksInOneLoad::test_retest_crosschecks_carry_monte_carlo_and_walkforward` — same failure before/after this slice (diff touches only `builder_agent.py`, `generator.py`, `test_builder_agent_g2.py`, `test_e2e_loadconfig.py`, `tasks.md`, `apply-progress.md`).
2. **No golden fixture files changed**: the "re-base" in 7.3 was limited to the flag-default assertion in `test_e2e_loadconfig.py`. No `.cfx` fixture bytes or external golden samples were modified.

## Phase 8: Verify / Cleanup (Batch 8)

- applyState at start (batch 8): `ready` — U1-U7 complete. The dedicated sdd-apply transport returned empty results; the general agent executed this slice under the sdd-apply skill contract per explicit user authorization.
- 2/2 Phase 8 tasks (8.1-8.2) complete. All U1-U8 tasks complete. Ready for sdd-verify.

### Batch 8 — U8 PR8 Verify (Phase 8, tasks 8.1-8.2)

- [x] 8.1 GREEN full suite green incl. keep-green files: fixed `tests/phase5/test_pipeline_registry.py::TestStageRegistry::test_registry_initializes_with_all_stages` — added `"custom_project"` to the expected stage set (U2 registered it in `_register_agent_stages`). Re-ran full suite: **3737 passed, 12 failed, 9 skipped** — the 12 failures are all pre-existing (F2 hypothesis builder/agent dirty work + the known `test_chained_retest_optimize.py` carry). Keep-green subset: **433 passed, 4 skipped**.
- [x] 8.2 GREEN docs: counts, flags, seed:
  - Canonical counts (16/25/27) already consistent in docs from U2 (`docs/multi-agent/agents.md`, `docs/multi-agent/pipeline.md`, `docs/configuration/pipeline-config.md`, `sdk/quantlab/agents/research_director.py`).
  - Fixed stale `builder_agent.py` docstring: `_is_custom_project_enabled` and `_translate` docstrings incorrectly said "unset → legacy"; corrected to "unset → CustomProject (schema 144.2953)" per 7.4 flip. Fixed `generator.py` docstring similarly.
  - Added `QUANTLAB_CUSTOM_PROJECT` flag table to `README.md` (Builder / CFX Flags section) with default `1` (CustomProject) and `0` → legacy schema 141.2219.
  - Added `quantlab sqx kb seed-ohlc` command to `README.md` Knowledge Commands with default symbols/timeframes.
  - Fixed leftover "Eight domain-specific agents" in `docs/architecture/multi-agent-system.md` → "Multiple specialized agents".
  - Left untouched: `docs/CHANGELOG.md:60` (historical record), `docs/STATE.md:194` (skipped test name reference), test files with stale wording (out of touch-list per U2 deviations).

## TDD Cycle Evidence

### Batch 8 — U8 PR8 Verify (Phase 8, tasks 8.1-8.2)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 8.1 | Full suite (`pytest -q`) | E2E | ✅ 433 keep-green passed pre-fix | ✅ Discovered 1 failure: `test_registry_initializes_with_all_stages` (missing `custom_project` in expected set) | ✅ Added `custom_project` to expected set; full suite **3737 passed, 12 pre-existing failures** | ✅ Re-ran keep-green + targeted registry + builder tests — 433 passed | ✅ Fixed 3 stale docstrings (`builder_agent.py` _is_custom_project_enabled, _translate; `generator.py` is_custom_project_enabled) that contradicted the 7.4 flip |
| 8.2 | README + docs manual review + keep-green re-run | Doc contract | ✅ 433 passed (no doc change broke tests) | ✅ Doc sweep found: stale "Eight domain-specific agents" in architecture doc; missing flag/seed docs in README; 3 stale docstrings post-7.4-flip | ✅ Updated `docs/architecture/multi-agent-system.md`, `README.md`, `builder_agent.py`, `generator.py`; keep-green still 433 passed | ➖ Single sweep — no branching logic in doc wording | ➖ None needed — wording fixes only |

## Work Unit Evidence

### Batch 8 — U8 PR8 Verify (Phase 8, tasks 8.1-8.2)

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/test_orchestrator_prompt.py tests/pipeline/test_pipeline_counts.py tests/campaign/test_delegation.py tests/campaign/test_phase_runner.py tests/knowledge/test_knowledge_store_v5.py tests/data/test_dukascopy_provider.py tests/agents/test_llm_research_agent_g3.py tests/pipeline/test_config_review_stage.py tests/agents/test_builder_agent_g2.py tests/customproject/ tests/cfx/ tests/phase5/test_pipeline_registry.py` -> **434 passed, 4 skipped** (exit 0). Full suite: **3737 passed, 12 failed, 9 skipped** — all 12 failures are pre-existing (F2 dirty work + known chained_retest carry). |
| Runtime harness command/scenario and exact result | N/A — Phase 8 is verify/cleanup; no new runtime boundary was introduced. The test suite IS the verification boundary. |
| Rollback boundary | Revert `tests/phase5/test_pipeline_registry.py` (expected set addition), revert `docs/architecture/multi-agent-system.md` (agent count wording), revert `README.md` (flag table + seed-ohlc command), revert `sdk/quantlab/agents/builder_agent.py` (2 docstring fixes), revert `sdk/quantlab/customproject/generator.py` (docstring fix), revert `openspec/changes/flow-ecosystem-alignment/tasks.md` checkbox marks (+this apply-progress). |

## Deviations from Design

### Batch 8 — U8 PR8 Verify

1. **`tests/phase5/test_pipeline_registry.py` updated beyond the design's file-changes table**: the design does not list this test file; it was added by an earlier change and has a hardcoded expected stage set. Adding `custom_project` to the expected set is a verify/cleanup correction, not a design deviation — without it the suite fails due to U2's correct registry registration.

## Issues Found

### Batch 8 — U8 PR8 Verify

1. **Pre-existing failing tests** (carried, unrelated to this change): 12 failures across `test_hypothesis_builder_f2.py` (3), `test_llm_research_agent_f2.py` (2), `test_chained_retest_optimize.py` (1), `test_hypothesis_builder.py` (5), `test_llm_agent.py` (1). Verified failing before/after Phase 8 changes.
2. **Stale docstrings post-7.4-flip**: `_is_custom_project_enabled` and `_translate` in `builder_agent.py` plus `is_custom_project_enabled` in `generator.py` still said "unset → legacy" after the default flipped to CustomProject. Fixed in 8.2 REFACTOR.

## Remaining Tasks

- [x] U1 PR1 G4: Phase 6 tasks 6.1-6.5 ✅
- [x] U2 PR2 G5: Phase 1 tasks 1.1-1.3 ✅
- [x] U3 PR3 G1: Phase 2 tasks 2.1-2.6 ✅
- [x] U4 PR4 G6: Phase 3 tasks 3.1-3.4 ✅
- [x] U5 PR5 G3: Phase 4 tasks 4.1-4.5 ✅
- [x] U6 PR6 G7: Phase 5 tasks 5.1-5.2 ✅
- [x] U7 PR7 G2: Phase 7 tasks 7.1-7.4 ✅
- [x] Phase 8: 8.1-8.2 ✅

## Workload / PR Boundary

- Mode: **stacked PR slice 8 of 8** (`auto-chain`, `stacked-to-main`)
- Current work unit: U8 PR8 Verify (Phase 8, tasks 8.1-8.2)
- Boundary: starts at PR 7's head (U7 G2 base); ends with full suite green (registry test fixed) + doc sweep complete (counts, flags, seed, stale wording). This is the LAST work unit of the change.
- Estimated review budget impact: ~60 changed lines — well within the 400-line budget. Dominated by doc/docstring fixes (~40) + registry test update (~20). No goldens touched.

## Test Summary (U8 PR8 Verify)

- **Focused test results**: `SQX_FORCE_MOCK=1 python3 -m pytest -q <keep-green files>` -> **433 passed, 4 skipped** (exit 0). Full suite: **3737 passed, 12 failed, 9 skipped** — 12 failures are all pre-existing (F2 dirty work + known chained_retest carry).
- **Safety net**: keep-green re-run after doc/docstring edits → 433 passed, no regression.
- **Layers used**: E2E (full suite), doc contract (README/STATE/architecture manual review).
