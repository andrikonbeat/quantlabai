# Apply Progress — knowledge-seeding-education (Batch 1 / PR 1)

## Batch Scope

- Tasks: T-1.1..T-1.6 (Phase 1, all of PR 1) — WU1 (seed flow + gate) + WU2 (goldens + index).
- Mode: Strict TDD (orchestrator-injected). Delivery: auto-chain, stacked-to-main. Hybrid artifacts.
- Chain strategy: stacked-to-main (from tasks.md guard lines).

## Empirical Band Confirmation (T-1.5) — ACTUAL NUMBERS

First real seed run against the pinned install (`assets/SQX_144_2953_linux_20260601`, doc
`doc_dev/SQX Builder Config.md`, curated `CFX_EVIDENCE_MAP` with 74 entries) produced:

| Metric | Actual | Design-proposed band | Decision |
|---|---|---|---|
| total | **82** | 82 | within |
| verified | **74** | [65, 73] | DEVIATES (74 > 73) |
| needs_review | **8** | [9, 15] | DEVIATES (8 < 9) |
| seeded | **0** | 0 | within |

Actual distribution 74/8 deviates from the design's provisional [65,73]/[9,15] band, so per
T-1.5 the band was **adjusted and frozen** at verified `[71, 77]`, needs_review `[5, 11]`
(74±3 / 8±3 drift window) in `validation.py` constants (`VERIFIED_MIN/MAX`,
`NEEDS_REVIEW_MIN/MAX`). The RED tests import these constants — single source of truth, no
duplicated literals to drift. Real-lake gate re-check (`quantlab sqx kb validate` against the
committed goldens): all 4 checks PASS, exit 0, counts `{total: 82, verified: 74, needs_review: 8, seeded: 0}`.

## Completed Tasks

- [x] T-1.1 RED `sdk/tests/test_kb_seed_validation.py` (27 tests: schema violation names field, stale index, partial coverage, dangling evidence, empty evidence_ref, band in/out, needs_review success, report shape, CFX map curation, E2E flow, CLI exit codes)
- [x] T-1.2 GREEN `sdk/quantlab/knowledge/kb/validation.py` — `SeedValidationReport`, `validate_seed` (pure, read-only: schema / index coverage / evidence / distribution checks)
- [x] T-1.3 GREEN `sdk/quantlab/knowledge/kb/seeding_flow.py` — `CFX_EVIDENCE_MAP` (74 curated entries), `run_seed_flow` (seed_from_doc → bulk_verify → demote → rebuild_index → gate)
- [x] T-1.4 CLI wiring `sdk/quantlab/cli/sq_commands.py` — `cmd_kb_seed` runs the full flow + gate (exit 0/1), new `sqx kb validate` (idempotent re-check), gate report printer
- [x] T-1.5 Empirical band confirmation (table above) — band frozen [71,77]/[5,11]
- [x] T-1.6 Goldens + index: 82 YAMLs committed under `knowledge/structured/sqx-kb/144.2953/parameters/{8 tabs}/`, `knowledge/index.yaml` rebuilt to v4 with `kb_parameters` coverage == 82 (REQ-403)

## TDD Cycle Evidence

| Task | RED (test written first) | GREEN (impl passes) | REFACTOR |
|---|---|---|---|
| T-1.1 → T-1.2 | 27 gate tests against tmp_path lakes (REQ-209 scenarios) | `validate_seed` passes 27/27 | Pure/read-only gate; errors name param+field |
| T-1.3 | E2E flow tests (`TestRunSeedFlow`) before `run_seed_flow` | `run_seed_flow` passes E2E + demote tests | `CFX_EVIDENCE_MAP` extracted as curated data; `_default_evidence_base` hook |
| T-1.4 | CLI exit-code tests (`TestKbSeedCliExitCodes`, `TestKbValidateCliExitCodes`) | `cmd_kb_seed`/`cmd_kb_validate` exit 0/1 per gate | `_DEFAULT_EVIDENCE_BASE_FACTORY` monkeypatch seam |
| T-1.5 | Band tests (`TestDistributionBand`) import constants | Real-lake gate PASS | Constants frozen; ±3 drift window |

## Work Unit Evidence

