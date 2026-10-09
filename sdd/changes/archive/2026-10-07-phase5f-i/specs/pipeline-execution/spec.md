# Delta Spec: Pipeline Execution Real

## Change Summary

Modifies **pipeline-cli** capability (existing spec: `openspec/specs/pipeline-cli/spec.md`) to execute real SQX pipeline stages via `PipelineRunner.run()` instead of only supporting `--dry-run`. Wires `phase4.stages` concrete SQX stages into `PipelineRegistry`. Persists `PipelineRun` to `knowledge/pipeline-runs/`. Handles errors/timeouts with proper exit codes.

**Type**: MODIFIED capability (delta spec)

---

## ADDED Requirements

### Requirement: FR-101 — SQX Stage Registration in Pipeline Registry

The system SHALL register all concrete SQX stage classes from `quantlab.phase4.stages` into `PipelineRegistry` at startup.

Stage mappings:
| Stage Type (YAML) | Concrete Class | Module |
|-------------------|----------------|--------|
| `validate` | `SQXValidateStage` | `quantlab.phase4.stages.validate` |
| `translate` | `SQXTranslateStage` | `quantlab.phase4.stages.translate` |
| `optimize` | `SQXOptimizeStage` | `quantlab.phase4.stages.optimize` |
| `walkforward` | `SQXWalkForwardStage` | `quantlab.phase4.stages.walkforward` |
| `montecarlo` | `SQXMonteCarloStage` | `quantlab.phase4.stages.montecarlo` |
| `portfolio` | `SQXPortfolioStage` | `quantlab.phase4.stages.portfolio` |
| `risk` | `SQRiskStage` | `quantlab.phase4.stages.risk` |
| `report` | `SQXReportStage` | `quantlab.phase4.stages.report` |
| `knowledge_store` | `SQXKnowledgeStoreStage` | `quantlab.phase4.stages.knowledge_store` |
| `history` | `SQXHistoryStage` | `quantlab.phase4.stages.history` |
| `finalize` | `SQXFinalizeStage` | `quantlab.phase4.stages.finalize` |

Registry SHALL resolve `type: builtin` → `type: <stage_name>` to concrete class.

#### Scenario: Registry resolves all 11 SQX stage types
- GIVEN `PipelineRegistry()` instantiated
- WHEN `registry.get_stage_class("translate")` called
- THEN returns `SQXTranslateStage` class
- AND all 11 stage types resolve to concrete classes

---

### Requirement: FR-102 — PipelineContext with Full Config

The system SHALL create `PipelineContext` with complete execution config before running pipeline.

`PipelineContext` SHALL include:
- `sqx_path: Path` — path to SQX installation (from config/env)
- `campaign_name: str` — unique campaign identifier (e.g., `campaign-{run_id}`)
- `output_dir: Path` — `knowledge/results/pipeline-{run_id}/`
- `pipeline_config: PipelineConfig` — resolved config with param overrides
- `knowledge_root: Path` — `QUANTLAB_KNOWLEDGE_ROOT`
- `timeout_seconds: int` — per-stage timeout (default: 300)
- `dry_run: bool` — False for real execution

#### Scenario: Context created with all fields
- GIVEN pipeline run initiated
- WHEN `PipelineContext` constructed
- THEN all fields populated
- AND `output_dir` created
- AND `campaign_name` follows pattern `campaign-pipe-run-{timestamp}-{uuid}`

---

### Requirement: FR-103 — PipelineRunner Executes Real Stages

The system SHALL invoke `PipelineRunner.run(pipeline_config, context)` which executes each stage sequentially.

`PipelineRunner.run()` SHALL:
1. Create `Pipeline` instance from config (using registered stage classes)
2. For each stage in order:
   a. Record stage start time
   b. Call `stage.execute(context)`
   c. Capture stage output/result
   d. Record stage duration, status
   d. On stage failure: stop pipeline, mark status `failed`, persist error
3. On all stages success: mark pipeline `completed`
4. Return `PipelineResult` with stages, outputs, final status

#### Scenario: All 11 stages execute sequentially
- GIVEN valid pipeline config, SQX available
- WHEN `PipelineRunner.run()` called
- THEN stages execute in order: validate → translate → optimize → walkforward → montecarlo → portfolio → risk → report → knowledge_store → history → finalize
- AND each stage `execute()` called with context
- AND stage results accumulated

