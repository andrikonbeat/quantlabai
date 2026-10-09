# Design: Guardian as First-Class Orchestration Agent with Bidirectional Feedback

## Technical Approach

Hybrid (proposal approach 3, REQ-641..644): a first-class `quantlab-guardian` subagent (config + prompt, campaign pattern) whose SDK entry `execute_guardian_directive()` wraps the EXISTING `guardian_evaluate` and `live-ops` stages' `execute()` via a constructed `PipelineContext` — no stage edits, no `PHASES` change (REQ-37). The bidirectional envelope reuses `FeedbackRecord`/`next_cycle_inputs()` (REQ-34): guardian → orchestrator as `GuardianReport`; orchestrator → guardian as bounded `GuardianDirective` (`evaluate | live_ops_status | escalation_ack`). Escalation ack round-trips `ops_surface.ack()` (REQ-36). Verified: `live.py` already carries the staged `Sequence | Iterable` widening with backward-compat tests at `sdk/tests/test_guardian/test_live.py:100-125` — assumed in scope.

## Architecture Decisions

| Decision | Options | Tradeoff | Decision |
|---|---|---|---|
| D1 Layer split | agent-only · SDK-bus · hybrid | agent-only loses testable contract; bus lacks agent identity | Hybrid — envelope is typed SDK, dispatch is agent |
| D2 Envelope home | `feedback.py` (canonical REQ-34) · new `envelope.py` · prompt-only | prompt-only untestable; new module splits REQ-34 spec target | `feedback.py` — additive pure dataclasses; keeps REQ-34 canonical, matches delta spec; agent glue in new `agent.py` |
| D3 Agent execution | reuse stage `execute()` via `PipelineContext(config, artifacts)` · duplicate stage logic | duplication drifts; reuse = literal wrap satisfying REQ-641 "wrap the existing stages" | Reuse — `agent.py` calls `GuardianEvaluationAgentStage().execute(ctx)` and `LiveOpsStage().execute(ctx)` unmodified |
| D4 Uncommitted `live.py` widening | assume in scope · block | already staged + backward-compat tested | Assume; flag at apply (risk L) |
| D5 Phase 14 delegation | `campaign.md` delegates to guardian · keep inline | inline keeps passive library status | Delegate — campaign keeps loop ownership/gates; folds guardian's `GuardianReport` into its Result Contract |
| D6 Test-claim correction | trust exploration "untested" · verify | exploration stale | `FeedbackRecord` (`tests/guardian/test_feedback.py`), `LiveOpsStage` (`tests/pipeline/test_live_ops_stage.py`) ARE covered; gap = `GuardianEvaluationAgentStage.execute()` behavior + new envelope |

## Data Flow

```
orchestrator.md GUARDIAN route ──task──▶ quantlab-guardian (guardian.md)
  directives: evaluate | live_ops_status | escalation_ack   (REQ-643, bounded)
       │
       ▼ execute_guardian_directive()  sdk/quantlab/guardian/agent.py
  ├─ evaluate ──────▶ GuardianEvaluationAgentStage.execute(ctx) ─▶ guardian_state
  │                  └─ evaluate_live(points) ─▶ FeedbackRecord (feedback.py)
  ├─ live_ops_status─▶ LiveOpsStage.execute(ctx) ─▶ live_ops_status (needs archive_bundle; hold fail-closed)
  └─ escalation_ack ─▶ ops_surface.ack(alert_id) ─▶ EscalationAlert | None   (REQ-36)
       │
       ▼ GuardianReport {guardian_state, feedback.next_cycle_inputs(),
  campaign phase 14 ◀── live_ops_status, escalations_acked}  ──▶ next-cycle generation
```

## File Changes

| File | Action | Description |
|---|---|---|
| `~/.config/opencode/prompts/quantlab/guardian.md` | Create | Agent prompt: directive intake, report envelope, ack via ops_surface, NO-phase rule |
| `~/.config/opencode/opencode.json` | Modify | `agent.quantlab-guardian` (quantlab-campaign pattern incl. `task: {"*":"deny","quantlab-*":"allow"}`); orchestrator task gains explicit `"quantlab-guardian": "allow"` |
| `~/.config/opencode/prompts/quantlab/orchestrator.md` | Modify | Intent table + GUARDIAN section (dispatch via task; non-guardian stays) |
| `~/.config/opencode/prompts/quantlab/campaign.md` | Modify | Phase 14 delegates Guardian flow to `quantlab-guardian`; folds report envelope; gates/PHASES untouched |
| `sdk/quantlab/guardian/feedback.py` | Modify | Additive pure `GuardianDirective`, `GuardianReport`, `build_report()` reusing `next_cycle_inputs()` |
| `sdk/quantlab/guardian/agent.py` | Create | `execute_guardian_directive()` — stage-wrap glue + ops_surface ack |
| `tests/guardian/test_feedback.py` | Modify | Envelope contract tests (extension) |
| `sdk/tests/test_guardian/test_guardian_agent.py` | Create | Directive execution + flow-integrity-after-run tests |
| `sdk/tests/test_pipeline_agent_stages.py` | Modify | Behavior test for `GuardianEvaluationAgentStage.execute()` |
| `sdk/quantlab/campaign/flow.py`, `agents/ops_surface.py`, `guardian/orchestrator.py`, `pipeline/stages/{agent_stages,live_ops_stage}.py` | Unchanged | `PHASES` stays 14; stages consumed as-is; ack reused |

