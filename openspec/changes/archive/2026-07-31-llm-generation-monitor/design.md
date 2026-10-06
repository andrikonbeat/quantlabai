# Design: LLM Generation Monitor

## Technical Approach

Standalone `LLMGenerationMonitor` running as a sibling asyncio task to `CampaignMonitor` inside `dispatch_campaign` (opt-in via `llm_config` param, mirroring `on_watcher_event`). `CampaignMonitor` gains `-databank action=list` polling and exposes `current_snapshot()`; the LLM monitor reads that snapshot every N-th tick, builds a compact prompt, calls the LLM through `LLMCircuitBreaker`, validates the verdict via a pydantic model, gates on confidence, human-confirms `stop`, and executes via `ActionExecutor` → HTTP `-project action=stop` + `monitor.cancel()`. Every failure path degrades to "continue, log" so heuristics remain the always-on fallback.

## Architecture Decisions

### D1: Module structure
| Option | Tradeoff | Decision |
|---|---|---|
| New `sdk/quantlab/sqx/llm_generation_monitor.py` | Matches flat sqx package (campaign_monitor, cli_wrapper); no import churn | **Chosen** |
| `sdk/quantlab/sqx/monitors/` package | Future-proof, but restructures existing files | Rejected |
| `quantlab/agents/` | Wrong layer — depends on sqx HTTP + campaign_monitor | Rejected |

### D2: Snapshot sharing
| Option | Tradeoff | Decision |
|---|---|---|
| CampaignMonitor stores latest status/databank counts; LLM monitor reads via `current_snapshot()` | Zero extra HTTP, single observability source, same event loop → no races | **Chosen** |
| LLM monitor polls HTTP itself | Independent, but duplicate requests and divergent state | Rejected |

### D3: Verdict parsing
| Option | Tradeoff | Decision |
|---|---|---|
| Pydantic `Verdict`; strip ```` ```json ```` fences before `json.loads` | Strict validation (Literal enum, 0–1 confidence); codebase already uses pydantic (`LLMConfig`) | **Chosen** |
| Manual dict checks (`llm_research_agent.parse_response` style) | No type coercion; drift-prone | Rejected |
| jsonschema | New dependency | Rejected |

### D4: Confidence threshold
| Option | Tradeoff | Decision |
|---|---|---|
| Default `0.7`, constructor param | False-positive stop is expensive; conservative default, tunable per call site | **Chosen** |
| Env var only / no gate | Hidden config / spec violation | Rejected |

### D5: Human confirmation
| Option | Tradeoff | Decision |
|---|---|---|
| `confirm_stop: Callable[[Verdict], Awaitable[bool]] | None`; default `rich.prompt.Confirm` | Mirrors `on_watcher_event` CLI/callback duality; testable, orchestrator-injectable | **Chosen** |
| Hardcoded rich prompt | Blocks non-interactive tests/integration | Rejected |

### D6: Circuit breaker
| Option | Tradeoff | Decision |
|---|---|---|
| Import `LLMCircuitBreaker` from `quantlab.robustness.llm_circuit_breaker`, constructor-injectable; `await cb.call(_call_llm(...))` | Exact `LLMResearchAgent.generate_config` pattern; injectable for tests | **Chosen** |
| Inline try/except only | No open-state short-circuit | Rejected |

## Data Flow

```
dispatch_campaign (llm_config set?)
  ├── CampaignMonitor task — status + NEW -databank action=list every poll
  │     └── current_snapshot() {status_text, generated, databank_counts, elapsed, baseline}
  ├── LLMGenerationMonitor task — every N-th tick (N default 5)
  │     ├── snapshot = monitor.current_snapshot()
  │     ├── build_prompt(snapshot) → LLM (via LLMCircuitBreaker)
  │     ├── parse Verdict {assessment, severity, detected_issues[], recommended_action, confidence, reasoning}
  │     ├── confidence < 0.7 → log, no action
  │     ├── stop → confirm_stop() → ActionExecutor → HTTP stop + monitor.cancel()
  │     └── any failure (CircuitOpenError / ValidationError / API error) → log, treated as continue
  └── heuristics (CampaignMonitor events) continue unchanged
