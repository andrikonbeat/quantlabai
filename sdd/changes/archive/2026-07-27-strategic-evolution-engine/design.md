# Design: Strategic Evolution Engine

## Technical Approach

New `sdk/quantlab/evolution/` module with 6 components. EvolutionOrchestrator coordinates a two-phase candidate lifecycle: **generation** (genetic or generative mode) → **validation** (backtest + WF + MC via PipelineRunner). Surviving candidates enter a persistent pool; MetaGuardian picks them up on its next `evaluate()` cycle. FitnessFunction wraps the existing HealthScoreCalculator with configurable weight profiles.

## Architecture Decisions

### Decision: Validation pipeline uses PipelineRunner with existing stages

**Choice**: Reuse PipelineRunner + StageRegistry with the existing `CampaignStage` / `ComputeStatsStage` stages, adding one new `MonteCarloStage` in the pipeline.
**Alternatives**: Run sqcli directly for each validation phase.
**Rationale**: PipelineRunner already provides retry, error isolation, contract validation, and progress callbacks. A single new stage is cheaper than duplicating process orchestration. PipelineContext carries candidate data without filesystem I/O.

### Decision: CandidatePool is a JSON-filesystem store

**Choice**: Each candidate is a JSON file under `knowledge/evolution/pool/{candidate_id}.json`, read at startup.
**Alternatives**: SQLite, in-memory only, Engram topics.
**Rationale**: Survives restart (spec requirement), simple to inspect/debug, no schema migration. Number of candidates is small (< 100). Engram is for agent memory, not operational state.

### Decision: GeneticOptimizer delegates to Optimizer + CfxPatcher

**Choice**: Parse CFX parameters via CfxPatcher mutation instructions, run `Optimizer.run()` for walk-forward optimization, score candidates via FitnessFunction.
**Alternatives**: Implement CFX parameter randomisation inline.
**Rationale**: Optimizer already handles sqcli lifecycle (load → start → poll → export). CfxPatcher provides validated parameter mutation with contract checks — inline mutation would duplicate that.

### Decision: NoveltyGenerator delegates to ResearchDirector + BuilderAgent

**Choice**: ResearchDirector creates a short-lived campaign (ResearchConfig with 1 iteration, no gates), BuilderAgent dispatches to SQX, early stats from StatisticsEngine feed FitnessFunction.
**Alternatives**: Direct DSL → CFX → sqcli without the agent pipeline.
**Rationale**: ResearchDirector already has the DSL-to-CFX pipeline, iteration logic, and pipeline construction. Short backtest only — no gates, no portfolio/deploy stages. Reusing the agent pipeline avoids building another translation pathway.

## Data Flow

```
MetaGuardian ──(DEGRADING/REPLACEMENT_PENDING)──→ EvolutionOrchestrator
     ↑                                                    │
     │                                           ┌────────┴──────────┐
     │                                           │  Mode selection   │
     │                                           └────────┬──────────┘
     │                                          ┌──────────┴───────────┐
     │                              ┌───────────┴──────────┐          │
     │                              │  GeneticOptimizer    │          │
     │                              │  (CfxPatcher →       │          │
     │  ┌──────────────────────┐    │   Optimizer → Fitness│          │
     │  │ CandidatePool        │    └──────────────────────┘          │
     │  │  (knowledge/evolution│                 OR                  │
     │  │   /pool/)            │    ┌──────────────────────────┐      │
     │  │  promotion on MG     │    │  NoveltyGenerator        │      │
     │  │  evaluate()          │    │  (ResearchDirector →     │      │
     │  └──────────────────────┘    │   BuilderAgent → Fitness)│      │
     │         ↑                    └──────────────────────────┘      │
     │         │                             │                        │
     │    ┌────┴──────────────┐              │                        │
     │    │ CandidateValidator│◄─────────────┘                        │
     │    │ (PipelineRunner:  │                                        │
     │    │  backtest →       │                                        │
     │    │  walk-forward →   │                                        │
     │    │  Monte Carlo)     │                                        │
     │    └───────────────────┘                                        │
     └────────────────────────────────────────────────────────────────┘
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/evolution/__init__.py` | Create | Public API exports |
| `sdk/quantlab/evolution/config.py` | Create | EvolutionConfig — enabled, mode, schedule, concurrency, thresholds |
| `sdk/quantlab/evolution/models.py` | Create | EvolutionCandidate, CandidateStatus, EvolutionResult, EvolutionSignal |
| `sdk/quantlab/evolution/orchestrator.py` | Create | EvolutionOrchestrator — trigger handling, priority, lifecycle |
| `sdk/quantlab/evolution/genetic.py` | Create | GeneticOptimizer — CFX mutation via CfxPatcher, Optimizer dispatch |
| `sdk/quantlab/evolution/novelty.py` | Create | NoveltyGenerator — ResearchDirector campaign, short backtest |
| `sdk/quantlab/evolution/fitness.py` | Create | FitnessFunction — wraps HealthScoreCalculator, weight profiles |
| `sdk/quantlab/evolution/validator.py` | Create | CandidateValidator — PipelineRunner with backtest→WF→MC stages |
| `sdk/quantlab/evolution/pool.py` | Create | CandidatePool — JSON-filesystem persistence, promotion logic |
| `sdk/quantlab/pipeline/stages/monte_carlo_stage.py` | Create | Pipeline stage wrapping Retester for MC validation |
| `sdk/quantlab/pipeline/registry.py` | Modify | Register `monte_carlo` stage in default registry |

