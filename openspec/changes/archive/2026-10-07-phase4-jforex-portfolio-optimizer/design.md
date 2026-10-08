# Design: Phase 4 — JForex Deployment, Portfolio Management, Optimizer & Retester Automation

## Technical Approach

Unified `sdk/quantlab/phase4/` package implementing four async submodules (`jforex_deploy`, `portfolio_composer`, `portfolio_master`, `optimizer`, `retester`) sharing `CfxTemplateBuilder` for CFX XML generation via extended `cfx-editor` models, `AsyncSQXClient` for HTTP API calls to SQX `-gui` server, and extended `CommandDispatcher` for sqcli lifecycle management. All submodules expose high-level async APIs matching the proposal signatures.

**Security Baseline**: All SQX HTTP API interactions bind to `127.0.0.1` only. DaemonManager validates localhost binding at startup. Version detection fails fast on unsupported SQX versions.

## Architecture Decisions

### Decision: Async-First Design with httpx.AsyncClient + asyncio Subprocess

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Sync `requests` + `subprocess.run` | Simple, blocks event loop | ❌ Rejected |
| Thread pool for sync calls | Works but adds complexity | ❌ Rejected |
| **Async `httpx.AsyncClient` + `asyncio.create_subprocess_exec`** | Native async, matches SDK direction, single event loop | ✅ **Chosen** |

**Rationale**: SDK uses Pydantic v2, modern Python; async fits SQX daemon lifecycle (long-running HTTP + subprocess). Dry-run mode remains synchronous for testing.

---

### Decision: Shared AsyncSQXClient with Retry Policy, Version Detection & Circuit Breaker

| Aspect | Choice |
|--------|--------|
| Base URL | Configurable, default `http://127.0.0.1:8888` (enforced localhost) |
| Timeouts | Connect 5s, Read 30s, Write 10s, Pool 60s |
| Retries | 3× with exponential backoff (0.5s, 1s, 2s) on 5xx, timeout, connection errors, **429 (respect Retry-After)** |
| Headers | `Accept: application/json`, `User-Agent: QuantLab-Phase4/1.0` |
| Lifecycle | Created lazily per `JForexDeployer`/`PortfolioComposer` instance; closed in `aclose()` |
| **Version Detection** | **On init: call `/health` or `/version`; parse version; fail fast if not in `SUPPORTED_VERSIONS`** |
| **API Compatibility** | **`VERSION_ENDPOINT_MAP`: version → endpoint paths + param encoding (JSON vs form)** |
| **Circuit Breaker** | **5 consecutive failures → 30s cooldown before retry** |

**Rationale**: PortfolioComposer and JForexDeployer both call SQX HTTP API; shared client avoids connection pool fragmentation and centralizes retry/timeout policy. Version detection prevents silent breakage on SQX upgrades. Circuit breaker protects SQX from overload.

---

### Decision: DaemonManager for SQX `-gui` Server Lifecycle with Binding Enforcement

| Aspect | Choice |
|--------|--------|
| Start | `sqcli -gui` via `asyncio.create_subprocess_exec` with `stdout`/`stderr` pipes |
| **Bind Address** | **Configurable `bind_address: str = "127.0.0.1"`; passed to sqcli via `--host` if supported, else env/config** |
| **Startup Validation** | **After starting, verify HTTP health endpoint responds on `127.0.0.1:8888` ONLY (not 0.0.0.0); fail if bound elsewhere** |
| Health Check | HTTP GET `/health` (fallback `/`) every 2s, max 30s startup timeout |
| Stop | SIGTERM → wait 5s → SIGKILL; reap child processes |
| Auto-Restart | On crash, restart once and retry failed command (configurable) |
| Singleton | One daemon per process; `CommandDispatcher` holds reference |

**SECURITY WARNING**: SQX `-gui` binds to all interfaces (0.0.0.0) by default. This exposes the HTTP API (strategy source code, portfolio operations) to the network. **Must configure SQX to bind localhost only** via `--host 127.0.0.1` or SQX config file. DaemonManager enforces this at startup and logs a warning if detection fails.

