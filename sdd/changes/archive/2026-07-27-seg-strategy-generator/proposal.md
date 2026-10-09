# Proposal: SEG — Strategy Evolution Generator

## Intent

Close three stub implementations (GeneticOptimizer, NoveltyGenerator, CandidateValidator) that return `[]` or passthrough, wire the evolution engine to real PipelineRunner backtests, and provide a unified "generate strategy from intent" entry point via StrategyGenerator facade, MCP tool, and CLI subcommand.

## Scope

### In Scope
- Implement GeneticOptimizer.optimize() — CFX parsing, parameter mutation (crossover/random/boundary), backtest delegation via PipelineRunner, fitness scoring
- Implement NoveltyGenerator.generate() — DSL strategy generation from context, CFX translation, short backtest, scoring, iterative refinement
- Implement CandidateValidator.validate() — PipelineRunner integration for BT → WF → MC chain with stage pass/fail
- Wire EvolutionOrchestrator through real PipelineRunner + CandidateValidator
- StrategyGenerator facade — accepts market/timeframe/objective, delegates to GA/NG/CV, returns ranked results
- MCP `generate_strategy` tool + CLI `quantlab-cli strategy generate` subcommand

### Out of Scope
- Template system (Layer 3) — 10–20 seeded strategy blueprints — deferred follow-up
- Strategy catalog / local registry of active strategies
- Batch/parallel backtest optimization

## Capabilities

### New Capabilities
- `seg-facade`: StrategyGenerator facade class, MCP `generate_strategy` tool, and CLI `strategy generate` subcommand

### Modified Capabilities
- `strategic-evolution-engine`: GeneticOptimizer, NoveltyGenerator, CandidateValidator change from stub to real implementations; EvolutionOrchestrator integrates with PipelineRunner
- `mcp-bridge`: New `generate_strategy` tool registered alongside existing domain tools

## Approach

Layered — Layer 1 (core stubs) first: implement GA/NG/CV in dependency order (validator needs PipelineRunner, optimizer needs validator, generator needs optimizer). Layer 2 (facade) builds on top. Multi-tier validation (quick BT → medium WF → full MC) to manage cost. Custom lightweight GA operators over DEAP to minimize new deps.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/evolution/genetic.py` | Modified | Real CFX mutation, crossover, backtest delegation |
| `sdk/quantlab/evolution/novelty.py` | Modified | DSL generation, CFX translation, short backtest |
| `sdk/quantlab/evolution/validator.py` | Modified | Wire to PipelineRunner for BT→WF→MC |
| `sdk/quantlab/evolution/orchestrator.py` | Modified | Real validation pipeline integration |
| `sdk/quantlab/evolution/` | New | StrategyGenerator module |
| `sdk/quantlab/mcp/seg_tools.py` | New | `generate_strategy` MCP tool |
| `sdk/quantlab/cli/strategy_commands.py` | New | `strategy generate` CLI subcommand |
| `sdk/quantlab/pipeline/runner.py` | Modified | Lighter entry point for evolution backtests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Backtest perf — serial SQX daemon for hundreds of candidates | High | Multi-tier validation; quick BT filters before expensive WF/MC |
| GA design complexity without DEAP | Med | Lightweight mutation/crossover operators specific to CFX params |
| Strategy ID management across SQX/pool/MetaGuardian | Med | Defer ID lifecycle to follow-up; in-process UUIDs for Layer 1 |

## Rollback Plan

Revert per layer: `git revert` Layer 1 commits (GA/NG/CV) independently from Layer 2 (facade/MCP/CLI). Core pipeline, DSL, and HealthScore remain unchanged. CandidatePool JSON persistence survives revert.

## Dependencies

- PipelineRunner (existing) — must accept evolution-triggered backtest jobs
- CandidatePool (existing) — JSON persistence available
- HealthScore + StatisticsEngine (existing) — used by FitnessFunction

## Success Criteria

- [ ] GeneticOptimizer.optimize() returns ≥1 candidate with mutated CFX params and fitness score
- [ ] NoveltyGenerator.generate() produces a runnable CFX strategy from DSL context
- [ ] CandidateValidator.validate() runs full BT→WF→MC pipeline and returns pass/fail
- [ ] `StrategyGenerator("MA Crossover on EURUSD H1")` returns ranked results
- [ ] `generate_strategy` MCP tool responds with valid JSON
- [ ] `quantlab-cli strategy generate --market EURUSD --timeframe H1` produces output
