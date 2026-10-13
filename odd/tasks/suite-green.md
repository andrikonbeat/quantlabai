# suite-green — remediate the 64 pre-existing suite failures

Branch: `fix/suite-green` (from `feature/gap-remediation` @ `ce3e882`).
Scope: the failures L15 recorded as baseline, explicitly outside the ten gaps of
`odd/tasks/gap-remediation.md`. Seven independent root causes, no product feature work.

## Specs

S1. The suite MUST be green under the project `.venv`, invoked from the branch root:
    `SQX_FORCE_MOCK=1 .venv/bin/python -m pytest -q` → **`0 failed`**.
    Out of scope by explicit user decision: the 2 collection errors caused by the
    untracked T9 RED modules (`sdk/tests/quantlab/jforex/test_strategy_bridge.py`,
    `..._integration.py`), which fail at import with
    `ImportError: cannot import name 'BridgeError' from 'quantlab.jforex.strategy_bridge'`
    and belong to T9, not to this feature.

S2. `scikit-learn` MUST be declared in `sdk/pyproject.toml` so a clean install (CI,
    which pins Python 3.11 and has no out-of-band packages) can run
    `sdk/tests/optimization/`. Today `sdk/quantlab/optimization/surrogate.py`
    raises `ImportError("scikit-learn is required for GaussianProcessSurrogate. "
    "Install with: pip install scikit-learn")` and declares nothing.

S3. The Python 3.14 hard guard MUST be removed. Verbatim user instruction:
    "Usa el la version de Pyhton que necesita y si el guard no es necesario quitalo".
    Evidence that it is not necessary:
    - `git show main:sdk/quantlab/cli/main.py` has no guard, so the CLI tests passed
      on Python 3.14 before this branch introduced it (commits `725f2c6`, `9f3f31d`).
    - `README.md:113` states: "**Python 3.11+** (CI pins 3.11; the project is developed
      and verified on 3.14)" — the guard contradicts the documented platform.
    - The `sdk/quantlab/sqx/sections.py` companion "workaround" is a no-op: its
      module-level sentinel `_MISSING` is never referenced.
    Current behaviour: `sdk/quantlab/cli/main.py:1279-1285` returns 1 before
    `build_parser()`, printing to stderr:
    `Error: Python 3.14 not supported — compiler bug inverts conditional jumps` /
    `Use Python <= 3.13 instead.`

S4. `run_javac` MUST return a `CompileReport` when javac exits non-zero, so that
    `CompilerPipeline.compile` reaches its own `if not report.ok:` branch and raises
    `CompileError(..., report=report, history=[...])`. It MUST NOT propagate
    `subprocess.CalledProcessError`. Today `sdk/quantlab/compiler/compiler.py:106`
    passes `check=True`, making the structured-report path at line 189 dead code.

S5. `sdk/tests/test_cli.py::TestCrossPlatform::test_windows_binary_naming` MUST patch the
    symbol `sdk/quantlab/cli/runner.py` actually resolves the binary with —
    `quantlab.cli.runner.resolve_sqcli_path` — and MUST assert an observable effect.
    It currently patches `quantlab.cli.runner.get_sqcli_binary`, which only works if
    `runner.py` re-exports an unrelated helper.
    Evidence that the test, not the code, is stale:
    - `73acf01`, which created `runner.py`, imported both `get_sqcli_binary` and
      `resolve_sqcli_path` but only ever called the latter.
    - `ae4ef3f` ("lint cleanup + env normalization + 4 product decisions") dropped the
      unused `get_sqcli_binary` import as dead code (F401). That is the correct change:
      `get_sqcli_binary()` returns the binary *name* and belongs to
      `quantlab.tools.platform`, where it is already covered by
      `sdk/tests/test_platform.py:37,41`.
    - The eight other patch sites in the same file (lines 115, 122, 130, 147, 162, 201,
      218, 316) already patch `quantlab.cli.runner.resolve_sqcli_path`.
    - The failing assertion is a no-op: `assert platform.system() or True`.
    Re-adding `get_sqcli_binary` to `runner.py` would restore a dead import to satisfy an
    assertion that checks nothing, so this task fixes the test instead of the code.

S6. The `_extract_campaigns` legacy fallback in `sdk/quantlab/knowledge/query.py` MUST
    append one `CampaignSummary` per indexed entry. Today the `if metrics:` block and
    `campaigns.append(...)` are indented at the `for dir_name` level instead of the
    inner `for rel_path` level, so the loop finishes with `info` bound to the LAST entry
    and exactly one campaign is produced per directory. Observable effect:
    `tests/dashboard/test_api.py::TestStatsEndpoint::test_stats_returns_aggregated_spec_fields`
    sees `sharpe_mean == 2.0` where the two seeded campaigns (1.0 and 2.0) require `1.5`.

