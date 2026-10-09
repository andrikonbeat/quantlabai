# Exploration: KB Re-verification Pipeline

Phase: `explore` · Change: `kb-reverification-pipeline` · Mode: hybrid (Engram + filesystem)
Research only — no proposal, spec, design, or tasks produced.

## Scope of this document

Answer five questions about the automatic re-verification pipeline that, after
`invalidate_on_version_drift` demotes catalog entries to `needs_review`,
re-validates each entry against the newly installed build's XML and either
re-marks it `verified` with fresh evidence or confirms the field is gone.

### Branch baseline (read this first)

The verified context describes work that is **not on the current checkout**.
Current branch is `wip/migration-checkpoint`; `git grep` finds zero hits for
`_CROSSCHECK_FIELD_SPECS` or `invalidate_on_version_drift` there, and
`tests/knowledge/test_crosschecks_schema.py` does not exist. The drift hook and
the CrossChecks schema work live on `feat/crosschecks-p6-w3-drift-hook`
(tip `ebe0bbb`, "fix(knowledge): wire invalidate_on_version_drift into the drift
workflow"). Line references below marked *(p6)* are read from that branch via
`git show`. `sdk/quantlab/knowledge/kb/models.py` is byte-identical between the
two branches, so findings about that file apply to both.

## Current State

**Catalog.** `knowledge/structured/sqx-kb/144.2953/parameters/` holds 82 YAMLs
across 9 tab directories (8 declared tabs plus `Building blocks`), of which 10
sit in `Cross checks/`. Distribution is 74 `verified`, 8 `needs_review`,
0 `seeded`. The 8 `needs_review` entries are doc gaps, not drift:

```
Building blocks/ATM tab          Ranking/Optimizer block
Cross checks/Cross Checks vs Retester
Data/Data range parts (OOS)      Ranking/Portfolio Master vs Portfolio Composer
Ranking/Use                      What to build/Number of Exit Types (SL_PT_etc...)
                                 What to build/Strategy style
```

**Drift hook.** `KbStore.invalidate_on_version_drift(current_version, *,
catalog_version=None, tab=None)` *(p6: `store.py:294-348`)* returns a
`VersionDriftResult` carrying `drifted`, `invalidated`, `warnings`,
`blocked=False`. It short-circuits to a no-op on exact version equality
*(`store.py:321-327`)*, skips entries already `needs_review` so the count is
delta-only *(`store.py:332-333`)*, and never raises. `DriftWorkflow.run()`
*(p6: `versioning.py:178-211`)* routes through it and records `kb_invalidated`,
`drifted`, and `warnings` into
`structured/sqx-version/{from}→{to}/checklist.yaml`, swallowing failures so the
dispatch stays fail-open. `VersionPreflight.run()` wraps that in another
try/except *(p6: `versioning.py`)*.

**What is missing.** Nothing re-verifies. `KbStore.verify(tab, param,
evidence_ref)` is reachable only through the manual
`quantlab sqx kb verify {tab}/{param} --evidence-ref`
*(p6: `sq_commands.py:305-324`, subparser at `:533-546`)*. After a real drift the
operator has 82 entries and no tooling to resolve them.

## Finding 0 — BLOCKER: `KbStore` writes destroy the XML traceability fields

`xml_path` and `element_name` exist in the 10 `Cross checks/*.yaml` files and
nowhere else. `git grep -n "xml_path|element_name"` across the p6 branch's
`sdk/` tree returns only `sdk/tests/conftest.py:34` (an unrelated local
variable). `KbParameter` *(`models.py:70-107`)* declares 22 fields and neither
of these two.

Because `KbParameter.from_yaml` is `cls.model_validate(data)` with pydantic's
default `extra="ignore"`, and `to_yaml` is
`model_dump(exclude_none=True)`, **every** `KbStore` write drops both keys.
`verify()`, `invalidate()`, and `invalidate_on_version_drift()` all go through
`_load_file` + `_save_file`.

Executed proof against a copy of the real lake
(`KbStore(root=copy).verify("Cross checks", "What If simulations", ...)`):

```
BEFORE xml_path: True | element_name: True
AFTER  xml_path: False | element_name: False
```

Two consequences:

1. The drift hook that shipped in PR #22 already deletes the exact fields a
   re-verification pipeline needs to locate the field in XML. This is a live
   bug in the base, not a hypothetical.
2. `tests/knowledge/test_crosschecks_schema.py:96-110`
   (`test_every_yaml_has_xml_path_and_element_name`) reads raw text through a
   naive line parser *(`:49-62`)*, so it will fail on a real lake after any
   drift run. The schema test and the store are already in conflict.

Any pipeline that writes through `KbStore` inherits this. Preserving those keys
is a hard prerequisite, not optional scope.

`sdk/quantlab/knowledge/sqX_doc_provider.py:245-253` reads the file with raw
`yaml.safe_load`, so it still sees the fields today — and stops seeing them
after any `KbStore` write.

## 1. What exists today that the pipeline can reuse

| Asset | Location | Reuse |
|---|---|---|
| `KbStore` lifecycle | `sdk/quantlab/knowledge/kb/store.py` | `get/list/consult/seed/verify/invalidate/status` + `invalidate_on_version_drift`. `list(tab=, status=, sqx_version=)` already filters exactly the population reverify needs. No write preserves unknown keys. |
| Seed gate | `sdk/quantlab/knowledge/kb/validation.py` | `validate_seed` is a pure read-only gate. `_resolve_evidence(ref, lake_root)` *(`:58-73`)* strips `#anchor`, tries absolute then `lake_root.parent` then `lake_root` — the resolution order reverify should reuse. `_check_evidence` *(`:104-129`)* already distinguishes: `verified` refs must resolve, `needs_review` refs need not exist. |
| Frozen distribution band | `validation.py:29-33` | `total==82`, `verified ∈ [71,77]`, `needs_review ∈ [5,11]`. **Reverification shifts these counts and can break the gate.** |
| Lake taxonomy | `sdk/quantlab/knowledge/conformance.py` | `canonical_destination("version_events")` → `structured/sqx-version/{old}→{new}/`; `kb_seeder` → `structured/sqx-kb/{ver}/parameters/{tab}/`. A reverify report can live under the version-events destination with no taxonomy change. |
| Index | `knowledge/index.yaml` | 82 `kb_parameters` entries, each `{sqx_version, tab, parameter, size, sha256}`. Every write desyncs the sha. Only `index_coverage` (an entry count) is gated in `validation.py`; no staleness gate was found. |
| CLI shape | `sdk/quantlab/cli/sq_commands.py` | `sqx kb {list,get,seed,seed-ohlc,validate,verify,status,table}` + `sqx check-version`. All handlers are `async def cmd_*(args) -> int` returning an exit code. `_kb_store(args)` *(`:71-74`)* and `_add_common(parser)` *(`:458`)* supply `--knowledge-root` / `--sqx-version`. `check-version` documents the exit contract `0 in-sync / 1 drift / 0 unknown` *(`:411-442`)*. |
| **XML validation algorithm** | `tests/knowledge/test_crosschecks_schema.py:142-190` | `zipfile` → prefer `Build-Task1.xml`, else `config.xml` → `ET.fromstring` → `root.find(".//CrossChecks")` → walk `xml_path.split("/")[1:]` with `Element.find()`. This is the proven YAML-vs-XML check and should be lifted into production code, not rewritten. |
| Scoped regex probe | `sdk/quantlab/sqx/project_builder.py:69-160`, table `:371` | `_template_xml()`, `_extract_template_value()`, `_coerce_template_default()`, `get_template_default(field_name)`, `_CROSSCHECK_FIELD_SPECS`. Proven for tab-scoped region matching. |
| Pipeline stage | `sdk/quantlab/pipeline/stages/config_review_stage.py` | The only stage touching `KbStore`. `requires=["build_config"]`, `provides=["config_review_verdict"]`. |

Two gaps in the existing reuse surface:

- `KbStore.consult()` filters on `status` only when the caller passes it.
  `build_review_teaching_table` calls `consult(term)` with no filter
  *(`config_review_stage.py:150`)* and then `KbParameter.model_validate(hit)`
  without checking `status`, so a drifted `needs_review` entry still reaches the
  reviewer table. REQ-208's "MUST NOT serve as verified" is advisory only today.
- There is no KB pipeline. `pipelines/sqx_campaign.yaml` is the 14-phase
  campaign pipeline; adding a stage there would touch the flow contract that
  `tests/campaign/test_flow_integrity.py` guards.

## 2. Where the new build's XML evidence comes from

Three candidate sources, and only one of them can prove anything about the
installed build.

**Bundled template — no version provenance.**
`sdk/quantlab/sqx/templates/default-project.sqx-template` is a ZIP holding
`Build-Task1.xml` (1,240,464 B) and `config.xml` (623 B). Its root is
`<Settings>` and a scan for `version="..."` in `Build-Task1.xml` returns **zero
matches**. The template declares which build it mirrors only by the implicit
convention that it is re-bumped alongside `PINNED_SQX_VERSION`. After a drift
to 145.x this file still holds 144.2953 defaults, so it can **never** serve as
evidence for the new build. It remains the right fixture for tests.

**Real install `.cfx` — self-describing version.**
`sdk/assets/SQX_144_2953_linux_20260601/user/projects/sqx_4fdea2e7519c/project.cfx`
contains `config.xml` with `<Project name="sqx_4fdea2e7519c" version="144.2953">`
and a `Build-Task1.xml`. The version attribute is real evidence. Availability
caveats: the repo-local `assets/SQX_144_2953_linux_20260601` is a **symlink**
to `/home/ogzuz/Proyectos/SQX_144_2953_linux_20260601` and is gitignored
(`.gitignore:59` `assets/SQX_*`); `sdk/assets/…` is untracked and not ignored,
so it must be copied into clean worktrees.

**SDK detection — major only.**
`VersionPreflight.detect_installed()` returns `LicenseInfo.build_number`, parsed
by `re.search(r"build\s+([0-9]+(?:\.[0-9]+)?)", lower)`
(`sdk/quantlab/pipeline/license.py:125`). The docstring records the real output
as `Build 144` with no point version, and `VersionPreflight._build_major()`
compares only the prefix. After a 144→145 drift the SDK knows the string
`"145"` and nothing more.

**Conclusion.** The pipeline cannot self-source 145.x XML. The evidence must be
operator-supplied: a `.cfx`, `.sqx-template`, or any ZIP containing
`Build-Task1.xml`, ideally one whose `config.xml` declares
`version="145.x"`. `_CROSSCHECK_FIELD_SPECS` is a useful precedent for scoped
matching, but it keys on `BuildConfig` dataclass field names
(`wf_oos_*`, `wi_by_hours_use`), not on KB `xml_path`/`element_name`, and it
probes the template rather than an install — so it informs the design without
being the implementation.

## 3. The pipeline surface

### Approaches

| # | Approach | Pros | Cons | Effort |
|---|---|---|---|---|
| A | `KbStore.reverify_against_build()` + `sqx kb reverify` CLI | Matches the existing store/CLI shape; `sq_commands.py` handlers are thin; dry-run default is a one-flag change; testable with `tmp_path` lakes and the tracked template as fixture | Store grows a build-aware concern; needs Finding 0 fixed first | Medium |
| B | Pure function in a new `sdk/quantlab/knowledge/kb/reverify.py`, exposed as a thin store method | Decision logic is pure and unit-testable without touching the lake; matches how `validation.py` already isolates gate logic from `store.py` | One more module; callers must remember the wrapper | Medium |
| C | Ingest adapter alongside `DocIndexer` (`sdk/quantlab/knowledge/ingest/`) | Reuses the existing evidence-ingestion seam and version-pinning discipline | `DocIndexer` is for licensed-install doc corpora into `docs/`; a KB status mutation is the wrong fit there, and adapters never write back into `parameters/` | High |
| D | New campaign pipeline stage | Would run automatically | There is no KB pipeline; `pipelines/sqx_campaign.yaml` is the 14-phase flow whose integrity is test-guarded; a stage cannot obtain a 145 artifact anyway, so it would be a no-op with extra machinery | High |

### Recommendation

**B wrapped by A**, wired as opt-in and never auto-promoting.

- New pure module `sdk/quantlab/knowledge/kb/reverify.py` holding the decision
  table and the evidence loader.
- `KbStore.reverify_against_build(evidence, *, tab=None,
  sqx_version=None, apply=False)` as the thin wrapper that reuses `list()` for
  population and `verify()` for promotion — so there is exactly one write path.
- `quantlab sqx kb reverify --evidence <path> [--tab T] [--apply]` in
  `sq_commands.py`, mirroring `cmd_kb_verify`'s handler shape and reusing
  `_kb_store` / `_add_common`. Default is dry-run.

Per-entry decision, four outcomes:

| Evidence state of the entry | Outcome |
|---|---|
| `xml_path` resolves in the evidence XML and the element is present | `verified`, `evidence_ref` = evidence artifact (+ anchor) |
| `xml_path` present, element absent in the evidence XML | stays `needs_review`, reason `field_absent` |
| No XML `xml_path` (doc-gap entries) | **skipped, never promoted**, reason `not_xml_backed` |
| Evidence artifact missing or unreadable | no writes at all; run fails open on dispatch, exit code distinct |

The third row is the discriminating fact that keeps this pipeline from
fabricating semantics. `Cross checks/Cross Checks vs Retester.yaml` carries
`status: needs_review`, doc-gap markers in all three prose fields, and
`xml_path: docs/sqx-builder-config/SQX Builder Config.md#Cross checks` — a
**Markdown anchor, not an XML path**. An XML walker must never touch it. Its
sibling `What If simulations.yaml` is the contrast case: `verified`,
`xml_path: CrossChecks/WhatIf`, evidence_ref to the real `.cfx`.

The minimal evidence-first contract is therefore: *promote only when an
XML-anchored `xml_path` was positively resolved in a named artifact; leave
everything else exactly as found, with a reason.*

## 4. Edge cases

- **Tab-scoped reverify.** Mirror `invalidate_on_version_drift(tab=...)`. A tab
  with zero `needs_review` entries is a no-op that still reports the drift
  verdict — drift is a property of the two version strings
  *(p6: `store.py:363-375` tests this for invalidation)*.
- **Missing XML / artifact.** Fail-closed on writes, fail-open on dispatch. The
  drift hook already failed open, so a reverify that cannot read its evidence
  must leave `needs_review` in place and report, not guess. Distinct non-zero
  exit code so CI can see it without blocking a run.
- **Partial evidence.** Per-entry outcomes only. There is no batch verdict: some
  entries resolving and some not is the expected outcome of a real version bump.
- **`xml_path` no longer exists in the new build.** `field_absent`, stays
  `needs_review`. This is the "confirm the field no longer exists" case, and it
  is a terminal answer, not a retry.
- **Strict-mode consumers.** `VersionDriftResult.blocked` stays `False`;
  REQ-208 is warn-only by contract *(p6: `store.py:308-310`)*. Reverification
  must not flip the catalog into a blocking posture, and must not silently
  promote either — both would change REQ-208's semantics.
- **Mock path (`SQX_FORCE_MOCK=1`).** `detect_installed()` returns `None`
  immediately *(`versioning.py:78-79`)*, so `run()` returns `"unknown"`, never
  creates drift, and never produces a `needs_review` population. A reverify
  driven off detection would therefore be **unverifiable by the 3900-test
  suite**. It must run off an explicit `--evidence` path, which is also why the
  tracked template works as the test fixture.
- **Version buckets other than 144.2953.** `KbParameter.sqx_version` is a plain
  `str`, but `tab` is a `Literal` of the 8 declared tabs *(`models.py:29-38`)*,
  so a new bucket that renames or adds a tab fails `model_validate` on load.
  No other bucket has a catalog today, so per-bucket behaviour is untested
  territory; the pipeline should default to the pinned bucket and refuse an
  unknown one rather than create it.
- **`needs_review` doc gap vs drift.** Same status value, opposite cause. The
  discriminator must be structural (`xml_path` shape), never the status string —
  `invalidate_on_version_drift` deliberately does not record *why* an entry was
  demoted, so there is no provenance field to read.
- **Distribution-band collision.** `validate_seed` freezes
  `needs_review ∈ [5,11]` and `verified ∈ [71,77]`. Promoting the 74 verified
  entries leaves 8 needs_review (still in band), but promoting the 8 doc gaps
  would drive `needs_review` to 0 and fail `_check_distribution`. The pipeline
  must not touch doc-gap entries, and the band needs a documented story before
  any large promotion lands.
- **Index desync.** `knowledge/index.yaml` stores a per-file `sha256`. Any
  promotion or demotion makes it stale. No staleness gate was found; the index
  needs a rebuild in the same work unit or an explicit "index is advisory here"
  note.
- **Name lookup.** `_safe_param_filename` sanitizes names
  *(`store.py:54-60`)*, so `verify()` lookups by `param` must use the sanitized
  filename form, not the raw `sqx_name`.

## 5. Scope recommendation

### Slice A — first slice, target ≤400 changed lines

1. **Fix Finding 0.** Declare `xml_path: str | None = None` and
   `element_name: str | None = None` on `KbParameter`
   (`sdk/quantlab/knowledge/kb/models.py`). Prefer explicit fields over
   `model_config = ConfigDict(extra="allow")`: these are real catalog fields that
   the doc provider and schema test already read, and an explicit declaration
   keeps `to_yaml` deterministic. Without this, nothing else is safe.
2. **Add the decision logic** in `sdk/quantlab/knowledge/kb/reverify.py`:
   evidence loader (ZIP → `Build-Task1.xml` else `config.xml`, reused from
   `test_crosschecks_schema.py:167-177`), XML path walker, and the four-outcome
   decision table.
3. **Thin store wrapper** `KbStore.reverify_against_build(...)` delegating to
   `list()` and `verify()`.
4. **CLI** `sqx kb reverify --evidence <path> [--tab] [--apply]`, dry-run default,
   in `sdk/quantlab/cli/sq_commands.py`.
5. **Tests** in `tests/knowledge/test_kb_reverify.py` using
   `default-project.sqx-template` as the fixture (tracked, no untracked assets,
   works under `SQX_FORCE_MOCK=1`) plus `tmp_path` lakes: promote, field-absent,
   doc-gap skipped, missing-artifact no-writes, dry-run no-writes, tab scoping,
   and a regression test that `xml_path` survives a `verify()` write.

Estimated: ~15 (model) + ~150 (reverify) + ~60 (CLI) + ~150 (tests) ≈ 375
authored lines. The report file under `structured/sqx-version/{old}→{new}/` is
the deferrable piece if the budget is tight — the counts already come back on
stdout.

### Follow-up (separate work units)

- Auto-discovery of the installed build's artifacts from the SQX install path,
  so `--evidence` becomes optional.
- Point-version-aware detection: a real `version=` source, since
  `LicenseInfo.build_number` is major-only and prevents naming the target bucket.
- Opt-in wiring into `DriftWorkflow.run()` after the checklist write.
- Status-gating `ConfigReviewStage.build_review_teaching_table` so
  `needs_review` entries stop reaching the reviewer table.
- `knowledge/index.yaml` rebuild (or a documented staleness policy) after writes.
- Extending `xml_path`/`element_name` beyond the 10 `Cross checks` entries — the
  other 72 currently have no XML anchor at all and cannot be re-verified
  mechanically.

## Affected Areas

- `sdk/quantlab/knowledge/kb/models.py` — Finding 0; declare `xml_path`,
  `element_name`.
- `sdk/quantlab/knowledge/kb/store.py` — Finding 0 write path; add the thin
  `reverify_against_build` wrapper.
- `sdk/quantlab/knowledge/kb/reverify.py` — new; pure evidence loader and
  decision table.
- `sdk/quantlab/cli/sq_commands.py` — new `sqx kb reverify` subcommand.
- `sdk/quantlab/versioning.py` — `DriftWorkflow.run()` is the natural follow-up
  hook point; not in Slice A.
- `tests/knowledge/test_crosschecks_schema.py` — must survive the model change
  (it already passes on a model that ignores the fields).
- `tests/knowledge/test_kb_reverify.py` — new.
- `openspec/specs/sqx-parameter-kb/spec.md` — REQ-208 currently ends at
  "MUST NOT serve as verified ... until re-verified"; the reverify requirement
  and the doc-gap exemption belong here.

## Risks

- **Finding 0 is a live data-loss bug in shipped code**, not a prerequisite
  nicety. Until the model preserves unknown keys, running the drift hook
  destroys evidence fields on the real lake.
- **Fabrication risk.** An XML walker that cannot distinguish "field absent"
  from "wrong path" will promote entries whose semantics it never confirmed. The
  four-outcome table must treat `field_absent` and `not_xml_backed` as terminal
  `needs_review` states.
- **Evidence sourcing is operator-gated.** No code path in the repo can obtain
  145.x XML autonomously; `detect_installed()` returns a major only. A pipeline
  that pretends otherwise will "verify" against 144.2953 data after a 145
  install.
- **Distribution-band coupling.** Promotion changes counts that
  `validate_seed` freezes. Slice A must not promote doc-gap entries, and the
  band needs revisiting before any broad promotion.
- **Untracked fixtures.** `assets/SQX_*` is a symlink and gitignored;
  `sdk/assets/…` is untracked. Tests that depend on the real install will fail
  in clean worktrees and CI. Use the tracked template as the fixture.
- **Branch divergence.** The work lands on a branch that already carries the
  drift hook; the current checkout does not. Verify the base before applying.
- **Index staleness.** `knowledge/index.yaml` sha256 entries desync on every
  write, silently.

## Ready for Proposal

**Yes.** The design is bounded, the reusable surfaces are identified with line
references, and the blocking dependency (Finding 0) is small and mechanical.

The orchestrator should tell the user two things before proposing:

1. The drift hook already shipped in PR #22 silently deletes `xml_path` and
   `element_name` from every Cross checks entry it demotes, and this breaks
   `test_crosschecks_schema.py` on a real lake. Slice A fixes that first.
2. "Automatic" re-verification is bounded by evidence availability: the SDK can
   detect only the major build, so a 145.x verdict needs an operator-supplied
   artifact. Slice A takes `--evidence` explicitly and auto-discovery is a
   follow-up.

Open question for the user, if the proposal needs it settled: should
Slice A write a machine-readable report under
`structured/sqx-version/{old}→{new}/reverify-report.yaml` (conformance-legal via
the `version_events` writer), or is stdout plus the mutated YAML enough for the
first slice?