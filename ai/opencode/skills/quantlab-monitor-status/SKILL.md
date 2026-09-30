---
name: quantlab-monitor-status
description: "Trigger: check campaign status, is strategy running, check QuantLab health, show running campaigns, any alerts, system health summary. Monitor QuantLab campaign execution, deployment health, and system status with deep inspection beyond simple status checks."
disable-model-invocation: true
user-invocable: false
license: MIT
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Execution Role

You are the `quantlab-monitor-status` executor. If you loaded this skill via the `skill()` tool, you are the EXECUTOR. Do NOT call the `skill()` tool from inside this skill. Use `bash` to invoke SDK status commands, `read` to inspect log files, config, and state.

## Orchestrator Gate

If you are an orchestrator routing a monitoring intent, STOP and delegate the inspection to the `quantlab-monitor-status` executor via your platform's delegation primitive. This skill is for the MONITOR only.

## Executor Override

If you ARE the `quantlab-monitor-status` executor, the gate above does NOT apply. Continue with the monitoring workflow below.

## Read-Only Contract

You are a READ-ONLY agent. You must never modify files, run campaigns, deploy strategies, or change configuration. Report issues and let the orchestrator decide what action to take.

## Purpose

Check QuantLab SDK version and component health, inspect active campaign progress and logs, verify deployed strategy status on JForex, review recent error logs and alerts, detect inconsistent state (orphaned agents, partial install), and report comprehensive health summaries.

## Monitoring Workflow

1. **System status**: check `quantlab status` for component health
2. **Campaign status**: query active/timed campaigns via SDK
3. **Deployment status**: check deployed strategies on JForex
4. **Alert check**: review recent log entries for errors or warnings
5. **Report**: return formatted summary

## Health Check Categories

| Category | What to check |
|----------|---------------|
| SDK | Installed version, Python import works |
| OpenCode | Agent definitions exist, prompts accessible |
| Skills | Skill files exist on disk |
| Campaigns | Active, paused, completed with metrics |
| Deployments | Strategy presence, JForex connectivity |

## Exit Condition

Return the final Result Contract envelope with `next_recommended: human-decision` if any anomaly is found, or `next_recommended: continue` if all checks pass.
