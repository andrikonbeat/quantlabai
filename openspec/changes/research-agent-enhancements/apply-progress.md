# Apply Progress: Research Agent Enhancements

## Resume Handoff (2026-09-30)

**State: implementation NOT started. 0 of 34 tasks implemented.** Verified against the codebase rather
than against task checkboxes: 9 of the 10 files this change declares as new do not exist, and no commit
in the repository references this change. It is a planning-only change.

### Staleness audit — read before scoping

The proposal was written 2026-09-28 but describes the system as of August. Two scope items are already
partly delivered by *other* changes, so the Intent paragraph is factually wrong on calibration:

| Proposal claim | Actual state | Evidence |
|---|---|---|
| Research "calibrates confidence using a single global historical Sharpe average" | **Already per-tag, on the rule-based path.** `TagCalibrator` computes per-tag Sharpe percentiles with Bayesian smoothing and is called from `ResearchAgent.formulate_hypotheses()` (gated on `if query_results:`), covered by `tests/agents/test_tag_calibrator.py` and `test_research_agent_f1.py`. The `global_sharpes` variable inside `calibrate()` is the percentile *reference distribution*, not the calibration input. | `sdk/quantlab/agents/tag_calibrator.py`, commit `9c22cde` (2026-08-19) |
| "Knowledge Lake semantic search: embedding generation, similarity retrieval" | **Token-level only.** `query_docs` has an n-gram fallback plus an embeddings *hook*. There is no embedding service, no vector storage, no cosine ranking. | commit `27b93b2` (2026-08-20) |

Consequences:

- Task **3.5** is *integration of an existing calibrator*, not greenfield — and the gap is narrower than
  it first appears. The rule-based path already calibrates; `LLMResearchAgent.build_prompt()` is a
  separate code path that never consults it. The work is exposing per-tag statistics to the LLM prompt,
  not computing them. Do not build a second calibrator.
- Task **1.1** is genuinely unbuilt, and the spec is concrete about it: `.npy` + `.meta.json` per
  hypothesis, cosine ranking, Jaccard fallback, version bump to index 6.
- Re-estimate the ~1200–1800 lines after the above is settled; the current figure predates both changes.

### Work-unit premise audit (verified against the tree, 2026-09-30)

Most task premises hold. These three do not — they were written in September against a stale picture:

| Task | Premise in `tasks.md` | Actual state | Consequence |
|---|---|---|---|
| **1.2** | "Add `embeddings/` directory to `KnowledgeStore.initialize()`" | **`embeddings/` already exists** — listed at `store.py:55`, created by `initialize()`, present on disk, and already referenced at `store.py:1067`. Index *is* at `_version` "5". | Only the **version bump to 6** remains. This is a near-free task, not a structural change. |
| **1.3** | "Implement `QueryBuilder.filter_by_similarity()`" | **Scaffolding exists** — `_tokenize()`, `_add_text()`, `_text_cosine()`, and `search_text()` are all present. The named method is absent. | Smaller than a greenfield method: add the signature, cosine ranking, Jaccard fallback. |
| **1.4** | "Add strategy-type metrics aggregation to `indexer.py`" | `Indexer` has **no** metrics method, **but** `TagCalibrator._build_tag_stats()` already computes per-tag `avg_sharpe`. | The aggregation logic exists in the wrong place. Consolidation, not invention. |

Premises that **do** hold: `embedding_service.py`, all five providers and `base.py`/`ProviderRegistry`
and `HypothesisConfig` embedding/feedback fields (currently `name`, `description`, `parameters`,
`expected_outcome`, `confidence`, `validation_warnings`, `llm_rationale` — no embedding or feedback field).
Task 2.5's env-var API keys have precedent to follow in `data/data_manager.py`.

### Work Unit 2 — DECIDED 2026-09-30: reuse the existing provider framework

Task 2.1 as written asks to "create `sdk/quantlab/data/providers/base.py` with `BaseProvider` ABC and
`ProviderRegistry`". **Do not do that.** `AbstractDataProvider` already provides everything it would.

| Proposed by task 2.1 | Actual equivalent |
|---|---|
| `data/providers/base.py` — `BaseProvider` ABC | `data/fundamental/base.py` — `AbstractDataProvider` (one abstract method: `async fetch(query, **params) -> dict`) + `ProviderError` |
| — | `data/news/base.py` — `NewsProvider(AbstractDataProvider)`, already extends the fundamental base |
| `ProviderRegistry` | **No registry needed.** `AbstractDataProvider.__init_subclass__` auto-registers every subclass into `_registry`. |
| rate-limit politeness (task 2.2) | `data/news/rate_limit.py` |
| env-var API keys (task 2.5) | precedent in `data/data_manager.py` |

> **Correction.** An earlier draft of this file mapped `ProviderRegistry` → `data/datasource_registry.py`.
> That was wrong: `DatasourceRegistry` registers `DatasourceHandler`s for *market data* sources
> (`sqx_name()`, `ensure()`, `update()` — dukascopy, jforex), not content providers. There is no existing
> provider registry because none is needed — registration is automatic.

**Agreed shape (maintainer decision, 2026-09-30):**

1. **Reuse `AbstractDataProvider`.** No new framework, no `data/providers/`. Each new provider implements
   `fetch()` and inherits automatic registration.
2. **New domain package `sdk/quantlab/data/literature/`**, matching the existing by-domain layout
   (`fundamental/`, `news/`, `market/`, `technical/`, `demo/`, `dukascopy/`). A flat `data/providers/`
   would break that convention.
3. **`LiteratureProvider(AbstractDataProvider)` plus a `PaperItem` model.** `NewsItem`
   (`data/news/models.py`) carries `sentiment`, which is meaningless for a paper, and lacks `authors`,
   `arxiv_id`, and `categories` — the last being an explicit task-2.2 requirement (category filter).