S7. `LiveOpsStage.provides` is `["live_ops_status", "live_pool_status"]` after the C10
    pool extension; the stale expectation `== ["live_ops_status"]` in
    `tests/pipeline/test_stage_io_contracts.py:100` MUST be synced. Adding a provided key
    does not break the downstream `requires` contract.

S8. The installer overlay MUST register the 14 `quantlab-phase-*` agents plus the
    guardian family so the live `~/.config/opencode/opencode.json` satisfies
    `tests/test_orchestrator_prompt.py`. Per-phase contract (from
    `TestPhaseAgentRegistration`): `mode == "subagent"`, `permission.task` deny-first
    (`"*": "deny"` and `"quantlab-*": "allow"`), question tool allowed, prompt reference
    present, bash scoped to `sdk/quantlab/pipeline/*` and `sdk/quantlab/campaign/*`.
    Also required: `quantlab-campaign` registered as subagent (today `mode: "standard"`
    in `installer/internal/opencode/overlay.json`, which declares only 6 agents and zero
    phase agents), the guardian orchestrator registered primary+visible, the guardian
    alert/replacement delegates registered hidden subagents with inline prompts, and the
    orchestrator task allowlist referencing campaign/guardian/guardian-orchestrator.
    The 14 prompt sources already exist at `ai/opencode/agents/phase-*.md`.
    Verbatim user authorization: "Autorizo escribir en `~/.config/opencode/`".

S9. The `pytest.ini` `[env]` block MUST be live. Today it is dead weight:
    `pytest-env` is not declared or installed, so pytest warns
    `PytestConfigWarning: Unknown config option: env` and `QUANTLAB_SQX_USE_HTTP=1`
    and `QUANTLAB_JFOREX_BRIDGE=1` are never exported, while
    `.github/workflows/ci.yml` does set them. Local runs therefore execute in a
    different mode than CI. Verbatim user decision: "Todo: deps + overlay + pytest.ini".

S10. Every task closes with a work-unit commit on `fix/suite-green`. The user's
     parallel work-in-progress MUST never be staged: the user is editing this clone
     concurrently. Commit only the paths this feature owns.

S11. The user's checkout MUST stay on `feature/gap-remediation`. All work happens in the
     isolated worktree `.worktree-suite-green`, so the user's active edits to
     `sdk/quantlab/exploration/params_schema.py` are never disturbed.

## Tasks

| ID | Spec | Task | Route | Commit |
|----|------|------|-------|--------|
| T1 | S3  | Remove the fabricated Python 3.14 guard (`cli/main.py`, `sqx/validator.py`, `sqx/sections.py` sentinel) → 14 failures | inline | `6b4474e` |
| T2 | S4  | Restore the compiler error path (`check=False` in `run_javac`) → 9 failures | inline | `4b0e989` |
| T3 | S5  | Fix the stale patch target in `test_windows_binary_naming` (test-side) → 1 failure | inline | `7b8cd08` |
| T4 | S6  | Fix the `_extract_campaigns` fallback indentation → 1 failure | inline | `05ceefa` |
| T5 | S7  | Sync the `LiveOpsStage.provides` expectation → 1 failure | inline | `85d00e2` |
| T6 | S2, S9 | Declare `scikit-learn`; make the `pytest.ini` env block live → environment/CI parity | inline | pending |
| T7 | S8  | Register the 14 phase agents + guardian family in the overlay and regenerate the live config → 23 failures | inline | pending |
| T8 | S1  | Final full-suite gate under `.venv`; record the delta against baseline | inline | pending |

Measured baseline: **64 failed / 4584 passed / 60 skipped** under `/usr/bin/python3`
(3.14.7, no `scikit-learn`); **49 failed / 272 passed** for the failing subset under the
project `.venv` (3.14.7, `scikit-learn` 1.9.1). Target after T1–T7: `0 failed`.

## Log

L1 (user's original request, quoted from the session's compaction record):
> Corregir todos los tests que están fallando en el repositorio `quantlab-ai` (rama `feature/gap-remediation`).

L2 (user's scope for this turn, quoted from the session's compaction record):
> Corregir las **72 fallas pre-existentes** de la suite completa que quedaron fuera del plan `odd/tasks/gap-remediation.md` (L15 las registra como baseline y aclara explícitamente "no task claims them yet"). Es un scope nuevo respecto de los 10 gaps originales.

L3 (user decisions, verbatim from the decision batch):
- Gate: "Gate con `.venv` + declarar scikit-learn"
- Guard: "Usa el la version de Pyhton que necesita y si el guard no es necesario quitalo"
- Live config: "Autorizo escribir en `~/.config/opencode/`"
- Branch: "Rama nueva desde `feature/gap-remediation`" (revised after this branch's
  evidence showed the 3.14 guard exists only on the feature branch, not on `main`)
