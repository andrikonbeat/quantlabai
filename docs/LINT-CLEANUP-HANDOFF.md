# Handoff — Lint & Type-Cleanup Campaign

> **Frozen campaign log.** The four blocking product decisions now live in
> [`sdd/PROJECT_STATE.md`](../sdd/PROJECT_STATE.md) §8 (Known debt and blocked
> decisions). Do not extend this doc — record new lint/type state in
> `sdd/PROJECT_STATE.md`. What follows is the frozen 2026-10-06 campaign
> record, kept for its verification discipline and gotchas.

Status document for the `--strict` mypy + Ruff cleanup on `main`.
Written at commit `5b1e4e6` (verify with `git log --oneline -1`; the
campaign is committed in slices, so the exact hash moves).

Read this before touching the type-check work. It records what is done, what
remains, and the four product decisions that lint cannot answer for you.

---

## 1. Where the campaign stands

| Gate | Baseline | Now | Status |
|---|---|---|---|
| Ruff `F401` (unused import) | 355 | **0** | done |
| Ruff `format` | 272 files pending | **0** pending | done |
| mypy `--strict` errors | 745 | **412** | in progress (45% down) |
| mypy `[no-redef]` | 8 | **0** | done |
| mypy `[type-arg]` | 145 | **0** | done |
| mypy `[valid-type]` | 6 | **0** | done |
| Ruff total | 1866 | **868** | not started |
| Tests | 4173 passed | **4173 passed, 18 skipped** | green throughout |

Tooling is pinned so the baseline cannot drift under you:

- `ruff==0.16.10`
- `mypy==2.4.0`

There is no `[tool.ruff]` section, so the active rule set is Ruff's defaults
plus whatever the pinned version ships. Be aware this means adding a
`[tool.ruff]` section will silently change the target.

### Canonical commands

```bash
# type check (must be run from sdk/)
cd sdk && ../.venv/bin/python -m mypy quantlab

# full suite (repo root)
SQX_FORCE_MOCK=1 .venv/bin/python -m pytest -q

# lint (from sdk/)
../.venv/bin/python -m ruff check .
../.venv/bin/python -m ruff format --check .
```

`SQX_FORCE_MOCK=1` is mandatory for the suite, otherwise pytest binds the
real SQX daemon on port 5050.

---

## 2. Defects found along the way

The type-check campaign was not cosmetic. It surfaced eight real defects
that the test suite could not see. Two are already fixed; six remain and
are listed in section 4.

### Fixed

1. **`cli/main.py` — `except` clause referencing an unimported name.**
   Referenced `JForexConnectionError` without importing it. A real
   `NameError` on the exception path.

2. **`dashboard/app.py` — unreachable block after `return`.**
   Ruff `F821` on a name only referenced in dead code.

3. **Six annotations that named a function instead of a type** (all
   `[valid-type]`, all silently meaningless under `--strict`):
   - `robustness/retry_policy.py` and `robustness/circuit_breaker.py` used
     `-> any` — the **builtin** `any`, not `typing.Any`.
   - `health/weights.py` used `dict[str, callable]` for `_NORMALIZERS`;
     all eight normalizers share `(float | None) -> float`.
   - `knowledge/kb/store.py` and `pipeline/registry.py` each define a
     method named **`list`**, which shadowed the builtin inside the class
     body. Sibling methods annotated `-> list[...]` resolved to *that
     method*, and `PipelineRegistry.list` was annotated as returning
     itself. Fixed with `builtins.list[...]` rather than renaming public
     API.

4. **Eight shadowed duplicate definitions** (`[no-redef]`). In every case
   the later definition wins, so the earlier was dead code — and mostly
   provably broken code. Worst case: `KnowledgeStore.tag/get_tags/link/
   get_links` built an `Indexer(self)` although `Indexer.__init__` expects
   a `Path`, then called a `@staticmethod` with the wrong arity. It never
   worked. In `cfx/patcher.py` the live
   `_parse_conditions_from_xml` had *lost* a `try/except ET.ParseError`
   guard and a `root.tag == "Conditions"` branch that the dead version had,
   so malformed `raw_xml` in a user-authored `.cfx` raised instead of
   returning `[]`. Those guards were ported before deleting.

