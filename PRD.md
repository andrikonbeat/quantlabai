# QuantLab AI — Product Requirements Document

**Status**: Draft v0.1.0
**Author**: QuantLab AI (inspired by the Gentle-AI ecosystem)
**Date**: 2026-08-08
**Scope**: Full implementation of the QuantLab AI research engine as a trading-domain port of the Gentle-AI architecture (orchestrator → sub-agents → skills → memory → gates → verification → install/TUI).

---

## 1. Summary

QuantLab AI turns StrategyQuant X (SQX) into a professionally harnessed trading research engine driven by an LLM orchestrator. The product is **not** another script that launches SQX: it is a persistent, memory-backed, human-gated ecosystem — an "LLM surrounded by harnesses" — modeled on the Gentle-AI repository architecture, adapted from the software-engineering domain to algorithmic trading.

**Who it helps**: traders who want a disciplined, repeatable path from a trading idea (e.g. "campaign with 100 USD") to strategies running live, with continuous learning across campaigns.

**Why it matters**: today QuantLab runs an in-process pipeline whose "agents" are Python code, not real LLM sub-agents; it lacks a complete memory discipline, a working compiler/deploy/archive chain, and a durable detached monitor for weeks-long generation runs. This PRD defines the target architecture, the phase flow, and the implementation slices.

---

## 2. Quick path (the flow at a glance)

QuantLab has **two orchestrators** that coexist under the same ecosystem (see §8):

**A. QuantLab-Orchestrator — generation flow (14 phases)**

```
QuantLab-Orchestrator (agent)
├─ 1. Reason over user input → define FRAME (risk, capital, timeframe, edge, instruments)
│
├─ 2. Research (sub-agent)          → gather evidence (FRED, Yahoo, news/RSS, Knowledge Lake) + formulate 3–5 hypotheses
├─ 3. HypothesisBuilder (sub-agent) → operationalize hypotheses into validated building blocks + strategies (NOT formulation — see §5.2)
├─ 4. Refutation (sub-agent)        → adversarially attack hypotheses before build
├─ 5. SQXconfig (sub-agent)         → parametrize hypotheses into ONE Custom Project: Builder + Retester + Optimizer + CreatePortfolio tasks
│
├─ 6. ConfigReviewer (sub-agent)    → review hypotheses + configs (parameter-by-parameter educational table)
│       └─ GATE HUMAN: HUMAN_APPROVE_CONFIG (fail-closed)
│
├─ 7. [ORCHESTRATOR] Execute: launch the Custom Project (detached daemon, no LLM wait)
├─ 8. [ORCHESTRATOR] Monitor: status + strategies.csv + LLM verdicts (continue/stop) — weeks-long capable
│       SQX chains internally: Build → Retest → Optimize → CreatePortfolio
│
├─ 9. ReviewerAgent (sub-agent)     → validate RESULTS against acceptance criteria
│       └─ GATE HUMAN: HUMAN_APPROVE_ITERATION
├─ 10. Portfolio (sub-agent)        → measure joint correlation/behavior; decide replacements for live strategies
│       └─ GATE HUMAN: HUMAN_APPROVE_PORTFOLIO
├─ 11. Compiler (sub-agent)         → export .java → javac → .jfx (external JDK)
├─ 12. Deploy (sub-agent)           → GATE HUMAN: HUMAN_APPROVE_DEPLOY
├─ 13. Demo (sub-agent)             → JForex demo (14 business days), compare live-demo vs SQX backtest
├─ 14. Archive (sub-agent)          → maintenance/replacement plan + account statistics
│       └─ GATE HUMAN: HUMAN_APPROVE_ARCHIVE
└─ 15. Handover → Guardian-Orchestrator for live-ops
```

**B. Guardian-Orchestrator — live-account flow (continuous, 24/7)**

