# Tasks: Knowledge Memory System

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1900 authored (excl. KB seed YAML) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 → PR6 (stacked) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Taxonomy reconcile + index v4 + conformance | PR 1 | `python3 -m pytest tests/test_knowledge.py tests/test_conformance.py -q` | N/A — pure fs layout, no runtime boundary | Revert store.py/indexer.py; delete conformance.py |
| 2 | Memory capture + engram dual-write + privacy | PR 2 | `python3 -m pytest tests/test_memory_capture.py tests/test_privacy.py -q` | tmp lake: capture_phase w/ fake engram; non-blocking check | Delete memory_capture.py/privacy.py; revert memory.py/director |
| 3 | SQX parameter KB + CLI | PR 3 | `python3 -m pytest tests/test_kb.py -q` | `quantlab sqx kb list --tab Ranking` | Delete knowledge/kb/, sq_commands.py, seed YAMLs |
| 4 | Version detection + literals + check-version | PR 4 | `python3 -m pytest tests/test_version.py tests/test_license_build.py -q` | `quantlab sqx check-version` w/ mock executor | Revert versioning.py/license.py/literal files |
| 5 | Context injection + agent consumption + prompts | PR 5 | `python3 -m pytest tests/test_context.py -q` | compose_prior_context on seeded tmp lake | Delete context.py; revert agent/prompt edits |
| 6 | Training exports + semantic retrieval (later) | PR 6 | `python3 -m pytest tests/test_training.py -q` | staged JSONL export, assert deny-list-clean | Delete training.py, embeddings/, datasets/ |

## Phase 1: Foundation — Taxonomy + Index v4 (WU1)

- [x] 1.1 RED `sdk/tests/test_conformance.py`: REQ-402 writer map; off-layout write fails naming path
- [x] 1.2 `sdk/quantlab/knowledge/store.py` `initialize()`: add `pipeline-runs/`, `agent-memory/` + sub-layouts `structured/{campaign_id}/`, `structured/sqx-kb/{ver}/parameters/{tab}/`, `structured/sqx-version/{old}→{new}/`; idempotent, `.gitkeep`
- [x] 1.3 Create `sdk/quantlab/knowledge/conformance.py`: writer→canonical-dir map (REQ-402)
- [x] 1.4 `store.py` `rebuild_index()`: `_version: 4` + kb_parameters + version_events areas; `_upgrade_index` maps v1–3 (REQ-403)
- [x] 1.5 `sdk/quantlab/knowledge/indexer.py`: legacy read fallback `campaigns/ results/ stats/`; metrics from `structured/{campaign_id}/metrics.yaml` (D6)
- [x] 1.6 GREEN: fresh init creates 7 dirs + 3 sub-layouts; v1 index readable with defaults

## Phase 2: Memory Capture + Privacy (WU2)

- [x] 2.1 RED `sdk/tests/test_privacy.py`: scrub `FUTLABF255` at write; export SHA-256-hashes campaign ID; export deny-list-clean fails otherwise (REQ-107)
- [x] 2.2 Create `sdk/quantlab/knowledge/privacy.py` `PrivacyScrubber`: field-scoped deny-list + hash fn (D4)
- [x] 2.3 RED `sdk/tests/test_memory_capture.py`: dual-write; engram fail→lake ok; missing fields null-default; save failure non-blocking (REQ-102/103)
- [x] 2.4 Create `sdk/quantlab/knowledge/memory_capture.py` `MemoryCaptureService.capture_phase(agent, campaign, phase, envelope, config=None)` async, non-blocking (D1/D2)
- [x] 2.5 `sdk/quantlab/agents/memory.py` `save_decision`: add phase+config to dict; scrub before write (D3)
- [x] 2.6 `sdk/quantlab/agents/research_director.py:66,511` + campaign.md agent: wire capture at phase boundaries; config-disabled (D1)

## Phase 3: SQX Parameter KB (WU3)

