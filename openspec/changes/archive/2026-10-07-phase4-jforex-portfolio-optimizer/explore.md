# Exploration: Phase 4 — JForex Deployment, Portfolio Management, Optimizer & Retester Automation

## Current State

StrategyQuant X (SQX) 144.2953 is installed at `assets/SQX_144_2953_linux_20260601/`. It provides:
- A Java-based desktop application with AngularJS frontend
- A CLI tool (`sqcli`) for headless operations
- An HTTP API on port 5050 (started with `-gui`)
- Project types: Builder, Optimizer, Retester, PortfolioComposer, PortfolioMaster

The SDK (`sdk/quantlab/`) provides Python tooling for CFX config parsing, DSL, stats, and CLI automation.

---

## 1. JForex Deployment

### How SQX deploys to JForex / JCloud

**There is no direct "deploy to JCloud" CLI command or HTTP API endpoint.**

- **Source code export**: SQX can export strategy source code as **JForex Expert Advisor (.java)** via the Results → Source Code tab.
- **Export mechanism**: `ResultsSourceCode` plugin uses backend endpoint `sourcecode/print` with generator type `"Expert Advisor for JForex (*.java)"`.
- **Custom indicators**: JForex strategies require custom indicators copied from `SQX/custom_indicators/JForex/Indicators` to the JForex strategies folder.
- **JCloud deployment**: Not automated in SQX. Manual process:
  1. Export `.java` file from SQX
  2. Compile in JForex SDK / Eclipse
  3. Upload to JCloud via JForex platform

### sqcli commands for export
- `sqcli -tools action=orderstocsv file="strategy.sqx"` — exports trades, not source code
- No `sqcli` command for source code export (GUI-only via `sourcecode/print` HTTP endpoint)

### Artifacts produced
- `.java` file (JForex strategy)
- Custom indicator `.java` files (from `custom_indicators/JForex/`)

---

## 2. Portfolio Management

### Project types
| Project | Purpose | sqcli support |
|---------|---------|---------------|
| **PortfolioComposer** | Combine strategies, optimize weights (Markowitz, risk parity, etc.) | `action=start/stop/status/loadconfig/saveconfig` |
| **PortfolioMaster** | Automatic portfolio builder (genetic/brute-force search) | Same as above |

### Portfolio .cfx format
- **PortfolioMaster**: Multi-task project (`CfxProject` with `Tasks` → `AutomaticPortfolioBuilder-Task1.xml`)
- **PortfolioComposer**: Empty project (config loaded via HTTP API at runtime)
- Key sections in CFX:
  - `<AutomaticPortfolioBuilder>` — search type, population, generations, fitness, correlation filters, money management
  - `<Databanks>` — input/output databank references
  - `<SelectedStrategies>` — chosen strategies

### Programmatic portfolio construction
- **HTTP API endpoints** (via `PortfolioComposerService`):
  - `POST /portfoliocomposer/recompute` — recalc weights
  - `POST /portfoliocomposer/savePortfolio` — save portfolio
  - `POST /portfoliocomposer/loadFiles` — load strategy files
  - `GET /portfoliocomposer/loadGridData` — load UI grid
- **sqcli**: Can start/stop projects, load/save configs, but no direct "add strategy to portfolio" command.

### Risk allocation, correlation, position sizing
- **Correlation filter**: `CorrMax` (default 0.3), `CorrType` (ProfitLoss), `CorrSampleType`, `CorrPeriod`
- **Money management**: Configurable per portfolio (`RiskFixedBalancePct`, `StocksSizeByPrice`, etc.)
- **Fitness types**: `NetProfitIS`, `ReturnDDRatio`, `ProfitFactor`, `SharpeRatio`, etc.
- **Max strategies**: Pro limited to 4, Ultimate unlimited

---

## 3. Optimizer Automation

### How SQX Optimizer works
- **Project type**: `Optimizer` (single-task `CfxConfig`)
- **Input databank**: "Strategies to optimize"
- **Output databank**: "Results"
- **Configuration sections** (in CFX):
  - `Optimization` — method (brute-force, genetic, random), walk-forward settings, max optimizations
  - `Parameters` — which parameters to optimize, ranges, steps
  - `Databanks` — input/output databank names

