# Tasks: KB Re-verification Pipeline

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 390–470 |
| 400-line budget risk | Medium (per-slice Low) |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 Finding 0 → PR 2 pure module → PR 3 store → PR 4 CLI |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

**Base (HARD):** every unit cuts from `feat/crosschecks-p6-w3-drift-hook` @ `ebe0bbb`, never `wip/migration-checkpoint`. Task 1.1 is a blocking gate.

### Suggested Work Units

| Unit | Goal | PR | Focused test | Runtime harness | Rollback boundary |
|------|------|----|--------------|-----------------|-------------------|
| 1 | Finding 0: anchors survive store writes | 1 | `pytest -q tests/knowledge/test_kb_reverify.py -k anchors` | N/A — pydantic field declaration, no runtime boundary | Revert `kb/models.py` + its 1 test |
| 2 | Pure `kb/reverify.py` loader + 4-outcome `classify` | 2 | `pytest -q tests/knowledge/test_kb_reverify.py -k "load or verdict or classify"` | `python3 -c "from quantlab.knowledge.kb.reverify import load_evidence; print(load_evidence('sdk/quantlab/sqx/templates/default-project.sqx-template'))"` → `CrossChecks` found | Delete `reverify.py` + tests; store/CLI untouched |
| 3 | `KbStore.reverify_against_build` wrapper | 3 | `pytest -q tests/knowledge/test_kb_reverify.py -k store` | N/A — no surface until PR 4; covered store-level on a `tmp_path` lake | Revert the one wrapper method |
| 4 | `sqx kb reverify` subcommand + suite | 4 | `pytest -q tests/knowledge/` | `SQX_FORCE_MOCK=1 python3 -m quantlab.cli sqx kb reverify --evidence sdk/quantlab/sqx/templates/default-project.sqx-template --tab "Cross checks"` → counts, exit 0; then `--evidence /nope` → exit 3 | Revert handler + subparser |

Threat matrix N/A per design (no shell/subprocess/VCS). RED-first pairs below.
Verified fixture facts: template holds both `Build-Task1.xml` + `config.xml`; `CrossChecks/SequentialOptimization` does not resolve in it (real `field_absent`); `docs/…SQX Builder Config.md#Cross checks` is the real doc gap.

## Phase 1: Pre-apply gate (PR 1)

- [x] 1.1 BLOCKING: cut the apply worktree from `feat/crosschecks-p6-w3-drift-hook` @ `ebe0bbb`. Confirm `invalidate_on_version_drift`, `test_crosschecks_schema.py`, the tracked template. AC: baseline `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/knowledge/` green pre-edit. Deps: none. Rollback: drop worktree.
  - Done: worktree `/home/ogzuz/Proyectos/quantlab-worktrees/crosschecks-p7-reverify` on `feat/crosschecks-p7-reverify-model` @ `ebe0bbb`. Gate assets present: `invalidate_on_version_drift` (`store.py:294`), `tests/knowledge/test_crosschecks_schema.py`, `sdk/quantlab/sqx/templates/default-project.sqx-template`, `_CROSSCHECK_FIELD_SPECS` (`sqx/project_builder.py`).
  - **AC deviation (pre-existing, NOT introduced here):** baseline is `1 failed, 90 passed`, not green. `test_evidence_refs_point_to_existing_files` fails because 9 of 10 lake YAMLs carry `evidence_ref: assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx`, a path that exists nowhere on this machine (real artifact is `user/projects/sqx_4fdea2e7519c/`). Undeclared finding; out of PR 1 scope (would rewrite 9 live YAMLs).
  - **Run note:** the worktree must be tested with `PYTHONPATH=<worktree>/sdk`; the shared `.venv` has `quantlab` installed editable against the main checkout, so a bare run imports the wrong tree.

## Phase 2: Finding 0 — `KbParameter` anchors (PR 1 · D1/D2 · REQ-201 scenario 3)

- [x] 2.1 RED `test_kb_reverify.py::test_xml_anchors_survive_a_verify_write`: seed a `Cross checks` entry with both anchors, call `KbStore.verify()`, reload YAML, assert unchanged. Must fail today (`extra="ignore"` + `model_dump(exclude_none=True)`). Deps: 1.1.
  - RED evidence: `tests/knowledge/test_kb_reverify.py` written first; pre-fix run = `4 failed, 1 passed`. The 4 failures are the real defect (verify write strips both keys, drift demotion strips both, fields absent from `model_fields`, `to_yaml` drops them). The 5th test is the D2 `extra="allow"` guard and passes before and after by design.
  - Fixture follows the real catalog shape (`CrossChecks/WhatIf` / `WhatIf` from `Cross checks/What If simulations.yaml`); the YAML is written as raw text on purpose, because the defect is a *load* defect.
