# ODD Task Document: exploration-pipeline

## Objective

Implement the exploration pipeline (E1–E11) that breaks an order into an execution plan and produces a **13-field decision artifact** per the user spec. This pipeline runs before the campaign pipeline and feeds its output into the research phase.

## Problem

Current state:
- No exploration-order pipeline exists; `ResearchDirector.build_pipeline()` builds the *campaign* pipeline (research → hypothesis → builder → ...), not the exploration sequence E1–E11.
- LLM research output is a `ResearchConfig` JSON (6 keys: campaign, market, timeframe, building_blocks, strategies, hypotheses) — **does not match** the 13-field decision artifact spec.
- `PhaseResult` in `campaign/delegation.py` is an 8-field generic envelope; no 13-field decision artifact model exists.
- E3 (market eval), E4 (timeframe vs SL-pips), E5 (asset eval with small-capital constraints) are **missing**.
- E7/E8/E9 (capital limits, prior observations, broker costs) exist but are **not wired into the research phase**.
- No small-capital risk warning (E1) surfaced to user.

## Why

To make the LLM research director produce a structured, auditable exploration decision that captures: capital, market, instruments, timeframe, leverage, capital limits, operational restrictions, risk/money management, prior observations, statistical edge, hypothesis, and broker costs — **before** the campaign pipeline runs.

## Scope

### In Scope
1. **New Pydantic model** `ExplorationDecision` (13 exact fields per spec) in `sdk/quantlab/dsl/models.py` or new `sdk/quantlab/exploration/models.py`.
2. **Exploration pipeline** `ExplorationDirector` (new class in `sdk/quantlab/exploration/`) that executes ordered steps E1–E11 and produces `ExplorationDecision`.
3. **Step implementations**:
   - E1: `SmallCapitalRiskWarner` — concrete warning (not generic) based on capital.
   - E2: Reuse existing providers (Yahoo, FRED, DDG, RSS, arXiv, blogs, screener).
   - E3: `MarketEvaluator` — score markets by capital, user limits, risk.
   - E4: `TimeframeEvaluator` — avg SL-pips per timeframe table + capital fit.
   - E5: `AssetEvaluator` — instruments fit given small-capital, tight SL, market moves.
   - E6: `HypothesisResearcher` — reuse LLMResearchAgent + refutation layer; add statistical edge estimation.
   - E7: `CapitalLimitsResolver` — wire `_apply_capital_constraints` + operational restrictions field.
   - E8: `PriorObservationsRecall` — wire `compose_prior_context` into research phase (currently 0 prod call sites).
   - E9: `BrokerCostsFetcher` — add web/API fetch to `costs/collector.py`; wire into exploration.
   - E10: `RiskManagementEvaluator` — leverage, risk/money mgmt evaluation.
   - E11: `ExplorationDecision` artifact emission (13 fields).
4. **Integration**: `ResearchDirector` consumes `ExplorationDecision` as prior context for campaign pipeline.
5. **Tests**: Unit tests for each step; integration test for full E1–E11 flow.

### Out of Scope
- Modifying the campaign pipeline (PHASES, ResearchDirector.build_pipeline) — only consumes the artifact.
- Changing LLMResearchAgent prompt structure — only its output contract changes to include ExplorationDecision fields.
- SQX/JForex integration — separate Bloque C.

## Authorized Scope

- `sdk/quantlab/dsl/models.py` (add `ExplorationDecision` model)
- `sdk/quantlab/exploration/` (new package: `__init__.py`, `models.py`, `director.py`, `steps/`)
- `sdk/quantlab/agents/llm_research_agent.py` (adapt output parsing to ExplorationDecision)
- `sdk/quantlab/agents/research_director.py` (consume ExplorationDecision as prior context)
- `sdk/quantlab/agents/research_agent.py` (wire `_apply_capital_constraints` + E7/E8/E9)
- `sdk/quantlab/costs/collector.py` (add web/API fetch for broker costs)
- `sdk/quantlab/knowledge/context.py` (ensure `compose_prior_context` prod call site)
- Tests under `tests/exploration/` and `sdk/tests/exploration/`

## Acceptance Criteria

- [ ] `ExplorationDecision` model with 13 exact fields validates (pydantic).
- [ ] `ExplorationDirector.run(capital, user_limits, objectives)` executes E1–E11 in order and returns validated `ExplorationDecision`.
- [ ] E1 produces concrete small-capital warning (e.g. "100 USD → max 0.01 lots, SL ≥ 15 pips on M5, risk of ruin > 40%").
- [ ] E3 scores ≥3 markets with capital/limits/risk rationale.
- [ ] E4 returns per-timeframe avg SL-pips + capital-fit score (M1..D1).
- [ ] E5 returns instrument shortlist with tight-SL feasibility.
- [ ] E6 returns hypotheses + statistical edge estimate (Sharpe, win-rate, profit-factor).
- [ ] E7 populates capital_limits + operational_restrictions fields.
- [ ] E8 injects prior observations from memory lake (at least 1 prod call site).
- [ ] E9 fetches broker costs (commission, slippage, spread, swap, rollover, triple swap) via web/API.
- [ ] E10 evaluates leverage, risk/money mgmt with concrete numbers.
- [ ] E11 emits complete `ExplorationDecision` artifact (YAML/JSON).
- [ ] `ResearchDirector` accepts `ExplorationDecision` as `prior_context` and uses it in campaign pipeline.
- [ ] All tests pass: `go test ./...` (if any Go) / `pytest -q tests/exploration/ sdk/tests/exploration/`.

## Tasks

- [ ] T1: Create `ExplorationDecision` Pydantic model (13 fields) in `sdk/quantlab/exploration/models.py`
- [ ] T2: Implement `SmallCapitalRiskWarner` step (E1) — concrete warning generator
- [ ] T3: Implement `MarketEvaluator` (E3) — market scoring with capital/limits
- [ ] T4: Implement `TimeframeEvaluator` (E4) — SL-pips per timeframe table
- [ ] T5: Implement `AssetEvaluator` (E5) — instrument feasibility with tight SL
- [ ] T6: Implement `HypothesisResearcher` (E6) — reuse LLMResearchAgent + edge estimation
- [ ] T7: Implement `CapitalLimitsResolver` (E7) — wire capital limits + ops restrictions
- [ ] T8: Implement `PriorObservationsRecall` (E8) — wire `compose_prior_context` prod call
- [ ] T9: Implement `BrokerCostsFetcher` (E9) — web/API fetch for broker costs
- [ ] T10: Implement `RiskManagementEvaluator` (E10) — leverage, risk/money mgmt
- [ ] T11: Create `ExplorationDirector` orchestrating E1–E11, emitting `ExplorationDecision`
- [ ] T12: Wire `ExplorationDecision` into `LLMResearchAgent` output parsing
- [ ] T13: Wire `ExplorationDecision` into `ResearchDirector` as prior context
- [ ] T14: Unit tests for each step + integration test for full flow
- [ ] T15: Update `ResearchConfig` if needed to reference `ExplorationDecision`

## Progress

- Created: 2026-01-15
- Status: planning
- Active Task: none

## Rationale For Accepted Changes

None yet.

## Next Step

Begin T1: create `ExplorationDecision` model with 13 exact fields per spec.