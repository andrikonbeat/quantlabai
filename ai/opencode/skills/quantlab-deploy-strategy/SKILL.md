---
name: quantlab-deploy-strategy
description: "Trigger: deploy strategy, publish strategy to JForex, update strategy parameters, deployment failure. Deploy QuantLab trading strategies to JForex DAS with fail-closed edge cases and human confirmation on running instances."
disable-model-invocation: true
user-invocable: false
license: MIT
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Execution Role

You are the `quantlab-deploy-strategy` executor. If you loaded this skill via the `skill()` tool, you are the EXECUTOR. Do NOT call the `skill()` tool from inside this skill. Use `bash` to invoke SQX CLI and JForex API calls, `read` to inspect strategy files, and `write` to export deployment reports.

## Orchestrator Gate

If you are an orchestrator routing a deployment intent, STOP and delegate the deployment to the `quantlab-deploy-strategy` executor via your platform's delegation primitive. This skill is for the DEPLOYER only.

## Executor Override

If you ARE the `quantlab-deploy-strategy` executor, the gate above does NOT apply. Continue with the deployment workflow below.

## Purpose

Deploy trading strategies to the JForex DAS platform. Validates strategy file existence and format, compiles strategy files using SQX CLI when applicable, deploys strategies to JForex DAS, updates strategy parameters on deployed instances, and verifies deployment success via JForex status API.

## Deployment Workflow

1. **Validate strategy file**: confirm `.java` / `.class` strategy file exists at configured path
2. **Compile**: compile-check the strategy file via SQX CLI when applicable
3. **Configure**: accept optional override parameters (lot size, stop loss, take profit)
4. **Deploy**: invoke JForex DAS deployment with the strategy config
5. **Verify**: confirm strategy appears in JForex dashboard
6. **Report**: return deployment URL and status

## Deployment Config Structure

```json
{
  "deploy": {
    "strategy_file": "/path/to/MomentumStrategy.java",
    "name": "MomentumStrategy",
    "parameters": {
      "lot_size": 0.1,
      "stop_loss": 20,
      "take_profit": 40
    }
  }
}
```

## Fail-Closed Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| Missing strategy file | Report the missing path and suggest `quantlab configure` to fix the strategy directory |
| JForex auth failure | Report the auth error with explicit host:port details and stop; never retry blindly |
| Deploy to running instance | Warn about disruption, present the complete envelope, and ask for explicit confirmation before replacing |
| SQX CLI missing | Suggest `quantlab configure` to fix the sqx path |

## Exit Condition

Return the final Result Contract envelope with `next_recommended: demo` on success, or `next_recommended: human-decision` with `risks` containing the exact failure reason on blocked/failed deployment.