**Rationale**: HTTP API (PortfolioComposer, JForexDeployer) requires running `-gui` server. sqcli daemon is separate from `-gui`; both managed by `CommandDispatcher`. Binding enforcement prevents accidental network exposure.

---

### Decision: CfxTemplateBuilder as Shared Utility (Not Base Class)

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Base class inherited by submodules | Couples submodules, harder to test | ❌ Rejected |
| **Standalone utility class with static methods** | Composable, testable, no inheritance | ✅ **Chosen** |

**API**:
```python
class CfxTemplateBuilder:
    @staticmethod
    def build_portfolio_cfx(config: PortfolioMasterConfig) -> CfxArchive
    @staticmethod
    def build_optimizer_cfx(config: OptimizerConfig, strategy_id: str) -> CfxArchive
    @staticmethod
    def build_retester_cfx(config: RetesterConfig, strategy_id: str) -> CfxArchive
```

Uses `cfx-editor` models (`PortfolioCfxModel`, `OptimizerCfxModel`, `RetesterCfxModel`) and `CfxWriter` internally. No XML construction logic in submodules.

---

### Decision: Phase4Error Hierarchy (Extends QuantLabError) — Extended

```
QuantLabError (tools.exceptions)
└── Phase4Error
    ├── JForexConnectionError
    ├── JForexStrategyNotFoundError
    ├── JForexServerError
    ├── PortfolioEmptyError
    ├── PortfolioNotOptimizedError
    ├── PortfolioOptimizationError
    ├── OptimizerExecutionError
    ├── OptimizerTimeoutError
    ├── RetesterExecutionError
    ├── RetesterTimeoutError
    ├── PortfolioMasterTimeoutError
    ├── **StrategyNotFoundError**          # NEW: raised when strategy ID not found in SQX session
    ├── **DatabankPathError**              # NEW: raised on databank path traversal attempt
    ├── **UnsupportedSQXVersionError**     # NEW: raised when SQX version not in SUPPORTED_VERSIONS
    └── **SQXBindingError**                # NEW: raised when -gui binds to non-localhost interface
```

All exceptions include `detail: str`, `cause: BaseException | None`, and context fields (e.g., `strategy_id`, `status_code`, `databank_name`, `detected_version`, `bind_address`).

---

### Decision: Extended CommandDispatcher Actions

Add to `CommandDispatcher` (in `sqx-cli-wrapper`):
| Action | Project Types | Args |
|--------|---------------|------|
| `loadconfig` | portfolio, master, optimizer, retester | `name`, `file` |
| `start` | all | `name` |
| `status` | all | `name` |
| `stop` | all | `name` |
| `export` | all | `name`, `output_dir`, `format` (csv/html/databank) |

New result types: `PortfolioStatus`, `OptimizerStatus`, `RetesterStatus` extending `CampaignStatus` with phase-specific fields (`mc_run`, `wf_cycle`, etc.).

---

### Decision: Databank Handling for Retester with Path Traversal Protection

| Aspect | Approach |
|--------|----------|
| Discovery | `databanks` config list maps to SQX databank names (e.g., `EURUSD_H1` → `{SQX_DATA}/EURUSD_H1.databank`) |
| Path Resolution | Configurable base path (`databank_dir`), default `assets/SQX_*/Data/` |
| **Validation** | **Each databank name MUST match regex `^[A-Z]{6}_[A-Z]\d+$` (e.g., `EURUSD_H1`)** |
| **Path Traversal Check** | **Resolve `Path(databank_dir) / f"{databank}.databank"`; verify `resolve().is_relative_to(databank_dir.resolve())`** |
| **Error on Invalid** | **Reject invalid names with `DatabankPathError(Phase4Error)`** |
| Export Format | `CommandDispatcher.export(..., format="databank")` writes `.databank` files to output dir |

---

### Decision: SQX Session Serialization Lock

| Aspect | Choice |
|--------|--------|
| **Lock Type** | **`asyncio.Lock` for intra-process + optional file lock (`portalocker`/`fcntl`) for multi-process** |
| **Lock File** | **`~/.quantlab/sqx-{install-hash}.lock` (install-hash = hash of SQX install path)** |
| **Acquisition** | **`CommandDispatcher` and `DaemonManager` acquire before ANY SQX operation (HTTP or CLI)** |
| **Scope** | **Single-process guaranteed; multi-process best-effort via file lock** |
| **Documentation** | **Explicit: single-process limitation; multi-instance orchestration deferred** |

