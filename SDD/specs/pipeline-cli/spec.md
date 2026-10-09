# Pipeline CLI Specification

## Purpose

Exposes the generic Pipeline framework (`sdk/quantlab/pipeline/`) via CLI with pipeline discovery, execution (with dry-run), and run history persistence in the Knowledge Lake. Reuses existing `PipelineRunner` and SQX stages.

---

## Requirements

### Requirement: Pipeline Registry

The system MUST provide a `PipelineRegistry` class that discovers and registers pipelines from YAML configuration files:

```python
class PipelineRegistry:
    def __init__(self, config_dirs: list[Path] | None = None):
        """Scan config_dirs for pipeline YAML files. Default: [Path('config/pipelines'), Path.home()/.quantlab/pipelines]"""

    def discover(self) -> dict[str, PipelineConfig]:
        """Return dict of pipeline_name → PipelineConfig (parsed from YAML)."""

    def get(self, name: str) -> PipelineConfig | None:
        """Get single pipeline config by name."""

    def list_pipelines(self) -> list[PipelineSummary]:
        """Return list of PipelineSummary(name, description, version, source_path, stage_count)."""
```

`PipelineConfig` is the existing model from `pipeline.models` (defines stages, parameters, SQX connection).
`PipelineSummary`: `name`, `description`, `version`, `source_path`, `stage_count`.

Pipeline YAML schema:
```yaml
name: "my-pipeline"
description: "Walk-forward optimization pipeline"
version: "1.0"
stages:
  - name: translate
    type: translate
    config: {...}
  - name: optimize
    type: optimize
    config: {...}
```

#### Scenario: Discover built-in and custom pipelines
- GIVEN `config/pipelines/wf_opt.yaml` and `~/.quantlab/pipelines/custom.yaml`
- WHEN `PipelineRegistry().discover()` called
- THEN returns both configs, keys are pipeline names

#### Scenario: Pipeline not found returns None
- GIVEN registry with pipelines `["a", "b"]`
- WHEN `registry.get("c")` called
- THEN returns `None`

---

### Requirement: Pipeline Run History in Knowledge Lake

The system MUST persist pipeline run history to Knowledge Lake at `knowledge/pipeline-runs/{run_id}.yaml`:

```yaml
run_id: "pipe-run-20240718-120000-abc123"
pipeline_name: "wf_opt"
status: "completed"  # running, completed, failed
started_at: "2024-07-18T12:00:00Z"
completed_at: "2024-07-18T12:05:30Z"
duration_seconds: 330.5
stages:
  - name: translate
    status: completed
    duration_seconds: 45.2
    output: "cfx_base64..."
  - name: optimize
    status: completed
    duration_seconds: 285.3
    output: "results.yaml"
error: null
config_snapshot: {...}  # full pipeline config used
```

Run ID format: `pipe-run-{timestamp}-{short_uuid}` (timestamp: YYYYMMDD-HHMMSS).
Uses existing `KnowledgeStore` for persistence (Feature 5c dependency).

#### Scenario: Run history saved on completion
- GIVEN pipeline executed via CLI
- WHEN run completes (success or failure)
- THEN `knowledge/pipeline-runs/pipe-run-...yaml` exists with full record

#### Scenario: Running status persisted at start
- GIVEN pipeline run starts
- WHEN `PipelineRunner` begins
- THEN history entry created with `status: "running"`, updated on completion

---

### Requirement: CLI Pipeline Subcommands

The system MUST extend `quantlab-cli` with `pipeline` subcommand group:

```
quantlab-cli pipeline run <name> [--config file.yaml] [--dry-run] [--output-dir PATH] [--params key=val ...]
quantlab-cli pipeline list
quantlab-cli pipeline history [--limit 10] [--status running|completed|failed]
```

#### `pipeline run`
- `--config`: override pipeline config file (merges with discovered config)
- `--dry-run`: outputs CFX base64 (like existing CLI dry-run), does not execute SQX
- `--output-dir`: where to write results (default: `knowledge/results/pipeline-{run_id}/`)
- `--params`: override pipeline parameters as `key=value` pairs (repeatable)
- Exit codes: 0 success, 1 pipeline not found, 2 config error, 3 execution error, 4 dry-run output

#### `pipeline list`
- Outputs table: `name | description | version | stages | source`
- `--json` option for machine-readable output

#### `pipeline history`
- Reads `knowledge/pipeline-runs/*.yaml`
- Filters by `--status`
- Limits to `--limit` most recent (default 10)
- Outputs table: `run_id | pipeline | status | started | duration | stages`
- `--json` option

#### Scenario: Run pipeline with dry-run
- GIVEN pipeline `wf_opt` exists
- WHEN `quantlab-cli pipeline run wf_opt --dry-run`
- THEN prints CFX base64 to stdout, exit code 0 or 4 (dry-run output)

#### Scenario: Run pipeline with param overrides
- GIVEN `quantlab-cli pipeline run wf_opt --params window=10 --params step=2`
- WHEN executed
- THEN pipeline config merged with overrides, passed to PipelineRunner

