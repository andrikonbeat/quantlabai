# Knowledge Storage Specification

## Purpose

Manages the Knowledge Lake directory structure — a filesystem-first, Git-versioned research artifact repository. Provides path conventions, directory initialization, and basic metadata indexing using open, human-readable formats.

## Requirements

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

### Requirement: Metadata Indexing

The system MUST maintain a metadata index (`knowledge/index.yaml`) tracking top-level files per directory, creation timestamps, file sizes, and content hashes. The index MUST be human-readable YAML.

#### Scenario: Index updates after file addition

- GIVEN an initialized Knowledge Lake with an index
- WHEN a file is added to `raw/` and the index is updated
- THEN the index contains the new file's path, size, and SHA-256 hash

#### Scenario: Corrupted index is recoverable

- GIVEN a Knowledge Lake with a corrupted `index.yaml`
- WHEN the system attempts to read the index
- THEN the corruption is detected and a new index is rebuilt from the filesystem state

### Requirement: Open Format Conventions

The system MUST enforce file format conventions: YAML for metadata, JSON for structured data, CSV for tabular data, Parquet for columnar data. Non-conforming files MUST raise a warning but cannot be rejected.

#### Scenario: Non-conforming file logs warning

- GIVEN a `.docx` file placed in `structured/`
- WHEN the system validates file conventions
- THEN a warning is logged noting the non-standard format

#### Scenario: Allowed formats pass validation

- GIVEN `.yaml`, `.json`, `.csv`, and `.parquet` files in their respective directories
- WHEN the system validates file conventions
- THEN no warnings or errors are raised

### Requirement: Path Resolution

The system MUST resolve Knowledge Lake paths relative to a configurable root, with cross-platform separator handling (forward slash on POSIX, backslash on Windows).

#### Scenario: Linux paths use forward slashes

- GIVEN a Knowledge Lake at `/home/user/knowledge` on Linux
- WHEN the system resolves `raw/backtest-1.csv`
- THEN the resolved path is `/home/user/knowledge/raw/backtest-1.csv`

#### Scenario: Windows paths use backslashes

- GIVEN a Knowledge Lake at `C:\knowledge` on Windows
- WHEN the system resolves `raw/backtest-1.csv`
- THEN the resolved path is `C:\knowledge\raw\backtest-1.csv`

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
