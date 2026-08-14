# Changelog

All notable changes to QuantLab AI will be documented in this file.

## [Unreleased] — Multi-Agent Research System

### Repository Reorganization (2026-08-14)
- Reorganized the repository for GitHub readiness: root docs moved under
  `docs/`, SQX Builder reference under `docs/sqx-builder-config/`, DB init
  schema under `infra/`, prompt registry under `AI/opencode/`.
- Added complete `.gitignore` / `.gitattributes` (LFS), `LICENSE` (MIT), and
  `SECURITY.md`; removed dead code and duplicated knowledge trees.
- First push to GitHub: `main` + `feat/per-phase-subagent-delegation-pr5`.


### Added (PR 1 — Foundation & Pipeline Core Extensions, ≈2100 lines)
- `GateInterceptorStage` abstract stage with async callback protocol, timeout handling, fallback policies (ABORT/CONTINUE/ESCALATE), Engram recording
- 8 abstract agent stage classes (Research, Builder, Statistics, Review, Portfolio, Deploy, Monitor, Gate) with `requires`/`provides` contracts
- `PipelineRunner.validate_contracts()` for stage dependency verification with `ContractValidationError`
- `MultiAgentPipelineConfig` Pydantic model with pipeline/agents/gates/memory/risk sections
- Pipeline config JSON Schema for YAML validation
- Config migration helper (v1→v2) for backward compatibility
- Env-var overrides via `QUANTLAB_PIPELINE_*` prefix
- Agent stage registry with 7 agent + 5 gate aliases alongside 11 SQX builtin stages
- `PipelineRunner.build_from_config()` for multi-agent pipeline construction
- `PipelineRunner.run_with_gates()` method with gate injection at configured positions
- Full backward compatibility: original 9-stage pipeline unchanged

### Added (PR 2 — Core Agents, ≈4700 lines)
- `ResearchDirector`: central orchestrator owning PipelineRunner, managing campaign lifecycle (create/run/pause/resume/rollback), iteration optimisation loop with convergence detection
- `ResearchAgent`: hypothesis generation from objectives, DSL extension for hypotheses/iteration config/gate policies
- `BuilderAgent`: CFX translation + SQX dispatch with retry logic and timeout
- Extended `ResearchConfig` DSL with hypotheses, iteration_config, gate_policies
- Example `research-config.yaml` and `pipeline.yaml` for multi-agent campaigns

### Added (PR 3 — Analysis Agents, ≈4300 lines)
- `StatisticsAgent`: full statistics computation, cross-campaign aggregation, Monte Carlo bands
- `ReviewerAgent`: criteria evaluation (ACCEPT/ITERATE/REJECT), walk-forward degradation detection, MC overfitting flags, benchmark comparison
- `PortfolioAgent`: Portfolio Master integration with correlation analysis, risk budgeting, Kelly fraction capping, walk-forward validation

### Added (PR 4 — Gates & Deployment, ≈2400 lines)
- `HumanGateOrchestrator`: manages 5 human gates with async approval protocol, configurable timeouts, fallback policies, notification hooks (email/Slack/file)
- Gate interceptor integration: `GateInterceptorStage` pauses pipeline, invokes orchestrator, records decision to Engram
- `DeploymentAgent`: JForex packaging (JAR/WAR), JCloud config generation, dry-run validation mode

### Added (PR 5 — Monitoring, Persistence & Reporting, ≈1300 lines)
- `MonitoringAgent`: live equity streaming, rolling Sharpe/drawdown, regime detection (252-period), alerting via context + gate trigger
- Knowledge Lake agent-memory directory structure (`agent-memory/{agent_name}/{campaign_id}/`)
- `AgentMemoryManager` wrapping Engram with per-agent topic keys and TTL policies
- Reporting extensions: agent decision audit sections, multi-campaign comparison, iteration progression views
- Cross-agent queries via `QueryBuilder.query_agent_memory()` and campaign similarity search

### Added (PR 6 — CLI, Integration, Docs, ≈3200 lines)
- `pipeline validate <config>` — validate pipeline config YAML with contract checking
- `pipeline run --research-config <file>` — run multi-agent campaigns via ResearchDirector
- `agent memory inspect <agent> <campaign>` — query Engram for agent memory
- `agent memory query <pattern>` — cross-agent pattern search
- `campaign rollback <id>` — delete Knowledge Lake artifacts for a campaign
- `campaign status <id>` — show campaign state from Knowledge Lake
- Full integration test suite: 17-stage dry-run, mock SQX e2e smoke, Knowledge Lake + Engram persistence
- Architecture docs: multi-agent system, pipeline config, agents, deployment, gates

### Changed
- `PipelineRunner` extended with multi-agent pipeline building and gate injection (PR 1)
- Pipeline config models support both flat and nested `pipeline.*` format (PR 1)
- `KnowledgeStore` extended with agent-memory directory structure and campaign indexing (PR 5)
- `ReportingGenerator` extended with agent decision audit and multi-campaign comparison views (PR 5)
- All PRs maintain backward compatibility: original 9-stage pipeline unchanged

