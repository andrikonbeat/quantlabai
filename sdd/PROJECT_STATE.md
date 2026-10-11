# QuantLab AI — Project State (canonical)

> **This file is the single canonical record of project state, changes, and
> migrations.** It unifies what was previously scattered across
> `docs/STATE.md` (snapshot), `docs/CHANGELOG.md` (release history),
> `docs/LINT-CLEANUP-HANDOFF.md` (lint/type campaign), and the per-change
> `apply-progress.md` / `archive-report.md` files.
>
> - `docs/STATE.md` is kept as a thin compatibility shim (required by
>   `tests/test_campaign_docs.py`) and points here.
> - `docs/CHANGELOG.md` is kept as an immutable historical record — changelog
>   entries are never rewritten; new history is recorded here and in
>   `sdd/changes/archive/*/archive-report.md`.
> - `docs/PRD.md` (product contract) and `docs/HANDOFF.md` (machine-setup
>   procedure) stay separate and are linked from §9.
>
> **Live truth beats any number on this page.** Verify with the commands in
> §3 before trusting a count.

| Field | Value |
|-------|-------|
| Last reconciled | 2026-10-10 |
| Branch | `main` |
| Commit | `d0c5299` |
| Active SDD changes | 0 (none — `quantlab-installer` closed 2026-10-10) |
| Archived SDD changes | 53 under `sdd/changes/archive/` |
| Normative capability specs | 107 under `sdd/specs/` |
| Explorations | 2 under `docs/research/explorations/` |

## 1. What this project is

QuantLab AI is a Python SDK that turns StrategyQuant X (SQX) into an
AI-directed trading research engine: OpenCode acts as research director, SQX
is the computation engine, and all work is governed by SDD (spec-driven
development). A campaign runs a **14-phase** loop from a trading idea to
strategies under live Guardian supervision.

**Stack**: Python 3.11+ (CI pins 3.11; local `.venv` runs 3.14.4), Pydantic,
pandas/numpy, httpx, MCP, OpenAI SDK. `installer/` is Go 1.23, `app_movil/`
is Kotlin + Jetpack Compose. External tools: SQX (`sqcli`, `.cfx`), JForex 4,
Dukascopy-only market data, JCloud deployment.

## 2. Where everything lives

```
sdd/
├── PROJECT_STATE.md        # this file (canonical state/changes/migrations)
├── config.yaml             # SDD router config (sdd/campaign/cli/dashboard/knowledge)
├── changes/                # active changes (proposal/design/tasks/specs/…)
└── changes/archive/        # completed history (YYYY-MM-DD-<slug>/)
sdd/specs/ …                # (i.e. sdd/specs/) normative capability specs
docs/
├── PRD.md                  # product contract (vision, 14 phases, 11 slices S1–S11)
├── HANDOFF.md              # new-machine setup procedure (start here on new hardware)
├── STATE.md                # thin shim → points here (kept for tests)
├── CHANGELOG.md            # immutable release history (never rewritten)
├── LINT-CLEANUP-HANDOFF.md # lint/type campaign tracking + 4 blocking decisions
├── index.md                # index of every doc under docs/
└── research/explorations/  # pre-SDD exploration documents (2)
```

Pre-SDD explorations (ordered, no loose files):

| Exploration | Topic | Led to |
|-------------|-------|--------|
| `docs/research/explorations/multi-agent-research-system.md` | Agent↔SDK mapping, pipeline-vs-actor architecture, gates, Engram topics | `2026-10-07-multi-agent-research-system` (archived) |
| `docs/research/explorations/research-agent-enhancements.md` | Multi-source research, LLM hypothesis generation, Knowledge Lake semantic search | `2026-10-09-research-agent-enhancements` (archived) |

## 3. Live status — sources of truth

```bash
git log --oneline -20              # what actually landed, and when
git status                         # is the tree clean
git branch --show-current          # which branch you are on
ls sdd/changes/                    # active changes
ls sdd/changes/archive/ | wc -l    # archived count
ls sdd/specs/ | wc -l              # normative spec count
SQX_FORCE_MOCK=1 python3 -m pytest -q   # full suite (mandatory flag)
gh run list --limit 5              # CI is authoritative for lint/types/sdk tree
```

| Question | Authoritative source |
|----------|---------------------|
| What is implemented? | `git log` + `sdd/changes/archive/YYYY-MM-DD-<slug>/` |
| Is the suite green? | `gh run list` (CI); local full-suite command above |
| Which changes are in flight? | `ls sdd/changes/` (active) vs `sdd/changes/archive/` |
| What is the code contract? | `sdd/specs/`, asserted by `tests/` |
| What do the agents actually do? | `ai/opencode/` (repo-canonical; live copies are generated) |