- [x] 3.1 RED `sdk/tests/test_kb.py`: missing `what_it_does` fails listing field; version-isolated lookup; status filter (REQ-201/502)
- [x] 3.2 Create `sdk/quantlab/knowledge/kb/models.py`: pydantic `KbParameter` 22 fields, tab Literal[8], status seeded|verified|needs_review (D7)
- [x] 3.3 Create `sdk/quantlab/knowledge/kb/store.py` `KbStore`: get/list/seed/verify/status/invalidate over `structured/sqx-kb/{ver}/` (REQ-202/208)
- [x] 3.4 Create `sdk/quantlab/knowledge/kb/seeder.py`: parse `doc_dev/SQX Builder Config.md` → seed 8 tabs; doc gaps → needs_review, never invent (REQ-203)
- [x] 3.5 Create `sdk/quantlab/cli/sq_commands.py` + wire `cli/main.py`: `quantlab sqx kb` list/get/seed/verify/status; unknown param exit 1 (REQ-207)
- [x] 3.6 GREEN: ≥1 param per tab verified vs real config evidence_ref (REQ-203)

## Phase 4: Version Detection (WU4)

- [ ] 4.1 RED `sdk/tests/test_license_build.py`: "Build 144 (Futlab…)" → `144.2953` (or `144`); missing Build → null, warn, no raise (REQ-301)
- [ ] 4.2 `sdk/quantlab/pipeline/license.py`: `LicenseInfo.build_number`, regex `Build (\d+)(?:\.(\d+))?`
- [ ] 4.3 Create `sdk/quantlab/versioning.py`: `PINNED_SQX_VERSION="144.2953"` (D8)
- [ ] 4.4 RED `sdk/tests/test_version.py`: in-sync silent; drift warns+proceeds; mock/no-sqcli skips; check-version exit 0/1/unknown; drift→checklist+KB invalidate; re-run additive (REQ-303/304/305)
- [ ] 4.5 `versioning.py`: `VersionPreflight` + `DriftWorkflow` → `structured/sqx-version/{old}→{new}/checklist.yaml` {from,to,detected_at,affected_files,kb_invalidated,status} + codegraph scan (D9)
- [ ] 4.6 `sdk/quantlab/sqx/cli_wrapper.py`: `version_preflight` beside `license_preflight` (~:310), skip w/o sqcli (REQ-701)
- [ ] 4.7 11 prod files + `tests/sqx/test_license_guard.py` + `test_project_builder_symbol.py`: literal `144.2953` → `PINNED_SQX_VERSION` (REQ-302)
- [ ] 4.8 `cli/sq_commands.py`: `quantlab sqx check-version` (REQ-304)

## Phase 5: Consumption + Prompts (WU5)

- [ ] 5.1 RED `sdk/tests/test_context.py`: prior memory injected w/ risks/lessons; empty lake → placeholder, no error (REQ-104/501)
- [ ] 5.2 Create `sdk/quantlab/knowledge/context.py`: `compose_prior_context(campaign_id, phase, *, limit=10)` via QueryBuilder + find_similar_campaigns → markdown (REQ-501)
- [ ] 5.3 `context.py`: self-correction detection-and-report; repeated failure signature → recommendation appended (REQ-105)
- [ ] 5.4 `sdk/quantlab/agents/builder_agent.py`: KB consult; block config w/o entry unless needs_review/override (REQ-204)
- [ ] 5.5 `sdk/quantlab/agents/config_reviewer.py`: teaching table per configured param (REQ-205)
- [ ] 5.6 `docs/prompts/campaign.md` + agent prompts: document injected memory block (REQ-104)

## Phase 6: Later (WU6, deferred)

- [ ] 6.1 Create `sdk/quantlab/knowledge/training.py`: curated JSONL export → `datasets/`, dedupe by config hash, deny-list-clean, hashed IDs (REQ-106)
- [ ] 6.2 Embeddings semantic retrieval (`find_similar_campaigns` ranking) + `embeddings/` dir
- [ ] 6.3 Building-blocks KB tab; changelog polling (future)
