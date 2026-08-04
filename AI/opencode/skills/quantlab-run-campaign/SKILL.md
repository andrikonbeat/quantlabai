---
name: quantlab-run-campaign
description: "Run an orchestrated QuantLab campaign end-to-end: research → hypothesis → config → review → dispatch → monitor → retest → optimize. Trigger: a campaign objective, 'run a full campaign', or orchestrator routing of a campaign intent to quantlab-campaign."
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

Run the orchestrated campaign flow defined by the `orchestrated-campaign-flow`
spec (REQ-01..21). The scope ends at retest/optimize with recommendations —
there is NO deploy phase (D1) and NO optimize → re-dispatch feedback loop (D4).

## Campaign Loop

Execute the 8 phases in order. Every phase returns the Result Contract
envelope (`status`, `executive_summary`, `artifacts`, `next_recommended`,
`risks`):

1. **research** — load the DSL/ResearchConfig and campaign objective.
2. **hypothesis** — state the hypothesis and its confirm/reject criteria.
3. **config** — build the SQX config via `BuildConfig` and the blocks bridge.
4. **review** — `ConfigReviewStage` verdict (APPROVE / MODIFY / BLOCK).
5. **dispatch** — only after the `HUMAN_APPROVE_CONFIG` gate approves;
   never after a BLOCK or a non-approval gate decision.
6. **monitor** — `CampaignMonitor` + `LLMGenerationMonitor`; consume
   `strategy_counts` and stall signals from the exported `strategies.csv`.
7. **retest** — `RetesterStage` when a `retest` block is configured; the
   config-adjustment loop is bounded by `max_iterations`.
8. **optimize** — `OptimizerStage` when an `optimize` block is configured;
   present recommendations and STOP (no deploy, no re-dispatch).

A phase with `status=failed` halts the loop for a human decision.

## Gate Protocol (AD-4)

- Gates write `{gate_id}.pending.json` under `/tmp/sqx-gates/{campaign_id}/`.
- Present the choice envelope via the `question` tool; the human decision is
  written back as `{gate_id}.decision.json`.
- Headless fallback: read the pending file and accept the decision from
  stdin.
- Autonomous mode (D2): config-review and optimizer re-dispatch gates ALWAYS
  block for a human; MODIFY requires human confirmation before applying (D3);
  unanswered gates fail closed (HOLD) — never auto-approve.

## Data (D5)

`DataManager` is Dukascopy-only (FX M1/M5/H1). Orchestrated dispatch runs
`_ensure_data` as a hard pre-flight; `skip_data_check` bypasses it only when
explicitly requested. Crypto/CSV/yahoo raise `NotSupportedError`.

## Files

- Agent prompt: `AI/opencode/agents/campaign.md`
- Pipeline wiring: `sdk/quantlab/agents/research_director.py`
  (`build_pipeline(orchestrated=True)`)
- Stages: `sdk/quantlab/pipeline/stages/{config_review,dispatch,retester,optimizer}_stage.py`
- Gates: `sdk/quantlab/gates/callbacks.py`
- Data: `sdk/quantlab/data/{data_manager,symbol_registry}.py`
- Monitors: `sdk/quantlab/sqx/{campaign_monitor,llm_generation_monitor}.py`

## Exit Condition

Return the final Result Contract envelope with `next_recommended:
stop-after-optimize` and state explicitly that no deploy was performed.
