# Exploration: Phase 2 — SQX Local Execution Pipeline

## Current State

### What Exists (Phase 1 — Complete)
The SDK foundation is solid with 124 tests passing:

1. **DSL Models** (`dsl/models.py`, `dsl/parser.py`) — `ResearchConfig` with market, timeframe, building blocks, strategies, acceptance criteria; YAML serialization
2. **Translator** (`translate/translator.py` + `translate/cfx.py`) — `ResearchConfig` → XML → `.cfx` ZIP archive; dry-run writes raw XML
3. **CLI Wrapper** (`cli/runner.py`) — `Executor` protocol, `MockExecutor` (dry-run), `RealExecutor` (subprocess), `CliRunner` facade
4. **Result Readers** (`readers/databank.py`) — `DatabankCSVReader` + `DatabankXLSXReader` for trades, equity curves, summary stats
5. **Statistics Engine** (`stats/engine.py`) — PF, Sharpe, Sortino, MDD, MAR, RF, expectancy computations
6. **Knowledge Store** (`knowledge/store.py`) — 5-directory Knowledge Lake with YAML index, format validation
7. **Exceptions** (`tools/exceptions.py`) — `QuantLabError` hierarchy with ParseError, ValidationError, TranslationError, SQXNotFoundError, TimeoutError, InsufficientDataError
8. **Platform** (`tools/platform.py`) — cross-platform path resolution, binary name, app dirs

### SQX Binary Discovery (CRITICAL)

The sqcli binary at `assets/SQX_144_2953_linux_20260601/sqcli` is an ELF x86-64 executable (Java launcher) with bundled JVM. The `help.txt` inside `internal/web/SQUANT/help.txt` reveals the ACTUAL CLI interface:

```
sqcli.exe -project action=start name=Builder              # Start a project
sqcli.exe -project action=loadconfig name=Builder file=...  # Load CFX config
sqcli.exe -project action=status name=Builder               # Check status
sqcli.exe -project action=stop name=Builder                 # Stop project
sqcli.exe -project action=list                              # List projects
sqcli.exe -databank action=export project=Builder ...       # Export results
sqcli.exe -databank action=list project=Builder             # List databanks
sqcli.exe -license action=info                              # License status
sqcli.exe -license action=update code=xxxxx                 # Activate license
sqcli.exe -exit                                             # Shutdown
sqcli.exe -run file=commands.txt                            # Batch commands
sqcli.exe -data action=update symbols=...                   # Update market data
```

**Key behavioral finding**: sqcli starts a server (port 5050) and processes CLI commands sequentially. It exits immediately with "Missing license" when no license is present. With a license it would stay resident, processing commands until `-exit`.

Also notable:
- Pre-existing user projects in `assets/.../user/projects/`: `Builder`, `Retester`, `Optimizer`, `PortfolioMaster`, etc.
- Builder project has `project.cfx` (which is actually a ZIP containing `config.xml`)
- Retester project adds a `databanks/Results/` directory
- ServletMCP plugin exists (MCP — possibly Master Control Protocol, not Model Context Protocol)

### The Gap Between Phase 1 and a Complete Pipeline

What's missing:

| Step | Phase 1 Status | Phase 2 Needs |
|------|---------------|---------------|
| Create ResearchConfig | ✅ DSL models + parser | — |
| Translate to CFX | ✅ XML generation + ZIP packaging | — |
| Execute in SQX | ❌ `RealExecutor` passes command strings but no campaign lifecycle exists | Need campaign manager that: starts sqcli, loads config, runs project, monitors progress, exports results |
| Read results | ✅ CSV/XLSX readers | Need to wire export command + readback |
| Compute stats | ✅ StatisticsEngine | Need to wire from results |
| Store artifacts | ✅ KnowledgeStore | Need to wire from pipeline |
| Handle errors | ❌ No retry/checkpoint/partial failure | Add recovery layer |
| Track progress | ❌ No callback/reporting | Add progress reporting |
| License mgmt | ❌ No license detection | Add license checks |

### Existing Executor Issue