- Extras: "Todo: deps + overlay + pytest.ini"

L4 (evidence — interpreter determines the baseline): with `/usr/bin/python3` the suite
reports `64 failed, 4584 passed, 60 skipped in 399.27s`; the 15 `sdk/tests/optimization/`
failures vanish under `.venv` (33s run: `49 failed, 272 passed`). `.venv` is Python
3.14.7 and is the environment AGENTS.md documents ("local `.venv` 3.14.4"). The L15
baseline of 72 failures was measured on the wrong interpreter.

L5 (evidence — why 23 failures are one root cause): `installer/internal/opencode/overlay.json`
declares 6 agents (`quantlab-orchestrator` primary, `quantlab-campaign` **standard**,
`guardian-orchestrator` primary, `quantlab-guardian`/`-alert`/`replacement` subagent) and
zero `quantlab-phase-*`. The live `~/.config/opencode/opencode.json` likewise has 6.
All 14 `ai/opencode/agents/phase-*.md` prompt sources already exist.

L6 (evidence — measured split by branch). Both trees run under `.venv` with
`SQX_FORCE_MOCK=1`. `main` @ `1c6313e`: `34 failed, 4376 passed, 36 skipped, 4 errors`.
`feature/gap-remediation` @ `ce3e882`: `49 failed, 272 passed` (failing subset only).
Set difference: 15 failures exist **only** on the feature branch, 4 errors exist **only**
on `main`, and 34 failures are common. The 34 common ones decompose exactly:

| Root cause | `main` | `feature/gap-remediation` | Common count |
|---|---|---|---|
| 6 — installer overlay registration | fails | fails | 23 |
| 2 — `run_javac(check=True)` | fails | fails | 9 |
| 3 — stale test patch target (`get_sqcli_binary`) | fails | fails | 1 |
| 4 — `_extract_campaigns` indentation | fails | fails | 1 |
| 1 — Python 3.14 guard | **passes** | fails | — |
| 5 — stale `LiveOpsStage.provides` expectation | **passes** | fails | — |
| 7 — undeclared `scikit-learn` | latent | latent | — |

23 + 9 + 1 + 1 = 34 ✓; 14 + 1 = 15 ✓. The 4 `main`-only errors are in
`tests/phase4/test_project_builder.py` and this branch already fixed them.

Correction to an earlier claim of mine in this session: root causes 2, 3, 4 and 6 exist
on `main`, but cause **5 does not** — the C10 pool extension that made the expectation
stale was added on this branch, so that failure is feature-branch-only, as is the guard.

L7 (incident, self-reported): while cleaning what I believed were untracked test
artifacts I ran `rm -rf knowledge/structured/bayesopt_* knowledge/deployment_failures/*.json`
and deleted **tracked** files. My own `echo "(vacio = no trackeados)"` misread a
non-empty `git ls-files` output. Restored immediately with `git restore knowledge/`;
verified 0 remaining deletions. Lost: only untracked, regenerable test output. Lesson:
never treat `git status --porcelain` presence as proof of untracked status when the check
command's output is being interpreted by hand.

L9 (T1 closed — code `6b4474e`, plan `c8dada1`): removed the guard from
`sdk/quantlab/cli/main.py` (`main()`), `sdk/quantlab/sqx/validator.py`
(`validate_spec_json()`), and the dead `_MISSING` sentinel plus its misleading
`parse_stop` docstring note in `sdk/quantlab/sqx/sections.py`.

RED observed first: `tests/phase4/test_cli_main.py sdk/tests/test_kb.py
sdk/tests/test_version.py tests/knowledge/test_kb_reverify_cli.py` → `14 failed,
78 passed`. After the fix, the same set plus `sdk/tests/sqx/test_sections.py` →
`115 passed, 1 skipped`.

Checked before editing: no test expects the guard (the only `3.14` matches under
tests are an unrelated float literal, `3.14159` in `test_project_builder.py`, and
unrelated docstrings about `Path.__new__` and ABC registration), and `_MISSING`
had exactly one occurrence in the whole tree — its own definition.

The `PytestConfigWarning: Unknown config option: env` from S9/T6 reproduced in this
run and is still open.

L10 (T2 closed — `4b0e989`): `run_javac` now passes `check=False`, so a failing javac
returns `CompileReport(exit_code=1, ...)` instead of raising `CalledProcessError`
before the report existed. RED: `tests/compiler/` → `9 failed, 40 passed`. GREEN:
`49 passed`.

Cross-cutting finding, outside this feature's scope (S1): the same `check=True` defect
is repeated four times in `sdk/quantlab/jforex/strategy_bridge.py` (lines 57, 76, 94,
112). That is precisely the module whose untracked T9 RED tests fail at import with
`ImportError: cannot import name 'BridgeError'`, so T9 is likely the same fix shape —
surface a structured error type instead of letting `CalledProcessError` escape.
Handoff note for the T9 owner; not a task here.

