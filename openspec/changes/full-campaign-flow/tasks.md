# Tasks: Full Campaign Flow

Constraint: 14 phases in order, human-gated; never merge/remove (REQ-37).

## Review Workload Forecast

```text
Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High
```

~2,100 total lines; risk PR-1 High, PR-2/4/6 Med, PR-3/5 Med.

### Suggested Work Units

| Unit | Focused test command | Runtime harness | Rollback boundary |
|------|----------------------|-----------------|-------------------|
| 1 DSL+CFX (REQ-22..25) | `pytest tests/customproject/` | sqcli loadconfig 4-task | `QUANTLAB_CUSTOM_PROJECT=0` |
| 2 Substrate (REQ-26..28,42) | `SQX_FORCE_MOCK=1 pytest tests/substrate/` | mock parity + resume | flag off |
| 3 Compiler+.jfx (REQ-29..30,39) | `pytest tests/compiler/` | javac via JDK_HOME | `QUANTLAB_COMPILER=0` |
| 4 Demo+gates (REQ-31..32,38) | `pytest tests/demo_deploy/ tests/gates/` | dry-run, no network | dry_run on |
| 5 Archive+feedback (REQ-33..34,40..41) | `pytest tests/campaign_archive/ tests/guardian/` | archive + DEGRADING | additive records |
| 6 Push+orch (REQ-35..36,01M,37,43..44) | `pytest tests/gates/test_notifiers.py tests/pipeline/stages/` | DEFENSIVE + ack sim | stages flag + assert |

## PR-1: Custom-Project Generator (REQ-22..25)

- [x] 1.1 RED: order/GoToTask/databank tests (REQ-22)
- [x] 1.2 `customproject/models.py` — CustomProject, CustomProjectTask, GoToTask, DatabankSpec, Filters
- [x] 1.3 `catalog.py` (21) + `renderers.py` per-type sections, WF in CrossChecks, unknown→Error (REQ-25)
- [x] 1.4 `generator.py` + `writer._write_project_archive` — Databanks, per-task type, taskXMLFile (REQ-23)
- [x] 1.5 RED: `validator.py` golden + `sqcli -h`; deviation→ValidationError, no dispatch (REQ-24)
- [x] 1.6 E2E: loadconfig accepts 4-task archive; single-task byte-identity (REQ-23)

## PR-2: Execution Substrate (REQ-26..28, 42)

- [x] 2.1 RED: mock parity + resume tests (REQ-28, REQ-26) — `tests/substrate/`
- [x] 2.2 `substrate/executor.py` + `lifecycle.py` — state machine, PhaseResult (REQ-26)
- [x] 2.3 `poller.py`, `events.py` (CampaignMonitor, REQ-42), `exporter.py`
- [x] 2.4 RED: sqcli selectors — relative, missing, `SQCLI_PATH`, mock (fail-closed)
- [x] 2.5 retest→optimize in one load, gate hold (REQ-27); legacy parity (REQ-28)

## PR-3: Compiler Pipeline (REQ-29..30, 39)

- [x] 3.1 RED: missing JDK→CompilerConfigError, no partial .jfx; non-exec javac (REQ-29)
- [x] 3.2 `compiler/compiler.py` javac compile + `jfx.py` packaging (REQ-29)
- [x] 3.3 `fixloop.py` bounded fix, per-iteration log, bound→CompileError + history (REQ-30)
- [x] 3.4 `jforex_deploy.py` .jfx routing; RED: compile failure blocks deploy (REQ-39)

## PR-4: Demo Deploy + Gates (REQ-31..32, 38)

- [x] 4.1 DEMO/ARCHIVE gates into GATE_POLICIES+GATE_IDS, HOLD; RED: no auto-approve, question-tool (REQ-38)
- [x] 4.2 `demo_deploy.py` 14-day window, expiry block + reminder (REQ-31)
- [x] 4.3 `deployment_agent.py` real JAR + JCloud; dry-run mock, no network (REQ-32)

## PR-5: Archive + Feedback (REQ-33..34, 40..41)

- [ ] 5.1 `feedback.py` record()→FeedbackRecord at archive; RED: gates never bypassed (REQ-34)
- [ ] 5.2 `stream_live()` feed; RED: STREAM_LOST hold, no transition (REQ-41, REQ-40)
- [ ] 5.3 MetaGuardian live eval — drawdown>10%→DEFENSIVE + feedback (REQ-40)
- [ ] 5.4 `campaign_archive.py` plan/stats/bundle; DEGRADING→replacement, ARCHIVE gate (REQ-33)

## PR-6: Mobile + Orchestration (REQ-35..36, 01M, 37, 43..44)

- [ ] 6.1 MobilePushNotifier + severity routing; RED: push fail logged, others deliver (REQ-35)
- [ ] 6.2 24-7 daemon escalation on transitions + expiry, ack (REQ-36)
- [ ] 6.3 `campaign.md` PHASES + flow assert; RED: dropped phase aborts (REQ-37)
- [ ] 6.4 stages portfolio/compile/deploy/demo/archive; chained retest/optimize (REQ-43..44)
