# Proposal: MCP Bridge + Fundamental Analysis

## Intent

Enable AI assistants to execute QuantLab operations (backtests, evolution, health scoring) via MCP tools, and add fundamental data analysis capabilities to support research workflows.

## Scope

### In Scope
- Hybrid Bridge MCP server — single `bridge.py` entry point, domain tool modules
- Pipeline tools: `run_backtest`, `list_pipelines`, `get_pipeline_run`
- Evolution tools: `generate_candidates`, `query_pool`, `promote_candidate`
- Health tools: `evaluate_strategy`, `get_health_metrics`, `compute_fitness`
- Fundamental Analysis — Yahoo Finance and FRED data providers with SQLite caching + rate limiting
- Fundamental tools: `get_fundamental_data`, `get_financial_ratios`, `get_market_data`
- Shared MCP Pydantic models (`quantlab/mcp/models.py`)
- New deps: `mcp`, `yfinance`, `pandas-datareader` in `pyproject.toml`

### Out of Scope
- Full integration of fundamental data into the evolution engine
- Web UI or dashboard for MCP tool management

## Capabilities

> Contract between proposal and specs phases.

### New Capabilities
- `mcp-bridge`: MCP server exposing QuantLab subsystems as callable AI tools
- `fundamental-analysis`: External financial data providers with local caching and rate limiting

### Modified Capabilities
- None — behavior changes are additive at the spec level

## Approach

**Hybrid Bridge**: `quantlab/mcp/bridge.py` boots the MCP server and registers tools from domain modules (`pipeline_tools.py`, `evolution_tools.py`, `health_tools.py`, `fundamental_tools.py`). Each module wraps the corresponding subsystem with `model_dump(mode="json")` serialization at the MCP boundary. `quantlab/data/fundamental/` provides Yahoo Finance and FRED clients with `httpx.AsyncClient`, SQLite-backed caching, and token-bucket rate limiting.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/pyproject.toml` | Modified | Add `mcp`, `yfinance`, `pandas-datareader` deps |
| `sdk/quantlab/mcp/` | New | Hybrid bridge server + 4 domain tool modules + models |
| `sdk/quantlab/data/fundamental/` | New | Yahoo Finance + FRED providers with cache/rate-limit |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| API rate limits on Yahoo/FRED | High | SQLite cache + token-bucket rate limiter + retry |
| Async loop conflicts (MCP ↔ QuantLab) | Medium | Single event loop, test with anyio |
| Serialization at MCP boundary | Medium | `model_dump(mode="json")` at every tool boundary |

## Rollback Plan

Remove `sdk/quantlab/mcp/` and `sdk/quantlab/data/fundamental/` packages, revert `sdk/pyproject.toml` dependency additions. No existing functionality is modified.

## Dependencies

- `mcp` (Model Context Protocol Python SDK)
- `yfinance` — Yahoo Finance data
- `pandas-datareader` — FRED API access

## Success Criteria

- [ ] MCP server starts and registers all 9+ tools from domain modules
- [ ] Each tool returns valid JSON via `model_dump(mode="json")` serialization
- [ ] `get_fundamental_data` retrieves and caches stock data from Yahoo Finance
- [ ] `get_market_data` retrieves from FRED with rate-limit compliance
- [ ] Rate limiter prevents >N requests/min per provider
- [ ] SQLite cache serves cached responses with configurable TTL
- [ ] 20+ new tests passing (unit + integration for tools, providers, caching, rate limiting)
