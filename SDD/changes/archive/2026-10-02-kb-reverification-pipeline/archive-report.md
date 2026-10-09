# Archive Report: kb-reverification-pipeline

**Change**: `kb-reverification-pipeline`
**Mode**: openspec
**Archived**: 2026-10-02
**Verified revision**: `097acd8` (tree `fdd90694`) on `validate/stacked-main`
**Delivery state**: 11 stacked PRs **open**, not merged — `#17`–`#27`, all base=`main`, all `MERGEABLE`/`CLEAN`
**Archive status**: **success with recorded warnings** — 0 CRITICAL; 6 verify WARNINGs carried forward, none blocking

---

## Intent

`KbParameter` (`sdk/quantlab/knowledge/kb/models.py:64-97`) declared neither `xml_path` nor
`element_name`. Pydantic's default `extra="ignore"` plus `to_yaml`'s
`model_dump(exclude_none=True)` stripped both on **every** store write — `verify`,
`invalidate`, and version-drift demotion all route through `_load_file` → `_save_file`.
The REQ-208 drift hook (PR #22) therefore deleted the XML anchors on the 10 `Cross checks`
YAMLs and failed `tests/knowledge/test_crosschecks_schema.py:96-110` against a real lake.
That was the headline (Finding 0); the pipeline gap behind it was that nothing re-verified
after drift — 82 entries, only a manual `sqx kb verify`.

Both closed: the anchors are now declared schema fields that survive every write, and an
operator-driven pipeline re-verifies the KB against operator-supplied build XML.

## What Shipped

### This change's own slices — PRs #23–#26

| PR | Branch | Commit | Scope | Authored lines |
|----|--------|--------|-------|----------------|
| #23 | `feat/crosschecks-p7-reverify-model` | `c59c41e` | Finding 0: `xml_path`/`element_name` survive every store write | 143 |
| #24 | `feat/crosschecks-p8-reverify-module` | `9cf2553` | Pure `kb/reverify.py`: evidence loader, XML walker, four-outcome `classify` | 543 |
| #25 | `feat/crosschecks-p9-reverify-store` | `2eb8c16` | Thin `KbStore.reverify_against_build` wrapper | 427 |
| #26 | `feat/crosschecks-p10-reverify-cli` | `6c5b673` | `sqx kb reverify` subcommand | 316 |
| #26 (tip) | — | `097acd8` | `fix(tests)`: resolve crosschecks schema test paths from repo root | 16 |

`5a355b1..097acd8` touches exactly **9 files** — 4 production, 3 new test files,
`sdk/tests/test_kb.py` (docstring field count), `test_crosschecks_schema.py` (path
resolution). Ancestry linear, **0 merge commits**, aggregate **+1422/−15**.

### The delivery stack — PRs #17–#27

The launch prompt records the vehicle as PRs `#17`–`#26` plus `#27`. Read precisely against
`gh`, the stack splits three ways, and the distinction matters for who reverts what:

| Range | Content | Owner |
|-------|---------|-------|
| `#17`–`#22` | Crosschecks dependency ladder: KB schema test, typed cfx models, tab-scoped builder, leaf-match fix, summary guard, drift hook (`5a355b1`) | **Prior changes**, present as dependency context only |
| `#23`–`#26` | This change — the four slices above | **This change** |
| `#27` (`fix/knowledge-crosschecks-evidence`) | Lake fix: repoint `Cross checks` `evidence_refs` to the tracked template + doc-gap markers on `Sequential Optimization.yaml` (`ec0e44e`, `db763bb`) | This change's verification unblocker |

`gh` confirms `#17`–`#27` all `OPEN`, base=`main`, `mergeable=MERGEABLE`,
`mergeStateStatus=CLEAN`. **Nothing is merged.** PR `#26` currently carries `#17`–`#25`'s
commits plus both lake-fix commits in its history, which is why its cumulative diff
(`+5198/−159`) is far larger than its own slice.

### Rebasing invalidated the apply-phase commit hashes

`apply-progress.md` records the slice commits as `95fe083`, `3108b25`, `770d552`,
`fa35754`. Those were pre-rebase; the ladder was rebased over `d060617`, so the hashes that
exist on origin today are `c59c41e`, `9cf2553`, `2eb8c16`, `6c5b673`. The apply ledger is
archived **verbatim** with its original hashes — a reader must map them through this table,
not treat them as dangling.

## Task Completion

Counted directly from the persisted `tasks.md` checkbox state, not from `apply-progress`
prose: **12 `- [x]`, 0 `- [ ]`, 1 `- [!]`** (task 6.2). No archive-time reconciliation was
performed, and none was authorised.

The Task Completion Gate is satisfied: **zero unchecked implementation tasks.** The single
`[!]` is task 6.2, and it is a stale *claim*, not a stale *checkbox* — see section 1.

## 1. Task 6.2 — stale snapshot, resolved at verify time

`tasks.md` line 97 carries `[!] 6.2 ~~SQX_FORCE_MOCK=1 python3 -m pytest -q~~ **NOT RUNNABLE
FROM THIS WORKTREE — blocked by the stack base, not by this change.**`, and
`apply-progress.md:45` repeats it as "Blocked by the stack base". Both were true when written:
base `ebe0bbb` predated `d060617`, leaving 19 test modules uncollectable.

`verify-report.md:57-61` and the launch prompt supersede both (Final-State Authority: rank 4
snapshots lose to rank 3 explicit final-state facts):

- the ladder rebased over `d060617`, full-suite collection is now **clean** (`0 errors during collection`, was 14);
- the full suite **was** run: **4255 passed, 20 skipped, 1 failed, 4 errors**;
- both non-pass groups are environmental and touch no KB code — 1 failure is
  `ModuleNotFoundError: No module named 'rich'` in `tests/phase4/test_campaign_monitor.py`
  (confirmed absent from the shared venv; the launch prompt adds that it **reproduces on
  `main`**), and 4 errors are `FileNotFoundError` at fixture setup for
  `assets/SQX_144_2953_linux_20260601/user/settings/Configs/DJ CFD H1.cfx` (directory absent
  on this machine).

`tasks.md` and `apply-progress.md` were **not** rewritten. They are the audit trail of what
apply believed at the time; the correction lives here and in `verify-report.md`.

## 2. Specification Sync

| Domain | Action | Detail |
|--------|--------|--------|
| `kb-reverification` | **Created** | No main spec existed (`openspec/specs/kb-reverification/` was absent). Per the precedent of the archived siblings `data-range-parts-and-ranking-filters` and `fix-flat-lane-settings-projection`, a new capability's delta is treated as a **full spec** and copied verbatim. |
| `sqx-parameter-kb` | **Updated** | Two `MODIFIED` requirements merged: REQ-201 and REQ-208. `+35/−1`. |

`openspec/specs/kb-reverification/spec.md` — mechanical shell copy, `diff -r` empty,
sha256-identical to the change's delta:

```
b0f93d13643c98303dcd4b576b3639341be377b5f8b4e887be60f5f757aa5e10  openspec/changes/kb-reverification-pipeline/specs/kb-reverification/spec.md
b0f93d13643c98303dcd4b576b3639341be377b5f8b4e887be60f5f757aa5e10  openspec/specs/kb-reverification/spec.md
```

`openspec/specs/sqx-parameter-kb/spec.md` (sha256 `fc56a744…`, 158 lines) — both merged
requirement blocks verified **byte-identical to their delta blocks** by a block-level diff:

| Requirement | Action | Scenarios |
|-------------|--------|-----------|
| REQ-201 KB Schema | Replaced: field set gains `xml_path`/`element_name`; new normative sentence — declared fields, preserved by `verify`/`invalidate`/drift demotion, a dropping write is a defect | 2 → **3** |
| REQ-208 Version-Invalidation Hook | Replaced: evidence-first re-verification, terminal `field_absent`, structural-shape discrimination, never the `status` string | 1 → **4** |

**Non-destructive, verified**: all 8 requirements survive, REQ-202…REQ-207 are untouched, and
the scenario count moves **14 → 18** by addition only. The git diff shows hunks confined to
the two replaced blocks.

### Merge-sequencing risk — PR #26 edits the same file

PR `#26` carries `openspec/specs/sqx-parameter-kb/spec.md` `+40/−1`: the archive-time merge
of a **different** change, `crosschecks-full-parameter-catalog` (archived 2026-09-30 *inside
that PR branch only* — the directory is absent from this checkout and from `main`). It
modifies the **same two requirements** this change modifies, with different wording for the
same fields: it inserts `xml_path`, `element_name` inline into the REQ-201 field list, while
this change appends them as "plus the optional XML traceability pair".

Both are correct against the baseline they were written against, and `git diff origin/main --
openspec/specs/sqx-parameter-kb/spec.md` is empty here, so this merge is correct against the
actual source of truth. But **whichever lands second must rebase and reconcile REQ-201 and
REQ-208 by hand.** Recorded as follow-up F1. No attempt was made to pre-reconcile PR #26's
variant: it is not in this checkout, and inventing a merge of two unmerged changes is not
archive's mandate.

## Verification Carried Forward

From `verify-report.md` (`verdict: pass_with_warnings`, `critical_findings: 0`,
`blockers: 0`), confirmed unchanged by the launch prompt:

| Measurement | Value |
|-------------|-------|
| Verdict | `pass_with_warnings` — **0 CRITICAL**, 6 WARNING, 4 SUGGESTION |
| Requirements / scenarios | **6/6** requirements, **19/19** scenarios COMPLIANT |
| Declared evidence suite | **133 passed, 1 skipped**, exit 0 |
| Touched slice (`tests/knowledge/` + `sdk/tests/test_kb.py`) | **202 passed, 1 skipped**, exit 0 (was `1 failed, 179 passed`) |
| Full suite | 4255 passed, 20 skipped, 1 failed, 4 errors, **0 collection errors** |
| `mypy --strict` on lines this change added | **0** (704 repo-wide findings across 117 files are pre-existing debt) |
| `reverify.py` (only new production module) | **0** mypy findings, `ruff E4,E7,E9,F` clean |
| New tests | **41 functions / 57 collected cases** across 3 files |
| Non-vacuity | 16 mutants across PR 3 + PR 4, **all killed**; corroborated by the live 0/1/2/3 exit matrix |
| Live runtime harness | 7 scenarios against the real 82-entry lake; lake SHA-256 digest unchanged before and after; `--apply` promoted exactly 8 entries and was byte-stable on repeat |

### Warnings carried into the archive record

1. **Full suite exits 1 on two environmental conditions** (missing `rich` package, missing
   machine-local `DJ CFD H1.cfx`). Neither reachable by code, neither touching KB code. The
   evidence suite and the touched slice are both green.
2. **704 repo-wide `mypy --strict` findings.** Long-standing debt; this change adds zero.
3. **`classify` consults `element_name`, which the design's decision table never uses**
   (`reverify.py:204-205`). Fail-closed (mismatch → `field_absent`, never a promotion) and
   consistent with the spec's intent, but an **unratified extension of the D-table**. All 9
   real XML-anchored entries have `element_name` == last path segment, so current-catalog
   behaviour is unchanged. The verify report explicitly asked for an archive-time note —
   **this is that note** (follow-up F2: ratify or amend D3).
4. **2 of 4 slices exceed the 400-line review budget** (PR 2 = 543, PR 3 = 427; PR 4 = 316
   and PR 1 = 143 are inside it). `auto-chain` / `stacked-to-main` was forecast up front and
   stack linearity is clean. Not a verification blocker, but PR #24 and PR #25 remain
   oversized review surfaces.
5. **`store.py:22` `F401` `typing.Iterable` unused** — confirmed byte-identical at the
   pre-change base `5a355b1`, so pre-existing.
6. **`_version_buckets` counts `sqx-kb/_template/` as a known bucket** (visible as
   `available: 144.2953, _template`). Pre-existing; the rebase changed its *cause* (the two
   `_template/.gitkeep` files are now tracked, introduced by `d060617`), not its existence.

## Deviations from `design.md`

All recorded during apply and re-confirmed by verify; all fail-closed; none regressed.

1. **`element_name` as a resolved-leaf-tag check.** The design's decision table never uses
   it. Implemented fail-closed and pinned by `test_mismatched_element_name_does_not_promote`.
   See warning 3.
2. **The store does not call `is_xml_anchored` before `classify`.** `classify` applies it
   internally as its first branch; calling it twice would create two sources of truth for one
   predicate — exactly the divergence D3 exists to prevent. Behaviour identical, proved by
   two dedicated tests.
3. **`reverify.py` gained the run-level report contract** (`evidence_ok`,
   `unreadable_reason`, `ReverifyReport.unreadable`, `EntryVerdict.reason`, +28 lines). The
   spec requires unreadable evidence be *reported*; the store fails open and cannot raise,
   so a store-local report type would have been invented instead. Necessary and minimal.
4. **D7 extended: stdout carries per-entry verdicts, not only counts.** The design asked for
   counts; the spec's Non-Goals defer the report file, which leaves stdout as the only place
   a per-entry verdict can land. Both are printed.

## Proposal Success Criteria

`proposal.md:72-74` carries three unchecked `- [ ]` success criteria. Those are
proposal-phase artifacts and are archived as written — archive does not rewrite upstream
phase artifacts. For the record, all three are met:

1. *"`xml_path` survives a `verify()` write; schema test green on a real lake"* →
   `test_xml_anchors_survive_a_verify_write`, `test_xml_anchors_survive_a_drift_demotion`;
   `test_crosschecks_schema.py` green after the PR #27 lake fix.
2. *"Four outcomes covered; dry-run and missing evidence write nothing"* → 12/12
   `kb-reverification` scenarios; whole-tree digest comparisons prove zero writes.
3. *"Suite green under `SQX_FORCE_MOCK=1`; ≤400 changed lines"* → evidence suite and touched
   slice green; **partially met** — 2 of 4 slices exceeded the 400-line budget (warning 4).

## Rollback Boundary

The archive is an audit trail; **nothing in `openspec/changes/archive/` is ever modified or
deleted.** Rolling back the *behaviour* means reverting the PRs, not this folder.

| Commit | Revert removes | Leaves intact |
|--------|----------------|---------------|
| `c59c41e` | The declared `xml_path`/`element_name` fields | `reverify.py`, store wrapper, CLI — they degrade to `not_xml_backed` verdicts rather than crash |
| `9cf2553` | The pure decision module | `models.py` fix; the live data-loss bug is already closed |
| `2eb8c16` | `KbStore.reverify_against_build` | The module; CLI would fail closed at the missing attribute |
| `6c5b673` | The `sqx kb reverify` subcommand | Everything else; `sqx kb verify` untouched |
| `097acd8` | Repo-root path resolution in the schema test | All production code |
| `ec0e44e` + `db763bb` | The lake `evidence_ref` repoint | Reintroduces 10 dangling `evidence_refs` — **revert this last** |

Recommended rollback order is reverse-chronological. **No migration, no schema break, no
feature flag.** Design's data-loss recovery, if ever needed:
`git checkout -- 'knowledge/structured/sqx-kb/144.2953/parameters/Cross checks/'`.

## Follow-Ups (each needs its own SDD change)

| # | Item | Note |
|---|------|------|
| **F1** | Reconcile this archive's REQ-201/REQ-208 merge with PR #26's competing variant | Highest priority. Same file, same two requirements, different wording. Whoever lands second rebases by hand. |
| **F2** | Ratify or amend `classify`'s use of `element_name` | The verify report requested this note explicitly. An unratified, fail-closed D-table extension is still an unratified one. |
| **F3** | Merge the 11 open PRs | Nothing is merged. The stack is `MERGEABLE`/`CLEAN`, but F1 must land first. |
| **F4** | `index.yaml` rebuild policy | Promotion desyncs `knowledge/index.yaml`'s sha256 and there is no staleness gate. Accepted only because the chain ships dry-run-first and `--apply` stays operator-initiated. |
| **F5** | `ci.yml` cannot run its own lint gate | Pre-existing infra defect: installs `pip install -e "sdk[dev]"`, whose extra declares neither `ruff` nor `mypy`, yet `ci.yml:37/41/45` invoke both. |
| **F6** | `AGENTS.md` is stale about the venv | It states "local `.venv` does not install `ruff` or `mypy`"; verification found `ruff 0.16.10` and `mypy 2.4.0` present. Documentation defect, outside this change's scope. |

## Engram Observations

Project `quantlabai`. Artifact store for this cycle was `openspec`; these exist because the
upstream phases were run in `hybrid` and mirrored. **The file is the source of truth.**

| ID | Title | State at close |
|----|-------|----------------|
| `#1133` | `sdd/kb-reverification-pipeline/explore` | Superseded by apply |
| `#1135` | `sdd/kb-reverification-pipeline/proposal` | Intent, scope, rollback plan |
| `#1137` | `sdd/kb-reverification-pipeline/spec` | The two change-local specs synced above |
| `#1138` | `sdd/kb-reverification-pipeline/design` | Decisions D1–D7 |
| `#1139` | `sdd/kb-reverification-pipeline/tasks` | Pre-apply snapshot |
| `#1142` | `sdd/kb-reverification-pipeline/apply-progress` | Pre-rebase; **its commit hashes and task-6.2 claim are stale** |
| `#1146` | `sdd/kb-reverification-pipeline/verify-report` | Terminal verdict `pass_with_warnings` |
| `#1148` | `Rebase cadena crosschecks sobre main completado` | Explains the hash remap and the clean collection |
| `#1143` | `Worktree tests need PYTHONPATH override` | Env gotcha, still true |
| `#1145` | `Full-suite pytest blocked by 3 missing modules` | **Stale** — true at `ebe0bbb`, superseded by `#1148` and section 1 |

**Absent**: no `sdd/kb-reverification-pipeline/review/*` topic exists. No native
receipt-driven review was ever started for this candidate, so `reviewGate` is structurally
absent and archive proceeded under ordinary repository policy.

## Archive Contents

| Artifact | Present |
|----------|---------|
| `explore.md` | yes (21.7K) |
| `proposal.md` | yes (79 lines) |
| `specs/kb-reverification/spec.md` | yes (100 lines, sha256 `b0f93d13…`) |
| `specs/sqx-parameter-kb/spec.md` | yes (63 lines, sha256 `d1a016f6…`) |
| `design.md` | yes (82 lines) |
| `tasks.md` | yes (126 lines, 12/12 `[x]`, 0 `- [ ]`, 1 `[!]`) |
| `apply-progress.md` | yes (81 lines, pre-rebase) |
| `verify-report.md` | yes (432 lines, `pass_with_warnings`) |
| `archive-report.md` | this file |

All artifacts are archived **verbatim** as history, including the pre-rebase commit hashes
and the stale task-6.2 claim. Correcting history in an archive destroys its value; the
corrections live in sections 1 and the hash-remap table above.

## Source of Truth Updated

- `openspec/specs/kb-reverification/spec.md` — **created**, 4 requirements / 12 scenarios
- `openspec/specs/sqx-parameter-kb/spec.md` — **updated**, REQ-201 and REQ-208 modified,
  8 requirements / 18 scenarios

## SDD Cycle

Complete. Planned, implemented across 4 stacked slices, verified with 19/19 scenario
compliance and 0 CRITICAL issues, specs synced, folder archived. The implementation ships in
**open PRs**; this archive records what was built and verified, not what has landed on
`main`.