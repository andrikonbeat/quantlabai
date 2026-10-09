# Exploration: Flow-Ecosystem Alignment

Change: `flow-ecosystem-alignment` · Artifact mode: hybrid (Engram + filesystem)
Scope: verify the 7-gap audit for the orchestrated 14-phase campaign flow with
file:line evidence, and compare approaches for the architectural decisions.
No code was modified.

---

## G1 — Proposal/Spec artifacts missing

### Current State

No per-campaign user-facing proposal (hypotheses + builder/retester/optimizer/
portfolio config proposal + sources + evidence) or technical spec ("Contrato")
is persisted. Evidence:

- The phrase "Contrato" appears **nowhere** in `ai/`, `openspec/`,
  `sdk/quantlab` (grep: 0 hits) — it is a term from the audit context, not the
  codebase.
- `ResearchConfig` (`sdk/quantlab/dsl/models.py`) is the only proposal-shaped
  object; it lives **in-memory** during the flow. `ResearchDirector.execute_campaign`
  builds `ctx.artifacts["research_config"]` / `hypotheses` in memory only
  (`sdk/quantlab/agents/research_director.py:673-688`) and returns a `CampaignRecord`
  that is never serialized to disk (`research_director.py:595-850`).
- What IS persisted today:
  - `knowledge/structured/{campaign_id}/configs/{campaign_id}.cfx` and
    `knowledge/parameter-matrix/{campaign_id}/parameter_matrix.json` — by
    `BuilderAgent._persist_build_artifacts`, gated on
    `context.config["knowledge_root"]` (`sdk/quantlab/agents/builder_agent.py:232-274`).
  - `knowledge/agent-memory/{agent}/{campaign}/memory.yaml` — via
    `MemoryCaptureService` (`sdk/quantlab/knowledge/memory_capture.py:60`), but
    **config-disabled by default** and non-blocking
    (`research_director.py:717-718`).
  - `knowledge/structured/demo/{campaign_id}/window.yaml` —
    `DemoWindowStore` (`sdk/quantlab/data/demo/store.py:31`).
  - `knowledge/campaign-phases/{campaign_id}/{phase}/envelope.json` —
    `KnowledgeStore.save_phase_envelope` (`sdk/quantlab/knowledge/store.py:638-698`)
    exists but has **ZERO production callers** (only tests:
    `tests/knowledge/test_knowledge_store_v5.py:258,281`).
- SDD mapping precedent: `openspec/changes/multi-agent-research-system/` holds
  the full proposal → specs/ → design → tasks → verify-report chain, and
  `openspec/changes/quantlab-installer/exploration.md` confirms
  `exploration.md` lives in the change folder. The campaign-level proposal/spec
  would be **flow artifacts** (under `knowledge/structured/{campaign_id}/`),
  distinct from SDD change artifacts.

### Affected Areas

- `sdk/quantlab/agents/research_director.py` — in-memory-only artifacts;
  no serialization of research_config/hypotheses.
- `sdk/quantlab/campaign/delegation.py:233-264` — executor returns
  `artifacts=[f"{phase}_{stage}.json"]` but **never writes that file**
  (claim-only artifact key).
- `sdk/quantlab/knowledge/store.py:638` — `save_phase_envelope` unwired.
- `ai/opencode/agents/phase-research.md:36`, `phase-hypothesis.md:36`,
  `phase-config.md:34` — agents forbidden to write; SDK writes artifacts.
- `sdk/quantlab/knowledge/context.py:259` — `compose_prior_context` is the
  natural read-side consumer (already injected into envelopes).

### Approaches

1. **SDK-owned artifact writers per phase** — add a proposal/spec writer in the
   research stage (or `ResearchDirector`) persisting
   `knowledge/structured/{campaign_id}/proposal.md` + `spec.md`, and wire
   `save_phase_envelope` into `_run_sdk_stage`
   (`sdk/quantlab/campaign/delegation.py:181-215`).
   - Pros: deterministic, testable, survives agent failure; follows the
     BuilderAgent precedent (builder_agent.py:232).
   - Cons: touches the delegation glue; needs `knowledge_root` propagated in
     directive payloads.
   - Effort: Low-Medium.
