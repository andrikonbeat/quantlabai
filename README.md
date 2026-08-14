# QuantLab AI

**Quantitative Research SDK for Algorithmic Trading**

QuantLab AI is a Python SDK that bridges quantitative research with the StrategyQuant X (SQX) trading platform. Define strategies in a YAML DSL, translate them to SQX `.cfx` format, run backtests via SQX CLI, parse results, compute statistics, and manage research artifacts — all from Python.

## Architecture

```
research.yaml ──→ [dsl/parser] ──→ ResearchConfig ──→ [translate/] ──→ XML string
                      ↑                                                  │
                      |                                     ┌── dry_run? ──→ return XML
                      |                                     │
                      |                               [cfx writer] ──→ .cfx file
                      |                                     │
 knowledge/index.yaml ← [knowledge/ store]                  │
                      │                                     ▼
                      │                              [cli/ runner] ──→ sqcli.exe
                      │                                     │
                      │                            ┌── dry_run? ──→ MockExecutor
                      │                            │                (canned result)
                      │                            ▼
                      │                     Databank CSV/XLSX
                      │                            │
                      │                            ▼
                      │                     [readers/] ──→ Trade[], Equity[], Summary
                      │                            │
                      └──────────────────────── [stats/] ──→ Metrics (PF, Sharpe, DD, MAR, Expectancy)
```

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Setup

```bash
# Clone the repository
git clone https://github.com/andrikonbeat/quantlabai
cd quantlab-ai

# Install with uv (recommended)
cd sdk
uv sync
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quick Start

### 1. Create a Research Campaign

```yaml
# my_campaign.yaml
campaign: "My First Campaign"
market: EURUSD
timeframe: H1

building_blocks:
  - name: trend_follow
    indicator:
      name: EMA
      params:
        period: 200
    entry:
      description: "Price closes above EMA"
      conditions:
        - "close > ema_200"
    exit:
      description: "Price closes below EMA"
      conditions:
        - "close < ema_200"

strategies:
  - name: TrendFollow_v1
    direction: LONG
    building_blocks:
      - trend_follow

criteria:
  - metric: profit_factor
    operator: ">="
    value: 1.5
  - metric: sharpe
    operator: ">="
    value: 1.0
```

### 2. Parse the Campaign

```python
from quantlab.dsl.parser import parse_yaml

config = parse_yaml("my_campaign.yaml")
print(f"Campaign: {config.campaign}")
print(f"Market: {config.market.value}, Timeframe: {config.timeframe.value}")
```

### 3. Translate to CFX (Dry-Run)

```python
from quantlab.translate.cfx import CfxArchive

# Dry-run: returns XML without writing a .cfx file
result = CfxArchive.from_model(config, dry_run=True)
print(result.xml_content[:500])
```

### 4. Run via CLI (Dry-Run without SQX)

```python
from quantlab.cli.runner import CliRunner

runner = CliRunner(dry_run=True)
cli_result = runner.execute("backtest --cfx my_campaign.cfx")
print(cli_result.stdout)
```

### 5. Read Backtest Results

```python
from quantlab.readers.databank import DatabankCSVReader

reader = DatabankCSVReader()
trades = reader.read_trades("results/trades.csv")
equity = reader.read_equity("results/equity.csv")
summary = reader.read_summary("results/summary.csv")

print(f"Total trades: {len(trades)}")
print(f"Net profit: {summary.net_profit}")
print(f"Win rate: {summary.win_rate}")
```

### 6. Compute Statistics

```python
from quantlab.stats.engine import StatisticsEngine

engine = StatisticsEngine()
result = engine.compute_all(trades=trades, equity=equity, returns=[t.profit for t in trades])

print(f"Profit Factor: {result.profit_factor:.2f}")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Max Drawdown: {result.max_drawdown:.2f}%")
print(f"Expectancy: {result.expectancy:.2f}")
```

### 7. Use the Knowledge Lake

```python
from quantlab.knowledge.store import KnowledgeStore

