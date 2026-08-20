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
