# Tasks: SDD Closure — Audit-driven close of active changes

Objective: close the 10 active SDD changes against verified reality (audit 2026-10-07).
Audit evidence: Engram observation "Auditoría SDD completa: 10 changes activos mapeados contra código".
Rule: verify-report must reflect HEAD, not stale claims. Every archived change gets complete artifact set
(proposal, specs/, design, tasks, apply-progress, verify-report, archive-report) + official spec sync.
Delivery strategy: one work-unit commit per change close; user decides push/PR/merge.

- [x] T1 health-score-system — DOCS-DRIFT → closed. Commit `5af822d`. Spec HS-REQ-05 amended (AD-3 pass-through). 89/89 tests, 12/12 scenarios, verdict pass.
- [x] T2 phase4-jforex-portfolio-optimizer — closed. Commit `bac5965` (5 delta specs + 6 official specs synced + proposal corrected + success-criteria triage). 657/657 tests, verify pass.
- [x] T3 phase5f-i — closed. Commit `fe26d85`. Smoke exists as tests/integration/test_smoke.py; benchmark overlay at generator.py:166-175; docs under configuration/+guides/; 1.6/2.4 test files honestly open.
- [x] T4 phase5b-e — closed. Commit `0b41e45`. 5.1 delegate verified (phase4/stages/__init__.py:475-512), 5.2/5.3 noted, 5.4 smoke shared, 5.6 full suite 4100 passed (51 pre-existing env fails classified).
- [x] T5 phase5-pipeline-core — closed. Commit `7cef6aa`. Spec sqx-cli-wrapper amended AD-pipe-1 (status→history); 4.3 metric + 6.4/6.7 test files as follow-ups; backcompat 657.
- [x] T6 hypothesis-builder — closed. Fix commit `99109d5` (H2: validation errors propagate, TDD RED→GREEN 68 passed) + archive `9fc284b`. H1 rejected (feature-flag WU8a contract; adding stages would duplicate engine).
- [x] T7 research-agent-improvements — CLOSED. Fix `cc51e7c` (F1-03 wiring both modes + 2 tests, F1-05 LRU frozenset cache + tests, F3 KnowledgeLakeFeedbackWriter + HypothesisFeedbackRecord + tests; removed try/except Exception anti-patterns from delegated worker) + archive `1faa5f5`. 122 targeted / 615 regression passed; verify-report replaces prior FAIL with pass. Follow-ups: build_pipeline docstring (9 vs 11 stages) doc-only; uncommitted sqx_doc_provider `_registry_key` fix tracked separately.
- [x] T8 multi-agent-research-system — CLOSED. Commit `a7d79e7` (docs(sdd) close + git mv). 127/127 tasks verified; PR5/PR6 implementados pero sin marcar → reconciliados con evidencia path:line (store.py:1214/1252, memory.py, query.py:138/201, pipeline_commands.py, agent_commands.py, smoke test auto-approve). Verify-report viejo (PR1-only, PASS WITH WARNINGS) refutado: HOLD existe (gate_interceptor.py:33,42,156), notifications existe (models.py:61). Follow-ups: naming search_agent_memory vs query_agent_memory; no CHANGELOG.md en repo.
- [x] T9 research-agent-enhancements — CLOSED. Commit `7e85f59` (docs(sdd) close + git mv). 127/127 tasks verified; 811 tests passing, full suite green. Specs updated: llm-research, hypothesis-builder, knowledge-store, knowledge-memory. Follow-ups: naming search_agent_memory vs query_agent_memory; no CHANGELOG.md in repo; build_pipeline docstring stage-count drift (9 vs 11).

Next: SDD closure complete — all 10 changes audited and closed.