#### Scenario: Stage failure stops pipeline
- GIVEN stage 3 (optimize) raises `SQXExecutionError`
- WHEN pipeline runs
- THEN stages 1-2 complete, stage 3 marked failed
- AND stages 4-11 NOT executed
- AND pipeline status `failed`
- AND error persisted in history

---

### Requirement: FR-104 — PipelineRun Persistence to Knowledge Lake

The system SHALL persist `PipelineRun` record to `knowledge/pipeline-runs/pipe-run-{timestamp}-{uuid}.yaml` on completion (success or failure).

`PipelineRun` schema (extends existing history schema):
```yaml
run_id: "pipe-run-20240718-120000-abc123"
pipeline_name: "wf_opt"
status: "completed"  # running, completed, failed
started_at: "2024-07-18T12:00:00Z"
completed_at: "2024-07-18T12:05:30Z"
duration_seconds: 330.5
campaign_id: "campaign-pipe-run-20240718-120000-abc123"
stages:
  - name: validate
    status: completed
    duration_seconds: 2.1
    output: "validation_passed"
    error: null
  - name: translate
    status: completed
    duration_seconds: 15.3
    output: "cfx_base64..."
    error: null
  # ... all 11 stages
config_snapshot: {...}  # full resolved pipeline config
error: null  # or error message if failed
```

#### Scenario: Run persisted on success
- GIVEN pipeline completes all stages
- WHEN `PipelineRunner` finishes
- THEN YAML file exists in `knowledge/pipeline-runs/`
- AND all 11 stages recorded with `status: completed`
- AND `campaign_id` matches context

#### Scenario: Run persisted on failure
- GIVEN stage 5 fails with timeout
- WHEN pipeline stops
- THEN YAML file exists with `status: failed`
- AND stages 1-4 `completed`, stage 5 `failed`, stages 6-11 absent or `skipped`
- AND `error` field populated

---

### Requirement: FR-105 — CLI: Real Execution Path in `cmd_pipeline_run`

The system SHALL modify `cmd_pipeline_run` in `quantlab.cli.pipeline_commands` to execute real pipeline when `--dry-run` NOT specified.

Behavior:
- `--dry-run`: existing behavior (CFX base64 to stdout, exit 0/4)
- No `--dry-run`: real execution path:
  1. Load pipeline config from registry (with `--config` and `--params` overrides)
  2. Create `PipelineContext` with `dry_run=False`
  3. Persist initial history entry with `status: "running"`
  4. Call `PipelineRunner.run(config, context)`
  5. On success: update history `status: "completed"`, persist results
  6. On failure: update history `status: "failed"`, persist error
  6. Exit codes: 0 success, 1 pipeline not found, 2 config error, 3 execution error, 4 dry-run output

#### Scenario: Real run without --dry-run
- GIVEN `quantlab pipeline run wf_opt` (no --dry-run)
- WHEN command executes
- THEN `PipelineRunner.run()` called
- AND history persisted with `status: completed`
- AND exit code 0

#### Scenario: Dry-run unchanged
- GIVEN `quantlab pipeline run wf_opt --dry-run`
- WHEN command executes
- THEN CFX base64 printed to stdout
- AND exit code 0 or 4
- AND NO history persisted (or status "dry-run")

---

### Requirement: FR-106 — Error Handling and Exit Codes

The system SHALL handle errors with specific exit codes and persisted error state.

| Error Condition | Exit Code | History Status | Error Field |
|-----------------|-----------|----------------|-------------|
| Pipeline not found in registry | 1 | N/A (early exit) | N/A |
| Config validation error (YAML parse, schema) | 2 | failed | Config error details |
| SQX binary not found / not executable | 3 | failed | "SQX not found at path..." |
| Stage execution error (SQX CLI fails) | 3 | failed | Stage error output |
| Stage timeout (> timeout_seconds) | 3 | failed | "Stage X timed out after Ys" |
| Knowledge Lake write error | 3 | failed | "Failed to persist: ..." |
| Unexpected exception | 3 | failed | Exception traceback |
| Dry-run output | 4 | N/A | N/A |

