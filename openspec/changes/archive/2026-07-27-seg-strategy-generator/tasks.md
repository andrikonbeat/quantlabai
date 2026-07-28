# Tasks: SEG — Strategy Evolution Generator

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 400–600 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Layer 1 core) → PR 2 (Layer 2 facade) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Layer 1: GA/NG/CV rewrites + orchestrator wiring | PR 1 | `pytest tests/evolution/ -v` | PipelineRunner via `evolution-pipeline` config | Revert PR 1 commits; pool JSON survives |
| 2 | Layer 2: facade + MCP tool + CLI | PR 2 | `pytest tests/mcp/test_seg_tools.py -v` | MCP server `generate_strategy` call | Revert PR 2 commits; Layer 1 unaffected |

## Phase 1: Core Implementation

- [x] 1.1 Rewrite `genetic.py` — CfxPatcher param parsing, gaussian/boundary/crossover operators, tournament selection, PipelineRunner backtest delegation
- [x] 1.2 Rewrite `novelty.py` — DSL ResearchConfig generation from context, CFX translation via `generate_cfx_archive`, short backtest, fitness scoring
- [x] 1.3 Rewrite `validator.py` — 3-tier BT→WF→MC validation via PipelineRunner, per-stage pass/fail, pool persistence
- [x] 1.4 Wire `orchestrator.py` — real PipelineRunner in `_execute_signal`/`_run_cycle`, pass cfx_content from pool
- [x] 1.5 Unit tests: GA mutation operators (gaussian, boundary, blend, single-point) with known inputs
- [x] 1.6 Unit tests: DSL building-block combos, CFX translation, empty-context edge case
- [x] 1.7 Unit tests: validator tier gating (skip WF when BT fails, skip MC when WF fails), partial failure recording

## Phase 2: Unified Entry Point

- [x] 2.1 Create `seg.py` — `StrategyGenerator` facade with `generate()`, `evolve()`, `list_strategies()`, mode dispatch
- [x] 2.2 Create `seg_tools.py` — `generate_strategy` MCP tool (11th tool, 12th counting list_tools)
- [x] 2.3 Modify `bridge.py` — import and register seg_tools in `_register_tools()`
- [x] 2.4 CLI scaffolding — StrategyGenerator importable for CLI integration
- [x] 2.5 MCP tool tests (4 tests: generator init, tool registration, generate intent, list strategies)

## Phase 3: Integration Tests

- [x] 3.1 Integration: MCP `generate_strategy` tool registered and callable (18 MCP tests passing)
- [x] 3.2 Integration: StrategyGenerator facade tested with minimal intent
- [x] 3.3 Full flow: 122 tests passing across evolution + data + MCP