### Still open

See section 4 — each needs a product decision, not a lint fix.

---

## 3. The verification discipline that produced this

Keep using it. It caught real problems every single time.

For **every** slice of delegated or mechanical work:

1. **Diff the per-category mypy counts before and after** and assert that
   **no category increased**. A rising category means the fix traded one
   error for another. Script used:

   ```python
   import re, collections
   def counts(p):
       c = collections.Counter()
       for l in open(p):
           m = re.search(r"\[([a-z-]+)\]$", l.strip())
           if m: c[m.group(1)] += 1
       return c
   ```

2. **Assert zero new suppressions** in the diff:
   `git diff -U0 | grep -cE '^\+.*(type:\s*ignore|noqa)'` must be `0`.

3. **Run the full suite before committing**, not the focused subset.

4. **Compare Ruff counts per touched file against `HEAD`**, not just the
   total. Use `git show HEAD:<path> | ruff check --stdin-filename <path>`.

5. **Never accept a delegated worker's numbers.** Re-derive them.

### Gotchas that will bite you

- **`AsyncMock` is a defect blindspot.** It accepts *any* attribute, so a
  call to a nonexistent method is indistinguishable from a valid one. This
  is how `phase4/portfolio_composer.py` calls three methods that do not
  exist without any test noticing.
- **Never blanket-replace `dict` → `dict[str, Any]`.** It zeroes the same
  error count while destroying the type information the annotation exists
  to provide. Read each body and infer the real type.
- **`knowledge/models.py` appears to have zero errors only because it
  lacks `from __future__ import annotations`.** The missing-`Any` import
  problems there are masked, not absent.
- **`robustness/retry_policy.py` takes `Callable[[], Awaitable[Any]]`, not
  `Awaitable[Any]`** — its body *calls* `coro()`. Contrast
  `circuit_breaker.call`, which awaits the object directly. Two
  similar-looking signatures, opposite contracts.
- **`valid-type` counts are the sharpest bug detector in the whole
  campaign.** Every single one was a real defect. Check it early.
- Deleting dead code frequently removes lint violations too, and can
  orphan an import. Re-check `F401` after any deletion commit.

---

## 4. Decisions required (blocking mypy → 0)

These four cannot be resolved by typing. Each needs a human call.

### 4.1 `phase4/portfolio_composer.py` — unwired prototype

`portfolio_composer.py` calls `load_strategy`, `recompute_portfolio` and
`save_portfolio` on `AsyncSQXClient`. **None of the three exist** in
`phase4/http_client.py`. It is not a `build_pipeline` stage; `AsyncMock`
hides the gap in tests.

- **Option A — re-route to the file-based `PortfolioMaster` flow.** This
  matches what `CommandDispatcher`'s own docstring already describes.
  Recommended.
- **Option B — keep the prototype and add `# type: ignore`.** Rejected:
  it suppresses the signal without fixing anything.

Chosen direction: attack the mechanical errors first, define the portfolio
contract separately. Still open on A-vs-B.

### 4.2 `costs/collector.py` — phantom required parameter

`get_recent_slippage(self, symbol: str)` **requires** a `symbol` that its
body never reads (line ~54 returns the profile slippage, ignoring the
argument). But `guardian/execution.py:244` calls it with **zero**
arguments, and the class docstring documents the zero-arg form.

Latent `TypeError`. Decide: make `symbol` optional, or drop it, or change
the call site.

### 4.3 `reporting` `--benchmark` — dead feature

`cli.py:54,57` loads the CSV into a local `benchmark_equity` that is
**never read** (AST-verified: zero loads).
`ReportConfig.benchmark_equity` is never assigned anywhere in live source,
so `generator.py`'s `e.timestamp` access on a `dict` can never fire today.
Wire it up (and fix the dict-vs-attribute mismatch) or delete the feature.

