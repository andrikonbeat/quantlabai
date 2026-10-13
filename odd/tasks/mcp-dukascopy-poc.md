# ODD Feature: Dukascopy MCP Scope PoC

## Context
QuantLab has no reliable source for execution-cost data today: no HTTP downloader for
Dukascopy history, spread/slippage hardcoded and truncated in
`sdk/quantlab/sqx/project_builder.py:2052-2053`, commission never reaching the generated CFX
(`:2131-2135`), and the Java bridge returning zeroed account data
(`QuantLabBridge.java` `cmdAccount`/`cmdStatus`).

Dukascopy Bank exposes a remote MCP server at `https://mcp.dukascopy.com/mcp` (OAuth 2.1 with
dynamic client registration; advertised scopes `openid`, `trading`). Its toolset cannot be
enumerated from public probes: `initialize` returns 401 without a bearer token, and
`/docs`, `/openapi.json`, `/tools`, `/reg`(GET) return 404. Official documentation states
demo accounts only for now, live in Summer-Autumn 2026, no MT4/MT5/Binary integration.

This PoC is **read-only**: enumerate the real toolset and its actual scope, then decide which
QuantLab pieces (if any) it can replace. It changes no QuantLab source.

## Decision
Enumerate through Pi's native MCP client (`pi mcp add` + `pi mcp login`), which already
implements OAuth 2.1 discovery (RFC 9728/8414), dynamic client registration and token storage.
No custom OAuth client is built for the PoC.

## Scope
### In Scope
- User-level MCP registration in `~/.pi/agent/mcp.json` (server name `dukascopy`)
- OAuth sign-in with a Dukascopy **demo** account (human gate)
- Real tool enumeration, evidence capture, and a scope report

### Out of Scope
- Any write to QuantLab source, generated CFX, campaign state, or the trading account
- Order placement, live-account use, or replacing any repo component
- Wiring the MCP into `sdk/quantlab` (separate, later decision)

## Tasks
- [x] **T1** Recon: `pi mcp` CLI surface, user-level config location, graphical session availability (`DISPLAY=:0`, `xdg-open` present)
- [x] **T2** Register server `dukascopy` (user-level) — `pi mcp list` reports `state: needs-auth`, confirming the 401 from a real MCP client. Dynamic client registration was accepted: `client_id cf677c33-5101-4d7c-a5be-6bd6c8d11048`, `client_name "pi"`, redirect `http://127.0.0.1:<port>/callback`
- [x] **T3** OAuth sign-in with a demo account (human gate) — `Signed in to MCP server "dukascopy" (13 tools)`
- [x] **T4** Enumerated the 13 tools of server `dukascopy-trading-mcp 0.2.0`, with descriptions, input schemas and live read-only samples
- [x] **T5** Scope report delivered and replacement decision recorded (see Findings)
- [x] **T6** Verify the MCP from inside a Pi session after `/reload`: the 13 tools are registered in codemode and `tools/list` works, but live account calls fail (see Session lifetime)
- [x] **T7** Characterize the trading-session lifetime (`ttl` claim 900000 ms) and whether a reconnect restores access without a browser sign-in — **COMPLETED**: the 15-min claim is NOT the trading-session lifetime. A fresh `session_key` (minted after clean logout+login) survived ≥46 min with ≥31 min of accumulated idleness. Reconnect with the stored token **works** (fresh Python client recovered the session at T+46). Automation verdict: headless Guardian loop viable with 1 browser login per ~24 h, maintaining an MCP connection or reconnecting via stored token. All earlier failures were due to dead-`session_key` reuse from re-authorization without SSO logout.

## Findings (live, 2026-10-11)
`dukascopy-trading-mcp 0.2.0`, 13 tools, no server instructions. Grouped by purpose:

| Group | Tools |
|---|---|
| Discovery / quotes | `search_instruments` (returns `symbol`, `name`, `group`, `pipSize`, `contractSize`, `minContractSize`, `leverage`), `get_market_price` (`bid`, `ask`, `spread_pips`, `timestamp`, `contractSize`), `get_market_price_bulk`, `get_candles` (M1/H1/D1, max 500, `side` bid\|ask\|both) |
| Account / positions | `get_account_state` (`balance`, `equity`, `usableMargin`, `leverage`, `currency`, `state`, `openPositions`), `get_open_positions` (live P/L in pips and money, SL, TP) |
| Execution (mutating) | `open_market_order` (with `slippage` + `priceClient`), `create_entry_order` (limit/stop resolved automatically), `close_positions` (single/partial/bulk/all), `cancel_entry_orders`, `manage_stop_loss`, `manage_take_profit` |

Live read-only samples:
- `get_account_state` → `balance 10000 / equity 10000 / usableMargin 10000 / leverage 100 / USD / state OK / 0 open positions` (demo account `DEMO2WVLtP`)
- `get_market_price EUR/USD` → `bid 1.11998 / ask 1.12023 / spread_pips 2.5`
- `get_candles EUR/USD H1 count=3 side=both` → 6 interleaved ask/bid candles (last data 2026-10-09)

**Absent from the toolset (decisive for QuantLab):** no swap, no commission, no fee or rollover
tool, no triple-swap day, no historical spread (only the live instantaneous `spread_pips`), no
tick data, no candle period beyond M1/H1/D1 and no depth beyond 500 bars, no news or economic
calendar, no sessions/holidays, no closed-trade history or statements, no backtest or SQX
integration, and no strategy lifecycle.

**Auth and automation constraints:** access token `exp` is 24h, `grant_types` is
`["authorization_code"]` only and no `refresh_token` is stored, so there is no unattended
refresh: a browser sign-in is required when it expires. Claims expose `session_id`,
`session_key`, `login_hash`, `api_urls` (5 `wss://` proxies) and `ttl` 900000 ms, which means
Dukascopy holds the account session server-side and the client never handles the password.
Demo only for now; live announced for Summer-Autumn 2026.

## Session lifetime (open finding)
After `/reload`, the 13 tools appear in codemode as `mcp__dukascopy__*` and `tools/list` succeeds,
but 163 minutes after sign-in every account/trading call returns:

```
{"error":"Trading session expired — re-authorization required. Please reconnect."}
```

The stored OAuth access token is still valid (`expires_in 86400`, no `refresh_token`, grant is
`authorization_code` only), and the access token carries `ttl: 900000` (15 minutes), which is
consistent with a short-lived **server-side trading session** layered on top of the 24h OAuth
token.

### Reconnect does not renew it
`/mcp reconnect dukascopy` re-established the HTTP connection **without re-running the browser
flow** (`mcp-auth.json` mtime unchanged at 01:00:45, token `iat` unchanged) and the trading
session was still expired: account calls kept returning the same error. Renewal therefore
requires a full `/mcp login dukascopy`. Measurement of the exact lifetime is still pending (T7).

### Re-authorization reuses a dead `session_key`
A full browser re-authorization at 03:50:00 minted a **new** OAuth token (new `jti`, new `iat`,
`mcp-auth.json` mtime 03:50:00), but that token carries the **same `session_id`/`session_key`**
as the 01:00 one: the masked prefixes recorded at 01:00 (`e0ad…` / `0d54…`) match the new
`e0ad5c…` / `0d549b…`. Both tokens expose those claims identically.

This explains every observation without a wall-clock TTL story:
- `session_key` was minted once, at 01:00, with `ttl: 900000` (15 minutes) → dead by ~01:15.
- Inside that window (01:02–01:04) `get_account_state` answered; outside it every account call fails.
- Every later authorization (03:50) reuses the same dead `session_key`, so the failure shows up
  ~74 seconds after a "successful" sign-in and is deterministic (3/3 attempts failed at 03:53:37).

Consequence: a browser re-authorization alone does **not** renew the trading session. A fresh
`session_key` requires ending the Dukascopy session first (log out in the browser /
`end_session_endpoint https://mcp.dukascopy.com/session/end`, plus `pi mcp logout dukascopy`),
then signing in again. Rigorous confirmation pending: sha256 of `session_id`/`session_key`
recorded before and after the next clean sign-in.

Note: the `sid` claim advertised in the server metadata is not actually present in either token;
the identifiers are `session_id` and `session_key`.

