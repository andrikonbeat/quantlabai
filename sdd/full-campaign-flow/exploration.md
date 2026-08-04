## Exploration: full-campaign-flow QuantLab

### Current State
The applied `orchestrated-campaign-flow` change (archived 2026-08-04) gives an 8-phase loop (research → hypothesis → config → config review → dispatch → monitor → retest → optimize) that STOPS at optimize (D1, no deploy). `quantlab-campaign` subagent (`AI/opencode/agents/campaign.md`) owns it; decision-file gates under /tmp/sqx-gates; Dukascopy-only data (D5); ConfigReviewer + HUMAN_APPROVE_CONFIG gate; fail-closed HOLD (REQ-11). SDK: pipeline framework (Pipeline/Stage/PipelineRunner), StageRegistry with config_review/dispatch/retester/optimizer stages, phases as one-shot single-task CFX runs.

### SQX installation evidence (assets/SQX_144_2953_linux_20260601.zip, 1224.5MB / 2630.6MB, 11222 entries)
- Version 144, build 2953, packaged 2026-06-01 (folder name). Sample project format versions 126.2189–143.2708; SDK CFX generators already use schema_version "144.2953".
- `sqcli` = Go-compiled Launch4j-style launcher → `com.strategyquant.strategyquant.SQConsoleStarter` (JVM engine). Bundled Azul Zulu 25 (Java 25) in `j64/` — JRE, NOT JDK (no javac).
- **CFX format CONFIRMED**: `.cfx` = ZIP archive containing `config.xml` + optional per-task XML files referenced via `taskXMLFile` attr (verified PK magic; dumped Builder/Retester/Optimizer/PortfolioMaster/VolumeProfile sample projects). `<Project name= version=>` root with `<Tasks><Task type= name= taskXMLFile= active=>` and `<Databanks><Databank name= view= syncType= position=>`.
- **Custom Project task catalog (21 tasks, from internal/plugins/Task*/task.xml)**: Build (task_forex/futures/stockpicker.xml, 1.27MB schema), Retest, Optimize, AutomaticRetest, AutomaticPortfolioBuilder, Filtering (Conditions + Source/Target databank), GoToTask (conditional, Conditions), LoadFromFiles, SaveToFiles, ClearDatabanks, CreatePortfolio, CustomAnalysis (per-strategy + full-databank), DeleteFile, CallExternalScript, LogDatabankStats, NeuralNetworkTrainer, Notification (email), StopAndStart, UpdateData, WaitFor, ApplyMassConfig. Plus SettingsGoToTask.
- **CrossChecks (Retest task)**: RetestOnAdditionalMarkets, RetestWithHigherPrecision, MonteCarloRetest, MonteCarloManipulation, WalkForwardOptimization, WalkForwardMatrix, SequentialOptimization, OptProfileSysParamPermutation, WhatIf. Walk-Forward lives INSIDE Optimize/Retest tasks (no standalone task).
- **Source code export**: `sourcecode/print` type `JForex (*.java)` + mq4/mq5/el/pla/pseudo/xml (ResultsPluginsService).
- **Data**: bundled Dukascopy M1/H1 history ~14 symbols (user/data/History/*_dukas); DataSourceDukascopy/MT5Api/TD/Yahoo/crypto; engines MetaTrader4 (SDK default), MetaTrader5, Tradestation. JForex engine experimental since build 130.
- **Unknown/not verified**: full Builder tab schema beyond sampled sections; sqcli subcommand surface beyond SDK-used (`-project action=start/stop/status/loadconfig`, `-databank action=export`, `-symbol`, `-data`, `-h` readiness probe); whether CFX writer's simplified `<Settings>` dialect is accepted by real SQX (RawXmlSection used as workaround); JForex engine backtest capability.

### Existing SDK map (all under sdk/quantlab/)
- `cfx/` — CfxProject model IS multi-task capable (tasks: dict[str, BuildTask]) but generators emit single-task archives; writer/reader/patcher/dom.
- `translate/translator.py` — DSL→Build CFX (generate_cfx_archive), generate_portfolio/optimizer/retester_cfx_archive.
- `phase4/` — retester.py, optimizer.py, portfolio_composer.py (HTTP recompute/savePortfolio), portfolio_master.py, jforex_deploy.py (export .java ONLY — NO compile/.jfx), campaign_orchestrator.py (one-shot pipeline), checkpoint.py, daemon.py + daemon_manager.py + http_client.py + lock.py, templates.py (CfxTemplateBuilder).
- `sqx/` — cli_wrapper.py (daemon HTTP dispatch, _dispatch_real + mock path), command_dispatcher.py (load_config→start→status→export), daemon.py, project_builder.py (SINGLE-TASK Build from hardcoded .sqx-template + regex patching; BuildConfig with ~90 fields), campaign_monitor.py (stall detection), llm_generation_monitor.py, blocks_bridge.py, mock_sqx_server.py.
- `agents/` — research_director (build_pipeline orchestrated flag), research_agent, hypothesis_builder/, builder_agent (orchestrated split), config_reviewer, reviewer_agent, statistics_agent, portfolio_agent, deployment_agent (JAR packaging is a PLACEHOLDER), monitoring_agent, autonomous_monitor (live daemon), llm_research_agent, analysis_agent.
- `gates/` — callbacks (decision-file), orchestrator, notifiers (console/webhook/email/slack — NO mobile), models (6 gates: 5 legacy + HUMAN_APPROVE_CONFIG).
- `pipeline/` — generic framework + stages (agent_stages incl. GuardianEvaluationStage, monte_carlo, retester, optimizer, dispatch, config_review) + registry + runner.
- `guardian/` — Market/Risk/Portfolio/Capital/Quality/ExecutionGuardian + MetaGuardianOrchestrator + state machine (NORMAL/VIGILANCE/DEFENSIVE/QUARANTINE/RECOVERY).
- `costs/` — collector (spread/slippage/session), engine, profiles, models. `regime/`, `robustness/`, `health/`, `stats/`, `readers/`, `reporting/`, `knowledge/`, `analysis/`, `evolution/`, `mcp/`, `dashboard/`, `cli/`, `data/` (DataManager Dukascopy-only, SymbolRegistry).

### OpenSpec map
Specified+buildt: campaign-orchestration (8-phase, D1), campaign-orchestrator, retest-optimize-stages, human-gates (REQ-10/11), buildconfig-bridge (REQ-03/04), config-review (REQ-05/06), data-manager (REQ-12/13), monitor-observability (REQ-14/15), campaign-monitor, optimizer-automation, retester-automation, portfolio-composer, portfolio-master, jforex-deploy (.java export only), meta-guardian, autonomous-monitor, cost-collector/cost-engine/cost-pipeline-integration, hypothesis-builder, refutation-layer, health-score, pipeline-core, cfx-editor, dashboard-api/ui, cli-bridge/entrypoint, quantlab-orchestrator. Changes applied/archived: orchestrated-campaign-flow, reconfiguration-loop, results-analysis-stage; tasks-only: advanced-robustness, autonomous-monitor.
MISSING for the full flow (nothing specified): full lifecycle spec, compiler pipeline, demo deploy, archive phase, Guardian→generation feedback loop, mobile/24-7 operations.

### Gaps & design questions
(a) Custom-project model: need DSL CustomProject (ordered tasks, per-task databank source/target, filters, loops/GoToTask conditions) + multi-task .cfx project generator reusing verified sample structure (taskXMLFile routing). Existing CfxProject tasks dict is the seed.
(b) Generic execution/monitoring substrate: 3 overlapping paths (CommandDispatcher, cli_wrapper._dispatch_real, CampaignOrchestrator). Unify: daemon + project lifecycle + polling + event detection (CampaignMonitor) + checkpoint + export, parameterized per phase (build/retest/optimize/portfolio).
(c) Compiler pipeline: export .java exists; javac compile missing (j64 is JRE — need external JDK or JForex SDK), error-fix loop missing, .jfx packaging missing.
(d) Demo deploy: 14 business-day demo window; renewal semi-manual; DeploymentAgent JAR placeholder; JCloud config exists in design only.
(e) Archive phase: maintenance/replacement plan + account statistics — nothing exists.
(f) Guardian live data: MetaGuardian+autonomous_monitor monitor equity; live Dukascopy/JForex positions/equity/costs feed + feedback into generation flow NOT wired (reconfiguration-loop is backtest-side only).
(g) Mobile notifications (only console/webhook/email/slack) + 24/7 server op (daemon mode OK; -run/-gui SQConsoleStarter flags unused; hardcoded license "FUTLABF255" + license_preflight).

### Approaches
1. **Extend harness in place** — extend `quantlab-campaign` prompt + stages (portfolio_stage, compiler_stage, demo_deploy_stage, archive_stage) under same flag-gated orchestrated pattern. Pros: consistent envelope/gates/fail-closed; reuses decision-file protocol. Cons: campaign.md grows; needs new gates (HUMAN_APPROVE_PORTFOLIO exists, add HUMAN_APPROVE_DEPLOY, HUMAN_APPROVE_DEMO, HUMAN_APPROVE_ARCHIVE). Effort: High.
2. **Custom-project CFX generator first** — build DSL custom-project model + multi-task .cfx generator validated against archive samples; then wire execution substrate. Pros: enables SQX-native multi-task (filter→retest→optimize) with one project load; matches SQX capabilities. Cons: XML dialect risk; largest unknown (SQX schema acceptance). Effort: High.
3. **Unify execution substrate** — one Executor/Runner parameterized per phase (build/retest/optimize/portfolio) replacing 3 overlapping paths. Pros: checkpoint+resume, event detection, notifications shared. Cons: refactor risk to 2790-test suite. Effort: Medium-High.

### Recommendation
Build the full lifecycle as an extension of the orchestrated harness (approach 1) using a unified execution substrate (approach 3) underneath, and introduce the custom-project CFX generator (approach 2) as the first slice since it unlocks retest/optimize task chaining in one project load. Constraint honored: simplification only on code/infra; all 14 flow phases + Guardian flow retained with human confirmation.

### Risks
- Exact custom-project task list is build-dependent (verified 144/2953: 21 tasks).
- JForex engine experimental since build 130; Dukascopy backtests run on MetaTrader4 engine.
- Demo account renewal semi-manual (14-day window).
- CFX writer simplified dialect vs SQX-native Param className — validate against archive sample projects.
- Hardcoded license; license_preflight exists. j64 is JRE, not JDK (compiler needs external JDK).
- Mock-vs-real divergence (SQX_FORCE_MOCK) — large suite runs on mock server.
- Delivery strategy auto-chain stacked-to-main: change likely exceeds 400-line budget → chained PRs forecast needed at sdd-tasks.

### Ready for Proposal
Yes — propose next (sdd-propose). Tell user: phases must be retained in order; propose as one change with phased slices (custom-project generator → unified substrate → compiler → demo deploy → archive → guardian feedback).
