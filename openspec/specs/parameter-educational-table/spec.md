# Parameter Educational Table Specification

## Purpose

A generator-driven educational table that makes every seeded SQX parameter teachable. The generator reads the seeded KB plus the SQX builder template (`tpl_build.xml`) and emits (1) a parameter-by-parameter markdown table in the REQ-205 shape and (2) a shared educational dataset consumed by `parameter-justification-matrix` as its rationale source (D2 decision: connected, not standalone).

## Requirements

### Requirement: Table Generation

The system MUST generate a markdown educational table covering every parameter in the seeded KB for the pinned SQX version. Each row MUST follow the REQ-205 column set: Tab / Section, Parameter, What it does, How it works in SQX, Quant trading role, Chosen config, Why, For what. The table MUST be generator-produced from KB fields and MUST NOT require hand-authored rows.

#### Scenario: Table covers all seeded parameters

- GIVEN a seeded KB with ~82 parameters for 144.2953
- WHEN the generator runs
- THEN one markdown row is emitted per parameter
- AND the emitted table matches the REQ-205 headers

#### Scenario: Empty KB yields placeholder, not error

- GIVEN an empty or unseeded KB
- WHEN the generator runs
- THEN the table is a stable placeholder line
- AND the generator exits successfully

### Requirement: Shared Educational Dataset

The generator MUST emit a machine-readable educational dataset (one record per seeded parameter) alongside the table. Each record MUST include: `name`, `sqx_name`, `tab`, `section`, `type`, `default`, `range`, `what_it_does`, `how_it_works_in_sqx`, `quant_trading_role`, `small_account_recommendation`, `why_choose`, `when_choose`, `status`, and `evidence_ref`. `parameter-justification-matrix` MUST consume this dataset as its rationale source.

#### Scenario: Dataset emitted per parameter

- GIVEN a seeded KB for 144.2953
- WHEN the generator runs
- THEN the dataset contains ~82 records
- AND each record carries the KB rationale fields

#### Scenario: Dataset is schema-loadable

- GIVEN an emitted dataset
- WHEN a consumer loads it
- THEN every record parses against the KbParameter contract
- AND no required field is empty for seeded or verified entries

### Requirement: Template Cross-Reference

The generator MUST cross-reference `tpl_build.xml` and SHALL use it to align `sqx_name`, `type`, `default`, and `range` for the Chosen config column. Parameters absent from the template MUST be flagged in the table and MUST retain their KB status without invented values.

#### Scenario: Template values drive the chosen-config cell

- GIVEN a parameter present in `tpl_build.xml` (e.g., Maximum Trades Per Day)
- WHEN the generator renders its row
- THEN the Chosen config cell uses the template type/default/range
- AND the row reflects the KB rationale fields

#### Scenario: Parameter absent from template is flagged

- GIVEN a seeded parameter with no `tpl_build.xml` counterpart
- WHEN the generator renders it
- THEN the row is marked template-missing
- AND the row retains its `needs_review` status

### Requirement: Deterministic Regeneration

The generator MUST be deterministic and idempotent: re-running with unchanged inputs MUST produce byte-identical table and dataset, and MUST NOT modify KB YAMLs or the index.

#### Scenario: Re-run produces identical output

- GIVEN unchanged KB and `tpl_build.xml`
- WHEN the generator runs twice
- THEN both outputs are byte-identical
- AND no KB or index file is modified

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