```
Guardian-Orchestrator (agent)
├─ 1. Onboard deployed portfolio from the Archive phase (HUMAN_APPROVE_ARCHIVE receipt)
├─ 2. Monitor loop: equity/positions/costs stream → MetaGuardian evaluation → state machine
│      (NORMAL → VIGILANCE → DEFENSIVE → QUARANTINE → RECOVERY)
├─ 3. Detect strategy degradation vs backtest expectations; regime shifts; drawdown breaches
├─ 4. Notify user (summaries, alerts) — desktop + mobile push (24-7 ops surface)
├─ 5. Recommend actions with verified evidence: replacement candidates, reconfiguration, risk cut
│      └─ GATE HUMAN: HUMAN_APPROVE_REPLACEMENT (only for live changes)
└─ 6. Feedback → QuantLab-Orchestrator (live behavior informs next campaign) — bidirectional
```

---

## 3. Problem statement

### 3.1 Current state (verified against the codebase)

- The SDK (`sdk/quantlab/`) already implements the canonical 14-phase pipeline (`campaign/flow.py`) and a large harness surface: `ResearchAgent`, `LLMResearchAgent`, `HypothesisBuilder` + `RefutationLayer`, `BuilderAgent` + `BuildConfig` (~90 fields), `ConfigReviewer`, `ReviewerAgent`, `RetesterStage`/`OptimizerStage`, `PortfolioComposer`/`PortfolioMaster`, `CompileStage`, `JForexDeployer` (export only), `DeploymentAgent` (placeholder), `CampaignMonitor` + `LLMGenerationMonitor`, `MetaGuardianOrchestrator` + `AutonomousMonitorDaemon`, gates with decision files, Knowledge Lake + Engram dual memory (REQ-102/103), `compose_prior_context` (REQ-104).
- **Structural gap**: the "agents" are in-process Python stages executed by `PipelineRunner`; they are **not** real LLM sub-agents with fresh context, so their reasoning work is invisible and not delegatable. There is no per-phase delegation like Gentle-AI's orchestrator → sub-agent model.
- **Functional gaps**: compiler pipeline incomplete (javac/.jfx need external JDK); demo deploy is a placeholder with a 14-business-day window and no renewal; **archive phase does not exist**; Guardian → generation feedback is not wired; `MetaGuardianOrchestrator` + `AutonomousMonitorDaemon` exist in the SDK but run as in-process Python, not as a first-class `guardian-orchestrator` LLM agent with its own routing, skills, and live gates; no detached monitor capable of weeks-long generation runs (`poll_timeout` default is 1 hour); no install/TUI distribution.

### 3.2 The vision

QuantLab is a **trading-domain port of the Gentle-AI architecture**: same concepts — orchestrator, sub-agents, skills, persistent memory, human gates, bounded review, verification, installation — with the trading engine (SQX) as the execution substrate instead of a compiler/toolchain. Gentle-AI and QuantLab coexist in the same OpenCode ecosystem: QuantLab recommends installing Gentle-AI because both complement each other (Gentle-AI owns the agent ecosystem; QuantLab owns the trading domain).

---

## 4. Goals / Non-goals

### 4.1 Goals

- G1. Real per-phase delegation: every phase in §2 runs as a dedicated LLM sub-agent with its own prompt, skills, and model routing, orchestrated by `quantlab-orchestrator` — never inline code pretending to be an agent.
- G2. Canonical flow preserved: all 14 generation phases in order, each human-gated, enforced by `assert_flow` (REQ-37), plus the live-account handover to the Guardian-Orchestrator.
- G9. **Two first-class orchestrators**: `quantlab-orchestrator` (generation) and `guardian-orchestrator` (live-account 24/7) are both real OpenCode agents with their own routing, gates, memory, and skills; the Guardian is not a terminal phase but a persistent orchestrator with its own lifecycle (see §8).
- G3. One-Custom-Project execution: leverage SQX native task chaining (Build → Retest → Optimize → CreatePortfolio) so 3 configs + 3 monitor runs collapse into one project load + one monitor loop.
- G4. Complete memory discipline: define How / When / Where / Why / What-for each piece of stored knowledge; complement (never replace) Engram with a structured trading Knowledge Lake; support future model training and private multi-user enrichment.
- G5. Campaign review (bounded review adapted to trading): frozen decision snapshots, risk-scaled review lenses, one bounded correction per candidate, receipts that gates validate without reopening.
- G6. Weeks-long generation support: detached monitor process writing periodic checkpoints, notifying on terminal/WARNING/CRITICAL states, with orchestrator re-entry.
- G7. Distribution: a `quantlab` CLI + TUI (installation, campaign status, artifact browser), modeled on Gentle-AI's install/verify/rollback experience.
- G8. Education by design: every SQX parameter configured is documented (what it does, why chosen, what edge it serves) — the "teach while working" principle.

