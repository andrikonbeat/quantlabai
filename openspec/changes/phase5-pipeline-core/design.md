# Design: Phase 5 — Pipeline Core & Campaign Orchestrator Refactor

## Technical Approach

Extract a reusable, SQX-agnostic pipeline framework from the monolithic `CampaignOrchestrator`. The `pipeline/` module provides generic `Stage` ABC, fluent `Pipeline` builder, `PipelineContext` for artifact passing, and `PipelineRunner` with per-stage timing and error isolation. `CampaignOrchestrator` is refactored internally to compose its 11 `CampaignPhase` stages as a `Pipeline` and delegate to `PipelineRunner`, while preserving 100% public API compatibility. CLI gains a `pipeline` subcommand with YAML-driven execution and a `DaemonContext` helper to eliminate daemon boilerplate.

Refs: `openspec/changes/phase5-pipeline-core/proposal.md`, `openspec/changes/phase5-pipeline-core/specs/campaign-orchestrator/spec.md`, `openspec/changes/phase5-pipeline-core/specs/sqx-cli-wrapper/spec.md`

## Architecture Decisions

### Decision: Package Separation — `pipeline/` (agnostic) vs `phase4/` (SQX-specific)

**Choice**: `pipeline/` has zero imports from `quantlab.phase4` or any SQX domain module. `phase4` imports from `pipeline`.
**Alternatives considered**: Single package with internal modules; mix of SQX and generic code.
**Rationale**: Enforces clean architectural boundary. `pipeline` becomes a reusable library for any async workflow (not just SQX). `CampaignOrchestrator` becomes a thin composition root. Existing 436 Phase 4 tests pass unchanged because public API is identical.

### Decision: Stage ABC Design — `requires`/`provides` as `list[str]`

**Choice**: Each `Stage` declares `requires: list[str]` (keys it reads from `ctx.artifacts`) and `provides: list[str]` (keys it writes). Runner validates at pipeline build time.
**Alternatives considered**: Typed dataclass context; no explicit contract (duck typing).
**Rationale**: Explicit string keys keep `PipelineContext` simple (`dict` for artifacts). Build-time validation catches wiring errors early without complex type system overhead. Matches spec requirement.

### Decision: `PipelineRunner` Sequential with Stop-on-First-Error

**Choice**: Stages execute sequentially. On stage failure, runner records `StageResult(status=FAILED)`, stops, marks remaining stages `SKIPPED`.
**Alternatives considered**: Continue-on-error with aggregation; parallel execution where `requires` allows.
**Rationale**: Spec mandates sequential execution with stop-on-first-error. Simpler semantics, predictable ordering, matches current `CampaignOrchestrator` behavior. Parallel execution deferred.

### Decision: `CampaignOrchestrator` Refactor — Internal Composition, External Identity

**Choice**: `CampaignOrchestrator.run()` builds a `Pipeline` from 11 SQX-specific stage classes (defined in `phase4/`, not `pipeline/`), passes `PipelineContext` initialized from `CampaignConfig`, runs via `PipelineRunner`, maps `PipelineResult` → `CampaignResult`.
**Alternatives considered**: Subclass `PipelineRunner`; replace `CampaignOrchestrator` entirely with `Pipeline`.
**Rationale**: Public API (`CampaignOrchestrator`, `CampaignConfig`, `CampaignResult`, `CampaignPhase`, `PhaseStatus`, `PhaseResult`, `run_campaign`) must remain 100% identical. Internal delegation preserves behavior while enabling reuse. Progress callbacks fire at each phase transition with same signature.

### Decision: CLI `DaemonContext` as Async Context Manager

**Choice**: New `DaemonContext(sqx_path, port, json_output)` with `__aenter__` → `daemon.start()`, `__aexit__` → `daemon.stop(force=False)`. Consumes CLI args namespace.
**Alternatives considered**: Function decorator; base class for CLI commands.
**Rationale**: Async context manager is Pythonic, explicit, guarantees cleanup on exception. Reduces ~20 lines of daemon boilerplate per CLI command to 3 lines. Meets ≥60% reduction target.

### Decision: Exception Hierarchy in `tools/exceptions.py`

**Choice**: Add `PipelineError(QuantLabError)`, `StageExecutionError(PipelineError)` with `stage_name` + `original_error`, `PipelineConfigError(PipelineError)` for YAML parsing.
**Alternatives considered**: Reuse `CampaignError`; new top-level exception.
**Rationale**: Keeps hierarchy clean. `PipelineError` isolates pipeline-framework failures from domain (`CampaignError`) and core (`QuantLabError`) errors. `StageExecutionError` preserves stage context for debugging.

## Data Flow

