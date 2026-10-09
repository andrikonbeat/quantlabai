# Proposal: Full Campaign Flow — Complete QuantLab Lifecycle

## Intent

Run a complete strategy campaign from idea to a live demo on a **100 USD Dukascopy account**, ending in a maintained, archived campaign with statistics. Today the flow stops at optimize (D1, no deploy). User goal: one orchestrated lifecycle — SQX backtest → robust portfolio → compiled JForex strategy → demo deploy → archive — with a live Guardian watching the demo account.

## Problem Statement

Three overlapping execution paths (CommandDispatcher, `cli_wrapper._dispatch_real`, CampaignOrchestrator); single-task CFX only; `jforex_deploy` exports `.java` with no compile/`.jfx`; DeploymentAgent JAR is a placeholder; archive, Guardian→generation feedback, and mobile/24-7 ops do not exist. **Constraint**: all 14 flow phases + Guardian flow MUST remain, in order, each gated by human confirmation; simplification applies to code/infra only, never flow steps.

## Scope

### In Scope (phased slices)
1. CustomProject DSL + multi-task `.cfx` generator (21-task catalog, `taskXMLFile` routing; validated against SQX 144/2953 sample projects)
2. Unified execution/monitoring substrate (daemon + lifecycle + polling + event detection + checkpoint + export, parameterized per phase)
3. Compiler pipeline (`.java` → javac with external JDK → `.jfx`; error-fix loop)
4. Demo deploy (14 business-day window; JCloud config; real DeploymentAgent packaging)
5. Archive/maintenance (replacement plan, account statistics)
6. Guardian→generation feedback loop + mobile notifications/24-7 ops surface

### Out of Scope
- Any change to flow phase order/count or removal of human confirmation
- JForex engine backtest validation (Dukascopy runs on MetaTrader4 engine)
- Demo renewal automation beyond semi-manual 14-day reminder
- Data sources beyond Dukascopy

## Capabilities

### New Capabilities
- `custom-project-generator`: DSL CustomProject + multi-task `.cfx` archives
- `execution-substrate`: unified daemon/lifecycle/polling/checkpoint/export per phase
- `compiler-pipeline`: `.java`→javac→`.jfx` with error-fix loop
- `demo-deploy`: 14-day window handling, JCloud config, DeploymentAgent packaging
- `campaign-archive`: maintenance/replacement plan + account statistics
- `guardian-feedback`: live degradation/drawdown/regime/cost data into generation flow
- `mobile-notifications`: push/ops surface for 24-7 monitoring

### Modified Capabilities
- `campaign-orchestration`: extend 8-phase loop to full 14-phase lifecycle (portfolio→compiler→demo→archive)
- `jforex-deploy`: add compile/`.jfx` stages beyond `.java` export
- `meta-guardian` / `autonomous-monitor`: live account feed + feedback loop wiring
- `human-gates`: add `HUMAN_APPROVE_DEPLOY` / `HUMAN_APPROVE_DEMO` / `HUMAN_APPROVE_ARCHIVE`
- `campaign-monitor`, `retester-automation`, `optimizer-automation`: run on unified substrate; retest/optimize chained in one project load

## Approach

Extend the orchestrated harness in place (same flag-gated pattern, Result Contract envelopes, fail-closed decision-file gates) over a unified execution substrate; custom-project generator ships first (unlocks retest/optimize chaining). Slices 1→6 land as separate specs + chained PRs.

## Key Design Decisions

- Slices = separate specs/chained PRs (400-line review budget, auto-chain stacked-to-main)
- Custom-project CFX first — largest unknown (SQX schema acceptance), unblocks everything
- External JDK required (`j64/` is JRE, no javac)
- New human gates fail-closed, mirroring `HUMAN_APPROVE_CONFIG`
- `SQX_FORCE_MOCK` retained for the 2790-test suite; real-path validated against archive sample projects

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/cfx/`, `translate/` | Modified | multi-task generator |
| `sdk/quantlab/sqx/`, `phase4/` | Modified | unify 3 dispatch paths |
| `sdk/quantlab/phase4/jforex_deploy.py` | Modified | add compile/.jfx |
| `sdk/quantlab/agents/deployment_agent.py` | Modified | real packaging |
| `sdk/quantlab/gates/models.py` | Modified | 3 new human gates |
| `sdk/quantlab/guardian/` | Modified | live feed + feedback |
| `AI/opencode/agents/campaign.md` | Modified | extended lifecycle |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| CFX writer dialect rejected by real SQX | Med | validate against sample projects first |
| Substrate refactor breaks 2790-test suite | Med | old paths flag-gated until parity |
| Demo renewal slips past 14-day window | Med | semi-manual reminder + monitoring |
| Mock-vs-real divergence (SQX_FORCE_MOCK) | Med | golden validation on real path |
| Chain exceeds 400-line budget | High | forecast chained PRs at sdd-tasks |

## Rollback Plan

- Each slice behind its own feature flag (existing pattern); revert = disable flag
- Substrate keeps legacy dispatch paths behind flag until parity proven
- Archive sample projects as validation goldens before generator changes

## Dependencies

- `assets/SQX_144_2953_linux_20260601/` (sqcli, sample projects)
- External JDK (Java 25-compatible) for javac
- JCloud/Dukascopy demo account config

## Success Criteria

- [ ] Multi-task `.cfx` accepted by real SQX (144/2953 sample projects as goldens)
- [ ] All 14 phases run end-to-end with human confirmation at each step
- [ ] Compiler produces `.jfx` from exported `.java`; error-fix loop self-corrects
- [ ] Demo deploy completes inside the 14 business-day window
- [ ] Archive produces maintenance/replacement plan + account statistics
- [ ] Guardian live degradation/drawdown data feeds back into generation flow

## Why SDD

Largest change in the repo: a 21-task catalog + a 14-phase lifecycle contract with business rules (order, human gates) need spec-level Given/When/Then and delta specs. Six slices need task/verify/PR discipline and fail-closed behavior verified before each chained merge.
