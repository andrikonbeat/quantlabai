# Design: MCP Bridge + Fundamental Analysis

## Technical Approach

Single `MCPServer` instance in `bridge.py` boots via `python -m quantlab.mcp`, registers tools from four domain modules via `@mcp.tool()`. Each tool wraps its subsystem with `model_dump(mode="json")` at the boundary. `quantlab/data/fundamental/` implements an ABC-based provider pattern with SQLite-backed TTL cache and token-bucket rate limiter, all async via `httpx.AsyncClient`.

## Architecture Decisions

| Decision | Options | Tradeoff | Decision |
|----------|---------|----------|----------|
| Server class | `mcp.server.MCPServer` vs raw `Server` | MCPServer auto-generates schemas from type hints; raw Server requires manual JSON-RPC | `MCPServer` v2 API (stable 2026-07-28) |
| Subsystem lifecycle | Singleton (lazy init at bridge start) vs fresh per-tool | Singleton avoids repeated construction cost for PipelineRunner, EvolutionOrchestrator, etc. Per-tool adds isolation but no concurrent safety benefit (MCP already serializes per-tool) | Lazy singleton per subsystem |
| Serialization | `model_dump(mode="json")` vs manual dict conversion | `mode="json"` handles Pydantic `BaseModel` natively; `dataclass` models need `to_dict()` bridge | `model_dump(mode="json")` for Pydantic; `to_dict()` for pipeline dataclasses |
| Provider pattern | ABC + registry vs single provider class | ABC forces consistent interface for Yahoo/FRED; registry allows future providers (Alpha Vantage, etc.) | `AbstractDataProvider` ABC with registry dict |
| Rate limiter | Token-bucket vs sliding window | Token-bucket simpler to implement async-safe; sliding window more precise at low rates | `asyncio.Lock`-protected token bucket per provider |
| Cache TTL | Per-query vs per-provider | Per-provider simpler; per-query more granular | Per-provider TTL (Yahoo: 300s, FRED: 3600s) with override support |
| Caching lib | Custom SQLite vs `diskcache` | Custom avoids extra dep; diskcache is more feature-rich | Custom SQLite (`CREATE TABLE cache (key, value, expires_at)`) |

## Data Flow

```
                ┌──────────────┐
  MCP Client ──►│  bridge.py   │── python -m quantlab.mcp
                │  MCPServer   │
                └──────┬───────┘
         ┌─────────────┼──────────────┐
         ▼             ▼              ▼
  pipeline_tools evolution_tools health_tools fundamental_tools
         │             │              │              │
         ▼             ▼              ▼              ▼
  PipelineRunner  EvolutionOrch. HealthCalc.  Data Providers
         │             │              │         ┌────┴────┐
         ▼             ▼              ▼       Yahoo    FRED
  PipelineResult EvolutionResult HealthScore      │       │
                                                 SQLite  Token
                                                 Cache   Bucket
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/pyproject.toml` | Modify | Add `mcp`, `yfinance`, `pandas-datareader` |
| `sdk/quantlab/mcp/__init__.py` | Create | Public exports, null-system guard |
| `sdk/quantlab/mcp/__main__.py` | Create | `python -m quantlab.mcp` entry point |
| `sdk/quantlab/mcp/bridge.py` | Create | `MCPServer` init, tool registration, subsystem singletons |
| `sdk/quantlab/mcp/models.py` | Create | MCP-specific request/response Pydantic models |
| `sdk/quantlab/mcp/pipeline_tools.py` | Create | `run_backtest`, `list_pipelines`, `get_pipeline_run` |
| `sdk/quantlab/mcp/evolution_tools.py` | Create | `generate_candidates`, `query_pool`, `promote_candidate` |
| `sdk/quantlab/mcp/health_tools.py` | Create | `evaluate_strategy`, `get_health_metrics`, `compute_fitness` |
| `sdk/quantlab/mcp/fundamental_tools.py` | Create | `get_fundamental_data`, `get_financial_ratios`, `get_market_data` |
| `sdk/quantlab/data/__init__.py` | Create | Package marker (currently missing) |
| `sdk/quantlab/data/fundamental/__init__.py` | Create | Package exports |
| `sdk/quantlab/data/fundamental/base.py` | Create | `AbstractDataProvider` ABC |
| `sdk/quantlab/data/fundamental/yahoo.py` | Create | `YahooFinanceProvider` via `yfinance` |
| `sdk/quantlab/data/fundamental/fred.py` | Create | `FredProvider` via `pandas-datareader` |
| `sdk/quantlab/data/fundamental/cache.py` | Create | SQLite cache with TTL |
| `sdk/quantlab/data/fundamental/rate_limit.py` | Create | `TokenBucket` rate limiter |

## Interfaces / Contracts

```python
# data/fundamental/base.py
class AbstractDataProvider(ABC):
    @abstractmethod
    async def fetch(self, query: str, **params: Any) -> dict[str, Any]: ...

# data/fundamental/cache.py
class SqliteCache:
    def __init__(self, db_path: str | None = None, ttl: int = 3600) -> None: ...
    async def get(self, key: str) -> dict[str, Any] | None: ...
    async def set(self, key: str, value: dict[str, Any], ttl: int | None = None) -> None: ...

# data/fundamental/rate_limit.py
class TokenBucket:
    def __init__(self, rate: float, capacity: int) -> None: ...
    async def acquire(self) -> None: ...  # blocks until token available
```

**Tool function signatures** (decorated with `@mcp.tool()`):

| Tool | Signature |
|------|-----------|
| `run_backtest` | `(pipeline_config: str, symbol: str, start: str, end: str) -> str` |
| `list_pipelines` | `() -> str` |
| `get_pipeline_run` | `(run_id: str) -> str` |
| `generate_candidates` | `(strategy_id: str, count: int = 5) -> str` |
| `query_pool` | `(status: str | None = None) -> str` |
| `promote_candidate` | `(candidate_id: str) -> str` |
| `evaluate_strategy` | `(strategy_id: str) -> str` |
| `get_health_metrics` | `(strategy_id: str, period: str = "90d") -> str` |
| `compute_fitness` | `(stats_json: str) -> str` |
| `get_fundamental_data` | `(ticker: str, start: str | None, end: str | None) -> str` |
| `get_financial_ratios` | `(ticker: str) -> str` |
| `get_market_data` | `(series_id: str = "GDP") -> str` |

All tools return JSON strings. Callers parse the response — no MCP Pydantic wrappers needed at return (MCPServer serializes to JSON-RPC natively).

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| **Unit** | `SqliteCache`, `TokenBucket` | In-memory SQLite, isolated per test with `tmp_path` |
| **Unit** | `YahooFinanceProvider`, `FredProvider` | `resp`x mock for `httpx`, test without live API |
| **Unit** | `AbstractDataProvider` ABC | Verify `TypeError` on instantiation, contract enforcement |
| **Integration** | Cache + rate limiter lifecycle | Concurrency tests with `asyncio.gather` |
| **Integration** | MCP tools | `Client(mcp)` in-memory — no transport needed (v2 API) |
| **Integration** | Full provider pipeline | Mock API, real SQLite cache, real token bucket |
| **E2E** | `python -m quantlab.mcp` | Subprocess launch, tool call via `mcp` Inspector (manual/CI) |

20+ new tests. Use `pytest.mark.asyncio` (existing project convention). All mocks via `unittest.mock` / `resp`x — no new test deps.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. The MCP server exposes data tools only; no command execution or VCS manipulation.

## Migration / Rollout

No migration required. New packages are additive — no existing functionality is modified.
