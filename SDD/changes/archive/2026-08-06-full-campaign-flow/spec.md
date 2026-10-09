# Delta Spec: Full Campaign Flow

**Change**: `full-campaign-flow` — complete QuantLab lifecycle from idea to live demo (100 USD Dukascopy account) and archived campaign. Constraint: all 14 flow phases + Guardian flow MUST remain, in order, each gated by human confirmation; simplification applies to code/infrastructure only, never flow steps. Data scope: Dukascopy-only.

**Traceability**: 7 new capabilities → full specs in `openspec/specs/`; 5 modified capability groups → delta specs under `openspec/changes/full-campaign-flow/specs/`. REQ IDs continue the global numbering (existing REQ-01..21 from `orchestrated-campaign-flow`).

| Req | Domain | Capability | Type |
|-----|--------|-----------|------|
| REQ-22..25 | custom-project-generator | new | full spec |
| REQ-26..28 | execution-substrate | new | full spec |
| REQ-29..30 | compiler-pipeline | new | full spec |
| REQ-31..32 | demo-deploy | new | full spec |
| REQ-33 | campaign-archive | new | full spec |
| REQ-34 | guardian-feedback | new | full spec |
| REQ-35..36 | mobile-notifications | new | full spec |
| REQ-01 (M), REQ-37 | campaign-orchestration | modified | delta |
| REQ-38 | human-gates | modified | delta |
| REQ-39 | jforex-deploy | modified | delta |
| REQ-40 | meta-guardian | modified | delta |
| REQ-41 | autonomous-monitor | modified | delta |
| REQ-42 | campaign-monitor | modified | delta |
| REQ-43 | retester-automation | modified | delta |
| REQ-44 | optimizer-automation | modified | delta |

---

# Domain: custom-project-generator (NEW)

## ADDED Requirements

### Requirement: DSL CustomProject Model (REQ-22)

The system MUST provide a `CustomProject` DSL model with an ORDERED task list; each task MUST carry `type`, `name`, `active`, per-task `source_databank`/`target_databank`, optional `filters`, and an optional `taskXMLFile` reference. A `GoToTask` task MUST support a `condition` referencing prior task output to form loops. Task order MUST be preserved exactly as declared.

#### Scenario: Ordered tasks round-trip

- GIVEN a CustomProject declaring tasks Build, Filtering, Retest, Optimize in that order
- WHEN the model is serialized
- THEN task order in output matches the declaration exactly
- AND every task retains type, name, databank source/target, and active flag

#### Scenario: GoToTask conditional loop

- GIVEN a CustomProject with Filtering → Retest → GoToTask(Filtering) with condition `retest_failed`
- WHEN serialized
- THEN GoToTask references the earlier task by name
- AND its condition is preserved in the task XML

#### Scenario: Per-task databank routing

- GIVEN tasks with distinct source_databank/target_databank pairs
- WHEN serialized
- THEN each task XML references only its own databanks
- AND no databank is shared implicitly across tasks

### Requirement: Multi-Task CFX Generator (REQ-23)

The system MUST generate a `.cfx` ZIP archive containing `config.xml` plus one XML file per non-trivial task, routed from `<Task ... taskXMLFile="...">` entries, with `<Project name= version=>` root and `<Databanks><Databank name= view= syncType= position=>` section. Schema version MUST be `144.2953`. Single-task projects MUST produce output structurally identical to the existing generator.

#### Scenario: ZIP matches verified format

- GIVEN a 4-task CustomProject
- WHEN `generate_cfx_archive(project)` runs
- THEN the output is a ZIP containing config.xml
- AND one task XML file per task
- AND each `<Task taskXMLFile=...>` attribute matches the packaged file name
- AND `<Databanks>` lists every declared databank

#### Scenario: Single-task backward compatibility

- GIVEN a CustomProject with one Build task
- WHEN the archive is generated
- THEN output is structurally identical to the current single-task CFX
- AND existing consumers accept it unchanged

### Requirement: Golden Validation Against SQX Samples (REQ-24)

The generator MUST validate generated archives against the verified SQX 144/2953 format (`schema_version "144.2953"`), using `assets/SQX_144_2953_linux_20260601/` sample projects as goldens. Validation MUST reject archives whose structure deviates from the golden format. A readiness probe via `sqcli -h` SHALL run before validation.

#### Scenario: Generated CFX accepted by real SQX

- GIVEN a generated multi-task archive
- WHEN `sqcli -project action=loadconfig` loads it
- THEN sqcli accepts the archive without schema errors
- AND taskXMLFile routing resolves for every task

#### Scenario: Deviation fails closed