### 4.2 Non-goals

- Not a code-fork of Gentle-AI: no porting of Go code; only the architecture/concepts are reused (see §12).
- Not an optimizer/re-dispatch feedback loop (D4): optimize does not auto re-dispatch.
- Not a multi-user hosted platform in v1; training-data enrichment from other users is a future capability with privacy gates.
- Not a replacement for Engram; Engram stays as session-persistence and is complemented by the Knowledge Lake.
- No crypto/CSV/yahoo datasources (D5); DataManager remains Dukascopy-only.

---

## 5. Architecture

### 5.1 Layered model

```
┌─────────────────────────────────────────────────────────────┐
│ L4 Distribution: quantlab CLI + TUI (install, status, browse)│
├─────────────────────────────────────────────────────────────┤
│ L3 Orchestration: TWO orchestrators — quantlab-orchestrator │
│   (generation: router, frame owner, gate holder) and        │
│   guardian-orchestrator (live-ops: monitor router, alert    │
│   owner, replacement gate holder); both delegate to L2      │
├─────────────────────────────────────────────────────────────┤
│ L2 Sub-agents (LLM, fresh context): research, hypothesis,    │
│   refutation, sqx-config, config-review, reviewer, portfolio,│
│   compiler, demo, archive, monitor-verdict, guardian         │
├─────────────────────────────────────────────────────────────┤
│ L1 Harness SDK (Python, existing): pipeline, stages, gates,  │
│   monitors, knowledge, costs, regime, guardian, data         │
├─────────────────────────────────────────────────────────────┤
│ L0 Substrate: SQX daemon (sqcli HTTP API) + JForex + JDK     │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Key design decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Research **and** hypothesis formulation live in the Research phase (one sub-agent, full search context) | `ResearchAgent.formulate_hypotheses` already uses `query_results` to calibrate confidence; the idea-generation step belongs with the evidence-gathering step (verified). |
| D2 | HypothesisBuilder is a **separate phase that operationalizes**, not formulates | Converts qualitative `HypothesisConfig` → validated `BuildingBlock`/`Strategy`; enables cheap re-runs (no re-fetch), independent validation, dual rule/LLM mode, and a refutation insertion point. |
| D3 | Refutation is mandatory between formulation and build | Adversarial attack against hypotheses is the cheapest place to kill a bad idea. |
| D4 | Configuration is **one Custom Project per hypothesis (or similarity group)** | SQX natively chains Build→Retest→Optimize→CreatePortfolio as tasks (verified in #717); collapses 3 config sub-agents + 3 executions into 1 config + 1 monitor. |
| D5 | Portfolio composition happens **after** generation | The composer needs generated strategies; placing it before execution was a design error corrected in review. |
| D6 | The orchestrator is **frame owner, not reasoner**: defines risk/capital/timeframe/instrument frame and gates results; delegates reasoning to sub-agents | Matches Gentle-AI's "delegate the reasoning, own the frame, gate the result" (verified #717). |
| D7 | The LLM **never waits** on SQX generation | Detached daemon launch + polling + verdicts + `loadconfig` reconfiguration; the orchestrator re-enters on events (see §9). |
| D8 | Memory: Engram (sessions) + Knowledge Lake (structured trading domain), dual-write, never replace | Already REQ-103; this PRD formalizes the 5W discipline (see §7). |
| D9 | Campaign review freezes **decision snapshots**, not code bytes | Trading's equivalent of the bounded-review candidate: config+criteria (pre-dispatch) and results+stats (post-generation), each hashed and immutable during review. |
| D10 | The Guardian is a **second orchestrator**, not a phase | Generation and live-account operation have disjoint lifecycles (batch vs. continuous), disjoint gates (campaign approval vs. live replacement approval), and disjoint memory rhythms; merging them forces a 24/7 agent to babysit generation or forces live risk decisions into a batch flow. |
| D11 | Guardian feedback → generation is **bidirectional and evidence-gated** | Live behavior (decay, regime, drawdown) feeds the next campaign's prior context; generation results feed the Guardian's expectation baselines. Both directions flow through Knowledge Lake + Engram, and only verified findings open a gate. |

### 5.3 Skills model

Each L2 sub-agent loads one or more SKILL.md files resolved through the skill registry (same mechanism as Gentle-AI). Initial skill catalog:

| Skill | Trigger | Owner |
|-------|---------|-------|
| `quantlab-run-campaign` | full campaign intent | executor |
| `quantlab-research` | research phase | research sub-agent |
| `quantlab-sqx-config` | SQX config phase (builder/retest/optimizer/portfolio tasks) | sqx-config sub-agent |
| `quantlab-review` | config/results review phase | reviewer sub-agents |
| `quantlab-compiler` | compile phase | compiler sub-agent |
| `quantlab-demo` | demo deploy phase | demo sub-agent |
| `quantlab-archive` | archive phase | archive sub-agent |
| `quantlab-guardian` | live-ops monitoring | guardian sub-agent |

AGENTS.md in the QuantLab root becomes the skill index (trigger → path), mirroring Gentle-AI's AGENTS.md.

---

## 6. Memory system (G4)

### 6.1 The 5W discipline — How / When / Where / Why / What-for

| Question | Design |
|----------|--------|
| **HOW** | Capture at phase boundaries using the Result Contract envelope (`status`, `executive_summary`, `artifacts`, `next_recommended`, `risks`) + decisions with rationale + hashed/versioned artifacts. Index with FTS + structured metadata (campaign, phase, instrument, timeframe, edge). |
| **WHEN** | Every phase boundary, every human gate decision, every correction/reconfiguration, every monitor discovery, every LLM-monitor verdict, every archive closure. |
| **WHERE** | Two complementary stores: Engram (agent session persistence) + Knowledge Lake (`knowledge/` with `agent-memory/`, `kb/`, `structured/{campaign_id}/`) — dual-write, never single-write. |
| **WHY** | Continuous learning: each campaign improves the next; never repeat an error; evidence-based decisions. |
| **WHAT-FOR** | (1) Inject the right context at the right moment via `compose_prior_context(campaign_id, phase)`; (2) export datasets for private model fine-tuning; (3) future privacy-scrubbed multi-user enrichment. |

### 6.2 Retrieval at the right moment

The orchestrator injects a **curated, phase-filtered context block** into each sub-agent before delegation (REQ-104). Sub-agents never search the lake themselves; they receive what the orchestrator pre-selected. Retrieval is: phase + campaign + instrument/timeframe/edge filters, ranked by recency and relevance, bounded (limit parameter), and never dumps the whole lake.

### 6.3 Training and privacy

- `knowledge/training.py` already exports the memory to dataset format; extend to per-phase JSONL (envelope + decision + result) suitable for fine-tuning.
- Privacy: all data stays local by default. Future multi-user enrichment requires explicit, privacy-scrubbed, opt-in export (no raw argv, paths, credentials, or user-identifying data) — reuse the existing `knowledge/privacy.py`.
- Engram complementarity is contractual: a decision is **never** persisted to only one store (REQ-103).

### 6.4 Context7 / CodeGraph

- **Context7**: docs for external libraries/tools (JForex API, SQX daemon, Python deps) when sub-agents need current API knowledge. Context tooling, not memory.
- **CodeGraph**: structural index of the QuantLab SDK itself so sub-agents navigate code with blast-radius context. Context tooling, not memory.

---

## 7. Campaign review (G5)

The Gentle-AI bounded review adapted from code diffs to trading decision snapshots:

| Gentle-AI concept | Campaign adaptation |
|-------------------|---------------------|
| Frozen candidate (git bytes) | Frozen decision snapshot (config+criteria pre-dispatch; results+stats post-generation), hashed, immutable during review |
| Risk → lenses | Low risk: structural readback; standard: one domain lens; high: 4 domain lenses |
| 4R lenses (code) | Risk of market/execution, interpretability, statistical robustness (WF/MC), degradation/resilience |
| One bounded correction | One reconfiguration iteration + retest, never regenerate-to-clean (loop prohibition) |
| Only candidate-caused findings block | Only violations of pre-agreed acceptance criteria block; pre-existing regime conditions go to follow-up; unknown escalates to human |
| Deterministic blockers need no refuter | Guardian checks / KB consult block directly; inferential findings share one read-only refuter |
| Two judges | Two judges decide final verdict |
| Receipt validated by gates | Campaign receipt validated by `HUMAN_APPROVE_*` gates without reopening review |

---

## 8. Guardian-Orchestrator (live-account orchestrator)

The Guardian is the **second orchestrator** of QuantLab AI (G9, D10). Where `quantlab-orchestrator` runs the batch generation flow (§2.A), `guardian-orchestrator` runs the **continuous live-account operation**: monitoring, regime detection, degradation alerts, replacement recommendation, and feedback back into generation. The two share the same substrate (SDK, SQX, JForex, memory, gates) but have **disjoint lifecycles, gates, and memory rhythms**.

### 8.1 Definition

A real OpenCode agent (`guardian-orchestrator`) defined in the QuantLab agent set, with its own routing, prompts, skills, and model assignment — the exact equivalent of `quantlab-orchestrator`, not a phase inside it. It owns:

- **The live-account frame**: account(s), capital at risk, deployed portfolio, per-strategy allocation, risk limits.
- **The monitor loop**: schedules and interprets `MetaGuardianOrchestrator` + `AutonomousMonitorDaemon` (already in the SDK, §3.1) and turns their state machine into user-facing operation.
- **The live gates**: `HUMAN_APPROVE_REPLACEMENT` (fail-closed) is the only path that changes a live position; everything else is advisory.
- **Feedback routing**: verified live findings become prior context for the next generation campaign (D11).

### 8.2 Lifecycle

```
Onboard  ──►  Monitor  ──►  Evaluate  ──►  Notify  ──►  (loop)
  │              │             │             │
  │              └── alerts:   ├── state transitions (NORMAL → VIGILANCE → DEFENSIVE → QUARANTINE → RECOVERY)
  │                             └── findings: degradation vs backtest baseline, regime shift, drawdown breach
  ▼
