# OpenCode Harness Elevation — Spec Artifact

## Domain: campaign-phase-agents

### MODIFIED Requirements

#### Requirement: Repo-Canonical Prompt Source (REQ-806)

The repo directory `AI/opencode/agents/` MUST be the single source of truth for the campaign prompt, all phase prompts, `orchestrator.md`, and `guardian-orchestrator.md`. The live `~/.config/opencode/prompts/quantlab/` copies MUST be generated from it by a sync script; hand-editing live prompts is not permitted. The sync MUST merge the existing guardian delegation into the repo canonical copy. `deploy.md` and `monitor.md` are retired from live and versioned as legacy in repo only.
(Previously: the allowlist covered only `campaign.md`, `phase-*.md`, and `guardian-orchestrator.md`; `orchestrator.md` was not managed, and `deploy.md`/`monitor.md` were live orphans.)

#### Scenario: orchestrator.md syncs
- GIVEN a repo edit to `orchestrator.md`
- WHEN the sync script runs
- THEN the live copy matches the repo bytes

#### Scenario: deploy.md/monitor.md retired
- GIVEN live copies of `deploy.md`/`monitor.md`
- WHEN the sync script runs
- THEN those files are removed from live
- AND the repo retains versioned legacy copies

#### Scenario: guardian-orchestrator.md still managed
- GIVEN a repo edit to `guardian-orchestrator.md`
- WHEN the sync script runs
- THEN the live copy matches the repo bytes
- AND `guardian.md` remains non-managed

#### Requirement: Prompt Parity Test (REQ-807)

A parity test MUST assert byte-equality between every repo prompt under `AI/opencode/agents/` and its live generated counterpart. A mismatch MUST fail the test and identify the drifted file.

#### Scenario: Parity holds after allowlist change
- GIVEN the extended allowlist
- WHEN the parity test runs
- THEN all repo ⇄ live pairs are byte-equal
- AND retired files are absent from live

#### Scenario: Drift detected
- GIVEN a live prompt altered outside sync
- WHEN the parity test runs
- THEN the test fails with the drifted file path

#### Requirement: Test Coupling (REQ-810)

Existing campaign tests MUST keep passing: `assert_flow`/`assert_flow_segments`, exact-path assertions in `tests/test_orchestrator_prompt.py`, and `SQX_FORCE_MOCK` gating. New per-phase assertions MUST extend, not replace. Allowlist flips MUST be reflected in the same change's tests.

#### Scenario: Flipped allowlist tests pass
- GIVEN the updated allowlist including `orchestrator.md` and excluding `deploy.md`/`monitor.md`
- WHEN `test_prompt_sync.py` runs
- THEN the updated sync tests pass
- AND no stale non-managed assertion fails

#### Requirement: Sync Contract Test Update (REQ-821)

`tests/campaign/test_prompt_sync.py` MUST assert the new boundary: `orchestrator.md` becomes managed; `guardian.md` (non-managed) MUST NOT be written or deleted by the sync script.
(Previously: `guardian-orchestrator.md` became managed; `guardian.md`/`orchestrator.md` were not explicitly bounded.)

#### Scenario: Allowlist boundary asserted
- GIVEN the sync script allowlist
- WHEN `test_prompt_sync.py` runs
- THEN `orchestrator.md` is included in managed set
- AND `guardian.md` is asserted untouched

#### Scenario: Parity test updated in same change
- GIVEN the allowlist change
- WHEN the test suite runs
- THEN the updated sync tests pass
- AND no stale assertion fails

### ADDED Requirements

#### Requirement: Skills Sync Discipline (REQ-822)

A sibling `sync_skills.py` MUST sync `ai/opencode/skills/` → `~/.config/opencode/skills/` with the same discipline as prompt sync: deterministic, idempotent, allowlist-based, `--dry-run`/`--check` modes, and repo-wins policy. Live hand-editing of synced skills is prohibited.

#### Scenario: Skills sync mirrors prompt sync
- GIVEN a repo skill edit under `ai/opencode/skills/`
- WHEN `sync_skills.py --check` runs
- THEN it reports drift if live differs from repo
- AND `sync_skills.py` would overwrite live with repo bytes

#### Scenario: Dry-run is safe
- GIVEN a repo skill edit
- WHEN `sync_skills.py --dry-run` runs
- THEN no live file is modified
- AND the report shows what would change

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | `orchestrator.md` appears in managed prompt allowlist |
| 2 | `deploy.md`/`monitor.md` absent from live after sync |
| 3 | `guardian.md` untouched by sync |
| 4 | Parity test passes with extended allowlist |
| 5 | `sync_skills.py` exists with `--check`/`--dry-run` and allowlist |