- GIVEN a generated archive with a malformed Tasks section
- WHEN golden validation runs
- THEN a ValidationError is raised naming the deviating element
- AND no dispatch is attempted

### Requirement: Task Catalog Coverage (REQ-25)

The generator SHALL support the verified 21-task catalog (Build, Retest, Optimize, AutomaticRetest, AutomaticPortfolioBuilder, Filtering, GoToTask, LoadFromFiles, SaveToFiles, ClearDatabanks, CreatePortfolio, CustomAnalysis, DeleteFile, CallExternalScript, LogDatabankStats, NeuralNetworkTrainer, Notification, StopAndStart, UpdateData, WaitFor, ApplyMassConfig). Walk-Forward SHALL be expressed inside Retest/Optimize `CrossChecks`, not as a standalone task. Unsupported task types MUST raise a clear error.

#### Scenario: All catalog tasks supported

- GIVEN any task type from the 21-task catalog
- WHEN the generator renders it
- THEN a task XML is produced with the correct taskXMLFile
- AND Walk-Forward settings render inside Retest/Optimize CrossChecks

#### Scenario: Unknown task type rejected

- GIVEN a task type outside the catalog
- WHEN the generator renders it
- THEN a TaskNotSupportedError is raised naming the type

---

# Domain: execution-substrate (NEW)

## ADDED Requirements

### Requirement: Unified Substrate (REQ-26)

The system MUST provide a single execution substrate parameterized by phase, providing daemon lifecycle, project load/start/status/stop, polling, event detection, checkpoint/resume, and export. When the unified flag is enabled, each phase MUST run on the substrate and produce output identical to the legacy path it replaces for the same inputs.

#### Scenario: Phase runs on substrate

- GIVEN the unified flag enabled and a build phase config
- WHEN the phase executes
- THEN the substrate loads the project, polls status, detects events, and exports results
- AND output artifacts match the legacy path for identical inputs

#### Scenario: Checkpoint resume

- GIVEN a phase interrupted at checkpoint N
- WHEN the phase is re-run
- THEN execution resumes at checkpoint N+1 without redoing completed work

### Requirement: Chained Multi-Task Runs (REQ-27)

The substrate SHALL execute retest and optimize chained in ONE project load via a multi-task Custom Project (REQ-23), preserving phase order and human gates between tasks. Only Dukascopy databanks MUST be used.

#### Scenario: Retest then optimize in one load

- GIVEN a multi-task project declaring Retest then Optimize tasks
- WHEN the substrate runs the project
- THEN SQX executes both tasks in declared order in a single load
- AND each task's exports land in its phase checkpoint

#### Scenario: Gate holds between chained tasks

- GIVEN a human gate configured between retest and optimize
- WHEN retest completes
- THEN the substrate holds before optimize until the gate resolves

### Requirement: Legacy Parity (REQ-28)

The substrate MUST keep legacy dispatch paths operational behind a flag until parity is proven; the 2790-test suite MUST keep passing on the legacy path. `SQX_FORCE_MOCK` SHALL remain honored for the suite.

#### Scenario: Legacy path unchanged

- GIVEN the unified flag disabled
- WHEN dispatch runs
- THEN the legacy path executes with prior behavior
- AND the full test suite passes

#### Scenario: Mock mode retained

- GIVEN `SQX_FORCE_MOCK` set
- WHEN the substrate runs
- THEN mock server responses are used

---

# Domain: compiler-pipeline (NEW)

## ADDED Requirements

### Requirement: Compile and Package .jfx (REQ-29)

The system MUST compile exported `.java` sources with `javac` from a configured external JDK (Java 25-compatible) and package the compiled classes into a `.jfx` archive. Compilation MUST run per exported strategy.

#### Scenario: Export compiles and packages

- GIVEN a strategy exported to `/out/MyStrategy.java`
- WHEN `CompilerPipeline.compile("/out/MyStrategy.java")` runs
- THEN javac from the external JDK compiles the source
- AND a `.jfx` archive is produced next to the source
- AND compile errors return a structured error report

#### Scenario: Missing JDK fails closed

- GIVEN no external JDK configured
- WHEN compile is attempted
- THEN a CompilerConfigError is raised before javac runs
- AND no partial `.jfx` is produced

### Requirement: Error-Fix Loop (REQ-30)

The pipeline MUST route compile failures into a bounded fix loop: the error report feeds a fix attempt (LLM-guided), recompile, and re-validate up to `max_fix_iterations`; exceeding the bound MUST halt with a final error report. Each iteration MUST be logged.

#### Scenario: Fix loop self-corrects

- GIVEN a `.java` failing on a missing import
- WHEN the fix loop runs
- THEN a fix attempt amends the source and recompiles
- AND a `.jfx` is produced within the iteration bound

