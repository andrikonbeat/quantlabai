# Design: SEG — Strategy Evolution Generator

## Technical Approach

Three-layer implementation: Layer 1 fills three stubs (GeneticOptimizer, NoveltyGenerator, CandidateValidator) with real PipelineRunner-backed logic. Layer 2 adds a StrategyGenerator facade, MCP tool, and CLI subcommand. Layer 3 (template catalog) deferred.

Key insight: the pipeline system already has backtest/WF/MC stages. SEG doesn't build new infrastructure — it wires evolution to existing stages via PipelineRunner, bypassing ResearchDirector for direct lightweight pipeline configs.

## Architecture Decisions

### Decision: Backtest Delegation
| Option | Tradeoff | Decision |
|--------|----------|----------|
| Via ResearchDirector | Reuses agent orchestration but adds 5 human gates and campaign overhead | ✗ |
| Direct PipelineRunner + evolution pipeline config | Lightweight, no gates, configurable stages | ✓ |

**Rationale**: Evolution runs 10–100s of backtests. ResearchDirector's gate-heavy flow is wrong for this. A minimal `evolution-pipeline` config with `daemon_start → load_cfx → run_backtest → compute_stats → export` stages executes in seconds, not hours.

### Decision: Genetic Operators
| Option | Tradeoff | Decision |
|--------|----------|----------|
| DEAP dependency | Full GA toolkit but +1 dep and version risk | ✗ |
| Pure Python operators | ~200 lines for gaussian/boundary/crossover/blend | ✓ |

**Rationale**: ~200 LoC for gaussian mutation (param += N(0, σ/3)), boundary reset (±20% range), blend crossover (α=0.5), single-point crossover. Not worth a library dep.

### Decision: Multi-Tier Validation
| Option | Tradeoff | Decision |
|--------|----------|----------|
| All tiers for every candidate | Robust but slow — 10 min/candidate | ✗ |
| Tiered: BT → WF threshold → MC threshold | Filters early, 70% of candidates never reach MC | ✓ |

**Tiers**: Tier-1: backtest only (all candidates). Tier-2: walk-forward (top 50% by fitness). Tier-3: Monte Carlo (top 20% from tier-2). Configurable via `EvolutionConfig`.

### Decision: Novelty Generation Approach
| Option | Tradeoff | Decision |
|--------|----------|----------|
| Template library (curated building blocks) | Quality ceiling but needs curation | Future |
| DSL random combination (indicators + rules) | No curation burden, covers more space | ✓ |

**Rationale**: NoveltyGenerator builds a `ResearchConfig` partial by randomly combining market/timeframe with 2–4 building blocks from the DSL model, then translates via existing `generate_cfx_archive()`. Genesis metadata tracks the combination path.

### Decision: Strategy Identity
| Option | Tradeoff | Decision |
|--------|----------|----------|
| Full lifecycle (SQX ID + pool ID + MetaGuardian) | Correct but complex for Layer 1 | Future |
| In-process UUID + pool persistence | Simple, survives restarts via JSON pool | ✓ |

**Rationale**: `EvolutionCandidate.candidate_id` is a UUID4. The `strategy_id` field links back to the originating strategy. Full MetaGuardian integration deferred to follow-up.

### Decision: Partial Pipeline Failure
| Option | Tradeoff | Decision |
|--------|----------|----------|
| Abort the candidate | Loses partial data | ✗ |
| Per-stage pass/fail, skip remaining on failure | Preserve what worked | ✓ |

**Rationale**: If backtest succeeds but WF fails (e.g., insufficient data), the candidate is marked `FAILED` with `validation_results` containing the partial output. The error field records the failing stage.

## Data Flow

