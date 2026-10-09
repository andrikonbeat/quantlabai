# Demo Deploy Specification

## Purpose

Deploys a compiled strategy to a 100 USD Dukascopy demo account within the 14 business-day demo window, using JCloud configuration and a real DeploymentAgent package (replacing the placeholder). Data scope is Dukascopy-only.

## Requirements

### Requirement: Demo Deploy Window (REQ-31)

The system MUST deploy to the Dukascopy demo account and complete within the 14 business-day demo window. Renewal SHALL be semi-manual: a reminder MUST fire before expiry, and re-deploy SHALL require a human gate (`HUMAN_APPROVE_DEMO`, REQ-38).

#### Scenario: Deploy completes inside window

- GIVEN an approved deploy gate and a demo account
- WHEN the demo phase runs
- THEN the strategy is deployed and verified live within 14 business days
- AND a renewal reminder is scheduled before expiry

#### Scenario: Window expiry fails closed

- GIVEN the demo window expired
- WHEN renewal is attempted
- THEN deployment blocks pending HUMAN_APPROVE_DEMO
- AND a renewal reminder is dispatched

### Requirement: JCloud Config and Packaging (REQ-32)

The system MUST package the strategy via DeploymentAgent into a real deployable JAR (replacing the placeholder) and MUST apply JCloud configuration (account, server, symbols). Dry-run MUST produce a mock package without network calls.

#### Scenario: Real packaging

- GIVEN compiled `.jfx` and JCloud config
- WHEN DeploymentAgent packages
- THEN a deployable JAR is produced with the `.jfx` embedded
- AND JCloud config is applied

#### Scenario: Dry-run mock package

- GIVEN DeploymentAgent with dry_run=True
- WHEN packaging runs
- THEN no network call occurs
- AND a mock JAR is produced for inspection
