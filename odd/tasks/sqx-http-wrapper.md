# ODD Feature: SQX HTTP API Wrapper + Shelling Replacement

## Context
PoC completed: SQX 145 exposes full sqcli command set via HTTP API at `http://localhost:5050/call?cmd=<command>`. This replaces 3400+ lines of fragile subprocess shelling in `cli_wrapper.py` (1191 lines, 255 call sites) and `project_builder.py` (2236 lines).

## Decision
Four-phase replacement:
1. **Wrapper HTTP** — typed client with parsed responses
2. **Gradual migration** — feature flag, one command category per PR
3. **Process Manager** — SQX lifecycle as a managed service
4. **Deprecate shelling** — delete subprocess code entirely

## Scope

### In Scope
- `sqx_http_client.py` — async HTTP client with Pydantic response models
- Feature flag `USE_SQX_HTTP` (env var + settings)
- Migration of all 255 call sites in `cli_wrapper.py`
- `sqx_process_manager.py` — start/stop/health/wait-ready
- Removal of `cli_wrapper.py` subprocess logic
- Removal of sqcli invocation from `project_builder.py`
- Tests for each phase

### Out of Scope
- MCP stdio/HTTP (not available in dev build)
- GUI/webserver integration
- AI chat internals
- JCloud deployment changes

## Tasks

### Phase 1: HTTP Wrapper (core value)
- [ ] **1.1** Create `sdk/quantlab/sqx/http_client.py` with `SQXHttpClient`
- [ ] **1.2** Define Pydantic models for all 17 command category responses
- [ ] **1.3** Implement methods: `project.*`, `databank.*`, `symbol.*`, `instrument.*`, `data.*`, `session.*`, `ai.*`, `portfolio.*`, `stockgroup.*`, `brokerprofile.*`, `tools.*`, `license.*`, `run`, `deletefile`, `waitfor`, `execute`, `exit`
- [ ] **1.4** Add error hierarchy: `SQXError`, `SQXCommandError`, `SQXTimeout`, `SQXNotReady`, `SQXParseError`
- [ ] **1.5** Add retry logic (exponential backoff), timeout config, request/response logging
- [ ] **1.6** Unit tests with mocked HTTP (pytest + respx/httpx-mock)
- [ ] **1.7** Integration test against live SQX (requires SQX running)

### Phase 2: Gradual Migration (feature flag)
- [ ] **2.1** Add `USE_SQX_HTTP` env var + `settings.SQX_USE_HTTP` (default false)
- [ ] **2.2** Create `cli_wrapper_new.py` that delegates to HTTP client when flag enabled
- [ ] **2.3** Migrate `-project` commands (PR 1)
- [ ] **2.4** Migrate `-databank` commands (PR 2)
- [ ] **2.5** Migrate `-symbol` / `-instrument` commands (PR 3)
- [ ] **2.6** Migrate `-data` commands (PR 4)
- [ ] **2.7** Migrate `-session` / `-ai` / `-portfolio` / `-stockgroup` / `-brokerprofile` / `-tools` / `-license` (PR 5)
- [ ] **2.8** Migrate `-run` / `-deletefile` / `-waitfor` / `-execute` / `-exit` (PR 6)
- [ ] **2.9** Update `project_builder.py` to use new wrapper (feature-flagged)

### Phase 3: Process Manager
- [ ] **3.1** Create `sdk/quantlab/sqx/process_manager.py` with `SQXProcessManager`
- [ ] **3.2** Implement `ensure_running(config)` → starts SQX, waits for `/call?cmd=-h` ready, returns handle
- [ ] **3.3** Implement `graceful_shutdown()` → `-exit` → wait → `SIGTERM`
- [ ] **3.4** Support multiple instances (Builder, Retester, Optimizer) with dynamic ports + lock files
- [ ] **3.5** Health check endpoint + automatic restart on crash
- [ ] **3.6** Pytest fixtures: `sqx_instance` (function), `sqx_session` (session)
- [ ] **3.7** Update integration tests to use process manager fixtures

### Phase 4: Deprecate Shelling
- [ ] **4.1** Set `USE_SQX_HTTP=true` as default in CI/test
- [ ] **4.2** Delete `cli_wrapper.py` subprocess implementation
- [ ] **4.3** Delete sqcli invocation code from `project_builder.py`
- [ ] **4.4** Remove `sqcli` from PATH/runtime dependencies where possible
- [ ] **4.5** Update docs/README with new architecture
- [ ] **4.6** Full test suite passes with HTTP-only path

## Acceptance Criteria
- [ ] All 255 call sites migrated and tested
- [ ] `pytest -q sdk/tests/sqx/` passes (unit + integration)
- [ ] Integration tests deterministic (no flaky port/JVM issues)
- [ ] Builder + Retester can run in parallel (two SQX instances)
- [ ] Feature flag rollback works (`USE_SQX_HTTP=false`)
- [ ] No subprocess `sqcli` calls remain in codebase

## Applicable Checks
- `SQX_FORCE_MOCK=1 python3 -m pytest -q sdk/tests/sqx/` — unit tests
- `python3 -m pytest -q tests/sqx_integration/` — integration (requires SQX)
- `ruff check sdk/quantlab/sqx/` — lint
- `mypy sdk/quantlab/sqx/` — type check

## Risks / Rollback
- **Risk**: HTTP API changes between SQX builds
- **Mitigation**: Version detection via `-h` response; response parsing defensive
- **Rollback Phase 1-2**: `USE_SQX_HTTP=false` — instant fallback to subprocess
- **Rollback Phase 3**: Process manager is additive; old lifecycle still works
- **Rollback Phase 4**: Git revert single commit

## Evidence
- PoC: `odd/tasks/sqx-mcp-poc.md` — HTTP API verified complete
- Memory: id 281 (`sqx-http-api/replacement`)

## Commits
- (pending) Phase 1: HTTP wrapper + models + tests
- (pending) Phase 2: Migration PRs (6)
- (pending) Phase 3: Process manager + fixtures
- (pending) Phase 4: Cleanup + defaults flip