- [x] 2.2 GREEN `sdk/quantlab/knowledge/kb/models.py` after `evidence_ref` (`:97`): add `xml_path: str | None = None`, `element_name: str | None = None` — explicit fields, **not** `extra="allow"`. AC: 2.1 green; `to_yaml` deterministic.
  - Done at commit `95fe083`. No `ConfigDict` added; `to_yaml` stays `model_dump(exclude_none=True)` — the declared fields are what keep the keys on write. Module + class docstrings updated `22 fields` → `24`; the same stale count in `sdk/tests/test_kb.py` docstrings updated for truthfulness. GREEN: `5 passed` focused; `tests/knowledge/` + `sdk/tests/test_kb.py` = `127 passed, 1 failed` (the pre-existing 1.1 failure, unchanged, no new failures).

## Phase 3: Pure `reverify.py` (PR 2 · D3 · kb-reverification scenarios 1–7)

- [x] 3.1 RED `test_load_prefers_build_task1_over_config_xml`, `..._reports_unreadable_for_missing_truncated_and_non_archive_paths`, `..._tracked_template_loads_without_install_assets`; `classify`: `..._positive_resolution_is_verified`, `..._absent_element_is_terminal`, `..._documentation_anchor_is_not_xml_backed`, `..._mixed_population_yields_a_verdict_per_entry`. Deps: 2.2.
  - RED evidence (2 cycles): RED#1 = `ModuleNotFoundError: No module named 'quantlab.knowledge.kb.reverify'` (collection error, module absent). GREEN#1 = `25 passed` (element_name deliberately unused). RED#2 = `1 failed, 26 passed` on `test_mismatched_element_name_does_not_promote` only. GREEN#2 = `27 passed`.
