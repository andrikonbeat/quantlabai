# Apply Progress: compiler-deploy-demo (PR1a+PR1b+PR2+PR3, WU1..WU9)

## Status

- **Change**: compiler-deploy-demo
- **Mode**: Standard (safety-net commit slice)
- **Progress**: 9/9 WUs committed
- **Commits**:
  - WU1: `8c327a5` — feat(phase4): add AsyncSQXClient.export_sourcecode() (WU1)
  - WU2: `d6936f6` — feat(phase4): add CompilerPipeline strategy_ids batch compile (WU2)
  - WU3: `2d2c008` — feat(phase4): add JCloudDeployClient ABC + SimulatedJCloudDeployClient (WU3)
  - WU4: `1024930` — feat(phase4): add DemoWindowStore atomic persistence (WU4)
  - WU5: `d9551ab` — feat(phase4): add JForexDeployer wiring verification tests (WU5)
  - WU6: `d20ea99` — feat(pipeline): wire DeployStage to JCloudDeployClient per strategy_id (WU6)
  - WU7a: `a79c5a9` — feat(pipeline): add DemoStage fail-closed expiry guard (WU7a)
  - WU7b: `cd9df61` — feat(pipeline): wire DemoWindowStore persistence into DemoStage (WU7b)
  - WU7c: `ee14aa0` — feat(pipeline): add compile→deploy→demo integration tests (WU7c)
  - WU8a: `f8082c4` — feat(agents): add BuilderAgent 14-phase config gated by QUANTLAB_14PHASE (WU8a)
  - WU8b: `8cdb03a` — feat(contract): add BuilderAgent 14-phase pipeline contract tests (WU8b)

## Commits

| WU | Commit SHA | Message | Files |
|----|-----------|---------|-------|
| WU1 | `8c327a5` | feat(phase4): add AsyncSQXClient.export_sourcecode() | http_client.py + test |
| WU2 | `d6936f6` | feat(phase4): add CompilerPipeline strategy_ids batch compile | compiler.py + test |
| WU3 | `2d2c008` | feat(phase4): add JCloudDeployClient ABC + SimulatedJCloudDeployClient | deployment_agent.py + test |
| WU4 | `1024930` | feat(phase4): add DemoWindowStore atomic persistence | data/demo + test |
| WU5 | `d9551ab` | feat(phase4): add JForexDeployer wiring verification tests | test_jforex_routing.py |
| WU6 | `d20ea99` | feat(pipeline): wire DeployStage to JCloudDeployClient per strategy_id | deploy_stage.py + test |
| WU7a | `a79c5a9` | feat(pipeline): add DemoStage fail-closed expiry guard | demo_stage.py + test |
| WU7b | `cd9df61` | feat(pipeline): wire DemoWindowStore persistence into DemoStage | demo_stage.py + test |
| WU7c | `ee14aa0` | feat(pipeline): add compile→deploy→demo integration tests | test_compile_deploy_demo.py |
| WU8a | `f8082c4` | feat(agents): add BuilderAgent 14-phase config gated by QUANTLAB_14PHASE | builder_agent.py + test |
| WU8b | `8cdb03a` | feat(contract): add BuilderAgent 14-phase pipeline contract tests | test_pipeline_config.py |

## Completed Tasks

- [x] T-1.1 Create `sdk/quantlab/data/demo/__init__.py` and `sdk/quantlab/data/demo/store.py` — **WU4**
- [x] T-1.2 Add `JCloudDeployClient` ABC, `SimulatedJCloudDeployClient`, `DeploymentStatus` enum — **WU3**
- [x] T-2.1 Add `AsyncSQXClient.export_sourcecode(strategy_id)` — **WU1**
- [x] T-2.2 Extend `CompilerPipeline.compile()` with `strategy_ids` — **WU2**
- [x] T-2.3 JForexDeployer wiring verified — **WU5**
- [x] T-2.5 Update `DeployStage` to accept `strategy_ids` — **WU6**
- [x] T-2.4 DemoWindow persistence wiring into DemoStage — **WU7b**
- [x] T-2.6 Append 14-phase config in BuilderAgent — **WU8a**
- [x] T-3.1 Connect CompileStage → DeployStage via `.jfx` artifact paths — **WU6**
- [x] T-3.3 Wire DemoWindowStore persistence into DemoStage lifecycle — **WU7b**
- [x] T-4.1–4.2 export_sourcecode tests — **WU1**
- [x] T-4.3–4.4 strategy_id mapping tests — **WU2**
- [x] T-4.5–4.6 DemoWindowStore tests — **WU4**
- [x] T-4.7–4.8 JCloudDeployClient ABC tests — **WU3**
- [x] T-4.13–4.14 JForexDeployer wiring tests — **WU5**
- [x] T-4.11–4.12 DeployStage wiring tests — **WU6**
- [x] T-4.9–4.10 Expired window fail-closed — **WU7a a79c5a9**
- [x] T-4.17 Integration: compile→deploy→demo end-to-end — **WU7c**
- [x] T-4.15–4.16 14-phase emission order/determinism — **WU8a**
- [x] T-4.18 Contract: 14-phase vs 8-phase — **WU8b**
- [x] T-5.1 Update docstrings — **WU9 (no changes needed)**
- [x] T-5.2 Inline comments for fail-closed — **WU9 (already present)**
- [x] T-5.3 Remove temporary debug logging — **WU6**

## Verification Gates

| WU | Focused test command | Result |
|----|---------------------|--------|
| WU1 | `pytest -q tests/phase4/test_http_client.py` | 6 passed |
| WU2 | `pytest -q tests/compiler/test_compiler.py` | 15 passed |
| WU3 | `pytest -q tests/demo_deploy/test_jcloud_client.py` | 8 passed |
| WU4 | `pytest -q tests/data/test_demo_store.py` | 5 passed |
| WU5 | `pytest -q tests/compiler/test_jforex_routing.py` | 10 passed |
| WU6 | `pytest -q tests/pipeline/test_deploy_stage.py` | 6 passed |
| WU7b | `pytest -q tests/pipeline/test_demo_stage.py` | 6 passed |
| WU7c | `pytest -q tests/pipeline/test_compile_deploy_demo.py` | 3 passed |
| WU8a | `pytest -q tests/agents/test_builder_agent.py` | 4 passed |
| WU8b | `pytest -q tests/contract/test_pipeline_config.py` | 5 passed |