2. **Agent-prompt-driven artifacts** — phase agents compose proposal/spec
   markdown and return artifact keys (prompts already claim REQ-820
   "artifacts not bytes").
   - Pros: no SDK changes; flexible LLM content.
   - Cons: non-deterministic; contradicts REQ-820 boundary; agent failure
     loses the artifact; no tests possible.
   - Effort: Low, but fragile.
3. **Hybrid: SDK writes structured JSON (config proposal + evidence) + agent
   renders markdown** — SDK persists the machine-readable proposal
   (`research_config`, `build_config`, matrix, sources) and the reviewer/
   research agents render the human spec.
   - Pros: deterministic core, human-readable surface, mirrors SDD
     proposal→spec split.
   - Cons: two writers to keep in sync.
   - Effort: Medium.

### Recommendation

Approach 1 (SDK-owned writers + wire `save_phase_envelope`): it is the only
deterministic option that survives agent crashes, matches the existing
`_persist_build_artifacts` precedent, and gives tests a stable contract. Phase
agents keep REQ-820 intact.

### Risks

- `knowledge_root` is not currently guaranteed in orchestrated directive
  payloads (`_run_sdk_stage` only passes `payload["config"]`).
- `save_phase_envelope` has no production caller today — wiring it changes
  observable behavior (files appear), which may affect existing
  golden/index tests.

### Ready for Proposal

Yes — proposal.md should define `proposal.md`/`spec.md` schemas, the
`knowledge/structured/{campaign_id}/` layout, and the
`save_phase_envelope` wiring.

---

## G2 — CustomProject multi-task model disconnected from orchestrated flow

### Current State

Two divergent CFX dialects exist; the orchestrated flow uses the legacy one.

- Orchestrated config phase: `phase-config.md` → `phase_runner` →
  `execute_phase` → `executor` → `_run_sdk_stage('config' → stage 'builder')`
  (`sdk/quantlab/campaign/delegation.py:181-215,233-264`) →
  `BuilderAgentStage` (`sdk/quantlab/pipeline/registry.py:172-180`) →
  `BuilderAgent.run` (`sdk/quantlab/agents/builder_agent.py:276-407`) →
  `_translate` → `translate/translator.py:generate_cfx_archive`
  (`translator.py:133-177`) — **single-task** archive
  (`Build-Task1.xml` + `CfxPatcher` regex patching of market/timeframe/blocks/
  criteria, translator.py:157-176).
- CustomProject dialect: `sdk/quantlab/customproject/` —
  `catalog.py:35-59` (21-task catalog), `renderers.py:407-420` (21 renderers),
  `templates.py` (15.1K), `generator.py:45-106` (`generate_cfx_archive(project)`
  → multi-file `CfxProject`), `cfx/writer.py:440-505`
  (`_write_project_archive` — `config.xml` + per-task XML). Its generator has
  21 callers **all inside `customproject/templates.py`** — never invoked by a
  pipeline stage; no `custom_project` stage exists in `StageRegistry`
  (`registry.py:130-366`).
- Rollback gate: `is_custom_project_enabled` (`customproject/generator.py:19-23`)
  — `QUANTLAB_CUSTOM_PROJECT != "0"`, i.e. **enabled by default**, yet unused by
  the flow. Archived design `openspec/changes/archive/2026-08-09-full-campaign-flow/
  design.md:15` claims "custom-project-first is the default path" — the code
  contradicts that claim.
- Separate phase4 engines for retest/optimize/portfolio exist outside the
  builder dialect: `sdk/quantlab/phase4/{retester,optimizer,portfolio_master}.py`.

### Affected Areas

- `sdk/quantlab/translate/translator.py:133` — legacy single-task generator.
- `sdk/quantlab/agents/builder_agent.py:276-407` — the only builder path in the
  orchestrated flow.
- `sdk/quantlab/customproject/*` — catalog/generator/renderers/templates (used
  only by tests + templates).
- `sdk/quantlab/cfx/writer.py:440` — `_write_project_archive` (multi-file
  dialect, dormant for the flow).
- `sdk/quantlab/pipeline/registry.py:317-366` — registered stage names.
- `sdk/quantlab/campaign/delegation.py:181-215` — stage resolution.

### Approaches

