## Exploration: Strategy Evolution Generator (SEG)

### Current State

QuantLab AI has **23 modules** across ~16,500 lines of Python, covering the full lifecycle of quantitative trading strategy research — except for the "generate from intent" entry point that ties it all together.

**What exists** (and works):
- **Pipeline System** — `PipelineRunner` + `StageRegistry` (26 stages) + contract validation + retry logic + gate injection
- **Multi-Agent System** — `ResearchDirector` orchestrates 8 agents through 5 human gates; campaign lifecycle (create → run → converge)
- **DSL Parser** — `ResearchConfig` model with markets, timeframes, building blocks, entry/exit rules, acceptance criteria
- **CFX Translator** — `translate/translator.py` converts `ResearchConfig` → `.cfx` archives via `CfxWriter`/`CfxPatcher`
- **Statistics Engine** — `StatsResult` with 10 metrics; rolling metrics, aggregation, Monte Carlo bootstrap
- **Health Score System** — `HealthScoreCalculator` with 7 weighted metrics, configurable profiles
- **MetaGuardian** — 6 guardian types (capital, execution, market, quality, risk, portfolio), `PortfolioState` state machine with hysteresis
- **Strategic Evolution Engine** — `EvolutionOrchestrator` with dual-trigger support, `CandidatePool` (JSON filesystem persistence), `FitnessFunction` (wraps HealthScore), `EvolutionConfig` with modes and schedules
- **MCP Bridge** — `QuantLabMCPServer` with 11 MCP tools across 4 domains (pipeline, evolution, health, fundamental)
- **CLI** — `quantlab-cli` with 10 subcommands: daemon, portfolio, optimizer, retester, jforex, report, pipeline, campaign, agent, knowledge
- **Knowledge Lake** — YAML/JSON persistence with query builder, indexer, campaign storage
- **Phase 4 SQX Automation** — SQX daemon manager, `CommandDispatcher`, Optimizer, Retester, PortfolioMaster, JForexDeployer

**Critical gaps** (the problem SEG must solve):
1. **GeneticOptimizer.optimize()** → returns `[]` (empty list). Zero implementation.
2. **NoveltyGenerator.generate()** → returns `[]` (empty list). Zero implementation.
3. **CandidateValidator.validate()** → returns candidate unchanged. Zero implementation.
4. **No unified "generate strategy from intent"** entry point — users must manually write YAML configs, run CLI commands, then manually evaluate.
5. **No strategy template library** — `CfxTemplateBuilder` only generates Portfolio/Optimizer/Retester CFX wrappers, not actual strategies.
6. **No strategy catalog** — strategies live inside SQX; no local registry of what exists, their characteristics, or their health.
7. **Evolution ↔ Pipeline disconnect** — evolution engine exists but can't run backtests; it'd need `PipelineRunner` but isn't wired to it.
8. **DSL → runnable strategy gap** — translator produces CFX archive XML but there's no automated strategy designer that picks building blocks.

### Affected Areas

- `sdk/quantlab/evolution/genetic.py` — **Placeholder** must be implemented: CFX parsing, parameter mutation, crossover, backtest delegation
- `sdk/quantlab/evolution/novelty.py` — **Placeholder** must be implemented: DSL generation, builder pipeline, short backtest, scoring
- `sdk/quantlab/evolution/validator.py` — **Placeholder** must be wired to `PipelineRunner` for real backtest→WF→MC pipeline
- `sdk/quantlab/evolution/orchestrator.py` — Must integrate with `PipelineRunner` and `CandidateValidator` for real validation
- `sdk/quantlab/mcp/bridge.py` — New SEG MCP tools need registration alongside existing pipeline/evolution/health tools
- `sdk/quantlab/mcp/` — New `seg_tools.py` module with composite tools (e.g., `generate_strategy`, `evolve_strategy`)
- `sdk/quantlab/cli/main.py` — New `quantlab-cli strategy generate` subcommand (or `seg` subcommand)
- `sdk/quantlab/cli/` — New `strategy_commands.py` or `seg_commands.py`
- `sdk/quantlab/dsl/models.py` — May need `StrategyTemplate` model and template catalog
- `sdk/quantlab/translate/translator.py` — May need template-based strategy generation
- `sdk/quantlab/pipeline/runner.py` — Evolution engine needs to invoke backtest pipelines; may need lighter entry point
- `sdk/quantlab/stats/models.py` — Already used by fitness function; no changes expected
- `sdk/quantlab/health/calculator.py` — Already used by fitness function; no changes expected
- `sdk/pyproject.toml` — May need new dependencies for template rendering or genetic algorithms
- `openspec/changes/seg-strategy-generator/` — New SDD artifacts

### Approaches

