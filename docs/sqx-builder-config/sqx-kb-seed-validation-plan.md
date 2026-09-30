# SQX-KB Seed Validation Plan

**Scope**: Seeding, validating, and re-generating the SQX Parameter Knowledge
Base (KB) for the pinned strategy builder build **144.2953**, including the
REQ-209 seed-validation gate and the REQ-205 educational dataset/table.

**Applies to**: `knowledge/structured/sqx-kb/144.2953/`, `knowledge/index.yaml`,
the modules under `sdk/quantlab/knowledge/kb/`, and the CLI commands under
`quantlab sqx kb ...`.

---

## 1. Background and Frozen Band

The KB is seeded from the SQX Builder Config reference document
(`docs/sqx-builder-config/SQX Builder Config.md`, the default at `DEFAULT_DOC_PATH`) with
**82 parameters** (77 SEED_SPEC + 5 GAP_SPEC). After seeding, the flow bulk
verifies parameters against the pinned real install's `.cfx` config files using
the curated `CFX_EVIDENCE_MAP` (74 entries pointing at exactly two distinct
files — `project.cfx`, 67 params, and `DJ CFD H1.cfx`, 7 params). Parameters
the install cannot confirm are demoted to `needs_review`; nothing is invented
for missing evidence.

The distribution band was frozen empirically from the first real seed run
(T-1.5, actual distribution `82 / 74 verified / 8 needs_review / 0 seeded`):

| Metric | Frozen band | Purpose |
|---|---|---|
| total | `== 82` | seed composition must stay complete |
| verified | `[71, 77]` | 74 ±3 drift window for doc/config edits |
| needs_review | `[5, 11]` | 8 ±3 drift window; **accepted terminal state** |
| verified + needs_review | `== total` | no leftover `seeded` entries |

`needs_review` within quota is a **success** state and MUST NOT fail the gate
(REQ-209 scenario 2). The constants live in
`sdk/quantlab/knowledge/kb/validation.py` (`VERIFIED_MIN/MAX`,
`NEEDS_REVIEW_MIN/MAX`, `SEED_TOTAL`) — single source of truth; adjust only
when the seed composition changes.

---

## 2. How to Seed (real install)

Prerequisites: the pinned install tree exists at
`/home/ogzuz/Proyectos/SQX_144_2953_linux_20260601/` (with `user/projects/Builder/project.cfx`
and `user/settings/Configs/DJ CFD H1.cfx`), and `docs/sqx-builder-config/SQX Builder Config.md`
is present.

Work from `sdk/` so the SDK is importable:

```bash
cd sdk
python3 -m quantlab.cli.main sqx kb seed --knowledge-root ../knowledge
```

What `seed` does (spec-faithful, no `--no-gate` escape hatch):

1. `seed_from_doc` — emits all 82 parameter YAMLs under
   `knowledge/structured/sqx-kb/144.2953/parameters/{tab}/` with `seeded`
   status and doc-anchored `evidence_ref`.
2. `_bulk_verify` — for every `CFX_EVIDENCE_MAP` entry whose real install file
   exists, promotes that parameter to `verified` with the map's relative
   evidence path.
3. `_demote_unverified` — leftover `seeded` entries become `needs_review`.
4. `rebuild_index` — rewrites `knowledge/index.yaml` (v4) with `kb_parameters`
   coverage.
5. `validate_seed` — runs the REQ-209 gate. **Exit 0 only when every check
   passes; exit 1 + report otherwise.**

CLI output shows the gate report (`Gate counts: ...` then `[PASS]/[FAIL]` per
check).

---

## 3. The REQ-209 Gate

`validate_seed` (pure, read-only — never writes) checks four invariants against
`structured/sqx-kb/{ver}/parameters/**/*.yaml` and `knowledge/index.yaml`:

1. **schema** — every YAML loads against the REQ-201 `KbParameter` model;
   violations name the parameter and the missing/malformed field.
2. **index_coverage** — `index.yaml` `kb_parameters` covers all 82 entries for
   version 144.2953 (REQ-403; asserts coverage, not the version literal).
3. **evidence** — every parameter has a non-empty `evidence_ref`; `verified`
   parameters' refs must resolve to an existing file. `needs_review` refs are
   best-effort doc anchors and are not required to exist.
4. **distribution** — the frozen band above; `verified + needs_review == total`.

### Re-validate (idempotent re-check)

```bash
cd sdk
python3 -m quantlab.cli.main sqx kb validate --knowledge-root ../knowledge
```

Same gate, no writes. Exit 0 when healthy, 1 otherwise.

### Status overview

```bash
cd sdk
python3 -m quantlab.cli.main sqx kb status --knowledge-root ../knowledge
```

Expected real-lake output:

```
sqx-kb/144.2953: 82 parameter(s) — seeded 0, verified 74, needs_review 8
```

---

## 4. Evidence Ledger

