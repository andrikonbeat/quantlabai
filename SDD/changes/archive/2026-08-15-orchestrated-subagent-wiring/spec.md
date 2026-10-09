# Delta for orchestrated-subagent-wiring

## campaign-phase-delegation (Modified)

### MODIFIED Requirements

### Requirement: execute_phase Glue (REQ-803)

The system MUST provide `execute_phase()` glue in `sdk/quantlab/campaign/delegation.py` that maps a `PhaseDirective` to the registered phase executor, enforces the agent's bounded authority, and returns a `PhaseResult`. The glue MUST NOT run long-running operations inline; it MUST hand back runnable scripts for orchestrator-shell execution. When no executor is registered, the glue MUST deny-first: without `SQX_FORCE_MOCK=1` it SHALL raise `AuthorityViolationError`; with `SQX_FORCE_MOCK=1` it SHALL fall back to the mock executor.
(Previously: no production executor existed — a missing executor always raised `AuthorityViolationError`; scope-check was the only gate.)

#### Scenario: Glue enforces authority

- GIVEN a directive whose executor attempts an out-of-scope action
- WHEN `execute_phase()` runs
- THEN the action is rejected
- AND the result carries an authority violation

#### Scenario: Long-running op returns script

- GIVEN a dispatch-phase directive requiring a long sqcli run
- WHEN `execute_phase()` handles it
- THEN a runnable script is returned in the result for the orchestrator shell
- AND the glue does not wait on completion

#### Scenario: Production executor present

- GIVEN a production executor registered for the research phase
- WHEN `execute_phase()` runs without `SQX_FORCE_MOCK`
- THEN the executor runs the SDK stage
- AND a validated `PhaseResult` is returned

### ADDED Requirements

### Requirement: Production Executor Protocol (REQ-815)

`execute_phase()` MUST gain a registered production executor for every phase of `PHASES`. Each executor SHALL resolve its SDK stage from `STAGE_FOR_PHASE` in `sdk/quantlab/campaign/flow.py`, run that stage, and return a validated `PhaseResult` (REQ-802). An executor SHALL reject out-of-scope actions before execution (deny-first, REQ-803). The mock path under `SQX_FORCE_MOCK=1` MUST remain intact (REQ-810).

#### Scenario: Stage resolved per phase

- GIVEN a directive for the archive phase
- WHEN its production executor runs
- THEN it resolves the `archive` stage from `STAGE_FOR_PHASE`
- AND the stage executes and yields a `PhaseResult` with `phase_id=archive`

#### Scenario: Executor gap fails closed

- GIVEN a phase whose executor is not registered
- WHEN `execute_phase()` runs without `SQX_FORCE_MOCK`
- THEN `AuthorityViolationError` is raised
- AND no SDK stage executes

### Requirement: Hybrid Delegation Split (REQ-816)

Reasoning-heavy phases (research, hypothesis, config, review, portfolio, optimize, archive) MUST run as LLM subagent phases. Mechanical/long phases (dispatch, monitor, compile, deploy, demo) MUST return a `LongOpSpec` handoff for orchestrator-shell execution; no subagent MAY wait on them (REQ-809). `retest` SHALL hand off via `LongOpSpec` when the retest run is long; `live-ops` SHALL delegate to the guardian surface.

#### Scenario: Reasoning phase runs as subagent

- GIVEN an optimize directive
- WHEN the phase dispatches
- THEN it runs as an LLM subagent producing recommendation reasoning
- AND returns a `PhaseResult` without a `handoff_payload`

#### Scenario: Mechanical phase hands off

- GIVEN a dispatch directive
- WHEN the phase dispatches
- THEN it returns a `LongOpSpec` in `handoff_payload`
- AND the orchestrator executes it in its own shell

### Requirement: Legacy Runner Retirement (REQ-817)

