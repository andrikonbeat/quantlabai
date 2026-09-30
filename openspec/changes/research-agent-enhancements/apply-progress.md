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
| Research "calibrates confidence using a single global historical Sharpe average" | **Already per-tag.** `TagCalibrator` computes per-tag Sharpe percentiles with Bayesian smoothing, and `ResearchAgent.formulate_hypotheses()` already calls it. | `sdk/quantlab/agents/tag_calibrator.py`, commit `9c22cde` (2026-08-19) |
| "Knowledge Lake semantic search: embedding generation, similarity retrieval" | **Token-level only.** `query_docs` has an n-gram fallback plus an embeddings *hook*. There is no embedding service, no vector storage, no cosine ranking. | commit `27b93b2` (2026-08-20) |

Consequences:

- Task **3.5** (inject tag-based Sharpe calibration from Knowledge Lake) is closer to *integration of an
  existing calibrator* than greenfield. Do not build a second calibrator.
- Task **1.1** is genuinely unbuilt, and the spec is concrete about it: `.npy` + `.meta.json` per
  hypothesis, cosine ranking, Jaccard fallback, version bump to index 6.
- Re-estimate the ~1200–1800 lines after the above is settled; the current figure predates both changes.

### Genuinely unbuilt (greenfield)

- All five data providers (2.1–2.5) — `sdk/quantlab/data/providers/` does not exist
- `DiversityEngine` (3.1), `PreValidator` (3.2), `FeedbackWriter` (4.1)
- `EmbeddingService` (1.1) and the similarity query path (1.3)

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

Reconcile the proposal against the staleness table, re-run proposal → tasks, then re-approve scope.
Do not start at 1.1 before that.

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
- `sdk/quantlab/data/providers/` (new: base, papers, blogs, sqx_docs, screeners)
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