#### Scenario: SQX not found returns exit code 3
- GIVEN `sqx_path` config points to nonexistent binary
- WHEN pipeline runs (real execution)
- THEN exit code 3
- AND history `status: failed`
- AND `error` contains "SQX not found"

#### Scenario: Stage timeout handled
- GIVEN stage `optimize` exceeds `timeout_seconds` (default 300)
- WHEN pipeline runs
- THEN stage terminated
- AND pipeline status `failed`
- AND history records timeout error

---

## MODIFIED Requirements

### Requirement: Pipeline Registry (MODIFIED)

**Full updated requirement — replaces existing `Requirement: Pipeline Registry` in `openspec/specs/pipeline-cli/spec.md`**

The system MUST provide a `PipelineRegistry` class that discovers and registers pipelines from YAML configuration files AND registers concrete SQX stage classes from `quantlab.phase4.stages`.

```python
class PipelineRegistry:
    def __init__(self, config_dirs: list[Path] | None = None):
        """Scan config_dirs for pipeline YAML files. Default: [Path('config/pipelines'), Path.home()/.quantlab/pipelines]"""
        # Also auto-registers SQX stages from quantlab.phase4.stages

    def discover(self) -> dict[str, PipelineConfig]:
        """Return dict of pipeline_name → PipelineConfig (parsed from YAML)."""

    def get(self, name: str) -> PipelineConfig | None:
        """Get single pipeline config by name."""

    def list_pipelines(self) -> list[PipelineSummary]:
        """Return list of PipelineSummary(name, description, version, source_path, stage_count)."""

    def get_stage_class(self, stage_type: str) -> type[PipelineStage] | None:
        """Resolve stage type to concrete class. Returns SQX stage for builtin types."""
        # Maps: validate→SQXValidateStage, translate→SQXTranslateStage, etc.

    def create_pipeline(self, config: PipelineConfig) -> Pipeline:
        """Instantiate Pipeline with concrete stage classes from config."""
```

`PipelineConfig` is the existing model from `pipeline.models` (defines stages, parameters, SQX connection).
`PipelineSummary`: `name`, `description`, `version`, `source_path`, `stage_count`.

Pipeline YAML schema (unchanged, but `type` values now map to SQX stages):
```yaml
name: "my-pipeline"
description: "Walk-forward optimization pipeline"
version: "1.0"
stages:
  - name: validate
    type: validate      # registry resolves to SQXValidateStage
    config: {}
  - name: translate
    type: translate     # registry resolves to SQXTranslateStage
    config: {}
  # ... all 11 stages
```

(Previously: registry only discovered pipeline YAMLs. Now: also registers SQX stage classes and instantiates Pipeline with them.)

#### Scenario: Registry resolves SQX stage classes
- GIVEN `PipelineRegistry()` instantiated
- WHEN `registry.get_stage_class("optimize")` called
- THEN returns `SQXOptimizeStage` class
- AND `registry.create_pipeline(config)` builds `Pipeline` with all 11 SQX stages

#### Scenario: Discover built-in and custom pipelines (unchanged)
- GIVEN `config/pipelines/wf_opt.yaml` and `~/.quantlab/pipelines/custom.yaml`
- WHEN `PipelineRegistry().discover()` called
- THEN returns both configs, keys are pipeline names

#### Scenario: Pipeline not found returns None (unchanged)
- GIVEN registry with pipelines `["a", "b"]`
- WHEN `registry.get("c")` called
- THEN returns `None`

---

### Requirement: CLI Pipeline Subcommands (MODIFIED)

**Full updated requirement — replaces existing `Requirement: CLI Pipeline Subcommands` in `openspec/specs/pipeline-cli/spec.md`**

The system MUST extend `quantlab-cli` with `pipeline` subcommand group:

```
quantlab pipeline run <name> [--config file.yaml] [--dry-run] [--output-dir PATH] [--params key=val ...] [--timeout SECONDS]
quantlab pipeline list [--json]
quantlab pipeline history [--limit 10] [--status running|completed|failed] [--json]
```

