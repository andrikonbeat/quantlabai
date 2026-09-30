# Review Lifecycle for SDK Changes

This guide describes the gentle-ai native review lifecycle for `sdk/quantlab/` changes. It covers the 4R consent envelope, the stop-reason continuation table, and the `repair --preflight` repair path. RDD mode enable/repair is user-owned and out of scope for this change.

## Quick path

1. Start every review with the status route command.
2. If a `stop` transition returns, consult the stop-reason table for the exact continuation.
3. If repair is required, run `gentle-ai review repair --preflight` to validate the candidate before editing.
4. Never alter RDD mode settings yourself; that decision remains with the user.

## Route

Begin every generated negotiated v2.1 lifecycle route with the following command. Read only the returned `next_transition`; never route from status prose or lifecycle state.

```bash
gentle-ai review status \
  --cwd <repo> \
  --contract gentle-ai.review-integration/v2 \
  --agent opencode \
  --next-transition
```

- For `execute`, invoke its exact operation and ordered argument tokens unchanged.
- For `collect`, satisfy only its named inputs with their exact capture operations and arguments, then query STATUS again.
- For `stop`, run no lifecycle operation. Surface both its `reason_code` and that code's continuation from the table below.

## 4R Consent Envelope

The review lifecycle tracks four stages. Consent is captured through a lossless blocking-prompt model:

| Stage | Purpose |
|-------|---------|
| **Request** | Present the candidate for review and capture consent. |
| **Review** | Execute lenses and capture reviewer artifacts. |
| **Repair** | Apply bounded corrections if reviewer findings require them. |
| **Release** | Finalize and deliver the approved candidate. |

### Consent envelope handling

- Present the complete semantic envelope once in the active conversation language.
- Preserve the original groups/order, selection mode, exact allowed-answer domain, and answer tokens.
- Project `value` as explicit benefits and every `effect` as explicit consequences; labels alone are forbidden.
- Never translate or alter machine answer tokens (`granted`, `declined`), commands, target IDs, or invocations.
- Run exactly the one named follow-up invocation for the human's answer. Granted and declined are both scoped to that exact candidate and do not suppress the question for a later medium/high candidate.

## Stop-Reason Continuation Table

When `review status` returns `stop`, use the `reason_code` to select the exact continuation. Never invent a continuation this table does not list.

