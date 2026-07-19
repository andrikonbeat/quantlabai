# Pipeline YAML Reference

Pipeline YAML files define automated campaigns for the QuantLab SDK. Each pipeline is a directed acyclic graph (DAG) of stages that execute sequentially against the StrategyQuant X daemon.

> **SDK Reference**: [`sdk/quantlab/pipeline/`](../sdk/quantlab/pipeline/)

---

## Top-Level Structure

```yaml
name: "pipeline-name"       # Required — unique pipeline identifier
description: "..."          # Optional — human-readable summary
version: "1.0"              # Optional — pipeline schema version (default: 1.0)
stages:                     # Required — ordered list of stage configs
  - name: stage_name
    type: builtin
    config: {}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Unique pipeline name. Used for CLI lookup and history tracking. |
| `description` | string | no | Human-readable summary shown in `pipeline list`. |
| `version` | string | no | Schema version for forward compatibility (default `"1.0"`). |
| `stages` | list | yes | Ordered list of stage configurations. Minimum 1 stage. |

---

## Stage Types

Every stage in a pipeline must use `type: builtin`. The system maps stage names to concrete SQX implementations via the `StageRegistry`.

### All 18 Registered Stage Types

| Stage Name | SQX Class | Phase 4 Module | Purpose |
|------------|-----------|----------------|---------|
| `validate` | `SQXValidateStage` | `phase4.stages` | Validate SQX binary and license |
| `translate` | `SQXTranslateStage` | `phase4.stages` | Translate DSL config to CFX archive |
| `daemon_start` | `SQXDaemonStartStage` | `phase4.stages` | Start the SQX daemon process |
| `load_config` | `SQXLoadConfigStage` | `phase4.stages` | Load campaign config into daemon |
| `run_campaign` | `SQXRunCampaignStage` | `phase4.stages` | Execute the campaign run |
| `poll_campaign` | `SQXPollCampaignStage` | `phase4.stages` | Poll until completion |
| `export` | `SQXExportStage` | `phase4.stages` | Export results to CSV/XLSX |
| `read` | `SQXReadStage` | `phase4.stages` | Read exported result files |
| `compute_stats` | `SQXComputeStatsStage` | `phase4.stages` | Compute trading statistics |
| `knowledge_store` | `SQXKnowledgeStoreStage` | `phase4.stages` | Persist to Knowledge Lake |
| `report` | `SQXReportStage` | `phase4.stages` | Generate campaign report |
| `optimize` | → `SQXRunCampaignStage` | — | Alias for run_campaign |
| `walkforward` | → `SQXPollCampaignStage` | — | Alias for poll_campaign |
| `montecarlo` | → `SQXPollCampaignStage` | — | Monte Carlo simulation step |
| `portfolio` | → `SQXCampaignStage` | — | Portfolio construction step |
| `risk` | → `SQXReadStage` | — | Risk analysis step |
| `history` | → `SQXExportStage` | — | History export step |
| `finalize` | → `SQXDaemonStartStage` | — | Finalization step (restart daemon) |

> **Alias stages** (`optimize`, `walkforward`, etc.) are mapped to the same implementations as their granular counterparts. They exist for pipeline YAML readability.

---

## Per-Stage Configuration

### `validate`

```yaml
- name: validate
  type: builtin
  config:
    dry_run: false                 # Skip binary validation in dry-run mode
```

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| `dry_run` | bool | `false` | Skip SQX binary check when true |

### `translate`

```yaml
- name: translate
  type: builtin
  config:
    strategy_id: "strat_123"      # Strategy identifier for CFX generation
    research_config: null          # Optional: path to research YAML config
```

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| `strategy_id` | string | — | Strategy ID for the CFX archive |
| `research_config` | string | `null` | Override path to research YAML |

### `daemon_start`

```yaml
- name: daemon_start
  type: builtin
  config:
    port: 8888                     # SQX daemon HTTP API port
    sqx_install_path: "/opt/StrategyQuantX"  # SQX installation directory
```

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| `port` | int | `8888` | SQX daemon `-gui` HTTP port |
| `sqx_install_path` | string | `/opt/StrategyQuantX` | SQX installation root |

### `load_config`

```yaml
- name: load_config
  type: builtin
  config:
    campaign_name: "MyCampaign"    # Campaign name in SQX
    config_overrides: {}           # Key-value param overrides
