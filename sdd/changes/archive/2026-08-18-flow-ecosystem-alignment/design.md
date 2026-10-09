# Design: Flow-Ecosystem Alignment

## Technical Approach

Wire durable artifact writing at the single delegation choke point (`_run_sdk_stage`, sdk/quantlab/campaign/delegation.py:181), which both reasoning and handoff executors reach — every completed phase then leaves a real file. Reuse existing engines (`JForexProvider`, `DataManager`, `IndicatorEngine`, `build_teaching_table`, `save_phase_envelope`) rather than building new ones. Security and doc fixes (G4/G5) are edits to live config + pinned tests; G2 lands last behind `QUANTLAB_CUSTOM_PROJECT` after goldens re-base. Code is authoritative over docs (G5).

## Architecture Decisions

| # | Option | Tradeoff | Decision |
|---|---|---|---|
| D1 | Envelope write in `_run_sdk_stage` vs executor vs separate service | Executor misses handoff path; service adds indirection | Write inside `_run_sdk_stage` after stage execute — covers inline AND `run_stage_for_handoff` nohup subprocess |
| D2 | Artifact keys `{phase}_{stage}.json` stay synthetic vs become real files | Synthetic keys violate REQ-819 "no claim without persist" | `_run_sdk_stage` writes stage outcome to `campaign-phases/{cid}/{phase}/{phase}_{stage}.json`, lists that real path in envelope artifacts |
| D3 | `knowledge_root` injected by campaign runner vs env var | Env var is implicit and untestable | Add `knowledge_root` + `campaign_id` to `PhaseDirective.payload` (built in phase_runner.py build_directive); missing → risk recorded, no claim (spec scenario) |
| D4 | Proposal/spec writers as new module vs methods on store | Store is indexing-focused | New `sdk/quantlab/knowledge/artifacts.py` — SDK-owned deterministic renderers from outcome dicts, invoked per phase hook |
| D5 | v4→v5 migration | Already implemented (store.py:727-733) | Only acceptance tests + seed CLI + organic dir population needed |
| D6 | Seed command: `sqx kb seed-ohlc` vs new top-level parser | New parser duplicates argparse wiring | Reuse `add_sqx_subparser` (sq_commands.py:373); `SQX_FORCE_MOCK=1` mock path mirrors `cmd_kb_seed` |
| D7 | G2 flag default | generator.py:23 currently defaults "1" (on) but is never invoked | Builder dispatch defaults to legacy until goldens re-based, then flips to CustomProject (schema 144.2953) |
| D8 | Canonical counts | Spec pins 16/25/27 | Integrity test counts `build_pipeline` output per mode; docs not consulted |

## Data Flow

```
G1: runner ─→ PhaseDirective(knowledge_root, campaign_id)
       ─→ _run_sdk_stage ─→ stage.execute(ctx) ─→ outcome dict
       ─→ artifacts.write_{proposal,spec}(outcome) → structured/{cid}/{proposal,spec}.md
       ─→ store.write(campaign-phases/{cid}/{phase}/{phase}_{stage}.json)
       ─→ save_phase_envelope(artifacts=[real paths]) → envelope.json
       ─→ PhaseResult.artifacts (real paths only) ─→ Knowledge Lake (index v5)

G3: DukascopyProvider.fetch_bars(sym, tf) → DataManager→JForexProvider.fetch_history
       → list[Bar] → IndicatorEngine.compute → zones → build_prompt market block
       → datasets/{symbol}/ cache → rebuild_index
```

## File Changes

| File | Action | Description |
|---|---|---|
| `sdk/quantlab/campaign/delegation.py` | Modify | `_run_sdk_stage` writes outcome JSON + envelope; artifacts hook |
| `sdk/quantlab/campaign/phase_runner.py` | Modify | inject `knowledge_root`/`campaign_id` into directive payloads |
| `sdk/quantlab/knowledge/artifacts.py` | Create | SDK-owned `write_proposal_artifact`, `write_spec_artifact` |
| `sdk/quantlab/knowledge/store.py` | Modify | expose datasets cache helper (v5 keys already emitted) |
| `sdk/quantlab/data/dukascopy/provider.py` | Create | `DukascopyProvider` (D5, M1/M5/H1, fail-soft) |
| `sdk/quantlab/agents/llm_research_agent.py` | Modify | market block appended at :366-382; omit on provider gap |
| `sdk/quantlab/cli/sq_commands.py` | Modify | `sqx kb seed-ohlc` handler (argparse precedent) |
| `sdk/quantlab/pipeline/stages/config_review_stage.py` | Modify | persist `structured/{cid}/review/teaching-table.md`; path in verdict + `PhaseResult.artifacts` |
| `sdk/quantlab/pipeline/registry.py` | Modify | register `custom_project` stage |
| `sdk/quantlab/pipeline/stages/agent_stages.py` | Modify | `BuilderStage` dispatches on `QUANTLAB_CUSTOM_PROJECT` (legacy → translator.py:133, new → customproject/generator.py:45) |
| `sdk/quantlab/customproject/generator.py` | Modify | flag default → legacy until flip |
| `~/.config/opencode/opencode.json` | Modify | remove deploy/monitor agents; prune run/status/compare (:519-534); campaign deny-first bash (:83-103); fix `sdk/pipeline/*`→`sdk/quantlab/pipeline/*` (:523); backup first |
| `installer/internal/opencode/overlay.json` | Modify | sync removals + campaign bash block |
| `~/.config/opencode/prompts/quantlab/orchestrator.md` | Modify | prune routing rows :26-29, :135-153 |
| `tests/test_orchestrator_prompt.py` | Modify | pin: legacy agents absent, no dangling refs, deny-first bash |
| `tests/campaign/test_delegation.py` | Modify | envelope/artifact RED tests |
| `tests/test_knowledge_store_v5.py` | Modify | v5 acceptance + migration scenarios |
| `tests/pipeline/test_pipeline_counts.py` | Create | 16/25/27 integrity |
| `tests/customproject/`, `tests/cfx/` | Modify | deliberate golden re-base (G2, before flip) |
| `multi-agent-research-system/` | Archive | after its deltas merge (coordinate with archive phase) |