4. **`sqx_docs` is not yet placed.** It scans local files under `knowledge/structured/sqx-kb/`, not a
   network source, so it may not belong to this hierarchy. Defer its placement to when task 2.4 is
   picked up.

**Task 2.1 is therefore re-scoped** from "create the framework" to "add the `data/literature/` package and
its base class". See the annotation on task 2.1 in `tasks.md`.

### Dependencies (verified in `sdk/pyproject.toml`)

The proposal lists four optional deps. Actual state:

| Dep | Status |
|---|---|
| `feedparser` | **Already a core dependency** (`sdk/pyproject.toml:26`). Only the local `.venv` is out of sync — not a project gap. |
| `beautifulsoup4` | **Already a core dependency** (`:25`). Installed and importable. |
| `arxiv` | **Not declared anywhere.** Task 2.2 needs it added. |
| `sentence-transformers` | **Not declared anywhere.** Task 1.1 needs an optional extra. Heavy (pulls torch); note `requires-python = ">=3.11"` with local 3.14.4. The task-1.1 token-similarity fallback already covers its absence, so this is a deferrable extra, not a blocker. |

### Revised estimate

Work Unit 1 shrinks materially: task 1.2 is near-free, and 1.3/1.4 have existing code to build on.
Task 3.5 drops from "build calibration" to "expose it".

Work Unit 2 does **not** shrink the way it appears to. Five providers are genuinely greenfield, but
task 2.1 should be re-scoped from "create the framework" to "extend the existing hierarchy" — which is
cheaper, yet adds a refactor with regression risk across `fundamental/` and `news/` that the change
never budgeted for. The under-specified item modelling (above) may cost more than the abstraction it
was going to replace.

Do not assume the change-wide `~1200–1800` falls proportionally. Re-estimate per work unit, and treat
the Work Unit 2 provider/item-model decision as the largest remaining unknown, before opening the
chaining decision.

### Open decision required before apply

The workload forecast records `Decision needed before apply: Yes` — 400-line budget risk High, chained
PRs recommended, chain strategy `feature-branch-chain`, delivery strategy `ask-on-risk`. Settle the
staleness reconciliation above *first*, because it changes the estimate that decision depends on.

### Process defect to be aware of

`archive-report.md` declares "Archive Status: Complete". That refers to the *planning* artifacts only —
implementation never started, and the change was never moved to `openspec/changes/archive/`. Do not read
that file as evidence that the change shipped. This is the same premature-completion pattern found in
`typed-crosschecks-models`, where 3 tasks were checked `[x]` without being implemented.

### Next action

1. Re-estimate per work unit against the reconciled premises above. The Work Unit 2 provider question
   is settled, so the estimate is now computable.
2. Resolve the `ask-on-risk` / `feature-branch-chain` gate with those numbers in hand.
3. Re-run proposal → tasks so the plan reflects the reconciled scope, then re-approve.
4. Only then start at task 1.1.

## Status

Planned — implementation not started. This document tracks work units for the 3 PR chain.

## Work Unit 1: Foundation (PR 1)

**Goal**: Knowledge Lake semantic layer — embeddings, similarity search, strategy-type metrics.

**Scope**:
- `sdk/quantlab/knowledge/embedding_service.py` (new)
- `sdk/quantlab/knowledge/store.py` (modified)
- `sdk/quantlab/knowledge/query.py` (modified)
- `sdk/quantlab/knowledge/indexer.py` (modified)
- Tests in `sdk/tests/knowledge/`

**Proof**: `SQX_FORCE_MOCK=1 python3 -m pytest sdk/tests/knowledge/ -q`

**Rollback**: Revert changes to `sdk/quantlab/knowledge/` only.

## Work Unit 2: Providers + LLM Intelligence (PR 2)

**Goal**: New data providers and hypothesis generation improvements.

**Scope**:
- `sdk/quantlab/data/literature/` (new: base with `LiteratureProvider`, `PaperItem`, papers, blogs —
  per the 2026-09-30 decision; the original `data/providers/` path is superseded)
- placement of `sqx_docs` and `screeners` undecided — see tasks 2.4 and 2.5
- `sdk/quantlab/agents/llm_research_agent.py` (modified)
- `sdk/quantlab/agents/research_agent.py` (modified)
- `sdk/quantlab/agents/diversity_engine.py` (new)
- `sdk/quantlab/agents/pre_validator.py` (new)
- `sdk/quantlab/agents/prompts.py` (new)
- `sdk/quantlab/agents/hypothesis_builder/` (modified)
- `sdk/quantlab/dsl/models.py` (modified)
- Tests in `sdk/tests/agents/` and `sdk/tests/data/`

**Proof**: `SQX_FORCE_MOCK=1 python3 -m pytest sdk/tests/agents/ sdk/tests/data/ -q`

**Rollback**: Revert `sdk/quantlab/data/`, `sdk/quantlab/agents/`, and `sdk/quantlab/dsl/models.py`.

## Work Unit 3: Integration + Feedback Loop (PR 3)

**Goal**: Wire feedback loop, semantic context injection, end-to-end verification.

**Scope**:
- `sdk/quantlab/knowledge/feedback.py` (new)
- `sdk/quantlab/agents/knowledge_memory.py` or equivalent (modified)
- Pipeline wiring for feedback at phase boundaries
- Integration tests for full campaign flow
- Spec updates in `openspec/specs/`

**Proof**: `SQX_FORCE_MOCK=1 python3 -m pytest -q`

**Rollback**: Revert `sdk/quantlab/knowledge/feedback.py` and context injection changes.