1. **Orchestrate per-task CustomProject generation** — extend the builder stage
   to render a `CustomProject` (Build/Retest/Optimize/Portfolio tasks) via
   `customproject/generator.py` instead of the single-task translator.
   - Pros: unifies dialects; 21-task catalog already verified
     (tests/customproject/); matches the archived design intent.
   - Cons: highest blast radius — builder artifact shape changes
     (`cfx_bytes` consumers, `dispatch_stage.py`), golden `.cfx` tests
     (tests/cfx/test_writer.py, tests/customproject/test_e2e_loadconfig.py)
     must be re-based; `project_builder.py` `BuildConfig` flow still used by
     blocks_bridge/cli_wrapper/config_reviewer.
   - Effort: High.
2. **Parallel config sub-agents writing distinct `.cfx` paths** — keep the
   builder single-task dialect for Build, and let retest/optimize/portfolio
   phase agents write their own `.cfx` via CustomProject templates.
   - Pros: incremental; each dialect stays where it is already tested.
   - Cons: does not remove the two-dialect divergence; cross-task databank
     consistency must be hand-wired.
   - Effort: Medium.
3. **Per-block monitoring** — keep generation as-is; add per-task/per-block
   visibility on top (monitor reads task XMLs).
   - Pros: cheapest; no dialect change.
   - Cons: papering over the divergence; monitoring still consumes whatever
     dialect the builder produced.
   - Effort: Low.

### Recommendation

Approach 1 is the correct long-term unification (the archived design already
committed to it), but it must be sequenced: first make the builder stage able
to render a `CustomProject` behind a flag, migrate `dispatch_stage.py` + golden
tests, then flip `QUANTLAB_CUSTOM_PROJECT` semantics from "templates only" to
"flow-wide default". Approach 2 is the safe intermediate if review budget
forces slicing.

### Risks

- Golden `.cfx` byte-identity tests (tests/customproject/test_e2e_loadconfig.py,
  tests/cfx/test_writer.py) and `BuilderAgent` dispatch tests will need
  deliberate updates.
- `BuildConfig` (project_builder.py:280, 134 callers) is the review/parameter-
  matrix contract — a dialect switch must preserve its field surface.

### Ready for Proposal

Yes — proposal must pick the sequencing (flag → migrate → flip) and name the
exact tests to update.

---

## G3 — Research has no broker-destination data

### Current State

- `LLMResearchAgent` providers: `YahooFinanceProvider`
  (`sdk/quantlab/data/fundamental/yahoo.py:15`), `FredProvider`
  (`fred.py:16`), `WebSearchProvider` (duckduckgo-search, `web_search.py:27`),
  `RSSNewsProvider` (`rss.py:32`) — imported at
  `sdk/quantlab/agents/llm_research_agent.py:22-41`. **No Dukascopy data in
  research.**
- Classic `ResearchAgent.query_knowledge_lake` only queries the lake
  (`sdk/quantlab/agents/research_agent.py:345-424`, `QueryBuilder`).
- `BuilderAgent._ensure_data` (`builder_agent.py:750-810`) is a pre-flight only:
  `DataManager.ensure_symbol(symbol, datasource="dukascopy")` →
  `SqcliDukascopyHandler` running `sqcli -symbol action=add` + `-data
  action=update` (`sdk/quantlab/data/data_manager.py:107-148`). No analysis.
- Dukascopy/JForex data assets that DO exist:
  - `DataManager` (data_manager.py:183) + `JForexProvider.fetch_history`
    (`sdk/quantlab/jforex/provider.py:23-74`) reading normalized Bars from the
    local JForex4 `history/{SQX_NAME}.json`.
  - `sdk/quantlab/jforex/` also holds `exporter.py` (IndicatorExporter .jfx
    injection), `strategy_bridge.py` (compile/deploy/start/stop),
    `config.py` (credentials), `live_feed.py` — **no research data client**.
- **Audit correction — TA engines EXIST**: `ta>=0.11`
  (`sdk/pyproject.toml:28`); `sdk/quantlab/analysis/indicators.py` —
  `IndicatorEngine.compute` (`indicators.py:122-141`) with RSI/MACD/ATR/ADX/
  BB/SMA/EMA via `ta` (`indicators.py:12-14`); and
  `sdk/quantlab/data/technical/indicators.py:44` (`compute_indicators`,
  fail-soft spot indicators). **Both are orphans**: `compute_indicators` has
  zero production callers; `IndicatorEngine` is referenced only by
  `sdk/tests/analysis/test_indicators.py:16`. The pipeline's `analysis` stage
  (`AnalysisAgent`, analysis_agent.py:30, `AnalysisEngine.analyze`) scores
  post-backtest strategies — it does not feed research.