| Evidence | WU1 (gate + flow + CLI + tests) | WU2 (goldens + index + artifacts) |
|---|---|---|
| Focused test command + result | `cd sdk && SQX_FORCE_MOCK=1 python3 -m pytest tests/test_kb_seed_validation.py -q` → **27 passed in 7.26s** | `cd sdk && python3 -c "… validate_seed('../knowledge') …"` → counts `82/74/8/0`, checks all True, ok True, errors [] |
| Runtime harness + result | `cd sdk && python3 -c "… cmd_kb_validate …"` on real lake → Gate counts 82/74/8/0, `[PASS]` ×4, **exit 0** | `knowledge/index.yaml` v4 `_generated` rebuilt; `grep -c sqx_version 144.2953` → 82 coverage entries |
| Rollback boundary | Revert 2 commits: delete `validation.py`, `seeding_flow.py`, revert `sq_commands.py`/`kb/store.py`/`knowledge/store.py`/`test_kb.py` hunks — KB returns to empty-but-functional without touching goldens | Delete `knowledge/structured/sqx-kb/144.2953/`, restore prior `index.yaml` (proposal rollback) |

## Deviations from Design

1. **Band adjusted** (design [65,73]/[9,15] → frozen [71,77]/[5,11]) — mandated by T-1.5 empirical confirmation; actual first seed = 74/8.
2. **`sdk/quantlab/knowledge/kb/store.py` + `sdk/quantlab/knowledge/store.py` modified** (proposal lists store as out-of-scope): `_safe_param_filename()` replaces `/` in param names ("Stop/Limit entry blocks", "Minimum / Maximum SL", "Opt. Profile / Sys. Param. Permutation") so the REQ-202 `parameters/{tab}/{param}.yaml` layout stays flat; `rglob` keeps list/index rebuild tolerant. Required for the golden layout contract; backward compatible.
3. **`sdk/tests/test_kb.py` one test adapted** (`test_kb_seed_exit_0` → `test_kb_seed_gate_fails_exit_1_on_partial_doc`): `cmd_kb_seed` now runs the REQ-209 gate, so a partial-doc seed exits 1 (old assertion asserted removed behavior). Proposal's "don't alter 32 KB tests" violated minimally and necessarily.
4. **`knowledge/structured/sqx-version/` NOT committed**: contains only a stray pre-existing `_template→_template/.gitkeep` junk dir (dated Aug 9, predates change). Left untracked — flagging for orchestrator.

## No-Regression Test Counts (post-change, repo root, `SQX_FORCE_MOCK=1 PYTHONPATH=sdk`)

- `sdk/tests/test_kb_seed_validation.py`: **27 passed** (new)
- `sdk/tests/test_kb.py`: **32 passed** (existing, 1 adapted)
- `sdk/tests/test_conformance.py`: **8 passed**
- `tests/campaign/test_flow_integrity.py`: **11 passed** (prior change; must run from repo root — CWD-dependent doc path)
- `sdk/tests/test_knowledge.py`: **19 passed, 4 failed** — failures PROVEN pre-existing at HEAD e8ba949 via clean worktree (`TestKnowledgeStoreIndexV4` asserts `_version=="4"`; `read_index` upgrades stale indexes to v5 — stale tests, unrelated to this change). Not fixed (out of scope).

## Generated Goldens

82 parameter YAMLs + rebuilt `knowledge/index.yaml` (v4, `kb_parameters`==82) — excluded from the
authored-line review budget, included in complete snapshot identity and verification.

## Workload / PR Boundary

- Mode: stacked PR slice 1 (auto-chain, stacked-to-main), 2 work-unit commits.
- Boundary: starts at `e8ba949`; ends at PR 1 = WU1 (gate+flow+CLI+tests) + WU2 (goldens+index+artifacts).
- Estimated review budget impact: authored additions+deletions ≈ **1,020 lines** (test module ~506,
  validation 220, seeding_flow 228, CLI/store/test_kb diffs ~128, artifacts ~60) — PR 1 as delivered
  exceeds the 400-line planning guard; test module is ~half. Recommend orchestrator split the test
  module into its own stack slice or record `size:exception` at PR creation.
