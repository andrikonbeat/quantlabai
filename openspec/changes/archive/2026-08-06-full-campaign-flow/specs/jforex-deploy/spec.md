# Delta for jforex-deploy

## ADDED Requirements

### Requirement: Compiled Artifact Deployment (REQ-39)

Beyond `.java` export, the deploy path MUST route exported sources through the compiler pipeline (REQ-29) and package the result as `.jfx`; DeploymentAgent MUST produce a real deployable JAR (replacing the placeholder) for the demo phase (REQ-32). Dry-run SHALL produce mock `.jfx`/JAR without HTTP calls.

#### Scenario: Export then compile to .jfx

- GIVEN a strategy exported as `.java`
- WHEN the deploy path continues
- THEN the compiler pipeline produces a `.jfx`
- AND DeploymentAgent packages a real JAR

#### Scenario: Compile failure blocks deploy

- GIVEN a `.java` that fails compilation
- WHEN the fix loop (REQ-30) exhausts its bound
- THEN deployment is blocked with the compile error
- AND no JAR is produced