## Interfaces / Contracts

```python
# evolution/config.py
class EvolutionConfig(BaseModel):
    enabled: bool = True
    mode: Literal["genetic", "generative", "both"] = "both"
    schedule_interval_hours: float = 168.0  # weekly
    max_concurrent_evolutions: int = 2
    max_attempts_genetic: int = 3
    max_attempts_generative: int = 5
    fitness_threshold: float = 60.0  # minimum fitness for pool entry
    weight_profile: dict[str, float] | None = None  # overrides HealthWeights

# evolution/models.py
class EvolutionSignal(BaseModel):
    strategy_id: str
    signal_type: Literal["DEGRADING", "REPLACEMENT_PENDING"]
    current_health: float
    timestamp: datetime

class EvolutionCandidate(BaseModel):
    candidate_id: str
    strategy_id: str  # source strategy (for genetic) or "novel"
    mode: Literal["genetic", "generative"]
    cfx_path: Path | None
    fitness_score: float | None = None
    validation_result: dict | None = None
    status: CandidateStatus = CandidateStatus.GENERATING
    created_at: datetime
    promoted_at: datetime | None = None

class CandidateStatus(str, Enum):
    GENERATING = "generating"
    VALIDATING = "validating"
    PASSED = "passed"
    REJECTED = "rejected"
    PROMOTED = "promoted"

# evolution/fitness.py
class FitnessFunction:
    def __init__(self, weights: HealthWeights | None = None): ...
    def score(self, stats: StatsResult) -> float: ...  # 0-100

# evolution/pool.py
class CandidatePool:
    def __init__(self, pool_dir: str | Path, threshold: float): ...
    def add(self, candidate: EvolutionCandidate) -> None: ...
    def get_ready_for_promotion(self) -> list[EvolutionCandidate]: ...
    def promote(self, candidate_id: str) -> None: ...
    def load_all(self) -> list[EvolutionCandidate]: ...
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | EvolutionConfig validation | Default values, mode enum, threshold bounds |
| Unit | FitnessFunction scoring | Mock StatsResult, verify weighted average against HealthScoreCalculator output |
| Unit | GeneticOptimizer contract validation | Mock CfxPatcher, verify invalid mutations discarded |
| Unit | CandidatePool persistence | Temp directory, verify survive restart |
| Integration | Full validation pipeline | Short backtest → WF → MC with known strategy CFX |
| Integration | NoveltyGenerator flow | Stub ResearchDirector, verify DSL config reaches BuilderAgent |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. SEE delegates subprocess execution to existing Optimizer/Retester/BuilderAgent which own their sqcli dispatch.

## Migration / Rollout

No migration required. Module is behind `evolution.enabled` toggle (default `false` for initial deploy). Feature is inactive until explicitly enabled.

## Open Questions

- [ ] What exact schedule mechanism for the orchetrator? asyncio loop with sleep/poll, or apscheduler, or called externally via CLI?