**Rationale**: Single SQX instance cannot run multiple projects concurrently. Serialization prevents corrupted CFX, mixed HTTP responses, and CLI state conflicts. File lock adds safety for multi-process scenarios (e.g., parallel test runners).

---

### Decision: XML Library — Standard Library `xml.etree.ElementTree`

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `lxml` | Faster, XPath, but extra dependency | ❌ Rejected (specs say stdlib) |
| **`xml.etree.ElementTree`** | Stdlib, sufficient for CFX generation | ✅ **Chosen** |

**Rationale**: CFX XML is flat key-value sections; no complex queries needed. `ElementTree` handles UTF-8 without declaration correctly. Performance is adequate (<10ms per CFX).

---

## Data Flow

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  DSL/Config │────▶│  CfxTemplate     │────▶│   CFX Archive    │
│  (Pydantic) │     │  Builder         │     │   (.cfx ZIP)     │
└─────────────┘     └────────┬─────────┘     └────────┬─────────┘
                             │                      │
                             ▼                      ▼
                    ┌──────────────────┐     ┌──────────────────┐
                    │  SQX HTTP API    │     │   sqcli Daemon   │
                    │  (PortfolioComp, │     │  (loadconfig/    │
                    │   JForexDeploy)  │     │   start/status/  │
                    └────────┬─────────┘     │   export/stop)   │
                             │               └────────┬─────────┘
                             ▼                        ▼
                    ┌──────────────────┐     ┌──────────────────┐
                    │  HTTP Response   │     │  Export Output   │
                    │  (.java, .cfx)   │     │  (CSV, HTML,     │
                    └────────┬─────────┘     │   .databank)     │
                             │               └────────┬─────────┘
                             ▼                        ▼
                    ┌─────────────────────────────────────────┐
                    │         Phase4 Result Objects           │
                    │  (weights dict, strategy list, CSV path,│
                    │   report paths)                         │
                    └─────────────────────────────────────────┘
