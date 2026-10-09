# Proposal: Results Analysis Stage

## Intent

Pipeline jumps from statistics to review — nothing decides which strategies are worth keeping. `selected_strategies` required by `PortfolioStage`, never provided; `strategies.csv` exported, never parsed; review overfit checks starve (`wf_cycles`, `strategy_returns` unpopulated). Add a deterministic stage between them: per-strategy metrics, overfit heuristics, selection.

## Scope

### In Scope
- `quantlab.analysis` module: models, reader, engine, selection
- Strategies parser in `readers/databank.py` (alias-mapped, mirrors `TRADE_COLUMNS`)
- `AnalysisAgent` (AnalysisStage) — deterministic, no LLM
- Wiring: registry, `research_director`, `generate_pipeline_config`
- Mock server emits realistic `strategies.csv`
- ReviewerAgent consumes `strategy_analysis`/`wf_cycles`
- `selected_strategies` feeds PortfolioStage

### Out of Scope
- LLM verdict layer (follow-up)
- Phase-4 path parity
- Per-strategy trade/equity export from SQX
- ReviewerAgent threshold changes (stay configurable)

## Capabilities

### New Capabilities
- `strategy-analysis`: per-strategy metrics; overfit heuristics (extreme PF/Sharpe + low trades, MC p10 breach, WF OOS/IS when available); selection → `strategy_analysis`, `strategy_verdicts`, `selected_strategies`

### Modified Capabilities
- `result-reader`: add strategies-databank parsing (`STRATEGY_COLUMNS`, tolerant of unknown columns)
- `pipeline-core`: add `AnalysisStage` contract (requires: `export_paths`, `statistics`; provides: `strategy_analysis`, `selected_strategies`, `strategy_verdicts`); `ReviewStage.requires` + `strategy_analysis`
- `reviewer-agent`: consume `strategy_analysis`/`wf_cycles` — closes review data gaps

## Approach

Mirror the stats pattern: pure library + thin agent. AnalysisAgent parses `strategies.csv`, computes metrics, applies heuristics, selects, writes artifacts. Insert stage; register; extend mock exports; wire reviewer inputs.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/analysis/` | New | Metrics, heuristics, selection |
| `sdk/quantlab/readers/databank.py` | Modified | Strategies parser |
| `sdk/quantlab/agents/analysis_agent.py` | New | AnalysisStage impl |
| `sdk/quantlab/pipeline/stages/agent_stages.py` | Modified | AnalysisStage contract |
| `sdk/quantlab/pipeline/registry.py` | Modified | Register stage |
| `sdk/quantlab/agents/research_director.py` | Modified | Insert stage |
| `sdk/quantlab/agents/builder_agent.py` | Modified | Pipeline config |
| `sdk/quantlab/sqx/mock_sqx_server.py` | Modified | Emit strategies.csv |
| `sdk/quantlab/agents/reviewer_agent.py` | Modified | Consume analysis |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `strategies.csv` format unverified, no sample in repo (CRITICAL) | High | Tolerant parser: alias map, skip unknowns, never hard-fail; realistic fixture |
| Column/alias drift with SQX export | Med | Central `STRATEGY_COLUMNS`; clear ParseError |
| Stage ordering/contract regression | Med | Pipeline contract validation; closure tests |

## Rollback Plan

Revert wiring (registry, `research_director`, `generate_pipeline_config`): statistics → review restored. Analysis module and parser stay inert; validation prevents silent breakage.

## Dependencies

- Real `strategies.csv` sample from SQX export (validation)
- ReviewerAgent thresholds via `ResearchConfig`

## Success Criteria

- [ ] Analysis stage runs between stats and review
- [ ] `strategies.csv` parses; unknown columns tolerated
- [ ] `selected_strategies` before PortfolioStage (contract satisfied)
- [ ] ReviewerAgent wf/benchmark checks run on real data
- [ ] Mock round-trip, pipeline tests green
