# Apply Progress: KB Re-verification Pipeline

Cumulative record across all four chained PR slices (stacked-to-main). Per-task detail
lives in `tasks.md`; the same artifact is mirrored to the Engram topic
`sdd/kb-reverification-pipeline/apply-progress`.

## Slice Ledger

| PR | Branch | Commit | Scope | Authored lines |
|---|---|---|---|---|
| 1 | `feat/crosschecks-p7-reverify-model` | `95fe083` | Finding 0: `xml_path`/`element_name` survive every store write | 79 |
| 2 | `feat/crosschecks-p8-reverify-module` | `3108b25` | Pure `kb/reverify.py`: evidence loading, 4-outcome `classify` | 551 |
| 3 | `feat/crosschecks-p9-reverify-store` | `770d552` | Thin `KbStore.reverify_against_build` wrapper | 427 |
| 4 | `feat/crosschecks-p10-reverify-cli` | `fa35754` | `sqx kb reverify` subcommand + suite verification | **316** |

Base for every slice: `feat/crosschecks-p6-w3-drift-hook` @ `ebe0bbb`. PR 4 is the first
slice inside the 400-line review budget.

## TDD Cycle Evidence (Strict TDD — active for all slices)

| Slice | RED | GREEN | Non-vacuity proof |
|---|---|---|---|
| PR 1 | `4 failed, 1 passed` — verify write strips both anchors, drift demotion strips both, fields absent from `model_fields`, `to_yaml` drops them | `5 passed` | The 5th test is the D2 `extra="allow"` guard: passes before and after by design |
| PR 2 | RED#1 `ModuleNotFoundError: quantlab.knowledge.kb.reverify` (collection error) · RED#2 `1 failed, 26 passed` on `test_mismatched_element_name_does_not_promote` | `27 passed` | 27 cases over 9 real XML-anchored entries + all 4 outcomes |
| PR 3 | `18 failed`, exactly 3 "code absent" modes (no `reverify_against_build`, no `EntryVerdict.reason`, no `ReverifyReport.evidence_ok`) | `18 passed` | **8 mutants, 8 killed** (see below) |
| PR 4 | `9 failed` — one mode: `argument kb_cmd: invalid choice: 'reverify'` | `9 passed` | **8 mutants, 8 killed** |

Mutants are the real proof of non-vacuity in this chain, not assertion counts.

* **PR 3 (8 killed):** D5 status filter (→4), dry-run guard removed (→2), `evidence_ref` losing
  `#xml_path` (→2), bucket guard removed (→2), `_version_buckets` ignoring the lake (→2), `counts`
  dropping run-level unreadable (→4), `classify` ignoring `element_name` (→2), unreadable raised
  instead of reported (→3).
* **PR 4 (8 killed):** exit 3→1 (→2), dry-run footer blanked (→1), footer inverted (→1),
  `tab=args.tab`→`None` (→1), unreadable branch deleted so it returns 0 (→2), bucket refusal turned
  into a bare `return 0` (→1), per-entry table deleted (→2), `apply=args.apply`→`False` (→1).

## Verification Status

| Task | Result |
|---|---|
| 6.1 `tests/knowledge/` | `1 failed, 147 passed` |
| 6.1 `sdk/tests/test_kb.py` | `32 passed` |
| Combined slice | `1 failed, 179 passed` (170 at PR 3 + 9 new) |
| 6.2 full suite | **Blocked by the stack base, not by this change.** 19 test modules cannot be collected because `ebe0bbb` lacks `quantlab.campaign.gatekeeper`, `quantlab.analysis.indicators`, and `quantlab.analysis.frame` (plus the `sync_common` helper). Introduced by `d060617`, which reaches `main`/`wip` but is **not an ancestor of the stack base**. |
| 6.2 partial (what was actually run) | 3668 tests, run twice — stashed and applied. Baseline `3520 passed / 125 failed / 4 errors`; with PR 4 `3529 passed / 125 failed / 4 errors`. The sorted FAILED+ERROR node-id sets are **identical** except one unrelated log line carrying a run timestamp. **Zero regressions; the 19 uncollectable modules remain unverified.** |

## Pre-existing Defects (documented, NOT fixed here)

1. **`test_evidence_refs_point_to_existing_files` fails** (recorded in task 1.1). 9 of 10 lake YAMLs
   cite `assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx`, a path that exists
   nowhere on this machine; the real artifact is under `user/projects/sqx_4fdea2e7519c/`. Fixing it
   means rewriting 9 live YAMLs — a maintainer decision, outside this chain.
2. **`invalidate_on_version_drift` clears `status` but leaves the stale `evidence_ref`**, so a demoted
   `needs_review` entry still advertises old evidence. Found at runtime in PR 3.
3. **`_version_buckets` counts the lake's `_template/` directory as a known bucket.** Harmless —
   nobody types that bucket.
4. **CI cannot run `ruff`/`mypy`.** `ci.yml` installs only `pip install -e "sdk[dev]"`, whose extra
   has neither tool. Both were run locally and compared against the HEAD baseline instead.
5. **The broad suite creates two untracked lake skeletons** (`knowledge/structured/jforex-kb/`,
   `knowledge/structured/sqx-kb/_template/docs/`) because some test initializes a store at the
   default `knowledge` root.

## Scenario Coverage

12/12 `kb-reverification` and 7/7 `sqx-parameter-kb` delta scenarios pinned by test name — see
tasks.md 6.3 for the full name-by-name mapping (3 of the 7 delta scenarios are pre-existing and
unchanged).

## Deferred (per design)

Report file under `structured/sqx-version/{old}→{new}/` (stdout is the only report surface until
then); artifact auto-discovery; point-version detection; `DriftWorkflow.run()` wiring;
`index.yaml` rebuild; reviewer-table gating; `xml_path` beyond the 10 current entries;
`validate_seed` band revisited before broad promotion.

## Next

`sdd-verify` for `kb-reverification-pipeline`. The verify phase must read task 6.2 as
**partial**, not full: 19 modules are unverified, and the `gatekeeper.py` reason alone is an
incomplete diagnosis.