## [Phase 4] — 2026-07-18

### Added (PR 1 — Foundation, ≈1900 lines)
- `quantlab.phase4` package with error hierarchy (Phase4Error + 13 subclasses incl. StrategyNotFoundError, DatabankPathError, UnsupportedSQXVersionError, SQXBindingError)
- `AsyncSQXClient` HTTP client with retry, circuit breaker, version detection, and 429 Retry-After handling
- `SQXSessionLock`: async + file lock for single-instance SQX serialization
- `DaemonManager` (`SQXDaemonManager`): SQX `sqcli` lifecycle with localhost-only binding enforcement, health checks, auto-restart
- `CfxTemplateBuilder`: static methods for Portfolio/Optimizer/Retester CFX generation
- CFX editor extensions: `PortfolioCfxModel`, `OptimizerCfxModel`, `RetesterCfxModel`, `AutomaticPortfolioBuilderConfig`, `PortfolioSettingsConfig`, `OptimizationConfig`, `OptimizationParametersConfig`, `WalkForwardConfig`, `DatabanksConfig`, `RankingsConfig`, `CrossChecksConfig`, `RetesterDataConfig`
- CFX reader extensions: `read_portfolio_cfx()`, `read_optimizer_cfx()`, `read_retester_cfx()`
- CFX writer extensions: `set_automatic_portfolio_builder()`, `set_portfolio_settings()`, `set_optimization()`, `set_optimization_parameters()`, `set_walkforward()`, `set_databanks()`, `set_rankings()`, `set_crosschecks()`, `set_retester_data()`
- CFX patcher: 8 new PatchInstruction types for portfolio/optimizer/retester with validators and appliers

### Added (PR 2 — JForex + Portfolio, ≈2300 lines)
- `JForexDeployer`: async strategy export via SQX HTTP API, indicator deployment to JForex 4 SDK
- `PortfolioComposer`: atomic strategy loading, weight optimization via `/recompute`, portfolio save, `create_portfolio()` high-level method
- `PortfolioMaster`: genetic portfolio builder via CFX + sqcli lifecycle, result parsing (CSV/XML), selected strategy extraction
- `CommandDispatcher`: async SQX campaign operations via HTTP command API (`/call?cmd=`), `SQXSessionLock` integration, project output management
- Full async conversion of domain modules with dry-run modes

### Added (PR 3 — Optimizer + Retester + CLI, ≈6000 lines)
- `Optimizer`: walk-forward optimization via sqcli, CSV export, HTML report generation, CSV parsing with adaptive column detection
- `Retester`: Monte Carlo / Walk-Forward retesting via sqcli, databank validation (regex `^[A-Z]{6}_[A-Z]\d+$`), HTML report with stability color-coding
- Translator extensions: `generate_portfolio_cfx()`, `generate_optimizer_cfx()`, `generate_retester_cfx()` delegating to CfxTemplateBuilder
- CFX packaging for portfolio/optimizer/retester task types (config.xml + Portfolio-Task1.xml, Optimizer-Task1.xml, Retester-Task1.xml)
- CLI entry point: `quantlab.cli.main` with subcommands (daemon, portfolio, optimizer, retester, jforex)
- `CampaignOrchestrator`: 11-phase pipeline with progress callbacks, dry-run mode, async context manager
- Result dataclasses: `OptimizationResult`, `WalkForwardCycle`, `RetestResult`, `MonteCarloResult`, `WalkForwardResult`, `PortfolioWeightResult`, `PortfolioMasterResult`, `SelectedStrategy`
- Phase 4 dry-run tests without SQX installation dependency

### Changed
- `CommandDispatcher` rewritten from subprocess-based to async HTTP API via `AsyncSQXClient` (PR 2)
- Domain modules fully async with `httpx.AsyncClient` + `asyncio` (PR 1–3)
- KnowledgeStore fixed: recursion in `read_index()`/`rebuild_index()` broken by implementing proper filesystem scanning in `rebuild_index()` (PR 3 cleanup)

## [Phase 3] — 2026-07-15

### Added
- CFX editor: CfxReader, CfxWriter, CfxPatcher for reading/writing/patching CFX archives
- CfxTemplateBuilder for generating CFX archives programmatically
- CMake-style instruction system (build tasks → patch instructions → appliers)
- Statistics engine: profit factor, Sharpe ratio, max drawdown, MAR, expectancy

## [Phase 2] — 2026-07-13

### Added
- Knowledge Lake: KnowledgeStore with index, format validation, rebuild
- Statistics engine (`quantlab.stats`)
- SQX CLI wrapper (`quantlab.cli.runner`)
- License validation module
- Pipeline error types
- Campaign orchestrator (initial version)

## [Phase 1] — 2026-07-13

### Added
- YAML DSL: ResearchConfig models + parser
- CFX translator: model-to-XML conversion
- Databank readers: CSV/XLSX trade/equity/summary reading
- CLI dry-run mock executor
- Project structure with pyproject.toml
- Initial test suite
