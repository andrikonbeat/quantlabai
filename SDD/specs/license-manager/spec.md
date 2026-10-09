# License Manager Specification

## Purpose

Detects and reports StrategyQuant SQX license state via `sqcli -license action=info`. Used by CampaignRunner at startup to verify execution eligibility. Supports license activation for trial-to-licensed upgrades.

## Requirements

### Requirement: License Detection

The system MUST detect the SQX license state by executing `sqcli -license action=info` and parsing the output. The system SHALL report one of: `licensed`, `unlicensed`, `expired`, or `trial`. The parser SHALL additionally extract `build_number` (e.g., "144.2953") and `expiry_date` as structured fields; a missing build token MUST yield `build_number = null` without raising.
(Previously: parsed license type and expiry only; no build_number extraction)

#### Scenario: Licensed installation detected

- GIVEN a licensed SQX installation
- WHEN the license manager executes `sqcli -license action=info`
- THEN the reported status is `licensed`
- AND the result includes the license type and expiry date

#### Scenario: Unlicensed installation detected

- GIVEN an SQX installation with no license
- WHEN the license manager executes `sqcli -license action=info`
- THEN the reported status is `unlicensed`
- AND the result indicates no active license found

#### Scenario: Expired license detected

- GIVEN an SQX installation with an expired license
- WHEN the license manager executes `sqcli -license action=info`
- THEN the reported status is `expired`
- AND the result includes the original expiry date

#### Scenario: Trial license detected

- GIVEN an SQX installation on a trial license
- WHEN the license manager executes `sqcli -license action=info`
- THEN the reported status is `trial`
- AND the result includes remaining trial days

#### Scenario: Build number parsed into structured field

- GIVEN output "StrategyQuant X Ultimate Build 144 (Futlab license) - valid until 14.08.2026, license FUTLABF255"
- WHEN LicenseInfo parses it
- THEN build_number equals the pinned format "144.2953" (or "144" if the point version is absent)
- AND expiry_date equals 2026-08-14

#### Scenario: Missing build token yields null

- GIVEN license output without a Build token
- WHEN LicenseInfo parses it
- THEN build_number is null, a warning is logged, and no exception is raised

### Requirement: License Activation

The system SHOULD support license activation via `sqcli -license action=update code=<activation_code>`. Activation SHALL be idempotent — re-activating with the same code MUST NOT error.

#### Scenario: Valid activation code activates license

- GIVEN an unlicensed SQX installation and a valid activation code
- WHEN the license manager activates with the code
- THEN `sqcli -license action=update code=<code>` is executed
- AND a subsequent license detection reports `licensed`

#### Scenario: Re-activation with same code is idempotent

- GIVEN an already-licensed SQX installation
- WHEN the license manager activates with the same code again
- THEN no error is raised
- AND the license status remains `licensed`

### Requirement: Startup Guard

The system MUST run `LicenseManager.check()` as a pre-flight on REAL dispatch (mock path skips it). Non-LICENSED status SHALL log a warning with detail; the run SHALL block (raise) only when `QUANTLAB_ENV=production`. (Previously: CampaignRunner raised LicenseError at startup for unlicensed/expired regardless of environment)

#### Scenario: Production unlicensed aborts
- GIVEN production env and unlicensed SQX
- WHEN a real dispatch starts
- THEN a LicenseError is raised and no sqcli commands beyond the license check run

#### Scenario: Production licensed proceeds
- GIVEN production env and a licensed SQX
- WHEN a real dispatch starts
- THEN the check passes and the run proceeds

#### Scenario: Dev unlicensed warns only
- GIVEN non-production env and unlicensed SQX
- WHEN a real dispatch starts
- THEN a warning with detail is logged and the run proceeds

#### Scenario: Mock path skips check
- GIVEN mock dispatch (SQX_FORCE_MOCK)
- WHEN a command dispatches
- THEN no license check runs

**Acceptance**: license guard active on real dispatch in production (proposal success criterion).

### Requirement: LIC-02 SQX_LICENSE override + raw logging

The system MUST accept the `SQX_LICENSE` env value as a passed-through license status override (CI/dev) and MUST always log the raw `sqcli -license action=info` output. No real-format parsing is required.

#### Scenario: Env override short-circuits
- GIVEN `SQX_LICENSE=licensed`
- WHEN check() runs
- THEN the override value is reported without invoking sqcli

#### Scenario: Raw output logged
- GIVEN a real license check
- WHEN check() executes sqcli
- THEN the raw output is logged for diagnosis

**Acceptance**: env override works; raw output visible in logs.