### sqcli control
```bash
sqcli -project action=start name=Optimizer
sqcli -project action=stop name=Optimizer
sqcli -project action=status name=Optimizer
sqcli -project action=saveconfig name=Optimizer file=opt.cfx
sqcli -project action=loadconfig name=Optimizer file=opt.cfx
```
- No direct "run one optimization iteration" command; `start` runs until stop condition.

### Optimization parameters (from CFX)
| Parameter | Values |
|-----------|--------|
| `Optimization@type` | 0=brute-force, 1=random, 2=genetic |
| `Optimization@maxOptimizations` | max iterations |
| `WalkForward@type` | 0=none, 1=WF, 2=WF matrix |
| `WalkForward@period` / `@optimization` | WF periods |
| `OptimizationMethod@method` | brute-force, genetic, etc. |
| `WhatToParametrize` | which param groups (periods, shifts, constants, entry/exit params) |

### Reading results
- Results stored in output databank ("Results")
- `sqcli -databank action=export project=Optimizer name=Results file=out.csv` — exports to CSV/XLSX
- HTTP API: `project/getDataItems` for strategy metrics

---

## 4. Retester Automation

### How SQX Retester works
- **Project type**: `Retester` (single-task `CfxConfig`)
- **Input databank**: Strategies to retest (e.g., "Results")
- **Configuration sections**:
  - `Data` — symbol, timeframe, date range, spread, slippage, commissions
  - `Rankings` — acceptance conditions (e.g., `ReturnDDRatio > 4`)
  - `CrossChecks` — robustness tests:
    - `RetestOnAdditionalMarkets`
    - `RetestWithHigherPrecision`
    - `WalkForwardOptimization`
    - `MonteCarloRetest`
    - `MonteCarloManipulation`
    - `WalkForwardMatrix`
    - `OptProfileSysParamPermutation`
    - `WhatIf`

### sqcli control
```bash
sqcli -project action=start name=Retester
sqcli -project action=stop name=Retester
sqcli -project action=status name=Retester
sqcli -project action=saveconfig name=Retester file=retest.cfx
sqcli -project action=loadconfig name=Retester file=retest.cfx
```

### Inputs required
- Strategies in input databank
- Data for test symbol/timeframe (auto-downloaded from Dukascopy if missing)
- Retester config (CFX) defining acceptance criteria and cross-checks

### Getting reports
- `sqcli -databank action=export project=Retester name=Results file=retest_report.csv`
- Results include main test + all cross-check sub-results

---

## Affected Areas

| Path | Why affected |
|------|--------------|
| `assets/SQX_144_2953_linux_20260601/sqcli` | CLI entry point for all automation |
| `assets/SQX_144_2953_linux_20260601/internal/plugins/ResultsSourceCode/` | JForex source code export |
| `assets/SQX_144_2953_linux_20260601/internal/plugins/PortfolioComposer/` | Portfolio composition logic |
| `assets/SQX_144_2953_linux_20260601/internal/plugins/AppPortfolioComposer/` | PortfolioComposer app |
| `assets/SQX_144_2953_linux_20260601/internal/plugins/AppPortfolioMaster/` | PortfolioMaster app |
| `assets/SQX_144_2953_linux_20260601/internal/plugins/AppOptimizer/` | Optimizer app |
| `assets/SQX_144_2953_linux_20260601/internal/plugins/AppRetester/` | Retester app |
| `assets/SQX_144_2953_linux_20260601/user/projects/Optimizer/project.cfx` | Optimizer config template |
| `assets/SQX_144_2953_linux_20260601/user/projects/Retester/project.cfx` | Retester config template |
| `assets/SQX_144_2953_linux_20260601/user/projects/PortfolioMaster/project.cfx` | PortfolioMaster config template |
| `sdk/quantlab/cfx/` | Python CFX reader/writer for config generation |
| `sdk/quantlab/cli/runner.py` | Python wrapper for sqcli |

---

## Approaches

### 1. JForex Deployment Automation
| Approach | Pros | Cons | Effort |
|----------|------|------|--------|
| **A: HTTP API `sourcecode/print` + custom script** | Uses existing SQX backend; generates `.java` | Requires running SQX HTTP server; no JCloud upload | Medium |
| **B: Extend sqcli with `-sourcecode export` command** | Native CLI; scriptable | Requires Java plugin development (outside SDK) | High |
| **C: Post-process SQX strategy XML → JForex template** | Fully offline; no SQX runtime needed | Complex: must replicate SQX codegen logic | Very High |

