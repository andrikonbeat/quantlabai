# Design: Compiler-Deploy-Demo Integration

## Technical Approach

Close four critical-path gaps to enable compile→deploy→demo end-to-end. Add `export_sourcecode()` to `AsyncSQXClient`, wire strategy IDs through `CompileStage`, persist `DemoWindow` state, define the `JCloudDeployClient` simulation-first interface, and extend `BuilderAgent` to emit the full 14-phase pipeline config additively.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `export_sourcecode` placement | Add to `AsyncSQXClient` vs new `SQXSourceClient` | Add to `AsyncSQXClient` — existing retry/circuit-breaker reused, no new client surface |
| Strategy ID mapping | Per-strategy compile vs batch compile | Per-strategy compile — `CompiledStrategy[strategy_id]` mapping preserves identity through the pipeline |
| Demo persistence | Knowledge Lake vs SQLite vs memory | Knowledge Lake `structured/demo/{campaign_id}/window.yaml` — matches existing Knowledge Lake conventions in `BuilderAgent._persist_build_artifacts` |
| JCloud interface | ABC with simulation first vs real-first with stub | ABC with `SimulatedJCloudDeployClient` shipping first — `NotImplementedError` on real paths, explicit simulation flag |
| 14-phase config | Replace 8-phase vs append | Append new phases after portfolio — preserves backward compatibility, additive merge guarded by `QUANTLAB_14PHASE` flag |
| Demo expiry | Grace period vs fail-closed | Fail-closed — expired window blocks with `HUMAN_APPROVE_DEMO`, 5-minute clock-skew tolerance |