#### Scenario: List pipelines shows custom and built-in
- GIVEN built-in `config/pipelines/basic.yaml` and custom `~/.quantlab/pipelines/mine.yaml`
- WHEN `quantlab-cli pipeline list`
- THEN both shown in table

#### Scenario: History filters by status
- GIVEN 5 completed, 2 failed, 1 running runs in history
- WHEN `quantlab-cli pipeline history --status failed`
- THEN only 2 failed runs shown

---

### Requirement: Pipeline Runner Integration

The CLI MUST reuse existing `PipelineRunner` from `pipeline.runner`:

```python
# Existing PipelineRunner interface
class PipelineRunner:
    def run(self, pipeline: PipelineConfig, params: dict | None = None) -> PipelineResult: ...
    def dry_run(self, pipeline: PipelineConfig, params: dict | None = None) -> str: ...  # returns CFX base64
```

CLI command constructs `PipelineConfig` (from registry + overrides), calls `runner.run()` or `runner.dry_run()`, persists history via `KnowledgeStore`.

#### Scenario: Dry-run delegates to PipelineRunner.dry_run
- GIVEN `--dry-run` flag
- WHEN CLI runs pipeline
- THEN `PipelineRunner.dry_run()` called, CFX base64 printed

#### Scenario: Real run delegates to PipelineRunner.run
- GIVEN no `--dry-run`
- WHEN CLI runs pipeline
- THEN `PipelineRunner.run()` called, history persisted with results

---

## Data Flow

```
config/pipelines/*.yaml
       │
       ├─► PipelineRegistry.discover()
       │       │
       │       └─► PipelineConfig (Pydantic)
       │
       ├─► CLI: pipeline list → PipelineSummary table
       │
       ├─► CLI: pipeline run <name>
       │       ├─► Registry.get(name) → PipelineConfig
       │       ├─► Merge --config YAML + --params overrides
       │       ├─► Create run_id, persist history (status=running)
       │       ├─► If --dry-run:
       │       │       └─► PipelineRunner.dry_run() → CFX base64 → stdout
       │       │
       │       └─► Else:
       │               ├─► PipelineRunner.run() → PipelineResult
       │               ├─► Persist results to Knowledge Lake
       │               └─► Update history (status=completed/failed, stages, duration)
       │
       └─► CLI: pipeline history
               ├─► KnowledgeStore.query(path="pipeline-runs/")
               ├─► Filter by status, sort by started_at desc
               └─► Limit → table/JSON output
```

---

## Interface Specifications

```python
# quantlab.pipeline.registry
class PipelineRegistry:
    def __init__(self, config_dirs: list[Path] | None = None): ...
    def discover(self) -> dict[str, PipelineConfig]: ...
    def get(self, name: str) -> PipelineConfig | None: ...
    def list_pipelines(self) -> list[PipelineSummary]: ...

class PipelineSummary(BaseModel):
    name: str
    description: str
    version: str
    source_path: Path
    stage_count: int

# quantlab.pipeline.runner (existing - reused)
class PipelineRunner:
    def run(self, pipeline: PipelineConfig, params: dict | None = None) -> PipelineResult: ...
    def dry_run(self, pipeline: PipelineConfig, params: dict | None = None) -> str: ...

# quantlab.cli.pipeline_commands
def pipeline_run_command(args: argparse.Namespace) -> int: ...
def pipeline_list_command(args: argparse.Namespace) -> int: ...
def pipeline_history_command(args: argparse.Namespace) -> int: ...

# quantlab.cli.main (extension)
def add_pipeline_subparser(subparsers: argparse._SubParsersAction) -> None: ...
```

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| `quantlab-cli pipeline list` shows all discovered pipelines | Integration test: create temp config dirs, run CLI |
| `pipeline run <name> --dry-run` outputs CFX base64 | Integration test: run known pipeline, validate base64 decode |
| `pipeline run <name>` executes and persists history | Integration test: run, check `knowledge/pipeline-runs/` |
| History entry has run_id, status, stages, duration | Unit test: inspect saved YAML structure |
| `pipeline history --status failed` filters correctly | Integration test: create mixed history, filter |
| `--params key=val` overrides pipeline config | Unit test: merge logic, assert override applied |
| Exit codes match spec | Integration test: each error condition |
| Uses KnowledgeStore for history (Feature 5c) | Code review: `KnowledgeStore` imported and used |
| No new dependencies | Check `pyproject.toml` |

---

## Non-Functional Requirements

- **Performance**: Pipeline discovery < 100ms for 50 pipelines
- **History storage**: One YAML per run, human-readable, queryable via Knowledge Lake (Feature 5c)
- **Dependencies**: Zero new deps (uses `argparse`, `yaml`, `pathlib`, existing `pipeline`, `knowledge`)
- **Error messages**: Clear stderr output for not found, config errors, execution failures
- **Dry-run compatibility**: Output format matches existing CLI dry-run (CFX base64 to stdout)