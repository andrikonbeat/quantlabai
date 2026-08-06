---
name: quantlab-run-campaign
description: "Run an orchestrated QuantLab campaign end-to-end: research → hypothesis → config → review → dispatch → monitor → retest → optimize → portfolio → compile → deploy → demo → archive → live-ops. Trigger: a campaign objective, 'run a full campaign', or orchestrator routing of a campaign intent to quantlab-campaign."
disable-model-invocation: true
user-invocable: false
license: MIT
metadata:
  author: gentleman-programming
  version: "1.0"
---

> **ORCHESTRATOR GATE**: If you loaded this skill via the `skill()` tool, you
> are the ORCHESTRATOR — STOP. Do NOT execute these instructions inline.
> Delegate the campaign to the `quantlab-campaign` subagent via your
> platform's delegation primitive. This skill is for the EXECUTOR
> (`quantlab-campaign`) only.

## Executor Override

If you ARE the `quantlab-campaign` subagent (NOT the orchestrator), the gate
above does NOT apply. Continue with the campaign loop below.

## Purpose

Run the orchestrated campaign flow defined by the canonical 14-phase lifecycle
(REQ-37). The loop runs research → hypothesis → config → review → dispatch →
monitor → retest → optimize → portfolio → compile → deploy → demo → archive →
live-ops, in order, each phase gated by human confirmation. The campaign ends
at archive with a maintenance plan and statistics, with live-ops (Guardian
watching the demo account) as the terminal phase. There is NO optimize →
re-dispatch feedback loop (D4).

## Flow-Integrity Assert (REQ-37)

Before any phase, assert the flow against the canonical constant:

```python
from quantlab.campaign.flow import PHASES, FlowIntegrityError, assert_flow

try:
    assert_flow(PHASES)          # canonical constant — MUST pass
except FlowIntegrityError as exc:
    raise RuntimeError(f"flow-integrity abort: {exc}") from exc
```

Never remove, reorder, merge, duplicate, or auto-approve a phase. The 14
phases plus the Guardian live flow MUST remain, in order, each human-gated.

## Campaign Loop (14 phases)

Execute the 14 phases in order. Every phase returns the Result Contract
envelope (`status`, `executive_summary`, `artifacts`, `next_recommended`,
`risks`):

1. **research** — load the DSL/ResearchConfig and campaign objective.
2. **hypothesis** — state the hypothesis and its confirm/reject criteria.
3. **config** — build the SQX config via `BuildConfig` and the blocks bridge.
4. **review** — `ConfigReviewStage` verdict (APPROVE / MODIFY / BLOCK).
5. **dispatch** — only after the `HUMAN_APPROVE_CONFIG` gate approves; never
   after a BLOCK or a non-approval gate decision.
6. **monitor** — `CampaignMonitor` + `LLMGenerationMonitor`; consume
   `strategy_counts` and stall signals from the exported `strategies.csv`.
7. **retest** — `RetesterStage` when a `retest` block is configured; the
   config-adjustment loop is bounded by `max_iterations`.
8. **optimize** — `OptimizerStage` when an `optimize` block is configured;
   present recommendations and CONTINUE past optimize (no D1 halt); never
   re-dispatch on your own (D4).
9. **portfolio** — compose the campaign portfolio from the qualified
   strategies (`PortfolioComposer`).
10. **compile** — route the portfolio sources through the compiler pipeline
    (`QUANTLAB_JDK_HOME` javac, per-strategy) and package `.jfx` archives.
11. **deploy** — after `HUMAN_APPROVE_DEPLOY`, package a real deployable JAR
    via `DeploymentAgent` (dry-run default, zero network) for the demo phase.
12. **demo** — deploy to the Dukascopy demo account within the 14-business-day
    window (`DemoWindow`); renewal after expiry requires `HUMAN_APPROVE_DEMO`
    (fail-closed block).
13. **archive** — compose the maintenance/replacement plan, account
    statistics, and artifact bundle (`ArchivePhase`); finalize only on
    explicit `HUMAN_APPROVE_ARCHIVE` approval (REQ-38, denial → back to
    maintenance).
14. **live-ops** — wire the Guardian live flow over the demo account
    (`AutonomousMonitorDaemon` stream → MetaGuardian eval → feedback); the
    campaign terminates here with a maintenance plan and statistics.

A phase with `status=failed` halts the loop for a human decision.

## Gate Protocol (AD-4)

- Gates write `{gate_id}.pending.json` under `/tmp/sqx-gates/{campaign_id}/`.
- Present the choice envelope via the `question` tool; the human decision is
  written back as `{gate_id}.decision.json`.
- Headless fallback: read the pending file and accept the decision from
  stdin.
- Autonomous mode (D2): `HUMAN_APPROVE_CONFIG`, `HUMAN_APPROVE_DEPLOY`,
  `HUMAN_APPROVE_DEMO`, `HUMAN_APPROVE_ARCHIVE`, and the optimizer re-dispatch
  gate ALWAYS block for a human; MODIFY requires human confirmation before
  applying (D3); unanswered gates fail closed (HOLD) — never auto-approve.
- Campaign ids passed to the gate channel are restricted to `[A-Za-z0-9_-]`.

## Data (D5)

`DataManager` is Dukascopy-only (FX M1/M5/H1). Orchestrated dispatch runs
`_ensure_data` as a hard pre-flight; `skip_data_check` bypasses it only when
explicitly requested. Crypto/CSV/yahoo raise `NotSupportedError`.

## Files

- Agent prompt: `AI/opencode/agents/campaign.md`
- Flow constant: `sdk/quantlab/campaign/flow.py` (`PHASES`, `assert_flow`)
- Pipeline wiring: `sdk/quantlab/agents/research_director.py`
  (`build_pipeline(orchestrated=True)`)
- Stages: `sdk/quantlab/pipeline/stages/{config_review,dispatch,retester,optimizer}_stage.py`
- Gates: `sdk/quantlab/gates/callbacks.py`
- Data: `sdk/quantlab/data/{data_manager,symbol_registry}.py`
- Monitors: `sdk/quantlab/sqx/{campaign_monitor,llm_generation_monitor}.py`

## Exit Condition

Return the final Result Contract envelope with `next_recommended: live-ops` and
state explicitly that the lifecycle terminated at archive with a maintenance
plan and statistics.
