# SQX CLI Wrapper — Delta Specification (Phase 5b-5e)

## Purpose

Extends the existing CLI (`quantlab-cli`) with three new subcommand groups:
1. `pipeline` — pipeline discovery, execution, history (Feature 5d)
2. `report` — campaign report generation (Feature 5b)
3. `knowledge query` — campaign search/filter (Feature 5c)

All follow existing CLI patterns: `argparse` subparsers, shared global args (`--sqx-path`, `--port`, `--json`, `--dry-run`), structured output.

---

## ADDED Requirements

### Requirement: Pipeline Subcommand Group

The system MUST add a top-level `pipeline` subcommand group with three verbs:

```bash
quantlab-cli pipeline run <name> [options]
quantlab-cli pipeline list [options]
quantlab-cli pipeline history [options]
```

#### Pipeline Run Command

```bash
quantlab-cli pipeline run <pipeline-name> \
    [--config FILE.yaml] \
    [--params KEY=VALUE ...] \
    [--dry-run] \
    [--output-dir PATH] \
    [--sqx-path PATH] \
    [--port PORT] \
    [--no-daemon-stop] \
    [--json]
```

**Global arg reuse**: `--sqx-path`, `--port`, `--no-daemon-stop`, `--json` match existing commands (`portfolio run`, `optimizer run`, etc.)

**Behavior:**
1. Resolve pipeline via `PipelineRegistry` (built-in + custom dirs)
2. Merge `--config` YAML + `--params` overrides
3. Create run record in Knowledge Lake (`pipeline-runs/{run_id}.yaml`)
4. If `--dry-run`: call `PipelineRunner.dry_run()` → output CFX base64 JSON
5. Else: call `PipelineRunner.run()` → execute full pipeline
6. Update run record with results
7. Output `PipelineResult` summary (table or `--json`)

**Exit codes:**
- 0 = success
- 1 = pipeline not found
- 2 = config error
- 3 = execution error
- 4 = dry-run output (CFX base64 to stdout)

#### Pipeline List Command

```bash
quantlab-cli pipeline list [--json] [--verbose]
```

Output table: `name | description | version | stages | source`

#### Pipeline History Command

```bash
quantlab-cli pipeline history \
    [--limit 10] \
    [--status running|completed|failed] \
    [--pipeline NAME] \
    [--since DATE] \
    [--json]
```

Reads `knowledge/pipeline-runs/*.yaml` via Knowledge Store. Output: `run_id | pipeline | status | started | duration | stages`

---

### Requirement: Report Subcommand Group

The system MUST add a top-level `report` subcommand group:

```bash
quantlab-cli report generate <campaign-id> [options]
```

#### Report Generate Command

```bash
quantlab-cli report generate <campaign-id> \
    [--html] [--no-html] \
    [--json] [--no-json] \
    [--output-dir PATH] \
    [--theme light|dark] \
    [--no-charts] \
    [--benchmark FILE.csv] \
    [--json]
```

Options:
| Option | Default | Description |
|--------|---------|-------------|
| `--html` / `--no-html` | `--html` | Generate interactive HTML |
| `--json` / `--no-json` | `--json` | Generate machine-readable JSON |
| `--output-dir` | `reports/` | Output directory |
| `--theme` | `light` | HTML theme |
| `--no-charts` | off | Skip Plotly charts |
| `--benchmark` | none | Benchmark equity CSV |

**Behavior:**
1. Load `CampaignResult` from `knowledge/structured/{campaign-id}/`
2. Build `ReportConfig` from CLI options
3. Call `ReportGenerator.generate(campaign_result, config)`
4. Write outputs to `--output-dir` or `reports/{campaign-id}/`
5. Output paths to stdout (table or `--json`)

---

### Requirement: Knowledge Query Subcommand (Extends Existing `knowledge`)

The existing `knowledge` group (has `rebuild-index`, `validate`) gets new `query` verb:

```bash
quantlab-cli knowledge query [options]
```

#### Knowledge Query Command

```bash
quantlab-cli knowledge query \
    [--sharpe RANGE] \
    [--pf RANGE] \
    [--win-rate RANGE] \
    [--mdd RANGE] \
    [--tag KEY=VALUE ...] \
    [--date START..END] \
    [--text TEXT] \
    [--sort FIELD] \
    [--asc | --desc] \
    [--limit 20] \
    [--json] \
    [--show-tags] [--show-links]
```

Range syntax: `">1.5"`, `">=1.0"`, `"<2.0"`, `"1.0..2.0"`, `"50"` (exact).

Sort fields: `sharpe`, `profit_factor`, `win_rate`, `max_drawdown`, `created`, `net_profit`.

Output table: `campaign_id | created | sharpe | pf | win% | mdd% | trades | tags`

---

## MODIFIED Requirements

### Requirement: CLI Main Parser Extension

The system MUST modify `sdk/quantlab/cli/main.py` to register new subcommand groups:

