# Exploration: MCP Bridge + Fundamental Analysis

## Current State

QuantLab SDK is a Python 3.11+ async quantitative research platform with six major subsystems: Pipeline, Agents, Evolution, Health, MetaGuardian, and Statistics. All entry points are async-native with Pydantic models throughout.

## Affected Areas

| Module | What Changes |
|--------|-------------|
| `pyproject.toml` | Add `mcp` + fundamental data deps (`yfinance`, `pandas-datareader`) |
| `sdk/quantlab/mcp/` | **New** — Hybrid bridge: single entry, modular domain tools |
| `sdk/quantlab/data/fundamental/` | **New** — Fundamental data providers (Yahoo, FRED) |
| `sdk/quantlab/pipeline/runner.py` | Wrap `PipelineRunner.run()` as MCP tool |
| `sdk/quantlab/evolution/orchestrator.py` | Expose cycle/signal tools |
| `sdk/quantlab/evolution/pool.py` | Expose pool query tools |
| `sdk/quantlab/health/calculator.py` | Expose compute as health tool |
| `sdk/quantlab/guardian/orchestator.py` | Expose evaluate as guardian tool |

## Recommendation

**Hybrid Bridge** (Approach 3):
- `quantlab/mcp/bridge.py` — main MCP server, registers tools from domain modules
- `quantlab/mcp/pipeline_tools.py` — `run_backtest`, `list_pipelines`, `get_pipeline_run`
- `quantlab/mcp/evolution_tools.py` — `generate_candidates`, `query_pool`, `promote_candidate`
- `quantlab/mcp/health_tools.py` — `evaluate_strategy`, `get_health_metrics`, `compute_fitness`
- `quantlab/mcp/fundamental_tools.py` — `get_fundamental_data`, `get_financial_ratios`, `get_market_data`
- `quantlab/mcp/models.py` — shared MCP-specific Pydantic models
- `quantlab/data/fundamental/` — providers for Yahoo Finance, FRED, with local caching

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Serialization at MCP boundary | Medium | `model_dump(mode="json")` at every tool boundary |
| API rate limits on data | High | `httpx.AsyncClient`, SQLite cache, rate limiting |
| Async loop conflicts | Medium | Test with anyio, single event loop |
| Evolution engine partially stubbed | Low | Document experimental tools |

Ready for proposal.