```

**Sequence Examples**:

1. **PortfolioComposer**: `load_strategies()` → **atomic batch or tracked individual loads with rollback on failure** → `optimize_weights()` → HTTP POST `/recompute` → `save_portfolio()` → HTTP POST `/savePortfolio` → CFX file
2. **PortfolioMaster**: `build_cfx()` → `CfxTemplateBuilder` → `CommandDispatcher.loadconfig/start/status/export` → parse result XML → return selected strategy IDs
3. **Optimizer**: `build_cfx(strategy_id)` → `CommandDispatcher` lifecycle → `export CSV` → parse CSV → return `Path`
4. **Retester**: `build_cfx(strategy_id)` → `CommandDispatcher` lifecycle → `export html+databank` → return report paths
5. **JForexDeploy**: HTTP GET `/sourcecode/print?id=X` → write `.java` → `deploy_indicators()` copies `{SQX}/custom_indicators/JForex/*.java` → target dir

**Serialization**: All SQX operations (HTTP + CLI) acquire `SQXSessionLock` before execution.

---

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/phase4/__init__.py` | Create | Package exports: `JForexDeployer`, `PortfolioComposer`, `PortfolioMaster`, `Optimizer`, `Retester`, `CfxTemplateBuilder`, `AsyncSQXClient`, `Phase4Error`, `DaemonManager`, `SQXSessionLock`, config models |
| `sdk/quantlab/phase4/errors.py` | Create | Phase4Error hierarchy (13 exception classes, incl. new: `StrategyNotFoundError`, `DatabankPathError`, `UnsupportedSQXVersionError`, `SQXBindingError`) |
| `sdk/quantlab/phase4/http_client.py` | Create | `AsyncSQXClient` with retry/timeout/health check, **version detection**, **circuit breaker**, **429 handling** |
| `sdk/quantlab/phase4/cfx_templates.py` | Create | `CfxTemplateBuilder` static methods for Portfolio/Optimizer/Retester CFX (**optimizer/retester accept strategy_id**) |
| `sdk/quantlab/phase4/jforex_deploy.py` | Create | `JForexDeployer` with `export_strategy()`, `deploy_indicators()`, dry-run |
| `sdk/quantlab/phase4/portfolio_composer.py` | Create | `PortfolioComposer` with **atomic `load_strategies()`**, `optimize_weights()`, `save_portfolio()`, `create_portfolio()` |
| `sdk/quantlab/phase4/portfolio_master.py` | Create | `PortfolioMaster` with `build_cfx()`, `run()`, `extract_selected_strategies()` |
| `sdk/quantlab/phase4/optimizer.py` | Create | `Optimizer` with `run()`, `export_results()`, config model (**uses strategy_id from config**) |
| `sdk/quantlab/phase4/retester.py` | Create | `Retester` with `run()`, `export_reports()`, config model (**databank validation**) |
| `sdk/quantlab/phase4/lock.py` | **Create (NEW)** | **`SQXSessionLock` class: asyncio.Lock + optional file lock** |
| `sdk/quantlab/phase4/daemon_manager.py` | **Create (NEW, extracted)** | **`DaemonManager` with `bind_address`, startup validation, health check** |
| `sdk/quantlab/cfx/models.py` | Modify | Add `PortfolioCfxModel`, `OptimizerCfxModel`, `RetesterCfxModel`, new `PatchInstruction` types (16 total) |
| `sdk/quantlab/cfx/reader.py` | Modify | Add `read_portfolio_cfx()`, `read_optimizer_cfx()`, `read_retester_cfx()`; extend `_SETTINGS_SECTIONS`, `_COMPLEX_SECTIONS` |
| `sdk/quantlab/cfx/writer.py` | Modify | Add `set_automatic_portfolio_builder()`, `set_portfolio_settings()`, `set_optimization()`, `set_optimization_parameters()`, `set_walkforward()`, `set_databanks()`, `set_rankings()`, `set_crosschecks()`, `set_retester_data()` |
| `sdk/quantlab/cfx/patcher.py` | Modify | Add 8 new `PatchInstruction` models + validators/appliers for portfolio/optimizer/retester |
| `sdk/quantlab/translate/translator.py` | Modify | Add `generate_portfolio_cfx()`, `generate_optimizer_cfx()`, `generate_retester_cfx()` using `CfxTemplateBuilder` |
| `sdk/quantlab/translate/cfx.py` | Modify | Extend CFX packaging for Portfolio/Optimizer/Retester task types (config.xml + Portfolio-Task1.xml, etc.) |
| `sdk/quantlab/cli/runner.py` | Modify | **Extract `DaemonManager` to phase4/daemon_manager.py**; extend `CommandDispatcher` with new actions + result types; **acquire `SQXSessionLock` before operations** |

---

## Interfaces / Contracts

### Config Models (Pydantic v2)

```python
# phase4/jforex_deploy.py
class JForexDeployConfig(BaseModel):
    sqx_base_url: str = "http://127.0.0.1:8888"
    bind_address: str = "127.0.0.1"  # NEW: enforced localhost binding
    sqx_custom_indicators_path: Path | None = None
    dry_run: bool = False
    timeout: float = 30.0

# phase4/portfolio_composer.py
class PortfolioComposerConfig(BaseModel):
    sqx_base_url: str = "http://127.0.0.1:8888"
    bind_address: str = "127.0.0.1"  # NEW
    dry_run: bool = False
    timeout: float = 30.0

class WeightConstraints(BaseModel):
    min_weight: float = Field(ge=0.0, le=1.0, default=0.0)
    max_weight: float = Field(ge=0.0, le=1.0, default=1.0)

# phase4/portfolio_master.py
class PortfolioMasterConfig(BaseModel):
    strategies: list[str] = Field(min_length=1)
    generations: int = Field(ge=1, default=50)
    population: int = Field(ge=1, default=200)
    fitness: str = "NetProfit"
    min_strategies: int = Field(ge=1, default=1)
    max_strategies: int | None = None
    rebalancing: str = "Monthly"
    dry_run: bool = False
    timeout: float = 3600.0

# phase4/optimizer.py
class ParameterRange(BaseModel):
    min: float
    max: float
    step: float = Field(gt=0)

class OptimizerConfig(BaseModel):
    strategy_id: str  # Already present — now explicitly used in build_optimizer_cfx
    parameter_ranges: dict[str, ParameterRange] = Field(min_length=1)
    walkforward_cycles: int = Field(ge=1, default=5)
    walkforward_oot_ratio: float = Field(gt=0, lt=1, default=0.3)
    databanks: list[str] = Field(min_length=1)
    objective_function: str = "NetProfit"
    method: str = "Genetic"
    ga_population: int = Field(ge=1, default=100)
    ga_generations: int = Field(ge=1, default=50)
    ga_crossover: float = Field(ge=0, le=1, default=0.8)
    ga_mutation: float = Field(ge=0, le=1, default=0.1)
    dry_run: bool = False
    timeout: float = 3600.0

# phase4/retester.py
class RetesterConfig(BaseModel):
    strategy_id: str
    databanks: list[str] = Field(min_length=1)  # Validated: ^[A-Z]{6}_[A-Z]\d+$ + path traversal check
    monte_carlo_runs: int = Field(ge=10, default=100)
    walkforward_cycles: int = Field(ge=1, default=5)
    confidence_level: float = Field(gt=0.5, le=0.99, default=0.95)
    min_trades: int = Field(ge=1, default=30)
    monte_carlo_percentile: int = Field(ge=1, le=99, default=95)
    dry_run: bool = False
    timeout: float = 3600.0
    databank_dir: Path = Path("assets/SQX_*/Data/")  # Configurable base path