L8 (coordination): the user committed the T5 WIP concurrently during this session
(`f7b2247 feat(campaign): wire LLM generation monitor into run-flow`,
`ce3e882 docs(odd): record T5 closure, gate certification and the gap-2 drift measurement`)
and is actively editing `sdk/quantlab/exploration/params_schema.py`. HEAD moved from
`a1098af` to `ce3e882` mid-session. The remediation therefore branches from `ce3e882`
and runs in an isolated worktree (S11).

L11 (T3 closed — `7b8cd08`): the failure was test-side. `test_windows_binary_naming`
patched `quantlab.cli.runner.get_sqcli_binary`, a name that was only ever an incidental
re-export in that module: `73acf01` imported it alongside `resolve_sqcli_path` but called
only the latter, and `ae4ef3f` removed the unused import as dead code (F401).
`get_sqcli_binary()` returns the binary *name* and lives in `quantlab.tools.platform`,
covered by `sdk/tests/test_platform.py:37,41`. The eight other patch sites in
`test_cli.py` (lines 115, 122, 130, 147, 162, 201, 218, 316) all use
`resolve_sqcli_path`.

The test also asserted nothing at all (`assert platform.system() or True`), so restoring
the import would have recreated a dead symbol to satisfy a no-op. Fixed the test:
it now patches `resolve_sqcli_path` and asserts the observable effect — the resolved
path becomes argv[0] of the sqcli subprocess.

RED: the exact node failed with `AttributeError: <module 'quantlab.cli.runner'> does not
have the attribute 'get_sqcli_binary'`. GREEN: `sdk/tests/test_cli.py` → `25 passed`;
`sdk/tests/test_platform.py` → `11 passed` (unchanged, still owns the name helper).

L12 (T4 closed — `05ceefa`): in the legacy fallback of `_extract_campaigns`, the
`if metrics:` block and `campaigns.append(...)` were dedented to the level of the outer
`for dir_name` loop instead of the inner `for rel_path, info in ...` loop, so the block
ran once per directory using the last iteration's `campaign_id`/`tags`/`info`/`metrics`
and emitted a single campaign — the last one. The primary v6+ indexer path
(`index["campaigns"]`) is indented correctly, which is why only the legacy
`directories` fallback was affected.

`tests/dashboard/seed.py:13` writes exclusively to `directories.results` and never to
`campaigns`, which is what routes the dashboard through that fallback. Observed
`sharpe_mean == 2.0` (campaign-b alone) instead of `1.5`. GREEN after the fix:
`tests/dashboard/` + `sdk/tests/knowledge/` → `109 passed`, satisfying all six
aggregate assertions (1.5, 0.7071, -12.0, 0.55, 300, 2 campaigns).

L13 (T5 closed — `85d00e2`): `LiveOpsStage.execute()` publishes `live_pool_status` in
every return path — both the fail-closed branch with no `archive_bundle`
(`live_ops_stage.py:145,148`) and the normal branch (`:166,170`) — and `1168916`
extended `provides` to declare it. `main` still carries the pre-C10 single-item list, so
the stage is right and the expectation is stale. Also corrected the class docstring,
which advertised only `live_ops_status` two lines above a `provides` field listing both.
GREEN: `tests/pipeline/` + `tests/campaign/` → `281 passed`.

L14 (T6 evidence — `scikit-learn` is declared nowhere). `sdk/tests/optimization/`
exercises `optimization/surrogate.py`, whose sklearn imports are function-local and
guarded by `except ImportError` raising "scikit-learn is required ... Install with: pip
install scikit-learn" (`surrogate.py:108,116,148,151,261,264`). Those tests carry **no**
skip marker, so the canonical suite fails without sklearn. `grep` over
`.github/`, `sdk/pyproject.toml`, `pyproject.toml` and any `requirements*.txt` finds no
sklearn declaration at all, and CI's test job installs only `pip install -e "sdk[dev]"`
(`ci.yml:97`), so those tests fail in CI too — the local `.venv` merely masks it by
having sklearn 1.9.1 installed by hand. This is the same defect class the `dev` extra
already documents for `flask` and `plotly` ("`pip install -e "sdk[dev]"` produced an
environment that could not run the suite it was meant to enable"), so scikit-learn goes
in `dev`, not in the base dependencies: `surrogate.py` keeps degrading gracefully for end
users who never run the optimization phase.

L15 (out-of-scope finding, not a task): `ruff check sdk/quantlab/knowledge/query.py`
reports `F821 Undefined name 'KnowledgeStore'` at `query.py:494`. It is byte-identical at
`HEAD~1` and after T4, so T4 did not introduce it and neither did this feature. Recorded
for the user's disposition rather than fixed, because S1 keeps unrelated remediation out
of this feature.
