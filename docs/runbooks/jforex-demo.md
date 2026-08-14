# JForex4 Demo Automation Runbook

Short operator guide for the JForex4 integration pipeline (change `jforex4-integration`).
Goal: get from an SQX-generated strategy to a monitored JForex4 deployment with LLM
indicator analysis, with the least human touch.

## 1. Prerequisites

- QuantLab SDK installed (`pip install -e ./sdk`)
- StrategyQuant X with a built portfolio (outputs `.jfx` via SQX export)
- JForex4 desktop client installed and running
- JForex4 local state directory readable by the QuantLab process:
  - `equity.json` and `orders.json` written by the live strategy
  - `history/{SQX_NAME}.json` written by the indicator/history export path

## 2. Pipeline flow

```
compile (SQX .jfx)  →  jforex_deploy (JForexStrategyBridge)  →  execution_monitor (JForexLiveFeed)  →  live evaluation
```

Stages and artifacts:

| Stage | Reads | Writes | Source |
|-------|-------|--------|--------|
| `CompileStage` | `portfolio_result` | `compiled_strategies` | SQX `.jfx` |
| `JForexDeployStage` | `compiled_strategies` | `deployment_result` | `JForexStrategyBridge` |
| `ExecutionMonitorStage` | config | `monitor_result` | `jforex_progress_fn(feed)` |
| `IndicatorExportStage` | `compiled_strategies` | `indicator_export_paths` | `IndicatorExporter.java` in `.jfx` |
| `LLMTechnicalAgent` | export JSON | summary | `~/JForex4/exports/quantlab-indicators-<strategy>.json` |

## 3. Demo automation (recommended path)

For demos, run **dry-run / simulated** mode end to end:

```bash
# 1. Compile the portfolio strategy to .jfx
python -m quantlab.cli.main pipeline run \
  --config demo.yaml --stage compile

# 2. Deploy to JForex4 (bridge injectable; use simulated bridge in demos)
python -m quantlab.cli.main pipeline run \
  --config demo.yaml --stage jforex_deploy

# 3. Monitor via JForexLiveFeed progress source
python -m quantlab.cli.main pipeline run \
  --config demo.yaml --stage execution_monitor --monitor-progress-source jforex

# 4. Export indicators and ask the LLM technical agent to summarize them
python -m quantlab.cli.main pipeline run \
  --config demo.yaml --stage indicator_export
```

Configure `demo.yaml` with:

```yaml
broker_profile: jforex
jforex_state_dir: ~/JForex4/state
monitor_phase: live
monitor_progress_source: jforex
```

## 4. Live automation (connect once, manage the rest)

JForex4 does not allow fully unattended live login (captcha/PIN). The supported model:

1. **Human connects once** in the JForex4 desktop client.
2. QuantLab handles **everything else** while the session is alive:
   - deploys `.jfx` (bridge)
   - polls equity/orders from local state (live feed)
   - streams indicators to the LLM technical agent
3. On disconnect, the broker adapter reports reduced health (`get_health_score()` < 1.0)
   and the execution monitor fails closed to `HOLD` for human review.

## 5. Fail-closed behaviour

| Failure | Result |
|---------|--------|
| JForex4 not running / state dir missing | adapter health 0.0, live feed empty, `(False, None)` progress → monitor HOLD |
| Deploy bridge error | `deployment_result[sid].status = FAILED`; pipeline continues |
| Indicator export missing/corrupt | `LLMTechnicalAgent` returns empty summary (no crash) |
| SQX build compile error | `CompileStage` halts (no partial `.jfx`) |

## 6. Verification commands

```bash
# Focused scope
python3 -m pytest tests/jforex/ tests/pipeline/test_jforex_pipeline_e2e.py -q

# Full change scope
python3 -m pytest tests/jforex/ tests/data/ tests/broker/ tests/test_guardian/ -q
```