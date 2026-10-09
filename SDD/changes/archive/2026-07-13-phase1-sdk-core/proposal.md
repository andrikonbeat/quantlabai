# Proposal: Phase 1 — SDK Core

## Intent

Build the foundational Python SDK for QuantLab AI. Enable researchers to define strategies in a DSL, translate them to SQX `.cfx` format, invoke SQX CLI operations (in dry-run mode without SQX installed), read backtest results, compute statistics, and organize research artifacts in a Knowledge Lake. This is the first executable layer — everything replaceable, SQX-optional.

## Scope

### In Scope
- Python SDK package (`quantlab/`) with 6 modules
- Knowledge Lake filesystem structure (`knowledge/`)
- Java strategy templates (`strategies/`)
- Dry-run mode for all SQX CLI operations
- Cross-platform support (WSL/Linux + Windows)

### Out of Scope
- End-to-end DSL→SQX→results pipeline integration (Phase 2)
- Multi-agent architecture
- Knowledge Lake full processing pipelines (ingestion, graph building, embedding)
- Actual SQX CLI execution
- Strategy deployment / JCloud integration

## Capabilities

> Contract with sdd-spec. No existing specs — all capabilities are new.

### New Capabilities
- `research-dsl`: Parse human-readable strategy DSL into structured models
- `sqx-translator`: Convert DSL models → `.cfx` (XML inside ZIP) format
- `sqx-cli-wrapper`: Abstracted CLI interface for `sqcli.exe` with dry-run mode
- `result-reader`: Parse SQX Databank CSV/XLSX output into Pydantic models
- `knowledge-storage`: Manage Knowledge Lake directory structure and file conventions
- `statistics-engine`: Compute performance metrics from backtest results

### Modified Capabilities
None — greenfield project, no existing specs.

## Approach

Flat monorepo: Python SDK (`sdk/quantlab/`) with 6 independent modules. Java exists only as generated templates (`strategies/`). SQX integration is layered (DSL → CFX → CLI → Reader → Stats) with an adapter pattern for `sqcli.exe`. Every CLI path has a dry-run fallback producing documented mock results. Knowledge Lake is filesystem-first, Git-versioned, with 5 directories under `knowledge/`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/dsl/` | New | Strategy DSL parser |
| `sdk/quantlab/translate/` | New | DSL → .cfx translator |
| `sdk/quantlab/cli/` | New | SQX CLI wrapper + dry-run |
| `sdk/quantlab/readers/` | New | Result readers |
| `sdk/quantlab/stats/` | New | Statistics engine |
| `sdk/quantlab/tools/` | New | Utilities (platform, paths) |
| `knowledge/{raw,structured,graph,embeddings,datasets}/` | New | Knowledge Lake structure |
| `strategies/` | New | Java strategy templates |
| `sdk/pyproject.toml` | New | Package config |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| SQX CLI undocumented behavior changes | Low | Adapter pattern, dry-run mode, version-lock SQX |
| Dual-stack (Python + Java) toolchain friction | Med | Java is template-only, no Java build in SDK itself |
| Knowledge Lake structure over-engineered for phase 1 | Med | Deliver skeleton only — empty dirs + path conventions |

## Rollback Plan

Delete `sdk/`, `knowledge/`, `strategies/`, `config/`, `campaigns/` directories. Revert `openspec/` to pre-change state. No git repo — manual removal is the rollback.

## Dependencies

- Python 3.11+ (runtime)
- Java 17+ (for strategy compilation only — not SDK runtime)
- No SQX installation required (dry-run mode)

## Success Criteria

- [ ] All 6 SDK modules have unit tests passing
- [ ] `research-dsl` parses a complete strategy definition to structured model
- [ ] `sqx-translator` produces a valid `.cfx` zip from DSL model
- [ ] `sqx-cli-wrapper` runs all commands in dry-run mode without SQX installed
- [ ] `result-reader` parses a sample Databank CSV into Pydantic models
- [ ] `statistics-engine` computes at least 5 standard metrics from parsed results
- [ ] `knowledge-storage` creates the 5-directory skeleton with metadata files
- [ ] Platform detection works correctly on both WSL/Linux and Windows
