# Archive Report: Flow-Ecosystem Alignment

**Change**: flow-ecosystem-alignment
**Archived**: 2026-08-18
**Artifact store**: hybrid
**Mode**: Strict TDD

## Final State

- **Tasks**: 33/33 complete (5+3+6+4+4+2+2+2) across U1-U7 + Phase 8 verify/cleanup.
- **PR plan**: 8 stacked PR slices (U1-U7 + Phase 8 verify/cleanup).
- **Tests**: 433 focused tests passed, 0 new failures. 12 pre-existing failures carried (F2 dirty work + chained_retest_optimize).
- **Build**: verification blocked by missing `build` module (pre-existing infra gap, not a regression).
- **Transport deviation**: sdd-apply sub-agent transport returned empty results for U4-U8; user authorized `general` agent to execute those slices under the sdd-apply skill contract. U1-U3 executed via sdd-apply successfully before the transport failure.

## Specs Synced

| Domain | Action | Details |
|--------|--------|---------|
| knowledge-store | Updated | 3 added requirements (Real OHLC Dataset Seeding, Operational Directory Population, Index v5 Migration Acceptance) |
| pipeline-core | Updated | 1 added requirement (Stage Registry as Canonical Source) |
| quantlab-orchestrator | Updated | 3 added requirements (Legacy Agent Retirement, Deny-First Bash Scope, Live Config Restore Path) |
| custom-project-generator | Updated | 2 added requirements (Pipeline Builder Integration, CustomProject Stage Registration) |
| full-campaign-lifecycle | Updated | 1 added requirement (Canonical Pipeline Entry Counts) |
| parameter-educational-table | Updated | 1 added requirement (Reviewer-Persisted Teaching Table) |
| sqx-translator | Updated | 1 added requirement (Legacy Dialect Flag Guard) |
| campaign-phase-delegation | Updated | 1 added requirement (Stage Artifact Persistence) |
| llm-research | Updated | 1 added requirement (Dukascopy Market Context) |
| technical-indicators | Updated | 1 added requirement (IndicatorEngine Production Wiring) |
| research-agent | Updated | 1 added requirement (Research Stage Canon) |

## Source of Truth Updated

The following main specs now reflect the new behavior:
- `openspec/specs/knowledge-store/spec.md`
- `openspec/specs/pipeline-core/spec.md`
- `openspec/specs/quantlab-orchestrator/spec.md`
- `openspec/specs/custom-project-generator/spec.md`
- `openspec/specs/full-campaign-lifecycle/spec.md`
- `openspec/specs/parameter-educational-table/spec.md`
- `openspec/specs/sqX-translator/spec.md`
- `openspec/specs/campaign-phase-delegation/spec.md`
- `openspec/specs/llm-research/spec.md`
- `openspec/specs/technical-indicators/spec.md`
- `openspec/specs/research-agent/spec.md`

## Deviations from Design

All deviations documented in `apply-progress.md` are recorded here as final state:

- G4 monitor pruned alongside deploy/run/status/compare.
- Overlay target resolved to installer overlay (no live `~/.config/opencode/overlay.json` exists).
- StageRunResult return type changed from `dict[str, Any]` to `StageRunResult` in `_run_sdk_stage`.
- `next_gate` uses phase ids, not `HUMAN_*` gate ids.
- Failed-stage error log is `{phase}_{stage}.error.json`, not `.log`.
- Mechanical executor `artifacts` `[]` + risk note (no synthetic `{phase}_handoff.json`).
- `custom_project` registered to `BuilderStage` in registry.py.
- `CHANGELOG.md` left untouched (historical record).
- Teaching table persistence via `config_review_stage.py` + delegation.py hunks.
- Dispatch in `BuilderAgent._translate` rather than `agent_stages.py`.
- Docstrings fixed post-7.4-flip.
- Registry expectation updated in `test_pipeline_registry.py`.

## Engram Observations Read

- #1008 — `sdd/flow-ecosystem-alignment/tasks` (stale intermediate snapshot: shows Phase 8 unchecked; overridden by filesystem `tasks.md` and orchestrator final-state facts showing 33/33 complete).

Note: Engram topics for proposal, design, verify-report, and apply-progress were not found under the expected keys. The archive report relies on the filesystem artifacts for those.

## Verification Notes

### Verdict Contradiction in verify-report

The verify-report contains a contradiction:
- YAML frontmatter declares `verdict: fail` with `critical_findings: 0` and `blockers: 0`.
- Narrative section states "PASS WITH WARNINGS".

This contradiction is recorded explicitly. The absence of CRITICAL findings means the archive is not blocked by the Native Review Receipt Gate. The build failure (`python3 -m build` exits 1 because the `build` module is not installed) is a pre-existing environment gap, not a regression from this change.

## Key Learnings

1. The Mechanical Copy Contract requires `diff -r` readback for every archive move, and the archive-report is additive-only.
2. Engram does not always contain all SDD artifacts; missing observations must be recorded explicitly rather than assumed present.
3. Delta spec merging for 11 domains is feasible with Read/Edit/Write when no main spec is absent, but mechanical copy is mandatory for new main specs.
4. Verify-report verdict fields can contradict narrative summaries; both must be preserved in the archive record.
5. Transport failures for sdd-apply sub-agents require explicit user authorization for fallback execution, which must be documented in the archive report.
