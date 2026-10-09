# Research Director Agent Specification

## Purpose

Central orchestrator that owns the PipelineRunner, sequences 8 agent stages, manages 5 human gates, and controls campaign lifecycle from objective definition through deployment monitoring. Implements objective optimization across cycles.

---

## Requirements

### Requirement: Pipeline Ownership

The system MUST provide a ResearchDirector class that owns a PipelineRunner instance, constructs the full 17-stage pipeline (8 agent stages + 5 gate stages + 4 transition stages), and manages campaign lifecycle state.

#### Scenario: Director constructs full pipeline
- GIVEN a ResearchConfig with objectives, hypotheses, and gate_policies
- WHEN ResearchDirector.build_pipeline() is called
- THEN a Pipeline with 17 stages is returned in correct order: research → gate1 → build → statistics → review → gate2 → portfolio → gate3 → deploy → gate4 → monitor → gate5 → (loop)
- AND each stage declares requires/provides contracts matching agent I/O

#### Scenario: Director manages campaign lifecycle
- GIVEN a campaign_id and ResearchConfig
- WHEN ResearchDirector.run_campaign() is called
- THEN PipelineRunner executes with error isolation per stage
- AND campaign state transitions: CREATED → RUNNING → GATE_PENDING → RUNNING → ... → COMPLETED | FAILED | GATE_TIMEOUT
- AND on gate timeout, configured fallback (escalate/abort/continue) is executed

### Requirement: Stage Scheduling with Contracts

The system MUST enforce stage contracts via PipelineContext requires/provides. ResearchDirector SHALL validate that all agent stages declare compatible I/O keys before execution.

#### Scenario: Contract validation before run
- GIVEN a pipeline with ResearchAgent (provides: research_config) and BuilderAgent (requires: research_config)
- WHEN ResearchDirector.validate_contracts() is called
- THEN validation passes — requires satisfied by provides
- AND missing required keys raise ContractValidationError with stage names

#### Scenario: Contract mismatch detected
- GIVEN a pipeline where StatisticsAgent requires "export_paths" but BuilderAgent provides "cfx_bytes"
- WHEN ResearchDirector.validate_contracts() is called
- THEN ContractValidationError lists missing "export_paths" and responsible stage

### Requirement: Gate Orchestration

The system MUST implement 5 human gates as pipeline stage interceptors with async approval protocol, configurable timeout (default 24h), and fallback policies.

#### Scenario: Gate interceptor pauses pipeline
- GIVEN pipeline reaches HUMAN_REVIEW_OBJECTIVES gate after ResearchAgent
- WHEN gate interceptor executes
- THEN pipeline pauses, GateContext with research_config and hypotheses is prepared
- AND on_gate callback is invoked with timeout=24h

#### Scenario: Human approves gate within timeout
- GIVEN gate callback returns GateDecision.APPROVED within 24h
- WHEN callback completes
- THEN pipeline resumes at next stage (BuilderAgent)
- AND gate decision stored in Engram topic agent/research-director/{campaign_id}

#### Scenario: Gate timeout triggers fallback
- GIVEN gate timeout=24h expires with no decision
- WHEN timeout fires
- THEN fallback policy executes: HUMAN_REVIEW_OBJECTIVES → escalate to research_lead; HUMAN_APPROVE_ITERATION → abort and archive; HUMAN_APPROVE_PORTFOLIO → escalate; HUMAN_APPROVE_DEPLOY → hold; HUMAN_REVIEW_PERFORMANCE → continue

#### Scenario: Gate decision audit trail
- GIVEN any gate decision (approve/reject/fallback)
- WHEN decision recorded
- THEN Engram observation created with gate_id, decision, timestamp, decision_maker, context_summary

### Requirement: Objective Optimization Across Cycles

The system MUST optimize research objectives across iteration cycles using PortfolioAgent results and MonitoringAgent feedback.

#### Scenario: Director proposes next cycle objectives
- GIVEN completed cycle with portfolio Sharpe=1.8, max_drawdown=8%, regime=trending
- WHEN ResearchDirector.propose_next_cycle() called
- THEN new hypotheses target regime-adaptive entry, reduced drawdown via position sizing
- AND iteration_config.convergence_threshold checked (e.g., Sharpe improvement < 0.02 → converge)

#### Scenario: Convergence detection stops campaign
- GIVEN 5 iterations with Sharpe improvements: 1.2→1.5→1.7→1.75→1.76 (threshold=0.02)
- WHEN ResearchDirector.check_convergence() called
- THEN campaign marked CONVERGED, gate HUMAN_REVIEW_PERFORMANCE triggered with retire recommendation

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| Director builds 17-stage pipeline with correct stage order | Unit test: assert stage names and requires/provides |
| Gate interceptors pause/resume pipeline correctly | Integration test: mock callback, assert pause/resume |
| Gate timeout fallback executes correct policy per gate | Unit test: mock timeout, assert fallback action |
| Contract validation catches missing requires | Unit test: mismatch pipeline, assert error details |
| Objective optimization uses monitoring feedback | Integration: feed regime=trending, assert hypothesis adaptation |
| Engram audit trail for all gate decisions | Unit test: verify Engram save called with gate context |

---

## Non-Functional Requirements

- **Performance**: Pipeline validation < 100ms for 17 stages
- **Reliability**: Stage errors isolated — failure in Stage N does not corrupt Stages 1..N-1 artifacts
- **Observability**: Each stage transition emits structured log with stage_name, duration_ms, artifacts_count
- **Dependencies**: pipeline-core, engram, research-dsl, knowledge-query only