# Exploration: Guardian as First-Class Orchestration Agent with Bidirectional Feedback

Change: `guardian-orchestrator-feedback`
Topic: "agente guardian primera clase, feedback bidireccional"

## Current State

The Guardian is a **library subsystem**, not an orchestration actor. It is fully
implemented in the SDK but has no agent identity and no bidirectional channel:

- **Guardian modules** (`sdk/quantlab/guardian/`): 6 independent guardians
  (`market.py`, `risk.py`, `portfolio.py`, `capital.py`, `quality.py`,
  `execution.py`) coordinated by `MetaGuardianOrchestrator`
  (`sdk/quantlab/guardian/orchestrator.py`) with a portfolio state machine
  (NORMAL → VIGILANCE → DEFENSIVE → QUARANTINE → RECOVERY; hysteresis in
  `_determine_state`).
- **Live evaluation** (`sdk/quantlab/guardian/live.py`): `evaluate_live()`
  consumes an equity stream (from `AutonomousMonitorDaemon`, REQ-41) and
  transitions to DEFENSIVE above a 10% live drawdown, producing a
  `FeedbackRecord` (REQ-40). STREAM_LOST holds fail-closed. The working tree
  has an uncommitted change widening `points` to any `Iterable[EquityPoint]`.
- **Feedback records** (`sdk/quantlab/guardian/feedback.py`): `FeedbackSignals`
  + `FeedbackRecord` (degradation, drawdown, regime, cost, parameter deltas)
  with `next_cycle_inputs()`. **Pure and additive by design** — never touches
  gates or flow order (REQ-34/REQ-37).
- **Pipeline wiring** (`sdk/quantlab/pipeline/registry.py:328`):
  `GuardianEvaluationAgentStage` registered as phase `guardian_evaluate`,
  sitting in the loop tail `monitor < guardian_evaluate < [retester] <
  [optimizer]` (`sdk/quantlab/campaign/flow.py:215-216`). `LiveOpsStage`
  (`stages/live_ops_stage.py`) is the terminal `live-ops` phase publishing
  `live_ops_status` from the archive bundle.
- **Feedback consumption today (one-directional, data-level)**:
  `FeedbackRecord` is embedded in the campaign archive
  (`sdk/quantlab/phase4/campaign_archive.py`) and consumed by next-cycle
  generation. `ArchiverAgent` builds the maintenance/replacement runbook from
  `guardian_state` (REQ-33). Escalations reach mobile push via the ops surface
  (`sdk/quantlab/agents/ops_surface.py`, REQ-36).
- **Orchestration layer has NO Guardian agent**: `~/.config/opencode/opencode.json`
  defines only `quantlab-campaign`, `quantlab-deploy`, `quantlab-monitor`,
  `quantlab-orchestrator`. The orchestrator routing table
  (`prompts/quantlab/orchestrator.md`) has no GUARDIAN route; the campaign
  agent prompt runs the Guardian live flow inline inside phase 14 (live-ops).

**Gap**: Guardian is a passive library callable. There is no orchestrator →
guardian directive channel, and guardian → orchestrator feedback exists only
as persisted archive data, not as an agent-to-agent feedback envelope.

## Affected Areas

- `~/.config/opencode/opencode.json` — add `quantlab-guardian` agent; add
  routing + permission entries on `quantlab-orchestrator`.
- `~/.config/opencode/prompts/quantlab/orchestrator.md` — extend the intent
  routing table with a GUARDIAN route (directives, live-ops status, feedback).
- `~/.config/opencode/prompts/quantlab/campaign.md` — phase 14 live-ops
  currently embeds the Guardian flow; align with the new agent boundary.
- `sdk/quantlab/guardian/feedback.py` — `FeedbackRecord`/`next_cycle_inputs()`
  are the natural guardian → orchestrator feedback payload (already REQ-34).
- `sdk/quantlab/guardian/live.py` — `evaluate_live` (modified in working tree)
  is the live-feedback entry point the agent would invoke.
- `sdk/quantlab/pipeline/stages/agent_stages.py` — `GuardianEvaluationAgentStage`
  (no covering tests) produces `guardian_state`; candidate for the agent's
  first-class path.
- `sdk/quantlab/pipeline/stages/live_ops_stage.py` — `LiveOpsStage` (no
  covering tests) publishes `live_ops_status`.
