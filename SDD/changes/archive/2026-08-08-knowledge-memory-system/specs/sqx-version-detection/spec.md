# SQX Version Detection Specification

## Purpose

Detect the installed SQX build, compare it against a single pinned constant, warn on drift (fail-open, never blocking), produce a migration checklist, and invalidate affected KB parameters.

## Requirements

### Requirement: REQ-301 Build Number Parsing

The system MUST parse the build number from `sqcli -license` output (e.g., "StrategyQuant X Ultimate Build 144 (Futlab license)") into `LicenseInfo.build_number`. The parser SHALL extract the build number and, when present, the point version; expiry parsing remains unchanged.

#### Scenario: Parses build from license output

- GIVEN output "StrategyQuant X Ultimate Build 144 (Futlab license) - valid until 14.08.2026"
- WHEN LicenseInfo parses it
- THEN build_number equals the pinned format "144.2953" (or "144" if the point version is absent)
- AND expiry_date remains populated

#### Scenario: Unparseable output

- GIVEN license output without a Build token
- WHEN parsing runs
- THEN build_number is null, a warning is logged, and no exception is raised

### Requirement: REQ-302 Pinned Version Constant

The system MUST define a single central `PINNED_SQX_VERSION` constant (default "144.2953"). The version MUST NOT be hardcoded elsewhere; the 23 references across `cfx/`, dashboard, `customproject/`, `sqx/`, and `phase4/` SHALL resolve through this constant.

#### Scenario: Single source of truth

- GIVEN a version-aware code path
- WHEN the version is needed
- THEN it is read from PINNED_SQX_VERSION, not from a literal

#### Scenario: Constant change propagates

- GIVEN the pinned constant updated to a new value
- WHEN any version-aware path runs
- THEN all consumers observe the new value

### Requirement: REQ-303 Preflight Hook (fail-open)

The system MUST run a version check in `cli_wrapper._dispatch_real` alongside `license_preflight`, before any SQX project work, comparing installed build vs pinned. On mismatch the system MUST warn only — it MUST NOT block or mock dispatch. Dry-run/mock paths SHALL skip the check.

#### Scenario: Matching version proceeds silently

- GIVEN installed build equals pinned
- WHEN a real dispatch starts
- THEN no version warning is emitted and dispatch proceeds

#### Scenario: Drift warns but proceeds

- GIVEN installed build differs from pinned
- WHEN a real dispatch starts
- THEN a prominent drift warning is logged and dispatch proceeds

#### Scenario: Mock path skips check

- GIVEN SQX_FORCE_MOCK set or sqcli not found
- WHEN a command dispatches
- THEN no version check runs

### Requirement: REQ-304 check-version CLI

The system MUST provide `quantlab sqx check-version`, printing installed build, pinned build, and status (`in-sync | drift | unknown`). Exit code SHALL be 0 for in-sync and 1 for drift.

#### Scenario: In-sync report

- GIVEN installed build equals pinned
- WHEN check-version runs
- THEN it prints in-sync with both versions and exits 0

#### Scenario: Drift report

- GIVEN installed build differs from pinned
- WHEN check-version runs
- THEN it prints drift with both versions and exits 1

#### Scenario: Unknown when sqcli unavailable

- GIVEN no sqcli binary and no override
- WHEN check-version runs
- THEN it prints unknown and exits 0 (fail-open)

### Requirement: REQ-305 Drift Response Workflow

On detected drift, the system MUST: (1) notify the user; (2) run a CodeGraph impact scan over version-dependent code; (3) write a migration checklist to `structured/sqx-version/{old}→{new}/checklist.yaml`; (4) trigger KB invalidation (REQ-208). Changelog polling, auto-migration, and blocking are out of scope.

#### Scenario: Drift produces checklist

- GIVEN drift 144.2953 → 145.0 detected
- WHEN the drift workflow runs
- THEN a checklist.yaml exists at `structured/sqx-version/144.2953→145.0/`
- AND it lists affected files from the CodeGraph impact scan
- AND all 144.2953 KB params are marked needs_review

#### Scenario: Re-run is additive

- GIVEN an existing checklist for the same transition
- WHEN the workflow runs again
- THEN the checklist is updated in place, not duplicated