| Step | Command | Evidence produced | Expected healthy values |
|---|---|---|---|
| Seed | `sqx kb seed --knowledge-root ../knowledge` | 82 parameter YAMLs under `parameters/{tab}/`, rebuilt `index.yaml`, gate report | Gate counts `82 / 74 / 8 / 0`, `[PASS]` ×4, exit 0 |
| Validate | `sqx kb validate --knowledge-root ../knowledge` | Gate report only (no writes) | Same counts, `[PASS]` ×4, exit 0 |
| Status | `sqx kb status --knowledge-root ../knowledge` | Per-tab/per-status counts | Total 82, verified 74, needs_review 8 |
| Educational table | `sqx kb table --knowledge-root ../knowledge` (below) | `educational/educational-table.md` + `educational-dataset.yaml` | 82 records, byte-identical on re-run |

Golden snapshot (all present under `knowledge/`):

- `structured/sqx-kb/144.2953/parameters/{tab}/*.yaml` — 82 goldens
- `index.yaml` — v4, `kb_parameters` coverage == 82
- `structured/sqx-kb/144.2953/educational/educational-table.md` — REQ-205 table
- `structured/sqx-kb/144.2953/educational/educational-dataset.yaml` — 15-field
  records, consumed by the justification matrix

---

## 5. Regenerating the Educational Table / Dataset

The table cross-references the real builder template
(`/home/ogzuz/Proyectos/SQX_144_2953_linux_20260601/internal/web/BUILDER/templates/tpl_build.xml`)
against the seeded KB via the curated `TPL_KEY_MAP`; unmapped parameters are
flagged `⚠ template-missing` and keep their KB status (nothing invented).

```bash
cd sdk
python3 -m quantlab.cli.main sqx kb table --knowledge-root ../knowledge
```

Deterministic and idempotent: re-running with unchanged inputs produces
byte-identical `educational-table.md` and `educational-dataset.yaml` and never
modifies the KB YAMLs or the index.

---

## 6. Spot-Checking a Parameter Against a .cfx

`.cfx` files are ZIP containers holding the config XML. The spot-check proves a
parameter's `verified` status maps to a real install file.

Example: **Max # of Generations** (tab `Genetic options`)

```bash
cd sdk
# 1. Show the KB record: status must be verified with a .cfx evidence_ref
python3 -m quantlab.cli.main sqx kb get "Genetic options/Max # of Generations" --knowledge-root ../knowledge

# 2. Check the evidence file exists and is a real .cfx container
unzip -l ..//home/ogzuz/Proyectos/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx
# expected: a Config.xml member rides inside the ZIP

# 3. Cross-check the curated mapping (project.cfx, 67 params)
grep -c "Max # of Generations" sdk/quantlab/knowledge/kb/seeding_flow.py
```

Expected values for this parameter: `status: verified`,
`evidence_ref: /home/ogzuz/Proyectos/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx`.
Trading-options params such as **Friday Close Time** map to
`user/settings/Configs/DJ CFD H1.cfx` instead (7 params). Parameters with no
install evidence (e.g. `Strategy style`, `Use`, `Number of Exit Types (SL/PT/etc...)`)
must stay `needs_review` — they are intentionally absent from `CFX_EVIDENCE_MAP`.

CI-safe synthetic spot-check (no real install required): the test suite builds
real `.cfx` ZIPs from the committed `config_mini.xml` fixture (via
`conftest.make_cfx`) and asserts a known parameter maps to a verified KB record
and the educational dataset loads over it — see
`sdk/tests/test_kb_seed_validation.py::TestCfxIntegration`.

---

## 7. Rollback

### Undo a seed run (data layer)

```bash
# 1. Remove the seeded version bucket entirely
rm -rf knowledge/structured/sqx-kb/144.2953/
# 2. Restore the previous index.yaml (from git)
git checkout -- knowledge/index.yaml
```

The KB returns to empty-but-functional: the store/seeder remain, nothing else
is touched. The same recipe removes the educational artifacts (they live inside
the same version bucket).

### Undo the code (VCS layer)

The feature landed as chained PRs stacked to main; revert by work unit:

- WU1/WU2 (PR 1): `git revert 9348e7e 5bebf47` — gate + flow + 82 goldens + index
- WU3/WU4 (PR 2): `git revert db26080 e3af055` — generator + matrix hook
- WU5 (PR 3): revert the integration tests + plan doc

### Frozen band recovery

If the gate starts failing on distribution, first re-check the real counts with
`sqx kb status`. If the doc/config drifted but counts stay within
verified `[71, 77]` / needs_review `[5, 11]`, the gate passes by design. If the
seed composition itself changes (new params added/removed), update the
`validation.py` constants to the new empirical distribution and re-run the RED
band tests — the constants are the single source of truth.

---

## 8. Running the Test Suite

Focused integration (WU5, `-k cfx` filter):

```bash
cd sdk
SQX_FORCE_MOCK=1 python3 -m pytest tests/test_kb_seed_validation.py -k cfx -q --tb=short
```

Full KB family:

```bash
cd sdk
SQX_FORCE_MOCK=1 python3 -m pytest tests/test_kb_seed_validation.py tests/test_kb.py tests/test_kb_educational.py tests/test_conformance.py -q --tb=short
```

Known pre-existing failures are out of scope and must not be "fixed" here:
`tests/test_knowledge.py` (v4/v5 index-version asserts) and
`tests/test_retest_optimize_stages.py` (databanks deviation).