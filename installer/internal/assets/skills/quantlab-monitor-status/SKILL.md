# Skill: quantlab-monitor-status

## Purpose
Monitor QuantLab campaign execution, deployment health, and system status. Provides real-time status readouts and alerts.

## Triggers
- "status of campaign X"
- "is my strategy running?"
- "check QuantLab health"
- "show all running campaigns"
- "any alerts?"

## Workflow

1. **System status**: check `quantlab status` for component health
2. **Campaign status**: query active/timed campaigns via SDK
3. **Deployment status**: check deployed strategies on JForex
4. **Alert check**: review recent log entries for errors or warnings
5. **Report**: return formatted summary

## Readout Format

```
QuantLab Status
├── SDK: ✅ v1.2.3
├── OpenCode Agents: ✅ 4 deployed
├── Skills: ✅ 3 installed
├── Campaigns
│   ├── backtest-march-2026: ✅ RUNNING (72%)
│   └── live-eurusd: ⏸ PAUSED
└── Deployments
    ├── MomentumStrategy: ✅ DEPLOYED (JForex)
    └── MeanReversion: ❌ ERROR — connection refused
```

## Edge Cases

| Case | Behavior |
|------|----------|
| SDK not installed | Report "not installed" and suggest install |
| No campaigns running | Show empty state with "run campaign X" hint |
| JForex down | Clearly distinguish system vs broker outage |
| Old state artifacts | Offer `quantlab sync` to clean up |