#### Scenario: Loop bound halts

- GIVEN a `.java` still failing after `max_fix_iterations`
- WHEN the loop exhausts its bound
- THEN the pipeline halts with a CompileError and full error history
- AND the failing source is not deployed

---

# Domain: demo-deploy (NEW)

## ADDED Requirements

### Requirement: Demo Deploy Window (REQ-31)

The system MUST deploy to the Dukascopy demo account and complete within the 14 business-day demo window. Renewal SHALL be semi-manual: a reminder MUST fire before expiry, and re-deploy SHALL require a human gate (`HUMAN_APPROVE_DEMO`, REQ-38).

#### Scenario: Deploy completes inside window

- GIVEN an approved deploy gate and a demo account
- WHEN the demo phase runs
- THEN the strategy is deployed and verified live within 14 business days
- AND a renewal reminder is scheduled before expiry

#### Scenario: Window expiry fails closed

- GIVEN the demo window expired
- WHEN renewal is attempted
- THEN deployment blocks pending HUMAN_APPROVE_DEMO
- AND a renewal reminder is dispatched

### Requirement: JCloud Config and Packaging (REQ-32)

The system MUST package the strategy via DeploymentAgent into a real deployable JAR (replacing the placeholder) and MUST apply JCloud configuration (account, server, symbols). Dry-run MUST produce a mock package without network calls.

#### Scenario: Real packaging

- GIVEN compiled `.jfx` and JCloud config
- WHEN DeploymentAgent packages
- THEN a deployable JAR is produced with the `.jfx` embedded
- AND JCloud config is applied

#### Scenario: Dry-run mock package

- GIVEN DeploymentAgent with dry_run=True
- WHEN packaging runs
- THEN no network call occurs
- AND a mock JAR is produced for inspection

---

# Domain: campaign-archive (NEW)

## ADDED Requirements

### Requirement: Archive and Maintenance Plan (REQ-33)

The system MUST, in the archive phase, produce: (1) a maintenance/replacement plan for the deployed strategy based on live demo performance and Guardian degradation data, (2) account statistics (equity, drawdown, P&L) over the demo window, and (3) an archived artifact bundle. Replacement candidates MUST come from the campaign portfolio.

#### Scenario: Archive produces plan and stats

- GIVEN a completed demo window and Guardian performance data
- WHEN the archive phase runs
- THEN a maintenance/replacement plan is written
- AND account statistics are computed over the demo window
- AND the artifact bundle is stored for audit

#### Scenario: Degraded strategy triggers replacement

- GIVEN Guardian reports the deployed strategy DEGRADING
- WHEN the archive plan is composed
- THEN the plan recommends replacement from the campaign portfolio
- AND the recommendation is human-confirmed before archive

---

# Domain: guardian-feedback (NEW)

## ADDED Requirements

### Requirement: Live Feedback into Generation (REQ-34)

The system MUST feed MetaGuardian live evaluations (degradation, drawdown, regime, cost) into the generation flow: the feedback SHALL inform reconfiguration decisions and next-cycle research inputs, and SHALL be persisted as a feedback record per campaign. Feedback MUST NOT alter the 14-phase flow order (REQ-37) or bypass human gates.

#### Scenario: Live degradation feeds next cycle

- GIVEN MetaGuardian reports a strategy DEGRADING during the demo window
- WHEN the campaign archives
- THEN the feedback record is attached to the campaign archive
- AND next-cycle generation receives the degradation signal as input

#### Scenario: Feedback never bypasses gates

- GIVEN live drawdown data arriving
- WHEN the generation flow consumes it
- THEN all human gates remain in force
- AND flow phase order is unchanged

---

# Domain: mobile-notifications (NEW)

## ADDED Requirements

### Requirement: Mobile Push Channel (REQ-35)

The system MUST provide a mobile push notifier registered in `NotifierDispatcher` alongside console/webhook/email/slack, routing by severity per policy (CRITICAL → push; WARNING → push configurable). Push delivery failures MUST be logged without breaking the alert pipeline.

#### Scenario: CRITICAL alert pushes

- GIVEN the push notifier registered and a CRITICAL alert
- WHEN the dispatcher routes
- THEN the push channel sends the full payload
- AND other configured channels still receive it

#### Scenario: Push failure degrades gracefully

- GIVEN the push provider unreachable
- WHEN an alert fires
- THEN the failure is logged at WARNING
- AND the remaining channels deliver

### Requirement: 24-7 Ops Surface (REQ-36)

