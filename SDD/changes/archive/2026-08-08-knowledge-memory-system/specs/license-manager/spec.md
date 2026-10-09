# Delta for License Manager

Change: extend license parsing to expose a structured `build_number` field alongside the existing status/expiry fields, feeding the SQX version detection capability.

## MODIFIED Requirements

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