1. **Facade Layer (recommended)** — Add a `StrategyGenerator` class that delegates to existing subsystems
   - Pros: Minimal new code; reusable existing subsystems; preserves clean architecture; testable in isolation
   - Cons: Doesn't fix the placeholder implementations (they still need real work); adds an abstraction layer
   - Effort: **Low** for facade, **High** for filling placeholder implementations

2. **New MCP Domain (SEG tools)** — Add `seg_tools.py` with composite MCP tools like `generate_strategy`
   - Pros: Natural extension of existing MCP pattern; immediately usable by MCP clients (OpenCode); follows existing architecture
   - Cons: Depends on approach 1's facade (or duplicates logic); MCP-only access pattern limits non-MCP use
   - Effort: **Medium**

3. **Full CLI subcommand** — Add `quantlab-cli strategy {generate,evolve,list,template}` 
   - Pros: CLI is already the primary user interface; discoverable via `--help`; scripting-friendly
   - Cons: CLI parsing is already 1155 lines in `main.py` alone; adding more may push toward split
   - Effort: **Medium**

4. **Strategy Template System** — Design a template catalog with pre-made strategy blueprints
   - Pros: Quick "generate working strategy from intent" without GA; templates can be seeded by domain knowledge
   - Cons: Templates constrain the search space; template maintenance burden
   - Effort: **Medium** (independent from other approaches, can be phased)

### Recommendation

**Phase the work in three layers:**

1. **Layer 1 — Core Implementation (must-do):**
   - Implement `GeneticOptimizer.optimize()` with real CFX parameter parsing, mutation operators (crossover, random, boundary), and backtest delegation via `PipelineRunner`
   - Implement `NoveltyGenerator.generate()` producing DSL strategy descriptions from context, translating to CFX, running short backtest, scoring
   - Implement `CandidateValidator.validate()` with real PipelineRunner → backtest → walk-forward → Monte Carlo chain
   - Wire `EvolutionOrchestrator` to actually pass candidates through validation

2. **Layer 2 — Unified Entry Point (should-do):**
   - Create a `StrategyGenerator` facade class that: accepts user intent (market, timeframe, objective) → generates templates → picks candidates → backtests → scores → returns ranked results
   - Add MCP tool `generate_strategy` that delegates to `StrategyGenerator`
   - Add CLI `quantlab-cli strategy generate` subcommand

3. **Layer 3 — Template System (could-do):**
   - Build a template catalog with 10-20 seeded strategy blueprints (MA Crossover, RSI Mean Reversion, Bollinger Squeeze, etc.)
   - Templates are parameterized `ResearchConfig` partials that SEG fills in and mutates

**Why layer 1 first**: The evolution engine is the core promise of SEG — without real genetic/generative/validation logic, any facade is just window dressing. The placeholder implementations are the single biggest gap.

### Risks

- **Backtest integration complexity**: The evolution engine needs to run hundreds of backtests. The current PipelineRunner + SQX daemon model is serial and SLOW (each backtest requires SQX daemon start/stop). Need a batch/parallel backtest path.
- **Genetic algorithm design**: No existing GA library dependency. DEAP or a custom lightweight GA? Custom keeps deps minimal but adds implementation risk.
- **Template quality**: Bad templates = bad strategies. Templates must be curated, not generated.
- **Validator performance**: Full walk-forward + Monte Carlo for every candidate is expensive. Multi-tier validation (quick backtest → medium WF → full MC) is needed.
- **Strategy identity**: Promoting a candidate to "active strategy" in MetaGuardian means managing strategy IDs across SQX, the pool, and the knowledge store. ID management could get messy.
- **User expectations**: SEG promises "generate strategy from intent" — but the quality ceiling is bounded by SQX's capabilities and the template library. Users need reasonable expectations.

### Ready for Proposal

**Yes** — the exploration reveals clear gaps and a layered roadmap. Key findings:

1. Three core evolution modules are stubs — they return `[]` or passthrough. Real implementation is the prerequisite for anything SEG-like.
2. The architecture is solid: pipelines for execution, DSL for strategy description, CFX translator for SQX bridge, MetaGuardian for monitoring, HealthScore for fitness. The bones are there.
3. Existing MCP Bridge + CLI provide natural extension points.
4. Template system can be phased.
5. **Critical blocker**: The evolution engine must produce real candidates before SEG can be useful. Proposal should prioritize the three stubs.

The orchestrator should run `sdd-propose seg-strategy-generator` to create the change proposal with:
- Scope: Layers 1+2 (core implementations + facade entry point)
- Out of scope: Template system (Layer 3) — propose as follow-up
- Priority: `GeneticOptimizer` → `NoveltyGenerator` → `CandidateValidator` → `StrategyGenerator` facade → MCP/CLI tools
