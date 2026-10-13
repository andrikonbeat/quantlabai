# ODD Feature: JForex Bridge Architecture Redesign

## Context
Current `JForexStrategyBridge` assumes a fictional `jforex` CLI binary with `deploy/start/stop` subcommands that **does not exist** in official Dukascopy distribution. `JForexLiveFeed` and `JForexBrokerAdapter` assume JForex Desktop auto-generates `equity.json`, `orders.json`, `health.txt` — it does not; strategies must be instrumented to write them.

## Decision
Build a **custom Java subprocess bridge** (`QuantLabBridge.java`) using official JForex SDK (API 2.13.99, DDS2 3.6.51) instead of adopting abandoned open source bridges (jforexgw4py: 2016, dukas-grpc: 2020).

## Architecture

```
Python (QuantLab SDK)
    │
    ├── JForexStrategyBridge (rewrite) ── subprocess.run(["java", "-cp", "bridge.jar", "QuantLabBridge", "deploy", ...])
    │                                          │
    │                                          ▼
    │                         ┌─────────────────────────────┐
    │                         │  QuantLabBridge.java          │
    │                         │  - main(String[] args)        │
    │                         │  - JSON stdin → JSON stdout   │
    │                         │  - Commands: compile, deploy, │
    │                         │    start, stop, status,       │
    │                         │    account                    │
    │                         │  - Uses IClient,              │
    │                         │    IRemoteStrategyManager     │
    │                         └──────────────┬────────────────┘
    │                                        │ JNLP
    │                                        ▼
    │                         ┌─────────────────────────────┐
    │                         │  Dukascopy Servers            │
    │                         └─────────────────────────────┘
    │
    ├── JForexLiveFeed (unchanged) ── reads ~/JForex4/state/equity.json, orders.json
    │
    └── JForexBrokerAdapter (unchanged) ── reads ~/JForex4/state/connection.json, health.txt, latency.txt, slippage.txt
```

## Acceptance Criteria
1. `QuantLabBridge.jar` builds with Maven, runs on Java 11+
2. Commands work: `compile`, `deploy`, `start`, `stop`, `status`, `account` (JSON in/out)
3. `JForexStrategyBridge` Python rewritten to call bridge subprocess
4. Strategy template Java writes required JSON state files for LiveFeed/BrokerAdapter
5. Installer auto-detects JForex 4 installation (like SQX)
6. All specs/runbooks updated to reflect real architecture
7. Integration tests pass with `SQX_FORCE_MOCK=1`

## Tasks

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 1 | Create ODD feature document and task breakdown | ✅ Done | This document |
| 2 | Design QuantLabBridge.java command protocol (JSON stdin/stdout) | 🔄 In Progress | Define commands, schemas, error handling |
| 3 | Implement QuantLabBridge.java with JForex SDK 3.6.51 / API 2.13.99 | ⏳ Pending | Maven project, fat-jar, IClient + IRemoteStrategyManager |
| 4 | Write Java unit tests for bridge commands | ⏳ Pending | Mock IClient/IRemoteStrategyManager, test JSON protocol |
| 5 | Rewrite sdk/quantlab/jforex/strategy_bridge.py to call bridge subprocess | ⏳ Pending | Replace fictional 'jforex' CLI |
| 6 | Create JForex strategy template that exports equity.json/orders.json/health.txt | ⏳ Pending | Template for LiveFeed/BrokerAdapter filesystem monitoring |
| 7 | Add JForex auto-detection to installer (config.go + wizard.go) | ⏳ Pending | ValidateJForexPath, autoDetectJForex like SQX |
| 8 | Update specs and runbooks with real architecture | ⏳ Pending | sdd/specs/jforex4-integration/, docs/runbooks/jforex-demo.md |
| 9 | Integration test: full deploy/start/stop cycle with mock | ⏳ Pending | SQX_FORCE_MOCK=1 pytest for bridge + strategy_bridge |

## Risks
- JForex SDK licensing: verify redistribution terms for fat-jar
- PIN handling for live accounts (demo = no PIN, live = PIN or IP whitelist)
- Reconexión automática: bridge is stateless subprocess, reconnection logic in Python layer
- Strategy template must be compiled by bridge before deploy

## Rollback
- Revert `strategy_bridge.py` to current (broken) version
- Delete `bridge/` directory
- Specs/runbooks revert to git HEAD

## Evidence
- Memory observation #267: decision record with bridge evaluation
- Web search results: jforexgw4py (2016), dukas-grpc (2020), SDK versions
- Current broken implementation: `sdk/quantlab/jforex/strategy_bridge.py` lines 45-67

## Commits
- TBD: `feat(jforex): add QuantLabBridge.java subprocess bridge`
- TBD: `feat(jforex): rewrite JForexStrategyBridge to use bridge`
- TBD: `feat(jforex): add strategy template with JSON state export`
- TBD: `feat(installer): add JForex auto-detection`
- TBD: `docs(jforex): update specs and runbooks for real architecture`