## Data Flow

    StrategyQuant GUI
         │
         ▼
    AsyncSQXClient.export_sourcecode(strategy_id)
         │  HTTP GET /sourcecode/print?id={id}
         │  raises JForexStrategyNotFoundError / JForexConnectionError / JForexServerError
         ▼
    JForexDeployer.export_strategy()
         │  writes {class_name}.java
         ▼
    CompilerPipeline.compile(strategy_id=..., src=...)
         │  javac → .classes → .jfx
         │  partial failure → compilation_failed artifact
         ▼
    DeployStage.package_jfx()
         │  JCloudDeployClient.deploy() (simulated)
         ▼
    DemoStage
         │  DemoWindow.load() → status check
         │  EXPIRED → BLOCKED_EXPIRED, HUMAN_APPROVE_DEMO
         │  ACTIVE → deploy proceeds
         ▼
    ArchiveStage

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/phase4/http_client.py` | Modify | Add `export_sourcecode(strategy_id) -> str` with GET `/sourcecode/print?id={id}` |
| `sdk/quantlab/compiler/compiler.py` | Modify | Extend `CompilerPipeline.compile()` to accept `strategy_id`; emit `compiled_strategies` and `compilation_failed` artifacts |
| `sdk/quantlab/phase4/jforex_deploy.py` | Modify | Wire existing `export_sourcecode` calls to the new client method (gap fix) |
| `sdk/quantlab/agents/deployment_agent.py` | Modify | Add `JCloudDeployClient` ABC, `SimulatedJCloudDeployClient`, `DeploymentStatus` enum |
| `sdk/quantlab/pipeline/stages/deploy_stage.py` | Modify | Accept `strategy_ids`; iterate and call `JCloudDeployClient.deploy()` per strategy |
| `sdk/quantlab/pipeline/stages/demo_stage.py` | Modify | Add `DemoWindow.persist()` / `load()` hooks; fail-closed on expiry |
| `sdk/quantlab/data/demo/__init__.py` | Create | Package init for demo persistence |
| `sdk/quantlab/data/demo/store.py` | Create | `DemoWindowStore` — atomic write/read of `window.yaml` under Knowledge Lake |
| `sdk/quantlab/agents/builder_agent.py` | Modify | Append compile/deploy/demo/archive/live_ops phases; gate with `QUANTLAB_14PHASE` |

## Interfaces / Contracts

**AsyncSQXClient.export_sourcecode(strategy_id: str) -> str**
```python
async def export_sourcecode(self, strategy_id: str) -> str:
    resp = await self._client.get(f"/sourcecode/print?id={urllib.parse.quote(strategy_id)}")
    if resp.status_code == 404:
        raise JForexStrategyNotFoundError(strategy_id)
    if 500 <= resp.status_code < 600:
        raise JForexServerError(resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.text
```

**CompileStage input/output**
```python
# Input
portfolio_result: dict[str, Any]  # includes strategy_ids list
strategy_ids: list[str]           # explicit mapping

# Output
compiled_strategies: dict[str, Path]      # strategy_id -> .jfx path
compilation_failed: dict[str, CompileError]  # strategy_id -> error
```

**JCloudDeployClient (ABC)**
```python
class JCloudDeployClient(ABC):
    @abstractmethod
    async def deploy(self, jfx_path: Path, strategy_id: str, config: dict) -> DeploymentResult: ...
    @abstractmethod
    async def status(self, deployment_id: str) -> DeploymentStatus: ...
```

**DemoWindowStore**
```python
class DemoWindowStore:
    PERSIST_PATH = "{knowledge_root}/structured/demo/{campaign_id}/window.yaml"
    async def persist(self, window: DemoWindow) -> None: ...   # atomic temp+rename
    def load(self, campaign_id: str) -> DemoWindow: ...        # idempotent, validates schema
```

**BuilderAgent 14-phase config** — phases appended after portfolio: `compile`, `deploy`, `demo`, `archive`, `live_ops`. Existing 8 phases unchanged. Gate with `QUANTLAB_14PHASE=1` or explicit opt-in.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `export_sourcecode` HTTP method, status mapping | Mock `httpx.AsyncClient`; assert GET `/sourcecode/print?id=...`, 404→NotFound, 5xx→ServerError |
| Unit | Strategy ID mapping in compile | Feed `strategy_ids=["s1","s2"]`; assert `compiled_strategies` keys match; missing ID logs warning and falls back to filename |
| Unit | `DemoWindowStore` persistence | Atomic write validation; corrupt YAML raises `StateCorruptionError`; concurrent writes serialize |
| Integration | compile→deploy→demo pipeline | `SimulatedJCloudDeployClient`; assert `.jfx` → JAR → demo window → `demo_result` |
| Contract | 14-phase emission | Assert phase count=14, order exact, existing phases unchanged, `QUANTLAB_14PHASE=0` emits 8 |
| Contract | Demo fail-closed | `DemoWindow` with past `expires_at`; assert `BLOCKED_EXPIRED` and `HUMAN_APPROVE_DEMO` gate |

## Threat Matrix

`N/A` — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary is being changed. The existing `javac` subprocess boundary in `run_javac` is untouched; this design only extends the input contract with `strategy_id` and preserves all existing subprocess safety guarantees.

## Migration / Rollout

No migration required. All changes are additive:
- Existing 8-phase configs continue to work via `QUANTLAB_14PHASE=0` default.
- `DemoWindowStore` writes new files; absence falls back to in-memory `DemoWindow(started_at=today)`.
- `JCloudDeployClient` ABC coexists with existing `DeploymentAgent.package_jfx()`.

## Open Questions

- [ ] Confirm SQX `/sourcecode/print` endpoint path and auth requirements with SQX team before release.
- [ ] Determine Knowledge Lake path convention for `structured/demo/{campaign_id}/window.yaml` — verify with data-platform owners.

## Key Learnings

1. `AsyncSQXClient` already imports `JForexStrategyNotFoundError` but never raises it — `export_sourcecode` closes this dead import gap.
2. `JForexDeployer.dry_run_export()` already calls `export_sourcecode()` on line 230, so adding it to `AsyncSQXClient` unblocks an existing code path.
3. `DemoDeployer` already implements fail-closed expiry in `deploy()`; persistence is the only missing piece for restart safety.
4. `BuilderAgent.generate_pipeline_config()` builds the stage list inline — appending 5 new phases is a simple list extension, not a refactor.
