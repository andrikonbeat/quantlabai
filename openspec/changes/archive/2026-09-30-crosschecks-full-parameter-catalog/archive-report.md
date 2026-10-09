# Archive Report: CrossChecks Full Parameter Catalog

**Change**: `crosschecks-full-parameter-catalog`
**Capability**: `crosschecks-parameter-catalog` (+ modified `sqx-parameter-kb`, `cfx-editor`, `crosschecks-models`)
**Artifact store**: hybrid (OpenSpec authoritative, Engram mirror)
**Archive date**: 2026-09-30
**Verdict**: `pass_with_warnings` — archived with warnings, no blockers, 0 critical findings

---

## 1. Status

| Field | Value |
|-------|-------|
| SDD cycle | Complete — planned, implemented, verified, archived |
| Verification verdict | `pass_with_warnings` |
| Blockers | 0 |
| Critical findings | 0 |
| Requirements | 6/6 compliant (2 with an unwired/untested sub-clause: W-3, W-4) |
| Scenarios | 6/6 with passing runtime evidence (0 `UNTESTED`, 0 `FAILING`) |
| Tasks | 40/40 complete (1.1–1.10, 2.1–2.7, 3.1–3.5, 4.1–4.4, 5.1–5.3, 6.1–6.11) |
| Native review receipt | None discovered — `reviewGate` structurally absent from the launch status; archive proceeded under ordinary repository policy |
| Evidence revision | `sha256:4ccb4cbbeaad3e69c0f3bc75627ffa91083f32166cd02e1a4dd48f0c8a7d6bf2` |
| Archived intentionally with warnings | Yes — 4 open warnings recorded below (W-1 … W-4) |

### Task Completion Gate

PASSED. Every implementation checkbox in `tasks.md` is `[x]`; no stale unchecked tasks; no archive-time reconciliation was required or performed. Task `3.3` is `[x]` with its original text struck through and an explicit rationale (see §7) — a legitimate scope reduction, not an unchecked task.

---

## 2. Executive Summary

The change gives LLM agents and human researchers one evidence-backed catalog of every SQX 144.2953 robustness-filtering parameter, spanning all **9** top-level `<CrossChecks>` children, and wires it end-to-end: 10 KB YAML catalog entries → typed `CrossChecksConfig` models → a 213-entry tab-scoped `BuildConfig` mapping → a dual JSON+text `summary()`. Evidence-first discipline held: 9 `verified` entries + 1 `needs_review` (`Cross Checks vs Retester`, doc gap), zero invented parameters, and every mapping regex resolved against real shipped XML. Verification passed with warnings: the capability works and the tests are green, but four items remain open — one misleading diagnostic at scale (W-1), one spec that under-counts the tabs it governs (W-2), one mechanism with no production caller (W-3), and one contract clause with no regression guard (W-4). None corrupt output; all four are recorded as follow-ups.

---

## 3. Final State (authoritative)

These are the facts **at close**. Where an intermediate snapshot in `apply-progress.md` or `verify-report.md` disagrees, the final state below wins.

### 3.1 Test and build evidence