store = KnowledgeStore(root="knowledge")
store.initialize()  # Creates 5 subdirectories with .gitkeep
store.rebuild_index()  # Scans all files and writes index.yaml
warnings = store.validate_formats()  # Checks for non-standard formats
```

## Orchestrated Campaign Flow

The AI-directed orchestrated campaign runs the full 14-phase research loop
end-to-end with human-validated gates at every boundary. The flow proceeds
through deploy, demo, and archive to the terminal live-ops phase (Guardian
watching the demo account) — it does NOT stop at optimize.

### Routing

`quantlab-orchestrator` classifies the intent and delegates campaign requests
(e.g., "run a full campaign") to the `quantlab-campaign` subagent via the
`task` tool. SDD, CLI, and dashboard routes are unchanged.

### Harness

The `quantlab-campaign` subagent owns the 14-phase loop:

```
research → hypothesis → config → review → dispatch → monitor → retest → optimize → portfolio → compile → deploy → demo → archive → live-ops
```

Each phase returns the Result Contract envelope (`status`,
`executive_summary`, `artifacts`, `next_recommended`, `risks`). A failed phase
halts the loop for a human decision.

Assets are versioned in-repo:

- `ai/opencode/agents/campaign.md` — the campaign agent prompt
- `ai/opencode/skills/quantlab-run-campaign/SKILL.md` — the seed skill

### Human Gates (fail-closed)

Gates resolve through a decision-file channel under
`/tmp/sqx-gates/{campaign_id}/`: the pipeline writes a `.pending.json`
envelope, the agent presents it via the `question` tool, and the human
decision is written back as `.decision.json`. In headless mode the agent falls
back to stdin.

Autonomous rules are binding:

- The `HUMAN_APPROVE_CONFIG`, `HUMAN_APPROVE_DEPLOY`, `HUMAN_APPROVE_DEMO`,
  and `HUMAN_APPROVE_ARCHIVE` gates **always block** for a human decision
  (D2/REQ-38); a MODIFY verdict requires human confirmation before applying
  (D3).
- Unanswered gates **fail closed (HOLD)** — they never auto-approve (REQ-11).
- Legacy CLI auto-approve remains available outside orchestrated mode.

### Data

`DataManager` is **Dukascopy-only** at launch (FX M1/M5/H1). Orchestrated
dispatch runs `_ensure_data` as a hard pre-flight; crypto, CSV, and yahoo
datasources raise `NotSupportedError` (D5).

## Directory Structure

```
quantlab-ai/
├── README.md
├── LICENSE
├── SECURITY.md
├── sdk/
│   ├── pyproject.toml
│   └── quantlab/
│       ├── __init__.py           # Package root + version
│       ├── dsl/                  # YAML DSL — models + parser
│       ├── translate/            # Model → CFX XML → ZIP
│       ├── cli/                  # SQX CLI wrapper (executor protocol)
│       ├── readers/              # Databank CSV/XLSX result readers
│       ├── stats/                # Trading metrics computation
│       ├── knowledge/            # Knowledge Lake management
│       ├── data/                 # Market data providers
│       ├── agents/               # Multi-agent research pipeline agents
│       └── tools/                # Platform, errors, utilities
├── tests/                        # Root test suite
│   ├── conftest.py
│   ├── fixtures/                 # Sample CSV, YAML files
│   └── ...                       # Unit + integration tests
├── sdk/tests/                    # SDK test suite
├── app_movil/                    # Android companion app (Kotlin, Jetpack Compose)
├── AI/opencode/                  # Agent prompts, skills, and orchestrator config
├── docs/                         # PRD, STATE, changelog, reference guides
│   └── sqx-builder-config/       # SQX Builder config reference (KB seed source)
├── infra/                        # Infrastructure assets (DB init schema)
├── docker-compose.yml            # API, SQX daemon, Postgres, Redis
├── knowledge/                    # Knowledge Lake (data)
│   ├── index.yaml
│   ├── raw/
│   ├── structured/
│   ├── graph/
│   ├── embeddings/
│   └── datasets/
├── openspec/                     # Spec-driven development artifacts
├── sdd/                          # SDD change planning artifacts
├── pipelines/                    # Pipeline YAML definitions
└── strategies/
    └── HelloWorldStrategy.java   # JForex 4 strategy template