# phase4/daemon_manager.py (NEW)
class DaemonManagerConfig(BaseModel):
    sqx_install_path: Path
    bind_address: str = "127.0.0.1"  # Enforced
    gui_port: int = 8888
    startup_timeout: float = 30.0
    health_check_interval: float = 2.0
    auto_restart: bool = True
```

### Core Class Interfaces

```python
# phase4/jforex_deploy.py
class JForexDeployer:
    def __init__(self, config: JForexDeployConfig | None = None) -> None: ...
    async def export_strategy(
        self, strategy_id: str, output_dir: Path, strategy_name: str | None = None
    ) -> Path: ...
    async def deploy_indicators(self, jforex_strategies_dir: Path) -> list[Path]: ...
    async def aclose(self) -> None: ...

# phase4/portfolio_composer.py
class PortfolioComposer:
    def __init__(self, config: PortfolioComposerConfig | None = None) -> None: ...
    
    async def load_strategies(self, strategy_ids: list[str]) -> None:
        """
        Atomic load: all-or-nothing.
        - Option A: If SQX supports batch load, single call.
        - Option B (fallback): Load sequentially; on any failure,
          unload already-loaded strategies via AsyncSQXClient.unload_strategy()
          before raising StrategyNotFoundError.
        """
        ...
    
    async def unload_strategy(self, strategy_id: str) -> None: ...  # NEW: for rollback
    async def optimize_weights(self, fitness: str = "ReturnDDRatio") -> dict[str, float]: ...
    async def save_portfolio(self, name: str, output_dir: Path) -> Path: ...
    async def create_portfolio(
        self,
        strategy_ids: list[str],
        fitness: str = "NetProfit",
        name: str = "Portfolio",
        output_dir: Path = Path("/tmp"),
        constraints: WeightConstraints | None = None,
    ) -> Path: ...
    async def aclose(self) -> None: ...

# phase4/portfolio_master.py
class PortfolioMaster:
    def __init__(self, config: PortfolioMasterConfig | None = None) -> None: ...
    async def build_cfx(self, config: PortfolioMasterConfig) -> Path: ...
    async def run(self, config: PortfolioMasterConfig) -> list[str]: ...
    def extract_selected_strategies(self, result_path: Path) -> list[str]: ...

# phase4/optimizer.py
class Optimizer:
    def __init__(self, config: OptimizerConfig | None = None) -> None: ...
    async def run(self, config: OptimizerConfig) -> Path: ...  # returns CSV path
    async def export_results(self, output_path: Path) -> Path: ...