| # | Command | Exit | Result | Source |
|---|---------|------|--------|--------|
| 1 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/phase4 tests/cfx` (declared gate, envelope `test_command`) | 0 | **854 passed**, 2 warnings | verify-report, written 2026-09-30 06:14:49, `sha256:d29b2adb…` |
| 1a | *same command, re-run at archive* | 0 | **886 passed**, 1 warning, 51.31s | this archive, 2026-09-30 — see §6.3, unexplained delta |
| 2 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/agents sdk/tests` | 0 | **1781 passed**, 0 failed, 21 warnings | verify-report + orchestrator final facts (two sources agree; not re-run at archive) |
| 3 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/` (whole tree) | 1 | **2662 passed**, 9 skipped, **1 failed** — pre-existing order-dependent flake, out of scope | verify-report; not re-run at archive |
| 4 | `python3 -m compileall -q` on the 4 changed modules | 0 | clean | verify-report |
| 5 | `python3 -c "import quantlab.cfx.models, quantlab.sqx.project_builder, quantlab.knowledge.kb.store, quantlab.agents.builder_agent"` | 0 | import smoke OK | verify-report |

`ruff` and `mypy` were not available locally (CI-only per project contract) — ➖ not a failure. `pytest-cov` is not installed and `pytest.ini` rejects `--cov`, so coverage is ➖ not available.


### 3.2 Catalog and builder invariants (re-verified at archive time)

Independently re-derived at archive; all figures below are observed, not carried over from the verify snapshot.

| Invariant | Observed value |
|-----------|----------------|
| Top-level `<CrossChecks>` children in real `project.cfx` (`assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx` → `config.xml`) | **9** — `RetestOnAdditionalMarkets`, `WalkForwardOptimization`, `RetestWithHigherPrecision`, `MonteCarloRetest`, `WalkForwardMatrix`, `MonteCarloManipulation`, `OptProfileSysParamPermutation`, `WhatIf`, `SequentialOptimization` |
| KB catalog files under `knowledge/structured/sqx-kb/144.2953/parameters/Cross checks/` | **10** YAMLs |
| Status distribution | **9 `verified` + 1 `needs_review`** (`Cross Checks vs Retester.yaml`, doc-gap markers present in `what_it_does` and `how_it_works_in_sqx`) |
| Entries missing any of the 13 required fields (`name`, `tab`, `type`, `xml_path`, `element_name`, `default`, `range`, `what_it_does`, `how_it_works_in_sqx`, `quant_trading_role`, `status`, `sqx_version`, `evidence_ref`) | **0** |
| `BuildConfig` fields | **213** |
| `_BUILD_CONFIG_MAP` entries | **213** |
| Parity | **213 ↔ 213, 0 unmapped fields, 0 extra keys** |
| `_CROSSCHECK_FIELD_SPECS` entries (tab-scoped) | **112** |
| `_apply_acceptance_settings` present in `project_builder.py` | **False** (removed by design, task 3.3 / 5.2 / 6.11) |

### 3.3 Cross-tab corruption fixed during the audit pass

Five silent corruptions were found by auditing the 15 pre-catalog entries (still document-wide regexes) against real CFX evidence, and fixed with tab-scoped regions:

| # | Field | Corruption | Fix |
|---|-------|-----------|-----|
| 1 | `wf_max_tests` | rewrote `<MaxTests>` in **three** tabs (WFO=100, WFM=100, PSPP=1000) | scoped to `_settings_scope(_WFO)` |
| 2 | `wf_period` / `wf_optimization` | leaked into WalkForwardMatrix (both tabs declare `<WalkForward period="10" optimization="15">`) | scoped to WFO settings |
| 3 | `wf_optimize_periods` / `wf_optimize_exit_types` | leaked into WFM | scoped to WFO settings |
| 4 | `wf_acceptance_threshold_pct` | rewrote WFM's `thresholdPct` (both tabs declare `<Conditions thresholdPct="80">`) | scoped to WFO acceptance |
| 5 | `rc_spread` | rewrote the **project's main chart** spread (`<Chart symbol="GBPUSD" spread="3">` in the root Setup) | scoped to RC settings |

Plus `wf_acceptance_min_conditions` / `_min_markets` were writing into the RC tab; WFO declares neither node, so both are now scoped to WFO acceptance and are inert.

Five WFM fields were added for WalkForwardMatrix's own copy of five WFO Settings leaves that had no field: `wfm_period`, `wfm_optimization`, `wfm_optimize_periods`, `wfm_optimize_exit_types`, `wfm_max_tests`.

---

## 4. Open Warnings (carried forward, none blocking)

### W-1 · Real defect, untriaged — false "field does not exist" warning at scale

`sdk/quantlab/sqx/project_builder.py:1874-1878`, in `_apply_in_scope`:

```python
patched = re.sub(leaf, replacement, region.group(0), flags=re.DOTALL)
if patched == region.group(0):
    logger.warning("... pattern found no match inside its own tab scope ...")
