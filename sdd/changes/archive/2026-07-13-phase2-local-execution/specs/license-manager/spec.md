# License Manager Specification

## Purpose

Detects and reports StrategyQuant SQX license state via `sqcli -license action=info`. Used by CampaignRunner at startup to verify execution eligibility. Supports license activation for trial-to-licensed upgrades.

## Requirements

### Requirement: License Detection

The system MUST detect the SQX license state by executing `sqcli -license action=info` and parsing the output. The system SHALL report one of: `licensed`, `unlicensed`, `expired`, or `trial`.

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

The CampaignRunner MUST check license status at startup. If the status is `unlicensed` or `expired`, the runner SHALL raise a LicenseError and abort the campaign.

#### Scenario: Unlicensed startup aborts campaign

- GIVEN an unlicensed SQX installation
- WHEN CampaignRunner starts a campaign
- THEN a LicenseError is raised
- AND no sqcli commands beyond the license check are dispatched

#### Scenario: Licensed startup proceeds normally

- GIVEN a licensed SQX installation
- WHEN CampaignRunner starts a campaign
- THEN the license check passes
- AND the campaign proceeds to the translate phase