```

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| `campaign_name` | string | — | Campaign name sent to daemon |
| `config_overrides` | dict | `{}` | Parameter overrides |

### `run_campaign`

```yaml
- name: run_campaign
  type: builtin
  config: {}                       # No config required
```

### `poll_campaign`

```yaml
- name: poll_campaign
  type: builtin
  config:
    poll_interval: 30              # Seconds between status checks
    timeout: 3600                  # Maximum wait time (seconds)
```

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| `poll_interval` | float | `30` | Seconds between status polls |
| `timeout` | float | `3600` | Max total wait time in seconds |

### `export`

```yaml
- name: export
  type: builtin
  config:
    export_formats: ["csv"]        # Export formats: csv, xlsx, or both
    export_databanks: true         # Export databank files
    output_dir: null               # Override export directory
```

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| `export_formats` | list | `["csv"]` | Formats: `csv`, `xlsx`, or both |
| `export_databanks` | bool | `true` | Include databank exports |
| `output_dir` | string | `null` | Override output directory |

### `read`, `compute_stats`, `knowledge_store`, `report`

These stages require no configuration but accept arbitrary metadata:

```yaml
- name: read
  type: builtin
  config: {}
```

```yaml
- name: knowledge_store
  type: builtin
  config:
    knowledge_root: "knowledge"    # Knowledge Lake root path
```

```yaml
- name: report
  type: builtin
  config:
    theme: "dark"                  # Report theme: light or dark
    formats: ["html", "json"]      # Output formats
```

---

## Complete Example

```yaml
name: "SQXCampaign"
description: "Full SQX campaign pipeline: validate through report"
version: "1.0"
stages:
  - name: validate
    type: builtin
    config:
      dry_run: false

  - name: translate
    type: builtin
    config:
      strategy_id: "strat_123"

  - name: daemon_start
    type: builtin
    config:
      port: 8888

  - name: load_config
    type: builtin
    config:
      campaign_name: "MyCampaign"

  - name: run_campaign
    type: builtin
    config: {}

  - name: poll_campaign
    type: builtin
    config:
      poll_interval: 30
      timeout: 3600

  - name: export
    type: builtin
    config:
      export_formats: ["csv"]
      export_databanks: true

  - name: read
    type: builtin
    config: {}

  - name: compute_stats
    type: builtin
    config: {}

  - name: knowledge_store
    type: builtin
    config:
      knowledge_root: "knowledge"

  - name: report
    type: builtin
    config: {}
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QUANTLAB_KNOWLEDGE_ROOT` | `knowledge/` | Knowledge Lake root directory |
| `SQX_INSTALL_PATH` | `/opt/StrategyQuantX` | SQX installation directory |

---

## CLI Commands

### Run a Pipeline

```bash
# Run a pipeline from the registry (by name)
quantlab pipeline run SQXCampaign

# Dry-run without executing
quantlab pipeline run SQXCampaign --dry-run

# Override config file
quantlab pipeline run SQXCampaign --config pipelines/my_pipeline.yaml

# Override parameters
quantlab pipeline run SQXCampaign --params window=10 --params step=2

# Set per-stage timeout (seconds)
quantlab pipeline run SQXCampaign --timeout 600
```

**Exit codes**: `0` = success, `1` = pipeline not found, `2` = config error, `3` = execution error/timeout, `4` = dry-run output

### List Pipelines

```bash
quantlab pipeline list
quantlab pipeline list --json
```

### View History

```bash
quantlab pipeline history
quantlab pipeline history --limit 20
quantlab pipeline history --status failed
quantlab pipeline history --json
```

---

## Programmatic API

```python
from quantlab.pipeline.registry import PipelineRegistry
from quantlab.pipeline.config import PipelineConfig

# Discover pipelines from config directories
registry = PipelineRegistry(config_dirs=["pipelines"])
registry.discover()

# Get a specific pipeline
config = registry.get("SQXCampaign")
print(f"Stages: {len(config.stages)}")

# Build and run
pipeline = registry.build_pipeline("SQXCampaign")
# See PipelineRunner for execution
from quantlab.pipeline.runner import PipelineRunner
runner = PipelineRunner()
# await runner.run(pipeline, context)
```
