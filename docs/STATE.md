# QuantLab AI — Project State

> This page describes the shape of the project and how to verify it. It is
> deliberately **not** a live dashboard — counts go stale the moment a commit
> lands. For current state use the commands in [Live status](#live-status).

## Live status

These are the sources of truth. Prefer them over any number written on this page.

```bash
git log --oneline -20              # what actually landed, and when
git status                         # is the tree clean
git branch --show-current          # which branch you are on

# CI is authoritative for lint, types, and the sdk/ test tree
gh run list --limit 5
gh run view --log-failed
```

| Question | Authoritative source |
|----------|---------------------|
| What is implemented? | `git log`, plus `openspec/changes/archive/YYYY-MM-DD-<slug>/` |
| Is the suite green? | `gh run list` for CI; the local command below for the full tree |
| Which changes are in flight? | `ls openspec/changes/` (active) vs `openspec/changes/archive/` |
| What is the code contract? | `openspec/specs/`, asserted by `tests/` |
| What do the agents actually do? | `ai/opencode/` (repo-canonical) |

> **Scope note:** CI (`.github/workflows/ci.yml`) runs `pytest` from the
> repository root with no `working-directory`, so it collects the same
> canonical suite as `pytest.ini` — `tests/` **and** `sdk/tests/` — on Python
> 3.11. A green CI badge therefore does mean the full suite is green. Run it
> locally with `SQX_FORCE_MOCK=1` regardless, since that is the only mode the
> suite supports.

## Verified snapshot

A point-in-time observation, recorded once. It is **not** the live status.

| Field | Value |
|-------|-------|
| Observed on | 2026-10-03 |
| Branch | `wip/migration-checkpoint` |
| Commit | `9189fbb` |
| Full suite | **4135 passed, 18 skipped, 0 failed** in 336s |
| Command | `SQX_FORCE_MOCK=1 python3 -m pytest -q` from the repo root |
| Go installer | `go build ./...` clean; `go test ./... -short` all packages pass |
| Active SDD changes | 14 |
| Archived SDD entries | 39 |
| Docs under `docs/` | 27 |

`SQX_FORCE_MOCK=1` is required: without it the tests try to bind the real
StrategyQuant X daemon on port 5050.

> The previous snapshot (2026-09-30, `486da48`) recorded 4111 passed / 9 skipped.
> Both the suite and the skip count moved between them; read the numbers above as
> one observation, not a trend.

## What this project is

A quantitative research SDK for algorithmic trading built on StrategyQuant X.
The product is an AI-directed research engine: OpenCode acts as research
director, StrategyQuant X is the computation engine, and work is governed by
**SDD** (spec-driven development) — each change carries proposal, specs, design,
and tasks, and is archived under `openspec/changes/archive/` on completion.

**Stack**: Python 3.11+ (local `.venv` runs 3.14.4; CI pins 3.11), Pydantic,
PyYAML, pandas/numpy, httpx, Plotly (matplotlib optional), MCP, OpenAI SDK.

## Layout

```
sdk/
├── quantlab/
│   ├── agents/         # agent stages + ResearchDirector + refutation/
│   ├── campaign/       # flow.py (PHASES, assert_flow*), delegation (PhaseResult)
│   ├── cfx/            # CFX reader/writer/patcher/dom/models
│   ├── cli/            # pipeline, campaign, sq, knowledge, monitor, report, daemon
│   ├── customproject/  # project templates (metadata + AutomaticRetest renderer)
│   ├── data/           # DataManager (Dukascopy) + market/ (providers, registry)
│   ├── dsl/            # ResearchConfig models + parser
│   ├── gates/          # HumanGateOrchestrator, notifiers, models, callbacks
│   ├── knowledge/      # KnowledgeStore, Indexer, KB (models/store/seeder)
│   ├── phase4/         # JForex, Portfolio, Optimizer, Retester, template_registry
│   ├── pipeline/       # Pipeline runner, stages, registry, config, progress
│   ├── substrate/      # executor + lifecycle support
│   └── reporting/ stats/ translate/ tools/
├── tests/              # canonical tree (included by testpaths)
└── examples/           # pipeline.yaml, research-config.yaml
tests/                  # second test tree (also included by testpaths)
docs/                   # docs, indexed by docs/index.md
  └── sqx-builder-config/  # SQX builder reference; the KB seeder's source doc
openspec/
├── specs/              # normative capability specs (the contract layer)
└── changes/            # active changes; archive/ holds completed history
ai/opencode/            # repo-canonical agent prompts + skills (source of truth)
infra/                  # init-schema.sql (DB init, referenced by docker-compose)
knowledge/              # Knowledge Lake (agent-memory/, structured/, timeseries/)
app_movil/              # standalone Android demo app (112 tracked files)
```

Two test trees exist (`tests/` and `sdk/tests/`); `testpaths` in `pytest.ini`
collects both.

## Campaign flow

The campaign is LLM-driven and runs **14 phases** in canonical order:

```
research → hypothesis → config → review → dispatch → monitor → retest
        → optimize → portfolio → compile → deploy → demo → archive → live-ops
```

The order lives in `PHASES` at `sdk/quantlab/campaign/flow.py:33` and is
mirrored in `ai/opencode/agents/campaign.md`; a test extracts the literal from
the prompt and compares it to the tuple, so the two cannot drift.

`retest` and `optimize` are conditional — they are only required when the
matching DSL block is present in the config. Every other phase must be present.

How to actually run it: [Running Multi-Agent Campaigns](guides/running-campaigns.md).

Dispatch runs through the `quantlab-campaign` agent, which delegates each phase
to a dedicated `quantlab-phase-<phase>` subagent and folds the returned
`PhaseResult` envelopes. The `orchestrated-campaign-flow` change that
introduced this shape is archived at
`openspec/changes/archive/2026-08-06-full-campaign-flow/`.

Human gates are **fail-closed** (REQ-11) — no auto-approval, and an unanswered
gate stops the run. The four gates that always block a dispatch are:

| Gate | Blocks |
|------|--------|
| `HUMAN_APPROVE_CONFIG` | the dispatch to StrategyQuant X |
| `HUMAN_APPROVE_DEPLOY` | deployment |
| `HUMAN_APPROVE_DEMO` | the demo account |
| `HUMAN_APPROVE_ARCHIVE` | archiving the campaign |

The full registry is the keys of `DEFAULT_GATE_POLICIES` in
`sdk/quantlab/gates/models.py` (referenced here without a count on purpose —
the count drifts every time a gate is registered, so read it from the dict).
`HUMAN_APPROVE_REPLACEMENT` is registered but is the one entry no
pipeline stage invokes yet; it is enforced at the prompt level. Decisions
travel by file under
`/tmp/sqx-gates/{campaign_id}/`. `DataManager` is **Dukascopy-only** at launch
(FX M1/M5/H1).

## Prompt and skill sync contract

`ai/opencode/` is the **single source of truth** for agent prompts and skills.
The live copies under `~/.config/opencode/` are generated artifacts — never
hand-edit them.

```bash
python3 ai/opencode/sync_prompts.py --check   # exit 1 on drift
python3 ai/opencode/sync_skills.py --check    # exit 1 on drift
```

Both scripts are idempotent and allowlist-scoped, and support `--dry-run`.

## Tests

```bash
# From the repo root. SQX_FORCE_MOCK=1 is mandatory.
SQX_FORCE_MOCK=1 python3 -m pytest -q

# Focused, during iteration
SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/
```

The KB suites (`sdk/tests/test_kb.py`, `test_kb_seed_validation.py`) validate
`DEFAULT_DOC_PATH` end-to-end → `docs/sqx-builder-config/SQX Builder Config.md`.
That filename is load-bearing: it is pinned in the seeder and cited by ~15
`evidence_ref` entries under `knowledge/structured/sqx-kb/**`.

CI additionally runs `ruff check`, `ruff format --check`, and
`mypy quantlab --strict`. All three, plus `pytest-asyncio`, are declared in
`sdk/pyproject.toml` under the `dev` extra — install with `pip install -e "sdk[dev]"`
and they are available locally too.

## Known debt

Verified present as of the snapshot above:

- **Orphaned modules** with no active references, pending triage or removal:
  `sdk/quantlab/broker/`, `sdk/quantlab/evolution/`, `sdk/quantlab/health/`,
  `sdk/quantlab/mcp/`.
- **Three duplicate `PhaseResult` types** — `phase4/models.py`,
  `campaign/delegation.py`, `substrate/executor.py`. They are deliberately
  aliased on import in `delegation.py` (AD-6) rather than consolidated.
- **Two test trees** (`tests/` + `sdk/tests/`) — inherited debt; `testpaths`
  unifies collection but the duplication persists.
- `LicenseManager` is exported but unused; `PipelineRunner.run_with_gates()`
  does not handle `GateTimeoutError`.

## Useful commands

```bash
# SQX installation (outside the repo, machine-local, never committed)
export SQX_INSTALL_PATH="/path/to/your/SQX_install_root"
export SQX_PORT=5050

# Prompt/skill parity
python3 ai/opencode/sync_prompts.py --check
python3 ai/opencode/sync_skills.py --check

# KB seeder default path
python3 -c "from quantlab.knowledge.kb.seeder import DEFAULT_DOC_PATH; print(DEFAULT_DOC_PATH)"

# CLI (the venv lives at the repo root, not in sdk/)
.venv/bin/python -m quantlab.cli campaign run-flow --help
```

Full new-machine procedure: [HANDOFF.md](HANDOFF.md).

## Next step

- [docs/index.md](index.md) — index of all 26 documents
- [AGENTS.md](../AGENTS.md) — the contracts this repo enforces