- `sdk/quantlab/campaign/flow.py` — `PHASES` constant; MUST NOT gain a new
  phase (REQ-37). Guardian stays an agent wrapper, not a new flow stage.
- `sdk/quantlab/agents/ops_surface.py` — escalation/ack surface (REQ-36) to
  reuse for the agent-to-orchestrator escalation leg.
- `openspec/specs/guardian-feedback/spec.md`, `openspec/specs/guardian-feedback-loop/spec.md`,
  `openspec/specs/meta-guardian/spec.md` — existing guardian specs (REQ-34,
  REQ-40) that the delta must target; note duplicate coverage today.

## Approaches

1. **Agent-only (orchestration layer)** — Add `quantlab-guardian` subagent +
   prompt; orchestrator routes guardian intents via `task`; Guardian returns
   the Result Contract envelope wrapping `guardian_state` + feedback. SDK stays
   virtually untouched.
   - Pros: smallest change; matches existing agent pattern (campaign/deploy/monitor).
   - Cons: contract lives in prompts, not code; no durable/testable feedback channel beyond archive.
   - Effort: Low-Medium

2. **SDK-native feedback bus (data layer)** — Extend `feedback.py` with typed
   bidirectional messages (e.g. `GuardianDirective` orchestrator → guardian,
   `GuardianReport` guardian → orchestrator) persisted and consumed by the
   pipeline; no new agent.
   - Pros: durable and unit-testable; survives sessions; feedback is a first-class artifact.
   - Cons: no agent identity — the "primera clase" ask is not met at the orchestration surface; more machinery.
   - Effort: Medium-High

3. **Hybrid: first-class agent + feedback envelope contract** — Add the
   `quantlab-guardian` agent (approach 1) AND formalize the agent-boundary
   feedback envelope: guardian → orchestrator returns `guardian_state` +
   `FeedbackRecord`-shaped feedback (reusing `next_cycle_inputs()`); orchestrator
   → guardian passes structured directives (evaluate now, live-ops status,
   acknowledged escalation). Reuses `ops_surface` for escalation ack.
   - Pros: satisfies both asks; feedback is explicit and testable; aligns with
     the Result Contract envelope used by every other agent.
   - Cons: touches both layers; needs coordination of prompts, permissions, and envelope tests.
   - Effort: Medium

## Recommendation

Hybrid (approach 3): a first-class `quantlab-guardian` subagent for the
orchestration surface, with the feedback envelope contract built on the
existing `feedback.py` records — NOT a new pipeline phase (REQ-37 keeps the 14
phases; the Guardian wraps `guardian_evaluate`/`live-ops`, it does not extend
`PHASES`). Bidirectional feedback reuses the already-designed REQ-34 payload:
guardian → orchestrator as envelope + persisted `FeedbackRecord`; orchestrator →
guardian as structured directives. Prefer adding covering tests for
`GuardianEvaluationAgentStage`/`LiveOpsStage` and `FeedbackRecord` (currently
untested) as part of the change.

## Risks

- **REQ-37 flow integrity**: adding a 15th phase or reordering `PHASES` aborts
  with `FlowIntegrityError` before execution. The Guardian must remain an agent
  wrapper over existing phases, never a new flow phase.
- **Spec fragmentation**: guardian requirements already live across
  `guardian-feedback`, `guardian-feedback-loop`, and `meta-guardian` specs. The
  proposal must pick a canonical target (likely `guardian-feedback-loop` or a
  new `guardian-agent`) and avoid duplicating REQ-34/REQ-40.
- **Human gates**: bidirectional feedback must never auto-approve/reorder flow
  (REQ-34 scenario 2). Agent autonomy must be bounded to evaluation + advice.
- **Uncommitted working-tree change**: `live.py` Iterable widening is unstaged;
  the proposal should assume it or call it out.
- **Untested surface**: `FeedbackRecord`, `GuardianEvaluationAgentStage`, and
  `LiveOpsStage` have no covering tests today; the agent boundary amplifies that risk.

## Ready for Proposal

Yes. The orchestrator should tell the user: the Guardian is currently a library
subsystem with a data-level one-way feedback channel; the proposed change makes
it a first-class orchestration agent (new `quantlab-guardian` subagent + routing)
with bidirectional feedback built on the existing REQ-34 record contract, without
touching the 14-phase flow (REQ-37).