## Affected Files

| File | Change |
|------|--------|
| `ai/opencode/sync_prompts.py` | Allowlist add `orchestrator.md`; remove `deploy.md`/`monitor.md` |
| `ai/opencode/sync_skills.py` | New sibling sync script |
| `tests/campaign/test_prompt_sync.py` | Flip allowlist/parity tests; add skills-sync tests |
| `ai/opencode/agents/orchestrator.md` | New versioned router prompt |
| `ai/opencode/agents/deploy.md` | Retired to repo legacy |
| `ai/opencode/agents/monitor.md` | Retired to repo legacy |

---

## Domain: campaign-orchestrator

### MODIFIED Requirements

#### Requirement: Orchestrated Campaign Loop (REQ-01)

The `quantlab-campaign` subagent MUST own the orchestrated phase loop across the full 14-phase lifecycle. Each phase MUST be delegated to its dedicated per-phase subagent. A post-phase gatekeeper MUST validate the `PhaseResult` envelope for contract conformance, artifact read-back, no-hallucination, no-input-drift, and routing coherence before the next phase. The gatekeeper MUST allow exactly one corrective re-run per failed phase, then stop and report. `quantlab-orchestrator` SHALL remain the router.
(Previously: the campaign subagent delegated phases but had no post-phase gatekeeper loop.)

#### Scenario: Gatekeeper validates envelope
- GIVEN a phase returning a `PhaseResult`
- WHEN the post-phase gatekeeper runs
- THEN it validates contract conformance, artifact read-back, no-hallucination, no-input-drift, and routing coherence
- AND only then dispatches the next phase

#### Scenario: Exactly-once corrective re-run
- GIVEN a phase that fails validation on first attempt
- WHEN the gatekeeper re-runs it
- THEN the phase executes exactly once more
- AND if it fails again, the loop stops and reports

#### Requirement: Flow-Integrity Invariant (REQ-37)

The full lifecycle MUST retain all 14 flow phases plus the Guardian live flow, in order, each gated by human confirmation. Simplification MUST apply only to code/infrastructure; it MUST NOT remove, reorder, merge, or auto-approve any flow phase. Phase count and order MUST be asserted at campaign start, at CLI run-flow start, and after any harness change.
(Previously: preflight was restored but the assertion timing was not fully explicit across all entry points.)

#### Scenario: Preflight runs after harness change
- GIVEN a harness change (e.g., sync extension)
- WHEN the campaign starts
- THEN the REQ-37 invariant is asserted
- AND a broken pipeline aborts with a flow-integrity error and non-zero exit

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | Post-phase gatekeeper validates `PhaseResult` envelope before next phase |
| 2 | Gatekeeper allows exactly one corrective re-run, then stops |
| 3 | REQ-37 asserted at campaign start, CLI run-flow start, and after harness change |
| 4 | 14 phases plus Guardian flow retained in order |

## Affected Files

| File | Change |
|------|--------|
| `ai/opencode/agents/campaign.md` | Gatekeeper loop; lossless gate protocol; canonical contract |
| `ai/opencode/skills/quantlab-run-campaign/SKILL.md` | Restore preflight parity; dedupe to pointer |

---

## Domain: human-gates

### MODIFIED Requirements

#### Requirement: Demo-Flow Human Gates (REQ-38)

The pipeline MUST add `HUMAN_APPROVE_DEPLOY`, `HUMAN_APPROVE_DEMO`, and `HUMAN_APPROVE_ARCHIVE` to `HUMAN_GATE_IDS`. Each gate MUST present a complete envelope, accept exactly one answer, and re-present with STOP if the answer is missing or invalid.
(Previously: gates were presented without explicit lossless discipline.)

#### Scenario: Exact-one answer required
- GIVEN a human gate presenting its envelope
- WHEN the user provides multiple answers
- THEN the gate re-presents the complete envelope
- AND stops until a single valid answer is given

#### Scenario: Missing answer re-presents
- GIVEN a gate with no decision
- WHEN the timeout expires
- THEN the gate re-presents the complete envelope
- AND blocks until a decision arrives

#### Scenario: Invalid answer halts
- GIVEN a gate receiving an unrecognized response
- WHEN the validation runs
- THEN the gate re-presents the envelope
- AND stops without proceeding

### ADDED Requirements

#### Requirement: Blocking-Prompt Discipline (REQ-11)

All human gates MUST use lossless blocking-prompt discipline: present the complete envelope, accept exactly one answer, and re-present + STOP on missing or invalid input. Auto-approval is prohibited.

