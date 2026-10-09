# Test Suite Specification

## Purpose

Defines the canonical test tree and green-suite contract: bare `pytest` from the repo root collects both `tests/` and `sdk/tests/`, avoids assets/venv/build crawl, and passes with zero failures once the in-scope fixes land.

## Requirements

### Requirement: TST-01 Canonical tree and green suite

The ROOT tree is canonical: bare `pytest` from repo root MUST collect both `tests/` and `sdk/tests/` and pass ~1315 tests with 0 failures once news, guardian, and stats fixes land.

#### Scenario: Bare pytest green
- GIVEN news implemented, guardian imports fixed, stats test updated
- WHEN `pytest` runs from repo root
- THEN ~1315 tests pass, 0 fail, 0 collection errors

#### Scenario: CI runs the same command
- GIVEN CI test job
- WHEN it runs the root pytest command after `pip install -e "sdk[dev]"`
- THEN the full suite (incl. root `tests/`) is exercised

**Acceptance**: ~1315 pass / 0 fail (proposal success criterion).

### Requirement: TST-02 pytest.ini testpaths/norecursedirs

Root `pytest.ini` MUST set `testpaths` and `norecursedirs` so bare pytest never crawls `assets/`, venvs, or build dirs.

#### Scenario: No asset crawl
- GIVEN `assets/` contains numpy blobs and bundled tests
- WHEN bare `pytest` runs
- THEN collection avoids `assets/` and completes without crash

**Acceptance**: bare pytest reaches only test trees.

### Requirement: TST-03 Guardian imports fixed

`sdk/tests/test_guardian/*` MUST import `from quantlab.guardian...` (drop the `sdk.` prefix) so all 8 files collect.

#### Scenario: Guardian suite collects
- GIVEN corrected imports
- WHEN `pytest sdk/tests/test_guardian -q` runs
- THEN 0 collection errors; tests execute

**Acceptance**: 8 collection errors eliminated.

### Requirement: TST-04 Stats degrade semantics

`test_pr3_statistics_agent.py::test_run_missing_export_paths_raises` MUST assert the graceful-degrade behavior (empty statistics + warning) instead of `ValueError`.

#### Scenario: Missing export paths degrades
- GIVEN a statistics agent run without export_paths
- WHEN the test invokes it
- THEN empty statistics are returned, a warning is logged, and no exception is raised

**Acceptance**: stale expectation replaced.