The system SHALL support 24-7 monitoring via daemon mode with mobile escalation for Guardian state changes (NORMAL → VIGILANCE → DEFENSIVE → QUARANTINE) and demo window expiry.

#### Scenario: Overnight escalation

- GIVEN the daemon running and a Guardian DEFENSIVE transition at night
- WHEN the transition fires
- THEN a push alert is dispatched with state and reason
- AND the alert is acknowledged via the ops surface

---

# Domain: campaign-orchestration (MODIFIED)

## MODIFIED Requirements

### Requirement: Orchestrated Campaign Loop (REQ-01)

The `quantlab-campaign` subagent MUST own the orchestrated phase loop across the full 14-phase lifecycle: research → hypothesis → SQX config → config review → dispatch → monitor → retest → optimize → portfolio → compile → deploy → demo → archive → live-ops (Guardian watching the demo account). Each phase MUST return the Result Contract envelope (`status`, `executive_summary`, `artifacts`, `next_recommended`, `risks`). The loop MUST NOT stop at optimize; it MUST proceed through deploy, demo, and archive. `quantlab-orchestrator` SHALL remain the router.
(Previously: 8-phase loop halting after optimize with recommendations (D1); no deploy or post-deploy orchestration.)

#### Scenario: Full loop runs all 14 phases

- GIVEN a campaign objective entered in OpenCode chat
- WHEN `quantlab-campaign` runs the loop
- THEN the 14 phases execute in order, each returning the Result Contract envelope
- AND the loop terminates at archive with a maintenance plan and statistics

#### Scenario: Phase failure halts for human

- GIVEN a phase that fails
- WHEN the phase returns its envelope
- THEN the envelope carries `status=failed` and the loop halts awaiting a human decision

## ADDED Requirements

### Requirement: Flow-Integrity Invariant (REQ-37)

The full lifecycle MUST retain all 14 flow phases plus the Guardian live flow, in order, each gated by human confirmation. Simplification MUST apply only to code/infrastructure (shared substrate, consolidated generators); it MUST NOT remove, reorder, merge, or auto-approve any flow phase. Phase count and order MUST be asserted at campaign start and after any harness change.

#### Scenario: Harness change preserves flow

- GIVEN a refactored harness (e.g., substrate rollout)
- WHEN the campaign starts
- THEN the 14 phases plus the Guardian flow are asserted present and in order
- AND each phase blocks on its human gate before proceeding

#### Scenario: Dropped phase fails the assert

- GIVEN a harness missing the archive phase
- WHEN the campaign start assertion runs
- THEN the campaign aborts with a flow-integrity error
- AND no execution begins

---

# Domain: human-gates (MODIFIED)

## ADDED Requirements

### Requirement: Demo-Flow Human Gates (REQ-38)

The pipeline MUST add `HUMAN_APPROVE_DEPLOY`, `HUMAN_APPROVE_DEMO`, and `HUMAN_APPROVE_ARCHIVE` to `HUMAN_GATE_IDS`, mirroring `HUMAN_APPROVE_CONFIG`: in autonomous mode they MUST always block for a human decision (fail-closed); approval proceeds, denial blocks the phase. Each gate MUST be resolvable via the OpenCode `question`-tool callback with stdin fallback.

#### Scenario: Deploy gate blocks autonomously

- GIVEN autonomous mode with HUMAN_APPROVE_DEPLOY pending
- WHEN the gate fires before deploy
- THEN the loop blocks until a human decision arrives
- AND it never auto-approves

#### Scenario: Demo gate blocks before go-live

- GIVEN HUMAN_APPROVE_DEMO pending
- WHEN the demo phase is about to go live
- THEN execution holds pending human approval
- AND denial halts the demo phase

#### Scenario: Archive gate blocks before close

- GIVEN HUMAN_APPROVE_ARCHIVE pending
- WHEN the archive phase completes its plan
- THEN the plan is held for human confirmation
- AND denial returns the campaign to maintenance

#### Scenario: Question-tool resolution

- GIVEN orchestrated mode with a pending demo gate
- WHEN the gate raises
- THEN the choice envelope is presented via the `question` tool
- AND the human decision resolves the gate

---

# Domain: jforex-deploy (MODIFIED)

## ADDED Requirements

### Requirement: Compiled Artifact Deployment (REQ-39)

Beyond `.java` export, the deploy path MUST route exported sources through the compiler pipeline (REQ-29) and package the result as `.jfx`; DeploymentAgent MUST produce a real deployable JAR (replacing the placeholder) for the demo phase (REQ-32). Dry-run SHALL produce mock `.jfx`/JAR without HTTP calls.

#### Scenario: Export then compile to .jfx