#### Scenario: Complete envelope always presented
- GIVEN any human gate
- WHEN the gate fires
- THEN the complete envelope (context, options, consequences) is presented
- AND the flow blocks until resolution

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | All gates present complete envelope |
| 2 | Multiple answers trigger re-present + STOP |
| 3 | Missing/invalid answers trigger re-present + STOP |
| 4 | Auto-approval is impossible |

## Affected Files

| File | Change |
|------|--------|
| `ai/opencode/agents/campaign.md` | Lossless gate protocol |
| `ai/opencode/agents/phase-*.md` (15) | Lossless gate sections |
| `ai/opencode/agents/guardian-orchestrator.md` | Lossless replacement gate |

---

## Domain: guardian-orchestrator

### MODIFIED Requirements

#### Requirement: HUMAN_APPROVE_REPLACEMENT Live Gate (REQ-824)

The system MUST implement a `HUMAN_APPROVE_REPLACEMENT` live gate with fail-closed semantics. It is the ONLY path that changes a live position; the system MUST NEVER auto-replace. The gate MUST present a complete envelope, accept exactly one answer, and re-present + STOP on missing or invalid input.
(Previously: the gate used fail-closed semantics but did not enforce lossless blocking-prompt discipline.)

#### Scenario: Exact-one answer required
- GIVEN `HUMAN_APPROVE_REPLACEMENT` firing
- WHEN the human provides multiple or invalid answers
- THEN the gate re-presents the complete envelope
- AND blocks until a single valid answer is given

#### Scenario: Non-approval fails closed
- GIVEN a HOLD decision on `HUMAN_APPROVE_REPLACEMENT`
- WHEN the gate resolves
- THEN the replacement is blocked
- AND the strategy is not replaced

#### Scenario: Invalid answer halts
- GIVEN a gate receiving an unrecognized response
- WHEN the validation runs
- THEN the gate re-presents the envelope
- AND stops without proceeding

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | `HUMAN_APPROVE_REPLACEMENT` is the only path to change a live position |
| 2 | Gate presents complete envelope with exact-one answer discipline |
| 3 | Missing/invalid input triggers re-present + STOP |
| 4 | Non-approval fails closed |

## Affected Files

| File | Change |
|------|--------|
| `ai/opencode/agents/guardian-orchestrator.md` | Lossless replacement gate |

---

## Domain: skill-registry (NEW)

### Requirement: Skills Sync Contract (REQ-901)

The system MUST provide a `sync_skills.py` that syncs `ai/opencode/skills/` → `~/.config/opencode/skills/` with repo-wins policy. Sync MUST be deterministic and idempotent, MUST use an explicit allowlist, MUST support `--dry-run` and `--check` modes, and MUST refresh the skill registry after sync. Live hand-editing of synced skills is prohibited.

#### Scenario: Repo-wins overwrites live
- GIVEN a live skill that differs from repo
- WHEN sync runs
- THEN the live copy is replaced with repo bytes

#### Scenario: --check reports drift without modifying
- GIVEN drifted live skills
- WHEN `sync_skills.py --check` runs
- THEN drift is reported
- AND no live file is modified

#### Scenario: Allowlist limits sync scope
- GIVEN an allowlist containing only `quantlab-*` skills
- WHEN sync runs
- THEN only matching skills are synced
- AND others are untouched

#### Scenario: Dry-run is safe
- GIVEN a repo skill edit
- WHEN `sync_skills.py --dry-run` runs
- THEN no live file is modified
- AND the report shows what would change

#### Scenario: Registry refresh order
- GIVEN a successful sync
- WHEN the registry refresh runs
- THEN the skill index reflects the synced state
- AND no stale entries remain

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | `sync_skills.py --check` reports drift without modifying |
| 2 | `sync_skills.py --dry-run` reports changes without modifying |
| 3 | Allowlist limits sync scope |
| 4 | Registry refresh follows sync |

## Affected Files

| File | Change |
|------|--------|
| `ai/opencode/sync_skills.py` | New deterministic idempotent sync |
| `ai/opencode/skills/quantlab-run-campaign/SKILL.md` | Deduped to pointer |
| `ai/opencode/skills/quantlab-deploy-strategy/SKILL.md` | New LLM-first rewrite |
| `ai/opencode/skills/quantlab-monitor-status/SKILL.md` | New LLM-first rewrite |

---

## Domain: project-agents (NEW)

### Requirement: Repo-Root AGENTS.md Contract (REQ-902)

