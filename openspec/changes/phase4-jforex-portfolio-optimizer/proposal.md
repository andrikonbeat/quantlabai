# Proposal: Phase 4 — JForex Deployment, Portfolio Management, Optimizer & Retester Automation

## Intent

Automate the end-to-end pipeline from SQX strategy research → JForex `.java` export → Portfolio construction (Composer/Master) → Walk-forward optimization → Robustness retesting. Currently these workflows are manual/GUI-only; this phase builds SDK automation so QuantLab AI can run them programmatically without human SQX interaction.

## Scope

### In Scope
- `sdk/quantlab/phase4/jforex-deploy/` — HTTP `sourcecode/print` wrapper + custom indicator deployment
- `sdk/quantlab/phase4/portfolio/` — PortfolioComposer (HTTP weight optimization) + PortfolioMaster (CFX genetic config) orchestration
- `sdk/quantlab/phase4/optimizer/` — CFX template generation + sqcli project lifecycle (start/stop/status/export)
- `sdk/quantlab/phase4/retester/` — CFX template generation + sqcli + databank export for Monte Carlo/WF reports
- Shared `CfxTemplateBuilder` utilities for Portfolio/Optimizer/Retester CFX XML structures

### Out of Scope
- JCloud upload/deployment (no API exists — stops at `.java` file output)
- Multi-instance SQX orchestration (requires multiple SQX installs; out of scope for Phase 4)
- GUI automation / Selenium fallback (HTTP API + sqcli covers all needed operations)
- Portfolio backtesting engine rebuild (uses SQX internal engine via PortfolioComposer)

## Capabilities

### New Capabilities
- `jforex-deploy`: Export strategy `.java` + custom indicators via HTTP `sourcecode/print`; deploy to JForex strategies folder
- `portfolio-composer`: Load strategies, optimize weights via HTTP recompute/savePortfolio, export portfolio CFX
- `portfolio-master`: Generate genetic portfolio builder CFX, run via sqcli, extract selected strategies
- `optimizer-automation`: Generate optimizer CFX from parameter spec, run sqcli, export results to CSV/DataFrame
- `retester-automation`: Generate retester CFX from strategy + databanks, run sqcli, export Monte Carlo/WF reports

### Modified Capabilities
- `cfx-editor`: Extend `CfxWriter`/`CfxReader` with Portfolio/Optimizer/Retester section writers (AutomaticPortfolioBuilder, Optimization, Parameters, Databanks, WalkForward, Rankings, CrossChecks)
- `sqx-translator`: Add Portfolio/Optimizer/Retester CFX template methods (reuses cfx-editor extensions)
- `sqx-cli-wrapper`: Add PortfolioComposer/Master/Optimizer/Retester project action methods (loadconfig, start, status, export)

## Approach

Unified `sdk/quantlab/phase4/` package with four submodules sharing `CfxTemplateBuilder` for CFX XML generation. Each submodule exposes a high-level async API:

```python
# JForex Deploy
await JForexDeployer.export_strategy(strategy_id, output_dir)
await JForexDeployer.deploy_indicators(jforex_strategies_dir)

# Portfolio
await PortfolioComposer.optimize_weights(strategies, fitness="ReturnDDRatio")
await PortfolioMaster.build_portfolio(strategies, generations=50, population=200)

# Optimizer
await Optimizer.run(config=OptimizerConfig(walkforward_cycles=5, method="genetic"))

# Retester
await Retester.run(config=RetesterConfig(databanks=["EURUSD_H1"], monte_carlo_runs=100))
```

All sqcli calls route through extended `CommandDispatcher`; all CFX generation routes through extended `cfx-editor`. HTTP calls require `-gui` server (managed by `sqx-cli-wrapper` daemon lifecycle).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/phase4/jforex_deploy/` | New | HTTP export + indicator copy |
| `sdk/quantlab/phase4/portfolio/` | New | Composer HTTP + Master CFX/sqcli |
| `sdk/quantlab/phase4/optimizer/` | New | Optimizer CFX template + sqcli |
| `sdk/quantlab/phase4/retester/` | New | Retester CFX template + sqcli |
| `sdk/quantlab/cfx/` | Modified | Extended writers for Portfolio/Optimizer/Retester sections |
| `sdk/quantlab/sqx_translator/` | Modified | New CFX template methods |
| `sdk/quantlab/sqx_cli/` | Modified | New project action methods + daemon mgmt |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| SQX single-instance limit blocks parallel portfolio+optimizer runs | High | Document serial execution; multi-install orchestration deferred |
| HTTP API requires `-gui` server; headless CI needs Xvfb | Medium | `sqx-cli-wrapper` manages daemon lifecycle; document Xvfb setup |
| CFX binary format changes across SQX versions | Low | Version-check in `CfxReader`; test against SQX 144.2953 baseline |
| JForex indicator paths differ by platform | Low | Configurable base path; default to SQX install `custom_indicators/JForex/` |
| Portfolio weight optimization non-deterministic (genetic) | Medium | Seed control in CFX; export weights for reproducibility |

## Rollback Plan

1. Delete `sdk/quantlab/phase4/` directory
2. Revert `cfx-editor`, `sqx-translator`, `sqx-cli-wrapper` extensions via git
3. No database migrations or external state — pure SDK code removal

## Dependencies

- SQX 144.2953 installed at `assets/SQX_144_2953_linux_20260601/`
- Python 3.11+ with `httpx`, `pydantic`, `lxml` (already in SDK deps)
- Xvfb for headless `-gui` server in CI (optional, documented)

## Success Criteria

- [ ] `JForexDeployer.export_strategy()` produces valid `.java` compilable in JForex SDK
- [ ] `PortfolioComposer.optimize_weights()` returns weight vector matching SQX GUI result (±0.1%)
- [ ] `PortfolioMaster.build_portfolio()` completes genetic search and exports selected strategies
- [ ] `Optimizer.run()` executes walk-forward optimization and exports CSV with expected columns
- [ ] `Retester.run()` produces Monte Carlo report with percentile bands matching GUI
- [ ] All four submodules pass dry-run tests without SQX installation
- [ ] End-to-end integration test: DSL → CFX → Optimize → Retest → Portfolio → JForex export