```

"No match" is decided by comparing the **rewritten region** against the original region. That comparison is also true when the requested value **equals the value already present** — a successful, idempotent no-op write. The result is a false "this field likely does not exist in this SQX build" warning.

Reproduced at archive time on the shipped template:

```text
BuildConfig(wf_acceptance_threshold_pct=55) → no warning,  thresholdPct ['55','80']   ← correct write
BuildConfig(wf_acceptance_threshold_pct=80) → WARNING,     thresholdPct ['80','80']   ← misleading warning
BuildConfig(wf_acceptance_threshold_pct=90) → no warning,  thresholdPct ['90','80']   ← correct write
```

- **Scope**: an independent archive-time sweep over `_CROSSCHECK_FIELD_SPECS` resolved the current value of **98** fields against `Build-Task1.xml` and set each to that value; **all 98** emitted the false warning. (The verify report recorded the same numerator, 98, against a denominator of 107 catalog fields; this sweep's denominator differs because its value-resolution step left 14 of the 112 spec entries unresolvable. The affected-field count, 98, is confirmed by both.)
- **Impact**: diagnosability only. No XML is ever corrupted and every postcondition holds — including the spec scenario's `<Conditions thresholdPct="80">`. The misleading part is that an agent explicitly setting a field to the template default is told the opposite of the truth.
- **Fix candidate (not applied — implementation code is out of archive scope)**: compare the *match* rather than the rewritten region, e.g. branch on `re.search(leaf, region.group(0), re.DOTALL) is None`.

**Classification**: confirmed defect, mechanism and scale reproduced. Not a blocker.

### W-2 · Spec drift — the spec under-counts the tabs it governs

`spec.md` enumerated **8** robustness tabs and omitted `SequentialOptimization`, in three places (the tab enumeration, the "Full tab coverage" scenario, and the acceptance criteria). The real `.cfx` has **9** top-level `<CrossChecks>` children, the catalog ships **9** `verified` entries including `Sequential Optimization.yaml`, and the proposal, design and tasks all said 9.

The **implementation, proposal, design and tasks are correct**; the spec was the stale artifact. **Corrected at archive time** (§5) under explicit authorization: the tab count is now 9 in both the delta spec and the merged main spec, and `SequentialOptimization` is named.

Secondary note, not corrected (test-code scope, out of archive authority): `tests/knowledge/test_crosschecks_schema.py` still holds an 8-element `_EXPECTED_TABS` set and asserts `_EXPECTED_TABS.issubset(present_tabs)`. The 9th tab is pinned by other tests in the same suite, so this under-constrains rather than hides, but widening it to an equality assertion is a cheap follow-up.

### W-3 · Missing production wiring — the version-drift hook has no caller

`KbStore.invalidate_on_version_drift()` (`sdk/quantlab/knowledge/kb/store.py:291`) is defined and unit-tested (4 passing tests: demotion, actionable warning naming both versions, matching-version no-op, tab scoping). A repo-wide symbol search returns exactly six hits: the definition plus five call sites, **all inside `tests/knowledge/test_crosschecks_schema.py`**. There is no production caller.

Consequence: on a real 145.x install nothing calls the hook, so no entry is ever actually demoted. The consumer half of the spec scenario is satisfied by a **separate** path — `builder_agent._consult_kb` (`sdk/quantlab/agents/builder_agent.py:203`) inspects `entry["status"] == "needs_review"` and appends a warning, raising only under `strict_kb` — but the two halves are not connected, so the end-to-end chain *drift → demotion → consumer warning* is unproven in production. A `needs_review` warning would only fire for entries already marked as such in the seed data.

**Classification**: implemented and unit-tested; the production call site is the gap. One call site (KB load or builder-agent startup) closes it. Follow-up, not a blocker.

### W-4 · Untested contract clause — the "single-line" text guarantee has no regression guard

The summary contract requires `text` to be "a single-line string for log envelopes". The four summary tests assert the presence of the `json`/`text` keys, their types and selected `json` values — **none asserts the absence of newlines**. The verifier confirmed the behavior holds at runtime (`"\n" not in text and "\r" not in text` → `True`, 260 chars) on real template input, so the behavior is correct today, but nothing would catch a regression that started embedding newlines. One `assert "\n" not in summary["text"]` closes it.

**Classification**: untested clause, behavior verified. Not a blocker.

---

## 5. Spec Sync Performed

`openspec/config.yaml` → `rules.archive: [Warn before merging destructive deltas]`. **No destructive delta was merged.** Every operation below is additive or a verified factual correction; no requirement was removed, renamed, or had scenarios dropped. No warning escalation was required.

### 5.1 `openspec/specs/crosschecks-parameter-catalog/spec.md` — UPDATED

The main spec already existed and was **byte-identical** to the delta (`sha256:2c7485554ca43f8fb1265517389d02b89758ab768eba659a889a9cf978a2c655` on both) — a consequence of the change's first archive on 2026-09-29 (see §8). All 6 requirements were therefore already present; nothing to append. Two **MODIFIED** requirement corrections were applied:

1. **Catalog Completeness** — tab count corrected 8 → 9 with `SequentialOptimization` named, and the required-field list extended to the 13 fields actually enforced and verified (`xml_path`, `element_name`, `sqx_version`, `evidence_ref` were missing from the list). This removes an under-specification: the spec previously required fewer fields than the test suite enforces.
2. **Full tab coverage** scenario — "all 8 robustness tabs" → "all 9", and the equality wording tightened to match the observed artifact.

### 5.2 Delta spec `openspec/changes/crosschecks-full-parameter-catalog/specs/crosschecks-parameter-catalog/spec.md` — CORRECTED

The same 8 → 9 correction was applied to the delta so the archived audit trail and the main spec agree. This is the exact amendment the verify report recommended, applied under the orchestrator's explicit authorization. Post-sync the two files are byte-identical again.

### 5.3 `openspec/specs/cfx-editor/spec.md` — UPDATED (ADDED requirement)

Appended **"Robustness Tab Typed Coverage and Dual-Output Summary"**, matching the proposal's declared `cfx-editor` modification:

- `CrossChecksAutomaticRetest` typed coverage extends to `what_if` (`WhatIfConfig` with `use` + `methods`) and `monte_carlo_retest.methods` (`list[CrossChecksMethod]` carrying `use` / `type` / `params`).
- `summary()` MUST return `{"json": dict, "text": str}`, with `json` carrying `dialect`, `enabled_tabs`, `typed_values` and the typed sub-model dumps, and `text` a space-joined single line.
- Scenarios for method round-trip, Generic/AutomaticRetest dialect preservation, and the dual-output shape.

Appended, so the 57 uncommitted lines already present in this working-tree file were not disturbed.

### 5.4 `openspec/specs/crosschecks-models/spec.md` — UPDATED (MODIFIED requirement)

The **CrossChecks AutomaticRetest Dialect Model** requirement enumerated 8 typed fields and omitted `what_if`, which the change actually shipped. Field list corrected to 9 and scenarios added for the WhatIf / MonteCarloRetest method round-trip. This was drift in a *sibling* main spec that the delta's "Model Extension" requirement directly modifies.

### 5.5 `openspec/specs/sqx-parameter-kb/spec.md` — UPDATED (MODIFIED requirements)

- **REQ-201 KB Schema** — `xml_path` and `element_name` added to the required field list, per the proposal's declared schema gain. All previously required fields preserved.
- **REQ-204 Consumption by Agents** — added the warn-not-block semantics: a consumer MUST warn when a consulted entry is `needs_review` (or absent) and MUST NOT abort unless strict mode is enabled. The pre-existing missing-entry scenario was **preserved**, not replaced: under non-strict mode a missing entry warns and proceeds, under strict mode it still blocks.
- **REQ-208 Version-Invalidation Hook** — added the concrete drift contract: `invalidate_on_version_drift()` returns a result carrying `catalog_version`, `current_version`, `drifted`, `invalidated` and actionable `warnings`; it **never raises** and `blocked` stays `False`; it short-circuits to a no-op when versions match; strict-mode consumers abort on `drifted` themselves.

### 5.6 Verified consumer semantics behind the REQ-204/208 sync

`builder_agent._consult_kb` was read to confirm the spec text matches the code:

```python
entries = store.consult(name="", tab=tab)
if not entries:
    warnings.append(f"KB tab '{tab}' has no entries"); continue
