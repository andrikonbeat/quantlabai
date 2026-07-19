# Tasks: Phase 4 — JForex, Portfolio, Optimizer, Retester

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 2000-3000 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 |
| Delivery strategy | auto-chain |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Foundation: errors, http_client, lock, cfx_templates, config models + CFX editor extensions | PR 1 | Base branch = feature/phase4-foundation; tests/docs included |
| 2 | JForex Deploy + Portfolio Composer + Portfolio Master | PR 2 | Base = feature/phase4-foundation; depends on PR 1 |
| 3 | Optimizer + Retester + CLI (DaemonManager, actions) + Translator + Tests | PR 3 | Base = PR 2 branch; depends on PR 1+2; integration tests |

## Phase 1: Foundation — Shared Infrastructure & CFX Extensions

- [x] 1.1 Create `sdk/quantlab/phase4/__init__.py` exporting all public symbols
- [x] 1.2 Create `sdk/quantlab/phase4/errors.py` with Phase4Error hierarchy (13 exception classes incl. StrategyNotFoundError, DatabankPathError, UnsupportedSQXVersionError, SQXBindingError)
- [x] 1.3 Create `sdk/quantlab/phase4/http_client.py` with AsyncSQXClient (retry/timeout/health, version detection, circuit breaker, 429 handling, localhost-only binding)
- [x] 1.4 Create `sdk/quantlab/phase4/lock.py` with SQXSessionLock (asyncio.Lock + optional file lock via portalocker/fcntl, lock file at ~/.quantlab/sqx-{hash}.lock)
- [x] 1.5 Create `sdk/quantlab/phase4/cfx_templates.py` with CfxTemplateBuilder static methods (build_portfolio_cfx, build_optimizer_cfx, build_retester_cfx)
- [x] 1.6 Create `sdk/quantlab/phase4/daemon_manager.py` with DaemonManager (bind_address enforcement, startup health check, auto-restart, SIGTERM/SIGKILL)
- [x] 1.7 Add PortfolioCfxModel, OptimizerCfxModel, RetesterCfxModel to `sdk/quantlab/cfx/models.py`
- [x] 1.8 Extend `sdk/quantlab/cfx/reader.py` with read_portfolio_cfx, read_optimizer_cfx, read_retester_cfx; extend _SETTINGS_SECTIONS, _COMPLEX_SECTIONS
- [x] 1.9 Extend `sdk/quantlab/cfx/writer.py` with set_automatic_portfolio_builder, set_portfolio_settings, set_optimization, set_optimization_parameters, set_walkforward, set_databanks, set_rankings, set_crosschecks, set_retester_data
- [x] 1.10 Extend `sdk/quantlab/cfx/patcher.py` with 8 new PatchInstruction models + validators/appliers for portfolio/optimizer/retester
- [x] 1.11 Add unit tests for Phase 1: errors hierarchy, AsyncSQXClient retry/health/version/circuit-breaker, SQXSessionLock acquire/release, CfxTemplateBuilder output validation, CFX reader/writer/patcher round-trips

## Phase 2: JForex Deploy + Portfolio Composer + Portfolio Master

- [x] 2.1 Create `sdk/quantlab/phase4/jforex_deploy.py` with JForexDeployer (export_strategy via HTTP sourcecode/print, deploy_indicators copy from SQX custom_indicators/JForex/, dry-run mode)
- [x] 2.2 Create `sdk/quantlab/phase4/portfolio_composer.py` with PortfolioComposer (atomic load_strategies with rollback on failure, optimize_weights via HTTP /recompute, save_portfolio via HTTP /savePortfolio, create_portfolio high-level method)
- [x] 2.3 Create `sdk/quantlab/phase4/portfolio_master.py` with PortfolioMaster (build_cfx via CfxTemplateBuilder, run via CommandDispatcher loadconfig/start/status/export, extract_selected_strategies from result XML)
- [x] 2.4 Create `sdk/quantlab/phase4/command_dispatcher.py` with CommandDispatcher (load_config, start_project, get_status, stop_project, export_results, _run_with_lock integration for SQXSessionLock, CampaignStatus parsing)
- [x] 2.5 Move DaemonManager from cli/runner.py to phase4/daemon_manager.py (already created in Phase 1); update imports in runner.py
- [x] 2.6 Add unit tests for Phase 2: JForexDeployer export/deploy dry-run, PortfolioComposer atomic load/optimize/save, PortfolioMaster CFX build/run/extract, CommandDispatcher new actions serialization

## Phase 3: Optimizer + Retester + CLI Integration + Translator + Integration Tests

- [x] 3.1 Create `sdk/quantlab/phase4/optimizer.py` with Optimizer (run via CommandDispatcher lifecycle, export_results CSV, config uses strategy_id for CFX)
- [x] 3.2 Create `sdk/quantlab/phase4/retester.py` with Retester (run via CommandDispatcher, export_reports HTML + databank, databank validation regex ^[A-Z]{6}_[A-Z]\d+$, path traversal check)
- [x] 3.3 Extend `sdk/quantlab/translate/translator.py` with generate_portfolio_cfx, generate_optimizer_cfx, generate_retester_cfx (delegate to CfxTemplateBuilder)
- [x] 3.4 Extend `sdk/quantlab/translate/cfx.py` CFX packaging for portfolio/optimizer/retester task types (config.xml + Portfolio-Task1.xml, Optimizer-Task1.xml, Retester-Task1.xml)
- [x] 3.5 Add integration tests: JForex end-to-end dry-run, Portfolio Composer weight optimization dry-run, Portfolio Master genetic search dry-run, Optimizer walk-forward dry-run CSV export, Retester Monte Carlo/WF dry-run HTML export, full DSL → CFX → Optimize → Retest → Portfolio → JForex dry-run chain
- [x] 3.6 Add CLI action wiring in cli/main.py for new project types (portfolio, master, optimizer, retester, jforex)
- [x] 3.7 Update CLI lock handling: acquire SQXSessionLock in CommandDispatcher for all new project types (handled in command_dispatcher.py — PR 2)
- [x] 3.8 Update `openspec/config.yaml` rules.tasks if Phase 4 conventions added
- [x] 3.9 Documentation: update SDK README with Phase 4 usage examples; add dry-run test scripts to tests/phase4/

## Phase 4: Cleanup & Polish

- [x] 4.1 Remove any temporary/debug code from implementation
- [x] 4.2 Verify all public exports in phase4/__init__.py are complete
- [x] 4.3 Run full test suite (pytest tests/ -x) and confirm all pass
- [x] 4.4 Verify dry-run tests pass without SQX installation
- [x] 4.5 Update CHANGELOG.md with Phase 4 summary