### Affected Areas

- `sdk/quantlab/agents/llm_research_agent.py:33-41` — provider set.
- `sdk/quantlab/data/data_manager.py:183` + `jforex/provider.py:23` — existing
  connectors to reuse.
- `sdk/quantlab/analysis/indicators.py:122` + `data/technical/indicators.py:44`
  — dormant TA engines to wire.
- `sdk/quantlab/agents/builder_agent.py:750` — pre-flight `_ensure_data`.
- `knowledge/datasets/` — empty; natural home for cached market data.

### Approaches

1. **Wire a Dukascopy data provider into research** — add a
   `DukascopyProvider` (or reuse `JForexProvider.fetch_history` +
   `DataManager`) that fetches M1/M5/H1 bars, and call `compute_indicators` /
   `IndicatorEngine` in `LLMResearchAgent.build_prompt`; persist samples under
   `knowledge/datasets/`.
   - Pros: closes the exact gap; deterministic SDK path, testable with mocks;
     reuses existing connectors.
   - Cons: JForex history requires the platform to have downloaded the symbol
     (fail-closed `provider.py:78-90`); sqcli path needs SQCLI_PATH.
   - Effort: Medium.
2. **Feed TA into the classic ResearchAgent too** — compute indicator zones
   from lake-stored bars and inject into `formulate_hypotheses`.
   - Pros: deterministic research without LLM.
   - Cons: lake is empty (G6) — cold start.
   - Effort: Medium.
3. **Prompt-only market context** — include a "market snapshot" block in the
   research prompt fed by whichever data is locally available.
   - Pros: trivial.
   - Cons: no real analysis; LLM hallucination risk persists.
   - Effort: Low.

### Recommendation

Approach 1: a `DukascopyProvider` behind `DataManager`/`JForexProvider` with
`IndicatorEngine` output injected into the LLM prompt, samples cached in
`knowledge/datasets/`. This reuses verified connectors and gives tests a mock
surface. Approach 2 folds in later once G6 seeding provides lake bars.

### Risks

- Real data fetch requires SQX/JForex environment; tests must mock the
  provider (SQX_FORCE_MOCK precedent).
- LLM prompt length grows; keep TA output compact (zone labels, not series).

### Ready for Proposal

Yes — proposal should define the provider interface, cache location, and the
exact prompt injection point (`llm_research_agent.py` `build_prompt`).

---

## G4 — opencode.json cleanup (live config, outside VCS)

### Current State

Read `/home/ogzuz/.config/opencode/opencode.json` (860 lines). Verified:

- `quantlab-deploy` (:125-136) — legacy entry: **no `permission` block**,
  `bash:true`, `edit:true`, `write:true`; prompt `{file:.../deploy.md}`
  (file exists, 1.1K stub).
- `quantlab-monitor` (:137-146) — legacy: no permission block, `bash:true`,
  `read:true`; prompt `{file:.../monitor.md}` (exists, 1.1K stub).