#### `pipeline run` (MODIFIED)
- `--config`: override pipeline config file (merges with discovered config)
- `--dry-run`: outputs CFX base64 (like existing CLI dry-run), does not execute SQX
- `--output-dir`: where to write results (default: `knowledge/results/pipeline-{run_id}/`)
- `--params`: override pipeline parameters as `key=value` pairs (repeatable)
- `--timeout`: per-stage timeout in seconds (default: 300)
- Exit codes: 0 success, 1 pipeline not found, 2 config error, 3 execution error, 4 dry-run output

#### `pipeline list` (UNCHANGED)
- Outputs table: `name | description | version | stages | source`
- `--json` option for machine-readable output

#### `pipeline history` (UNCHANGED)
- Reads `knowledge/pipeline-runs/*.yaml`
- Filters by `--status`
- Limits to `--limit` most recent (default 10)
- Outputs table: `run_id | pipeline | status | started | duration | stages`
- `--json` option

#### Scenario: Real run executes pipeline (NEW)
- GIVEN pipeline `wf_opt` exists with 11 SQX stages
- WHEN `quantlab pipeline run wf_opt` (no --dry-run)
- THEN `PipelineRunner.run()` called
- AND history persisted with `status: completed`
- AND exit code 0

#### Scenario: Run pipeline with param overrides (UNCHANGED)
- GIVEN `quantlab pipeline run wf_opt --params window=10 --params step=2`
- WHEN executed
- THEN pipeline config merged with overrides, passed to PipelineRunner

#### Scenario: List pipelines shows custom and built-in (UNCHANGED)
- GIVEN built-in `config/pipelines/basic.yaml` and custom `~/.quantlab/pipelines/mine.yaml`
- WHEN `quantlab pipeline list`
- THEN both shown in table

#### Scenario: History filters by status (UNCHANGED)
- GIVEN 5 completed, 2 failed, 1 running runs in history
- WHEN `quantlab pipeline history --status failed`
- THEN only 2 failed runs shown

#### Scenario: Dry-run delegates to PipelineRunner.dry_run (UNCHANGED)
- GIVEN `--dry-run` flag
- WHEN CLI runs pipeline
- THEN `PipelineRunner.dry_run()` called, CFX base64 printed

---

### Requirement: Pipeline Runner Integration (MODIFIED)

**Full updated requirement — replaces existing `Requirement: Pipeline Runner Integration` in `openspec/specs/pipeline-cli/spec.md`**

The CLI MUST reuse existing `PipelineRunner` from `pipeline.runner` but with real SQX stage execution.

```python
# Existing PipelineRunner interface (reused)
class PipelineRunner:
    def run(self, pipeline: PipelineConfig, params: dict | None = None) -> PipelineResult: ...
    def dry_run(self, pipeline: PipelineConfig, params: dict | None = None) -> str: ...  # returns CFX base64
```

**Implementation change**: `PipelineRunner.run()` now executes concrete SQX stages (from `phase4.stages`) via `Pipeline` framework, not mock/stub.

CLI command constructs `PipelineConfig` (from registry + overrides), creates `PipelineContext`, calls `runner.run()` or `runner.dry_run()`, persists history via `KnowledgeStore`.

#### Scenario: Dry-run delegates to PipelineRunner.dry_run (UNCHANGED)
- GIVEN `--dry-run` flag
- WHEN CLI runs pipeline
- THEN `PipelineRunner.dry_run()` called, CFX base64 printed

#### Scenario: Real run delegates to PipelineRunner.run (MODIFIED)
- GIVEN no `--dry-run`
- WHEN CLI runs pipeline
- THEN `PipelineRunner.run()` called with concrete SQX stages
- AND history persisted with results

---

## REMOVED Requirements

None. This delta only adds/modifies.

---

## RENAMED Requirements

None.

---

## Interface Specifications

### Updated `PipelineRegistry` (quantlab.pipeline.registry)

```python
# quantlab.pipeline.registry
class PipelineRegistry:
    def __init__(self, config_dirs: list[Path] | None = None): ...

    def discover(self) -> dict[str, PipelineConfig]: ...

    def get(self, name: str) -> PipelineConfig | None: ...

    def list_pipelines(self) -> list[PipelineSummary]: ...

    # NEW: SQX stage resolution
    def get_stage_class(self, stage_type: str) -> type[PipelineStage] | None: ...

    def create_pipeline(self, config: PipelineConfig) -> Pipeline: ...
```

### PipelineContext (quantlab.pipeline.context)

