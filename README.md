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
git clone <repo-url>
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

## Directory Structure

```
quantlab-ai/
├── README.md
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
│       └── tools/                # Platform, errors, utilities
├── tests/
│   ├── conftest.py
│   ├── fixtures/                 # Sample CSV, YAML files
│   ├── test_dsl_*.py
│   ├── test_translator.py
│   ├── test_cfx.py
│   ├── test_cli.py
│   ├── test_readers.py
│   ├── test_stats.py
│   └── test_knowledge.py
├── knowledge/                    # Knowledge Lake (data)
│   ├── index.yaml
│   ├── raw/
│   ├── structured/
│   ├── graph/
│   ├── embeddings/
│   └── datasets/
└── strategies/
    └── HelloWorldStrategy.java   # JForex 4 strategy template
```

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

## License

MIT