The script `_run_campaign.py` (legacy entry point building `orchestrated=False`) SHALL be retired in favor of the CLI `campaign run-flow` (REQ-37). Its removal SHALL be documented as a migration: any reference to `_run_campaign.py` in docs or harnesses SHALL point to `campaign run-flow`; `cmd_campaign_run_flow` in `sdk/quantlab/cli/campaign_commands.py` SHALL remain the only real campaign entry point.

#### Scenario: Retired script absent

- GIVEN the change applied
- WHEN the repo is inspected
- THEN `_run_campaign.py` no longer exists
- AND `campaign run-flow` remains available

#### Scenario: Migration documented

- GIVEN a doc or harness referencing `_run_campaign.py`
- WHEN the migration sweep runs
- THEN the reference points to `campaign run-flow`
- AND the legacy `orchestrated=False` build is no longer the campaign entry

## phase-runner (New)

### Requirement: phase_runner CLI (REQ-818)

The system MUST provide a `phase_runner` CLI under `sdk/quantlab/campaign/` that bridges a `PhaseDirective` to its production executor (REQ-815) and returns a validated `PhaseResult`. The CLI SHALL accept `--phase` and `--directive <json>`, enforce REQ-803 scope deny-first, and emit the envelope as JSON. Long-op handoff SHALL target `/tmp/opencode` with `timeout >= 240`, a cleanup command, and a per-phase report.

#### Scenario: Runner executes a phase

- GIVEN `phase_runner` invoked with `--phase research --directive <json>`
- WHEN the executor runs
- THEN a validated `PhaseResult` is emitted as JSON
- AND the phase id matches the directive

#### Scenario: Out-of-scope directive rejected

- GIVEN a directive whose scope contains a forbidden action
- WHEN `phase_runner` validates it
- THEN execution is rejected with an authority error
- AND no SDK stage runs

#### Scenario: Handoff script under /tmp/opencode

- GIVEN a mechanical phase returning a `LongOpSpec`
- WHEN the runner emits the handoff
- THEN `log_path` is under `/tmp/opencode`, `timeout >= 240`, and `cleanup` is set
- AND the per-phase report records the handoff

## campaign-phase-agents (Modified)

### MODIFIED Requirements

### Requirement: Repo-Canonical Prompt Source (REQ-806)

The repo directory `AI/opencode/agents/` MUST be the single source of truth for the campaign prompt, all phase prompts, and the `guardian-orchestrator.md` prompt. The live `~/.config/opencode/prompts/quantlab/` copies MUST be generated from it by a sync script; hand-editing live prompts is not permitted. The sync MUST merge the existing guardian delegation into the repo canonical copy.
(Previously: the allowlist covered only `campaign.md` and `phase-*.md`; `guardian-orchestrator.md` was not a managed prompt.)

#### Scenario: Sync propagates to live

- GIVEN an edited repo campaign.md
- WHEN the sync script runs
- THEN the live copy matches the repo bytes
- AND the guardian delegation drift is resolved in the repo canonical copy

#### Scenario: Live prompt never hand-edited

- GIVEN a live prompt that differs from repo canonical
- WHEN the parity check runs
- THEN the difference is attributed to a sync miss, not a manual edit
- AND the sync script is the only update path

#### Scenario: guardian-orchestrator.md is managed

- GIVEN a repo edit to `guardian-orchestrator.md`
- WHEN the sync script runs
- THEN the live copy matches the repo bytes
- AND `guardian.md` / `orchestrator.md` stay non-managed

### ADDED Requirements

### Requirement: Prompt Reasoning Enrichment (REQ-819)

All 14 phase prompts MUST carry real LLM reasoning over the mapped SDK classes; `edit:false, write:false` SHALL remain. Reasoning-heavy phases MUST map to their SDK class and expose its reasoning in the prompt:

