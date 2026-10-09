# Proposal: Knowledge Memory System

## Intent

Campaigns are isolated one-shots: decisions and lessons die each session. Make the lake durable Git-versioned memory (Engram = session memory; OpenSpec = requirements), build an evidence-based SQX parameter KB, detect SQX version drift before it breaks pinned 144.2953.

## Scope

### In Scope
- **T1 — Persistent memory**: reconcile taxonomy (raw/structured/graph/embeddings/datasets/pipeline-runs/agent-memory + sqx-kb/ + sqx-version/); save_decision at phase boundaries via Result Contract; engram complement; retrieval via injected context + QueryBuilder; self-correction; training pipeline (JSONL curated/deduped/privacy-scrubbed); privacy deny-list + hashed campaign IDs.
- **T2 — SQX parameter KB**: YAML-per-parameter at `structured/sqx-kb/{sqx_version}/parameters/{tab}/{param}.yaml`; seeded from SQX Builder Config.md, verified vs real configs; consumed by builder_agent + config_reviewer (teaching table, small-account guidance); `quantlab sqx kb` CLI.
- **T3 — Version detection**: `LicenseInfo.build_number`; preflight in `cli_wrapper._dispatch_real`; `quantlab sqx check-version`; migration checklist → `structured/sqx-version/{old}→{new}/`; KB params → needs_review.

### Out of Scope
Regime fix (pyc-only), deploy/live-ops, demo-deploy automation, changelog polling.

## Proposal Question Round (assumptions for spec)

1. MVP capture: decisions + Result envelopes + configs; backtest artifacts deferred.
2. KB: seed all 8 tabs, verify subset first; building-blocks deferred.
3. Version detection preflight-only; no auto-migration/blocking.
4. Doc gaps → `needs_review`; never invent.
5. Privacy: deny-list + hashes; training data stays local.

## Capabilities

### New Capabilities
- `knowledge-memory`: capture, engram complement, retrieval injection, self-correction, training, privacy
- `sqx-parameter-kb`: schema, seeding, verification, consumption, teaching table, CLI
- `sqx-version-detection`: build probe, preflight, drift checklist, KB invalidation

### Modified Capabilities
- `knowledge-storage`: taxonomy reconciliation, index v4, new dirs
- `knowledge-query`: injected-context retrieval + KB query surface
- `license-manager`: `build_number` structured field
- `sqx-cli-wrapper`: version preflight hook

## Approach

- **T1**: lake = durable memory; capture at boundaries; inject at prompt layer.
- **T2**: YAML-per-parameter; schema: sqx_name, tab/section/type, default/range, what_it_does, how_it_works_in_sqx, quant_trading_role, hypothesis/edge relation, small-account rec, status lifecycle, evidence_ref.
- **T3**: parse `build_number` from `sqcli -license`; compare vs pinned; on mismatch codegraph scan → checklist.

## Affected Areas

| Area | Impact |
|------|--------|
| `knowledge/` | taxonomy, index v4, KB store |
| `phase4/stages/`, `campaign/flow.py` | stage layout, save hooks |
| `agents/` | complement, KB consumption |
| `pipeline/license.py` | build_number |
| `sqx/`, `customproject/` | preflight, KB consumers |
| `cfx/`, dashboard, prompts, `doc_dev/` | version awareness, seeds |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Taxonomy drift | Med | conformance test |
| Retention vs training | Med | dedup + curation policy |
| KB content volume | High | iterative verification |
| Doc gaps → invented params | High | needs_review only |
| No SQX in CI | Med | dry-run mocks |
| 144.2953 hardcoding | Med | central constant + detection |

## Rollback Plan

- **T1**: additive (new dirs/hooks), config-disabled; index v4 reads v3.
- **T2**: additive YAML + CLI; agents fall back.
- **T3**: warn-only, never blocks; config-disabled.

## Dependencies

`sqcli -license` format; SQX Builder Config.md (seed); CodeGraph for impact scan.

## Success Criteria

- [ ] Campaign N memory retrieved and injected into N+1
- [ ] Unified taxonomy; conformance test green
- [ ] ≥1 param per tab verified vs real config
- [ ] `check-version` detects drift and writes checklist
- [ ] Training exports deny-list-clean (tested)