```python
def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(...)
    subparsers = parser.add_subparsers(dest="command")
    
    # Existing: daemon, portfolio, optimizer, retester, jforex, knowledge
    add_daemon_subparser(subparsers)
    add_portfolio_subparser(subparsers)
    add_optimizer_subparser(subparsers)
    add_retester_subparser(subparsers)
    add_jforex_subparser(subparsers)
    add_knowledge_subparser(subparsers)  # EXISTING
    
    # NEW:
    add_pipeline_subparser(subparsers)
    add_report_subparser(subparsers)
```

Each `add_*_subparser` function registers its subcommand group.

### Requirement: Shared CLI Infrastructure

New commands MUST reuse existing CLI patterns:
- Global args: `--sqx-path`, `--port`, `--json`, `--no-daemon-stop`
- Dry-run output: CFX base64 to stdout (same as `portfolio run --dry-run`)
- Error handling: structured exceptions → stderr, exit codes
- Output: table (default) or `--json` machine-readable
- Logging: respect `--verbose`/`--quiet`

---

## Interface Specifications (Delta)

```python
# quantlab.cli.main (EXTENDED)
def add_pipeline_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register pipeline run/list/history subcommands."""

def add_report_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register report generate subcommand."""

# quantlab.cli.pipeline_commands (NEW FILE)
def pipeline_run_command(args: argparse.Namespace) -> int:
    """Execute pipeline run command. Returns exit code."""
    ...

def pipeline_list_command(args: argparse.Namespace) -> int: ...

def pipeline_history_command(args: argparse.Namespace) -> int: ...

# quantlab.cli.report_commands (NEW FILE)
def report_generate_command(args: argparse.Namespace) -> int:
    """Execute report generate command. Returns exit code."""
    ...

# quantlab.cli.knowledge_commands (EXTENDED - existing file)
def knowledge_query_command(args: argparse.Namespace) -> int:
    """Execute knowledge query command. Returns exit code."""
    ...

# Existing knowledge_commands.py already has:
def knowledge_rebuild_index_command(args): ...
def knowledge_validate_command(args): ...
# ADD: knowledge_query_command
```

---

## Data Flow (New Commands)

```
quantlab-cli pipeline run <name>
       │
       ├─► PipelineRegistry.get(name) → PipelineConfig
       ├─► Merge --config YAML + --params
       ├─► Create run_id, KnowledgeStore.save_pipeline_run(running)
       │
       ├─► --dry-run:
       │       └─► PipelineRunner.dry_run() → CFX base64 → stdout
       │
       └─► real run:
               ├─► PipelineRunner.run() → PipelineResult
               ├─► KnowledgeStore.save_pipeline_run(completed/failed)
               └─► Output PipelineResult summary
       
quantlab-cli report generate <id>
       │
       ├─► KnowledgeStore.load_campaign(id) → CampaignResult
       ├─► ReportConfig.from_args(args)
       ├─► ReportGenerator.generate(campaign, config) → ReportResult
       └─► Write outputs, print paths

quantlab-cli knowledge query
       │
       ├─► KnowledgeStore.query() → QueryBuilder
       ├─► Apply filters from args
       ├─► Execute → QueryResult
       └─► Format table/JSON
```

---

## Acceptance Criteria (Delta)

| Criterion | Verification |
|-----------|--------------|
| `quantlab-cli --help` shows `pipeline`, `report` groups | Run CLI, check help |
| `pipeline run --help` shows all options | Run, check help |
| `pipeline run <name> --dry-run` outputs CFX base64 | Integration test with known pipeline |
| `pipeline run <name>` persists run record | Integration: run, check `pipeline-runs/` |
| `pipeline list` shows built-in + custom | Integration: temp config dirs |
| `pipeline history --status failed` filters | Integration: create mixed history |
| `report generate` produces HTML + JSON | Integration: load campaign, run |
| `knowledge query --sharpe ">1.5"` filters | Integration: index with known campaigns |
| All commands support `--json` output | Unit test each command with `--json` |
| Exit codes match spec | Integration tests for each code |
| Existing commands still work | Run full test suite (507 tests) |

---

## Non-Functional Requirements

- **Startup latency**: New subparsers add < 10ms to CLI init
- **Help text**: All new commands have descriptive help matching existing style
- **Dependencies**: Zero new deps (uses `argparse`, `yaml`, existing modules)
- **Code organization**: New commands in separate files (`pipeline_commands.py`, `report_commands.py`), registered in `main.py`

---

## Files Modified/Added

| File | Change |
|------|--------|
| `sdk/quantlab/cli/main.py` | Add `add_pipeline_subparser`, `add_report_subparser` calls |
| `sdk/quantlab/cli/pipeline_commands.py` | NEW: 3 pipeline command functions |
| `sdk/quantlab/cli/report_commands.py` | NEW: report generate command |
| `sdk/quantlab/cli/knowledge_commands.py` | EXTEND: add `knowledge_query_command` |
| `sdk/quantlab/cli/__init__.py` | Export new command modules |
| `tests/test_cli.py` | EXTEND: add CLI integration tests for new commands |