```

## File Changes

| File | Action | Description |
|---|---|---|
| `sdk/quantlab/sqx/llm_generation_monitor.py` | Create | `Verdict`, `MonitorSnapshot`, `build_prompt`, `parse_verdict`, `ActionExecutor`, `_call_llm`, `LLMGenerationMonitor` |
| `sdk/quantlab/sqx/campaign_monitor.py` | Modify | `-databank action=list` fetch per tick, `parse_databank_counts`, `current_snapshot()`; heuristic events unchanged |
| `sdk/quantlab/sqx/cli_wrapper.py` | Modify | `llm_config`/`on_llm_verdict` params; LLM-monitor task lifecycle in both dispatch paths |
| `sdk/quantlab/sqx/mock_sqx_server.py` | Modify | Rejection mode (growing generation count, static databank 0); never completes until stopped |
| `tests/phase4/test_llm_generation_monitor.py` | Create | Unit + integration tests |

## Interfaces / Contracts

```python
@dataclass
class MonitorSnapshot:  # internal, mirrors WatcherEvent style
    status_text: str
    generated_count: int
    databank_counts: dict[str, int] | None   # None = parse failed (spec)
    elapsed_s: float
    baseline: dict[str, Any]                 # raw cfg + BaselineConfig

class Verdict(BaseModel):                    # strict, pydantic
    assessment: str
    severity: str
    detected_issues: list[str]
    recommended_action: Literal["continue", "stop"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str

LLMGenerationMonitor(
    campaign_id: str, base_url: str,
    snapshot_provider: Callable[[], MonitorSnapshot],
    llm_config: LLMConfig,
    llm_caller: Callable[[str, LLMConfig], Awaitable[str]] | None = None,  # default _call_llm
    circuit_breaker: LLMCircuitBreaker | None = None,
    confirm_stop: Callable[[Verdict], Awaitable[bool]] | None = None,      # default rich Confirm
    confidence_threshold: float = 0.7, poll_every_n: int = 5,
    on_verdict: Callable[[Verdict], None] | None = None) -> None

# dispatch_campaign gains:
llm_config: LLMConfig | None = None   # None ⇒ no LLM monitor, behavior unchanged
on_llm_verdict: Callable[[Verdict], None] | None = None  # mirrors on_watcher_event
```

**Note**: `compute_baseline` lives in `campaign_monitor.py`, not `project_builder.py` (proposal misattributes it). Prompt baseline context is assembled in `_dispatch_real` from cfg_dict values (generations, population, WF/MC, criteria) plus `BaselineConfig`.

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Unit | `parse_databank_counts` (both formats + garbage → None); `build_prompt` includes counts/baseline + JSON schema; `parse_verdict`: valid, fenced, invalid JSON, missing fields, bad confidence → treated as continue + warning | Pure helpers, pytest |
| Unit | Confidence gate (0.65 vs 0.7 → no dispatch); ActionExecutor: stop → stop_action once, continue → no-op | AsyncMock |
| Unit | Circuit open → no exception propagates, poll logged as continue | `LLMCircuitBreaker(failure_threshold=1)` + failing caller |
| Integration | Mock LLM caller stop verdict + confirm True → HTTP stop dispatched; low confidence → nothing; LLM raising → heuristics events still collected | MockSQXServer + injected `llm_caller` |
| E2E | `dispatch_campaign(force_mock=True, llm_config, llm_caller=fake)` on rejection-mode campaign → stopped before completion; without `llm_config` → zero LLM calls, identical result shape | Extend `TestDispatchWithMonitorE2E` |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary is added or changed. All new actions are in-process asyncio plus HTTP API calls on the existing pattern; daemon subprocess lifecycle (`_SQXDaemonHandle`) is untouched.

## Migration / Rollout

No migration. Opt-in: `dispatch_campaign` without `llm_config` is previous behavior exactly (spec scenario). Rollback = remove the parameter.

## Open Questions

- [ ] Real (non-mock) `-databank action=list` output format must be verified during implementation — parser is tolerant, but mock format may differ.
- [ ] Confirm default `poll_every_n=5` (~50s at 10s poll) is acceptable cadence vs LLM cost.
