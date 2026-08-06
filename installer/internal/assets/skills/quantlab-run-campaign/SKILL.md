# Skill: quantlab-run-campaign

## Purpose
Execute and monitor QuantLab trading campaigns. Routes requests to `quantlab-campaign` sub-agent.

## Triggers
- "run campaign X"
- "start backtesting Y"
- "execute strategy Z on symbol EUR/USD"

## Workflow

1. **Parse request**: extract campaign name, strategy, symbol, timeframe, and parameters
2. **Validate**: check SDK is installed (`quantlab status` → SDK component)
3. **Delegate**: invoke `quantlab-campaign` via task tool with structured campaign config
4. **Monitor**: report progress callbacks, stream log output
5. **Report**: return summary with status URL and key metrics

## Configuration

Campaign parameters are read from `~/.quantlab/config.yaml`:
- `jforex.host` / `jforex.port` — DAS connection
- `jforex.username` — trading account
- `api_keys.openai` / `api_keys.anthropic` — LLM providers for signal generation

## Edge Cases

| Case | Behavior |
|------|----------|
| SDK not installed | Offer to run `quantlab install` |
| JForex disconnected | Warn and suggest `quantlab configure` |
| Invalid strategy path | Show validation error with path hint |
| Campaign already running | Report status and offer to attach |
