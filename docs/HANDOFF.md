# Handoff — Setting Up QuantLab AI on a New Machine

Everything needed to go from an empty computer to a working, verified
development environment. Follow the sections in order; each one assumes the
previous ones are done.

If you only want the short version, pick one:

**Guided (TUI)** — one command, prepares everything and drops you into the
installation wizard + onboarding guide:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/andrikonbeat/quantlabai/main/install.sh)"
```

**Autonomous** — same preparation, wizards skipped (CI / unattended):

```bash
curl -sSL https://raw.githubusercontent.com/andrikonbeat/quantlabai/main/install.sh | bash -s -- --no-wizard
```

**Manual** — the five lines the one-liner runs for the Python side:

```bash
git clone git@github.com:andrikonbeat/quantlabai.git
cd quantlabai
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -U pip && pip install -e "sdk[dev]"
SQX_FORCE_MOCK=1 python3 -m pytest -q
```

That is enough to run the entire test suite. Everything below is detail.

---

## 1. System requirements

| Requirement | Version | Needed for | Notes |
|---|---|---|---|
| Git | any recent | cloning | |
| Python | **3.11+** | the SDK and its tests | CI pins **3.11**; verified locally on **3.14.4** |
| pip | 26+ on Python 3.14 | installing | `python -m pip install -U pip` |
| Go | 1.23+ | `installer/` only | `go.mod` declares `go 1.23.0` |
| JDK + Android SDK | — | `app_movil/` only | see [section 11](#11-optional-build-units) |
| StrategyQuant X | build 144.2953 | **real** backtests only | machine-local, never committed |

Supported platforms: Linux and WSL are the primary target. Windows works via
WSL; `sqcli` and the SQX daemon are not natively supported there.

Disk: roughly **1.5 GB** for a full checkout including `.venv`, plus **~1.2 GB**
if you also install the StrategyQuant distribution.

## 2. Install

### One-command install (recommended)

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/andrikonbeat/quantlabai/main/install.sh)"
# Local clone alternative: ./install.sh [--no-wizard] [--dev] [--skip-tests]
```

The installer detects the OS, explains QuantLab and its dependencies,
guides OpenCode/SQX/JForex setup, verifies components, and leaves the
tree ready for the `quantlab-orchestrator` agent. (Absorbed from the
former `docs/INSTALL_INTERACTIVE.md`, 2026-10-10.)

### Manual install

```bash
git clone git@github.com:andrikonbeat/quantlabai.git
cd quantlabai

python3 -m venv .venv
source .venv/bin/activate          # Windows/WSL: .venv\Scripts\activate
python -m pip install -U pip

pip install -e "sdk[dev]"
```

**The virtualenv goes at the repository root, not in `sdk/`.** The Python
package is declared in `sdk/pyproject.toml`, but the canonical test suite is
defined by root-level `pytest.ini` (`testpaths = tests sdk/tests`) and
`conftest.py`. A venv in `sdk/` works for importing the package but not for
running the suite the way CI does.

`[dev]` is the extra that pulls in `pytest`, `pytest-asyncio`, `ruff`, and
`mypy`. Without `pytest-asyncio` the suite fails with unhandled coroutines,
because `pytest.ini` sets `asyncio_mode = auto`.

There is **no committed lockfile**. Resolution follows the ranges declared in
`sdk/pyproject.toml`. If you hit `ModuleNotFoundError` for something that is
declared there, your environment is older than a dependency addition — re-run
the install line above rather than pinning by hand.

## 3. Configure

### Environment variables

```bash
cp .env.example .env
$EDITOR .env
```

`.env.example` documents every supported variable with section comments. Only
one is usually required:

| Variable | Purpose | Default if unset |
|---|---|---|
| `SQX_INSTALL_PATH` | StrategyQuant distribution root | discovery fails; mock mode still works |
| `SQX_PORT` | port the SQX daemon binds | `5050` |
| `SQX_LICENSE` | SQX license key | real runs fail |
| `QUANTLAB_KNOWLEDGE_ROOT` | Knowledge Lake location | `knowledge/` |
| `OPENCODE_API_KEY` | LLM access for the agent phases | agents cannot call a model |