**Last measured suite** (2026-10-10, HEAD `d0c5299` plus the uncommitted SDD-close
tree; `SQX_FORCE_MOCK=1` from the repo root): **4380 passed, 37 failed,
29 skipped, 4 errors** in ~410s. Without the flag the suite binds the real SQX
daemon on port 5050 and hangs. Triage (all pre-existing on HEAD, none from
doc/SDD changes — the failing files are untouched by the working tree):

| Failures | Cause |
|----------|-------|
| 23 `test_orchestrator_prompt.py` | live-config drift (`~/.config/opencode` vs repo) |
| 9 compiler/fixloop/jforex-routing | external-JDK behavior on this machine |
| 3 cfx reader/writer | machine-local SQX fixture archives absent |
| 1 dashboard stats (`2.0 == 1.5`), 1 sdk cli windows naming | code/test drift |
| 4 errors `phase4/test_project_builder.py` | fixture-setup, crosscheck post-merge fallout |

Prior snapshot (2026-10-03): 4135 passed, 18 skipped, 0 failed in ~336s.

## 4. Campaign flow (14 phases, fail-closed gates)

Canonical order (`PHASES` in `sdk/quantlab/campaign/flow.py:33`, mirrored in
`ai/opencode/agents/campaign.md` — a test compares the two so they cannot
drift; enforced at runtime by `assert_flow_segments()` before any stage
executes):

```
research → hypothesis → config → review → dispatch → monitor → retest
        → optimize → portfolio → compile → deploy → demo → archive → live-ops
```

`retest`/`optimize` are conditional (only when the matching DSL block is
present). Every human gate is **fail-closed (HOLD)** — unanswered gates never
auto-approve. The gates that always block a dispatch:

| Gate | Blocks |
|------|--------|
| `HUMAN_APPROVE_CONFIG` | dispatch to SQX |
| `HUMAN_APPROVE_DEPLOY` | deployment |
| `HUMAN_APPROVE_DEMO` | demo account |
| `HUMAN_APPROVE_ARCHIVE` | archiving the campaign |

Full registry: keys of `DEFAULT_GATE_POLICIES` in
`sdk/quantlab/gates/models.py` (nine entries). `HUMAN_APPROVE_REPLACEMENT` is
registered with `fallback=ABORT` but no pipeline stage invokes it yet — it is
enforced at the Guardian prompt level only. Decisions travel by file under
`/tmp/sqx-gates/{campaign_id}/`. `DataManager` is **Dukascopy-only**
(FX M1/M5/H1); crypto/CSV/yahoo raise `NotSupportedError`.

## 5. Active SDD changes

_None — all SDD changes are archived. Last closed: `2026-10-10-quantlab-installer` (38/38 tasks, 363 tests green). Propose new work via `sdd/changes/<slug>/proposal.md`._

## 6. Recently archived (latest 10 of 53)

| Archived change | shipped |
|-----------------|---------|
| `2026-10-10-quantlab-installer` | 38/38 tasks, 5 PRs; Go/Bubbletea installer + wizard + lifecycle; `go test -short` 363 green |
| `2026-10-09-research-agent-enhancements` | 127/127 tasks, 5 PRs; embeddings+providers+diversity+feedback loop; full suite 811 green |
| `2026-10-07-research-agent-improvements` | LLM research path + KB consult wiring |
| `2026-10-07-multi-agent-research-system` | 8 agent specs + director/orchestrator contracts |
| `2026-10-07-hypothesis-builder` | Builder operationalization phase |
| `2026-10-07-health-score-system` | HealthState bands + calculator, 89/89 tests |
| `2026-10-07-phase5-pipeline-core` / `phase5b-e` / `phase5f-i` | Pipeline core, statistics, execution/reporting |
| `2026-10-07-phase4-jforex-portfolio-optimizer` | JForex/portfolio/optimizer/retester automation |
| `2026-10-02-kb-reverification-pipeline` | `quantlab sqx kb reverify`; fixed `KbParameter` dropping `xml_path`/`element_name` on store write (live data loss) |
| `2026-10-02-fix-flat-lane-settings-projection` | Flat-lane CFX codec fix — **breaking dialect change, see §7** |

Full list: `ls sdd/changes/archive/`. Each entry carries its own
`archive-report.md` (completion evidence) and `verify-report.md` (test
evidence). A `research-agent-enhancements`-style report scoped to "planning
artifacts only" is **not** completion — check its stated implementation count.

## 7. Migrations and breaking changes