```
ValidateStage  → config → TranslateStage → cfx_bytes → DaemonStartStage → daemon_url
CampaignStage  ←────────────────────────────────────────────────────────← (daemon_url + cfx)
ExportStage    ← campaign_name
ReadStage      ← export_path
ComputeStats   ← parsed_results
KnowledgeStore ← stats + results
ReportStage    ← stats + results
```

**PipelineContext flow**:
- `ctx.config` — immutable input from `CampaignConfig` (or YAML)
- `ctx.artifacts` — mutable dict; each stage writes to keys in `provides`, reads from `requires`
- `ctx.metadata` — timestamps, stage durations, run ID
- `ctx.error` — set by runner on first failure; subsequent stages skipped

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/pipeline/__init__.py` | Create | Public exports: Stage, Pipeline, PipelineContext, PipelineRunner, StageResult, PipelineResult, built-in stages |
| `sdk/quantlab/pipeline/base.py` | Create | `Stage` ABC, `Pipeline` dataclass with `.then()`, `PipelineContext` dataclass |
| `sdk/quantlab/pipeline/models.py` | Create | `StageResult`, `PipelineResult`, `StageStatus` enum (PENDING, RUNNING, COMPLETED, FAILED, SKIPPED) |
| `sdk/quantlab/pipeline/runner.py` | Create | `PipelineRunner.run(pipeline, ctx)` — sequential execution, timing, error isolation |
| `sdk/quantlab/pipeline/stages.py` | Create | 9 abstract base stages: ValidateStage, TranslateStage, DaemonStartStage, CampaignStage, ExportStage, ReadStage, ComputeStatsStage, KnowledgeStoreStage, ReportStage |
| `sdk/quantlab/phase4/campaign_orchestrator.py` | Modify | Refactor `run()` to build Pipeline from SQX-specific stages in `phase4/stages/`, delegate to `PipelineRunner`, map results. Public API unchanged. |
| `sdk/quantlab/phase4/__init__.py` | Modify | Re-export new internal stage classes if needed; no public API change |
| `sdk/quantlab/phase4/stages/__init__.py` | Create | SQX-specific implementations of the 9 abstract stages |
| `sdk/quantlab/phase4/stages/validate.py` | Create | `SQXValidateStage` — license check, extends `ValidateStage` |
| `sdk/quantlab/phase4/stages/translate.py` | Create | `SQXTranslateStage` — DSL→CFX, extends `TranslateStage` |
| `sdk/quantlab/phase4/stages/daemon_start.py` | Create | `SQXDaemonStartStage` — starts daemon, extends `DaemonStartStage` |
| `sdk/quantlab/phase4/stages/campaign.py` | Create | `SQXCampaignStage` — load config, start project, poll, extends `CampaignStage` |
| `sdk/quantlab/phase4/stages/export.py` | Create | `SQXExportStage` — export results/databanks, extends `ExportStage` |
| `sdk/quantlab/phase4/stages/read.py` | Create | `SQXReadStage` — parse CSV/XLSX, extends `ReadStage` |
| `sdk/quantlab/phase4/stages/compute.py` | Create | `SQXComputeStatsStage` — StatisticsEngine, extends `ComputeStatsStage` |
| `sdk/quantlab/phase4/stages/store.py` | Create | `SQXKnowledgeStoreStage` — KnowledgeStore, extends `KnowledgeStoreStage` |
| `sdk/quantlab/phase4/stages/report.py` | Create | `SQXReportStage` — generate report, extends `ReportStage` |
| `sdk/quantlab/tools/exceptions.py` | Modify | Add `PipelineError`, `StageExecutionError`, `PipelineConfigError` |
| `sdk/quantlab/cli/main.py` | Modify | Add `pipeline` subcommand with `run`/`status`/`list`; add `DaemonContext` helper |
| `sdk/quantlab/cli/daemon.py` | Create (optional) | Extract `DaemonContext` here if file grows; otherwise inline in `main.py` |

## Interfaces / Contracts

```python
# pipeline/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

@dataclass
class PipelineContext:
    config: dict
    artifacts: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    error: Exception | None = None

class Stage(ABC):
    name: str
    requires: list[str]
    provides: list[str]

    @abstractmethod
    async def execute(self, ctx: PipelineContext) -> Any:
        ...

@dataclass
class Pipeline:
    name: str
    stages: list[Stage] = field(default_factory=list)

    def then(self, stage: Stage) -> "Pipeline":
        self.stages.append(stage)
        return self
```

```python
# pipeline/models.py
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class StageResult:
    stage_name: str
    status: StageStatus
    duration: float = 0.0
    error: str | None = None
    output: Any = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

@dataclass
class PipelineResult:
    pipeline_name: str
    stages: list[StageResult] = field(default_factory=list)
    total_duration: float = 0.0
    error: str | None = None

    @property
    def is_successful(self) -> bool:
        return self.error is None and all(s.status == StageStatus.COMPLETED for s in self.stages)