## Interfaces / Contracts

```python
@dataclass(frozen=True)
class GuardianDirective:          # feedback.py — bounded (REQ-643)
    kind: Literal["evaluate", "live_ops_status", "escalation_ack"]
    campaign_id: str
    alert_id: str | None = None   # escalation_ack
    points: Sequence[EquityPoint] | Iterable[EquityPoint] | None = None  # evaluate
    research_config: dict = field(default_factory=dict)

@dataclass(frozen=True)
class GuardianReport:             # feedback.py
    guardian_state: dict[str, Any] | None
    feedback: FeedbackRecord | None          # .next_cycle_inputs() consumed downstream
    live_ops_status: dict[str, Any] | None
    escalations_acked: tuple[str, ...] = ()  # alert ids acked, never fabricated

async def execute_guardian_directive(
    directive: GuardianDirective, *, ops_surface: Any | None = None,
) -> GuardianReport:             # agent.py — impure glue
```

Unknown `kind` raises `ValueError` before execution; report carries NO gate/flow fields; empty `points` → `feedback=None` yet envelope still carries `guardian_state` (REQ-644 s2).

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | Envelope: kind bounded; `build_report` reuses `next_cycle_inputs()` (degradation/drawdown/delta) | extend `tests/guardian/test_feedback.py` |
| Unit | `execute_guardian_directive` evaluate → `guardian_state` + `FeedbackRecord`; no-signal still carries state | new `sdk/tests/test_guardian/test_guardian_agent.py` |
| Integration | `live_ops_status` via `LiveOpsStage` (hold fail-closed w/o `archive_bundle`); ack round-trip + unknown id → `None` surfaced | `test_guardian_agent.py` |
| Flow integrity | After agent run: `assert_flow(PHASES)` passes, `len(PHASES)==14`, `STAGE_FOR_PHASE`/registry unchanged, no gate import | `test_guardian_agent.py` + `tests/campaign/test_flow_segments.py` |
| Config/E2E | opencode.json parses: agent registered, `"*":"deny"` first, explicit allow; prompt GUARDIAN row present; non-guardian intents never route (REQ-642) | static config asserts in verify; prompt-route scenario tests |

## Threat Matrix

Reference rows (VCS/PR/exec taxonomy):

| Boundary | Applicability | Reason |
|---|---|---|
| Documentation-like paths | N/A | Prompts are `{file:}`-loaded instructions, never executables |
| Git repository selection | N/A | No `git -C`/path-authority changes |
| Commit state | N/A | No commit automation added |
| Push state | N/A | No push/refspec handling |
| PR commands | N/A | No PR automation |

Applicable extension — agent routing/delegation boundary (must propagate to tasks + RED tests unchanged):

| Boundary | Min adversarial cases | Design response | Planned RED tests |
|---|---|---|---|
| Intent routing authority (GUARDIAN row) | guardian keyword false-positive; non-guardian intent | Safe: guardian intents → `task quantlab-guardian`; unknown stays (REQ-642 s2). Failure: misroute → agent returns `unrecognized directive` partial envelope, never touches gates/flow | Routing-table test: guardian intents map, unrelated intents do NOT; classifier rejects unknown kind |
| Delegation ownership (task permission) | typo agent name; denied task bypass | Safe: explicit `"quantlab-guardian": "allow"` under `"*": "deny"`. Failure: unknown task denied → orchestrator reports failure, no invented fallback | Config parse: agent registered + allowlist entry; wildcard-deny still first |
| Directive boundedness (REQ-643) | auto-approve/reorder attempt | Safe: `ValueError` pre-execution; report lacks gate/flow fields. Failure: out-of-band directive mutating flow | `GuardianDirective` kind validation; post-run flow/registry unchanged assert |
| Escalation ack integrity (REQ-36) | ack unknown id; fabricated ack | Safe: `None` surfaced; report claims only real acked ids. Failure: silent fake success | Ack round-trip + unknown-id test |

## Migration / Rollout

No data migration. Additive envelope + new agent; `PHASES`/schema untouched, so no `FlowIntegrityError` path. Rollback: `git revert` of agent block, routing row, `campaign.md` phase 14 restores inline flow; reverted envelope code is deleted, not migrated.

## Open Questions

- [ ] Ack `ops_surface` instance source: resolve from `AutonomousMonitorDaemon` wiring (REQ-41) or inject per-directive? (decide in apply; default `None` → graceful no-op in report)
- [ ] Campaign phase 14 re-dispatch: `quantlab-campaign` task wildcard `quantlab-*` already permits `quantlab-guardian` — confirm no explicit entry needed.