- GIVEN a strategy exported as `.java`
- WHEN the deploy path continues
- THEN the compiler pipeline produces a `.jfx`
- AND DeploymentAgent packages a real JAR

#### Scenario: Compile failure blocks deploy

- GIVEN a `.java` that fails compilation
- WHEN the fix loop (REQ-30) exhausts its bound
- THEN deployment is blocked with the compile error
- AND no JAR is produced

---

# Domain: meta-guardian (MODIFIED)

## ADDED Requirements

### Requirement: Live Account Feed (REQ-40)

MetaGuardian MUST evaluate against live demo-account data (equity, positions, costs) streamed by the autonomous monitor (REQ-41) during the demo phase, in addition to backtest-derived signals. Live drawdown/degradation SHALL drive state transitions and feed the Guardian feedback record (REQ-34). Data scope is Dukascopy-only.

#### Scenario: Live drawdown drives DEFENSIVE

- GIVEN a live account stream with drawdown > 10%
- WHEN MetaGuardian evaluates
- THEN the state transitions to DEFENSIVE
- AND the transition is recorded for feedback

#### Scenario: No stream fails closed

- GIVEN the live stream is unavailable
- WHEN MetaGuardian would evaluate live data
- THEN evaluation holds with a STREAM_LOST alert
- AND no live-based state transition occurs

---

# Domain: autonomous-monitor (MODIFIED)

## ADDED Requirements

### Requirement: Live Feed and Feedback Wiring (REQ-41)

The autonomous monitor MUST stream live demo-account equity/positions during the demo phase and deliver the feed to MetaGuardian (REQ-40) and the Guardian feedback record (REQ-34). All existing daemon behaviors (heartbeat, reconnect, alerts) SHALL remain; alert dispatch SHALL also route to the mobile push channel (REQ-35).

#### Scenario: Demo feed streamed

- GIVEN a running demo phase with the daemon active
- WHEN `stream_live(campaign_id)` consumes the account feed
- THEN equity/positions are streamed to MetaGuardian
- AND heartbeat/metrics continue as before

#### Scenario: Alerts reach mobile

- GIVEN a CRITICAL alert during demo
- WHEN the daemon dispatches
- THEN the mobile push channel receives it (REQ-35)
- AND console/webhook still receive it

---

# Domain: campaign-monitor (MODIFIED)

## ADDED Requirements

### Requirement: Substrate-Backed Event Detection (REQ-42)

`CampaignMonitor` MUST run as the event-detection component of the unified execution substrate (REQ-26), parameterized per phase, detecting stalls/config errors across build/retest/optimize/portfolio phases. Existing signals (status text, exported `strategies.csv`, REQ-21) SHALL remain.

#### Scenario: Monitor runs on substrate

- GIVEN the unified flag enabled and a running phase
- WHEN the substrate executes the phase
- THEN event detection runs on the substrate's polling
- AND stall/config events flow as WatcherEvents

#### Scenario: Legacy monitor unchanged

- GIVEN the unified flag disabled
- WHEN dispatch spawns a monitor
- THEN prior standalone behavior is preserved

---

# Domain: retester-automation (MODIFIED)

## ADDED Requirements

### Requirement: Chained Retest Task (REQ-43)

The Retester MUST be invocable as a task within a multi-task Custom Project (REQ-22/REQ-23), allowing retest to run chained with optimize in ONE project load (REQ-27). Standalone `RetesterAutomation` generation/execution SHALL remain unchanged.

#### Scenario: Retest as chained task

- GIVEN a multi-task project declaring Filtering → Retest → Optimize
- WHEN the generator emits the project
- THEN the Retest task XML carries its CrossChecks (Monte Carlo, Walk-Forward)
- AND SQX executes it chained in one load

#### Scenario: Standalone path preserved

- GIVEN RetesterAutomation invoked standalone
- WHEN `run(config, strategy_id, output_dir)` is called
- THEN behavior is identical to pre-change output

---

# Domain: optimizer-automation (MODIFIED)

## ADDED Requirements

### Requirement: Chained Optimize Task (REQ-44)

The Optimizer MUST be invocable as a task within a multi-task Custom Project (REQ-22/REQ-23), chained after retest in ONE project load (REQ-27). Standalone `Optimizer.run` SHALL remain unchanged.

#### Scenario: Optimize as chained task

- GIVEN a multi-task project with Optimize after Retest
- WHEN the generator emits the project
- THEN the Optimize task XML carries parameter ranges and Walk-Forward settings
- AND SQX executes it chained in one load

#### Scenario: Standalone path preserved

- GIVEN Optimizer invoked standalone
- WHEN `run(config)` is called
- THEN behavior is identical to pre-change output