```

```python
# pipeline/stages.py (abstract base classes — SQX-agnostic)
class ValidateStage(Stage):
    name = "validate"
    requires = []
    provides = ["validated_config"]
    async def execute(self, ctx): ...

class TranslateStage(Stage):
    name = "translate"
    requires = ["validated_config"]
    provides = ["cfx_bytes", "cfx_path"]
    async def execute(self, ctx): ...

class DaemonStartStage(Stage):
    name = "daemon_start"
    requires = []
    provides = ["daemon_url", "daemon_manager"]
    async def execute(self, ctx): ...

class CampaignStage(Stage):
    name = "campaign"
    requires = ["daemon_url", "cfx_path"]
    provides = ["campaign_name", "campaign_status"]
    async def execute(self, ctx): ...

class ExportStage(Stage):
    name = "export"
    requires = ["campaign_name", "daemon_url"]
    provides = ["export_paths"]
    async def execute(self, ctx): ...

class ReadStage(Stage):
    name = "read"
    requires = ["export_paths"]
    provides = ["parsed_results"]
    async def execute(self, ctx): ...

class ComputeStatsStage(Stage):
    name = "compute_stats"
    requires = ["parsed_results"]
    provides = ["statistics"]
    async def execute(self, ctx): ...

class KnowledgeStoreStage(Stage):
    name = "knowledge_store"
    requires = ["parsed_results", "statistics"]
    provides = ["knowledge_keys"]
    async def execute(self, ctx): ...

class ReportStage(Stage):
    name = "report"
    requires = ["parsed_results", "statistics"]
    provides = ["report_path"]
    async def execute(self, ctx): ...
```

```python
# tools/exceptions.py additions
class PipelineError(QuantLabError):
    pass

class StageExecutionError(PipelineError):
    def __init__(self, detail: str, *, stage_name: str, original_error: BaseException | None = None):
        super().__init__(detail, cause=original_error)
        self.stage_name = stage_name

class PipelineConfigError(PipelineError):
    pass
```

```python
# cli/main.py — DaemonContext helper
class DaemonContext:
    def __init__(self, sqx_path: str, port: int = 8888, json_output: bool = False):
        self.sqx_path = sqx_path
        self.port = port
        self.json_output = json_output
        self._daemon: SQXDaemonManager | None = None

    async def __aenter__(self) -> tuple[str, SQXDaemonManager]:
        self._daemon = SQXDaemonManager(self.sqx_path, port=self.port)
        base_url = await self._daemon.start()
        return base_url, self._daemon

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._daemon:
            await self._daemon.stop(force=False)

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "DaemonContext":
        return cls(args.sqx_path or DEFAULT_SQX_PATH, args.port, args.json)
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `pipeline/` core (base, runner, models, stages) | Pure Python, no SQX. Mock `PipelineContext`, verify artifact flow, timing, error isolation, skip-on-failure |
| Unit | `phase4/stages/` SQX-specific stages | Mock `SQXDaemonManager`, `CommandDispatcher`, `StatisticsEngine`, `KnowledgeStore`. Verify `requires`/`provides` contracts |
| Integration | `CampaignOrchestrator` refactor | All 436 existing Phase 4 tests must pass unchanged. Add 2 integration tests: dry-run and real-run (if SQX available) |
| E2E | CLI `pipeline run <yaml>` | Write valid YAML with 3-4 stages, execute via CLI, verify stdout streaming, exit codes |
| E2E | CLI `DaemonContext` reduction | Count lines in `cmd_portfolio_run` before/after; verify ≥60% reduction |

## Migration / Rollout

No migration required. `CampaignOrchestrator` public API is identical. Existing code using `run_campaign()` or `CampaignOrchestrator` works without changes. New `pipeline/` module is additive.

Rollback plan (per proposal):
1. Revert `campaign_orchestrator.py` to pre-refactor state
2. Remove `sdk/quantlab/pipeline/` directory
3. Revert `cli/main.py` pipeline additions and daemon helper
4. Verify all 436 Phase 4 tests pass

## Open Questions

- [ ] Should `pipeline/status` and `pipeline/list` persist run history to a local file (JSONL/CSV) or rely on in-memory only for Phase 5?
- [ ] YAML stage registry: built-in stages registered by string name (e.g., `ValidateStage`) vs. fully qualified import paths?
- [ ] `DaemonContext` location: inline in `cli/main.py` or separate `cli/daemon.py`? (Lean toward separate file for reusability)
- [ ] Progress callback signature: keep `(CampaignPhase, PhaseStatus, str)` for `CampaignOrchestrator` or map to `PipelineRunner` events?