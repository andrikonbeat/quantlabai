# Exploration: knowledge-memory-consumption-wiring

## Current State

The `knowledge-memory-system` change (WU1–WU6) delivered the Knowledge Lake, SQX parameter KB, version detection, context injection, and training exports. Two consumption surfaces were delivered and unit-tested in WU5 but **not wired** into the agents that need them:

- **REQ-204**: `KbStore.consult()` is implemented in `sdk/quantlab/knowledge/kb/store.py:121` and tested in `sdk/tests/test_context.py` (`TestKbConsult`). It returns agent-facing guidance metadata (`what_it_does`, `how_it_works_in_sqx`, `quant_trading_role`, `small_account_recommendation`, `status`, `evidence_ref`) and returns an empty list when nothing matches — the REQ-204 "missing entry blocks configuration" hook.
- **REQ-205**: `build_teaching_table()` is implemented in `sdk/quantlab/knowledge/kb/teaching.py:39` and tested in `sdk/tests/test_context.py` (`TestTeachingTable`). It renders a markdown table (Tab/Section, Parameter, What it does, How it works in SQX, Quant trading role, Chosen config, Why, For what) for a list of `KbParameter` entries.
- **Task 6.3** (building-blocks KB tab + changelog polling) was explicitly deferred as future in the original change.

`builder_agent.py` currently translates `ResearchConfig` → CFX, validates, checks license, and dispatches. It does **not** consult the KB before configuring builder parameters. `config_reviewer.py` reviews in-flight `BuildConfig` for contradictions and emits APPROVE/MODIFY/BLOCK verdicts, but does **not** emit the teaching table.

## Affected Areas

- `sdk/quantlab/agents/builder_agent.py` — REQ-204 wiring point: before/after `_translate()` or within `run()`, the agent must call `KbStore.consult()` on parameters being configured. The `research_config` (DSL) and `build_config` (in-flight) are available in `run()` and `_dispatch_with_retry()`.
- `sdk/quantlab/agents/config_reviewer.py` — REQ-205 wiring point: `ConfigReviewer.review()` must call `build_teaching_table()` on the KB parameters matching the `BuildConfig` and include the markdown table in the verdict. **BLOCKED**: this file has 11 lines of uncommitted concurrent edits (adding a `None` guard for `build_config`). Do NOT touch, revert, or assume its current state is safe to modify.
- `sdk/quantlab/cli/sq_commands.py` — already exposes `quantlab sqx kb list/get/seed/verify/status` and `sqx check-version`. A building-blocks tab view could extend `kb list --tab "Building blocks"`, but no dedicated tab-view subcommand exists yet.
- `sdk/quantlab/dashboard/app.py` + `templates/` — no KB tab scaffold exists. The dashboard has Campaigns, Pipeline, and Statistics. A new `/knowledge` or `/kb` route + template would be needed for a building-blocks tab view.
- `sdk/quantlab/knowledge/kb/seeder.py` — already seeds all 8 tabs including "Building blocks" (Signals, Indicators, Stop/Limit entry blocks, Order types, Exit types, Calibrate indicators).
- `doc_dev/SQX Builder Config.md` — mentions the need to "detect version changes, review the official SQX changelog, and re-adjust QuantLab." This is the upstream source for "changelog polling."
- `sdk/quantlab/versioning.py` — `DriftWorkflow` already writes migration checklists and invalidates the KB on version drift. "Changelog polling" is not yet implemented anywhere.

## Approaches

