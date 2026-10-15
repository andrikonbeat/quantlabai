# QuantLab AI — Project State (shim)

> **Canonical state lives in [`../sdd/PROJECT_STATE.md`](../sdd/PROJECT_STATE.md).**
> This file is a thin compatibility shim kept because
> `tests/test_campaign_docs.py` asserts the campaign contract here. Do not
> extend it — record new state, changes, and migrations in
> `sdd/PROJECT_STATE.md`.

## Live status

```bash
git log --oneline -20              # what actually landed, and when
git status                         # is the tree clean
git branch --show-current          # which branch you are on
ls ../sdd/changes/                 # active changes
```

| Question | Authoritative source |
|----------|---------------------|
| What is implemented? | `git log`, plus `sdd/changes/archive/YYYY-MM-DD-<slug>/` |
| Is the suite green? | `gh run list` for CI; `SQX_FORCE_MOCK=1 python3 -m pytest -q` locally |
| Which changes are in flight? | `ls sdd/changes/` (active) vs `sdd/changes/archive/` |
| What is the code contract? | `sdd/specs/`, asserted by `tests/` |
| Full unified record? | [`sdd/PROJECT_STATE.md`](../sdd/PROJECT_STATE.md) |

## Campaign flow

The campaign is LLM-driven and runs **14 phases** in canonical order:

```
research → hypothesis → config → review → dispatch → monitor → retest
        → optimize → portfolio → compile → deploy → demo → archive → live-ops
```

Dispatch runs through the `quantlab-campaign` agent. The
`orchestrated-campaign-flow` change that introduced this shape is archived at
`sdd/changes/archive/2026-08-06-full-campaign-flow/`.

Human gates are **fail-closed** (REQ-11) — no auto-approval, and an unanswered
gate stops the run. The gates that always block a dispatch include
`HUMAN_APPROVE_CONFIG`, and the deploy/demo/archive boundaries name
`HUMAN_APPROVE_DEPLOY`, `HUMAN_APPROVE_DEMO`, and `HUMAN_APPROVE_ARCHIVE`.

Full unified record, migrations, debt, and next steps:
[`sdd/PROJECT_STATE.md`](../sdd/PROJECT_STATE.md). New-machine procedure:
[HANDOFF.md](HANDOFF.md).
