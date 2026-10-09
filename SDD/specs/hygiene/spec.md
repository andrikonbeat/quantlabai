# Hygiene Specification

## Purpose

Removes tracked junk and the oversized SQX zip from tracking, commits triage groups in their own commits, and keeps documentation honest about workflow and test counts.

## Requirements

### Requirement: HGN-01 Tracked junk removed

The system MUST `git rm` tracked junk: `=5.18`, the `Save location: /` directory, the installer skeleton (go.sum + compiled binary), and duplicated test files (e.g. root `test_refutation_layer.py`). Untracked `=3.0` MUST be deleted.

#### Scenario: Junk absent from tracking
- GIVEN the cleanup commits
- WHEN `git ls-files` is checked
- THEN none of the junk paths appear

**Acceptance**: junk gone (proposal success criterion).

### Requirement: HGN-02 SQX zip untracked

The SQX zip (`assets/SQX_144_2953_linux_20260601.zip`, 1224.5M) MUST be removed from tracking via `git rm --cached` and kept on an external volume; runtime resolution follows config → `SQX_INSTALL_PATH` → default. No LFS.

#### Scenario: Zip untracked but resolvable
- GIVEN the zip removed from tracking
- WHEN `git ls-files` is checked
- THEN the zip is absent; with SQX_INSTALL_PATH set the external copy resolves

#### Scenario: Missing zip errors clearly
- GIVEN no zip resolvable
- WHEN a component needs SQX
- THEN a clear error is returned, no crash

**Acceptance**: .git stops growing from the zip (proposal: SQX zip removal).

### Requirement: HGN-03 Untracked triage committed

Untracked specs (`sdd/`, `openspec/`) and refutation work MUST be committed in their own commits; deletions in their own commits.

#### Scenario: Triage commits land cleanly
- GIVEN the triage
- WHEN commits are made
- THEN each logical group (specs, refutation, deletions) is a separate commit

**Acceptance**: per-slice rollback preserved (proposal rollback plan).

### Requirement: HGN-04 STATE.md refreshed

`STATE.md` MUST reflect current reality (workflow, test counts) or be deleted; stale claims (e.g. poetry, 630 tests) MUST NOT remain.

#### Scenario: STATE.md matches repo
- GIVEN the updated document
- WHEN it is read
- THEN workflow and test counts match the repo

**Acceptance**: no stale documentation.
