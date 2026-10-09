# Design: Phase 2 — SQX Local Execution Pipeline

## Technical Approach

Connect Phase 1's DSL→CFX translation and result readers into an end-to-end campaign pipeline. 3 chained PRs under 400 lines each: Foundation → Core CampaignRunner → Resilience. Everything testable with `MockExecutor` — no license required for development.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| **per-command subprocess** vs keep-alive daemon pipe | subprocess: clean isolation, sqcli handles daemon internally; pipe: fragile, sqcli doesn't expose REPL | **Subprocess per command** — CommandDispatcher constructs `[sqcli, -command, action=..., key=val]` each call |
| **sequential state machine** (if/elif over phase enum) vs chain-of-responsibility | sequential: simple, testable, matches 7-phase linear flow; CoR: over-engineered for linear pipeline | **Sequential state machine** — CampaignRunner iterates phase list, each phase is a method |
| **typing.Protocol** callback vs abstract base vs event emitter | Protocol: zero runtime overhead, trivially mockable; ABC: heavier, requires inheritance; emitter: over-engineered for 1 listener | **Callable `Protocol`** — `ProgressCallback(callable[[CampaignPhase, PhaseStatus, str | None], None])` |
| **JSON file** checkpoint vs SQLite vs pickle | JSON: human-readable, diffable, no deps; SQLite: overkill for <1KB state; pickle: opaque, version-sensitivity risk | **JSON checkpoint** — saves current phase index, config ref, export paths |
| **90% MockExecutor** coverage vs real integration tests | mock: 0 dependencies, instant, deterministic; real: requires license, flaky | **MockExecutor for PR 1-3**, real sqcli test flagged `@pytest.mark.integration` |

## Data Flow

```
ResearchConfig ──→ CfxArchive ──→ .cfx file ──→ CommandDispatcher ──→ sqcli (subprocess)
                         │                                                │
                         ↓                                                ↓
                    KnowledgeStore ←── StatsEngine ←── DatabankCSVReader ←── .csv export
                         │                  │               │
                         ↓                  ↓               ↓
                    artifacts/          metrics.json     raw_results/
```

Runner orchestrates: `translate → daemon_start → load_config → run → poll [loop] → export → read → compute → store`

## File Changes

### PR 1 — Foundation (~380 lines)

| File | Action | Lines | Description |
|------|--------|-------|-------------|
| `sdk/quantlab/pipeline/models.py` | Create | ~60 | `CampaignPhase` enum, `CampaignStatus` enum, `PhaseResult` model, extended `CliResult` with command metadata |
| `sdk/quantlab/pipeline/error.py` | Create | ~30 | `LicenseError`, `CampaignError` extending `QuantLabError` |
| `sdk/quantlab/pipeline/dispatcher.py` | Create | ~80 | `CommandDispatcher` — constructs `key=value` args as list, delegates to executor, extended `CliResult` |
| `sdk/quantlab/pipeline/license.py` | Create | ~50 | `LicenseManager` — calls `-license action=info`, parses output into `LicenseStatus` |
| `sdk/quantlab/cli/runner.py` | Modify | ~40 | `RealExecutor.execute()` change `command.split()` → `[str(self._binary), *args]` where args is list |
| `sdk/quantlab/tools/platform.py` | Modify | ~10 | Add `get_sqcli_dir()` for asset base resolution |
| `sdk/tests/test_pipeline.py` | Create | ~110 | Pipeline models, dispatcher with MockExecutor, license manager |

### PR 2 — Core CampaignRunner (~390 lines)

| File | Action | Lines | Description |
|------|--------|-------|-------------|
| `sdk/quantlab/pipeline/progress.py` | Create | ~25 | `ProgressCallback` protocol, `PhaseStatus` enum |
| `sdk/quantlab/pipeline/campaign.py` | Create | ~180 | `CampaignRunner` — 7-phase sequential flow, polling loop, progress callbacks |
| `sdk/quantlab/pipeline/__init__.py` | Create | ~15 | Public API re-exports |
| `sdk/tests/test_pipeline.py` | Modify | +170 | CampaignRunner integration with MockExecutor, callback firing tests |