- [x] 3.2 GREEN create `sdk/quantlab/knowledge/kb/reverify.py`: `load_evidence()` (`zipfile` → `Build-Task1.xml` else `config.xml` → `ET.fromstring` → `.//CrossChecks`), `Evidence`, `classify()`, `ReverifyReport`, unknown-bucket guard. **No store imports.** Walker lifted from `test_crosschecks_schema.py:142-190`.
  - Done at commit `3108b25` (branch `feat/crosschecks-p8-reverify-module`, stacked on `95fe083`). 289 lines / 142 of them code; no store or CLI import (verified). `load_evidence` RAISES `EvidenceUnreadableError` instead of returning `crosschecks | None` (design's sketch) so `evidence_unreadable` can never be computed against half-parsed evidence; that also makes `Verdict.EVIDENCE_UNREADABLE` run-level and never returned by `classify`.
- [x] 3.3 GREEN discriminator: XML-anchored iff non-empty, no `#`, not `.md`, `split("/")[0] == "CrossChecks"`. Never read `status`. AC: 3.1 green, no lake needed.
  - GREEN: `tests/knowledge/` → `1 failed, 121 passed` (the pre-existing 1.1 failure, unchanged). `sdk/tests/test_kb.py` → `32 passed`. Runtime harness → `member: Build-Task1.xml | crosschecks: CrossChecks | tabs: 8`. `mypy --strict` clean on the new module.
  - **Two interpretations to flag for the reviewer:** (a) `element_name` is a required parameter of `classify` but design's table never uses it — implemented as a leaf-tag check (resolved leaf tag ≠ `element_name` → `field_absent`, fail-closed, never promotes); all 9 real XML-anchored entries have `element_name` == last path segment. (b) `require_known_bucket(sqx_version, known)` is pure: the store supplies the lake's buckets in PR 3, the module owns the refusal rule.
  - **Size note:** 551 authored changed lines vs the 400 review budget. Driven by docstring-heavy pure module + 26 real-data test cases, not scope creep; every item in 3.2/3.3 is present. Orchestrator may re-slice if the budget is hard.

## Phase 4: Store wrapper (PR 3 · D4/D5 · scenarios 8–10 · REQ-208 scenarios 2/3/4)

- [x] 4.1 RED `test_dry_run_is_the_default_and_writes_nothing`, `test_promotion_routes_through_the_existing_verify_path` (spy on `verify`), `test_tab_scoping_narrows_the_population`, `test_unknown_version_bucket_is_refused`, `test_idempotent_reverify_is_stable`. Lakes via `tmp_path`. Deps: 3.3.
  - Added as a separate file `tests/knowledge/test_kb_store_reverify.py` (17 cases, 12 test functions) rather than extending `test_kb_reverify.py`: the wrapper slice owns its own lake fixture and its own RED/GREEN cycle, so a revert of PR 3 drops one file cleanly.
  - RED evidence: `18 failed` on first execution. Exactly three failure modes, all "production code absent": `AttributeError: 'KbStore' object has no attribute 'reverify_against_build'`, `AttributeError: 'EntryVerdict' object has no attribute 'reason'`, `TypeError: ReverifyReport.__init__() got an unexpected keyword argument 'evidence_ok'`. No fixture bugs. GREEN: `18 passed`.
  - **Non-vacuity proved by mutation, not by assertion count.** 8 mutants applied one at a time against `tests/knowledge/` (baseline `1 failed, 139 passed`); every one was killed: D5 status filter (→4 failed), dry-run guard removed (→2), `evidence_ref` losing `#xml_path` (→2), bucket guard removed (→2), `_version_buckets` ignoring the lake (→2), `counts` dropping run-level unreadable (→4), `classify` ignoring `element_name` (→2), unreadable raised instead of reported (→3). Zero survivors.
- [x] 4.2 GREEN add `KbStore.reverify_against_build(evidence, *, tab=None, sqx_version=None, apply=False)` after `store.py:348`: population from unfiltered `list(tab=, sqx_version=)`; promote only via `verify(tab, name, f"{artifact}#{xml_path}")`; per-entry verdicts under both `apply` values; refuse unknown bucket.
  - Done at commit `770d552` on branch `feat/crosschecks-p9-reverify-store` (stacked on `3108b25`). 427 authored changed lines.
  - **Deviation 1 — `reverify.py` gained the run-level report contract** (28 added lines): `ReverifyReport.evidence_ok` + `unreadable_reason` + `ReverifyReport.unreadable()`, and `counts` now reports `evidence_unreadable: 1` on an unreadable run instead of `0`. Without this the wrapper could not satisfy the spec's "reported as unreadable" without either raising (forbidden — fail-open) or inventing a store-local report type. `EntryVerdict.reason` added for the per-entry reason the report contract requires.
  - **Deviation 2 — the store does NOT call `is_xml_anchored` itself.** The assignment said to use it, then `classify`. `classify` already applies it internally as its first branch, so calling it again in the store would create two sources of truth for the same predicate — exactly the divergence D3 exists to prevent. The *behaviour* is identical (None and `.md#` anchors are `not_xml_backed` and skipped, proven by two dedicated tests); only the redundant call is omitted.
  - `evidence_ref` uses `f"{report.artifact}#{entry.xml_path}"` where `artifact` is `str(loaded.path)` — D6's `path#anchor` form, which `validate_seed` already strips.
  - **Runtime harness (tasks.md calls Unit 3 N/A; run anyway, stronger evidence).** Dry-run against the REAL 82-entry worktree catalog, SHA-256 of every YAML before/after: `tab="Cross checks"` → `8 verified / 1 field_absent / 1 not_xml_backed`, digest `668329cb… → 668329cb…` UNCHANGED. Unscoped → 82 entries, 73 `not_xml_backed`. Apply on a `shutil.copytree` clone after `invalidate_on_version_drift("145.1")` (82/82 demoted): promoted entry `status=verified`, `evidence_ref=…#CrossChecks/WhatIf`, `xml_path`/`element_name` intact (Finding 0 held); `Sequential Optimization` file **byte-identical**; second apply byte-stable. Unreadable → `evidence_ok=False`, `evidence_unreadable: 1`, zero writes. Unknown bucket → refused, `available: 144.2953, _template`.
  - **Two runtime observations (pre-existing, NOT introduced here):** (a) `invalidate_on_version_drift` clears `status` but leaves the stale `evidence_ref` on a demoted entry, so a `needs_review` entry still advertises old evidence; (b) `_version_buckets` counts the lake's `_template/` directory as a known bucket.
  - Focused: `pytest -q tests/knowledge/test_kb_store_reverify.py` → `17 passed`. Slice: `tests/knowledge/ + sdk/tests/test_kb.py` → `1 failed, 170 passed` (only the pre-existing 1.1 failure). `mypy --strict` → the same 2 pre-existing `store.py` errors and no new ones; `ruff check`/`format` clean on the new test file, and zero new findings on the two edited modules.

## Phase 5: CLI (PR 4 · D6 · scenarios 11–12)

- [x] 5.1 RED `test_dry_run_prints_counts_and_exits_zero`, `test_unreadable_evidence_exits_three_without_writing`: handler called directly under `SQX_FORCE_MOCK=1`, assert YAML bytes unchanged. Deps: 4.2.
  - New file `tests/knowledge/test_kb_reverify_cli.py` (225 lines, 9 test functions / 9 cases) — kept separate from PR 3's store file so a revert of PR 4 drops one file cleanly. Argv is parsed through the **real** `build_parser()`, so the tests also pin the subparser wiring and the dispatch path, not just the handler.
  - RED evidence: `9 failed, 0 passed` on first execution. Every failure is one mode — argparse rejects the subcommand that does not exist yet: `argument kb_cmd: invalid choice: 'reverify' (choose from list, get, seed, seed-ohlc, validate, verify, status, table)` / `SystemExit: 2`. No fixture bugs.
  - **Vacuous-green avoided deliberately.** The first draft asserted only `main(["sqx","kb","reverify"]) == 2`, which *passed at RED* because argparse rejects an unknown subcommand with the same code — a green that proved nothing. Tightened to also assert stderr names `--evidence`, so the test now distinguishes "the flag is required" from "the subcommand does not exist". Flagged because that same mistake would silently survive a future refactor.
  - Two later failures were **test bugs, not code bugs**, and were fixed in the test: the help assertion looked for the literal `unreadable` (the help text says "could not be read") and for a lowercase `dry-run` (argparse text is `Dry-run`). The help assertion now collapses argparse's wrapping (`" ".join(out.split())`) and matches case-insensitively, so it tests the contract rather than the terminal width.
- [x] 5.2 GREEN `cmd_kb_reverify` mirroring `cmd_kb_verify` (`sq_commands.py:305-324`) + subparser after `:533-546`; reuse `_kb_store`/`_add_common`. Dry-run default; per-outcome counts on stdout (D7); unreadable → exit **3**, zero writes, dispatch completes.
  - Done at commit `fa35754` on branch `feat/crosschecks-p10-reverify-cli` (stacked on `770d552`). 316 authored changed lines (93 in `sq_commands.py`, 223 in the new test file) — inside the 400 budget for the first time in this chain (PR 2 = 551, PR 3 = 427).
  - The handler only renders: `store.reverify_against_build(...)` decides and writes, the handler prints and maps `evidence_ok` to an exit code. It adds no decision and no serializer.
  - **Stdout renders per-entry verdicts, not just counts.** D7 asked for counts; the orchestrator asked for per-entry verdicts; and the spec's Non-Goals defer the report file, which leaves stdout as the *only* place a per-entry verdict can land. Counts alone would silently drop the report the whole pipeline exists to produce, so both are printed: a `print_table` of `tab/name/verdict/reason`, then the four counts, then a footer.
  - Exit code is a named constant `EXIT_EVIDENCE_UNREADABLE = 3` rather than a bare literal, so D6's "3 ≠ argparse's 2" is greppable and the module docstring can point at it.
  - `--tab` uses `choices=KB_TABS`, matching the sibling `list` subcommand; `--evidence` is `required=True`, which is what reserves exit 2 for usage errors.
  - **Non-vacuity by mutation: 8 mutants, 8 killed** (baseline `9 passed`). Exit 3→1 (→2 failed); dry-run footer blanked (→1); footer inverted (→1); `tab=args.tab`→`None` (→1); unreadable branch deleted so it returns 0 (→2); bucket refusal turned into a bare `return 0` (→1); per-entry table deleted (→2); `apply=args.apply`→`False` (→1). Zero survivors.
  - **Lint:** `ruff check` + `ruff format --check` clean on the new test file. On `sq_commands.py` the change adds exactly **one** finding — `BLE001` for the defensive `except Exception` — which is the same pattern the nine neighbouring `cmd_kb_*` handlers already use; kept for consistency with `cmd_kb_verify`, which the design requires it to mirror. `mypy --strict` finding set on `sq_commands.py` is byte-identical before and after (21 findings, all pre-existing). The new test file's only remaining finding is `Returning Any` from `yaml.safe_dump`, identical to PR 3's `_yaml` helper on purpose, so a reviewer diffing the two files sees only what differs.
  - **Runtime harness (6 scenarios, all against the real 82-entry worktree lake):** dry-run `--tab "Cross checks"` → `verified 8, field_absent 1, not_xml_backed 1, evidence_unreadable 0`, exit 0, lake SHA-256 digest unchanged — matching PR 3's recorded ground truth exactly, which is an independent cross-PR confirmation. Unreadable `/nope.cfx` → exit **3**, `evidence_unreadable: 1`, zero writes. Unknown bucket `999.1` → exit 1. Missing `--evidence` → exit 2. `--apply` against a `/tmp` `copytree` clone → exactly **8** files changed, each gaining `evidence_ref: <artifact>#CrossChecks/…` while `xml_path`/`element_name` survived intact (Finding 0 held end-to-end through the CLI); `Sequential Optimization` (`field_absent`) absent from the diff; second apply byte-stable. The live lake was never written — digest-verified before and after every scenario.
  - Rollback boundary: `git revert fa35754` on this branch only. No live lake YAML is touched by any test or harness run (all writes went to `tmp_path` or a `/tmp` clone), so no anchor re-population is needed.

## Phase 6: Suite and impact (PR 4)

- [x] 6.1 `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/knowledge/` — `test_crosschecks_schema.py` stays green (the Finding 0 tripwire).
  - `tests/knowledge/` → **`1 failed, 147 passed`**; `sdk/tests/test_kb.py` → **`32 passed`**; combined slice → **`1 failed, 179 passed`**. The slice grew 170 → 179 = exactly the 9 new CLI tests. The single failure is the pre-existing `test_evidence_refs_point_to_existing_files` recorded in task 1.1, unchanged, and `test_crosschecks_schema.py`'s other cases (including the Finding 0 tripwire) stayed green.
  - Pre-existing root cause, documented and NOT fixed: 9 of 10 lake YAMLs cite `assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx`, which exists nowhere on this machine (the real artifact lives under `user/projects/sqx_4fdea2e7519c/`). Fixing it means rewriting 9 live YAMLs — out of scope for this change and a decision for the maintainer.
- [!] 6.2 ~~`SQX_FORCE_MOCK=1 python3 -m pytest -q`~~ **NOT RUNNABLE FROM THIS WORKTREE — blocked by the stack base, not by this change.** Superseded by the partial verification below.
  - **Root cause is broader than the orchestrator's stated `gatekeeper.py`.** A verbatim full run dies at *collection*, not execution. The stack base `ebe0bbb` is missing **three** modules that `main`/`wip/migration-checkpoint` do have:
    | Missing module | Test modules it breaks | Present on `main`/`wip`? |
    |---|---|---|
    | `quantlab.campaign.gatekeeper` | 3 | yes |
    | `quantlab.analysis.indicators` | 9 | yes |
    | `quantlab.analysis.frame` | 3 | yes |
    | `sync_common` (harness helper, not a package) | 1 | yes |
  - Verified precisely: `git merge-base --is-ancestor d060617 HEAD` → **false**. `gatekeeper.py` is introduced by `d060617 "chore: checkpoint in-flight work before machine migration"`, which reaches `main` and `wip/migration-checkpoint` but is **not an ancestor of the stack base**. So "the base predates the analysis + gatekeeper work" is the accurate diagnosis; blaming `gatekeeper.py` alone understates it by 12 test modules.
  - **`gatekeeper.py` was NOT committed and the missing modules were NOT grafted**, per the orchestrator's user-approved partial-verification decision.
  - **Partial verification actually run (stronger than planned).** Rather than stopping at `tests/knowledge/`, the 19 collection-erroring modules were programmatically discovered (`--collect-only`, iteratively extending `--ignore` until collection is clean) and excluded, then the rest of the suite was run **twice** — once at `770d552` with PR 4 stashed, once with it applied:
    | | Collected | Passed | Failed | Skipped | Errors |
    |---|---|---|---|---|---|
    | baseline `770d552` | 3668 | 3520 | 125 | 12 | 4 |
    | with PR 4 (`fa35754`) | 3668 | **3529** | 125 | 12 | 4 |
    | delta | 0 | **+9** (my tests) | **0** | 0 | **0** |
    - The sorted FAILED+ERROR node-id sets are **identical** except for one line: an unrelated `quantlab.evolution.orchestrator` log line embedding a run timestamp (`cycle-0001-1790972700` vs `cycle-0001-1790972190`). So: **zero regressions across 3668 tests**, and all 125 failures + 4 errors are pre-existing at the stack base, untouched by this change.
    - **Honest scope of that claim:** 19 modules (the campaign flow/phase-runner/delegation, the analysis-agent, contract-frame, pipeline-stage and guardian-agent modules) are *unverified by this change* — not passing, just unrunnable. They touch no KB code, but that is an argument, not a measurement.
    - Side observation: the broad run creates two untracked dirs (`knowledge/structured/jforex-kb/`, `knowledge/structured/sqx-kb/_template/docs/`, both just `.gitkeep` skeletons) — some suite test initializes a store at the default `knowledge` root. Pre-existing, not from this slice; removed to keep the worktree clean, and the isolated `tests/knowledge/` re-run confirms this slice does not create them.
- [x] 6.3 Log in `apply-progress.md`: 12/12 `kb-reverification` and 7/7 `sqx-parameter-kb` delta scenarios pinned by name (3 pre-existing unchanged); `knowledge/index.yaml` sha256 desyncs on promotion, no staleness gate — deferred per design.
  - Cumulative apply-progress written to `openspec/changes/kb-reverification-pipeline/apply-progress.md` (new) and mirrored to the Engram topic `sdd/kb-reverification-pipeline/apply-progress`.
  - **12/12 `kb-reverification` scenarios pinned by test name**, all green: member preference → `test_load_prefers_build_task1_over_config_xml`; unreadable evidence → `test_load_reports_unreadable_for_missing_truncated_and_non_archive_paths` + CLI `test_unreadable_evidence_exits_three_without_writing`; tracked fixture → `test_load_tracked_template_loads_without_install_assets`; positive promotion → `test_positive_resolution_is_verified` + `test_promotion_routes_through_the_existing_verify_path` + CLI `test_apply_promotes_only_the_resolving_entry`; absent terminal → `test_absent_element_is_terminal` + `test_field_absent_is_terminal_and_is_left_untouched`; doc anchor → `test_documentation_anchor_is_not_xml_backed_without_probing` + `test_an_already_verified_doc_gap_is_still_not_promoted`; mixed population → `test_mixed_population_yields_a_verdict_per_entry`; dry-run default → `test_dry_run_is_the_default_and_writes_nothing` + CLI `test_dry_run_prints_counts_and_exits_zero`; single write path → `test_promotion_routes_through_the_existing_verify_path` (spies on `KbStore.verify`); tab scoping → `test_tab_scoping_narrows_the_population` + CLI `test_tab_scoping_narrows_the_reported_population`; dry-run reports → CLI `test_dry_run_prints_counts_and_exits_zero` + `test_dry_run_renders_every_entry_and_its_verdict`; unreadable exits distinctly → CLI `test_unreadable_evidence_exits_three_without_writing` (parametrized over `--apply`).
  - **7/7 `sqx-parameter-kb` delta scenarios**: 3 pre-existing and unchanged (valid file loads, missing required field, drift invalidates KB — owned by `sdk/tests/test_kb.py` and the drift hook); 4 added by this change: XML anchors survive a store write → `test_xml_anchors_survive_a_verify_write` + `test_xml_anchors_survive_a_drift_demotion` + `test_wrapper_write_preserves_the_xml_anchor_pair`; XML evidence re-promotes → PR 3 + PR 4 (above); absent field stays `needs_review` → PR 2 + PR 3; doc gap never promoted → PR 2 + PR 3.
  - `knowledge/index.yaml` sha256 desyncs on promotion and there is no staleness gate — deferred per design; accepted only because this chain ships dry-run-first, and `--apply` remains operator-initiated.

### Spec archive impact (recorded for sdd-archive — NOT applied here)

- `openspec/specs/sqx-parameter-kb/spec.md` is **not** edited by this change. The REQ-201 delta (declared `xml_path`/`element_name` fields, preserved by every write) and the REQ-208 delta (evidence-first re-verification, structural-shape discrimination, terminal absence) merge into it at **sdd-archive**, once `verify-report.md` exists. Nothing in Phases 1–5 needs the main spec, and editing it now would put an unverified claim in the archived spec.
- No new capability spec is created: the whole pipeline lives under the existing `kb-reverification` delta spec.

