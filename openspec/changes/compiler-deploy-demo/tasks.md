# Tasks: Compiler-Deploy-Demo Integration (ultra-small WUs ≤150L)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~900 total across 11 WUs |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1a (WU1+WU2, ≤400) → PR1b (WU3+WU4, ≤400) → PR2a (WU5, ≤400) → PR2b (WU6, ≤400) → PR3a (WU7a+WU7b, ≤400) → PR3b (WU8, ≤400) → PR3c (WU9, cleanup) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

## Committed Slices (already on main)

| WU | Commit | Files | Lines | Status |
|----|--------|-------|-------|--------|
| WU1 | `8c327a5` | http_client.py + test_http_client.py | 155 | ✅ committed |
| WU2 | `d6936f6` | compiler.py + test_compiler.py | 315 | ✅ committed |
| WU3 | `2d2c008` | deployment_agent.py + test_jcloud_client.py | 225 | ✅ committed |
| WU4 | `1024930` | data/demo/__init__.py + store.py + test_demo_store.py | 196 | ✅ committed |
| WU5 | `d9551ab` | test_jforex_routing.py | 48 | ✅ committed |
| WU6 | `d20ea99` | deploy_stage.py + test_deploy_stage.py | 358 | ✅ committed |

Total committed: 1297 lines across 6 WUs.

## Remaining Work Units (ultra-small ≤150L)

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| WU7a | DemoStage fail-closed expiry guard | PR3a | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk rtk pytest -q tests/pipeline/test_demo_stage.py --tb=short` | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/pipeline/test_demo_stage.py` | Revert `sdk/quantlab/pipeline/stages/demo_stage.py`, `tests/pipeline/test_demo_stage.py` |
| WU7b | DemoWindowStore persistence wiring into DemoStage | PR3a | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk rtk pytest -q tests/pipeline/test_demo_stage.py --tb=short` | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/pipeline/test_demo_stage.py` | Revert `sdk/quantlab/pipeline/stages/demo_stage.py`, `tests/pipeline/test_demo_stage.py` |
| WU7c | DeployStage→DemoStage artifact connection + integration test | PR3a | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk rtk pytest -q tests/pipeline/test_compile_deploy_demo.py --tb=short` | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/pipeline/test_compile_deploy_demo.py` | Revert `tests/pipeline/test_compile_deploy_demo.py`, minor demo_stage.py changes |
| WU8a | BuilderAgent 14-phase config core | PR3b | `QUANTLAB_14PHASE=1 SQX_FORCE_MOCK=1 PYTHONPATH=sdk rtk pytest -q tests/agents/test_builder_agent.py --tb=short` | `QUANTLAB_14PHASE=1 SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/agents/test_builder_agent.py` | Revert `sdk/quantlab/agents/builder_agent.py`, `tests/agents/test_builder_agent.py` |
| WU8b | BuilderAgent 14-phase contract tests | PR3b | `QUANTLAB_14PHASE=1 SQX_FORCE_MOCK=1 PYTHONPATH=sdk rtk pytest -q tests/contract/test_pipeline_config.py --tb=short` | `QUANTLAB_14PHASE=1 SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/contract/test_pipeline_config.py` | Revert `tests/contract/test_pipeline_config.py` |
| WU9 | Cleanup: docstrings + comments + remove debug logging | PR3c | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk rtk pytest -q tests/ --tb=short` (sanity) | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/ --tb=short` | Revert docstring/comment changes in demo_stage.py, deploy_stage.py, compiler.py |

## Phase 0: Research

- [ ] 0.1 Confirm SQX `/sourcecode/print` endpoint path and auth with SQX team
- [ ] 0.2 Verify Knowledge Lake path convention for `structured/demo/{campaign_id}/window.yaml`

## Phase 1: Foundation

- [x] 1.1 Create `sdk/quantlab/data/demo/__init__.py` and `sdk/quantlab/data/demo/store.py` — **WU4 committed**
- [x] 1.2 Add `JCloudDeployClient` ABC, `SimulatedJCloudDeployClient`, `DeploymentStatus` enum — **WU3 committed**

## Phase 2: Core Implementation

- [x] 2.1 Add `AsyncSQXClient.export_sourcecode()` — **WU1 committed**
- [x] 2.2 Extend `CompilerPipeline.compile()` with `strategy_ids` — **WU2 committed**
- [x] 2.3 JForexDeployer wiring verified — **WU5 committed**
- [x] 2.4 Add `DemoWindow.persist()`/`load()` and fail-closed expiry guard — **WU7a a79c5a9 + WU7b cd9df61**
- [x] 2.5 Update `DeployStage` to accept `strategy_ids` — **WU6 committed**
- [x] 2.6 Append compile/deploy/demo/archive/live_ops phases in `BuilderAgent` — **WU8a**

## Phase 3: Integration

- [x] 3.1 Connect `CompileStage` → `DeployStage` via `.jfx` artifact paths — **WU6 committed**
- [x] 3.2 Connect `DeployStage` → `DemoStage` via `deployment_result` artifact — **WU7c**
- [x] 3.3 Wire `DemoWindowStore` persistence into `DemoStage` lifecycle — **WU7b**
- [x] 3.4 Ensure `BuilderAgent.generate_pipeline_config()` emits 14-phase config — **WU8a**

## Phase 4: Testing (TDD: RED → GREEN → REFACTOR)

- [x] 4.1–4.2 export_sourcecode tests — **WU1 committed**
- [x] 4.3–4.4 strategy_id mapping tests — **WU2 committed**
- [x] 4.5–4.6 DemoWindowStore tests — **WU4 committed**
- [x] 4.7–4.8 JCloudDeployClient ABC tests — **WU3 committed**
- [x] 4.13–4.14 JForexDeployer wiring tests — **WU5 committed**
- [x] 4.11–4.12 DeployStage wiring tests — **WU6 committed**
- [x] 4.9–4.10 Expired window fail-closed, active window allow, dry-run default — **WU7a committed a79c5a9**
- [x] 4.17 Integration: compile→deploy→demo end-to-end — **WU7c committed**
- [x] 4.15–4.16 14-phase emission order/determinism, backward-compat 8-phase — **WU8a committed**
- [x] 4.18 Contract: 14-phase vs 8-phase — **WU8b committed**

## Phase 5: Cleanup

- [x] 5.1 Update docstrings for new public methods and classes — **WU9 (no changes needed)**
- [x] 5.2 Add inline comments for fail-closed expiry logic — **WU9 (already present in demo_stage.py)**
- [x] 5.3 Remove temporary debug logging — **WU6 committed**

## TDD Cycle Evidence

| Work Unit | RED | GREEN | REFACTOR |
|-----------|-----|-------|----------|
| WU1 | 4.1 | 4.2 | Inline during 4.2 |
| WU2 | 4.3 | 4.4 | Inline during 4.4 |
| WU3 | 4.7 | 4.8 | Inline during 4.8 |
| WU4 | 4.5 | 4.6 | Inline during 4.6 |
| WU5 | 4.13 | 4.14 | None needed |
| WU6 | 4.11 | 4.12 | Inline during 4.12 |
| WU7a | 4.9 | 4.10 | Inline during 4.10 |
| WU7b | 4.9 (persistence) | 4.10 (persistence) | Inline during 4.10 |
| WU7c | 4.17 | — | — |
| WU8a | 4.15 | 4.16 | Inline during 4.16 |
| WU8b | 4.18 | — | — |
| WU9 | — | — | Cleanup |
