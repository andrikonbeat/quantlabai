# Delta for pipeline-core

## ADDED Requirements

### Requirement: Stage Registry as Canonical Source (G5)

`StageRegistry` (pipeline/registry.py) MUST be the authoritative source of registered stage types; fixed abstract-stage counts in docs (including the retired "17 abstract stages" wording) MUST be superseded. A stage MUST be registered before `build_pipeline` can use it.

#### Scenario: Registry is the source of truth

- GIVEN the current StageRegistry
- WHEN stage types are enumerated
- THEN the enumerated set matches what `build_pipeline` can instantiate
- AND doc counts are not consulted

#### Scenario: Unregistered stage rejected

- GIVEN a stage name absent from the registry
- WHEN `StageRegistry.lookup()` is called
- THEN `RegistryError` is raised