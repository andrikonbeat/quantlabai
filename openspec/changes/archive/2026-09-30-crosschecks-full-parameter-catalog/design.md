# Design: CrossChecks Full Parameter Catalog

## Technical Approach

Hybrid typed + `raw_xml` approach. The KB YAML files become the evidence-first catalog with schema extensions for XML traceability. SDK models extend `CrossChecksConfig` to cover WhatIf and MonteCarloRetest method leaves. The builder gains ~80+ regex mappings for scalar leaves and helper functions for nested Settings/AcceptanceSettings. Recursive Condition trees stay as `raw_xml` passthrough to avoid over-modeling.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Fully recursive Condition model | Complete round-trip, but high maintenance across SQX versions | Rejected |
| Typed scalar leaves + `raw_xml` for Conditions | Loses fine-grained Condition editing, but stable across versions | Chosen |
| Separate catalog service | Extra moving part, unclear consumer | Rejected |
| KB YAML as single source of truth | Tightly couples docs to code, but evidence-first per spec | Chosen |

## Data Flow

    KB YAML (catalog)
        ↓ read
    Agent / Builder Agent
        ↓ configure
    BuildConfig / CrossChecksConfig
        ↓ map
    project_builder._apply_build_config()
        ↓ regex replace
    Build-Task1.xml (in .cfx zip)
        ↓ serialize
    CrossChecksConfig.to_xml()
        ↓ produce
    summary() → JSON + text

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/cfx/models.py` | Modify | Add WhatIfConfig, extend MonteCarloRetest with method params, add acceptance settings models |
| `sdk/quantlab/sqx/project_builder.py` | Modify | Add ~80+ entries to `_BUILD_CONFIG_MAP`, add helper functions for Settings/AcceptanceSettings |
| `knowledge/structured/sqx-kb/144.2953/parameters/Cross checks/*.yaml` | Modify | Add xml_path, element_name, type, default, range fields |
| `sdk/tests/test_cfx.py` | Modify | Add round-trip tests for WhatIf and MonteCarloRetest methods |
| `sdk/tests/sqx/test_project_builder.py` | Create | Add builder mapping tests for new CrossChecks fields |

## Interfaces / Contracts

### KB YAML extension (per entry)
```yaml
name: Walk-Forward Optimization
sqx_name: Walk-Forward Optimization
tab: Cross checks
section: 3. EXTENSIVE (SLOWEST)
type: config
xml_path: CrossChecks/WalkForwardOptimization/Settings/WalkForward
element_name: WalkForward
default: period=12, optimization=6
range: period 1-100, optimization 1-50
what_it_does: ...
how_it_works_in_sqx: ...
quant_trading_role: ...
status: verified
sqx_version: '144.2953'
evidence_ref: assets/.../project.cfx
```

### Summary contract
```json
{
  "dialect": "automatic_retest",
  "enabled_tabs": ["WalkForwardOptimization", "MonteCarloRetest"],
  "typed_values": {
    "wf_period": 12,
    "wf_optimization": 6,
    "mc_number_of_simulations": 10
  },
  "needs_review": []
}
```
Text: `dialect=automatic_retest tabs=WalkForwardOptimization,MonteCarloRetest wf_period=12 wf_optimization=6 mc_number_of_simulations=10`

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Model round-trip for WhatIf + MonteCarloRetest | Parse CFX XML → model → to_xml() → compare canonical XML |
| Unit | Builder regex mappings | `_apply_build_config` with `BuildConfig` overrides, assert XML contains expected values |
| Integration | Catalog extraction | Parse KB YAML + CFX evidence, assert every entry has `evidence_ref` and correct `xml_path` |
| E2E | Summary contract | `CrossChecksConfig.summary()` returns both JSON dict and single-line text |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required. Existing `raw_xml` fallback preserves backward compatibility. `needs_review` entries warn but do not block unless `strict` mode is enabled.

## Open Questions

- [ ] Confirm WhatIf method parameter names with SQX 145.x evidence before locking schema
- [ ] Decide whether `OptProfileSysParamPermutation` scalar fields (`ProfitOptPct`, `AvgProfit`) get typed models or stay `raw_xml`

## Implementation Sequence

1. **KB schema extension** — add xml_path, element_name, type, default, range to all 10 YAML files
2. **SDK model extension** — add WhatIfConfig, extend MonteCarloRetest/RetestWithHigherPrecision with typed leaves, update `from_xml`/`to_xml`
3. **Builder mapping** — add ~80+ entries to `_BUILD_CONFIG_MAP`, add `_apply_acceptance_settings` helper
4. **Summary contract** — implement `summary()` returning JSON + text, add `needs_review` warning
5. **Tests** — model round-trip, builder mapping, catalog extraction, summary contract
6. **Version drift handler** — invalidate to `needs_review` on sqx_version mismatch
