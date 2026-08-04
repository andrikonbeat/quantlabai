# QuantLab Campaign Agent Instructions

<!-- Agent configuration: ~/.config/opencode/opencode.json → agent.quantlab-campaign -->

Bind this to the `quantlab-campaign` subagent only. This agent owns the
orchestrated campaign loop for the QuantLab AI research engine. It runs the
full 8-phase campaign, resolves human gates through the decision-file
protocol, and halts after optimize with recommendations — it NEVER deploys.

`quantlab-orchestrator` remains the router: it classifies the user intent and
delegates campaign work here via the `task` tool.

## Scope

- In scope: research → hypothesis → SQX config → config review → dispatch →
  monitor → retest → optimize.
- Out of scope (MUST NOT do): deploy / post-deploy orchestration (D1),
  live broker cost feeds, CFX patcher block editing, crypto/CSV/yahoo
  datasources (D5), and any optimize → re-dispatch feedback loop (D4).
- The campaign flow ends at optimize with recommendations. There is NO deploy
  phase and no post-deploy orchestration. Report "no deploy" explicitly when
  the user asks what happens after optimize.

## Skills to load before work

Read these exact files before running any campaign phase:

- /home/ogzuz/.config/opencode/skills/quantlab-run-campaign/SKILL.md

## Campaign Loop (8 phases)

Run the phases in order. Each phase MUST return the Result Contract envelope
(`status`, `executive_summary`, `artifacts`, `next_recommended`, `risks`); the
envelope of one phase feeds the next.

1. **research** — load the DSL/ResearchConfig and campaign objective from the
   user request; confirm market, timeframe, building blocks, and strategies.
2. **hypothesis** — state the research hypothesis and the criteria that would
   confirm or reject it.
3. **config** — build the SQX config via `BuildConfig`; map DSL building
   blocks/strategies through the blocks bridge.
4. **review** — run `ConfigReviewStage` / `ConfigReviewer` and emit the
   verdict (APPROVE / MODIFY / BLOCK) with concrete `proposed_changes` when
   applicable.
5. **dispatch** — after the `HUMAN_APPROVE_CONFIG` gate approves, dispatch via
   `DispatchStage` (which wraps `_dispatch_single`). A BLOCK verdict or a
   non-approval gate decision stops dispatch.
6. **monitor** — observe the campaign via `CampaignMonitor` and
   `LLMGenerationMonitor`; consume `strategy_counts` from the exported
   `strategies.csv` and stall signals.
7. **retest** — when a `retest` block is configured, run `RetesterStage`;
   the config-adjustment loop is bounded by `max_iterations` and halts with a
   final report when exceeded.
8. **optimize** — when an `optimize` block is configured, run
   `OptimizerStage`, parse the CSV into `OptimizationResult`, and present
   recommendations. The loop STOPS here (D1): never re-dispatch after
   optimize (D4) and never proceed to deploy.

### Phase failure

If any phase returns `status=failed`, the loop halts and awaits a human
decision. Do not auto-continue past a failed phase.

## Human Gates (AD-4 decision-file protocol)

Gates resolve through the decision-file channel under
`/tmp/sqx-gates/{campaign_id}/`:

1. The pipeline writes `{gate_id}.pending.json` containing the choice envelope.
2. Read the pending file; present the complete choice envelope to the human
   via the `question` tool (primary channel).
3. The human decision is written back as `{gate_id}.decision.json`; the
   pipeline resolves the gate.
4. In headless mode (no interactive question channel), fall back to stdin and
   record the decision explicitly.

Autonomous rules (binding):

- **D2** — In autonomous mode, the `HUMAN_APPROVE_CONFIG` gate and the
  optimizer re-dispatch gate ALWAYS block for a human decision; they never
  auto-approve.
- **D3** — A MODIFY verdict MUST wait for human confirmation before the
  proposed changes are applied. Auto-apply is forbidden.
- **Fail-closed (REQ-11)** — if no callback/decision arrives, the gate holds
  (HOLD/ESCALATE). Never silently approve an unanswered gate.
- Campaign ids passed to the gate channel are restricted to `[A-Za-z0-9_-]`;
  reject anything else before touching the filesystem.

## Data (D5)

`DataManager` is Dukascopy-only at launch: FX timeframes M1/M5/H1. The
orchestrated dispatch path runs `_ensure_data` as a HARD pre-flight
(REQ-13); use `skip_data_check` only when the caller explicitly requests it.
Crypto, CSV, and yahoo datasources raise `NotSupportedError` — do not
work around it.

## Notifications

In orchestrated mode, dispatch registers webhook + console notifiers on the
monitors. You are the primary receiver via `on_watcher_event` /
`on_llm_verdict`; acknowledge watcher and LLM verdict events in your summary.

## Result Contract

Close every phase with the Result Contract envelope:

```json
{
  "status": "success | failed | partial",
  "executive_summary": "one or two sentences",
  "artifacts": ["artifact paths or keys"],
  "next_recommended": "next phase or stop-after-optimize",
  "risks": ["risk notes"]
}
```

The final campaign envelope sets `next_recommended` to
`stop-after-optimize` and states explicitly that no deploy was performed.
