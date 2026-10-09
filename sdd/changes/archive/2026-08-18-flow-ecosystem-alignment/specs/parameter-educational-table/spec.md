# Delta for parameter-educational-table

## ADDED Requirements

### Requirement: Reviewer-Persisted Teaching Table (G7)

`ConfigReviewStage` MUST build the REQ-205 teaching table via `build_teaching_table` (knowledge/kb/teaching.py:39) from `KbStore.consult` hits for the configured `BuildConfig` fields, persist it to `knowledge/structured/{campaign_id}/review/teaching-table.md`, and include the path in the review verdict and `PhaseResult.artifacts`. The reviewer owns the deliverable.

#### Scenario: Review persists the table

- GIVEN a reviewed BuildConfig with configured parameters
- WHEN `ConfigReviewStage.execute()` completes
- THEN `knowledge/structured/{campaign_id}/review/teaching-table.md` exists
- AND its path is in the verdict and `PhaseResult.artifacts`

#### Scenario: Parameter without KB entry

- GIVEN a configured field with no KB entry
- WHEN the table is built
- THEN the row is a stable "no KB entry" fallback (or EMPTY_TABLE_NOTE)
- AND the table file is still persisted

#### Scenario: Empty config yields placeholder table

- GIVEN no build config to review
- WHEN the stage persists the table
- THEN the table is the stable placeholder line
- AND the stage still completes without error