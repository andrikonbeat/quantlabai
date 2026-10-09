# Proposal: Flow-Ecosystem Alignment

## Intent

Campaign flow persists no durable artifacts, Knowledge Lake is empty, research ignores broker data, `quantlab-campaign` has unrestricted bash. Root cause: no phase owns durable artifact writing. Fix plumbing, security/docs/data gaps, CFX dialect.

## Scope

### In Scope
- G4: remove `quantlab-deploy`/`quantlab-monitor`; prune run/status/compare refs; deny-first bash on `quantlab-campaign`; fix stale pipeline path.
- G5: fix stale "17-stage" wording; archive `multi-agent-research-system`.
- G1: SDK-owned `proposal.md`/`spec.md` writers; wire `save_phase_envelope`.
- G6: seed real OHLC via `DataManager`; migrate index v4→v5.
- G3: `DukascopyProvider` + `IndicatorEngine` zones in research prompt.
- G7: `ConfigReviewStage` persists `teaching-table.md` in `PhaseResult.artifacts`.
- G2 (last): builder renders `CustomProject` behind flag; migrate goldens; flip default.

### Out of Scope
Config-in-VCS sync; fabricated data; new stages; 14-phase changes.

## Capabilities

> Contract for sdd-spec. New → `openspec/specs/<name>/spec.md`; modified → deltas.

### New Capabilities
- `campaign-artifact-writers`: SDK proposal/spec/envelope writers.
- `dukascopy-research-data`: broker data + indicators for research.

### Modified Capabilities
- `campaign-phase-delegation`: stages write artifacts; envelope wired.
- `knowledge-store`: v5 index; dirs populated.
- `llm-research`: Dukascopy provider + indicator zones.
- `technical-indicators`: `IndicatorEngine` reaches production.
- `quantlab-orchestrator`: deny-first; legacy agents removed.
- `full-campaign-lifecycle`/`research-agent`/`pipeline-core`: canonical counts.
- `parameter-educational-table`: reviewer-owned persisted table.
- `custom-project-generator`/`sqx-translator`: builder behind flag.

## Approach

Sequence: G4 → G5 → G1 → G6 → G3 → G7 → G2. Reuse `DataManager`/`JForexProvider`, `IndicatorEngine`, `build_teaching_table`, `save_phase_envelope`. Code authoritative over docs. SQX: G6 via `sqx kb seed`-style CLI; G2 touches `.cfx` config/task XML.

## Affected Areas

- `campaign/delegation.py`, `knowledge/store.py` — artifact writes; v5 index
- `agents/research_director.py`, `llm_research_agent.py`, `config_review_stage.py` — persist config; provider+TA; teaching table
- `~/.config/opencode/opencode.json`, `orchestrator.md` — G4 cleanup (outside VCS)
- `multi-agent-research-system/` — fix counts; archive
- `translate/translator.py`, `pipeline/registry.py` — G2 flag + stage
- `knowledge/{datasets,campaign-phases,pipeline-runs}/` — seeded/populated

## Risks

- Live config edit breaks sessions — Med — restart; tests pin
- Golden `.cfx` tests fail (G2) — High — flag-first; re-base deliberately
- v5 index rewrite breaks store tests — Med — update `test_knowledge_store_v5.py`
- Real data fetch env-dependent — Med — CLI seed; `SQX_FORCE_MOCK=1`

## Rollback Plan

- G4: restore config backup + installer overlay; tests re-pin.
- G1/G6/G7: revert delegation/store; no files → no migration.
- G2: flip flag back to legacy translator.
- G5: un-archive `multi-agent-research-system` (deltas merged).

## Dependencies

- SQX/JForex env for OHLC seeding.
- Keep-green: `test_orchestrator_prompt.py`, `tests/customproject/`, `tests/cfx/`, `test_knowledge_store_v5.py`.

## Success Criteria

- [ ] `quantlab-campaign` deny-first; legacy agents gone; orchestrator tests green
- [ ] Campaigns persist `proposal.md`/`spec.md` + per-phase `envelope.json`
- [ ] Index v5; real OHLC seeded; `campaign-phases/` populated
- [ ] Research prompt has Dukascopy bars + indicator zones
- [ ] `teaching-table.md` persisted per review
- [ ] Builder emits CustomProject `.cfx` by default; goldens re-based
- [ ] `multi-agent-research-system` archived