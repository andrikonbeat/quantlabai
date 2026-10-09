# Deployment Agent Specification

## Purpose

Packages portfolio CFX for JForex via jforex-deploy, generates JCloud deployment configuration, validates deployment via dry-run, and manages deployment artifacts.

---

## Requirements

### Requirement: JForex Package Generation

The system MUST convert portfolio CFX into a JForex-compatible JAR/WAR artifact using jforex-deploy.

#### Scenario: Valid portfolio CFX packages to JAR
- GIVEN portfolio_cfx with strategies, weights, PortfolioSettings
- WHEN DeploymentAgent.package_for_jforex() called
- THEN JAR file created at deploy/{campaign_id}/portfolio.jar
- AND JAR contains: compiled strategies, portfolio.xml, jforex.properties

#### Scenario: CFX modification at deploy time
- GIVEN portfolio_cfx, deploy-time adjustments: slippage=1.5, commission=0.8
- WHEN DeploymentAgent.package_for_jforex(adjustments=...) called
- THEN cfx_editor.modify() applies adjustments before packaging
- AND resulting JAR reflects modified parameters

### Requirement: JCloud Configuration Generation

The system MUST generate JCloud deployment manifest (YAML) with instance sizing, region, strategy mapping, and monitoring config.

#### Scenario: JCloud config generated
- GIVEN campaign_id, portfolio_jar_path, target_region="eu-central-1"
- WHEN DeploymentAgent.generate_jcloud_config() called
- THEN jcloud_config.yaml with:
  - instance_type: "t3.medium" (configurable)
  - strategies: list with strategy_id, weight, params
  - monitoring: {enabled: true, metrics_port: 9090}
  - auto_restart: true, max_restarts: 3

#### Scenario: Config validates against JCloud schema
- GIVEN generated jcloud_config.yaml
- WHEN DeploymentAgent.validate_jcloud_config() called
- THEN validation passes: required fields present, types correct

### Requirement: Dry-Run Verification

The system MUST support dry-run mode that validates packaging and config without uploading to JCloud.

#### Scenario: Dry-run succeeds
- GIVEN portfolio_cfx, dry_run=True
- WHEN DeploymentAgent.deploy(dry_run=True) called
- THEN package_for_jforex() executes, JAR created
- AND generate_jcloud_config() executes, config validated
- AND NO upload to JCloud, NO live trading started
- AND DeploymentResult: status=DRY_RUN_SUCCESS, artifact_paths=[jar, yaml]

#### Scenario: Dry-run catches config error
- GIVEN invalid portfolio_cfx (missing strategy reference)
- WHEN DeploymentAgent.deploy(dry_run=True) called
- THEN DeploymentResult: status=DRY_RUN_FAILED, errors=["Strategy 's2' not found in CFX"]

### Requirement: Live Deployment Execution

The system MUST upload artifacts to JCloud and start instances when not in dry-run.

#### Scenario: Live deployment uploads and starts
- GIVEN valid artifacts, dry_run=False, JCloud credentials configured
- WHEN DeploymentAgent.deploy(dry_run=False) called
- THEN JAR uploaded to JCloud storage
- AND jcloud_config applied, instances provisioned
- AND DeploymentResult: status=DEPLOYED, instance_ids=[], endpoint_url

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| JAR contains all strategies and portfolio.xml | Integration: unzip JAR, assert files exist |
| JCloud config passes schema validation | Unit test: jsonschema.validate(config, schema) |
| Dry-run produces artifacts without upload | Unit test: mock upload, assert not called |
| CFX modifications applied before packaging | Unit test: adjust slippage, assert modified CFX |
| Live deployment returns instance IDs | Integration: mock JCloud API, assert response parsed |

---

## Non-Functional Requirements

- **Dependencies**: jforex-deploy, cfx-editor
- **Security**: JCloud credentials via env vars / secret manager, never in config
- **Idempotency**: Re-deploy with same campaign_id updates existing deployment
- **Rollback**: DeploymentResult includes previous version for rollback capability