# Design: KB Re-verification Pipeline

> **Base branch.** The drift hook, the `Cross checks` schema test, and `_CROSSCHECK_FIELD_SPECS` live on `feat/crosschecks-p6-w3-drift-hook` @ `ebe0bbb`, **not** on this checkout (`wip/migration-checkpoint`). All `store.py` / `sq_commands.py` / `versioning.py` refs below are read from that branch via `git show`; `kb/models.py` is byte-identical across branches. **Create the apply worktree from `feat/crosschecks-p6-w3-drift-hook` and verify the drift hook + schema test exist before starting.**

## Technical Approach

Task 0 fixes the live data-loss bug (REQ-201/208), then a pure module decides, a thin store method writes, and a CLI surfaces it. Promotion only on a positive XML resolution in an operator-named artifact; everything else stays as found, with a reason.

## Architecture Decisions

| # | Decision | Options / tradeoff | Choice + rationale |
|---|---|---|---|
| D1 | Finding 0 first | (a) fix model, then pipeline; (b) pipeline first | **(a)**. Every write goes `_load_file`→`_save_file` (`store.py:104-111`) and `to_yaml` is `model_dump(exclude_none=True)` (`models.py:104-112`), so `extra="ignore"` strips both anchors today. |
| D2 | Model fix shape | (a) explicit optional fields; (b) `ConfigDict(extra="allow")` | **(a)**: `xml_path: str \| None = None`, `element_name: str \| None = None`. Keeps `to_yaml` deterministic and the schema truthful; (b) leaks typos into the catalog. REQ-201 mandates (a). |
| D3 | Where the decision lives | (a) in `store.py`; (b) pure `kb/reverify.py` + thin wrapper; (c) ingest adapter | **(b)**. Matches `validation.py` (pure gate beside the store), testable without a lake. (c) misfits: `DocIndexer` never writes into `parameters/`. |
| D4 | Promotion write path | (a) new writer; (b) reuse `verify()` (`store.py:246-269`) | **(b)**. One write path; no second serializer can diverge from `verify()`. |
| D5 | Population | (a) `list(status="needs_review")`; (b) unfiltered `list(tab=, sqx_version=)` | **(b)**. Verdicts come from `xml_path` shape, never `status` (spec). Status filtering would exempt a doc-gap entry already `verified`; re-`verify()` is idempotent. |
| D6 | Unreadable-evidence exit | `1` / `2` / `3` | **`3`**. `1` = ran, non-promoting outcomes; `2` is `argparse`'s usage-error code and would collide. |
| D7 | Report file | (a) `structured/sqx-version/{old}→{new}/…yaml`; (b) stdout | **(b)**; deferred. Stdout carries per-outcome counts. |

## Data Flow

```
--evidence (ZIP/.cfx/.xml)
   │ load_evidence(): Build-Task1.xml else config.xml → ET.fromstring → .//CrossChecks
   ▼
Evidence(crosschecks | None)   ── None ⇒ evidence_unreadable: zero writes, exit 3
   ▼
store.list(tab=, sqx_version=) → classify(entry, crosschecks) → Verdict
                                        │
              apply=False ───────────────┤ report only
              apply=True  ─► store.verify(tab, name, f"{artifact}#{xml_path}")
```

### Four-outcome decision table (`classify`, pure)

Structural discriminator — **never** `status`: `xml_path` is XML-anchored iff non-empty, has no `#`, does not end `.md` (case-insensitive), and `split("/")[0] == "CrossChecks"` (the segment the walker drops when rooting at `.//CrossChecks`).

| `xml_path` shape | XML probe | Verdict | Store effect |
|---|---|---|---|
| XML-anchored, all `parts[1:]` `find()` hit | element present | `verified` | promote via `verify()`; `evidence_ref = f"{artifact}#{xml_path}"` |
| XML-anchored | root resolves, a `parts[1:]` tag missing | `field_absent` (terminal) | none; stays `needs_review` |
| doc anchor (`docs/…md#Cross checks`) or absent | not probed | `not_xml_backed` | none; never promoted, whatever the status |
| — | archive/XML unparseable | `evidence_unreadable` (run-level) | **zero writes**, exit 3 |

Walker lifted from `tests/knowledge/test_crosschecks_schema.py:142-190` (member preference, `.//CrossChecks`, `Element.find` per `parts[1:]`).

## File Changes

| File | Action | Description |
|---|---|---|
| `sdk/quantlab/knowledge/kb/models.py` | Modify | Add `xml_path` / `element_name` optional `str` after `evidence_ref` (`models.py:97`). |
| `sdk/quantlab/knowledge/kb/reverify.py` | Create | `load_evidence()`, `classify()`, `ReverifyReport`, tab/bucket guards. No store imports. |
| `sdk/quantlab/knowledge/kb/store.py` | Modify | `reverify_against_build(evidence, *, tab=None, sqx_version=None, apply=False)` → `list()` + `verify()` only; unknown bucket refused. After `store.py:348`. |
| `sdk/quantlab/cli/sq_commands.py` | Modify | `cmd_kb_reverify` (mirrors `cmd_kb_verify`, `:305-324`) + subparser after `:533-546`; `_add_common` supplies `--knowledge-root`/`--sqx-version`. |
| `tests/knowledge/test_kb_reverify.py` | Create | See Testing Strategy. |

## Testing Strategy

Tracked fixture `sdk/quantlab/sqx/templates/default-project.sqx-template` only — **never** `assets/SQX_*` (symlink, gitignored `:59`) or `sdk/assets/…` (untracked). Lakes via `tmp_path`. Run: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/knowledge/`.

| Layer | Test | Boundary |
|---|---|---|
| Regression (task 0) | `xml_path` survives a `verify()` write | RED first, then green |
| Unit | promote; `field_absent`; doc-gap skipped, status unchanged | `classify` + wrapper, `apply=True` |
| Integration | missing artifact → zero writes, exit 3; dry-run → zero writes, exit 0; `--tab` scoping; unknown bucket refused | handler called directly |

## Threat Matrix

**Not applicable** — no shell, subprocess, VCS/PR automation, or executable-file classification boundary. `--evidence` is an operator-supplied path read via `zipfile`/`ElementTree`; malformed input is a *file-parsing* boundary covered by the fail-closed `evidence_unreadable` row (zero writes, exit 3).

## Migration / Rollout

No migration. **Rollback boundary**: one revertable work unit — revert `models.py`, delete `reverify.py`, drop the wrapper and subparser. If a write stripped anchors, `git checkout -- 'knowledge/structured/sqx-kb/144.2953/parameters/Cross checks/'` restores all 10. `knowledge/index.yaml` sha256 desyncs on promotion; no staleness gate exists — acceptable while the slice ships dry-run-first.

## Deferred

Report file under `structured/sqx-version/{old}→{new}/`; artifact auto-discovery; point-version detection (`detect_installed` is major-only); `DriftWorkflow.run()` wiring (`versioning.py:178-211`); `index.yaml` rebuild; status-gating `build_review_teaching_table`; `xml_path` beyond the 10 entries; `validate_seed` band (`validation.py:29-33`) revisited before broad promotion.

## Open Questions

None. Proposal round Q1 resolved by D7 (stdout only); Q2 resolved as `artifact#xml_path`.