Gate HUMAN_APPROVE_REPLACEMENT ──► apply change ──► re-baseline
  │
  └── feedback → Knowledge Lake / Engram → compose_prior_context(next campaign)
```

- **Continuous vs. batch**: the Guardian never waits for a campaign. It re-enters on schedule (polling cadence) and on events (alert conditions), regardless of whether `quantlab-orchestrator` is idle.
- **Human-in-the-loop**: every live mutation is a human-gated decision; the Guardian recommends with verified evidence, never executes on its own.
- **Memory**: live-ops observations are dual-written (Engram + Knowledge Lake) under the same 5W discipline (§6), tagged with live-account scope so retrieval is disjoint from campaign scope.
- **Baselines**: each deployed strategy carries its backtest expectation (from Archive phase); the Guardian compares live vs. expected behavior (drawdown, deviation, regime fit) and escalates only verified violations.

### 8.3 Guardian skills and sub-agents

| Skill | Trigger | Owner |
|-------|---------|-------|
| `quantlab-guardian` | live-ops monitoring | guardian-orchestrator |
| `quantlab-guardian-alert` | alert synthesis / user notification | guardian-orchestrator delegate |
| `quantlab-replacement` | replacement candidate selection (portfolio + reviewer evidence) | guardian-orchestrator delegate |

Guardian sub-agents run with fresh context like generation sub-agents (§5.3); the Guardian routes each evaluation to a focused delegate and synthesizes the result.

### 8.4 Bidirectional feedback contract (D11)

- **Live → generation**: verified degradation, regime shifts, and strategy-level live-vs-backtest deltas are persisted as structured prior context; the next campaign's Research phase receives them via `compose_prior_context` (REQ-104). This closes the loop without ever auto-trading.
- **Generation → live**: archive baselines, risk/allocations, and maintenance plans (phase 14) are the Guardian's onboarding input; the Guardian treats them as the expectation baseline until a human-approved change re-baselines.

---

## 9. Weeks-long generation (G6)

- Execution: orchestrator launches the Custom Project through the `sqcli` daemon (HTTP API) and **returns** — no LLM turn stays alive.
- Monitor: `CampaignMonitor` + `LLMGenerationMonitor` poll `-project action=status` + `strategies.csv`, detect `campaign_complete` / `zero_growth_stall` / `config_error` / excessive rejection, write gate decision files and notify (`NotifierDispatcher`).
- **New: detached mode.** Monitor as a persistent process (systemd/tmux daemon) that writes periodic checkpoints (not only at end), survives orchestrator/session death, and notifies on terminal/WARNING/CRITICAL states. `CampaignConfig.poll_timeout` default must be lifted/configurable for multi-day/multi-week runs.
- Re-entry: on event (or user prompt), a fresh orchestrator turn reads checkpoint + Knowledge Lake + Engram gate decisions, decides the next stage, continues.
- Root-cause support: during monitoring the LLM can analyze all available data to find generation blockers (hypothesis-logic or technical) with verified evidence, and recommend where the user should look or when to cancel/reconfigure (`-project action=loadconfig`).

---

## 10. Distribution (G7)

A `quantlab` CLI + TUI modeled on Gentle-AI's install experience:

- `quantlab install` — installs/verifies the SDK, SQX daemon integration, JDK for compiler, OpenCode agent definitions, skills, Knowledge Lake layout.
- `quantlab campaign new|status|resume|cancel` — orchestration entry points.
- `quantlab memory browse|search` — artifact browser over the Knowledge Lake.
- `quantlab doctor` — health checks (SQX daemon, JDK, data, gates).
- Rollback/verify equivalents for each install step.

---

## 11. Implementation slices

Ordered so each slice unlocks the next. Delivery strategy: chained PRs (forecast likely exceeds 400 lines).

| Slice | Scope | Unlocks |
|-------|-------|---------|
| S1 | **Custom-project CFX generator**: DSL `CustomProject` (ordered tasks, databank source/target, filters, loops/GoToTask, Notification) + multi-task `.cfx` generator validated against archive samples (144/2953) | D4: one project chains Build→Retest→Optimize→CreatePortfolio |
| S2 | **Unified execution substrate**: one parameterized Executor/Runner (build/retest/optimize/portfolio) replacing 3 overlapping paths; checkpoint+resume; detached monitor mode with periodic checkpoints + notifications | G6, G3 |
| S3 | **Per-phase sub-agent delegation**: convert agent stages into real `task` delegations (`quantlab-research`, `quantlab-sqx-config`, ...); keep `requires/provides` contract | G1 |
| S4 | **Memory discipline level 2**: formalize 5W capture (metadata schema, retrieval-by-phase, dataset export, privacy-scrubbed enrichment path) | G4 |
| S5 | **Campaign review**: frozen snapshots, domain lenses, refutation, two-judge verdict, receipts | G5 |
| S6 | **Compiler pipeline**: javac + .jfx + error-fix loop (external JDK required) | phase 11 |
| S7 | **Demo deploy**: renewal automation for the 14-day window, SQX-vs-JForex comparison | phase 13 |
| S8 | **Archive phase**: maintenance/replacement plan + account statistics + plan refresh | phase 14 |
| S9 | **Guardian-Orchestrator (first-class agent)**: define `guardian-orchestrator` OpenCode agent, its routing/prompts/skills (`quantlab-guardian`, `quantlab-guardian-alert`, `quantlab-replacement`), live gates (`HUMAN_APPROVE_REPLACEMENT`), monitor-loop integration with `MetaGuardianOrchestrator` + `AutonomousMonitorDaemon`, onboarding from Archive baselines | G9, D10, live-ops |
| S10 | **Guardian feedback loop (bidirectional)**: live-ops metrics → generation prior context (`compose_prior_context`), generation baselines → Guardian expectations; verified findings only, no auto-trading | D11, live-ops |
| S11 | **Distribution**: CLI + TUI + install/verify/rollback | G7 |

### 11.1 OpenSpec / SDD

Implement S1–S11 as one SDD change with phased slices (`full-campaign-flow`), consistent with the archived `orchestrated-campaign-flow` + `knowledge-memory-system` changes. Each slice keeps the 14-step generation flow intact (`assert_flow`) and the Guardian-Orchestrator lifecycle (§8.2).

---

## 12. Relationship to Gentle-AI

QuantLab **does not fork** Gentle-AI. It is an **architecture port**:

- **Reuse (concepts)**: orchestrator/sub-agent model, skills + registry + AGENTS.md index, Engram memory, human gates with decision files, bounded review discipline, SDD methodology, install/verify/rollback experience, TUI patterns.
- **Reuse (tools)**: Engram (installed by Gentle-AI), Context7, CodeGraph, OpenCode agent definitions, skills.
- **Do not port**: Go code, code-diff review receipts, PR-gated delivery — those belong to the software domain.
- **Coexistence**: QuantLab recommends installing Gentle-AI; both live in the same OpenCode ecosystem, one owning the agent ecosystem, the other the trading domain.

---

## 13. Risks

- SQX Custom Project task list is build-dependent (verified 21 tasks in 144/2953); schema acceptance of the simplified CFX dialect must be validated against archive samples.
- JForex engine is experimental since build 130; Dukascopy backtests run on the MetaTrader4 engine.
- Demo account renewal remains semi-manual (14 business days).
- `j64/` bundled JRE is not a JDK; the compiler slice needs an external JDK (e.g. `QUANTLAB_JDK_HOME`).
- Mock-vs-real divergence: the large suite runs on the mock server (`SQX_FORCE_MOCK`); real-daemon slices need explicit E2E.
- Detached monitor introduces process-lifecycle complexity (systemd/tmux, log rotation, crash recovery).
- Guardian live-account operation is a **second always-on surface**: alert fatigue, false-positive degradation alerts, and 24/7 notification routing need explicit policies (thresholds, dedup, quiet hours); every live change stays human-gated.
- Privacy for future multi-user enrichment is a hard gate: no export without explicit privacy scrub.

---

## 14. Checklist (verification)

- [ ] `assert_flow(PHASES)` passes before any campaign starts and after any harness change (REQ-37).
- [ ] `guardian-orchestrator` is a real OpenCode agent (own routing, prompts, skills, model) — not a phase inside `quantlab-orchestrator`.
- [ ] Guardian lifecycle (§8.2) runs continuously and independently of campaign execution; every live mutation goes through `HUMAN_APPROVE_REPLACEMENT` (fail-closed).
- [ ] Every phase in §2 is a real delegated sub-agent with its own skill(s) — no inline-code agent.
- [ ] Each SQX parameter configured produces the educational table (tab, parameter, what/why/for, edge).
- [ ] Memory captures every gate decision to BOTH Engram and Knowledge Lake (REQ-103).
- [ ] Retrieval into sub-agents is phase-filtered and bounded (REQ-104) — never a lake dump.
- [ ] A weeks-long generation run survives orchestrator/session death via detached monitor + periodic checkpoints.
- [ ] Campaign review freezes hashed snapshots; only pre-agreed acceptance-criteria violations block; one bounded correction max.
- [ ] `HUMAN_APPROVE_*` gates validate the campaign receipt without reopening review.
- [ ] Compiler slice produces `.jfx` and halts fail-closed on any compile error (REQ-29/30).
- [ ] Archive phase writes a maintenance/replacement plan with account statistics.
- [ ] Guardian live-ops metrics feed back into the generation flow (live → generation) and archive baselines onboard the Guardian (generation → live), verified findings only.
- [ ] `quantlab install` completes with verify + rollback on a clean machine.

---

## 15. Next step

Approve this PRD, then start S1 (Custom-project CFX generator) as the first SDD slice of the `full-campaign-flow` change. The exploration artifact (#723) and SQX custom-project analysis (#717) are the reference inputs.
