# Proposal: Phase 3 — CFX Engineering & Builder Control

## Intent

Build a CFX Editor module in Python that can read, modify, and write StrategyQuant project CFX files programmatically. This is the foundation for OpenCode to control Builder campaigns without GUI interaction — the missing link between the SDK and automated quantitative research.

## Scope

### In Scope
1. `quantlab.cfx` module with Pydantic models mapping 1:1 to real CFX XML structure
2. `CfxReader`: open CFX (config and project types), parse XML → typed models
3. `CfxWriter`: typed models → XML → ZIP (matching exact format quirks)
4. `CfxPatcher`: high-level API for LLM-driven modifications
5. Domain methods: set_market(), add_timeframe(), enable_block(), set_genetic(), set_date_range(), add_ranking_condition()
6. Complete test suite with real CFX files as fixtures
7. CLI integration: load modified CFX via sqcli, launch Builder, verify

### Out of Scope
- JForex deployment
- Portfolio management
- Optimizer automation
- Retester automation (beyond modifying its config via CFX)
- UI for CFX editing
- GUI integration

## Capabilities

### New Capabilities
- `cfx-editor`: Read, modify, and write SQX project CFX files programmatically. Pydantic models mapping 1:1 to real CFX XML structure, with CfxReader, CfxWriter, CfxPatcher, and domain methods for market, timeframe, building blocks, genetics, date ranges, and ranking conditions.

### Modified Capabilities
- `sqx-translator`: The current translator generates wrong-format XML (`<StrategyQuantX><Project>...`). It will be rewritten to use the new cfx-editor models, producing proper CFX archives. The spec will be updated to reflect the new model-driven approach.

## Approach

Bottom-up: models first (1:1 fidelity to real CFX XML), then reader, then writer, then patcher. Reuse nothing from the current translator — start fresh with `quantlab.cfx` package.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `quantlab/cfx/` | New | CFX editor package (models, reader, writer, patcher) |
| `quantlab/translate/` | Modified | Translator must be rewritten to use new CFX models |
| `tests/cfx/` | New | Test suite with real CFX fixtures |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Schema version changes across SQX updates | Medium | Version-aware parsing, fail fast on unknown schemas |
| Embedded XML in attributes is fragile | Medium | Use XML parser for inner content, not regex |
| Magic negative values must be preserved exactly | Low | Store raw values as-is, never interpret |
| Effort: 3-4 weeks for complete module | Medium | Bottom-up approach reduces rework risk |

## Rollback Plan

Revert to the current translator (`quantlab/translate/`) which generates the old-format XML. The new `quantlab.cfx/` package is additive — existing pipeline code continues to work until the orchestrator is updated to use the new module.

## Dependencies

- StrategyQuant X with sqcli for integration testing
- Real CFX project files as test fixtures (from user's SQX installation)

## Success Criteria

- [ ] CFX round-trip: read real CFX → modify → write → load back in sqcli → Builder runs with modified settings
- [ ] At least 6 real project CFX files can be parsed and re-written
- [ ] LLM can modify a CFX via CfxPatcher without manually constructing XML
