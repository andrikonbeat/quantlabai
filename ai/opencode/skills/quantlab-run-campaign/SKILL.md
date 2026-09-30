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

## Long-Running Execution Policy

**Definition.** A **long-running operation** is anything that may exceed ~10
minutes or that starts the real SQX daemon: real dispatch, strategy build,
full backtest, prolonged monitor, compile with the real JDK, and real deploy.
Unit tests, health checks, and bounded CLI commands are NOT long-running. Real
campaign runs can take 20-35 minutes and boot the daemon SQX (JVM ~1.7GB RAM,
startup 90-105s over the 243 legacy projects).

**Why it exists.** The runtime cancels subagents that wait on long-running
operations; long execution belongs to the orchestrator's shell, with log
polling and monitoring.

**Orchestrator rule.** On a campaign intent, delegate the REASONING of the
phases to the `quantlab-campaign` subagent via the `task` tool. When that
subagent returns a long-running operation (a script or execution plan), NEVER
wait for it inside another `task` call and NEVER delegate the wait to a
subagent. Execute it DIRECTLY in your own shell (bash) in the background:
`nohup` with output redirected to a log file and `flush=True`. Poll the log,
report progress to the user phase by phase, and kill residual processes when
the run finishes. The subagent NEVER waits for the long run.

**Executor rule.** You MAY prepare the config, review, write the
driver/execution script, and run bounded operations with an explicit timeout.
When a phase requires a long-running operation (e.g. waiting on real daemon
generation), prepare the execution script (e.g. under `/tmp/opencode/`), return
control to the orchestrator with the script and exact instructions (command,
log path, what to expect), and do NOT wait for the full run inside your
subagent session. The script MUST include a generous timeout
(`QUANTLAB_SQCLI_TIMEOUT >= 240`), process cleanup (`pkill` of everything you
launched), and a per-phase report format.

## Purpose

Delegate execution of the orchestrated 14-phase campaign lifecycle to the
`quantlab-campaign` subagent. The canonical contract lives in
`ai/opencode/agents/campaign.md`; this skill is the lightweight LLM-first
entry point that enforces the orchestrator/executor gate and long-running
execution policy. Do NOT inline the phase loop, gate protocol, or flow-integrity
logic here — they are canonical only in `campaign.md`.

## Canonical Contract Pointer

The authoritative campaign loop, gate protocol, flow-integrity assertions,
data contracts, and exit conditions are defined in
`ai/opencode/agents/campaign.md`. Load and obey that contract. This skill
exists only to route the orchestrator correctly and to enforce the long-running
execution policy above.

## Files

- Canonical contract: `ai/opencode/agents/campaign.md`
- Flow constant: `sdk/quantlab/campaign/flow.py` (`PHASES`, `assert_flow`)
- Pipeline wiring: `sdk/quantlab/agents/research_director.py`
  (`build_pipeline(orchestrated=True)`)
- Stages: `sdk/quantlab/pipeline/stages/{config_review,dispatch,retester,optimizer}_stage.py`
- Gates: `sdk/quantlab/gates/callbacks.py`
- Data: `sdk/quantlab/data/{data_manager,symbol_registry}.py`
- Monitors: `sdk/quantlab/sqx/{campaign_monitor,llm_generation_monitor}.py`
