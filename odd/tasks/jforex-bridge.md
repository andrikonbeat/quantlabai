# ODD Feature: JForex 4 Bridge

## Context
SQX 145 embeds JForex 4. The JForex API (`com.dukascopy.api`) provides real-time access to:
- **IFinancialInstrument** — specs (pipValue, pipScale, tickScale, minTradeAmount, leverage, currencies, swaps, sessions)
- **IDataService** — market data (swaps, rollovers, high/low, sentiment, offline times, server properties)
- **IHistory** — historical data (ticks, bars, orders, feed data, point & figure, range bars)
- **IAccount** — account state (equity, balance, leverage, margin, positions)
- **IContext** — central access (engine, history, account, dataService, indicators, engine)
- **IClient** (DDS2) — connection to JForex platform (demo/live)

Currently QuantLab hardcodes or approximates these (spread=3 pips, slippage=1, frozen symbols, no swaps, no commissions, no sessions/holidays). The bridge will replace hardcoded values with live JForex data.

## Decision
Build a **lightweight Java bridge** managed by our `SQXProcessManager`, exposing JForex data via REST + WebSocket matching our HTTP API patterns. Feature-flagged (`QUANTLAB_JFOREX_BRIDGE=1`).

## Scope

### In Scope
- Java bridge (`jforex-bridge` module) with REST + WebSocket
- Connect to JForex demo (configurable live later)
- Expose: instruments, swaps/rollovers, spreads, sessions, account, positions, orders, ticks, bars
- Process manager integration (start/stop/health, multi-instance)
- Python client + feature flag
- Feature-flagged integration in `cli_wrapper` / `project_builder`

### Out of Scope
- Full JForex strategy execution (use SQX for backtest)
- JCloud deployment (separate agent)
- MT4/MT5 bridge
- Binary options / MT5 bridge

## Tasks

### Phase 1: Java Bridge Core
- [x] **1.1** Create `sdk/quantlab/jforex_bridge/` module structure (Maven)
- [x] **1.2** Add JForex API + DDS2 dependencies (local JARs → Maven local)
- [x] **1.3** Implement `JForexBridgeApplication` (Spring Boot minimal / Jetty)
- [x] **1.4** Implement `JForexStrategy` (implements `IStrategy`) for market data
- [x] **1.5** Implement `JForexClientManager` (connect/disconnect/reconnect, demo/live)
- [x] **1.6** REST endpoints: `/instruments`, `/swaps`, `/spreads`, `/sessions`, `/account`, `/positions`, `/orders`
- [x] **1.7** WebSocket endpoints: `/ws/ticks`, `/ws/bars`, `/ws/account`
- [x] **1.7** Health check + graceful shutdown (`/health`, `POST /shutdown`)
- [x] **1.8** Unit tests (mock JForex context)

### Phase 2: Process Manager Integration
- [x] **2.1** Add `JForexProcessManager` (extends `SQXProcessManager` pattern)
- [x] **2.2** `ensure_running()` with JForex-specific config (JNLP, user, pass, demo/live)
- [x] **2.3** Dynamic port allocation + lock files
- [x] **2.4** Health check + auto-restart on crash
- [x] **2.5** Pytest fixtures: `jforex_instance`, `jforex_session`

### Phase 3: Python Client + Feature Flag
- [x] **3.1** `sdk/quantlab/jforex/client.py` — async HTTP + WebSocket client
- [x] **3.2** Pydantic models for all responses
- [x] **3.3** Feature flag `QUANTLAB_JFOREX_BRIDGE` in `settings.py`
- [x] **3.3** Integrate in `cli_wrapper.py` (delegate to bridge when flag=1)
- [x] **3.4** Update `project_builder.py` to use bridge for swaps/commissions/specs

### Phase 4: Tests & Migration
- [ ] **4.1** Integration tests with live demo account
- [ ] **4.2** Feature flag ON in CI (`pytest.ini`, CI)
- [ ] **4.3** Rollback test (flag OFF → subprocess fallback)
- [ ] **4.4** Docs: architecture, config, troubleshooting

## Acceptance Criteria
- [ ] Bridge starts, connects to JForex demo, serves REST + WS
- [ ] `/instruments` returns specs with real swaps, pip values, leverage
- [ ] `/swaps` returns long/short swap rates + triple-swap calendar
- [ ] `/spreads` returns real-time bid/ask spreads
- [ ] `/sessions` returns trading sessions + holidays per instrument
- [ ] `/account` returns equity, balance, margin, leverage
- [ ] WebSocket streams ticks/bars/account updates in real-time
- [ ] Process manager starts/stops bridge reliably
- [ ] Feature flag toggles bridge ON/OFF without code changes
- [ ] All existing tests pass with flag ON (CI)

## Applicable Checks
- `./gradlew build` in `sdk/quantlab/jforex_bridge/`
- `pytest -q sdk/tests/jforex/` (unit + integration with `JFOREX_INTEGRATION=1`)
- `QUANTLAB_JFOREX_BRIDGE=1 pytest -q tests/campaign/` (integration)

## Risks / Rollback
- **Risk**: JForex demo account limits (concurrent connections, rate limits)
- **Mitigation**: Connection pooling, rate limiting, graceful degradation
- **Risk**: JForex API changes between versions
- **Mitigation**: Version pinning, defensive parsing, integration tests
- **Rollback**: Feature flag OFF → full subprocess fallback (current behavior)

## Evidence
- JForex API interfaces confirmed: `IFinancialInstrument`, `IDataService`, `IHistory`, `IAccount`, `IContext`, `IStrategy`
- JARs obtained: `JForex-API-2.13.88.jar`, `DDS2-jClient-JForex-3.6.14.jar` (from dukas-proxy Gradle build)
- Dukascopy Maven repo: `https://www.dukascopy.com/client/jforexlib/publicrepo` (requires auth for direct download, works via Gradle)
- dukas-proxy reference implementation: Spring Boot + WebSocket + REST

## Commits
- (pending) Phase 1: Java bridge core
- (pending) Phase 2: Process manager integration
- (pending) Phase 3: Python client + feature flag
- (pending) Phase 4: Tests & migration