- `quantlab-run` / `quantlab-status` / `quantlab-compare` — **NOT agent
  entries** (audit's "exist" is imprecise): they are dangling references in
  `quantlab-orchestrator`'s bash list (:519-523) and task list (:530-534), and
  in the live `orchestrator.md` routing table
  (`~/.config/opencode/prompts/quantlab/orchestrator.md:26-29,135-153`).
- `quantlab-campaign` (:83-103) — **verified audit claim**: no bash permission
  block at all (`"bash": true` at :96) and `edit/write:true` (:97,:101).
- `quantlab-orchestrator` (:511-551) — **verified stale path**:
  `"sdk/pipeline/*": "allow"` (:523); the real path is `sdk/quantlab/pipeline/*`
  (used correctly by all 14 phase agents, e.g. :159-160).
- The 14 `quantlab-phase-*` agents (:147-510) are the correct deny-first shape:
  bash `{*: deny, sdk/quantlab/pipeline/*, sdk/quantlab/campaign/*}`, task
  `{*: deny, quantlab-*: allow}`, `question: allow`, `edit/write:false`.
- `guardian-orchestrator` (:758-786), `quantlab-guardian-alert` (:787),
  `quantlab-replacement` (:801) — deny-first bash, edit/write false.
- **Tests that pin the live config** (tests/test_orchestrator_prompt.py reads
  `Path.home()/".config"/"opencode"/"opencode.json"`, :34-36):
  - quantlab-campaign registered + mode + prompt ref (:142-149);
  - orchestrator task allowlist includes quantlab-campaign (:151-154) and
    quantlab-guardian (:263-266);
  - quantlab-guardian deny-first task (:249-261);
  - **all 14 phase agents**: registered, subagent, deny-first task, question
    allowed, exact prompt refs, bash scopes (:301-364+);
  - guardian-orchestrator registered + bash deny-first (:431-446);
  - quantlab-guardian-alert + quantlab-replacement registered (:482-490).
  - **No test pins quantlab-deploy/monitor/run/status/compare** — they are
    free to remove or update. `tests/test_campaign_docs.py:54-55` only pins
    "quantlab-campaign"/"quantlab-orchestrator" mentions in docs.
- Repo `opencode.json` is minimal (default_agent only, 4 bytes of content).

### Affected Areas

- `/home/ogzuz/.config/opencode/opencode.json` — legacy entries + orchestrator
  permissions.
- `/home/ogzuz/.config/opencode/prompts/quantlab/orchestrator.md:26-29,135-153`
  — legacy routing rows/sections for run/monitor/compare/status.
- `~/.config/opencode/prompts/quantlab/deploy.md`, `monitor.md` — legacy stubs.
- `tests/test_orchestrator_prompt.py` — must stay green or be updated
  deliberately.
- `installer/internal/opencode/overlay.json` + `installer/internal/assets/...`
  — installer mirrors of the config (keep in sync).

### Approaches

1. **Delete legacy entries + prune orchestrator references** — remove
   `quantlab-deploy`/`quantlab-monitor` entries, drop run/status/compare from
   orchestrator bash/task lists, remove their routing rows from orchestrator.md,
   add a deny-first bash block to `quantlab-campaign`, fix `sdk/pipeline/*` →
   `sdk/quantlab/pipeline/*`.
   - Pros: closes the security gap (campaign agent currently has unrestricted
     bash + write); removes dead routing.
   - Cons: touches a live config outside VCS; must re-run the pinned tests and
     the installer overlay.
   - Effort: Low-Medium.
2. **Keep entries but harden** — only fix quantlab-campaign bash deny-first
   and the stale path.
   - Pros: minimal diff.
   - Cons: leaves dead agents + dangling references.
   - Effort: Low.
3. **Sync config into VCS** — move agent definitions into
   `ai/opencode/` (agents already live there) and generate/validate
   `~/.config/opencode/opencode.json` from a checked-in template.
   - Pros: config changes become reviewable/testable like the prompts.
   - Cons: larger change; installer overlay must adopt the template.
   - Effort: Medium.

### Recommendation

Approach 1 now + Approach 3 as a follow-up. G4 is a security/correctness fix
(unrestricted bash on `quantlab-campaign` contradicts the deny-first posture of
every other phase agent), and the tests give a hard contract to keep green.

### Risks

- Editing the live config while an OpenCode session is running: config is read
  at session start — a restart is needed to take effect.
- Installer overlay (`installer/internal/opencode/overlay.json`) duplicates the
  config; it must be updated in the same change or drift returns.

### Ready for Proposal

Yes — proposal must enumerate exact deletions, the new `quantlab-campaign`
permission block, and the orchestrator.md edits, and name
`tests/test_orchestrator_prompt.py` as the keep-green contract.

---

## G5 — Doc vs code: "17 stages" vs reality

### Current State

- Spec wording (stale): `openspec/changes/multi-agent-research-system/specs/
  research-director/spec.md:5` "8 agent stages, 5 human gates"; `:13`
  "full 17-stage pipeline (8 agent stages + 5 gate stages + 4 transition
  stages)"; `:18` scenario "17 stages … research → gate1 → build → statistics →
  review → gate2 → portfolio → gate3 → deploy → gate4 → monitor → gate5 →
  (loop)". Same count in `proposal.md:118` ("extends 9 → 17 stages") and
  `design.md:5,127,176,187`.
