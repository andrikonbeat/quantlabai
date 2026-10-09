# Human Gate Orchestrator Specification

## Purpose

Implements 5 asynchronous human approval gates as pipeline stage interceptors with configurable timeout (default 24h), fallback policies (abort/continue/escalate), and notification hooks (email, Slack, webhook).

---

## Requirements

### Requirement: Gate Interceptor Framework

The system MUST provide a GateInterceptor class that integrates with PipelineRunner as a special stage type, pausing execution and awaiting async human decision.

#### Scenario: Gate interceptor pauses pipeline
- GIVEN pipeline reaches gate stage HUMAN_REVIEW_OBJECTIVES
- WHEN GateInterceptor.execute(ctx) called
- THEN PipelineContext.gate_pending = gate_id, gate_context populated
- AND stage returns GatePendingResult, runner pauses

#### Scenario: Gate context contains required artifacts
- GIVEN gate HUMAN_APPROVE_PORTFOLIO after PortfolioAgent
- WHEN gate context prepared
- THEN GateContext includes: portfolio_cfx, selected_strategies, correlation_matrix, risk_allocation, portfolio_stats

### Requirement: Async Approval Protocol

The system MUST implement callback protocol: on_gate(gate_id, context) -> Awaitable[GateDecision] with decision enum: APPROVE, REJECT, MODIFY, ESCALATE.

#### Scenario: Human approves via callback
- GIVEN gate HUMAN_REVIEW_OBJECTIVES, callback registered
- WHEN human reviews and clicks "Approve" in UI
- THEN callback returns GateDecision.APPROVE with optional comments
- AND pipeline resumes at next stage

#### Scenario: Human requests modification
- GIVEN gate HUMAN_APPROVE_ITERATION
- WHEN human selects "Modify criteria" and submits new min_sharpe=1.6
- THEN callback returns GateDecision.MODIFY with modified_context
- AND pipeline updates context and re-runs ReviewerAgent

### Requirement: Timeout and Fallback Policies

Each gate MUST have configurable timeout_hours (default 24) and fallback: ABORT | CONTINUE | ESCALATE.

| Gate ID | Default Timeout | Fallback |
|---------|-----------------|----------|
| HUMAN_REVIEW_OBJECTIVES | 24h | ESCALATE to research_lead |
| HUMAN_APPROVE_ITERATION | 24h | ABORT campaign, archive |
| HUMAN_APPROVE_PORTFOLIO | 24h | ESCALATE to portfolio_mgr |
| HUMAN_APPROVE_DEPLOY | 12h | HOLD, queue for next window |
| HUMAN_REVIEW_PERFORMANCE | 48h | CONTINUE monitoring |

#### Scenario: Timeout triggers fallback
- GIVEN gate HUMAN_APPROVE_DEPLOY, timeout=12h, fallback=HOLD
- WHEN 12h elapsed with no decision
- THEN fallback executes: deployment queued, status=PENDING_APPROVAL
- AND notification sent: "Deploy held — awaiting manual approval"

#### Scenario: Escalation fallback notifies alternate approver
- GIVEN gate HUMAN_REVIEW_OBJECTIVES, fallback=ESCALATE, escalate_to="research_lead@quantlab.ai"
- WHEN timeout fires
- THEN notification sent to escalate_to with gate context
- AND gate re-opened with extended timeout (24h) for escalated approver

### Requirement: Notification Hooks

The system MUST support multiple notification channels: email, Slack webhook, generic webhook, console.

#### Scenario: Multi-channel notification on gate pending
- GIVEN gate HUMAN_APPROVE_PORTFOLIO pending, config: email + Slack
- WHEN gate activated
- THEN email sent to portfolio_team@ with portfolio summary
- AND Slack message posted to #portfolio-approvals with approve/reject buttons
- AND both include gate_id, campaign_id, timeout_remaining

#### Scenario: Notification on decision
- GIVEN gate decision=REJECT
- WHEN decision recorded
- THEN notification: "Campaign {id} rejected at {gate}: {reason}"

### Requirement: Gate Decision Audit Trail

All gate decisions MUST be persisted to Engram topic agent/research-director/{campaign_id} with full context.

#### Scenario: Decision audit entry created
- GIVEN gate HUMAN_APPROVE_ITERATION, decision=APPROVE, decider="alice@quantlab.ai"
- WHEN decision recorded
- THEN Engram observation: type=decision, content includes gate_id, decision, decider, timestamp, context_summary
- AND topic_key = "agent/research-director/{campaign_id}"

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| All 5 gates defined with correct timeout/fallback | Unit test: assert gate configs match table |
| Callback protocol returns GateDecision enum | Unit test: mock callback, assert return type |
| Timeout triggers correct fallback per gate | Unit test: advance time, assert fallback action |
| Notifications sent to configured channels | Integration: mock email/Slack, assert called |
| Engram audit entry for every decision | Unit test: verify mem_save called with decision data |

---

## Non-Functional Requirements

- **Dependencies**: engram (audit), notification adapters (pluggable)
- **Reliability**: Gate state persisted — process restart resumes at pending gate
- **Security**: Notification webhooks validated (HMAC); no secrets in gate context
- **Observability**: Gate state transitions logged: PENDING → APPROVED/REJECTED/MODIFIED/TIMEOUT