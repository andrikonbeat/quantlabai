# Tasks: Phase 1 — SDK Core

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | ~1,100–1,300 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 |
| Delivery strategy | force-chained |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Foundation + DSL + Tools | PR 1 | base: feature/phase1-sdk-core |
| 2 | Translator + CLI Wrapper | PR 2 | base: pr/phase1-core/pr-1 |
| 3 | Readers + Stats + Knowledge + Docs | PR 3 | base: pr/phase1-core/pr-2 |

## Phase 1: Foundation (PR 1)

- [x] 1.1 `sdk/pyproject.toml` — uv config, Pydantic v2, pytest
- [x] 1.2 `quantlab/__init__.py` + `tools/exceptions.py` — QuantLabError hierarchy
- [x] 1.3 `tools/platform.py` — platformdirs + pathlib resolution
- [x] 1.4 `dsl/models.py` — ResearchConfig + nested Pydantic models
- [x] 1.5 `dsl/parser.py` — YAML parse, validate, serialize
- [x] 1.6 `tests/` init + fixtures + unit tests for tools and dsl

## Phase 2: Translator + CLI (PR 2)

- [x] 2.1 `translate/translator.py` — model→CFX XML generation
- [x] 2.2 `translate/cfx.py` — XML→ZIP archive, dry-run skip write
- [x] 2.3 `cli/runner.py` — CliRunner + Executor protocol + MockExecutor
- [x] 2.4 Tests: translate (XML elements, dry-run) + cli (mock exec, timeout, cross-platform)

## Phase 3: Readers + Stats + Knowledge (PR 3)

- [x] 3.1 `readers/models.py` — Trade, EquityPoint, SummaryStats
- [x] 3.2 `readers/databank.py` — CSV parsing, XLSX parsing
- [x] 3.3 `stats/engine.py` — PF, Sharpe, Sortino, MDD, MAR, RF, expectancy
- [x] 3.4 `knowledge/store.py` — init 5 dirs, rebuild index, format validation
- [x] 3.5 `strategies/HelloWorldStrategy.java` + `knowledge/*/.gitkeep`
- [x] 3.6 Tests: readers (fixtures, corrupt), stats (zero-div, empty), knowledge (tmpdir)
- [x] 3.7 README.md — install, commands, dry-run walkthrough
