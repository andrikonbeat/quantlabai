# Apply Progress: Phase 5b-5e — Advanced Features

## State

**IMPLEMENTED (37/40)** — all code phases (1-4) verified in earlier audit; cross-cutting
phase re-checked during close with two documented gaps (5.2, 5.3). Archived.

## Progress

| Task | Status | Evidence |
|------|--------|----------|
| 1.1–1.9 reporting core | ✅ | `reporting/{models,generator,templates,__init__}.py`; `pyproject.toml:109` reporting extra; `tests/phase5/test_reporting.py` |
| 2.1–2.10 reporting CLI + knowledge query | ✅ | `reporting/cli.py`; `knowledge/{models,query,indexer}.py`; `store.py` v2 schema; `tests/phase5/{test_reporting_cli,test_knowledge_cli}.py` |
| 3.1–3.9 pipeline CLI | ✅ | `pipeline/registry.py` (410,513); `cli/pipeline_commands.py`; `cli/main.py` wiring; `tests/phase5/{test_pipeline_registry,test_pipeline_cli}.py` |
| 4.1–4.5 stats aggregation | ✅ | `stats/aggregation.py`; `tests/phase5/test_stats_aggregation.py` |
| 4.6 stats integration tests | ❌ | Requires Phase 4/5 modules not yet merged (task note) |
| 5.1 orchestrator report delegate | ✅ | `phase4/stages/__init__.py:475-512` -> `ReportGenerator` |
| 5.2 orchestrator tests | ❌ absent | `tests/phase4/test_stages.py` not created; covered by `tests/integration/{test_full_pipeline,test_smoke}.py` |
| 5.3 cli exports | ❌ by design | `__init__` keeps runner+daemon only, avoids circular import; commands via `cli_entry()->main` (smoke-proven) |
| 5.4 e2e smoke | ✅ | `tests/integration/test_smoke.py` — all 4 commands, 1 passed 1.24s |
| 5.5 docs | ✅ | README 3 sections; guides/{reporting,knowledge-query}.md; configuration/pipeline-yaml.md |
| 5.6 full-suite regression | ✅ | 4100 passed; 51 pre-existing env failures (see verify) |

## Re-verification Findings (2026-10-07 close)

1. **5.1 was already implemented** (delegate to `ReportGenerator`, `phase4/stages/__init__.py:475-512`)
   — earlier audit marked it pending; code proves otherwise. Marked with evidence.
2. **5.4 smoke exists under a different name/path**: `tests/integration/test_smoke.py`
   (`test_phase5f_i_smoke_full_pipeline`), shared with phase5f-i 3.1. Naming drift corrected.
3. **5.3 intentionally absent**: `cli/__init__.py` explicitly defers command imports to runtime
   to avoid circular imports. Adding the requested export would regress the import graph; the
   commands are reachable and smoke-exercised via the entry point.
4. **5.2 test file never created**, same pattern as phase5f-i 1.6/2.4 — behavior covered
   integrationally, dedicated unit file missing. Recorded, not marked done.

## Test Evidence

- Full suite: `SQX_FORCE_MOCK=1 python3 -m pytest -q` → **4100 passed, 51 failed, 29 skipped** (343s)
- Failure breakdown (all pre-existing env/config classes, zero overlap with named regression areas):
  - `tests/campaign/test_prompt_sync.py` + `tests/test_orchestrator_prompt.py` + `TestOpencodeJson*`: 42 — live config/prompt copies drifted from repo (repo-wins sync not re-run; config edited by parallel session)
  - `tests/cfx/*` + `tests/compiler/*`: 8 — require real `sqcli` (StrategyQuant X) or CFX schema version
  - `sdk/tests/test_cli.py::test_windows_binary_naming`: 1 — linux platform expectations
- Close batch commits touched **docs/specs only** (5af822d, bac5965, fe26d85 — no runtime code), so none of the 51 can be regressions from this batch.

## Next Action

Archived as `archive/2026-10-07-phase5b-e/` (follow-ups: 5.2 test file, 4.6 integration tests; 5.3 intentionally deferred).