`OPENCODE_API_KEY` and `SQX_LICENSE` are secrets. `.env` is git-ignored —
never commit it, and never paste its contents into an issue or a chat.

### StrategyQuant X

QuantLab discovers the distribution through `SQX_INSTALL_PATH`, then
`--sqx-path`, then `SQX_PATH`. Inside that root it expects `sqcli` and a
bundled JDK at `j64/`.

```bash
export SQX_INSTALL_PATH="/path/to/your/SQX_install_root"
export SQX_PORT=5050
```

The distribution is a **local tool dependency and is never committed**
(`.gitignore` excludes `assets/SQX_*`). A fresh clone will not contain it, and
CI cannot provision it. Everything in this repository therefore runs in
`SQX_FORCE_MOCK=1` mode, which is exactly how the test suite is executed.

### Agent prompts and skills (optional)

`ai/opencode/` is the single source of truth for agent prompts and skills. The
live copies under `~/.config/opencode/` are **generated artifacts**. If you
work on the agents, sync them:

```bash
python3 ai/opencode/sync_prompts.py      # write
python3 ai/opencode/sync_skills.py
python3 ai/opencode/sync_prompts.py --check   # exit 1 on drift
python3 ai/opencode/sync_skills.py --check
```

Two tests assert parity between the repo and your live `~/.config/opencode/`
tree, resolved via `Path.home()`. On a fresh machine that tree does not exist
yet, and those tests still **pass** — verified on a clean clone with no live
config tree present. Running the sync first is still recommended, because it is
what makes those assertions meaningful rather than vacuous, and CI runs it
explicitly before the suite.

## 4. Verify the install

```bash
SQX_FORCE_MOCK=1 python3 -m pytest -q
```

Expected on a clean clone with no StrategyQuant data present:
**4134 passed, 19 skipped, 0 failed** (~6 minutes). On a machine that has the
local SQX data bundle, one further test runs and you see 4135 passed / 18
skipped. Both are green; the difference is machine-local data, not code.

`SQX_FORCE_MOCK=1` is mandatory — without it the suite tries to bind the real
SQX daemon on port 5050 and hangs or fails.

Then confirm the optional build units, if you need them:

```bash
cd installer && go build ./... && go test ./... -short && cd ..
cd sdk && python -m ruff check . && python -m mypy quantlab --strict && cd ..
```

## 5. How to run it

### Dry run, no StrategyQuant required

The whole pipeline works in mock mode:

```bash
SQX_FORCE_MOCK=1 python3 -m quantlab.cli campaign run-flow --help
SQX_FORCE_MOCK=1 python3 -m quantlab.cli pipeline list
SQX_FORCE_MOCK=1 python3 -m quantlab.cli knowledge rebuild-index
```

### The 14-phase campaign flow

```bash
python3 -m quantlab.cli campaign run-flow --json
```

The flow runs in canonical order:

```
research → hypothesis → config → review → dispatch → monitor → retest
        → optimize → portfolio → compile → deploy → demo → archive → live-ops
```

The order is defined once, in `PHASES` at `sdk/quantlab/campaign/flow.py`, and
a test extracts the same literal from `ai/opencode/agents/campaign.md` and
compares them — so the prompt and the code cannot drift apart.

To run a single phase in isolation:

```bash
python3 sdk/quantlab/campaign/phase_runner.py --phase <name> --directive '<json>'
```

> `_run_campaign.py` was retired. `campaign run-flow` is the only campaign
> entry point. Any harness or doc still pointing at `_run_campaign.py` is wrong.

### Human gates are fail-closed

Gates resolve through files under `/tmp/sqx-gates/{campaign_id}/`. The pipeline
writes `.pending.json`, the agent presents it, and your decision is written back
as `.decision.json`. An unanswered gate **holds** — it never auto-approves.
`HUMAN_APPROVE_CONFIG`, `HUMAN_APPROVE_DEPLOY`, `HUMAN_APPROVE_DEMO`, and
`HUMAN_APPROVE_ARCHIVE` always block a dispatch.

## 6. How to test

