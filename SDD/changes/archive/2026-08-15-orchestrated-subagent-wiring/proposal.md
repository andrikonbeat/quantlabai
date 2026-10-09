# Proposal: Orchestrated Subagent Wiring

## Intent

The orchestrated flow is a paper design: `_run_campaign.py` → `execute_campaign()` builds the LEGACY pipeline (`orchestrated=False`), bypassing the 14-phase flow. The only real runner, CLI `campaign run-flow`, is inline Python, no LLM subagents. `delegation.py` has full envelope machinery with ZERO production callers; phase agents' bash allowlist has no executable entry, so they cannot run SDK stages. Violates PRD G1; `guardian-orchestrator` (G9/§8, PRD:334) is missing.

## Scope

### In Scope
1. **F1 — Real runner wiring**: `phase_runner.py` CLI, `execute_phase()` production executors, hybrid delegation, `_run_campaign.py` disposition.
2. **F2 — Enrich 14 phase prompts** with real LLM reasoning over existing SDK classes.
3. **F3 — Guardian-orchestrator**: repo prompt, opencode.json entry, routing, `HUMAN_APPROVE_REPLACEMENT` gate, delegates, sync contract.

### Out of Scope
- No trading functionality, broker integration, or live-trading surfaces.
- No change to 14-phase order (REQ-37) or gate fail-closed semantics (REQ-11).

## Capabilities

> Contract for sdd-spec — names from `openspec/specs/`.

### New
- `phase-runner`: CLI bridging `PhaseDirective` → production executor under `sdk/quantlab/campaign/`, returning validated `PhaseResult` with `LongOpSpec` handoff (F1).
- `guardian-orchestrator`: second first-class orchestrator — prompt, config (primary, visible, deny-first), routing, live gate, delegates (F3).

### Modified
- `campaign-phase-delegation`: `execute_phase()` gains production executors (mock-only today); `_run_campaign.py` retired.
- `campaign-phase-agents`: prompts get reasoning; sync allowlist extends to `guardian-orchestrator.md` (contract + test update).
- `guardian-agent`: intents also routable from `guardian-orchestrator`.

## Approach

**F1**: `phase_runner.py <phase> --directive <json>` parses the directive, resolves the executor, runs the SDK stage, validates/returns `PhaseResult` (REQ-803). Reasoning phases (research/hypothesis/config/review/portfolio/optimize/archive) → LLM subagents; mechanical (dispatch/monitor/compile/deploy/demo) → `LongOpSpec` handoff (REQ-809). Retire `_run_campaign.py` → `campaign run-flow`.

**F2** (phase → class → reasoning): research→`LLMResearchAgent` (KB rationale REQ-203/204/205); hypothesis→`hypothesis_builder/llm.py`; review→reviewer (verdict); monitor→`LLMGenerationMonitor` (stall diagnosis); optimize→optimizer (recommendation); portfolio→`portfolio_agent` (composition); archive→archiver (maintenance plan). Keep `edit:false, write:false`; SDK stages write artifacts (D3).

**F3**: add repo `guardian-orchestrator.md`; opencode.json entry (primary, visible, deny-first); routing row in live `orchestrator.md` (non-managed); `HUMAN_APPROVE_REPLACEMENT` fail-closed gate; delegates `quantlab-guardian-alert`/`quantlab-replacement`; extend `sync_prompts.py` allowlist + update `test_guardian_live_prompt_never_synced`.

## Affected Areas

| Area | Impact |
|------|--------|
| `sdk/quantlab/campaign/phase_runner.py` | New |
| `sdk/quantlab/campaign/delegation.py` | Modified |
| `_run_campaign.py` | Removed |
| `ai/opencode/agents/phase-*.md` (14) | Modified |
| `ai/opencode/agents/guardian-orchestrator.md` | New |
| `ai/opencode/sync_prompts.py` | Modified |
| `tests/campaign/test_prompt_sync.py` | Modified |
| `~/.config/opencode/opencode.json` | Modified |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Runner miswiring executes out-of-scope stages | Med | REQ-803 scope-check + deny-first |
| `_run_campaign.py` retirement breaks flows | Med | Keep `campaign run-flow`; deprecate first |
| Prompt enrichment drifts from parity | Med | REQ-810 parity tests |
| Guardian misconfig reaches live surface | High | `HUMAN_APPROVE_REPLACEMENT` fail-closed (D10/D11) |
| Executor gaps leave a phase un-runnable | High | Mock under `SQX_FORCE_MOCK`; per-phase tests |
| Sync allowlist change breaks tests | Med | Update tests in same change |

## Rollback Plan

- **F1**: revert `phase_runner.py` + executor wiring (mock path returns); restore `_run_campaign.py`.
- **F2**: revert prompt edits; re-run `sync_prompts.py`.
- **F3**: remove opencode.json entry, routing row, prompt; revert allowlist + tests.

## Dependencies

- SDK: `delegation.py`, `guardian/{agent,feedback,orchestrator}.py`, `AutonomousMonitorDaemon`, `LLMResearchAgent`, `LLMGenerationMonitor`.
- Live `~/.config/opencode/opencode.json` + prompts (outside VCS).

## Success Criteria

- [ ] 14-phase flow runs via real per-phase delegation (no inline-code agents) in mock mode.
- [ ] `phase_runner` executes SDK stages; mechanical ops hand off via `LongOpSpec`.
- [ ] All 14 prompts carry mapped reasoning; parity tests pass.
- [ ] `guardian-orchestrator` registered, routed, gated; PRD:334 closed.