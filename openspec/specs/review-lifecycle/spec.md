# review-lifecycle Specification

## Purpose

Review lifecycle for SDK changes: 4R consent envelope, stop-reason table, repair reference. RDD enable is out of scope.

## Requirements

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