## Interfaces / Contracts

```python
# PhaseDirective.payload additions
{"knowledge_root": str, "campaign_id": str}

# _run_sdk_stage outcome persistence
outcome_rel = f"campaign-phases/{cid}/{phase}/{phase}_{stage}.json"
store.write(outcome_rel, json.dumps(outcome, default=str))   # real file
store.save_phase_envelope(cid, phase, status=..., artifacts=[outcome_rel, *hooks])

# artifacts.py
def write_proposal_artifact(campaign_id, outcome, root) -> str  # → structured/{cid}/proposal.md
def write_spec_artifact(campaign_id, outcome, root) -> str      # → structured/{cid}/spec.md

# dukascopy/provider.py
class DukascopyProvider:
    def fetch_bars(self, symbol: str, timeframe: str) -> list[Bar]  # [] on gap, never raises
# market block: compact zone labels only (overbought/high/trending), raw series omitted
```

SQX integration: G2 emits `.cfx` as `config.xml` + per-task XML (schema `144.2953`) via `customproject/generator.py`; legacy dialect stays `141.2219` single-task until flip. G6 seed touches no `.cfx`; it feeds `DataManager`/JForex history.

## Testing Strategy

| Layer | What | How |
|---|---|---|
| Unit | Envelope writes, artifact hooks, missing knowledge_root degrade | extend `tests/campaign/test_delegation.py`; tmp-path store |
| Unit | DukascopyProvider fail-soft, IndicatorEngine `insufficient_data` | mock JForexProvider; `SQX_FORCE_MOCK=1` |
| Unit | Teaching-table persist + placeholder rows | config_review_stage tests, empty/unknown param cases |
| Integration | v4→v5 migration, datasets cache, seed CLI | `test_knowledge_store_v5.py` + CLI test under mock |
| E2E | 16/25/27 counts; registry lookup; `.cfx` goldens | `test_pipeline_counts.py`; `tests/customproject/`, `tests/cfx/` re-based then flip |
| E2E | Live config pinned | `test_orchestrator_prompt.py` parses `~/.config/opencode/opencode.json` + overlay |

## Threat Matrix

| Boundary | Applicability | Design response | Planned RED tests |
|---|---|---|---|
| Documentation-like paths (executable Markdown) | **Applicable** — `orchestrator.md` is an agent-instruction file; routing rows drive delegation | G4 prunes run/status/compare rows (:26-29, :135-153); safe = rows reference only registered agents; failure = task routes to unregistered agent, fails closed | orchestrator.md contains no `quantlab-run\|status\|compare`; opencode.json has no `quantlab-deploy\|monitor` agent |
| Shell commands (process boundary) | **Applicable** — `quantlab-campaign` bash `true` with no deny block (:83-103); G6 adds `sqx kb seed-ohlc` | Deny-first `{*: deny, sdk/quantlab/pipeline/*: allow, sdk/quantlab/campaign/*: allow}`; orchestrator stale `sdk/pipeline/*`→`sdk/quantlab/pipeline/*`; seed exits naming missing JForex/SQCLI, reports partial files | test asserts campaign `bash["*"]=="deny"` + both SDK allows; orchestrator bash has no `sdk/pipeline/*`; seed env-unavailable exit code test |
| Process integration (stage registry) | **Applicable** — G2 registers `custom_project`; unregistered stages fail closed | `StageRegistry.lookup("custom_project")` returns stage; absent → `RegistryError` before execution (pipeline-core) | registry lookup test; flag-off byte-identity goldens |
| Git repository selection | N/A — no VCS automation in this change | — | — |
| Commit state | N/A — no commit automation | — | — |
| Push state | N/A — no push automation | — | — |
| PR commands | N/A — no PR automation | — | — |

## Migration / Rollout

G4: backup `opencode.json` (timestamped) before edit; installer overlay updated in same change; restore = copy back. G1/G6/G7: additive writes only — no data migration; index v4→v5 auto-upgrades on `read_index()`. G5: archive `multi-agent-research-system` only after its deltas merge. G2: flag-first — legacy default, golden re-base, then flip default to CustomProject; rollback = flip back. G6 seed requires real JForex history or mock.

## Open Questions

- [ ] Which phases map to `spec.md` (hypothesis/config) vs `proposal.md` (research only) — writer hook table needs confirm in tasks.
- [ ] Envelope timestamps: `started_at`/`completed_at` captured where — runner or `_run_sdk_stage`?
- [ ] `seed-ohlc` symbol set + default timeframes (M1/M5/H1) — confirm small set (e.g. EURUSD only) for CI determinism.