```python
# quantlab.pipeline.context
class PipelineContext:
    def __init__(
        self,
        sqx_path: Path,
        campaign_name: str,
        output_dir: Path,
        pipeline_config: PipelineConfig,
        knowledge_root: Path,
        timeout_seconds: int = 300,
        dry_run: bool = False
    ): ...
```

### PipelineRunner (quantlab.pipeline.runner) — behavior change only

```python
# quantlab.pipeline.runner
class PipelineRunner:
    def run(self, pipeline: PipelineConfig, context: PipelineContext) -> PipelineResult: ...
    def dry_run(self, pipeline: PipelineConfig, params: dict | None = None) -> str: ...
```

### PipelineResult (quantlab.pipeline.models)

```python
# quantlab.pipeline.models
class PipelineResult(BaseModel):
    run_id: str
    pipeline_name: str
    status: Literal["completed", "failed"]
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    campaign_id: str
    stages: list[StageResult]
    config_snapshot: dict
    error: str | None = None

class StageResult(BaseModel):
    name: str
    status: Literal["completed", "failed", "skipped"]
    duration_seconds: float
    output: Any | None
    error: str | None
```

### CLI Commands (quantlab.cli.pipeline_commands)

```python
# quantlab.cli.pipeline_commands
def pipeline_run_command(args: argparse.Namespace) -> int: ...
def pipeline_list_command(args: argparse.Namespace) -> int: ...
def pipeline_history_command(args: argparse.Namespace) -> int: ...
```

### Phase 4 Stages Export (quantlab.phase4.stages)

```python
# quantlab.phase4.stages.__init__.py
from .validate import SQXValidateStage
from .translate import SQXTranslateStage
from .optimize import SQXOptimizeStage
from .walkforward import SQXWalkForwardStage
from .montecarlo import SQXMonteCarloStage
from .portfolio import SQXPortfolioStage
from .risk import SQRiskStage
from .report import SQXReportStage
from .knowledge_store import SQXKnowledgeStoreStage
from .history import SQXHistoryStage
from .finalize import SQXFinalizeStage

__all__ = [
    "SQXValidateStage", "SQXTranslateStage", "SQXOptimizeStage",
    "SQXWalkForwardStage", "SQXMonteCarloStage", "SQXPortfolioStage",
    "SQRiskStage", "SQXReportStage", "SQXKnowledgeStoreStage",
    "SQXHistoryStage", "SQXFinalizeStage",
]
```

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| Registry resolves all 11 SQX stage types | Unit test: `registry.get_stage_class("optimize")` returns `SQXOptimizeStage` |
| Pipeline runs 11 stages sequentially | Integration test: mock SQX, verify 11 `execute()` calls in order |
| PipelineRun persisted on success | Integration test: run pipeline, check `knowledge/pipeline-runs/` YAML |
| PipelineRun persisted on failure | Integration test: mock stage failure, check YAML has `status: failed` |
| Exit code 3 on SQX execution error | Integration test: mock SQX error, assert exit code 3 |
| Exit code 3 on stage timeout | Integration test: slow mock stage, assert timeout handling |
| Dry-run unchanged (exit 0/4, CFX output) | Regression test: `quantlab pipeline run x --dry-run` |
| `--params` overrides work in real run | Integration test: pass params, verify in stage config |
| `--timeout` respected per stage | Integration test: set timeout=1, slow stage, assert timeout |
| History persists `campaign_id` linking to results | Check YAML has `campaign_id` matching `campaign-{run_id}` |
| `phase4.stages` exports all 11 classes | `from quantlab.phase4.stages import SQXOptimizeStage` succeeds |

---

## Non-Functional Requirements

- **Performance**: Pipeline discovery + stage registration < 200ms
- **Timeout handling**: Stage timeout uses `subprocess.run(timeout=...)` or asyncio wait_for
- **Error messages**: Clear stderr output for each exit code condition
- **Dependencies**: No new deps (uses existing `pipeline`, `phase4`, `knowledge`, `subprocess`)
- **Backward compatibility**: `--dry-run` behavior unchanged; existing pipeline YAMLs work
- **Knowledge Lake separation**: Pipeline runs in `pipeline-runs/`, campaigns in `structured/`, results in `results/`