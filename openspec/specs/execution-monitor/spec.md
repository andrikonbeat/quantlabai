# Execution Monitor Specification

## Purpose

Monitors long-running SQX campaigns via long-polling, detects stalls, and provides LLM-assisted diagnostics within 60 seconds of stall detection.

## Requirements

### Requirement: Long-Polling with Event Detection

The system MUST poll SQX daemon status at configurable intervals (default 30s) and detect stall conditions: no progress for 2x expected duration, error states, or daemon disconnection. The monitor SHALL emit events to the campaign event bus.

#### Scenario: Normal progress continues polling

- GIVEN a campaign progressing at expected rate
- WHEN the monitor polls
- THEN status updates are recorded
- AND no stall event is emitted

#### Scenario: Stall triggers event

- GIVEN a campaign with no progress for 6 minutes (2x 3-minute expected)
- WHEN the monitor detects the stall
- THEN a stall event is emitted
- AND the campaign is marked STALLED

#### Scenario: Daemon disconnection triggers event

- GIVEN the SQX daemon becomes unreachable
- WHEN the monitor detects the disconnection
- THEN a daemon_lost event is emitted
- AND the campaign enters HOLD state

### Requirement: LLM-Assisted Diagnostics

The system MUST invoke LLM diagnostics within 60 seconds of stall detection. Diagnostics SHALL analyze campaign logs, SQX error output, and Knowledge Lake artifacts to propose a remediation action.

#### Scenario: LLM diagnostics on stall

- GIVEN a stalled optimize phase
- WHEN the monitor invokes LLM diagnostics
- THEN the analysis completes within 60 seconds
- AND a remediation suggestion is attached to the campaign envelope

#### Scenario: LLM fallback on timeout

- GIVEN LLM diagnostics exceed 60 seconds
- WHEN the monitor detects the timeout
- THEN a timeout event is emitted
- AND the campaign enters HOLD for human review

### Requirement: Checkpoint Integration

The monitor MUST integrate with the unified execution substrate checkpoint system. On stall, the monitor SHALL trigger a checkpoint write before invoking diagnostics.

#### Scenario: Stall triggers checkpoint before diagnostics

- GIVEN a stalled portfolio phase
- WHEN the monitor detects the stall
- THEN a checkpoint is written immediately
- AND LLM diagnostics are invoked after checkpoint completion

### Requirement: Canonical Monitor Phase Binding (REQ-26)

The system MUST bind the orchestrated monitor phase to `ExecutionMonitorStage` (REQ-26) as its canonical execution stage in the orchestrated tail. The orchestrated tail MUST NOT route monitor-phase execution through the legacy `MonitoringAgent`, which is a no-op without live equity.

#### Scenario: Orchestrated tail binds ExecutionMonitorStage

- GIVEN the orchestrated campaign tail reaching the monitor phase
- WHEN the monitor phase executes
- THEN the phase runs on `ExecutionMonitorStage` (REQ-26)
- AND its events flow through the substrate polling

#### Scenario: Canonical binding supersedes legacy agent

- GIVEN the orchestrated monitor phase configured
- WHEN the tail starts
- THEN no monitor-phase work is routed through the legacy `MonitoringAgent`
- AND stage-based monitoring is used throughout
