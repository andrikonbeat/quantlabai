# Proposal: Per-Phase LLM Sub-Agent Delegation

## Intent
One subagent (`quantlab-campaign`) runs all 14 phases inline today. Each phase gets a dedicated agent: focused role, fresh context, bounded authority, isolation, auditable handoffs. The loop becomes orchestration: dispatch, fold, gate, next. User sees the same flow, clearer per-phase status, contained failures.

## Scope
**In:** 14 phase subagents (opencode.json + prompts; judgment phases full, mechanical thin); SDK contract `sdk/quantlab/campaign/delegation.py` (`PhaseDirective`/`PhaseResult` + `execute_phase()` glue); campaign.md rewrite; orchestrator.md routing note; drift fix (repo canonical + sync + parity test); tests.
**Out:** flow.py PHASES untouched (REQ-37); no re-architecture of `sdk/quantlab/agents/`; no reorder/rename/new phases; no gate-policy changes.

## Capabilities
**New:**
- `campaign-phase-delegation`: SDK contract — directives, result envelopes, `execute_phase` glue, enforced authority.
- `campaign-phase-agents`: agent family — registration, prompts, permissions, sync.

**Modified:**
- `campaign-orchestrator` (REQ-01): loop delegates per-phase via `task`.
- `human-gates`: decision-file/question protocol extended to phase agents, fail-closed (REQ-11/38).
- `permission-model`: deny-first allowlists for 14 agents.
- `intent-routing`: phase-routing note in orchestrator.md.

## Approach
Exploration #2 (SDK-backed), SDD-5 template: PR1 SDK+tests; PR2 agents+prompts+registry+sync; PR3 campaign.md rewrite+tests. Phase agents single-dispatch; long ops return scripts — orchestrator shell executes, subagents never wait (cancel = task-cancel). Alternatives: prompt-only (cheaper, no enforced authority); family grouping (cheaper, spans REQ-37 gates).

## Product Questions (auto defaults)
1. All 14 phases → agents? **Yes** — literal per-phase; mechanical phases (dispatch/compile/demo) thin.
2. Long-phase cancellation? **Orchestrator scripts + task-cancel**.
3. Prompt source of truth? **Repo canonical**; sync + parity test.
4. Human gates? **Phase agents present them** via question tool; HOLD bubbles fail-closed.
5. Envelope? **Result Contract reuse** + `PhaseResult` fields.

## Affected Areas
opencode.json · `{phase}.md` prompts · campaign.md · AI/opencode mirrors · `delegation.py` · flow.py (unchanged) · test files.

## Risks
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| REQ-37 mutation | High | wrap-only; integrity test |
| Long-running wait | High | orchestrator shell; policy per agent |
| Prompt drift ×14 | High | repo canonical + parity test |
| Gate bypass | Med | `question: allow`; fail-closed HOLD |
| Permission gaps | Med | deny-first allowlists |
| Test coupling | Med | extend asserts; SQX_FORCE_MOCK intact |

## Rollback Plan
Per-slice git revert; no PHASES/schema migration; sync revert restores live prompts.

## Dependencies
SDD-5 guardian pattern; Result Contract (REQ-01); AD-4 decision-file; `task` delegation.

## Sizing
~1,300–1,500 lines. `Decision needed before apply: No` · `Chained PRs recommended: Yes` · `400-line budget risk: High`. Slices: PR1 ~400 · PR2 ~500 · PR3 ~350.

## Success Criteria
- [ ] 14 phases via dedicated agents; envelopes folded
- [ ] `assert_flow`/`assert_flow_segments` pass; PHASES unchanged
- [ ] Parity test green (repo ⇄ live)
- [ ] Gates intact; no subagent waits on long ops
