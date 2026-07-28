# Fundamental Analysis Specification

Provide Yahoo Finance and FRED data with SQLite caching and token-bucket rate limiting.

## Requirements

### Stock Data

The system MUST retrieve historical prices and fundamentals from Yahoo Finance.

- GIVEN a valid ticker and date range
- WHEN `get_fundamental_data` is called
- THEN OHLCV prices and fundamentals are returned, cached in SQLite

### Financial Ratios

The system MUST compute P/E, P/B, ROE, ROA, and Debt/Equity from financials.

- GIVEN a ticker with available financials
- WHEN `get_financial_ratios` is called
- THEN all five ratios are returned with source metrics

### Economic Indicators

The system MUST retrieve GDP, unemployment, and CPI from FRED via `pandas-datareader`.

- GIVEN FRED series IDs for GDP, UNRATE, CPIAUCSL
- WHEN `get_market_data` is called
- THEN latest values are returned with timestamps

### Caching

Responses MUST be cached in SQLite with configurable TTL (default 1h). Cache hits within TTL MUST skip upstream calls.

- GIVEN a cached query within TTL
- WHEN the same query is made
- THEN cached data is returned, upstream API is NOT called

- GIVEN a cached query past TTL
- WHEN requested
- THEN fresh data is fetched and the cache is updated

### Rate Limiting

Token-bucket limits MUST be enforced per provider (defaults: 5 req/s Yahoo, 10 req/s FRED). Excess requests MUST be rejected with a 429 error.

- GIVEN requests exceeding the allowed rate
- WHEN additional requests arrive
- THEN they are rejected with a rate-limit error

- GIVEN requests within the allowed rate
- WHEN processed
- THEN they execute normally

### Error Handling

API timeouts, HTTP errors, and missing tickers MUST yield structured errors without crashing.

- GIVEN a non-existent ticker symbol
- WHEN `get_fundamental_data` is called
- THEN a structured error is returned

### Async

Fetches SHOULD use `httpx.AsyncClient`. Rate limiter and cache MUST be async-safe.

- GIVEN multiple concurrent provider requests
- WHEN issued simultaneously
- THEN they run concurrently without blocking the event loop
