# Campaign Archive Specification

## Purpose

Closes a campaign: produces a maintenance/replacement plan and account statistics, and archives campaign artifacts for audit, gated by `HUMAN_APPROVE_ARCHIVE` (REQ-38).

## Requirements

### Requirement: Archive and Maintenance Plan (REQ-33)

The system MUST, in the archive phase, produce: (1) a maintenance/replacement plan for the deployed strategy based on live demo performance and Guardian degradation data, (2) account statistics (equity, drawdown, P&L) over the demo window, and (3) an archived artifact bundle. Replacement candidates MUST come from the campaign portfolio.

#### Scenario: Archive produces plan and stats

- GIVEN a completed demo window and Guardian performance data
- WHEN the archive phase runs
- THEN a maintenance/replacement plan is written
- AND account statistics are computed over the demo window
- AND the artifact bundle is stored for audit

#### Scenario: Degraded strategy triggers replacement

- GIVEN Guardian reports the deployed strategy DEGRADING
- WHEN the archive plan is composed
- THEN the plan recommends replacement from the campaign portfolio
- AND the recommendation is human-confirmed before archive
