# Delta for deploy

## ADDED Requirements

### Requirement: Deployable Package Production (REQ-611)

The system MUST provide `DeploymentAgent.package_jfx()` that produces a deployable artifact consisting of a JAR with embedded `.jfx` and a `jcloud.json` manifest.

#### Scenario: Package produces JAR and manifest

- GIVEN a compiled `.jfx` at `/out/strat.jfx`
- WHEN `package_jfx()` runs
- THEN `/out/strat.jar` is produced
- AND `/out/jcloud.json` manifest is written with artifact metadata

**Acceptance**: JAR exists and contains .jfx; manifest is valid JSON.

**Error behavior**: Missing .jfx raises FileNotFound before packaging starts.

#### Scenario: Manifest includes strategy metadata

- GIVEN strategy_id "s1" and jcloud config
- WHEN `package_jfx()` runs
- THEN jcloud.json includes strategy_id, version, and target environment

**Acceptance**: Manifest fields match input config.

**Error behavior**: Invalid config blocks packaging with validation error.

#### Scenario: Dry-run produces inspectable mock

- GIVEN dry_run=True
- WHEN `package_jfx()` runs
- THEN no network call occurs
- AND a mock JAR is produced for inspection

**Acceptance**: Mock JAR exists; no external I/O.

**Error behavior**: Network attempt in dry-run is a test failure.

### Requirement: JCloud Deploy Interface (REQ-612)

The system MUST define `JCloudDeployClient` as an abstract interface with `deploy(jfx_path, strategy_id, config)` and `status(instance_id)` methods; a simulated implementation ships first, and the real implementation is deferred.

#### Scenario: Interface enforces contract

- GIVEN JCloudDeployClient ABC
- WHEN a subclass is created without deploy()
- THEN instantiation raises TypeError
- AND the missing method is named in the error

**Acceptance**: ABC enforces both methods at instantiation or call time.

**Error behavior**: Missing method raises NotImplementedError or TypeError.

#### Scenario: Simulated deploy returns instance ID

- GIVEN SimulatedJCloudDeployClient
- WHEN `deploy("/out/s.jfx", "s1", config)` is called
- THEN an instance_id string is returned
- AND no network call is made

**Acceptance**: Instance ID is stable for the session; config is recorded.

**Error behavior**: Real API path raises NotImplementedError with explicit message.

#### Scenario: Status returns simulated state

- GIVEN a simulated instance_id from deploy()
- WHEN `status(instance_id)` is called
- THEN a DeploymentStatus enum is returned (PENDING, RUNNING, STOPPED)

**Acceptance**: Status transitions are deterministic in simulation.

**Error behavior**: Unknown instance_id raises InstanceNotFoundError.

### Requirement: Deploy Result Emission (REQ-613)

The deploy stage MUST emit a `deployment_result` artifact containing the artifact path and instance ID (real or simulated).

#### Scenario: Successful deploy emits result

- GIVEN a packaged JAR and JCloud config
- WHEN deploy stage completes
- THEN deployment_result contains artifact_path and instance_id
- AND the instance_id matches the deploy client output

**Acceptance**: Artifact path is absolute; instance_id is non-empty string.

**Error behavior**: Failed deploy emits deployment_failed with error cause.

#### Scenario: Simulated deploy emits result

- GIVEN SimulatedJCloudDeployClient is configured
- WHEN deploy stage completes
- THEN deployment_result contains simulated instance_id
- AND no real network call occurred

**Acceptance**: Result structure identical for real and simulated paths.

**Error behavior**: Simulation mode is explicit in artifact metadata.
