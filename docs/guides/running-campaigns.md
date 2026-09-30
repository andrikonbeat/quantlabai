# Running Multi-Agent Campaigns

How to execute the full 14-phase research campaign with the QuantLab CLI: what the
command is, how human gates block it, and how to read the exit status.

> **Scope**: this runbook covers `quantlab campaign run-flow`, the orchestrated
> end-to-end flow. For the JForex4 demo/live deployment path see
> [JForex4 Demo Automation Runbook](../runbooks/jforex-demo.md).

## Quick path

1. Write a `ResearchConfig` (YAML or JSON), or skip it and pass `--campaign`,
   `--market`, `--timeframe` instead.
2. Run `quantlab campaign run-flow --config <file>`.
3. Answer each gate. The run **stops at the first gate you do not approve**.
4. Check the exit code: `0` means the whole flow completed; `1` means it did not.

## The 14 phases

The lifecycle is canonical and ordered. Simplification applies only to
code and infrastructure — a phase is never removed, reordered, merged, or
auto-approved.

| # | Phase | # | Phase | # | Phase | # | Phase |
|---|-------|---|-------|---|-------|---|-------|
| 1 | `research` | 5 | `dispatch` | 9  | `portfolio` | 13 | `archive` |
| 2 | `hypothesis` | 6 | `monitor` | 10 | `compile` | 14 | `live-ops` |
| 3 | `config` | 7 | `retest` | 11 | `deploy` | | |
| 4 | `review` | 8 | `optimize` | 12 | `demo` | | |

Each phase maps onto a concrete pipeline stage. The `monitor` phase is served by
`execution_monitor` in the orchestrated pipeline and by the legacy `monitor`
stage; `research` is likewise satisfied by `research` or `research_llm`.

`retest` and `optimize` are conditional: they are only required when the
corresponding DSL block is present in your config. Every other phase must be
present.

## Flow integrity is checked before anything runs

Before the first stage executes, the built pipeline is checked against the
segment structure (presence, post-deploy boundary, loop-tail order). If the
check fails the run aborts with a `flow-integrity error` and exit code `1`.
Nothing is executed against a broken flow.

## Human gates block the flow

Gates are never auto-approved. At each `HUMAN_*` gate the run writes a pending
envelope, waits for a decision, and continues only if the decision is an
approving action. Anything else — `REJECT`, `HOLD`, `ABORT`, a missing
decision, or a timeout — stops the run with a non-zero exit.

Approving actions are `approve`, `approved`, and `fallback` (case-insensitive).

The gates registered in code are:

| Gate | Fallback when unanswered |
|------|-------------------------|
| `HUMAN_REVIEW_OBJECTIVES` | ESCALATE |
| `HUMAN_APPROVE_CONFIG` | HOLD |
| `HUMAN_APPROVE_ITERATION` | ABORT |
| `HUMAN_APPROVE_PORTFOLIO` | ESCALATE |
| `HUMAN_APPROVE_DEPLOY` | HOLD |
| `HUMAN_APPROVE_DEMO` | HOLD |
| `HUMAN_APPROVE_ARCHIVE` | HOLD |
| `HUMAN_REVIEW_PERFORMANCE` | CONTINUE |

## Two ways to answer a gate

### Interactive (default)

The run writes a pending envelope and polls for a decision:

```
{gate_event_dir}/{campaign_id}/{gate_id}.pending.json    → what is being asked
{gate_event_dir}/{campaign_id}/{gate_id}.decision.json   → your answer
```

`--gate-event-dir` sets the base directory (default `/tmp/sqx-gates`). Answer by
writing the `decision.json` file:

```json
{ "action": "approve", "reason": "reviewed", "decided_by": "you" }
```

`--gate-timeout <seconds>` bounds the wait. Without it the run waits
indefinitely — a pending gate will not time out on its own.

### Headless

`--gate-decisions-file <file>` supplies decisions up front. The file maps gate
id to a decision envelope, is re-read on every gate so you can add decisions
while the flow runs, and is treated as read-only input:

```json
{
  "HUMAN_APPROVE_CONFIG":    { "action": "approve", "reason": "config ok", "decided_by": "ci" },
  "HUMAN_APPROVE_DEPLOY":    { "action": "hold",     "reason": "wait for review", "decided_by": "ci" }
}
```

In headless mode the system never prompts. A gate with no entry in the file
fails closed and stops the flow.

## Command reference

| Flag | Default | Purpose |
|------|---------|---------|
| `--config <file>` | — | `ResearchConfig` YAML or JSON. Takes precedence over the flags below. |
| `--campaign <name>` | `full-flow` | Campaign name, used when `--config` is absent. |
| `--market <symbol>` | `EURUSD` | Market symbol, used when `--config` is absent. |
| `--timeframe <tf>` | `H1` | Timeframe, used when `--config` is absent. |
| `--knowledge-root <path>` | `knowledge` | Knowledge Lake root. |
| `--gate-event-dir <path>` | `/tmp/sqx-gates` | Base directory for the decision-file channel. |
| `--gate-decisions-file <file>` | — | Headless decisions file. Disables interactive prompting. |
| `--gate-timeout <seconds>` | wait indefinitely | Wait bound before failing closed. |
| `--json` | off | Emit a machine-readable result instead of human-readable output. |

## Exit status

| Code | Meaning |
|------|---------|
| `0` | Every stage ran and every gate approved. |
| `1` | Invalid config, pipeline build failure, flow-integrity violation, a stage raised, a gate was not approved, or a dispatch was blocked. |

With `--json`, a failure reports the phases that did complete and the stage that
stopped the run.

A blocked dispatch surfaces as a visible failure — never a false success.

## Checklist

- [ ] `--config` validates (or the fallback flags are set deliberately).
- [ ] `retest` / `optimize` are present in your config if you need them.
- [ ] A human is available to answer gates, or a decisions file is staged.
- [ ] You checked the exit code, not just the log output.

## Next step

- [Pipeline YAML Reference](../configuration/pipeline-yaml.md) — stage-by-stage YAML specification.
- [Pipeline Configuration Reference](../configuration/pipeline-config.md) — configuration keys and value ranges.
- [Human Gates Guide](../multi-agent/gates.md) — gate behaviour in detail.
- [Agent Reference](../multi-agent/agents.md) — what each agent does.