for entry in entries:
    if entry.get("status") == "needs_review":
        warnings.append(f"KB tab '{tab}' has entries needing review"); break
if warnings and self._strict_kb:
    raise ConfigurationError(...)
return warnings
```

Warn-collect by default, raise only under `strict_kb` — exactly the contract written into REQ-204.

---

## 6. Stale Claims Corrected

### 6.1 S-1 · `apply-progress.md` overstates pre-existing breakage — CORRECTED

`apply-progress.md` recorded "`tests/agents` + `sdk/tests`: 5 failures, all **pre-existing**". That is no longer true. An independent run at verify time gave **1781 passed, 0 failed, exit 0**; the same figure is carried as final state in §3.1. A stale "known pre-existing" note on a test path is actively harmful: it invites a future reader to discount a real regression there as already-accounted-for. Corrected in place with an archive-time annotation.

### 6.2 Other staleness found at archive time — RECORDED, not rewritten

Found while reading the change folder. The historical rows are left intact (they are a valid record of what was believed at the time) and annotated in a new `Archive Corrections` section appended to `apply-progress.md`:

| Stale claim | Location | Actual state at close |
|-------------|----------|----------------------|
| `_apply_acceptance_settings()` "addresses a leaf by tab scope" | `apply-progress.md` L17 (3.3 Helper row) | Helper was **removed** (tasks 3.3 / 5.2 / 6.11); `hasattr(project_builder, "_apply_acceptance_settings") == False` |
| "114 entries in `_BUILD_CONFIG_MAP`" | `apply-progress.md` L16 (3.2 GREEN map row) | **213** entries |
| `design.md` "File Changes" lists `sdk/tests/test_cfx.py` (modify) and `sdk/tests/sqx/test_project_builder.py` (create) | `design.md` L39-40 | Neither file exists. Real test homes: `tests/cfx/test_crosschecks_models.py`, `tests/cfx/test_reader_crosschecks.py`, `tests/phase4/test_project_builder.py`, `tests/knowledge/test_crosschecks_schema.py`. Task 5.3 checked the *decisions*, not this table. |
| `design.md` "E2E | Summary contract" testing layer | `design.md` L85 | Realised as a unit test; no E2E layer exists in this project. SUGGESTION-level only. |

### 6.3 Contradiction recorded, not silently resolved — the change-scoped gate count differs by 32

**This contradiction is unrankable. It is recorded here rather than resolved in either direction.**

| | Statement | Source | When written |
|---|---|---|---|
| A | `tests/phase4 tests/cfx` → **854 passed**, exit 0 | `verify-report.md` envelope + test table row 3, `test_output_hash: sha256:d29b2adb…` | 2026-09-30 06:14:49 |
| B | `tests/phase4 tests/cfx` → **886 passed**, 0 failed, exit 0, 51.31s | this archive's own re-run of the identical command | 2026-09-30 (archive phase) |

**What was checked, and what it showed.** Both runs agree the gate is green with **zero failures**, so the archive decision is unaffected. The 32-test difference is *not* explained by tree state:

- Every change-scoped source, test and data file has an mtime at or before **2026-09-29 06:55:08** — `project_builder.py` and `test_project_builder.py` (06:55:08), `models.py` (06:55:08), `store.py` (06:23:14), `test_crosschecks_models.py` (06:23:15), `test_crosschecks_schema.py` (2026-09-28), the two modified KB YAMLs (06:55:08), and the template (2026-08-12). All **predate** the verify report's write time of 06:14:49 on 2026-09-30. The tree did not change between the two runs.
- Collection is not data-driven in a way that could drift: the only `parametrize` decorators in `test_project_builder.py` (lines 1120, 1218, 1243) use literal argument lists, and the knowledge-schema tests iterate YAML files inside a single test body rather than generating cases. `pytest --collect-only` currently reports a stable 886 (127 in `test_project_builder.py`, 17 in `test_crosschecks_models.py`, 7 in `test_reader_crosschecks.py`).

**No cause is asserted.** A passing count cannot fall below an earlier passing count without tests being deleted, and none were — so B is the larger and current observation, but the mechanism behind the 32 is not established by the evidence available at archive time. Both numbers are reported with their sources; a reader needing the exact 854-case enumeration must either re-run or trust the verify report's output hash.

**Commands not re-run at archive** (figures carried from two agreeing sources, per §3.1): `tests/agents sdk/tests` (1781 passed — verify row 4 and the orchestrator's final facts agree) and the whole-tree `tests/` run (2662 passed / 9 skipped / 1 flake).

### 6.4 Earlier whole-suite failure counts differ across sessions — final state reported, no causal story

Earlier sessions in this change's history reported different whole-suite failure counts: 7 in the 2026-09-29 audit pass (Engram #1094), and 13 in a 2026-09-29 diagnostic (Engram #1090, which attributed 8 of them to the separate `typed-crosschecks-models` change). The final state is **1 pre-existing order-dependent flake** (§3.1), which is what the verify report and the orchestrator's final facts record. This archive reports the final count only and **asserts no causal link** between the earlier figures and the final one — those runs observed different tree states, and stitching them into a single narrative would be speculation.

---

## 7. Deliberate Deferrals (accepted, not defects)

| Deferred item | Decision |
|---------------|----------|
| WhatIf per-method day/hour/month toggles (7 weekdays + 24 hours + 12 months) stay `raw_xml` | Needs a typed list/dict shape — an API decision, deliberately not pre-empted. 43 real leaves confirmed in evidence as plain `<Param key=.. type="Boolean">`. |
| Acceptance `Condition` trees stay `raw_xml` | Chosen design decision (over a fully recursive Condition model). Consequence: **PF minimums are unreachable through `BuildConfig`**; callers must go through `CrossChecksConfig`. |
| `wf_acceptance_pf_min` / `rc_pf_min` registered as **inert** | SQX 144.2953 never emits `minValue` on `<Column-Value>` — checked across `Build-Task1.xml`, 2 saved configs and 123 sampled real project configs: 0 occurrences (`minValue` only ever appears on strategy `<Param>` nodes). Registered in `TestCrosscheckMappingsHaveEvidence._INERT` with a guard that the list cannot grow silently, and kept in the table so 213/213 parity holds. The fabricated `Column-Value minValue` fixture was dropped (task 5.2). |
| `wf_acceptance_min_conditions` / `_min_markets` retained in `BuildConfig` | WFO declares neither node, so they can never write. Kept for API compatibility, scoped to WFO acceptance, asserted as no-ops. Deprecate once no caller sets them. |
| `WalkForwardMatrix` / `OptProfileSysParamPermutation` keep `raw_xml` | Matches the design's open question rather than pre-empting it. |
| `opt_profile_sys_param_permutation` / `walk_forward_matrix` parse a `use` flag they cannot store | Both models declare only `raw_xml`, so pydantic's default `extra='ignore'` drops `use`. Effect: `summary()["json"]["enabled_tabs"]` lists those two tabs whenever the element *exists*, regardless of its `use` value. Pre-existing model shape; the summary contract is in this change's scope, so it is on the record. Mild imprecision for 2 of 9 tabs. |

### Scope reduction recorded — task 3.3

Task 3.3's `_apply_acceptance_settings` helper was **conditional** ("only if the mapping actually needs nested handling"). The condition did not hold: `_CROSSCHECK_FIELD_SPECS` already expresses tab scoping as `{tab}/AcceptanceSettings` plus `_acceptance_scope(tab)`, so the helper reduced to a one-line wrapper over `_apply_in_scope` with no production caller. Its direct tests were rewritten to drive `_apply_build_config` instead, so the same invariants are now covered on the real entry point (`TestCrosscheckAcceptanceIsTabScoped`). Verified at archive time: no dangling references, `hasattr(...) == False`.

---

## 8. Change History — This Is the Second Archive

This change was **archived once before, then reopened**. The record matters for anyone reading the audit trail:

1. **2026-09-29 05:50:56** — first archive (Engram #1089). Delta spec synced to `openspec/specs/crosschecks-parameter-catalog/spec.md`; change folder moved to `openspec/changes/archive/2026-09-29-crosschecks-full-parameter-catalog/`. That report noted 29 checkboxes in `tasks.md` at the time.
2. **2026-09-29 ~06:56** — the archived change was **reopened** to run the cross-tab corruption audit. Phase 6 (tasks 6.1–6.11) was added, task 3.3 struck through, a "Not Done" section added, `apply-progress.md` extended with a follow-up pass log, and the change folder moved **back** to `openspec/changes/crosschecks-full-parameter-catalog/`. The old archive folder is no longer on disk; only `2026-09-29-typed-crosschecks-models/` remains in `openspec/changes/archive/` for this family of changes.
3. **2026-09-30** — verify admitted (`pass_with_warnings`); this archive.

**Consequence for the main spec**: because the first archive already synced it, `openspec/specs/crosschecks-parameter-catalog/spec.md` arrived at this archive byte-identical to the delta, and the 40-task `tasks.md` is a superset of the 29-checkbox version the first archive recorded. This is why §5.1 is a correction rather than an append.

---

## 9. Artifacts

### 9.1 OpenSpec (authoritative)

| Path | Role |
|------|------|
| `openspec/changes/crosschecks-full-parameter-catalog/proposal.md` | Intent, scope, acceptance criteria, risks, delivery/rollback plan |
| `openspec/changes/crosschecks-full-parameter-catalog/specs/crosschecks-parameter-catalog/spec.md` | Delta spec — **corrected 8 → 9 tabs at archive** |
| `openspec/changes/crosschecks-full-parameter-catalog/design.md` | Architecture decisions, data flow, summary contract, threat matrix; "File Changes" table stale (§6.2) |
| `openspec/changes/crosschecks-full-parameter-catalog/tasks.md` | 40/40 complete, incl. Phase 6 audit pass and "Not Done" section |
| `openspec/changes/crosschecks-full-parameter-catalog/apply-progress.md` | Apply log + follow-up defect table; **S-1 corrected at archive** (§6.1) |
| `openspec/changes/crosschecks-full-parameter-catalog/verify-report.md` | Verdict, compliance matrix, 5 warnings, 4 suggestions, evidence revision |
| `openspec/changes/crosschecks-full-parameter-catalog/archive-report.md` | **This file** |

Implementation files (unchanged by this archive): `sdk/quantlab/cfx/models.py`, `sdk/quantlab/sqx/project_builder.py`, `sdk/quantlab/knowledge/kb/store.py`, `sdk/quantlab/agents/builder_agent.py`, 10 KB YAMLs, 4 test modules.

### 9.2 Main specs synced

| Path | Action |
|------|--------|
| `openspec/specs/crosschecks-parameter-catalog/spec.md` | MODIFIED — tab count 8 → 9, required-field list completed |
| `openspec/specs/cfx-editor/spec.md` | ADDED — robustness tab typed coverage + dual-output summary |
| `openspec/specs/crosschecks-models/spec.md` | MODIFIED — AutomaticRetest field list gains `what_if`; method round-trip scenarios |
| `openspec/specs/sqx-parameter-kb/spec.md` | MODIFIED — REQ-201 gains `xml_path`/`element_name`; REQ-204 warn-not-block; REQ-208 drift contract |

### 9.3 Engram observation IDs (traceability)

| Artifact | Observation ID | Note |
|----------|---------------|------|
| `sdd/crosschecks-full-parameter-catalog/proposal` | **#1081** | read |
| `sdd/crosschecks-full-parameter-catalog/design` | **#1071** | read |
| `sdd/crosschecks-full-parameter-catalog/tasks` | **#1072** | read |
| `sdd/crosschecks-full-parameter-catalog/apply-progress` | **#1080** | read (status/all-done record) |
| `sdd/crosschecks-full-parameter-catalog/archive-report` | **#1089** | **prior (first) archive, 2026-09-29** — superseded by this report |
| Spec + verify-report | — | No Engram counterpart; OpenSpec files authoritative for a hybrid store |
| Phase 6 bugfix context | **#1093**, **#1094**, **#1090** | cross-tab corruption fix, reopen session, pre-existing-failure diagnostic |
| Sibling change context | **#997**, **#1092** | `typed-crosschecks-models` (archived as `2026-09-29-typed-crosschecks-models/`) |
| Reference archive pattern | **#1087** | `guardian-control-loop` archive-report |

This report upserts the topic `sdd/crosschecks-full-parameter-catalog/archive-report` (revision 2), superseding #1089.

---

## 10. Risks and Follow-Ups

### Open defects (none blocking)

| ID | Risk | Severity | Suggested owner action |
|----|------|----------|----------------------|
| W-1 | False "field does not exist" warning on every idempotent write; 98 confirmed fields. Misleads agents that set a field to the template default. | Medium (diagnosability; no corruption) | One-line fix in `_apply_in_scope`: branch on `re.search(leaf, region.group(0)) is None` instead of comparing the rewritten region. Add a regression test asserting no warning when the value equals the current one. |
| W-2 | `tests/knowledge/test_crosschecks_schema.py` `_EXPECTED_TABS` still holds 8 elements and asserts `issubset` | Low (under-constrains; 9th tab pinned elsewhere) | Widen to 9 and assert equality so the catalog cannot silently lose a tab. |
| W-3 | `invalidate_on_version_drift()` has no production caller; a real 145.x install never demotes anything | Medium (the drift safety net is inert in production) | Add one call site (KB load, or builder-agent startup) and cover the drift → demotion → consumer-warning chain end to end. |
| W-4 | Summary `text` single-line clause has no regression guard | Low (behavior verified correct) | One `assert "\n" not in summary["text"]`. |
| §7 | `enabled_tabs` lists `WalkForwardMatrix` / `OptProfileSysParamPermutation` by element presence, not `use` value | Low (2 of 9 tabs) | Either store `use` on those two models or document the imprecision. |

### Process risks recorded

- **This is the second archive of one change.** The reopen-after-archive pattern worked, but it left the first archive's `tasks.md` snapshot (29 checkboxes) out of step with the final 40, and it is the reason the main spec arrived pre-synced. Worth a deliberate "reopen or amend?" decision up front next time rather than moving folders in both directions.
- **`tests/knowledge/test_crosschecks_schema.py` hardcodes absolute paths**, including `/home/ogzuz/Proyectos/QuantLab AI`. The module will fail outright in CI, in a container, or on any other checkout path. The sibling `tests/phase4/test_project_builder.py` derives the same artifacts correctly via `Path(__file__).resolve().parents[2]`. Out of archive scope (test code), but it will bite CI.
- **One assertion is an unfalsifiable disjunction** (`tests/phase4/test_project_builder.py:1326`): `assert "unchanged" in caplog.text or "ProfitOptPct" not in caplog.text`. If nothing is logged the right disjunct is trivially true, so the test passes without proving any log was emitted. The `xml == template_build_xml` half still carries real value; the log half should become `assert "so_use" in caplog.text` like its sibling at L1332.
- **Working tree is dirty and concurrently modified.** At archive time `git status` showed modifications across SDK modules, specs and tests, plus untracked installer assets, and `openspec/changes/orchestrated-subagent-wiring/` showed as deleted. None were touched by this archive.

### Deferred API decisions (unchanged from `tasks.md` / `design.md`)

1. Typed list/dict shape for the 43 WhatIf per-method toggles and for `WalkForwardMatrix` acceptance `Condition` lists.
2. Whether `OptProfileSysParamPermutation` scalars (`ProfitOptPct`, `AvgProfit`) get typed models or stay `raw_xml`.
3. Confirm WhatIf method parameter names against SQX 145.x evidence before locking the schema.
4. Deprecate `wf_acceptance_min_conditions` / `wf_acceptance_min_markets` once no caller sets them.
5. PF minimums are reachable only through `CrossChecksConfig`, never `BuildConfig` — document this for API consumers.

---

## 11. Mechanical Copy Contract

No artifact was copied or moved by this archive. Per explicit orchestrator instruction, the change folder **was not** moved to `openspec/changes/archive/YYYY-MM-DD-crosschecks-full-parameter-catalog/`; that move is the orchestrator's to perform with user consent. The specs sync in §5 was performed with targeted edits to requirement text, not by reproducing file content, so no `diff -r` readback applies to it — **except** the catalog capability spec, which was refreshed by mechanical copy (`cp` to a temp file, `diff -r` readback, then `mv`), per the Mechanical Copy Contract.

Verbatim readback for that copy, run twice (staged copy, then final destination):

```text
$ diff -r openspec/changes/crosschecks-full-parameter-catalog/specs/crosschecks-parameter-catalog/spec.md \
         openspec/specs/crosschecks-parameter-catalog/.spec.md.XXXXXX
