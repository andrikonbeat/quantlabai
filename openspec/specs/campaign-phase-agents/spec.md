# Campaign Phase Agents Specification

## Purpose

Agent family for per-phase LLM delegation: 14 literal phase agents with focused roles, bounded authority, deny-first permissions, repo-canonical prompts, sync, and parity.

## Requirements

### Requirement: Per-Phase Agent Registration (REQ-805)

The system MUST register 14 literal phase subagents — one per phase of `PHASES` (research, hypothesis, config, config-review, dispatch, monitor, retest, optimize, portfolio, compile, deploy, demo, archive, live-ops). Judgment-heavy phases (research, hypothesis, config-review, retest, optimize, portfolio) MUST have full role prompts; mechanical phases (dispatch, compile, demo) MUST have thin prompts. No family grouping is permitted; each phase MUST map to exactly one agent.

#### Scenario: All 14 phases have agents

- GIVEN the orchestration surface registration
- WHEN the phase registry is enumerated
- THEN 14 agents exist, one per canonical phase id
- AND each agent declares the phase it owns

#### Scenario: Unmapped phase fails registration

- GIVEN a registration missing an agent for the archive phase
- WHEN the registry validates
- THEN registration fails
- AND the missing phase is reported

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

### Requirement: Prompt Parity Test (REQ-807)

A parity test MUST assert byte-equality between every repo prompt under `AI/opencode/agents/` and its live generated counterpart. A mismatch MUST fail the test and identify the drifted file.

#### Scenario: Parity holds

- GIVEN synced prompts
- WHEN the parity test runs
- THEN all repo ⇄ live pairs are byte-equal

#### Scenario: Drift detected

- GIVEN a live prompt that was regenerated or altered
- WHEN the parity test runs
- THEN the test fails
- AND the drifted file path is reported

### Requirement: Deny-First Permissions (REQ-808)

Each phase agent MUST be configured with a deny-first permission allowlist matching the `quantlab-campaign`/`quantlab-guardian` pattern: `question: allow`, `task` restricted to `quantlab-*`, all other tools denied unless explicitly allowed. Agents MUST NOT mutate `flow.py`, skip gates, or reach the live trading surface unless their phase grants it.

#### Scenario: Out-of-scope tool denied

- GIVEN a compile-phase agent invoking a deploy tool
- WHEN the permission check runs
- THEN the action is denied
- AND no execution occurs

#### Scenario: Gate question allowed

- GIVEN a phase agent at a human gate
- WHEN it presents the gate via the question tool
- THEN the question is allowed
- AND the flow blocks until a decision arrives

### Requirement: Orchestrator-Shell Long Operations (REQ-809)

No phase subagent MAY wait on a long-running operation (research, optimize, retest, deploy, demo waits). Phase agents MUST return runnable scripts in their `PhaseResult`; the orchestrator MUST execute them in its own shell with log polling and MUST cancel via task-cancel. A subagent that attempts to wait MUST be cancelled.

#### Scenario: Long op handed to orchestrator

- GIVEN an optimize phase requiring a long backtest run
- WHEN the phase agent completes its work
- THEN the agent returns a runnable script in the envelope
- AND the orchestrator executes it in its own shell

#### Scenario: Waiting agent is cancelled

- GIVEN a phase agent that blocks on a long operation
- WHEN the orchestrator detects the wait
- THEN the agent is cancelled via task-cancel
- AND the operation continues on the orchestrator shell

### Requirement: Test Coupling (REQ-810)

Existing campaign tests MUST keep passing: `assert_flow`/`assert_flow_segments`, the exact-path assertions in `tests/test_orchestrator_prompt.py`, and mock-vs-real behavior gated by `SQX_FORCE_MOCK` MUST remain intact. New per-phase assertions MUST extend, not replace, these tests.

#### Scenario: Existing asserts pass

- GIVEN the delegation layer and phase agents in place
- WHEN the campaign test suite runs
- THEN all pre-existing flow and prompt assertions pass unchanged
- AND SQX_FORCE_MOCK paths still mock

#### Scenario: Mock-vs-real preserved

- GIVEN SQX_FORCE_MOCK set
- WHEN a dispatch-phase test runs
- THEN the mock path executes without real sqcli calls

### Requirement: Prompt Reasoning Enrichment (REQ-819)

All 14 phase prompts MUST carry real LLM reasoning over the mapped SDK classes; `edit:false, write:false` SHALL remain. Reasoning-heavy phases MUST map to their SDK class and expose its reasoning in the prompt:

| Phase | SDK class | Prompt reasoning |
|-------|-----------|----------------|
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