1. **Minimal wiring (recommended first slice)** — Wire REQ-204 and REQ-205 only, leaving Task 6.3 for a follow-up change.
   - **REQ-204 in builder_agent.py**: After `research_config` is parsed into `ResearchConfig` (line 120), extract builder-relevant parameter names/tabs and call `KbStore.consult()`. If the result is empty for a configured parameter, raise/block or append a warning to the envelope (matching REQ-204's "missing entry blocks configuration" contract).
   - **REQ-205 in config_reviewer.py**: After the contradiction/adjustment checks in `review()`, look up the configured parameters via `KbStore` and append `teaching_table` (markdown string) to the `ConfigReviewVerdict`.
   - **Pros**: Small, focused, matches the original SDD scope. REQ-204/205 surfaces already exist and are tested.
   - **Cons**: `config_reviewer.py` is blocked by concurrent uncommitted edits; this slice MUST wait until that file is stable.
   - **Effort**: Low (2 files, no new modules).

2. **Full Task 6.3 in the same change** — Add a building-blocks KB tab view (CLI + dashboard) and implement changelog polling.
   - **CLI**: Add `quantlab sqx kb tab Building-blocks` or extend `list --tab "Building blocks"` with richer output. This is already possible with the existing CLI — just documentation/formatting.
   - **Dashboard**: New `/kb` route + `kb_dashboard.html` template rendering the building-blocks tab from `KbStore.list(tab="Building blocks")`.
   - **Changelog polling**: Net-new. Would need a `ChangelogPoller` that scrapes/polls the official SQX changelog (URL TBD), diffs against current KB, and surfaces "needs_review" entries. The `DriftWorkflow` in `versioning.py` is the closest analog but does not poll changelogs.
   - **Pros**: Completes the deferred Task 6.3; users get a browsable KB view.
   - **Cons**: Changelog polling is underspecified (no URL, no format, no schedule). The dashboard slice adds templates, routes, and JS. Scope creep risk.
   - **Effort**: Medium–High (new CLI subcommand, new dashboard page, new polling service).

3. **Defer Task 6.3 entirely** — Close only REQ-204 and REQ-205 in this change, explicitly leave building-blocks tab + changelog polling for a future `knowledge-kb-consumption` change.
   - **Pros**: Keeps the change small and reviewable. Matches the original change's explicit "future" labeling.
   - **Cons**: Delays the visible KB surface one more change.
   - **Effort**: Low.

## Recommendation

**Approach 1 (minimal wiring) + Approach 3 (defer Task 6.3)**.

Wire REQ-204 and REQ-205 first because:
- The surfaces (`KbStore.consult`, `build_teaching_table`) are already built, tested, and referenced in `campaign.md` prompts.
- `builder_agent.py` is clean (no concurrent edits) and the wiring point is obvious.
- `config_reviewer.py` **must not be touched now** due to concurrent uncommitted edits; defer its wiring to a follow-up micro-change or wait until the concurrent edits are committed.

Leave Task 6.3 (building-blocks KB tab + changelog polling) for a future change because:
- The original change explicitly labeled it "future."
- "Changelog polling" is underspecified: no changelog URL, format, or polling mechanism exists in the codebase. It would be net-new and require architectural decisions.
- The existing `quantlab sqx kb list --tab "Building blocks"` already surfaces the data; a dedicated tab view is a UX layer, not a correctness gap.

## Risks

- **Concurrent edits on `config_reviewer.py`** — 11 uncommitted lines adding a `None` guard. Any attempt to wire REQ-205 now risks merge conflicts or overwriting the other process's work. **BLOCKER for REQ-205 until edits are committed or stashed.**
- **Concurrent edits on `compiler.py`, `jforex_deploy.py`, `project_builder.py`, `test_project_builder.py`** — these are listed in the constraints as do-not-touch. They do not block REQ-204 but indicate an active working tree that must be respected.
- **Ambiguous requirement for "changelog polling"** — no implementation target, URL, or schedule exists. Attempting to spec this in the same change would stall on design questions.
- **REQ-204 blocking behavior** — the spec says "configuration is blocked pending a needs_review entry or explicit user override." The exact blocking mechanism (raise exception? return warning in envelope? modify `BuildConfig`?) needs a design decision.
- **Dashboard KB tab scope** — no scaffold exists. A new tab requires Flask routes, Jinja templates, JS page modules, and CSS. This is medium effort and better owned by a dedicated dashboard/KB change.

## Ready for Proposal

**Yes** — scope is clear enough for proposal.

**What the orchestrator should tell the user**:
> This change will wire the two deferred consumption hooks from `knowledge-memory-system`: (1) `builder_agent` KB consult (REQ-204) and (2) `config_reviewer` teaching-table emission (REQ-205). Task 6.3 (building-blocks KB tab + changelog polling) is deferred to a future change because the original SDD explicitly marked it future and changelog polling is underspecified. **Caution**: `config_reviewer.py` has uncommitted concurrent edits and is blocked until those are committed. `builder_agent.py` is clean and can proceed immediately.

## Key Learnings

1. `KbStore.consult()` and `build_teaching_table()` were delivered in WU5, tested in `sdk/tests/test_context.py`, and documented in `AI/opencode/agents/campaign.md`, but never imported or called by `builder_agent.py` or `config_reviewer.py`.
2. `config_reviewer.py` has 11 lines of uncommitted concurrent edits (adding `None` guard) — it is blocked for modification until the other process commits or stashes.
3. Task 6.3 was explicitly labeled "future" in the original `knowledge-memory-system` tasks and proposal; changelog polling has no existing scaffold, URL, or mechanism in the codebase.
4. The dashboard has no KB tab scaffold — only Campaigns, Pipeline, and Statistics views exist.
5. The `quantlab sqx kb` CLI already supports `list --tab "Building blocks"`, so the building-blocks data is already queryable.