# phase4/retester.py
class Retester:
    def __init__(self, config: RetesterConfig | None = None) -> None: ...
    async def run(self, config: RetesterConfig, output_dir: Path) -> RetesterResults: ...
    async def export_reports(self, output_dir: Path) -> RetesterReports: ...

@dataclass
class RetesterResults:
    monte_carlo_report: Path
    walkforward_report: Path
    databank_exports: list[Path]

@dataclass
class RetesterReports:
    monte_carlo_html: Path
    walkforward_html: Path
    databanks: list[Path]

# phase4/daemon_manager.py (NEW)
class DaemonManager:
    def __init__(self, config: DaemonManagerConfig) -> None: ...
    
    async def start(self) -> None:
        """
        Start sqcli -gui with --host {bind_address}.
        After process starts, verify HTTP health on {bind_address}:{gui_port} ONLY.
        Raise SQXBindingError if health responds on 0.0.0.0 or unexpected interface.
        """
        ...
    
    async def health_check(self) -> bool: ...
    async def stop(self) -> None: ...
    async def restart(self) -> None: ...

# phase4/lock.py (NEW)
class SQXSessionLock:
    def __init__(self, install_hash: str) -> None:
        """
        install_hash: hash of SQX install path (for multi-process lock file naming)
        """
        self._async_lock = asyncio.Lock()
        self._file_lock_path = Path(f"~/.quantlab/sqx-{install_hash}.lock").expanduser()
    
    async def __aenter__(self) -> None:
        await self._async_lock.acquire()
        # Try file lock (best-effort, non-blocking for intra-process)
        self._acquire_file_lock()
    
    async def __aexit__(self, *args) -> None:
        self._release_file_lock()
        self._async_lock.release()
    
    def _acquire_file_lock(self) -> None: ...  # portalocker/fcntl, log warning on fail
    def _release_file_lock(self) -> None: ...

# phase4/http_client.py
class AsyncSQXClient:
    SUPPORTED_VERSIONS: ClassVar[list[str]] = ["144.2953"]  # Baseline
    VERSION_ENDPOINT_MAP: ClassVar[dict[str, dict]] = {
        "144.2953": {
            "load_strategy": {"path": "/load", "method": "POST", "encoding": "json"},
            "unload_strategy": {"path": "/unload", "method": "POST", "encoding": "json"},
            "recompute": {"path": "/recompute", "method": "POST", "encoding": "json"},
            "save_portfolio": {"path": "/savePortfolio", "method": "POST", "encoding": "json"},
            "source_code": {"path": "/sourcecode/print", "method": "GET", "encoding": "query"},
            "health": {"path": "/health", "method": "GET", "encoding": "none"},
            "version": {"path": "/version", "method": "GET", "encoding": "none"},
        }
        # Future versions added here with potentially different endpoints/encodings
    }
    
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8888",
        timeout: httpx.Timeout | None = None,
        retries: int = 3,
    ) -> None:
        """
        On init: call detect_version(); fail fast with UnsupportedSQXVersionError
        if version not in SUPPORTED_VERSIONS.
        """
        ...
    
    async def detect_version(self) -> str:
        """Call /health or /version; parse version string; return detected version."""
        ...
    
    async def get_source_code(self, strategy_id: str) -> str: ...
    async def load_strategy(self, strategy_id: str) -> None: ...
    async def unload_strategy(self, strategy_id: str) -> None: ...  # NEW: for atomic rollback
    async def recompute_portfolio(self, fitness: str) -> dict[str, float]: ...
    async def save_portfolio(self, name: str, weights: dict[str, float]) -> bytes: ...
    async def health_check(self) -> bool: ...
    async def aclose(self) -> None: ...
    
    # Circuit breaker state (internal)
    _consecutive_failures: int = 0
    _circuit_open_until: float = 0.0
    
    async def _request_with_circuit_breaker(self, ...) -> httpx.Response:
        """
        - If circuit open (time < _circuit_open_until), raise immediately
        - On 429: respect Retry-After header, increment failures
        - On 5xx/timeout/connection error: increment failures
        - On success: reset failures
        - If failures >= 5: _circuit_open_until = now + 30s
        """
        ...
