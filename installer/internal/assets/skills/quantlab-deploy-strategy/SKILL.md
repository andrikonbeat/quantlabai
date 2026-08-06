# Skill: quantlab-deploy-strategy

## Purpose
Deploy trading strategies to the JForex DAS platform. Manages compilation, parameter binding, and deployment lifecycle.

## Triggers
- "deploy strategy X"
- "publish strategy to JForex"
- "update strategy parameters"

## Workflow

1. **Inspect strategy**: validate `.java` / `.class` strategy file exists at configured path
2. **Configure**: accept optional override parameters (lot size, stop loss, take profit)
3. **Validate**: compile-check the strategy file, verify JForex connection
4. **Delegate**: invoke `quantlab-deploy` via task tool with deployment config
5. **Verify**: confirm strategy appears in JForex dashboard
6. **Report**: return deployment URL and status

## Configuration

Deployment parameters from `~/.quantlab/config.yaml`:
- `sqx.cli_path` — SQX CLI binary for compilation
- `jforex.host:port` — DAS connection
- Default lot size, risk parameters

## Edge Cases

| Case | Behavior |
|------|----------|
| Strategy file not found | List files in configured strategy dir |
| SQX CLI missing | Suggest `quantlab configure` to fix sqx path |
| JForex auth failure | Return clear auth error with fix instructions |
| Deploy to running instance | Warn about disruption and ask confirmation |