| Phase | SDK class | Prompt reasoning |
|-------|-----------|------------------|
| research | `LLMResearchAgent` | KB rationale (REQ-203/204/205) |
| hypothesis | `hypothesis_builder/llm.py` | hypothesis generation rationale |
| config | `BuildConfig`/`BuilderAgent` | KB teaching-table rationale |
| review | `ConfigReviewStage`/`ConfigReviewer` | verdict (APPROVE/MODIFY/BLOCK) + `proposed_changes` |
| monitor | `CampaignMonitor`/`LLMGenerationMonitor` | stall diagnosis |
| optimize | `OptimizerStage` | recommendation reasoning |
| portfolio | `PortfolioComposer` | composition reasoning |
| archive | `ArchivePhase` | maintenance-plan reasoning |

Remaining phases (dispatch, retest, compile, deploy, demo, live-ops) SHALL carry accurate, grounded instructions, with LLM reasoning where it adds value.

#### Scenario: Reasoning prompt maps to class

- GIVEN the research phase prompt
- WHEN an LLM subagent runs it
- THEN it reasons over `LLMResearchAgent` with KB rationale
- AND returns the verdict-shaped evidence

#### Scenario: Grounded prompt for mechanical phase

- GIVEN the compile phase prompt
- WHEN an LLM subagent runs it
- THEN it carries grounded compile instructions
- AND returns a `PhaseResult` without fabricating stage output

#### Scenario: All 14 prompts enriched

- GIVEN the enriched prompt set
- WHEN a parity/coverage check runs
- THEN all 14 phase prompts carry mapped reasoning or grounded instructions
- AND the check passes

### Requirement: D3 Artifact-Write Boundary (REQ-820)

Phase agents MUST NOT write artifacts (`edit:false, write:false`); the SDK stages (via `phase_runner`/`execute_phase`) SHALL write artifacts (D3 auto-apply forbidden). Where the config phase must produce a file, the `phase_runner`/SDK writes it, never the agent.

#### Scenario: Agent never writes artifacts

- GIVEN a config-phase agent holding a produced config
- WHEN it completes its turn
- THEN the agent returns the artifact key in the envelope
- AND the SDK stage writes the file

### Requirement: Sync Contract Test Update (REQ-821)

`tests/campaign/test_prompt_sync.py` SHALL be updated in this change: `test_guardian_live_prompt_never_synced` is a deliberate contract change — `guardian-orchestrator.md` becomes a managed prompt (REQ-806), while `guardian.md` and `orchestrator.md` remain non-managed and MUST NOT be written or deleted by the sync script. Tests SHALL assert the new boundary.

#### Scenario: Allowlist extends

- GIVEN the updated sync script
- WHEN `managed_prompt_names()` runs
- THEN it includes `guardian-orchestrator.md`
- AND the updated test asserts `guardian.md`/`orchestrator.md` are untouched

#### Scenario: Parity test updated in same change

- GIVEN the allowlist change
- WHEN the test suite runs
- THEN the updated sync tests pass
- AND no stale non-managed assertion fails

## guardian-orchestrator (New)

### Requirement: Second First-Class Orchestrator Registration (REQ-822)

The system MUST define `guardian-orchestrator` as a first-class OpenCode agent: prompt versioned in repo (`ai/opencode/agents/guardian-orchestrator.md`), opencode.json entry with `mode: primary`, visible, and deny-first permissions mirroring `quantlab-orchestrator` safety (bash `*: deny` + allowlist, task `*: deny` + `quantlab-*` allow, question allow). It owns its own routing, gates, and delegates; it is NOT a phase inside `quantlab-orchestrator` (PRD G9).

#### Scenario: Agent registered and visible

- GIVEN the updated opencode.json
- WHEN the agent set loads
- THEN `guardian-orchestrator` is present with `mode: primary`
- AND its deny-first permissions mirror `quantlab-orchestrator`

#### Scenario: Not a pipeline phase

- GIVEN the guardian-orchestrator registration
- WHEN `assert_flow` runs
- THEN `PHASES` remains 14
- AND no flow stage is added

### Requirement: GUARDIAN-LIVE Routing Decision (REQ-823)