The current `RealExecutor.execute()` splits the command string on whitespace:
```python
proc = subprocess.run([str(self._binary), *command.split()], ...)
```

This is problematic for two reasons:
1. sqcli arguments use `=` syntax (`action=start name="Builder"`) — spaces in values would break with `split()`
2. The execution model is one-shot per command; for campaigns we need session management (start sqcli, send multiple commands, read output, exit)

## Affected Areas

### New Files Needed
- `sdk/quantlab/pipeline/__init__.py` — Pipeline module init
- `sdk/quantlab/pipeline/campaign.py` — CampaignRunner orchestrator
- `sdk/quantlab/pipeline/dispatcher.py` — sqcli command dispatcher (HTTP? subprocess?)
- `sdk/quantlab/pipeline/progress.py` — Progress reporting (callbacks, events)
- `sdk/quantlab/pipeline/license.py` — License state detection and management
- `sdk/quantlab/pipeline/models.py` — Pipeline-specific models (CampaignResult, CampaignStatus, etc.)
- `sdk/tests/test_pipeline.py` — Pipeline tests

### Existing Files That Need Changes

| File | Why Affected | Change |
|------|-------------|--------|
| `sdk/quantlab/cli/runner.py` | Current `RealExecutor` has fragile command parsing | Fix argument handling for `key=value` syntax with spaces; add session/daemon management |
| `sdk/quantlab/tools/exceptions.py` | New error types for pipeline failures | Add `LicenseError`, `CampaignError`, `PipelineError` |
| `sdk/quantlab/tools/platform.py` | Need to resolve sqcli base directory (for data/ dirs) | Add `resolve_sqcli_dir()` |
| `openspec/specs/sqx-cli-wrapper/spec.md` | Spec needs updating for new capabilities | Add campaign, progress, license requirements |
| `knowledge/` | Will receive campaign results | No code change — data population |

## Approaches

### Approach A: Full Pipeline Orchestrator (Recommended)
Build a complete `CampaignRunner` that manages the full lifecycle: license check → CFX generation → sqcli dispatch → progress tracking → result export → parsing → stats → storage.

**Key design decisions:**
- `CampaignRunner` accepts a `ResearchConfig` + optional callbacks
- Uses a `CommandDispatcher` that wraps sqcli subprocess calls with proper argument handling
- Implements a polling loop for project status via `-project action=status`
- Exports results via `-databank action=export` → CSV → `DatabankCSVReader`
- Orchestrates: translate → dispatch → poll → export → read → compute → store
- Progress via callback protocol (not just polling)
- License detection at startup via `-license action=info`
- Checkpoint-based recovery (save intermediate state to JSON)

**Pros:**
- Complete end-to-end user experience
- All pipeline logic in one coherent module
- Fits the "research director" architecture goal
- Can be fully tested with MockExecutor for all phases
- Checkpoint support enables resume for long campaigns

**Cons:**
- Larger surface area in one release
- Some parts (sqcli interaction patterns) are speculative without a license
- Progress callback API needs upfront design

**Effort: Medium-High**

### Approach B: Minimal Viable Pipeline (MVP)
Build only the essential bridge: a `CampaignRunner` that wraps the existing pieces with a simple sequential flow. No progress tracking, no checkpoints, no automatic retry.

**Key design decisions:**
- Sync-only execution (blocking call)
- Fix `RealExecutor` argument handling minimally
- CampaignRunner is a simple method chain: translate → save CFX → run sqcli → export → read → return
- License check is a separate utility function, not integrated
- Results returned as a dict/struct, not persisted automatically
- No progress reporting — just log output

**Pros:**
- Fastest path to "working" pipeline
- Minimal new code
- Easy to test with MockExecutor
- Unlocks integration testing immediately

**Cons:**
- No progress feedback (bad UX for 30-min+ campaigns)
- No resume capability (failure = full restart)
- No checkpointing (lose work on crash)
- License management is manual
- Will need refactoring when adding these later
- Doesn't match the "AI research director" product vision

**Effort: Low-Medium**

