# Pipeline Error Types Specification

## Purpose

Pipeline-specific error hierarchy extending `QuantLabError` for the local execution pipeline. Enables callers to catch pipeline errors distinctly from translation, parsing, or timeout errors.

## Requirements

### Requirement: LicenseError

The system MUST define a `LicenseError` extending `QuantLabError`. It SHALL be raised when the SQX license is missing, expired, or invalid for the requested operation.

#### Scenario: LicenseError is raised for missing license

- GIVEN an unlicensed SQX installation
- WHEN CampaignRunner checks license at startup
- THEN a LicenseError is raised with detail "SQX license not found"
- AND the error is catchable as `QuantLabError` and as `LicenseError`

#### Scenario: LicenseError is raised for expired license

- GIVEN an SQX installation with an expired license
- WHEN CampaignRunner checks license at startup
- THEN a LicenseError is raised with detail including the expiry date
- AND the error is catchable as `QuantLabError` and as `LicenseError`

### Requirement: CampaignError

The system MUST define a `CampaignError` extending `QuantLabError`. It SHALL be raised when a campaign fails, times out, or is misconfigured. The error SHALL carry the phase name where the failure occurred.

#### Scenario: CampaignError raised on timeout

- GIVEN a campaign that exceeds the poll timeout
- WHEN the orchestrator detects the timeout
- THEN a CampaignError is raised with detail including the phase name and timeout duration
- AND the error is catchable as `QuantLabError` and as `CampaignError`

#### Scenario: CampaignError raised on export failure

- GIVEN a campaign where the databank export command fails
- WHEN the orchestrator attempts to export results
- THEN a CampaignError is raised with detail including the export type and error message
- AND the error carries the phase name "export"

#### Scenario: CampaignError raised on misconfiguration

- GIVEN a ResearchConfig with missing required fields
- WHEN the orchestrator validates the config before translation
- THEN a CampaignError is raised with detail identifying the missing field
- AND the error carries the phase name "validate"