**Recommendation**: **Approach A** — Use HTTP API (`sourcecode/print` with generator `Expert Advisor for JForex (*.java)`) from Python SDK. Wrap in `quantlab.tools.sqx_export_jforex()`. JCloud upload remains manual (no API).

---

### 2. Portfolio Management Automation
| Approach | Pros | Cons | Effort |
|----------|------|------|--------|
| **A: HTTP API via `PortfolioComposerService` endpoints** | Full control; matches UI capabilities | Requires running SQX server | Medium |
| **B: sqcli project start/stop + CFX config generation** | Simple CLI; good for batch | Limited to project-level control; no fine-grained strategy add/remove | Low |
| **C: Direct CFX manipulation + databank sync** | Fully offline; fast | Complex CFX structure; databank sync tricky | High |

**Recommendation**: **Approach B + A hybrid** — Use sqcli for project lifecycle (start/stop/config), HTTP API for portfolio recomputation and weight optimization. Generate PortfolioMaster CFX via SDK for automatic portfolio building.

---

### 3. Optimizer Automation
| Approach | Pros | Cons | Effort |
|----------|------|------|--------|
| **A: sqcli project control + CFX templates** | Native; supports all optimization modes | Long-running; no progress callbacks via CLI | Low |
| **B: HTTP API polling** | Real-time progress; can fetch intermediate results | Requires running server | Medium |
| **C: Databank export → external optimizer (Optuna, etc.)** | Full control; modern algorithms | Replicates SQX backtest engine externally | Very High |

**Recommendation**: **Approach A** — Use sqcli `start/stop/status` with SDK-generated CFX configs. Add `quantlab.cli.run_optimization(config_dict)` wrapper.

---

### 4. Retester Automation
| Approach | Pros | Cons | Effort |
|----------|------|------|--------|
| **A: sqcli project control + CFX templates** | Native; all cross-checks supported | Batch-oriented; no streaming results | Low |
| **B: HTTP API** | Can monitor per-strategy progress | More complex | Medium |

**Recommendation**: **Approach A** — sqcli `start/stop/status` with SDK-generated Retester CFX. Export results via `databank export` to CSV for analysis.

---

## Recommendation

**Unified Phase 4 SDK Module**: Create `sdk/quantlab/phase4/` with:

1. **`jforex_export.py`** — `export_to_jforex(strategy_name, output_dir)` using HTTP `sourcecode/print`
2. **`portfolio.py`** — `PortfolioComposer` / `PortfolioMaster` wrapper:
   - `create_portfolio_master_config(strategies, fitness, correlation_max, ...)` → CFX dict
   - `run_portfolio_composer(strategies, weights)` via HTTP API
3. **`optimizer.py`** — `OptimizerConfig` dataclass + `run_optimization(config, project_name="Optimizer")`
4. **`retester.py`** — `RetesterConfig` dataclass + `run_retest(config, project_name="Retester")`
5. **`cli_runner.py`** — High-level `sqcli` wrapper with timeout, status polling, result export

All configs generated via `cfx.writer` / `cfx.patcher` from templates in `user/projects/*/project.cfx`.

---

## Risks

1. **No JCloud API** — JForex deployment stops at `.java` file; manual JCloud upload required
2. **SQX single-instance lock** — Only one SQX process per install; parallel runs need multiple installations
3. **HTTP API requires GUI server** — Headless CLI doesn't expose portfolio/optimizer endpoints; need `-gui` background process
4. **CFX binary format** — Must use SDK reader/writer; manual XML editing error-prone
5. **Long-running processes** — Optimizer/Retester can run hours; need robust timeout/heartbeat handling
6. **License limits** — Pro version limits PortfolioComposer to 4 strategies

---

## Ready for Proposal

**Yes** — sufficient understanding to write SDD proposal. Key deliverables:
- `phase4-jforex-portfolio-optimizer/proposal.md` with unified architecture
- `spec.md` with requirements for each sub-feature
- `design.md` with SDK module structure and API contracts
- `tasks.md` with implementation breakdown

Next step: Orchestrator launches `sdd-propose` for this change.