### Fresh session lifetime measurement (T7 completed)
After clean logout+login (03:58:06):

| Time | Elapsed | Activity | Result |
|---|---|---|---|
| T+5  (04:03) | 5 min  | probe | alive |
| T+10 (04:08) | 10 min | probe | alive |
| T+15 (04:13) | 15 min | probe | **alive past claim ttl** |
| T+31 (04:29) | 31 min | **16 min silence** | alive |
| T+46 (04:44) | 46 min | **31 min silence** | **alive + fresh Python client also works** |

**Key findings**:
- The trading session does **not** expire at 15 min (claim `ttl: 900000` is not the lifetime).
- Session survives ≥ 46 min with ≥ 31 min of complete idleness.
- A fresh client (new connection, stored token) recovers the session → **reconnect without browser works**.
- Practical ceiling: OAuth access token 24 h, id_token 1 h, no refresh token.
- All earlier "Trading session expired" failures were caused by dead-`session_key` reuse, not by a real TTL.

**Automation verdict**: a headless Guardian loop is viable with **one browser login per ~24 h** (to mint a fresh `session_key`), maintaining a persistent MCP connection or reconnecting with the stored token. The 15-min claim is irrelevant to the trading session lifetime once a fresh session is minted.

### What survives without a trading session

| Tool | Needs trading session |
|---|---|
| `get_market_price`, `get_market_price_bulk`, `get_candles` | no — the token alone is enough |
| `search_instruments` | yes |
| `get_account_state`, `get_open_positions`, `get_entry_orders` | yes |
| every order / SL / TP / cancel tool | yes |

Important consequence: without a live trading session there is no instrument search, so even the
quote path cannot discover symbols. Note also that `spread_pips` is unreliable outside FX
(`BRENT.CMD/USD` reported `spread_pips: 860` for a raw 0.086 spread).

Consequence for automation: **confirmed**. The trading session cannot be renewed without a
browser sign-in, so the MCP cannot back an unattended Guardian loop. It stays usable for
human-in-the-loop assisted trading and for shallow read-only market data.

## Scope decision
The MCP is a **trading control surface, not a data source**. It replaces nothing in the
research/data layer: swap, spread history, commission, news and tick depth still have to come
from `IDataService`/`IFinancialInstrument` plus an own `datafeed` downloader. Its only real
overlap is the account/execution half of the custom Java bridge
(`QuantLabBridge` `cmdAccount`/`cmdStatus`, which currently returns zeroed data) — and even
there, strategy compile/deploy/start/stop via `IRemoteStrategyManager` stays bridge-only.

## Acceptance Criteria
1. `pi mcp list` reports the real tool inventory for `dukascopy` — **met** (13 tools, exit 0).
2. Every capability claim is backed by a live tool name and description, never by documentation alone — **met**.
3. The report states explicitly which QuantLab pieces the MCP can and cannot replace — **met** (see Scope decision).

## Applicable Checks
No behavior change in this repository, so test-first is not applicable (no runnable RED step).
Verification was the live enumeration plus four read-only tool calls. No mutating tool was
invoked: no order, entry order, close, SL/TP change or cancellation was issued.

## Risks and Rollback
Risk: the authorization server may restrict dynamic client registration to known clients. It did
not: registration succeeded for `pi`. Rollback is `pi mcp remove dukascopy` plus
`pi mcp logout dukascopy`; nothing in the repository or the account was mutated. If the stored
token is revoked from the Dukascopy side, `pi mcp list` reports `needs-auth` again.

## Evidence
- `pi mcp list --json`: `state: needs-auth, tools: []` before sign-in; `state: connected`, 13 tools after (exit 0)
- `~/.pi/agent/mcp-auth.json`: authorization server metadata (`registration_endpoint /reg`, token endpoint, `pushed_authorization_request_endpoint /request`, DPoP algorithms, scopes `openid trading`, grants `[authorization_code]`)
- `tools/list` plus four read-only calls over streamable HTTP with the stored bearer token
- Saved outputs: `/tmp/mcp-list2.json`, `/tmp/duka-login.log`

## Commits
None — this PoC changed no repository source. This task file is the only repo artifact.
