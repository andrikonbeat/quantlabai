# Design: Knowledge Memory System

## Technical Approach

Three additive tracks over the existing lake: **T1** durable campaign memory (phase-boundary capture, Engram complement, injected retrieval, privacy scrub, index v4); **T2** version-isolated SQX parameter KB; **T3** pinned SQX version + fail-open drift detection. All persistence flows through `KnowledgeStore`; code is config-disabled.

## Architecture Decisions

| # | Choice | Rejected | Rationale |
|---|---|---|---|
| D1 | `MemoryCaptureService` wraps `AgentMemoryManager`; invoked from `ResearchDirector` at phase boundaries + campaign.md agent at phase close | Per-stage hooks in 14 stage classes | Single choke point; `ResearchDirector` owns `engram_save_fn` (research_director.py:66,511) |
| D2 | Reuse campaign.md Result Contract dict (`status, executive_summary, artifacts, next_recommended, risks`); null-defaults | New dataclass | Contract already canonical (campaign.md:174) |
| D3 | Keep `AgentMemoryManager.save_decision` dual-write; add `phase`+`config` to the decision dict | Parallel service | Existing dual-write satisfies REQ-103 |
| D4 | `PrivacyScrubber` (knowledge/privacy.py): field-scoped deny-list + SHA-256 campaign-ID hash in exports | Post-hoc cleanup | Write-time scrub, avoids false positives |
| D5 | `rebuild_index` → `_version: 4` + `kb_parameters` + `version_events`; `_upgrade_index` maps v1–3 | Separate index file | Backward compat via existing `_upgrade_index` (store.py:458) |
| D6 | `SQXKnowledgeStoreStage` writes `structured/{campaign_id}/` (cfx, results, metrics.yaml) not legacy `campaigns/ results/ stats/` | Keep legacy writes | REQ-101/402; Indexer keeps legacy read fallback |
| D7 | pydantic `KbParameter` + `KbStore` over `KnowledgeStore` | Plain dicts | Version isolation, status filter, validation (REQ-201/502) |
| D8 | `PINNED_SQX_VERSION="144.2953"` in `sdk/quantlab/versioning.py`; literals resolve to it | Config file | Import-time constant, single source (REQ-302) |
| D9 | `version_preflight` beside `license_preflight` in `_dispatch_real` (~line 310); warn-only, skip without sqcli | Block on drift | Mirrors LIC-01 fail-open (REQ-303/701) |

## Data Flow

```
phase N ─► MemoryCaptureService ─► AgentMemoryManager ─► Engram agent/{agent}/{campaign}
   │                                └─► agent-memory/.../memory.yaml ─► PrivacyScrubber
compose_prior_context ─► QueryBuilder + find_similar_campaigns ─► markdown ► next envelope
sqcli -license ─► build_number ─► version_preflight ─(drift)─► DriftWorkflow
                    └─► sqx-version/{old}→{new}/checklist.yaml ─► KbStore.invalidate(old)
```

## File Changes

| File | Action | Description |
|---|---|---|
| `knowledge/{privacy,memory_capture,context,training,conformance}.py` | Create | Scrubber; capture service; `compose_prior_context` + self-correction (report-only); JSONL exporter (later); REQ-402 helper |
| `knowledge/kb/*.py` | Create | pydantic model; `KbStore` (get/list/seed/verify/status/invalidate); seeder from `doc_dev/SQX Builder Config.md` → `sqx-kb/144.2953/parameters/{tab}/{param}.yaml` |
| `sdk/quantlab/versioning.py` | Create | `PINNED_SQX_VERSION`, `VersionPreflight`, `DriftWorkflow`, checklist writer |
| `cli/sq_commands.py` + `cli/main.py` | Create/Modify | `quantlab sqx kb` (list/get/seed/verify/status) + `sqx check-version` |
| `knowledge/{store,indexer}.py` | Modify | structured sub-layouts in `initialize()`; index v4; metrics from `structured/{campaign_id}/metrics.yaml` + legacy fallback |
| `phase4/stages/__init__.py` | Modify | `SQXKnowledgeStoreStage` → canonical `structured/{campaign_id}/` writes |
| `pipeline/license.py` | Modify | `LicenseInfo.build_number`; parse `Build (\d+)(?:\.(\d+))?`; null on missing |
| `sqx/cli_wrapper.py` | Modify | `version_preflight` beside license preflight (~line 310) |
| `agents/{research_director,memory,builder_agent,config_reviewer}.py` | Modify | wire capture; `phase` normalization; KB consult (REQ-204); teaching table (REQ-205) |
| `cfx/*`, `dashboard/app.py`, `customproject/*`, `translate/translator.py`, `phase4/{http_client,templates,daemon}.py` | Modify | `144.2953` literals → `PINNED_SQX_VERSION` (REQ-302) |
| `sdk/tests/test_{privacy,kb,version,conformance,license_build}.py` | Create | RED tests per specs |

## Interfaces / Contracts

```python
class KbParameter(BaseModel):                    # 22 fields per REQ-201
    name; sqx_name; tab: Literal[8 tabs]; section; type
    default: Any|None; range: Any|None
    what_it_does; how_it_works_in_sqx; quant_trading_role
    hypothesis_relation|None; edge_relation|None
    small_account_recommendation|None  # {recommended_value, default_value, reason}
    why_choose|None; when_choose|None; related_parameters|None
    status: Literal["seeded","verified","needs_review"]="seeded"
    sqx_version=PINNED_SQX_VERSION; evidence_ref|None

def compose_prior_context(campaign_id, phase, *, limit=10) -> str
def get_parameter(tab, param, sqx_version=None) -> KbParameter
def list_parameters(tab=None, status=None, sqx_version=None) -> list[KbParameter]
async def capture_phase(agent, campaign, phase, envelope, config=None) -> None  # non-blocking
# checklist.yaml: from_version, to_version, detected_at, affected_files[], kb_invalidated, status
```

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Unit | build parse (build+point, missing→null); KbParameter missing field; scrub `FUTLABF255`; hash determinism | FakeExecutor + fixtures |
| Unit | check-version exit 0/1/unknown; preflight skip (no sqcli, `SQX_FORCE_MOCK`) | mock executor |
| Integration | dual write (Engram fail→lake ok); KB version isolation; drift→checklist+invalidation | tmp_path lake, codegraph mocked |
| Conformance | REQ-402 writer map; off-layout write fails; REQ-107 export deny-list-clean | `conformance.py` + staged export |

## Threat Matrix

| Boundary | Applicability | Design response | Planned RED tests |
|---|---|---|---|
| Subprocess (sqcli) | Applicable | args as list via `Executor` (no shell=True); missing binary→skip+warn; mock→skip | injection-shaped args verbatim; drift warns, proceeds; missing build→null, no raise |
| Documentation-like paths | N/A — no executable-file classification added | — | — |
| Git selection / commit / push / PR | N/A — no git or PR automation in this change | — | — |

## Migration / Rollout

Additive. Index v4 reads v3; legacy `stats/ tags/ links/` readable. Capture + preflight config-disabled. KB seeded once, subset verified first.

## Open Questions

- [ ] Real `sqcli -license` output: does point version ("2953") appear on the Build line? If not, preflight compares build major only.
- [ ] Confirm literal sites: 13 files found vs 23 reported (some may be test fixtures).