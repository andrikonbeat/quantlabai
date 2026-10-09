# Delta for SQX CLI Wrapper

Change: add a warn-only SQX version preflight hook to real dispatch, alongside the existing license preflight.

## ADDED Requirements

### Requirement: REQ-701 Version Preflight Hook

The system MUST run a version preflight in `cli_wrapper._dispatch_real` alongside `license_preflight`, before any SQX project work. The preflight SHALL compare the installed build (REQ-301) against `PINNED_SQX_VERSION` (REQ-302) and SHALL be warn-only (fail-open): drift MUST NOT block or mock dispatch. Dry-run/mock paths SHALL skip the preflight.

#### Scenario: In-sync preflight is silent

- GIVEN installed build equals pinned
- WHEN `_dispatch_real` starts
- THEN no version warning is emitted and dispatch continues

#### Scenario: Drift warns only

- GIVEN installed build differs from pinned
- WHEN `_dispatch_real` starts
- THEN a drift warning is logged and dispatch continues (fail-open)

#### Scenario: Missing sqcli skips preflight

- GIVEN no sqcli binary found at the install path
- WHEN `_dispatch_real` starts
- THEN the preflight is skipped with a warning, mirroring license_preflight behavior