GUARDIAN-LIVE intents MUST route to `guardian-orchestrator`. Decision (documented from exploration): PRD G9/D10 requires disjoint lifecycles for the two orchestrators, but there is one interactive session — so `quantlab-orchestrator`'s live routing table (`orchestrator.md`, non-managed) SHALL delegate GUARDIAN-LIVE intents to `guardian-orchestrator` via `task`, mirroring how SDD intents route to `gentle-orchestrator`. `guardian-orchestrator` SHALL handle the intent with its own routing.

#### Scenario: GUARDIAN-LIVE intent delegates

- GIVEN a GUARDIAN-LIVE intent in the interactive session
- WHEN `quantlab-orchestrator` routes it
- THEN it delegates via `task` to `guardian-orchestrator`
- AND no other agent receives it

#### Scenario: Disjoint lifecycles preserved

- GIVEN both orchestrators active
- WHEN a live-ops event arrives
- THEN `guardian-orchestrator` handles it on its own cadence
- AND the campaign loop is not reordered or interrupted (REQ-37)

### Requirement: HUMAN_APPROVE_REPLACEMENT Live Gate (REQ-824)

The system MUST implement a `HUMAN_APPROVE_REPLACEMENT` live gate with REQ-11 fail-closed semantics (D10/D11): it is the ONLY path that changes a live position; the system MUST NEVER auto-replace a strategy. A HOLD, missing, or non-approved decision SHALL block the replacement; `guardian-orchestrator` SHALL present the gate via the decision-file protocol and MUST NOT execute without approval.

#### Scenario: Replacement waits for human

- GIVEN a degrading strategy with a replacement candidate
- WHEN `HUMAN_APPROVE_REPLACEMENT` fires
- THEN the replacement is held pending a human decision
- AND no live position changes

#### Scenario: Non-approval fails closed

- GIVEN a HOLD decision on `HUMAN_APPROVE_REPLACEMENT`
- WHEN the gate resolves
- THEN the replacement is blocked
- AND the strategy is not replaced

### Requirement: Guardian Orchestrator Delegates (REQ-825)

`guardian-orchestrator` MUST delegate via `task` to `quantlab-guardian` (live-ops monitoring/evaluation), `quantlab-guardian-alert` (alert synthesis/notification), and `quantlab-replacement` (replacement candidate selection from portfolio + reviewer evidence). Each delegate SHALL return the Result Contract envelope; `guardian-orchestrator` SHALL synthesize the results.

#### Scenario: Monitoring delegates

- GIVEN a live-ops monitoring intent
- WHEN `guardian-orchestrator` routes it
- THEN it delegates to `quantlab-guardian`
- AND synthesizes the returned envelope

#### Scenario: Replacement selection delegates

- GIVEN a replacement-recommendation intent
- WHEN `guardian-orchestrator` routes it
- THEN it delegates to `quantlab-replacement`
- AND the candidate evidence is returned for the human gate (REQ-824)

## guardian-agent (Modified)

### MODIFIED Requirements

### Requirement: GUARDIAN Intent Routing (REQ-642)

Both orchestrators MUST route guardian intents (directives, live-ops status, feedback) to `quantlab-guardian` through a GUARDIAN route in their routing tables. Non-guardian intents MUST NOT be dispatched to the agent.
(Previously: only `quantlab-orchestrator` held the GUARDIAN route.)

#### Scenario: Directives route to guardian

- GIVEN the routing table of either orchestrator contains the GUARDIAN route
- WHEN a guardian directive arrives
- THEN it is dispatched to `quantlab-guardian`
- AND no other agent receives it

#### Scenario: Unknown intent stays with orchestrator

- GIVEN an intent that is not guardian-related
- WHEN the routing table evaluates it
- THEN it does not match the GUARDIAN route
- AND the owning orchestrator handles it

#### Scenario: guardian-orchestrator routes to quantlab-guardian

- GIVEN a live-ops evaluation intent routed to `guardian-orchestrator`
- WHEN it dispatches
- THEN it delegates to `quantlab-guardian` via `task`
- AND the `GuardianReport` envelope returns (REQ-644)