```bash
# Full canonical suite — from the repo ROOT
SQX_FORCE_MOCK=1 python3 -m pytest -q

# One area
SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/
SQX_FORCE_MOCK=1 python3 -m pytest -q sdk/tests/gates/

# Flow-integrity contract on its own — never let an early abort skip it
SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/
```

There are **two test trees**, `tests/` and `sdk/tests/`, and root
`pytest.ini` collects both. CI runs the same root suite, so a green CI run and
a green local run mean the same thing. Run the suite from the root; running it
from `sdk/` silently collects only half of it.

## 7. Build

Nothing needs compiling for the Python SDK — it runs from the editable install.

```bash
cd installer && go build ./...     # Go installer
cd app_movil/quantlabai && ./gradlew assembleDebug    # Android app
docker compose build                # API + SQX + Postgres + Redis
```

## 8. What works right now

Verified on this machine against the commit recorded in
[STATE.md](STATE.md):

- **Full Python suite** — 4380 passed / 37 failed / 29 skipped / 4 errors
  (measured 2026-10-10 on `d0c5299`, `SQX_FORCE_MOCK=1`; triage in
  [PROJECT_STATE.md](../sdd/PROJECT_STATE.md) §3 — 23 live-config drift, the rest
  environmental or pre-existing on HEAD, none from doc/SDD changes).
- **Go installer green** — `go build ./...` clean, `go test -short ./...`
  363 passed in 19 packages (network integration skips under `-short`).
- **Lint and types** — `ruff`, `mypy --strict`, and `pytest-asyncio` are all
  declared and installed; the CI `lint` job can actually report a verdict.
- **14-phase campaign flow** — enforced at runtime by
  `assert_flow_segments()` in `sdk/quantlab/cli/campaign_commands.py`, which
  runs before any stage executes.
- **Human gates** — nine registered policies, fail-closed.

## 9. Known problems and limitations

Read these before changing anything.

- **CI does not run the StrategyQuant integration job.** `.github/workflows/ci.yml`
  gates `integration` on `github.repository == 'quantlab/quantlab-ai'`, but the
  remote is `andrikonbeat/quantlabai`; the condition can never be true. The job
  is also broken independently — it `cd`s into `assets/SQX_144_2953_linux_20260601`,
  which is git-ignored and absent on a fresh checkout. **The guard is left
  deliberately wrong**: correcting only the repository name would turn a silent
  no-op into a hard CI failure. It carries an explicit
  `DO NOT ACTIVATE WITHOUT AN OWNER DECISION` comment. Do not "fix" the repo
  name without first provisioning SQX in CI.
- **`DataManager` is Dukascopy-only** (FX M1/M5/H1). Crypto, CSV, and yahoo
  datasources raise `NotSupportedError`.
- **Orphaned SDK modules**, pending triage or removal: `sdk/quantlab/broker/`,
  `evolution/`, `health/`, `mcp/`.
- **Three duplicate `PhaseResult` types** — `phase4/models.py`,
  `campaign/delegation.py`, `substrate/executor.py` — deliberately aliased on
  import rather than consolidated (AD-6).
- **Two test trees** (`tests/` + `sdk/tests/`) — inherited duplication;
  `testpaths` unifies collection but the duplication remains.
- **No Python lockfile** — dependency resolution is range-based.
- **Git LFS is configured but unused.** `.gitattributes` declares
  `filter=lfs` for `*.pdf` and `assets/**`, but no LFS object is tracked and
  `assets/**` is git-ignored. If you add a PDF, install `git-lfs` first.
- **`docs/sqx-builder-config/SQX Builder Config.md` has a load-bearing
  filename.** The KB seeder pins it as `DEFAULT_DOC_PATH` and ~15
  `evidence_ref` entries under `knowledge/structured/sqx-kb/**` cite it.
  Renaming it breaks the KB suites.
- `LicenseManager` is exported but unused, and
  `PipelineRunner.run_with_gates()` does not handle `GateTimeoutError`.

## 10. Git and GitHub

- **Remote**: `git@github.com:andrikonbeat/quantlabai.git` (private).
- **Default branch**: `main`.
- **Clone with SSH** — the deploy key on this machine is SSH-based. Over HTTPS
  you need a PAT with `repo` scope.
