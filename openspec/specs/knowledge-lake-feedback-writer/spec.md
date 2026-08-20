# Knowledge Lake Feedback Writer Specification

## Purpose

Persists campaign evaluation outcomes and hypothesis feedback to Knowledge Lake, closing the research loop by making results available for future calibration and retrieval.

## Requirements

### Requirement: REQ-F3-01 Feedback Record Persistence

The system MUST append a FeedbackRecord after hypothesis evaluation:
- hypothesis_id: str
- campaign_id: str
- outcome: accepted | rejected
- final_metrics: dict[str, float] (sharpe, profit_factor, win_rate, max_drawdown)
- timestamp: ISO8601

FeedbackRecords SHALL be appended to the campaign's metadata.yaml under a feedback section.

#### Scenario: Accepted hypothesis persisted

- GIVEN a hypothesis is accepted after evaluation with sharpe=1.8
- WHEN KnowledgeLakeFeedbackWriter.write_feedback() runs
- THEN a FeedbackRecord is appended to the campaign metadata
- AND the record contains the final metrics

#### Scenario: Rejected hypothesis persisted

- GIVEN a hypothesis is rejected due to validation failure
- WHEN KnowledgeLakeFeedbackWriter.write_feedback() runs
- THEN a FeedbackRecord with outcome=rejected is persisted
- AND no metrics are recorded (or recorded as null)

### Requirement: REQ-F3-02 ResearchAgent Wiring

The system MUST wire feedback writing into ResearchAgent.run() when evaluation outcomes are available. Writing MUST be async and non-blocking to the main research flow.

#### Scenario: Feedback written after evaluation

- GIVEN ResearchAgent.run() completes evaluation
- WHEN outcomes are available
- THEN KnowledgeLakeFeedbackWriter.write_feedback() is called asynchronously
- AND the main flow does not wait for the write to complete

### Requirement: REQ-F3-03 Read-Only Recommendations First

The system MUST expose feedback as read-only recommendations before enabling auto-adjust:
- Recommendations SHALL be queryable via QueryBuilder
- Auto-adjust of hypothesis confidence SHALL be gated behind a human approval flag
- Default mode: read-only

#### Scenario: Recommendations are queryable

- GIVEN feedback records exist for 20 campaigns
- WHEN QueryBuilder.filter_by_tags({"feedback_status": "accepted"}) runs
- THEN matching campaigns are returned
- AND confidence adjustments are not applied automatically

#### Scenario: Human gate blocks auto-adjust

- GIVEN auto_adjust=False (default)
- WHEN a new hypothesis is formulated
- THEN feedback is used for ranking only
- AND confidence is not automatically modified