| Reason code | Continuation |
| --- | --- |
| `captured_artifacts_unverifiable` | Terminal — A captured reviewer artifact failed local verification. Ask a maintainer to inspect the review authority store, or run `gentle-ai review mode disable --scope clone --cwd <repo>` to deliver under ordinary policy instead. |
| `captured_result_selection_unavailable` | Terminal — internal invariant violation with no caller-side retry. File a defect with the lineage id, or run `gentle-ai review mode disable --scope clone --cwd <repo>` to deliver under ordinary policy instead. |
| `captured_verification_evidence_invalid` | Terminal — the captured verification record or its raw payload failed integrity checks. Ask a maintainer to inspect it, or run `gentle-ai review mode disable --scope clone --cwd <repo>` to deliver under ordinary policy instead. |
| `corrected_candidate_unavailable` | If the review found real defects: change the candidate, then re-run the route command (or `gentle-ai review finalize --lineage <id>`). If the reviewers had the wrong input: a maintainer reopens their lenses with `gentle-ai review reopen-results --prepare --cwd <repo> --lineage <id> --expected-revision <revision> --target <target> --reason <reason> --actor <actor> --quarantine-lens <lens>` (repeat per lens) and applies the emitted authorization. |
| `empty_base_diff_bootstrap_required` | Terminal — the selected committed base has no changes to review. If this follows the authorized empty-root first-publication bootstrap, a maintainer inserts an empty root below the content commit, then runs the route command with `--base-ref <empty-root> --committed-only`. Do not re-submit the same base or invent a START. |
| `lens_context_budget_exceeded` | Terminal — complete immutable reviewer evidence exceeds the native budget and is never truncated. Reduce the candidate scope or target identity, then run `gentle-ai review start` for the new candidate; or run `gentle-ai review mode disable --scope clone --cwd <repo>` to deliver under ordinary policy. Do not change the runtime, provider, or toolchain. |
| `correction_repository_verification_failed` | Change the correction candidate within the same open budget, then re-run the route command. |
| `corrupted_or_unverifiable_authority` | Terminal — `gentle-ai review repair --preflight --cwd <repo>` classified this authority as unrecoverable. Ask a maintainer to inspect it, or run `gentle-ai review mode disable --scope clone --cwd <repo>` to deliver under ordinary policy instead. |
| `final_verification_retry_unavailable` | Terminal — internal invariant violation with no caller-side retry. File a defect with the lineage id, or run `gentle-ai review mode disable --scope clone --cwd <repo>` to deliver under ordinary policy instead. |
| `manual_intervention_required` | Terminal — authority state this protocol does not recognize. Ask a maintainer to review the lineage, or run `gentle-ai review mode disable --scope clone --cwd <repo>` to deliver under ordinary policy instead. |
| `missing_authority_binding` | Terminal — internal invariant violation with no caller-side retry. File a defect with the lineage id, or run `gentle-ai review mode disable --scope clone --cwd <repo>` to deliver under ordinary policy instead. |
| `native_stop_required` | Terminal — escalated lineage not yet eligible for automated action. Ask a maintainer to review it, or run `gentle-ai review mode disable --scope clone --cwd <repo>` to deliver under ordinary policy instead. |
| `original_finalize_request_required` | Re-run `gentle-ai review finalize --lineage <id>` with the exact original content-bound payload. |
| `recovery_scope_unchanged` | Change the candidate's target identity, then retry the same `review.recover` selector, or run `gentle-ai review mode disable --scope clone --cwd <repo>` to deliver under ordinary policy instead. |
| `rdd_disabled` | Run the exact source-scoped `gentle-ai review mode enable` command rendered with this STATUS result, then re-run its exact repository-bound STATUS command. |
| `staged_delivery_candidate_required` | Stage every reviewed path exactly as it was reviewed, then re-run the route command with `--lineage <id> --projection staged --gate pre-commit --next-transition`. STATUS returns `review.validate` only when that staged candidate exactly matches the approved receipt. |
| `staged_workspace_overlay_recovery_unavailable` | Terminal — pass `--lineage <id>` to recover an existing lineage, or drop `--workspace-overlay` and run `gentle-ai review start --projection staged` to start fresh. |
| `unchanged_or_unverified_authority` | Terminal — `gentle-ai review start` on this exact unchanged candidate only resumes this same review, not a fresh one. Change the candidate content first, then run `gentle-ai review start` to begin a genuinely new one, or run `gentle-ai review mode disable --scope clone --cwd <repo>` to deliver under ordinary policy instead. |

## Repair Path

Before editing a correction candidate, validate the existing authority:

```bash
gentle-ai review repair --preflight --cwd <repo>
```

`repair --preflight` inspects invalid or quarantined lineages and returns repair instructions without modifying review state. Use it when `corrupted_or_unverifiable_authority` or other terminal codes indicate an unrecoverable authority. Do not change runtime, provider, or toolchain to resolve stop reason codes.

## RDD Scope Boundary

RDD mode enable/repair is user-owned and **out of scope** for this change. If a review requires RDD to proceed, the user must enable or repair it themselves through the appropriate native interface. This document does not cover RDD configuration, repair workflows, or mode transitions.

## Checklist

- [ ] Route command is invoked at the start of every review.
- [ ] Stop-reason codes are mapped through the continuation table, never invented.
- [ ] `repair --preflight` is used for invalid/quarantined lineages before editing.
- [ ] RDD mode changes are left to the user; no automation here touches RDD.