```

### CFX Template Builder

```python
# phase4/cfx_templates.py
class CfxTemplateBuilder:
    @staticmethod
    def build_portfolio_cfx(config: PortfolioMasterConfig) -> CfxArchive: ...
    @staticmethod
    def build_optimizer_cfx(config: OptimizerConfig, strategy_id: str) -> CfxArchive: ...
    @staticmethod
    def build_retester_cfx(config: RetesterConfig, strategy_id: str) -> CfxArchive: ...
```

---

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| **Unit** | `AsyncSQXClient`, `CfxTemplateBuilder`, config models, error hierarchy | Mock `httpx.AsyncClient` with `respx`/`httpx_mock`; validate XML output against schema; test dry-run paths; **test version detection, circuit breaker, 429 handling, atomic load rollback** |
| **Unit** | `CfxReader`/`CfxWriter` extensions | Round-trip test: read known-good Portfolio/Optimizer/Retester CFX → modify → write → read → assert equality |
| **Unit** | `CfxPatcher` new instructions | Apply each new instruction type; validate mutated model; test validation failures |
| **Unit** | `SQXSessionLock` | Test async lock serialization; test file lock acquisition/release (mock portalocker) |
| **Unit** | `DaemonManager` | Test bind_address validation; test health check on localhost only; mock subprocess |
| **Unit** | `RetesterConfig.databanks` validator | Test regex `^[A-Z]{6}_[A-Z]\d+$`; test path traversal rejection (`../etc/passwd`, absolute paths) |
| **Integration** | `JForexDeployer.export_strategy()` | Testcontainers or real SQX `-gui` in CI; verify `.java` compiles with JForex SDK |
| **Integration** | `PortfolioComposer.create_portfolio()` | Real SQX HTTP API; compare weights to GUI result (±0.1%); **test atomic load failure rollback** |
| **Integration** | `PortfolioMaster.run()` | Real sqcli; verify genetic search completes, extracts strategies |
| **Integration** | `Optimizer.run()` | Real sqcli; verify CSV columns match spec |
| **Integration** | `Retester.run()` | Real sqcli; verify Monte Carlo + WF reports + databank export; **test databank validation** |
| **E2E** | Full pipeline: DSL → CFX → Optimize → Retest → Portfolio → JForex | Manual with real SQX; automated smoke test in dry-run mode |

**Dry-Run Coverage**: All 5 submodules implement `dry_run=True` returning mock outputs without SQX. Unit tests run dry-run only (no external deps).

---

## Migration / Rollout

No data migration. Pure additive SDK package.

**Rollback**: Delete `sdk/quantlab/phase4/`; revert `cfx/`, `translate/`, `cli/` modifications via git.

**Feature Flags**: Each submodule controlled by `dry_run` config; no global flags needed.

**Security Baseline Enforcement**: 
- All configs default `bind_address = "127.0.0.1"`; cannot be overridden to `0.0.0.0` without explicit opt-in (not provided).
- DaemonManager startup validation is mandatory; cannot be disabled.
- Version detection runs on every `AsyncSQXClient` init; unsupported versions hard-fail.

---

## Open Questions

- [ ] **SQX HTTP API exact endpoints/params for PortfolioComposer** — Need to verify `/load`, `/unload`, `/recompute`, `/savePortfolio` signatures against real SQX 144.2953. Specs assume JSON payloads; may be form-encoded. `VERSION_ENDPOINT_MAP` encodes this.
- [ ] **Databank path resolution for Retester** — SQX databank format (`.databank` vs `.db`) and exact path mapping from symbol (e.g., `EURUSD_H1`) to file needs verification.
- [ ] **Seed control for genetic reproducibility** — PortfolioMaster and Optimizer use genetic algorithms; SQX CFX may support `Seed` parameter. Need to confirm and expose in config if available.
- [ ] **SQX `-gui` server health endpoint** — `/health` may not exist; fallback to `/` or `/sourcecode/print?id=test`. Need to verify. `AsyncSQXClient.health_check()` tries both.
- [ ] **SQX batch load/unload support** — Does SQX 144.2953 support batch strategy load/unload? Determines Option A vs B for atomic `load_strategies()`. Current design assumes Option B (fallback) with unload rollback.

---

## Next Step

Ready for tasks (sdd-tasks).