### PR 3 — Resilience (~370 lines)

| File | Action | Lines | Description |
|------|--------|-------|-------------|
| `sdk/quantlab/pipeline/campaign.py` | Modify | +80 | Checkpoint save/restore, retry wrapper, per-phase timeout |
| `sdk/quantlab/pipeline/checkpoint.py` | Create | ~70 | `CheckpointManager` — load/save/resume JSON state |
| `sdk/quantlab/pipeline/models.py` | Modify | +20 | `CampaignCheckpoint` model |
| `sdk/tests/test_pipeline.py` | Modify | +200 | Checkpoint recovery, retry logic, timeout error scenarios |

## Interfaces / Contracts

```python
# pipeline/models.py
class CampaignPhase(str, Enum):
    TRANSLATE = "translate"
    DAEMON_START = "daemon_start"
    LOAD_CONFIG = "load_config"
    RUN = "run"
    POLL = "poll"
    EXPORT = "export"
    STORE = "store"

class CampaignStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"

class LicenseStatus(str, Enum):
    LICENSED = "licensed"
    UNLICENSED = "unlicensed"
    EXPIRED = "expired"
    TRIAL = "trial"

# pipeline/progress.py
class PhaseStatus(str, Enum):
    STARTED = "started"
    SUCCESS = "success"
    ERROR = "error"

class ProgressCallback(Protocol):
    def __call__(self, phase: CampaignPhase, status: PhaseStatus,
                 detail: str | None = None) -> None: ...

# pipeline/dispatcher.py
class CommandDispatcher:
    def __init__(self, executor: Executor) -> None: ...
    def start_daemon(self) -> CliResult: ...
    def load_config(self, project: str, cfx_path: str) -> CliResult: ...
    def start_project(self, project: str) -> CliResult: ...
    def poll_status(self, project: str) -> CampaignStatus: ...
    def stop_project(self, project: str) -> CliResult: ...
    def export_databank(self, project: str, format: str,
                        file: str, type: str) -> CliResult: ...
    def stop_daemon(self) -> CliResult: ...

# pipeline/license.py
class LicenseManager:
    def __init__(self, dispatcher: CommandDispatcher) -> None: ...
    def check(self) -> LicenseInfo: ...
    def activate(self, code: str) -> CliResult: ...

# pipeline/campaign.py
@dataclass
class CampaignConfig:
    project_name: str = "campaign-1"
    poll_interval: int = 30
    poll_timeout: int = 600  # 10 min
    retry_attempts: int = 3
    export_formats: list[str] = field(default_factory=lambda: ["csv"])

class CampaignRunner:
    def __init__(self, translator, dispatcher, reader,
                 stats_engine, knowledge_store,
                 license_mgr: LicenseManager | None = None,
                 progress: ProgressCallback | None = None): ...
    def run(self, config: ResearchConfig,
            cfg: CampaignConfig | None = None) -> CampaignResult: ...
```

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Unit | Models, error types, checkpoint serialization | Pure assertions, no mocks |
| Unit | CommandDispatcher arg construction | MockExecutor, assert call args |
| Unit | LicenseManager status parsing | MockExecutor with canned output per status variant |
| Integration | CampaignRunner full flow | MockExecutor returns success at each phase, verify callback seq |
| Integration | Poll loop timing | MockExecutor returns `running` → `running` → `completed`, verify 3 polls |
| Resilience | Retry succeeds after N-1 failures | MockExecutor fails twice then succeeds, verify retry count |
| Resilience | Checkpoint save/restore | Write checkpoint, create new runner, call `resume()`, verify skips completed phases |

## Migration / Rollout

No migration required. The `pipeline/` module is additive — no existing code changes behavior. `RealExecutor` arg construction fix is backward-compatible for simple commands while fixing `key=value` with spaces.

## Open Questions

- [ ] sqcli status output format unknown — require `pytest.mark.integration` test with real binary to reverse-engineer. MockExecutor status parser must be pluggable.
- [ ] Does sqcli daemon need a `-port` argument or does it default to 5050? Will confirm with real binary.
- [ ] Does `-project action=run` exist, or is it `-run file=<path>`? Spec uses "run" — verify with real binary.
