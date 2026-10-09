# Proposal: Project Template Engine and Adaptive Retest Strategy

## Intent

Users manually assemble CustomProjects or reuse ad-hoc task chains. AutomaticRetest lacks a dedicated renderer, and RetesterStage reads config only from DSL blocks, not from generated CFX. This change delivers reusable project templates and an adaptive retest agent that selects AutomaticRetest vs full Retest based on runtime CFX signals.

## Scope

### In Scope
- Custom Project Template Engine with 3 templates: `standard_research`, `quick_validation`, `deep_robustness`
- Adaptive Retest Strategy Agent that dynamically chooses `AutomaticRetest` vs `Retest`
- Template serialization to multi-task `.cfx` via existing CustomProject DSL
- CfxPatcher-based mutations for adaptive retest configuration
- RetesterStage config sourced from CFX (not only DSL)

### Out of Scope
- New SQX task types or schema changes
- Changes to the 21-task catalog itself
- UI for template selection (CLI-only in first slice)
- Post-retest analysis or report generation beyond existing export

## Capabilities

> This section is the CONTRACT between proposal and specs phases.

### New Capabilities
- `project-template-engine`: Generates pre-configured CustomProject CFX archives from named templates with consistent task ordering and databank routing.
- `adaptive-retest-strategy`: Inspects CFX runtime signals and dynamically selects between AutomaticRetest and full Retest configurations via CfxPatcher mutations.

### Modified Capabilities
- `custom-project-generator`: Add dedicated `AutomaticRetest` renderer and template-aware task XML generation.
- `retester-automation`: Accept configuration from CFX files (not only DSL blocks) and expose hooks for adaptive retest selection.

## Approach

Build the Template Engine as a thin layer over the existing CustomProject DSL and CfxPatcher. Each template declares task lists, filters, and CrossChecks preset for its profile. The Adaptive Retest Agent runs as a RetesterStage pre-processor: it reads the CFX, applies adaptive mutations via `sqcli`/CfxPatcher, and selects the retest task variant. No new SQX schema is required.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `openspec/specs/custom-project-generator/spec.md` | Modified | Add AutomaticRetest renderer and template routing |
| `openspec/specs/retester-automation/spec.md` | Modified | Add CFX-sourced config and adaptive hooks |
| `pipelines/template_engine.py` | New | Template registry and CFX generation |
| `pipelines/adaptive_retest_agent.py` | New | Retest mode selection logic |
| `sdk/cfx_patches.py` | Modified | Add retest mutation primitives |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Templates diverge from SQX golden format | Low | Validate generated CFX against existing 144/2953 goldens via `sqcli -h` readiness probe |
| Adaptive agent chooses wrong retest mode | Medium | Require explicit `retest_mode` override in CFX metadata |
| CfxPatcher mutations are lossy | Low | Round-trip validation and existing version-safety checks |

## Rollback Plan

Remove `pipelines/template_engine.py` and `pipelines/adaptive_retest_agent.py`. Templates remain as static CFX files users can import manually via `sqcli -project action=loadconfig`. RetesterStage falls back to DSL-only config path.

## Dependencies

- Existing `custom-project-generator` and `cfx-editor` specs (completed)
- Verified SQX 144/2953 golden projects (`assets/SQX_144_2953_linux_20260601/`)
- `sqcli` CLI availability in PATH or `SQCLI_PATH`

## Success Criteria

- [ ] 3 templates (`standard_research`, `quick_validation`, `deep_robustness`) generate valid CFX accepted by SQX
- [ ] Adaptive Retest Agent selects retest mode based on CFX signals in 100% of golden project scenarios
- [ ] RetesterStage reads config from CFX when present, falls back to DSL otherwise
- [ ] Zero changes to existing single-task CFX backward compatibility
