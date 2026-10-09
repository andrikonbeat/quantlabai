# Design: Phase 1 — SDK Core

## Technical Approach

Flat monorepo Python SDK with 6 layered modules under `sdk/quantlab/`. SQX integration uses an **adapter pattern**: `CliRunner` abstracts `sqcli.exe` behind an `Executor` protocol with dry-run fallback. All modules depend only on Pydantic v2 + stdlib — no SQX runtime required at dev time. Knowledge Lake is filesystem-first, Git-versioned, with 5 directories under `knowledge/`. Cross-platform via `platformdirs` + `pathlib`.

## Architecture Decisions

### 1. Python Toolchain

| Option | Tradeoff | Choice |
|--------|----------|--------|
| **uv** | Fastest, cross-platform, modern | **✓** |
| Poetry | Mature but slower lockfile, fewer features | Rejected |
| pip+venv | Manual dep management, no lock | Rejected |

**Rationale**: uv installs 10× faster, manages Python versions natively, and has first-class Windows/Linux support. Single `pyproject.toml`.

### 2. Data Models

| Option | Tradeoff | Choice |
|--------|----------|--------|
| **Pydantic v2** | Validation, serialization, JSON Schema | **✓** |
| dataclasses | No validation, manual serialization | Rejected |
| attrs | Feature-rich but less ecosystem | Rejected |

**Rationale**: Specs require validation (market/timeframe pairs, duplicate names), serialization round-trips, and error-safe parsing — Pydantic v2 provides all built-in.

### 3. Package Structure

| Option | Tradeoff | Choice |
|--------|----------|--------|
| **Flat quantlab/ subpackages** | Independent modules, no cross-coupling | **✓** |
| Namespace packages | Over-engineered for 6 modules | Rejected |
| Single module | Too large, violates SRP | Rejected |

**Rationale**: Each of the 6 specs maps to one subpackage. Module independence enables parallel development and Phase 2 integration.

### 4. Dry-Run Pattern

| Option | Tradeoff | Choice |
|--------|----------|--------|
| **Strategy pattern** | Clean interface, testable, SOLID | **✓** |
| Conditional checks | Scattered logic, hard to mock | Rejected |
| Monkey-patching | Brittle, not type-safe | Rejected |

**Rationale**: `CliRunner` accepts an `Executor` protocol. `RealExecutor` spawns subprocess, `MockExecutor` returns canned Pydantic fixtures. Per-call `dry_run=False` override via kwarg — keeps modules testable without SQX.

### 5. Cross-Platform Paths

| Option | Tradeoff | Choice |
|--------|----------|--------|
| **platformdirs + pathlib** | Battle-tested, pure Python | **✓** |
| os.environ manual parsing | Fragile, platform-specific | Rejected |
| Conditional if/else per OS | Scattered, untestable | Rejected |

**Rationale**: `platformdirs` resolves Windows Program Files vs Linux `/opt`, `/usr/local`. `pathlib` normalizes separators. `platform.system()` drives binary name (`sqcli.exe` vs `sqcli`).

### 6. Error Hierarchy

| Hierarchy | Tradeoff | Choice |
|-----------|----------|--------|
| **QuantLabError → subclasses** | Catchable, descriptive, testable | **✓** |
| Generic Exception | Meaningless to callers | Rejected |
| Return types (Result/Option) | Over-engineered for Phase 1 | Rejected |

**Rationale**: `QuantLabError` base → `ParseError`, `ValidationError`, `TranslationError`, `SQXNotFoundError`, `TimeoutError`, `InsufficientDataError`. All inherit Pydantic's validation for model errors.

## Data Flow

```
research.yaml ──→ [dsl/parser] ──→ ResearchConfig ──→ [translate/] ──→ XML string
                      ↑                                                  │
                      |                                     ┌── dry_run? ──→ return XML
                      |                                     │
                      |                               [cfx writer] ──→ .cfx file
                      |                                     │
knowledge/index.yaml ← [knowledge/ store]                   │
                      │                                     ▼
                      │                              [cli/ runner] ──→ sqcli.exe
                      │                                     │
                      │                            ┌── dry_run? ──→ MockExecutor
                      │                            │                (canned result)
                      │                            ▼
                      │                     Databank CSV/XLSX
                      │                            │
                      │                            ▼
                      │                     [readers/] ──→ Trade[], Equity[], Summary
                      │                            │
                      └──────────────────────── [stats/] ──→ Metrics (PF, Sharpe, DD, MAR, Expectancy)
```

**Dry-run bypasses**:
- **translate**: `dry_run=True` → returns XML string, skips `.cfz` ZIP write
- **cli**: `dry_run=True` → `MockExecutor` returns `CliResult(exit_code=0, stdout=..., is_dry_run=True)`
- **readers/stats/knowledge**: Zero SQX dependency — work on any CSV/XLSX or filesystem path

## Interfaces / Contracts

Core type signatures for the 6 module boundaries:

```python
# research-dsl
class ResearchConfig(BaseModel): ...          # market, timeframe, strategies, criteria
def parse_yaml(path: Path) -> ResearchConfig
def validate(model: ResearchConfig) -> ResearchConfig

# sqx-translator
class CfxArchive:
    @staticmethod
    def from_model(config: ResearchConfig, dry_run: bool = False) -> CfxResult
# CfxResult: xml_content: str, path: Path | None

# sqx-cli-wrapper
class CliRunner:
    def __init__(self, dry_run: bool = False, sqcli_path: Path | None = None)
    def execute(self, command: str, **overrides) -> CliResult
# CliResult: stdout, stderr, exit_code, duration_s, is_dry_run, platform

# result-reader
class DatabankReader:
    def read_trades(self, path: Path) -> list[Trade]
    def read_equity(self, path: Path) -> list[EquityPoint]
    def read_summary(self, path: Path) -> SummaryStats
# Trade, EquityPoint, SummaryStats: all BaseModel subclasses

# statistics-engine
class StatsEngine:
    def profit_factor(self, trades: list[Trade]) -> float
    def sharpe_ratio(self, returns: list[float], annual: int = 252) -> float
    def sortino_ratio(self, returns: list[float]) -> float
    def max_drawdown(self, equity: list[EquityPoint]) -> float
    def mar_ratio(self, cagr: float, dd: float) -> float
    def recovery_factor(self, profit: float, dd: float) -> float
    def expectancy(self, trades: list[Trade]) -> tuple[float, float]

# knowledge-storage
class KnowledgeStore:
    def __init__(self, root: Path = Path("knowledge"))
    def initialize(self) -> None              # idempotent, creates 5 dirs
    def rebuild_index(self) -> IndexModel      # scans filesystem → YAML
    def validate_formats(self) -> list[Warning]  # open format check
```

## Error Handling Strategy

All errors inherit from `QuantLabError(BaseException)`. Modules raise specific subclasses:

| Error | Module | Trigger |
|-------|--------|---------|
| `ParseError` | dsl, readers | Invalid YAML, missing CSV columns, corrupted XLSX |
| `ValidationError` | dsl, translate | Unknown market, duplicate strategies, missing fields |
| `SQXNotFoundError` | cli | `sqcli.exe` not found in real mode |
| `TimeoutError` | cli | Subprocess exceeds configured timeout |
| `InsufficientDataError` | stats | Empty trade list for metric computation |

**Policy**: Fail early with descriptive messages. Never silently swallow. All errors expose a `detail` field for UI/logging. Readers emit `FormatWarning` (via `warnings.warn`) for non-standard files but continue.

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Unit — dsl | Parse, validate, serialize | Fixture YAML files → assert `ResearchConfig` fields; assert error types for bad inputs |
| Unit — translate | XML generation, dry-run | Parametrized `ResearchConfig` → assert XML element presence; `dry_run=True` → assert no file |
| Unit — cli | Mock executor, per-call override | Inject `MockExecutor` → assert `CliResult` fields; `dry_run=False` override raises `SQXNotFoundError` on Linux |
| Unit — readers | CSV/XLSX parse, empty/corrupt | Fixture CSVs in `tests/fixtures/` → assert `Trade[]` length, `None` defaulting |
| Unit — stats | 9 metrics, zero-div, empty | Fixture `Trade[]` lists → assert exact numeric values per spec |
| Unit — knowledge | Init, re-init, index rebuild, format warnings | `tempfile.TemporaryDirectory` → assert 5 dirs + `.gitkeep`; add `.docx` → assert warning |
| Cross-platform | Path resolution, binary name | Mock `platform.system()` → assert `sqcli.exe` vs `sqcli`; assert `pathlib` separator behavior |

All tests run with `pytest` — no SQX installation required at any layer.

## Migration / Rollout

No migration required — greenfield project. All files are new. No existing data to migrate.

## File Changes

All files are **Create** (greenfield):

| File | Description |
|------|-------------|
| `sdk/pyproject.toml` | uv project config, deps (pydantic, pyyaml, platformdirs, openpyxl, pandas) |
| `sdk/quantlab/__init__.py` | Package root |
| `sdk/quantlab/dsl/{__init__,models,parser}.py` | Pydantic models + YAML parser |
| `sdk/quantlab/translate/{__init__,translator,cfx}.py` | Model→XML→ZIP pipeline |
| `sdk/quantlab/cli/{__init__,runner,mock}.py` | Executor protocol, real + mock impls |
| `sdk/quantlab/readers/{__init__,databank,models}.py` | CSV/XLSX → Pydantic readers |
| `sdk/quantlab/stats/{__init__,engine,models}.py` | Metric computations |
| `sdk/quantlab/tools/{__init__,platform,exceptions}.py` | OS detection, error hierarchy |
| `sdk/tests/` (10+ files) | Test modules mirroring `quantlab/` structure |
| `sdk/tests/fixtures/` | Sample YAML, CSV, XLSX fixtures |
| `strategies/HelloWorldStrategy.java` | Java strategy template (skeleton) |
| `knowledge/{raw,structured,graph,embeddings,datasets}/.gitkeep` | Knowledge Lake skeleton |

## Open Questions

- [ ] Determine actual SQX `.cfx` XML schema — need to inspect a real `.cfx` file to confirm element names and structure. For now the translator emits a best-guess XML skeleton.
- [ ] Confirm Databank CSV column names — do they match the field names in the Result Reader spec? Need real SQX output to validate.
- [ ] uv version pin: should we pin to a specific uv version in CI or use latest?