### Approach C: Campaign Runner with HTTP Server Mode
Given sqcli starts an HTTP server on port 5050, build the dispatcher as an HTTP client instead of subprocess per command. The `sqcli -gui` command starts a web UI server — we could interact via HTTP REST calls.

**Key design decisions:**
- `sqcli -gui` starts the server in background
- `CampaignRunner` controls through REST API instead of repeated subprocess
- Reuse existing `subprocess` to start/stop the daemon
- Use `httpx` or `aiohttp` for API calls
- Real-time progress via server-sent events or polling the web API

**Pros:**
- Single persistent SQX session (no startup overhead per command)
- Potentially richer API via REST than CLI
- Could enable real-time progress via WebSocket/SSE
- Cleaner architecture than subprocess chaining

**Cons:**
- Unknown REST API surface (we only have CLI help.txt, no API docs)
- Would need to reverse-engineer the HTTP endpoints by examining web app
- Higher risk — cannot test without a license
- Added dependency on async HTTP library
- The server mode might behave differently than CLI mode
- Port 5050 conflicts if multiple instances needed

**Effort: High (very speculative)**

## Recommendation

**Approach A (Full Pipeline Orchestrator)** is the right call — but delivered incrementally as a chain of work units that each provide value:

1. **PR 1: Foundation** — Fix `RealExecutor` argument handling, add `CommandDispatcher` for proper sqcli command construction, add `LicenseManager` utility, add pipeline models and error types. Everything testable with MockExecutor.
2. **PR 2: Core CampaignRunner** — Build the sequential execution flow: translate → dispatch → poll → export → read → compute → store (as `CampaignResult`). Progress callback protocol. Full test coverage with MockExecutor.
3. **PR 3: Resilience** — Checkpoint/recovery, partial failure handling, configurable retry, timeout management per campaign phase. Integration test scaffolding.

This approach gives a working pipeline after PR 2 while keeping PR 3's resilience as a valuable but separable improvement.

### Key Design Unknowns (Require Investigation or License)

1. **sqcli output format for `-project action=status`** — What does it print? JSON? Plain text? Without a license we can only guess.
2. **sqcli execution model** — Does sqcli process one command and exit, or stay resident? The `-exit` command suggests it stays resident, but the "Missing license" exit suggests otherwise.
3. **Databank export column names** — We mapped columns in `databank.py` (EntryTime, ExitTime, etc.) — needs real SQX output to verify.
4. **CFX schema completeness** — The current XML may be missing required elements for real SQX execution.
5. **Project naming** — Does each campaign need a unique project name? Conflicts?

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **sqcli behavior differs with license** | All subprocess patterns could be wrong | Build with MockExecutor-first design; PR 1 focus on getting the arguments right |
| **CFX XML schema incomplete** | SQX rejects our .cfx files | Add validation step; reverse-engineer Builder/project.cfx XML |
| **Unknown status output format** | Progress polling design may be invalid | Make status parser pluggable; parse as text initially |
| **No license for testing** | Cannot verify real execution | Design so 90% of code works with MockExecutor; integration testing requires user to obtain license |
| **Port 5050 conflicts** | Cannot run multiple campaigns | Design dispatcher to handle port config; document port management |
| **Databank column mapping wrong** | Parse failures at pipeline output | Parser column mapping is already alias-based — extend as needed |

## Unknowns

1. What is the actual output format of `-project action=status`?
2. Does sqcli need to be kept alive between commands or is each invocation independent?
3. What is the relationship between the HTTP server (port 5050) and CLI commands? Does the CLI talk to the server?
4. Can we pass a `.cfx` file directly to start a run, or must it be loaded into a project first?
5. Are there required XML elements in project.cfx that our translator doesn't generate?
6. What percentage of strategy building steps can run without market data configured?

## Ready for Proposal

**Yes** — the exploration is complete enough to proceed to `sdd-propose`. The core architecture is well-understood: sqcli CLI commands are documented, the gap between Phase 1 and a working pipeline is clearly defined, and three approaches with tradeoffs have been identified. The most significant unknowns (sqcli runtime behavior, status output format, CFX schema completeness) can be resolved during design by building abstraction layers that isolate those concerns.
