# Tasks: MCP Bridge + Fundamental Analysis

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~600-700 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Foundation + Data) → PR 2 (Bridge + Tools) → PR 3 (Tests + Polish) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Deps + mcp/models + data providers (cache, rate-limit, yahoo, fred, base ABC) | PR 1 | `pytest tests/data/fundamental/ -x` | `python -c "from quantlab.data.fundamental.yahoo import YahooFinanceProvider; print('OK')"` | `git revert` of `pyproject.toml` + `sdk/quantlab/data/fundamental/` + `sdk/quantlab/data/__init__.py` |
| 2 | Bridge + all domain tool modules | PR 2 | `pytest tests/mcp/ -x` | `python -m quantlab.mcp --help` (verify boot + tool registration) | `git revert` of `sdk/quantlab/mcp/` (independent of PR 1 data layer) |
| 3 | All tests + polish | PR 3 | `pytest tests/ -x --cov=quantlab` | Full test suite | Revert test files only — no production code change |

## Phase 1: Foundation

- [x] 1.1 Add `mcp`, `yfinance`, `pandas-datareader` to `sdk/pyproject.toml`
- [x] 1.2 Create `sdk/quantlab/data/__init__.py` (package marker)
- [x] 1.3 Create `sdk/quantlab/data/fundamental/__init__.py` + `base.py` (`AbstractDataProvider` ABC)
- [x] 1.4 Create `sdk/quantlab/data/fundamental/cache.py` (`SqliteCache` with TTL)
- [x] 1.5 Create `sdk/quantlab/data/fundamental/rate_limit.py` (`TokenBucket` rate limiter)
- [x] 1.6 Create `sdk/quantlab/mcp/__init__.py` (exports) + `mcp/models.py` (MCP Pydantic models)

## Phase 2: Core Implementation

- [x] 2.1 Create `sdk/quantlab/mcp/__main__.py` (`python -m quantlab.mcp` entry)
- [x] 2.2 Create `sdk/quantlab/data/fundamental/yahoo.py` (`YahooFinanceProvider` via `yfinance`)
- [x] 2.3 Create `sdk/quantlab/data/fundamental/fred.py` (`FredProvider` via `pandas-datareader`)
- [x] 2.4 Create `sdk/quantlab/mcp/bridge.py` (MCPServer, tool registration, subsystem singletons)
- [x] 2.5 Create `sdk/quantlab/mcp/pipeline_tools.py` (`run_backtest`, `list_pipelines`, `get_pipeline_run`)
- [x] 2.6 Create `sdk/quantlab/mcp/evolution_tools.py` (`generate_candidates`, `query_pool`, `promote_candidate`)
- [x] 2.7 Create `sdk/quantlab/mcp/health_tools.py` (`evaluate_strategy`, `get_health_metrics`, `compute_fitness`)
- [x] 2.8 Create `sdk/quantlab/mcp/fundamental_tools.py` (`get_fundamental_data`, `get_financial_ratios`, `get_market_data`)

## Phase 3: Testing

- [x] 3.1 Unit tests: `cache.py` (TTL, hit/miss, expiry with in-memory SQLite + `tmp_path`)
- [x] 3.2 Unit tests: `rate_limit.py` (token-bucket acquire, refill, concurrent safety with `asyncio.gather`)
- [x] 3.3 Unit tests: `yahoo.py` + `fred.py` — 4 real API tests (Yahoo AAPL/MSFT, FRED GDP/UNRATE) — all passing
- [x] 3.4 Unit tests: `bridge.py` — 4 tests: init, server name, 11 tool registration, tool descriptions
- [x] 3.5 Integration: MCP models — 9 tests covering ErrorCode, MCPError, ToolRequest, ToolResponse, frozen models, JSON serialization
- [x] 3.6 Integration: MCP bridge with lazy subsystem loading (12 tools registered, no early imports)
- [x] 3.7 Integration: provider tests with real cache + real rate limiter + real APIs
- [x] 3.8 E2E: server boots with `python -c "from quantlab.mcp.bridge import QuantLabMCPServer; s=QuantLabMCPServer(); print(len(s.mcp._tool_manager.list_tools()))"` — 12 tools confirmed

## Phase 4: Polish

- [x] 4.1 Verify `python -m quantlab.mcp` boots and registers all tools without error
- [x] 4.2 Final review: `__all__` exports, `__init__.py` re-exports, no stale imports