- **Sync before starting**: `git fetch --all --prune`.

### Working on a change

This project uses **SDD** (spec-driven development): work is tracked as a
change under `sdd/changes/<name>/` carrying a proposal, specs, design, and
tasks, and archived under `sdd/changes/archive/YYYY-MM-DD-<slug>/` when
done. `sdd/specs/` is the normative contract layer that `tests/` assert
against.

Keep changes reviewable: **≤400 changed lines** per work unit, one logical
commit, and keep code with its tests and docs. Branches are named
`feat/…`, `fix/…`, `chore/…`.

### Do not

- Do not rewrite published history or force-push `main`.
- Do not commit `.env`, `.venv/`, `knowledge/raw/`, `assets/SQX_*`,
  `deploy/`, `reports/`, or `_output/` — all git-ignored by design.
- Do not hand-edit anything under `~/.config/opencode/`; edit
  `ai/opencode/` and run the sync scripts.
- Do not register a human-gate policy and assume it blocks anything. A policy
  only blocks if a `build_pipeline` stage resolves it. `HUMAN_APPROVE_REPLACEMENT`
  is registered but no stage invokes it yet.

## 11. Optional build units

### Go installer

```bash
cd installer
go build ./...
go test ./... -short
make            # see installer/Makefile for packaging targets
```

### Android companion app

```bash
# Point the build at your SDK — local.properties is git-ignored
echo "sdk.dir=/path/to/Android/Sdk" > app_movil/quantlabai/local.properties

cd app_movil/quantlabai
./gradlew assembleDebug
```

The Gradle wrapper JAR is committed, so a fresh clone can build without a
pre-installed Gradle. `ANDROID_HOME` is deliberately **not** set in
`gradle.properties` — a hardcoded SDK path breaks the build on any other
machine.

### Docker

```bash
docker compose up
```

Brings up the API, an SQX daemon, Postgres, and Redis. The image requires the
StrategyQuant assets, which are not in the repository.

## 12. Repository layout

```
quantlabai/
├── sdk/                 Python package (pyproject.toml here)
│   ├── quantlab/        dsl, translate, cli, readers, stats, knowledge,
│   │                    data, agents, campaign, gates, cfx, phase4, pipeline…
│   └── tests/           SDK test tree
├── tests/               Root test tree  (both are collected)
├── docs/                All documentation, indexed in docs/index.md
│   ├── HANDOFF.md       This file
│   ├── STATE.md         Point-in-time project status
│   └── index.md         Index of every doc
├── sdd/            SDD artifacts
│   ├── specs/           Normative capability specs (the contract layer)
│   └── changes/         Active changes; archive/ holds completed history
├── ai/opencode/         Repo-canonical agent prompts + skills (source of truth)
├── installer/           Go installer
├── app_movil/           Android companion app
├── knowledge/           Knowledge Lake (tracked: index.yaml, structure, KB)
├── infra/               DB init schema used by docker-compose
├── pipelines/           Pipeline YAML definitions
├── strategies/          JForex 4 strategy templates
├── examples/            Sample pipeline.yaml / research-config.yaml
├── pytest.ini           Canonical testpaths (tests + sdk/tests)
├── AGENTS.md            Project contracts the repo enforces
└── .env.example         Every supported environment variable
```

Git-ignored and machine-local — do not expect these after a clone:
`.venv/`, `assets/SQX_*`, `deploy/`, `reports/`, `_output/`, `knowledge/raw/`,
`.codegraph/`, `knowledge/timeseries/`.

## 13. Where the project actually stands

See **[STATE.md](STATE.md)** for the point-in-time snapshot, the active SDD
changes, and known debt. It deliberately avoids restating counts that drift, and
points at `git log` and CI for live truth.

## 14. Next steps for a new contributor

1. Read [STATE.md](STATE.md), then [PRD.md](PRD.md) for intent.
2. Read [guides/running-campaigns.md](guides/running-campaigns.md) for the
   operational path.
3. Get the suite green on your machine **before** changing anything.
4. Pick an active change from `sdd/changes/`, or open a new one with a
   proposal before writing code.
5. Keep the 14-phase order and the gate contracts intact — both are enforced by
   tests, not by convention.