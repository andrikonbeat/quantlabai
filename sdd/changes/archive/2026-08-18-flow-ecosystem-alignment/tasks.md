# Tasks: Flow-Ecosystem Alignment

## Review Workload Forecast

Estimate: ~2,700 authored lines (goldens excluded).

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Work Units

Tests run as `SQX_FORCE_MOCK=1 python3 -m pytest -q <path>`.

- U1 PR1 G4 config security: test `tests/test_orchestrator_prompt.py`; harness `json.load(opencode.json)`+restart; rollback backup+overlay
- U2 PR2 G5 counts+registry: test `tests/pipeline/test_pipeline_counts.py`; harness N/A (code-asserted); rollback revert test+wording
- U3 PR3 G1 envelope+writers: test `tests/campaign/test_delegation.py`; harness `test_phase_runner.py` (mock); rollback revert 3 SDK files
- U4 PR4 G6 seed-ohlc+v5: test `tests/knowledge/test_knowledge_store_v5.py`; harness `kb seed-ohlc` (mock); rollback drop subcommand+helper
- U5 PR5 G3 provider+zones: test `tests/data/test_dukascopy_provider.py`; harness prompt test (mock); rollback drop provider+block
- U6 PR6 G7 teaching table: test `tests/pipeline/test_config_review_stage.py`; harness review test (mock); rollback revert config_review_stage
- U7 PR7 G2 flag-first+flip: test `tests/customproject tests/cfx`; harness golden byte-identity build; rollback flip flag to legacy

## Phase 1: G5 Canonical Counts

- [x] 1.1 RED `tests/pipeline/test_pipeline_counts.py`: 16/25/27; research first; custom_project lookup raises
- [x] 1.2 GREEN remove "17-stage"/"8 agents" wording (research_director.py, docs)
- [x] 1.3 GREEN register `custom_project` in `sdk/quantlab/pipeline/registry.py`

## Phase 2: G1 Artifact Writers

- [x] 2.1 RED `tests/campaign/test_delegation.py`: envelope+files, failed→HOLD, missing root→risks, no claim
- [x] 2.2 GREEN create `sdk/quantlab/knowledge/artifacts.py` (proposal/spec writers)
- [x] 2.3 GREEN `_run_sdk_stage`: outcome JSON + envelope; timestamps here (Q2)
- [x] 2.4 GREEN `phase_runner.py`: inject knowledge_root+campaign_id (D3)
- [x] 2.5 GREEN hooks: proposal→research; spec→hypothesis/config (Q1)
- [x] 2.6 REFACTOR idempotent re-run; write-failure folds (REQ-802)

## Phase 3: G6 Seed + v5 (SQX)

- [x] 3.1 RED `tests/knowledge/test_knowledge_store_v5.py`: v4→v5 + v5 keys
- [x] 3.2 RED seed: EURUSD default (Q3) M1/M5/H1; env-gap names dep
- [x] 3.3 GREEN `store.py` datasets cache helper
- [x] 3.4 GREEN `sq_commands.py` seed-ohlc (`add_sqx_subparser`:333; mock per `cmd_kb_seed`:124)

## Phase 4: G3 Dukascopy + Zones

- [x] 4.1 RED `tests/data/test_dukascopy_provider.py`: bars normalized; gap→[] no raise
- [x] 4.2 RED prompt: zones+source; gap→omitted; insufficient_data
- [x] 4.3 GREEN create `sdk/quantlab/data/dukascopy/provider.py`
- [x] 4.4 GREEN `llm_research_agent.py`: market block via IndicatorEngine (no series)
- [x] 4.5 GREEN cache fetch + rebuild_index

## Phase 5: G7 Teaching Table

- [x] 5.1 RED config_review: persisted, in verdict+artifacts, fallback/placeholder rows
- [x] 5.2 GREEN `config_review_stage.py` via `build_teaching_table` (kb/teaching.py:39)

## Phase 6: G4 Live Config (outside VCS)

- [x] 6.1 RED `tests/test_orchestrator_prompt.py`: no deploy/monitor, no run/status/compare, deny-first, no sdk/pipeline/*
- [x] 6.2 BACKUP opencode.json (timestamped)
- [x] 6.3 GREEN edit: remove agents (:519-534), deny-first bash (:83-103), fix path (:523)
- [x] 6.4 GREEN overlay.json sync + orchestrator.md prune (:26-29,:135-153)
- [x] 6.5 verify 6.1 green

## Phase 7: G2 Flag-First (LAST)

- [x] 7.1 RED dispatch: flag=1→CustomProject; flag=0→legacy byte-identical
- [x] 7.2 GREEN `agent_stages.py` dispatch; legacy default (D7)
- [x] 7.3 DELIBERATE re-base tests/customproject/ + tests/cfx/ goldens
- [x] 7.4 FLIP default→CustomProject (last task)

## Phase 8: Verify / Cleanup

- [x] 8.1 full suite green incl. keep-green files
- [x] 8.2 docs: counts, flags, seed