### 4.4 `knowledge/store.py` `query()` signature

The dead duplicate accepted a `filters` argument; the live one does not.
Verified: **no caller anywhere passes `filters`**, so nothing regressed
when it was dropped. Flagging only so it is a conscious choice.

---

## 5. Remaining work, in recommended order

### Step 1 — `attr-defined` (55) and `name-defined` (36)

The highest bug-density categories remaining. `name-defined` already
surfaced one real latent bug (`providers.py:65` annotates `-> datetime`
while `datetime` is imported only *inside* the function, so
`typing.get_type_hints()` would raise). Expect more.

Expect `PortfolioComposer` to surface here.

### Step 2 — `arg-type` (95), `assignment` (53), `call-arg` (48)

The bulk of the remaining count (196 total). These are a mix of real bugs
and genuine stub gaps — separate them before fixing. Watch for
`reporting/cli.py:151,152,169`, which passes `str` where the models declare
`datetime`; the CSV really does yield strings, so the fix is a parse step,
not an annotation.

### Step 3 — `no-any-return` (35), `return-value` (20), `union-attr` (19)

Mostly narrowings once the above land. One known pre-existing case:
`reporting/models.py:134` `is_successful()` declares `-> bool` but returns
`Literal[False] | Path | None`.

### Step 4 — the long tail (44 total)

`misc` 14, `index` 7, `operator` 6, `typeddict-item` 6, `call-overload` 4,
`func-returns-value` 3, `var-annotated` 3, `dict-item` 3,
`import-not-found` 2, `unused-coroutine` 2, `list-item` 1.

`func-returns-value` (3) means a `return` inside a generator or `__init__`
— always a real bug. `unused-coroutine` (2) means an unawaited coroutine.
Handle those two first in this step.

### Step 5 — Ruff, 868 errors

Deliberately untouched so far. Only `F401` and formatting were in scope.
The distribution:

| Count | Rule | Note |
|---|---|---|
| 217 | `BLE001` blind-except | needs a decision per site; cannot be blanket-fixed |
| 142 | `RUF012` mutable-class-default | use `ClassVar` |
| 103 | `PLC0414` useless-import-alias | **see below** |
| 67 | `I001` unsorted-imports | auto-fixable |
| 48 | `S110` try-except-pass | judgment per site |
| 45 | `F841` unused-variable | auto-fixable |
| 37 | `F821` undefined-name | **real bugs — check each** |
| 26 | `DTZ005` naive `datetime.now()` | needs a timezone decision |
| 19 | `RUF059` unused unpacked variable | auto-fixable |
| 16 | `C408` unnecessary dict/list call | auto-fixable |

**`PLC0414` is a direct consequence of our own F401 work.** The 355 `F401`
errors were largely PEP 484 implicit re-exports (`from x import y` with no
importer in the file), fixed by writing `from x import y as y`. That is the
correct PEP 484 idiom, but Ruff's default rule set flags it as a useless
alias. The alternative is explicit `__all__` membership. Pick one
consistently — do not leave the codebase half-`as`-aliased and
half-`__all__`. 73 of the 103 are in `quantlab/`, the rest in `tests/`.

### Step 6 — unblock the lint gate

`.github/workflows/ci.yml` currently carries `continue-on-error: true` on
the lint job. **Remove it only once Ruff and mypy are both at zero**, then
confirm a full green CI run.

`Integration Tests (SQX)` stays deliberately disabled — it references a
repository that never matches and `SQX_*` assets are gitignored.

---

## 6. Commit conventions

- Conventional Commits, no AI attribution and no `Co-Authored-By`.
- Keep slices at **≤400 changed lines** where possible. The formatter phase
  had two unavoidable exceptions: single files of 767 and 401 lines.
- Tests and documentation travel in the same work unit as the code.
- `main` has no branch protection. Never force-push.

Each slice in this campaign records the baseline→after delta, the
per-category no-regression check, the suppression check, and the test count
in its commit message. Keep doing that — it is what makes the campaign
auditable.
