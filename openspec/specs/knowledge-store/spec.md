# Delta for knowledge-store

## ADDED Requirements

### Requirement: Campaign Phase Directories

The system MUST create `campaign-phases/{campaign_id}/{phase_name}/` directories in Knowledge Lake. Each phase directory MUST contain `envelope.json`. The system SHALL create the directory structure when a campaign initializes.

#### Scenario: Campaign initialization creates phase directories

- GIVEN a new campaign ID "camp_001"
- WHEN the campaign initializes
- THEN `campaign-phases/camp_001/` is created
- AND subdirectories for all 14 phases are pre-created

#### Scenario: Phase envelope written on completion

- GIVEN a completed research phase for campaign "camp_001"
- WHEN the envelope is written
- THEN `campaign-phases/camp_001/research/envelope.json` exists
- AND it contains the phase result metadata

## MODIFIED Requirements

### Requirement: Directory Initialization

The system MUST create the Knowledge Lake skeleton: `raw/`, `structured/`, `graph/`, `embeddings/`, `datasets/`, `pipeline-runs/`, `agent-memory/`, `campaign-phases/`, `parameter-matrix/`, `guardian-feedback/`, `maintenance/`. `structured/` SHALL host the reconciled sub-layouts `structured/{campaign_id}/` (configs, metrics, results, envelopes), `structured/sqx-kb/{sqx_version}/parameters/{tab}/`, and `structured/sqx-version/{old}→{new}/`. Each directory SHALL contain a `.gitkeep` or metadata file. `campaign-phases/` MUST contain `{campaign_id}/{phase_name}/envelope.json` for every completed phase.
(Previously: 7-directory skeleton with pipeline-runs/ and agent-memory/)

#### Scenario: Fresh initialization creates all directories

- GIVEN a `knowledge/` path that does not exist
- WHEN the system initializes the Knowledge Lake
- THEN 11 top-level subdirectories are created
- AND each contains a `.gitkeep` marker file

#### Scenario: Re-initialization on existing structure is idempotent

- GIVEN an already-initialized Knowledge Lake with files present
- WHEN the system initializes again
- THEN no existing files are modified or deleted
- AND no error is raised

### Requirement: Metadata Indexing

The system MUST maintain a metadata index (`knowledge/index.yaml`) tracking top-level files per directory, creation timestamps, file sizes, and content hashes. The index MUST include entries for `campaign-phases/{campaign_id}/envelope.json`, `parameter-matrix/{run_id}/parameter_matrix.json`, `guardian-feedback/{campaign_id}/feedback.json`, and `maintenance/{campaign_id}/plan.json`. The index MUST be human-readable YAML and SHALL be version 5.
(Previously: index.yaml tracking top-level files; version 4)

#### Scenario: Index tracks new artifact types

- GIVEN an initialized Knowledge Lake
- WHEN a parameter matrix and campaign envelope are written
- THEN the index includes entries for both artifact types
- AND the version is 5

#### Scenario: Legacy v4 index migrates to v5

- GIVEN an index.yaml of version 4
- WHEN `read_index()` runs
- THEN entries parse with defaults
- AND the version is upgraded to 5