```

> The `assets/` directory holds the local StrategyQuant X distribution and is
> git-ignored — it is not part of the public repository.

## Companion Mobile App

`app_movil/` contains an Android companion app (Kotlin + Jetpack Compose) for
monitoring campaigns. It is versioned in this repository but is a separate
build unit from the Python SDK (see `app_movil/quantlabai/` for its Gradle
project).

## Commands

### Testing

```bash
cd sdk
uv run pytest              # Run all tests
uv run pytest -v           # Verbose output
uv run pytest tests/       # Specific test directory
uv run pytest -k test_     # Filter by name
```

### Dry-Run Walkthrough (No SQX Required)

The entire pipeline works without StrategyQuant X installed:

1. **DSL → Config**: `parse_yaml("campaign.yaml")` — pure Python YAML parsing
2. **Config → XML**: `CfxArchive.from_model(config, dry_run=True)` — generates XML, skips ZIP
3. **CLI mock**: `CliRunner(dry_run=True)` — uses `MockExecutor`, no subprocess
4. **Readers**: Works on **any** CSV/XLSX file — no SQX dependency
5. **Statistics**: Pure Python math — works on any trade list
6. **Knowledge Lake**: Filesystem operations — no external services

## SDK Modules

| Module | Purpose | SQX Required |
|--------|---------|-------------|
| `quantlab.dsl` | YAML-based research DSL parser | No |
| `quantlab.translate` | Model-to-CFX XML translation | No |
| `quantlab.cli` | SQX CLI wrapper (Executor protocol) | Yes (real mode) |
| `quantlab.readers` | Databank CSV/XLSX result parsing | No |
| `quantlab.stats` | Trading performance metrics | No |
| `quantlab.knowledge` | Knowledge Lake management | No |

## Pipeline Commands

Manage pipeline YAML files and execute campaigns.

| Command | Description |
|---------|-------------|
| `quantlab pipeline list` | List available pipelines |
| `quantlab pipeline run <name>` | Run pipeline (dry-run by default) |
| `quantlab pipeline run <name> --dry-run=false` | Execute real SQX pipeline stages |
| `quantlab pipeline run <name> --params key=value` | Override pipeline parameters |
| `quantlab pipeline history` | Show pipeline run history |
| `quantlab pipeline validate <file>` | Validate pipeline YAML syntax |
| `quantlab pipeline config <name>` | Show pipeline configuration |

See [Pipeline YAML Reference](docs/configuration/pipeline-yaml.md) for complete YAML schema, stage types, and examples.

## Report Commands

Generate campaign reports with themes, benchmarks, and custom templates.

```bash
# Install reporting extras
pip install quantlab[reporting]           # Plotly-based (default)
pip install quantlab[reporting-matplotlib]  # Matplotlib fallback
```

| Command | Description |
|---------|-------------|
| `quantlab report generate <campaign>` | Generate HTML + JSON report |
| `quantlab report generate <campaign> --theme dark` | Dark theme |
| `quantlab report generate <campaign> --theme light` | Light theme |
| `quantlab report generate <campaign> --benchmark bench.csv` | Overlay benchmark equity curve |
| `quantlab report generate <campaign> --template custom.j2` | Use custom Jinja2 template |
| `quantlab report generate <campaign> --output-dir ./reports` | Custom output directory |
| `quantlab report generate <campaign> --json` | JSON-only output |

**Benchmark CSV format:**
```csv
timestamp,equity
2024-01-01 00:00:00,10000
2024-01-02 00:00:00,10100
```

See [Reporting Reference](docs/guides/reporting.md) for template variables, themes, API, and exit codes.

## Knowledge Commands

Query, tag, link, and export campaigns from the Knowledge Lake.

| Command | Description |
|---------|-------------|
| `quantlab knowledge query [--sharpe ">1.5"] [--pf ">1.2"] [--tags trend]` | Filter campaigns by metrics/tags |
| `quantlab knowledge query --json` | JSON output |
| `quantlab knowledge tag <campaign> <tags...>` | Add tags |
| `quantlab knowledge tag <campaign> <tag> --remove` | Remove tags |
| `quantlab knowledge link --parent <id> --children <id1> <id2>` | Create parent-child links |
| `quantlab knowledge link --list <campaign>` | List links |
| `quantlab knowledge export --format csv|json --output file.csv` | Export query results |
| `quantlab knowledge rebuild-index` | Rebuild knowledge index |

See [Knowledge Query Reference](docs/guides/knowledge-query.md) for filter syntax, API, and schema details.

## License

MIT — see [LICENSE](LICENSE).

## Security

Report vulnerabilities privately via GitHub Private vulnerability reporting —
see [SECURITY.md](SECURITY.md) for the policy and response expectations.