The repo MUST contain a root `AGENTS.md` defining the project stack, testing conventions, harness conventions, and OpenSpec workflow. It SHALL be the single source of truth for agent onboarding. All QuantLab agents SHALL reference it at session start.

#### Scenario: New agent reads AGENTS.md
- GIVEN a new agent joining the project
- WHEN it reads `AGENTS.md`
- THEN it finds stack, testing, conventions, and workflow
- AND can start contributing without additional context

#### Scenario: Agent validates against AGENTS.md
- GIVEN an agent about to execute a task
- WHEN it checks `AGENTS.md` for conventions
- THEN the conventions are current
- AND the agent follows the documented workflow

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | `AGENTS.md` exists at repo root |
| 2 | `AGENTS.md` covers stack, testing, harness conventions, OpenSpec workflow |
| 3 | All QuantLab agents reference `AGENTS.md` at session start |

## Affected Files

| File | Change |
|------|--------|
| `AGENTS.md` | New repo-root technical English contract |

---

## Domain: model-assignments (NEW)

### Requirement: Uniform Model Policy (REQ-903)

All QuantLab agents MUST use `model: "opencode/deepseek-v4-flash-free"` in repo `opencode.json`. No agent MAY split models without an explicit change to this policy. `default_agent` MUST remain intact.

#### Scenario: All 19 agents share one model
- GIVEN the repo `opencode.json`
- WHEN the agent set loads
- THEN all 19 QuantLab agents declare `opencode/deepseek-v4-flash-free`
- AND `default_agent` is intact

#### Scenario: Split model rejected
- GIVEN an `opencode.json` edit that assigns different models
- WHEN validation runs
- THEN the validation fails
- AND the change is rejected

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | All 19 QuantLab agents declare `opencode/deepseek-v4-flash-free` |
| 2 | `default_agent` remains intact |
| 3 | Split model assignments are rejected by validation |

## Affected Files

| File | Change |
|------|--------|
| `opencode.json` | `model` on all QuantLab agents |

---

## Domain: skill-format (NEW)

### Requirement: LLM-First Skill Format (REQ-904)

Every QuantLab skill MUST follow the LLM-first format: YAML frontmatter with `name`, `description`, `disable-model-invocation`, `user-invocable`, `license`, `metadata`, and a `## Execution Role` section defining executor/orchestrator boundaries. Skills MUST include an orchestrator/executor gate and explicit exit conditions.

#### Scenario: Skill loads with valid format
- GIVEN a skill directory with `SKILL.md`
- WHEN the skill registry loads it
- THEN frontmatter parses successfully
- AND the execution role is recognized

#### Scenario: Invalid format rejected
- GIVEN a `SKILL.md` missing frontmatter or execution role
- WHEN the registry loads it
- THEN the skill is flagged as invalid
- AND a repair reference is returned

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | All QuantLab skills have valid YAML frontmatter |
| 2 | All skills include `## Execution Role` section |
| 3 | Skills include orchestrator/executor gate and exit conditions |

## Affected Files

| File | Change |
|------|--------|
| `ai/opencode/skills/quantlab-run-campaign/SKILL.md` | Deduped to pointer format |
| `ai/opencode/skills/quantlab-deploy-strategy/SKILL.md` | New LLM-first rewrite |
| `ai/opencode/skills/quantlab-monitor-status/SKILL.md` | New LLM-first rewrite |

---

## Domain: review-lifecycle (NEW)

### Requirement: Review Lifecycle for SDK Changes (REQ-905)

The system MUST define a review lifecycle for SDK changes: a 4R consent envelope (Request, Review, Repair, Release), a stop-reason table blocking invalid transitions, and a `repair --preflight` reference. RDD enable is out of scope.

#### Scenario: 4R envelope captures consent
- GIVEN an SDK change requiring review
- WHEN the review lifecycle starts
- THEN the 4R consent envelope is presented
- AND all four stages are tracked

#### Scenario: Stop-reason table blocks invalid transitions
- GIVEN a review in the Request stage
- WHEN a Release transition is attempted
- THEN the stop-reason table blocks it
- AND the flow halts with the reason

#### Scenario: Repair references preflight
- GIVEN a repair needed after review
- WHEN `repair --preflight` runs
- THEN it validates the change against the consent envelope
- AND returns repair instructions

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | 4R consent envelope (Request, Review, Repair, Release) is defined |
| 2 | Stop-reason table blocks invalid transitions |
| 3 | `repair --preflight` reference exists |
| 4 | RDD enable is explicitly out of scope |

## Affected Files

| File | Change |
|------|--------|
| `docs/guides/review-lifecycle.md` | New 4R review for SDK changes |