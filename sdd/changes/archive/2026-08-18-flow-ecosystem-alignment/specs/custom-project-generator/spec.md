# Delta for custom-project-generator

## ADDED Requirements

### Requirement: Pipeline Builder Integration (G2)

The builder stage MUST render a `CustomProject` via `customproject/generator.py:45` (multi-task `.cfx`: `config.xml` + per-task XML, schema `144.2953`) when the `QUANTLAB_CUSTOM_PROJECT` flag is enabled, and MUST register a `custom_project` stage in `StageRegistry` (pipeline/registry.py). The flag MUST default to the legacy path until golden tests (`tests/customproject/`, `tests/cfx/`) are deliberately re-based; then it SHALL flip to CustomProject as the flow default. No silent breakage MAY occur.

#### Scenario: Flag on renders CustomProject

- GIVEN `QUANTLAB_CUSTOM_PROJECT=1` and re-based goldens
- WHEN the builder stage runs
- THEN the archive contains `config.xml` and per-task XML files
- AND the schema version is 144.2953

#### Scenario: Flag off keeps legacy output

- GIVEN the legacy default (or `QUANTLAB_CUSTOM_PROJECT=0`)
- WHEN the builder stage runs
- THEN the single-task dialect output is unchanged
- AND existing golden tests still pass byte-identically

### Requirement: CustomProject Stage Registration (G2)

`custom_project` MUST be a registered stage type in `StageRegistry` before the flag flips, so `build_pipeline` can instantiate it.

#### Scenario: Stage lookup succeeds

- GIVEN the updated registry
- WHEN `StageRegistry.lookup("custom_project")` is called
- THEN the CustomProject stage class is returned