```
User Intent ──→ StrategyGenerator.generate(intent)
                     │
            ┌────────┴────────┐
            ▼                  ▼
    NoveltyGenerator     GeneticOptimizer
      (no parent CFX)    (parent CFX)
            │                  │
            ▼                  ▼
    DSL ResearchConfig    CfxPatcher.parse_params()
            │                  │
    translate/              Mutation operators
    generate_cfx_archive()   (gaussian/boundary/crossover)
            │                  │
            └────┬─────────────┘
                 ▼
         PipelineRunner
         ┌────────────────┐
         │ daemon_start   │
         │ load_cfx       │
         │ run_backtest   │──► FitnessFunction.evaluate(stats)
         │ compute_stats  │
         │ export         │
         └────────────────┘
                 │
                 ▼
         CandidateValidator
         ┌────────────────┐
         │ Tier-1: BT     │── fitness > threshold?
         │ Tier-2: WF     │── fitness > threshold?
         │ Tier-3: MC     │── PASSED / FAILED
         └────────────────┘
                 │
                 ▼
           CandidatePool
         (JSON persistence)
                 │
                 ▼
          Ranked results ──► User
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/evolution/genetic.py` | Rewrite | CFX param parsing via CfxPatcher, mutation operators, tournament selection, PipelineRunner backtest |
| `sdk/quantlab/evolution/novelty.py` | Rewrite | DSL ResearchConfig generation, CFX translation, short backtest, fitness scoring |
| `sdk/quantlab/evolution/validator.py` | Rewrite | 3-tier validation pipeline (BT→WF→MC), status update, pool persistence |
| `sdk/quantlab/evolution/orchestrator.py` | Modify | Wire real PipelineRunner into `_execute_signal` and `_run_cycle`; pass `cfx_content` from pool |
| `sdk/quantlab/evolution/seg.py` | Create | `StrategyGenerator` facade: `generate(intent)`, `evolve(strategy_id)`, `list_strategies()` |
| `sdk/quantlab/mcp/seg_tools.py` | Create | `generate_strategy` MCP tool wrapping StrategyGenerator |
| `sdk/quantlab/mcp/bridge.py` | Modify | Import + register `seg_tools` in `_register_tools()` |
| `sdk/quantlab/cli/strategy_commands.py` | Create | `quantlab-cli strategy generate --market --timeframe --risk --objective --count` |
| `sdk/quantlab/cli/main.py` | Modify | Add `strategy` subparser + wire handlers |

## Interfaces / Contracts

```python
# seg.py — StrategyGenerator facade
class StrategyGenerator:
    async def generate(self, intent: StrategyIntent) -> list[EvolutionCandidate]: ...
    async def evolve(self, strategy_id: str) -> list[EvolutionCandidate]: ...
    async def list_strategies(self) -> list[EvolutionCandidate]: ...

@dataclass
class StrategyIntent:
    market: str
    timeframe: str
    risk: str = "moderate"       # conservative | moderate | aggressive
    objective: str = "sharpe"    # sharpe | profit | sortino
    count: int = 5               # candidates to return
    mode: EvolutionMode = EvolutionMode.FULL

# GeneticOptimizer internal interface (same public signature)
async def optimize(self, strategy_id: str, cfx_content: str,
                   parent_candidate_id: str | None = None) -> list[EvolutionCandidate]: ...

# NoveltyGenerator internal interface
async def generate(self, context: dict, parent_candidate_id: str | None = None) -> list[EvolutionCandidate]: ...

# CandidateValidator internal interface
async def validate(self, candidate: EvolutionCandidate) -> EvolutionCandidate: ...
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Mutation operators (gaussian, boundary, blend, single-point) | Parametrized tests with known inputs, verify output ranges |
| Unit | CFX param parsing from CfxPatcher | Mock CfxPatcher, verify extracted param dict |
| Unit | DSL ResearchConfig generation (NoveltyGenerator) | Verify building blocks, market, timeframe are valid combos |
| Integration | PipelineRunner backtest delegation | Mock SQX daemon, verify pipeline config is built + stages called |
| Integration | Validator tier threshold logic | Fitness threshold gating: verify tier-2 skipped when tier-1 fails |
| E2E | `generate_strategy` MCP tool | Spin server, call tool, verify JSON response with candidate list |
| E2E | `strategy generate` CLI | Run command with test params, verify exit code + stdout |

## Threat Matrix

**N/A** — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary introduced by SEG. PipelineRunner already manages SQX daemon lifecycle; SEG calls it the same way existing stages do.

## Migration / Rollout

No migration required. Existing `CandidatePool` JSON files from stub runs survive Layer 1 rewrites (same model schema). The facade/MCP/CLI are additive — zero impact on existing pipeline, evolution, or guardian flows.

## Open Questions

- [ ] Should `StrategyGenerator.generate()` with `mode=GENETIC_ONLY` require a seed CFX, or generate one via NoveltyGenerator first?
- [ ] Tier thresholds: what are sensible defaults for WF and MC fitness cutoffs?
