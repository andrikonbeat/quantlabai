# Delta for Knowledge Storage

Change: reconcile the Knowledge Lake to a single canonical layout, extend the skeleton to 8 top-level directories plus structured sub-layouts, bump the index to v4, and require a taxonomy conformance test.

## MODIFIED Requirements

### Requirement: Directory Initialization

The system MUST create the Knowledge Lake skeleton: `raw/`, `structured/`, `graph/`, `embeddings/`, `datasets/`, `pipeline-runs/`, `agent-memory/`. `structured/` SHALL host the reconciled sub-layouts `structured/{campaign_id}/` (configs, metrics, results), `structured/sqx-kb/{sqx_version}/parameters/{tab}/`, and `structured/sqx-version/{old}→{new}/`. Each directory SHALL contain a `.gitkeep` or metadata file.
(Previously: 5-directory skeleton without `pipeline-runs/`, `agent-memory/`, `sqx-kb/`, or `sqx-version/`)

#### Scenario: Fresh initialization creates all directories

- GIVEN a `knowledge/` path that does not exist
- WHEN the system initializes the Knowledge Lake
- THEN 7 top-level subdirectories and the 3 structured sub-layouts are created, each with a `.gitkeep` marker file

#### Scenario: Re-initialization on existing structure is idempotent

- GIVEN an already-initialized Knowledge Lake with files present
- WHEN the system initializes again
- THEN no existing files are modified or deleted, and no error is raised

## ADDED Requirements

### Requirement: REQ-402 Taxonomy Conformance Test

The system MUST provide a conformance test asserting every writer's artifacts land in the reconciled canonical layout and that no writer emits outside its mapped directories.

#### Scenario: Conformance green

- GIVEN writers producing artifacts across the lake
- WHEN the conformance test runs
- THEN all artifacts map to canonical locations and the test passes

#### Scenario: Off-layout write fails the test

- GIVEN a writer emitting a file outside its mapped directory
- WHEN the conformance test runs
- THEN the test fails, naming the offending path

### Requirement: REQ-403 Index v4 Compatibility

The system MUST bump `knowledge/index.yaml` to version 4, covering the reconciled layout: campaign metrics/tags/links, agent-memory decisions, KB parameter files, and version events. The index MUST read legacy v1–v3 indexes with defaults (backward compatible).

#### Scenario: Rebuild covers new areas

- GIVEN campaigns, agent-memory, and sqx-kb entries
- WHEN `rebuild_index()` runs
- THEN index.yaml is version 4 and includes entries for each area

#### Scenario: Legacy index readable

- GIVEN an index.yaml of version 1
- WHEN `read_index()` runs
- THEN entries parse with defaults and no error
