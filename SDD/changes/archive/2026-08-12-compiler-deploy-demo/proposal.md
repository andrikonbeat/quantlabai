# Proposal: Compiler-Deploy-Demo Integration

## Intent
`AsyncSQXClient` lacks `export_sourcecode()`, blocking compiler critical path. `BuilderAgent` emits a stale 8-stage pipeline; demo state is not persisted; JCloud has no real interface. This change closes all four gaps so compile→deploy→demo executes end-to-end.

## Scope
**In:** `AsyncSQXClient.export_sourcecode()`, strategy ID wiring in `CompilerPipeline`, demo window state persistence, `JCloudDeployClient` interface, `BuilderAgent` 14-phase config, demo fail-closed expiry guard.
**Out:** Replace existing stages, real JCloud API, SQX CLI changes.

## Requirements
REQ-60: `AsyncSQXClient` MUST expose `export_sourcecode(strategy_id) -> Path`.
REQ-61: `CompilerPipeline` MUST accept `strategy_id` per run.
REQ-62: `DemoWindowState` MUST persist `started_at`/`expires_at` atomically.
REQ-63: Demo stage MUST fail closed on expired 14-business-day window.
REQ-64: `JCloudDeployClient` MUST define `deploy(jfx_path, strategy_id, config)` with simulation fallback.
REQ-65: `BuilderAgent.generate_pipeline_config()` MUST emit 14 phases additively.
REQ-66: All new paths MUST have strict TDD under `SQX_FORCE_MOCK=1`.

## Non-goals
No stage replacement. No real JCloud API. No SQX CLI or Dukascopy provisioning changes.

## Architecture
- `sdk/quantlab/client.py` — add `AsyncSQXClient.export_sourcecode()`
- `sdk/quantlab/compiler/compiler.py` — accept `strategy_id`
- `sdk/quantlab/phase4/jforex_deploy.py` — use new client
- `sdk/quantlab/deploy/jcloud_client.py` — new `JCloudDeployClient`
- `sdk/quantlab/phase4/demo_deploy.py` — persist state + expiry guard
- `sdk/quantlab/agents/builder_agent.py` — 14-phase pipeline config

Key classes: `AsyncSQXClient.export_sourcecode()`, `JCloudDeployClient.deploy()`, `DemoWindowState.persist()/load()`, `BuilderAgent.generate_pipeline_config()`.

Stage I/O: Compile (source+id → .jfx), Deploy (.jfx+id+target → deployment_id), Demo (deployment_id → status+state).

## Risks
- SQX API drift (M): Version endpoint, fail closed on unknown shape.
- Builder backward compat (M): Additive merge, flag-gated 14-phase default.
- Demo state corruption (L): Atomic write with temp+rename, validate on load.
- JCloud stub treated as prod (M): NotImplementedError on real paths, explicit docs.
- strategy_id mapping mismatch (L): Tolerate missing ID, fallback to filename inference.

## Rollback Plan
Revert commits in reverse PR order. Demo state and JCloud interface are additive; removing them leaves prior behavior intact.

## Dependencies
- SQX server with `sourcecode/print` endpoint during compile
- Knowledge Lake for demo state persistence

## Success Criteria
- [ ] `AsyncSQXClient.export_sourcecode()` returns Path
- [ ] `CompilerPipeline` compiles per strategy_id
- [ ] `DemoWindowState` survives restart
- [ ] Demo stage blocks on expired window
- [ ] `JCloudDeployClient` exists with simulation mode
- [ ] `BuilderAgent` emits 14 stages
- [ ] TDD green under `SQX_FORCE_MOCK=1`

## Suggested Slicing
- PR 1: Compiler critical path — `AsyncSQXClient.export_sourcecode()` + strategy_id wiring.
- PR 2: Deploy interface + demo persistence — `JCloudDeployClient` + `DemoWindowState` + fail-closed guard.
- PR 3: Pipeline config + integration — `BuilderAgent` 14-phase emission + wiring.

## Capabilities
- `jcloud-deploy` (new): Real API client interface + simulation mode for JCloud strategy deployment.
- `jforex-deploy` (modified): Use `AsyncSQXClient.export_sourcecode()` instead of missing workaround.
- `demo-deploy` (modified): Add state persistence and fail-closed expiry guard.
- `compiler-pipeline` (modified): Accept strategy_id per compile run.
- `builder-agent` (modified): Emit full 14-phase pipeline config.