1. **`sdd/` rename (2026-10-09, this change).** `openspec/` → `sdd/`
   (lowercase); pre-SDD explorations moved to
   `docs/research/explorations/`. Live references updated (`AGENTS.md`,
   `README.md`, `docs/`, `sdd/config.yaml`, `installer/.../overlay.json`
   `sdd/**` allowlist, `tests/test_orchestrator_prompt.py`,
   `tests/test_project_agents.py`). `sdd/changes/archive/**` internals
   intentionally untouched (historical record).
2. **Flat-lane CFX codec (2026-10-02, breaking for external consumers).**
   Flat settings now emit grouped `<Tag attr="v"/>` instead of
   `<Setting key="Tag@attr" value="v"/>`. Consumers matching
   `Setting[@key='Tag@attr']` must switch. Legacy files converge after one
   read/write cycle.
3. **Legacy campaign runner retired (REQ-817).** `_run_campaign.py` is gone;
   the only entry point is `campaign run-flow`. Per-phase isolation via
   `phase_runner.py --phase <name> --directive '<json>'` (REQ-818).
4. **Pipeline config v1→v2 migration.** `Config migration helper` keeps
   backward compat; flat and nested `pipeline.*` formats both accepted.
5. **Calibration is per-tag, not global (delivered 2026-08-19).**
   `TagCalibrator` (Bayesian smoothing) runs on the rule-based path; the
   remaining gap is exposing per-tag stats to the LLM prompt, not computing
   them. Do not build a second calibrator.
6. **Embeddings are a hook, not a service.** `query_docs` has an n-gram
   fallback + embeddings hook; no embedding service, vector storage, or
   cosine ranking shipped until `research-agent-enhancements`.
7. **CI integration job deliberately disabled.** Gated on a repository name
   that never matches *and* references git-ignored `assets/SQX_*`. Do not
   "fix" the repo name without provisioning SQX in CI (marked
   `DO NOT ACTIVATE WITHOUT AN OWNER DECISION`).
8. **Installer coexistence contract.** `quantlab-*` namespace + deep merge;
   never modify `gentle-*` / `sdd-*` agents, skills, or prompts.

## 8. Known debt and blocked decisions

Verified debt (do not re-discover; fix or explicitly carry):

- Orphaned modules pending triage/removal: `sdk/quantlab/broker/`,
  `evolution/`, `health/`, `mcp/`.
- Three duplicate `PhaseResult` types (`phase4/models.py`,
  `campaign/delegation.py`, `substrate/executor.py`) — deliberately aliased
  (AD-6), not consolidated.
- Two test trees (`tests/` + `sdk/tests/`) — `testpaths` unifies collection.
- No committed Python lockfile (range-based resolution); no `uv` binary in
  env (lockfile task deferred by design).
- Load-bearing filename: `docs/sqx-builder-config/SQX Builder Config.md`
  (pinned by KB seeder + ~15 `evidence_ref` entries — never rename).
- `LicenseManager` exported but unused; `run_with_gates()` does not handle
  `GateTimeoutError`.
- LINT campaign (see `docs/LINT-CLEANUP-HANDOFF.md`) needs 4 **product**
  decisions, not lint fixes: `portfolio_composer.py` unwired prototype
  (3 phantom `AsyncSQXClient` methods), `costs/collector.py` phantom
  `symbol` param, dead `--benchmark` feature, `knowledge/store.py`
  `query()` signature. Plus `PLC0414` vs PEP-484 re-export convention
  (pick `as`-alias or `__all__` consistently).

## 9. Document map — read this, not that

| If you need… | Read (canonical) | Do not duplicate into |
|--------------|------------------|----------------------|
| Current state / what changed / what migrates | **this file** | new status docs |
| Product vision, goals, slices S1–S11, checklists | `docs/PRD.md` | state files |
| New-machine setup, install, verify, repo facts | `docs/HANDOFF.md` | state files |
| Release history (immutable) | `docs/CHANGELOG.md` | rewrite old entries |
| Lint/type campaign + its 4 decisions | `docs/LINT-CLEANUP-HANDOFF.md` | state files |
| Doc index | `docs/index.md` | — |
| Pre-SDD research | `docs/research/explorations/` | `sdd/` root |
| Per-change audit trail | `sdd/changes/archive/<slug>/` | state files |
| Enforced contracts | `AGENTS.md` + `sdd/specs/` + `tests/` | prose promises |

## 10. Next steps

1. `quantlab-installer`: DONE 2026-10-10 — archived as
   `sdd/changes/archive/2026-10-10-quantlab-installer/` (38/38 tasks, 363 green).
2. Resolve the 4 LINT product decisions (§8) before pushing mypy/Ruff to zero
   and removing `continue-on-error` from the CI lint job.
3. Triage the 14 non-drift suite failures (§3: compiler/cfx/dashboard/cli/phase4) —
   all pre-existing on HEAD, none from doc/SDD changes.
4. Triage or remove the orphaned modules (§8).