- Code (authoritative): `build_pipeline`
  (`sdk/quantlab/agents/research_director.py:221-487`):
  - **Non-orchestrated**: 11 agent stages (research|research_llm,
    hypothesis_builder, refutation, builder, statistics, analysis, review,
    portfolio, compile, deploy, monitor — :280-302,330) + 5 gates
    (:333-373) = **16 entries** (audit's "16 non-orchestrated" verified).
  - **Orchestrated**: 17 base agent stages (adds config_review, dispatch,
    demo, archive, live_ops, execution_monitor, guardian_evaluate — :286-323)
    + 8 gates (adds HUMAN_APPROVE_CONFIG/DEMO/ARCHIVE — :374-408) =
    **25 entries**; with `retest`/`optimize` configured: 19 agent stages +
    8 gates = **27** (:325-328).
- The "4 transition stages" never existed in code — the spec describes the
  pre-2026-08-06 design (8-agent research pipeline). The 14-phase lifecycle
  (REQ-37) superseded it: `openspec/config.yaml:12-14`, `flow.py PHASES`
  (`sdk/quantlab/campaign/flow.py:33`), and the archived
  `full-campaign-flow` changes are the canonical sources.
- `multi-agent-research-system` is still an **open change** (has
  verify-report.md, not archived).

### Affected Areas

- `openspec/changes/multi-agent-research-system/specs/research-director/spec.md`
  (:5,13,18) and `specs/pipeline-core/spec.md`, `proposal.md:118`,
  `design.md:5,127,176,187` — stale counts.
- `sdk/quantlab/agents/research_director.py:221-487` — the code is
  authoritative; do not "fix" the code to 17.
- `sdk/quantlab/campaign/flow.py:33` — canonical PHASES.

### Approaches

1. **Fix the spec wording to match code** — update
   research-director/spec.md (+ pipeline-core, proposal, design) to describe
   the current 16/25/27 entry shapes, then archive the change.
   - Pros: docs match reality; the change's verify-report already covers
     implementation.
   - Cons: re-verification of spec deltas before archiving.
   - Effort: Low.
2. **Fix the code to 17** — regress the pipeline to 8 agents + 5 gates.
   - Pros: none (would delete compile/analysis/config_review/dispatch/demo/
     archive/live-ops from the flow).
   - Cons: destroys the implemented 14-phase flow; contradicts REQ-37.
   - Effort: Very High; wrong.
3. **Add a canonical stage-count spec** — write
   `openspec/specs/pipeline-orchestration/spec.md` (or extend
   `full-campaign-lifecycle`) that states the entry counts per mode.
   - Pros: gives future audits a single source of truth.
   - Cons: spec already exists in pieces; risk of another drift.
   - Effort: Low.

### Recommendation

Approach 1 (+3): correct the stale multi-agent-research-system wording and
archive it (its deltas already live in the main specs); add a short canonical
"pipeline entry counts per mode" note to the lifecycle spec. Code is
authoritative.

### Risks

- Archiving multi-agent-research-system requires its delta specs to be merged
  into `openspec/specs/` first (sdd-archive convention) — verify
  `openspec/specs/research-agent` etc. already carry the content.
- Any new count wording will drift again unless anchored to
  `flow.py PHASES` + `build_pipeline` (tests/test_flow_integrity.py exists).

### Ready for Proposal

Yes — proposal should name the exact spec lines to correct and the archive
sequence.

---

## G6 — Knowledge Lake empty

### Current State

- Empty dirs (only `.gitkeep` / `_template`): `datasets/`, `raw/`, `graph/`,
  `embeddings/`, `guardian-feedback/`, `maintenance/`, `pipeline-runs/`,
  `parameter-matrix/` (has `_template/`), `campaign-phases/` (`.gitkeep` +
  `_template/` only).
- Populated: `structured/sqx-kb/144.2953/` — 85 files (82 parameter YAMLs +
  `educational/educational-dataset.yaml` + `educational-table.md`);
  `agent-memory/quantlab-campaign/invest-100usd/memory.yaml` (1 entry).
- `knowledge/index.yaml`: `_version: '4'` (store.py rebuilds to v5 with
  campaign_phases/parameter_matrix/guardian_feedback/maintenance keys,
  `store.py:470-483`), `directories: {}`, `kb_parameters: 82` (verified by
  count), `campaign_phases: None`, `parameter_matrix: None`. Index is stale
  (generated 2026-08-11) and predates v5.
- Seeders exist and are CLI-wired:
  - `sdk/quantlab/knowledge/kb/seeder.py` — `seed_from_doc` (:897),
    `iter_seed_entries` (:932); `validation.py:29`:
    `SEED_TOTAL = 82 (77 SEED_SPEC + 5 GAP_SPEC)` — matches index.
  - `sdk/quantlab/knowledge/kb/seeding_flow.py:183` `run_seed_flow` →
    `sdk/quantlab/cli/sq_commands.py:136` (`sqx kb seed`).
  - `sdk/quantlab/knowledge/kb/educational.py:176` `build_educational_dataset`
    → `sq_commands.py:26` (`sqx kb educational`) — writes
    `structured/sqx-kb/{ver}/educational/educational-dataset.yaml` (82 records,
    status `needs_review` for undocumented params).
- Query machinery: `QueryBuilder` (`sdk/quantlab/knowledge/query.py`) reads
  `index.yaml`; `find_similar_campaigns` (`store.py:962-999`) loads `.npy`
  embeddings from `embeddings/` → empty → falls back to text similarity
  (`_find_similar_text`).

### Affected Areas

- `knowledge/{datasets,raw,graph,embeddings,guardian-feedback,maintenance,
  pipeline-runs,parameter-matrix,campaign-phases}/` — seed targets.
- `sdk/quantlab/knowledge/kb/{seeder,educational,seeding_flow}.py` — existing
  seeders.
- `sdk/quantlab/knowledge/store.py:431-500` — `rebuild_index` (v5).
- `sdk/quantlab/knowledge/query.py` + `store.py:962` — consumption side.

### Approaches

1. **Real-data seeding via the connectors that exist** — run `_ensure_data`/
   `DataManager` for a small symbol set (M1/M5/H1), cache OHLC samples in
   `datasets/`, and generate SQX databank summaries from exports; keep KB
   seeding as-is (already 82 entries).
   - Pros: no fabricated data; exercises the real Dukascopy/JForex path;
     unblocks G3 TA + embeddings (G6 enables G3).
   - Cons: requires SQX/JForex environment for real data; small dataset only.
   - Effort: Medium.
2. **Pipeline-run + phase-envelope seeding** — wire `save_phase_envelope` and
   `save_pipeline_run` into the flow (G1) so every campaign populates
   `campaign-phases/` + `pipeline-runs/` naturally.
   - Pros: organic growth; no synthetic content.
   - Cons: needs G1's wiring first.
   - Effort: Low (depends on G1).
3. **Educational/benchmark seeding** — extend the educational generator to a
   benchmark index (parameter guidance summaries) + doc-gap entries.
   - Pros: zero market-data risk.
   - Cons: does not feed TA/embeddings.
   - Effort: Low.

### Recommendation

Approach 1 + 2 together: seed real OHLC samples through the existing
DataManager/JForexProvider path and let campaigns fill the operational dirs
once G1 wires the envelope writers. Never fabricate market data.

### Risks

- Real fetch is environment-dependent (SQCLI_PATH / JForex state) — seed must
  be a CLI command with mock-able tests, not an implicit init.
- `rebuild_index` v4→v5 migration will rewrite index.yaml — check
  `tests/knowledge/test_knowledge_store_v5.py` expectations.

### Ready for Proposal

Yes — proposal should scope the seed command, the dataset layout
(`datasets/{campaign}/…`), and the index migration.

---

## G7 — Teaching table not a reviewer deliverable

### Current State

- `build_teaching_table` (`sdk/quantlab/knowledge/kb/teaching.py:39`) renders
  the REQ-205 markdown table; `TABLE_HEADERS` (:19-28). Its docstring says
  "config_reviewer must return per configured parameter (REQ-205)" — but
  `ConfigReviewer.review` (`sdk/quantlab/agents/config_reviewer.py:84-132`)
  returns only `action/reason/proposed_changes/cost_note`; **no teaching
  table, no persistence**.
- `ConfigReviewStage` (`sdk/quantlab/pipeline/stages/config_review_stage.py:22-61`)
  emits `config_review_verdict` into `ctx.artifacts` — in-memory only.
- Current consumers of `build_teaching_table`: campaign prompt example
  (`ai/opencode/agents/campaign.md:378-384`), the educational dataset generator
  (`kb/educational.py`), tests (`sdk/tests/test_context.py:351-362`). The
  prompts instruct agents to "include the Knowledge base teaching table markdown
  block" (campaign.md:387-390; phase-config.md:25; phase-review.md:33) — this
  is guidance, not a persisted artifact, and phase agents cannot write
  (edit:false/write:false).

### Affected Areas

- `sdk/quantlab/agents/config_reviewer.py:84` — `review()` must build the table
  for the configured parameters.
- `sdk/quantlab/pipeline/stages/config_review_stage.py:41-61` — must persist.
- `sdk/quantlab/knowledge/kb/teaching.py:39` — table renderer (reuse as-is).
- `sdk/quantlab/knowledge/kb/store.py:140` — `KbStore.consult` (parameter
  lookup for the configured BuildConfig fields).
- `ai/opencode/agents/phase-review.md` — envelope `artifacts` gains the path.

### Approaches

1. **Reviewer-emitted persisted table** — `ConfigReviewStage.execute` calls
   `build_teaching_table` over `KbStore.consult` hits for the `BuildConfig`
   fields, writes
   `knowledge/structured/{campaign_id}/review/teaching-table.md`, and includes
   the path in the verdict + `PhaseResult.artifacts`.
   - Pros: deterministic, testable, closes the REQ-205 wording; reviewer
     becomes the deliverable owner.
   - Cons: needs `campaign_id`/`knowledge_root` in the stage context;
     teaching rows must be derived from the configured fields (mapping effort).
   - Effort: Medium.
2. **Phase-review agent renders and returns the table** — the review phase
   agent composes the table from `KbStore.consult` and returns it in the
   envelope.
   - Pros: no SDK persistence change.
   - Cons: agents cannot write files (REQ-820); content lost unless the
     orchestrator persists it; non-deterministic.
   - Effort: Low, fragile.
3. **Include the table in the existing parameter_matrix.json** — extend the
   builder's matrix artifact (builder_agent.py:232-274) with the teaching
   columns.
   - Pros: reuses the already-persisted matrix path.
   - Cons: puts a review deliverable in the build artifact; blurs ownership.
   - Effort: Low-Medium.

### Recommendation

Approach 1: the reviewer stage owns and persists the teaching table — it is the
only option that matches the REQ-205 wording in `teaching.py:3-8` ("config_reviewer
must return per configured parameter") and REQ-820's artifact boundary.

### Risks

- BuildConfig→KB-parameter mapping is fuzzy (KB entries keyed by tab/name) —
  the table may need a "no KB entry" row fallback (REQ-204 needs_review path).
- New persisted files may affect `tests/knowledge/test_knowledge_store_v5.py`
  or index rebuild expectations.

### Ready for Proposal

Yes — proposal should define the artifact path, the field→KB lookup, and the
envelope wiring.

---

## Cross-Gap Synthesis

- **Dependency chain**: G1 wiring (envelope writers) enables G6 Approach 2;
  G6 seeding enables G3 (TA on real bars); G3 and G7 both depend on
  `knowledge_root` + `campaign_id` being reliably present in stage contexts
  (a shared plumbing gap in `_run_sdk_stage`, delegation.py:181-215).
- **Single root cause family**: the delegation layer (`campaign/delegation.py`)
  treats stage outcomes as ephemeral context dicts — no phase owns durable
  artifact writing. Fixing the envelope/artifact plumbing (G1/G6/G7 together)
  is the highest-leverage slice.
- **Security**: G4's unrestricted `quantlab-campaign` bash is the only
  emergency-grade item (config outside VCS, affects every campaign run).
- **Docs**: G5 is a pure doc-archival task; low risk, do first.
- **Architecture**: G2 is the largest change; sequence it behind the plumbing
  fixes and keep `QUANTLAB_CUSTOM_PROJECT` as the migration flag.

## Key Learnings

1. The orchestrated campaign flow persists no user-facing proposal or spec artifact; phase envelopes exist as an unwired API with zero production callers.
2. The orchestrated builder path uses the legacy single-task CFX translator while the 21-task CustomProject generator is enabled-by-default but never invoked by any pipeline stage.
3. Two real ta-backed indicator engines exist in the SDK but both are orphans; research consumes no Dukascopy data.
4. The live opencode.json grants quantlab-campaign unrestricted bash and references three agents that do not exist, while the phase agents are properly deny-first.
5. The "17-stage pipeline" wording in multi-agent-research-system specs is stale; the code builds 16 non-orchestrated and 25-27 orchestrated pipeline entries.