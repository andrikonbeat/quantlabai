# Delta for knowledge-store

## ADDED Requirements

### Requirement: Guardian Metrics Query API (Issue 6)

`TimeSeriesStore` MUST expose a guardian-facing query API: `query_guardian_metrics(campaign_id, guardian_name=None, start=None, end=None)` returning `list[GuardianMetricRecord]`. The system SHALL index records by `campaign_id` and `timestamp` for efficient range queries. The API MUST be read-only; writes SHALL flow exclusively through `GuardianFeedbackStore`.

#### Scenario: Query by campaign returns all metrics

- GIVEN persisted metrics for campaigns `camp_001` and `camp_002`
- WHEN `query_guardian_metrics(campaign_id="camp_001")` is called
- THEN all records for `camp_001` are returned
- AND results are ordered by timestamp

#### Scenario: Query by guardian filters

- GIVEN metrics from `RiskGuardian` and `PortfolioGuardian`
- WHEN `query_guardian_metrics(campaign_id="camp_001", guardian_name="RiskGuardian")` is called
- THEN only `RiskGuardian` records are returned

#### Scenario: Range query enforces boundaries

- GIVEN metrics spanning 2025-01-01 to 2025-06-01
- WHEN `query_guardian_metrics(campaign_id="camp_001", start="2025-03-01", end="2025-04-01")` is called
- THEN only records within the range are returned

#### Scenario: Empty campaign returns empty list

- GIVEN no metrics for `camp_nonexistent`
- WHEN `query_guardian_metrics(campaign_id="camp_nonexistent")` is called
- THEN an empty list is returned
- AND no error is raised

## MODIFIED Requirements

### Requirement: Directory Initialization

The system MUST create the Knowledge Lake skeleton: `raw/`, `structured/`, `graph/`, `embeddings/`, `datasets/`, `pipeline-runs/`, `agent-memory/`, `campaign-phases/`, `parameter-matrix/`, `guardian-feedback/`, `maintenance/`. `structured/` SHALL host the reconciled sub-layouts `structured/{campaign_id}/` (configs, metrics, results, envelopes), `structured/sqx-kb/{sqx_version}/parameters/{tab}/`, and `structured/sqx-version/{old}→{new}/`. Each directory SHALL contain a `.gitkeep` or metadata file. `campaign-phases/` MUST contain `{campaign_id}/{phase_name}/envelope.json` for every completed phase. `guardian-feedback/` MUST contain `{campaign_id}/metrics.jsonl` for every campaign with guardian evaluation.

(Previously: 11-directory skeleton without guardian-feedback/ requirement)

#### Scenario: Fresh initialization creates all directories

- GIVEN a `knowledge/` path that does not exist
- WHEN the system initializes the Knowledge Lake
- THEN 11 top-level subdirectories are created
- AND `guardian-feedback/` exists with a `.gitkeep` marker file

#### Scenario: Re-initialization on existing structure is idempotent

- GIVEN an already-initialized Knowledge Lake with files present
- WHEN the system initializes again
- THEN no existing files are modified or deleted
- AND no error is raised
