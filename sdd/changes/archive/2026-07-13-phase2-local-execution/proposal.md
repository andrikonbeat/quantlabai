# Proposal: Phase 2 — SQX Local Execution Pipeline

## Intent

Connect Phase 1's DSL models, translator, and result readers into an end-to-end campaign execution pipeline that manages the full sqcli lifecycle: license check, campaign start, progress monitoring, result export, and result ingestion. Without this, users must manually run sqcli and stitch results together.

## Scope

### In Scope
- Fix `RealExecutor` argument parsing for `key=value` syntax with spaces
- `CommandDispatcher` — proper sqcli command construction, daemon lifecycle
- `LicenseManager` — license state detection via `sqcli -license action=info`
- Pipeline models (`CampaignStatus`, `CampaignPhase`, `CampaignResult`) + error types
- `CampaignRunner` — sequential flow: translate → dispatch → poll → export → read → compute → store
- Progress callback protocol for long campaigns (30min+)
- Checkpoint/recovery, configurable retry, per-phase timeout (PR 3)
- Full test coverage with MockExecutor for all phases
- 3-chained-PR delivery: Foundation → Core CampaignRunner → Resilience

### Out of Scope
- HTTP/REST-based sqcli integration (unknown API surface — revisit with license)
- Multi-campaign scheduling or queuing
- Real-time market data feed
- Web UI for campaign monitoring
- sqcli binary distribution or license provisioning
- Reverse-engineering unknown databank export formats

## Capabilities

> **Contract for sdd-spec**: each new capability becomes a spec file; each modified capability gets a delta spec.

### New Capabilities
- `campaign-orchestrator`: End-to-end campaign lifecycle (start via CFX, monitor via status polling, export results, ingest into reader/stats/knowledge). Sequential execution flow with progress callbacks. Checkpoint save/restore.
- `license-manager`: License state detection (`sqcli -license action=info`), status reporting, activation support (`sqcli -license action=update`).
- `pipeline-error-types`: Pipeline-specific error hierarchy — `LicenseError`, `CampaignError` extending `QuantLabError`.

### Modified Capabilities
- `sqx-cli-wrapper`: RealExecutor argument handling upgraded from `command.split()` to structured key=value construction with space handling. `CommandDispatcher` abstraction for session management (start daemon, send commands, stop). Campaign lifecycle commands (`start`, `loadconfig`, `status`, `stop`, `export`). Subprocess result model extended with command metadata.

> **No spec changes needed** for `research-dsl`, `result-reader`, `statistics-engine`, `knowledge-storage` — they are pipeline consumers, not changed by pipeline orchestration.

## Approach

Approach A (Full Pipeline Orchestrator) in 3 chained PRs under 400 lines each:

1. **PR 1 — Foundation**: Fix RealExecutor, add CommandDispatcher, LicenseManager, pipeline models, error types. Testable with MockExecutor.
2. **PR 2 — Core CampaignRunner**: Sequential execution flow + progress callback protocol. Translate → dispatch → poll → export → read → compute → store.
3. **PR 3 — Resilience**: Checkpoint/recovery JSON, partial failure handling, configurable retry, per-phase timeout.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `cli/runner.py` | Modified | RealExecutor arg handling, daemon lifecycle |
| `tools/exceptions.py` | Modified | Add LicenseError, CampaignError |
| `tools/platform.py` | Modified | Add sqcli base dir resolution |
| `pipeline/` | New | `models.py`, `license.py`, `dispatcher.py`, `campaign.py`, `progress.py` |
| `tests/test_pipeline.py` | New | Full pipeline test suite |
| `specs/sqxj-cli-wrapper` | Modified | New campaign, daemon, and license requirements |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Unknown sqcli status output format | Med | Pluggable status parser, test with MockExecutor |
| Cannot test real execution without license | High | 90%+ coverage with MockExecutor, integration flagged |
| CFX schema may be incomplete | Low | Validate against Builder/project.cfx as reference |

## Rollback Plan

Per PR: `git revert <merge-commit>`. No database or schema changes — pure code and test artifacts. If config introduced, restore previous `config.yaml`.

## Dependencies

- Licensed SQX/sqcli binary (optional — MockExecutor covers dev)
- Phase 1 modules: translator, result-reader, statistics-engine, knowledge-storage

## Success Criteria

- [ ] All 124 existing tests continue passing
- [ ] `CommandDispatcher` constructs correct `key=value` args for all 8 sqcli command types
- [ ] `CampaignRunner` orchestrates full flow with MockExecutor (translate → dispatch → poll → export → read → compute → store)
- [ ] Progress callbacks fire at each phase transition
- [ ] Checkpoint save/restore survives mid-campaign restart
- [ ] Retry logic handles transient failures (3 attempts, configurable backoff)
- [ ] Pipeline errors raised for: missing license, campaign timeout, export failure