(empty diff — byte-identical)

$ diff -r openspec/changes/crosschecks-full-parameter-catalog/specs/crosschecks-parameter-catalog/spec.md \
         openspec/specs/crosschecks-parameter-catalog/spec.md
(empty diff — byte-identical)

$ sha256sum <both>
0440fcb29c2a5b442e721a6dbc75fa203aefffb2c5077f0f3eaf23a6d59ed789  .../specs/crosschecks-parameter-catalog/spec.md
0440fcb29c2a5b442e721a6dbc75fa203aefffb2c5077f0f3eaf23a6d59ed789  openspec/specs/crosschecks-parameter-catalog/spec.md
```

The pre-correction hash of both files was `sha256:2c7485554ca43f8fb1265517389d02b89758ab768eba659a889a9cf978a2c655`; it changed because of the authorized 8 → 9 tab correction. The other three synced specs (`cfx-editor`, `crosschecks-models`, `sqx-parameter-kb`) were edited in place as MODIFIED/ADDED requirement blocks, so no byte-copy and no `diff -r` readback applies to them.


## 12. SDD Cycle Complete

The change has been fully planned, implemented, verified, and archived. The main specs now reflect the shipped behavior, including the corrected 9-tab completeness statement, the `needs_review` warn-not-block semantics, and the KB schema's XML-traceability fields.
