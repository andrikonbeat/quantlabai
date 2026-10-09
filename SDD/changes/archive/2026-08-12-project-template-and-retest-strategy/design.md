# Design: Project Template Engine and Adaptive Retest Strategy

## Technical Approach

Thin layer over the existing CustomProject DSL and CfxPatcher. Three built-in templates (`standard_research`, `quick_validation`, `deep_robustness`) serialize to multi-task `.cfx` via `generate_cfx_archive` + `CfxWriter`. The Adaptive Retest Agent runs as a RetesterStage pre-processor: it reads the CFX, applies adaptive mutations via `CfxPatcher`, and selects the retest task variant. No new SQX schema is required.

## Architecture Decisions

### Decision: Template Registry
**Choice**: Case-insensitive dict in `sdk/quantlab/phase4/template_registry.py` with `TemplateDefinition` dataclass and `DuplicateTemplateError`.  
**Alternatives considered**: External YAML registry; subclass-based registry.  
**Rationale**: Dict gives O(1) lookup and keeps built-in templates importable without filesystem discovery.

### Decision: Serialization via Existing DSL
**Choice**: Build `CustomProject` from template definition, call `generate_cfx_archive`, then `CfxWriter.write`.  
**Alternatives considered**: Direct BuildTask assembly bypassing DSL.  
**Rationale**: Reuses verified task ordering, databank routing, and round-trip validation; template definitions stay immutable.

### Decision: Validation via Golden Probe
**Choice**: Reuse `customproject.validator.validate_golden` with sqcli readiness probe before structural checks.  
**Alternatives considered**: Lightweight XML-only validation.  
**Rationale**: The existing validator is the proven fail-closed gate (REQ-24); probe is already injectable for tests.

### Decision: Read-Only Signal Inspection
**Choice**: `CfxReader.read` + targeted section extraction from `RetesterData`, `CrossChecks`, `Rankings`.  
**Alternatives considered**: Parse CSV exports or SQX status text.  
**Rationale**: CFX is the single source of truth; reading the archive avoids side effects and extra sqcli calls.

### Decision: Retest Mode Selection Hook
**Choice**: Pure function `select_retest_mode(signals: RetestSignals, metadata: dict | None) -> RetestMode`.  
**Alternatives considered**: Class-based strategy with state.  
**Rationale**: Pure function is trivially testable, composable, and respects the precedence rules (CFX metadata > signals > default).

### Decision: AutomaticRetest Dedicated Renderer
**Choice**: Replace `render_generic` for `AutomaticRetest` with a renderer that emits AutomaticRetest-specific CrossChecks (no Monte Carlo/Walk-Forward sections).  
**Alternatives considered**: Parameterize generic renderer with flags.  
**Rationale**: Keeps the catalog contract explicit; the 21-task catalog already lists `AutomaticRetest` separately.

## Data Flow

    Template Registry
         │
         ▼
    CustomProject DSL ──► generate_cfx_archive ──► CfxWriter ──► .cfx
         │                                                    │
         │                 sqcli readiness probe               │
         │                 validate_golden                     │
         │                                                    ▼
         │                                              CfxReader
         │                                                    │
         │                                                    ▼
    Template Metadata ◄── RetestSignals ◄── inspect_cfx_signals
         │                    │
         │                    ▼
         │           select_retest_mode
         │                    │
         ▼                    ▼
    Task XML Gen       CfxPatcher mutations
                              │
                              ▼
                        RetesterStage ◄── RetesterConfig (DSL fallback)
                              │
                              ▼
                        Retester.run

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/phase4/template_registry.py` | Create | Template registry, definitions, `serialize_template` |
| `sdk/quantlab/phase4/adaptive_retest_agent.py` | Create | `RetestSignals`, `inspect_cfx_signals`, `select_retest_mode`, `apply_adaptive_mutations` |
| `sdk/quantlab/customproject/renderers.py` | Modify | Add `render_automatic_retest` replacing generic renderer for `AutomaticRetest` |
| `sdk/quantlab/customproject/generator.py` | Modify | Inject `<Template>` metadata into task XML when project has template_name |
| `sdk/quantlab/pipeline/stages/retester_stage.py` | Modify | Accept optional CFX path; parse config from CFX when present |
| `sdk/quantlab/phase4/retester.py` | Modify | Add `select_retest_mode` hook and `from_cfx` constructor path |

## Interfaces / Contracts

```python
class RetestMode(str, Enum):
    AUTOMATIC_RETEST = "AutomaticRetest"
    RETEST = "Retest"

@dataclass(frozen=True)
class TemplateDefinition:
    name: str
    tasks: list[CustomProjectTask]
    databanks: list[DatabankSpec]
    cross_checks_preset: dict[str, Any]

@dataclass
class RetestSignals:
    last_run_status: str | None
    trade_count: int | None
    monte_carlo_passed: bool | None
    walkforward_passed: bool | None
    databank_coverage: float | None

def serialize_template(name: str, output_path: Path) -> Path: ...
def inspect_cfx_signals(cfx_path: Path) -> RetestSignals: ...
def select_retest_mode(
    signals: RetestSignals,
    metadata: dict | None = None,
) -> RetestMode: ...
def apply_adaptive_mutations(cfx_path: Path, mode: RetestMode) -> Path: ...
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Registry lookup, duplicate rejection, case-insensitivity | Instantiate registry, assert resolve/reject |
| Unit | `select_retest_mode` rules and precedence | Table-driven tests for all spec scenarios |
| Unit | `inspect_cfx_signals` read-only behavior | Hash CFX before/after; assert missing fields default to None |
| Unit | AutomaticRetest renderer output | Assert task XML has `type="AutomaticRetest"` and no MC/WF CrossChecks |
| Integration | Round-trip CFX → patch → re-read | `CfxReader.read` after `apply_adaptive_mutations` |
| Golden | All 3 templates vs 144/2953 | `validate_golden` with injected probe runner |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required. DSL path remains default; CFX config is opt-in via explicit CFX path argument. Template metadata is additive and ignored by pre-existing generators. Rollback: remove new modules; templates remain as static CFX files importable via `sqcli`.

## Open Questions

- [ ] Confirm whether `AutomaticRetest` CrossChecks parameters should be configurable per-template or hardcoded to SQX defaults.
- [ ] Verify SQX `AutomaticRetest` task XML schema against current 144/2953 goldens before final renderer implementation.
