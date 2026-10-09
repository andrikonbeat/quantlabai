# Campaign Phase Delegation Specification

## Purpose

SDK contract for per-phase LLM sub-agent delegation: `PhaseDirective` handoffs, `PhaseResult` envelopes, and `execute_phase()` glue that enforces bounded authority without mutating the flow constant.

## Requirements

### Requirement: Phase Directives (REQ-801)

A phase dispatch MUST be expressed as a `PhaseDirective` carrying the phase id, the bounded scope, the directive payload, and a reference to the preceding `PhaseResult`. Directives MUST reference only the 14 canonical phase ids from `PHASES` (REQ-37).

#### Scenario: Directive carries phase and payload

- GIVEN an orchestrator about to dispatch the research phase
- WHEN a `PhaseDirective` is built
- THEN it carries the phase id, bounded scope, and directive payload
- AND it references the preceding `PhaseResult`

#### Scenario: Unknown phase id rejected

- GIVEN a directive whose phase id is not in `PHASES`
- WHEN the delegation layer validates it
- THEN validation fails with a phase-not-found error
- AND no dispatch occurs

### Requirement: PhaseResult Envelope (REQ-802)

Each phase agent MUST return a `PhaseResult` envelope reusing the Result Contract fields (`status`, `executive_summary`, `artifacts`, `next_recommended`, `risks`) plus `phase_id`, `evidence`, and `handoff_payload`. A `status` other than `success` MUST halt folding until a human decision arrives.

#### Scenario: Success envelope folds

- GIVEN a phase that completed successfully
- WHEN its `PhaseResult` is returned
- THEN the orchestrator folds it into the campaign context
- AND the next phase directive is built from it

#### Scenario: Failed envelope halts

- GIVEN a phase returning `status=failed`
- WHEN the orchestrator receives the envelope
- THEN folding halts awaiting a human decision
- AND no further phase is dispatched

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

### Requirement: Wrap-Only Flow Invariant (REQ-804)

The delegation layer MUST wrap and delegate above the existing `PHASES` tuple and above `sdk/quantlab/agents/`; it MUST NOT mutate, reorder, rename, or remove any entry of `PHASES` in `sdk/quantlab/campaign/flow.py` (REQ-37). An integrity test MUST assert the flow constant is unchanged after this change lands.

#### Scenario: PHASES unchanged

- GIVEN the delegation layer in place
- WHEN `assert_flow` and `assert_flow_segments` run
- THEN both pass against the same 14-phase tuple
- AND the integrity test confirms flow.py untouched

#### Scenario: Mutation attempt detected

- GIVEN an accidental edit to flow.py that drops a phase
- WHEN the integrity test runs
- THEN it fails with a flow-integrity error
- AND no delegation proceeds

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

## ADDED Requirements

### Requirement: Stage Artifact Persistence (REQ-819)

The delegation layer MUST persist every artifact key claimed in `PhaseResult.artifacts` to the Knowledge Lake. `_run_sdk_stage` SHALL call `save_phase_envelope` (knowledge/store.py:638) for each completed stage, writing `campaign-phases/{campaign_id}/{phase}/envelope.json` with status, timestamps, artifacts, and next gate. A stage MUST NOT claim an artifact key it did not persist.

#### Scenario: Stage artifacts persisted

- GIVEN a completed research stage returning an artifacts list
- WHEN `execute_phase()` returns the `PhaseResult`
- THEN `campaign-phases/{campaign_id}/research/envelope.json` exists
- AND each artifact key resolves to a real file

#### Scenario: Missing knowledge_root degrades, does not crash

- GIVEN a directive payload without `knowledge_root`
- WHEN the stage completes
- THEN the result records the gap in `risks`
- AND no artifact is claimed as persisted

#### Scenario: Failed stage still leaves an envelope

- GIVEN a retest stage that fails with an SQX error
- WHEN the envelope is written
- THEN `envelope.json` carries failed status and lists the error log
- AND the next gate is HOLD