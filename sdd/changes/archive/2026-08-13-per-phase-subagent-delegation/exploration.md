## Exploration: per-phase LLM sub-agent delegation for QuantLab campaigns

### Current State

**Execution model today: ONE subagent, inline loop.** `quantlab-campaign`
(`~/.config/opencode/prompts/quantlab/campaign.md`) owns the full 14-phase
loop and runs every phase INLINE in its own session — each phase is a section
of the campaign prompt that calls SDK code directly (`BuildConfig`,
`ConfigReviewStage`, `DispatchStage`, `RetesterStage`, `OptimizerStage`,
`PortfolioComposer`, `DeploymentAgent`, `DemoWindow`, `ArchivePhase`). There
are **no per-phase worker subagents**. The only delegation inside the loop is
phase 14 (`live-ops`): the live `~/.config` copy delegates the Guardian flow
to `quantlab-guardian` via the `task` tool (SDD-5, archived 2026-08-13) and
folds the `GuardianReport` envelope back in.

**Flow constant is code-only, immutable.** `sdk/quantlab/campaign/flow.py`
holds `PHASES` (14-tuple), `STAGE_FOR_PHASE` (phase → pipeline stage),
`assert_flow` (exact-order), and `assert_flow_segments` (presence + boundary
+ loop tail). REQ-37: `PHASES` MUST NOT be reordered/renamed/removed; any
per-phase change must WRAP or delegate, never mutate. `tests/campaign/test_flow_integrity.py` asserts the repo prompt copy (`AI/opencode/agents/campaign.md`) declares the same tuple.

**The pipeline has code-level "agents" per phase already.** `sdk/quantlab/agents/` holds SDK agent classes (`research_agent`, `llm_research_agent`, `hypothesis_builder/`, `builder_agent`, `config_reviewer`, `reviewer_agent`, `portfolio_agent`, `deployment_agent`, `archiver`, `monitoring_agent`, `execution_monitor`, `adaptive_retest_agent`, `autonomous_monitor`, `statistics_agent`, `analysis_agent`) — these are the *implementations* phases call, NOT LLM subagents. `ResearchDirector.build_pipeline(orchestrated=True)` wires them as pipeline stages (research_llm|research → hypothesis_builder → refutation → builder → config_review → dispatch → statistics → analysis → review → portfolio → compile → deploy → demo → archive → live_ops → execution_monitor → guardian_evaluate → [retester] → [optimizer]). `research_llm` is the one LLM-powered stage today — it calls provider APIs in-process (`llm_research_agent.py`), it is not an agent delegation.

**Orchestration surface is outside the repo.** `~/.config/opencode/opencode.json` registers: `quantlab-orchestrator` (primary, routing table), `quantlab-campaign` (subagent, `question: allow`, task `"*": deny, "quantlab-*": allow`), `quantlab-guardian` (subagent, deny-first same pattern), `quantlab-deploy`, `quantlab-monitor`, plus SDD/review agents. Prompts in `~/.config/opencode/prompts/quantlab/`: `orchestrator.md` (intent routing table: SDD→gentle-orchestrator, CAMPAIGN→quantlab-campaign, GUARDIAN→quantlab-guardian, CLI→sqcli, etc. + long-running policy), `campaign.md` (14-phase loop), `guardian.md` (bounded directives: evaluate | live_ops_status | escalation_ack, NO-phase rule), `deploy.md`, `monitor.md` (read-only). Repo mirrors live under `AI/opencode/agents/campaign.md` + `AI/opencode/skills/quantlab-run-campaign/SKILL.md`; skill is executor-gated (orchestrator must delegate via task).

**CRITICAL: the two campaign.md copies have already diverged both ways.**
Live `~/.config/.../campaign.md` (260 lines) contains the SDD-5 guardian
delegation in phase 14; repo `AI/opencode/agents/campaign.md` (314 lines)
contains newer content the live copy lacks (REQ-104 Prior Context Injection,
REQ-203/204/205 KB teaching table, `assert_flow_segments` guidance) — and
does NOT contain the guardian delegation. Tests assert exact paths of BOTH
(`tests/test_orchestrator_prompt.py` reads `~/.config` opencode.json +
orchestrator.md AND repo campaign.md; `tests/campaign/test_flow_integrity.py`
parses the repo PHASES tuple). SDD-5 verify already hit a "stale
`AI/opencode/agents/campaign.md` assertion" failure (pre-existing at d0a6b16).
Any per-phase change must define ONE source of truth and a sync mechanism —
this drift will otherwise compound 14×.

**Delegation surface.** Today the campaign loop delegates: (a) reasoning to
`quantlab-campaign` (orchestrator.md CAMPAIGN row, `task`), (b) live-ops to
`quantlab-guardian` (campaign.md phase 14). Long-running ops (dispatch, real
build/backtest, monitor, compile, deploy) are NEVER waited on by a subagent:
the executor writes a script under `/tmp/opencode/`, returns control, and the
ORCHESTRATOR runs it in its own shell with log polling (long-running policy,
in both orchestrator.md and campaign.md + skill). Per-phase delegation would
add a THIRD delegation tier (campaign → phase agent → orchestrator shell for
long ops), which must preserve the no-subagent-waits rule.

### Affected Areas

- `~/.config/opencode/opencode.json` — add N phase agents (name, mode, permission allowlist, `{file:...}` prompt refs). Deny-first `quantlab-*` wildcard pattern already established for campaign/guardian.
- `~/.config/opencode/prompts/quantlab/campaign.md` — rewrite the loop section to delegate per phase instead of inline; keep Result Contract + gate protocol + REQ-37 flow assert.
- `~/.config/opencode/prompts/quantlab/{phase}.md` (new, N files) — per-phase role, scope, bounded authority, long-running policy.
- `~/.config/opencode/prompts/quantlab/orchestrator.md` — possibly a phase-routing note; long-running policy must stay with orchestrator.
- `AI/opencode/agents/campaign.md` + `AI/opencode/skills/quantlab-run-campaign/SKILL.md` — repo mirrors MUST be synced (tests assert them); resolve drift first.
- `sdk/quantlab/campaign/flow.py` — MUST NOT change (REQ-37). At most, a per-phase *delegation contract* module could be added elsewhere in the SDK.
- `tests/test_orchestrator_prompt.py`, `tests/campaign/test_flow_integrity.py` — extend assertions (per-phase registration, sync check); `tests/test_campaign_docs.py` asserts README/STATE 14-phase chain.
- `sdk/quantlab/guardian/` (unchanged) — the precedent: `agent.py` glue + `feedback.py` envelope is the pattern a per-phase SDK entry could follow (guardian-orchestrator-feedback: PR1 SDK glue, PR2 orchestration surface).

### Approaches

1. **Prompt-only per-phase agents (no SDK change)** — N subagents defined in opencode.json + N prompt files; campaign.md delegates each phase via `task`; phases keep calling existing SDK code. Pros: zero SDK risk, mirrors SDD-5 PR2 slice, fast. Cons: 14 prompts × duplication of the loop contract (drift risk ×14), long-running policy must be restated per agent, no code-level enforcement of bounded authority. Effort: Medium.

2. **SDK-backed phase entrypoints (guardian pattern)** — add a thin per-phase delegation contract in the SDK (e.g. `sdk/quantlab/campaign/delegation.py` or per-phase `execute_<phase>()` glue like `guardian/agent.py`) that phase subagents call; prompts stay thin. Pros: bounded authority enforced in code, testable, matches SDD-5 precedent (PR1 SDK + PR2 orchestration). Cons: more surface, needs envelope/handoff contract design, largest slice. Effort: High.

3. **Family grouping (not 14 agents)** — group phases into a few role agents (research/hypothesis, config/review, dispatch/monitor, retest/optimize, portfolio/compile, deploy/demo, archive/live-ops). Pros: ~7 agents instead of 14, still "dedicated role per phase group", lower prompt duplication. Cons: not strictly per-phase; crosses REQ-37 gates less cleanly (a family agent spans multiple human-gated boundaries). Effort: Medium.

### Recommendation

Approach 2 scoped as TWO chained PRs (SDD-5 precedent: SDK slice + orchestration slice):
- PR 1 (SDK): per-phase delegation contract — envelope/dataclasses + `execute_phase` glue + tests; `flow.py` untouched.
- PR 2 (orchestration): N phase agents in opencode.json + N prompts + campaign.md loop rewrite + orchestrator.md touch + sync tests; repo mirrors updated.

Before design: resolve the repo/live prompt drift (pick one source of truth; add a sync test). Phase 14 (live-ops) already proves the delegation pattern works end-to-end.

### Risks

- REQ-37 (High): any PHASES mutation → FlowIntegrityError. Wrap/delegate only; add an integrity test asserting flow.py unchanged.
- Long-running policy (High): subagents get cancelled on long waits; phase agents MUST return scripts, never wait. Restate per agent + orchestrator executes.
- Prompt drift ×14 (High): two copies already diverged; per-phase prompts multiply the sync burden. One source of truth + sync test is mandatory.
- Human gates (Medium): AD-4 decision-file protocol + question tool; each phase agent must preserve lossless blocking prompts and fail-closed HOLD (REQ-11). Phase agents need `question: allow`.
- Permission model (Medium): deny-first `quantlab-*` allowlist must extend to new agents on orchestrator + campaign task lists.
- Token/context per phase (Medium): 14 agents × fresh context, cross-phase handoff contract needed (Result Contract envelope already exists as the vehicle).
- Test coupling (Medium): exact-path asserts in `test_orchestrator_prompt.py` will need per-phase additions; mock-vs-real (SQX_FORCE_MOCK) must stay intact.
- 400-line review budget (Medium): forecast exceeds budget → chained PRs (SDD-5 precedent: SDK + orchestration).

### Ready for Proposal

Yes — propose next (sdd-propose). Tell the user: flow.py PHASES stays 14 and untouched; the change is a wrapper/delegation layer; pick scope (14 agents vs family grouping) and the prompt source-of-truth sync strategy before spec.

### Open Questions for Proposal

1. Literal per-phase (14 agents) or family grouping (~7)? Cost per extra agent ≈ 1 prompt + registry entry + tests.
2. Where does the delegation contract live — pure prompts (Approach 1) or SDK glue (Approach 2)? If SDK: what envelope/handoff schema?
3. Which phases genuinely benefit from a dedicated LLM role vs. thin code wrappers (research/hypothesis/config/review/optimize are judgment-heavy; dispatch/compile are mechanical)?
4. How to fix the repo↔live prompt drift as part of this change (single source of truth, sync script, or test-enforced)?
5. Do phase agents present human gates themselves (question tool) or bubble them to the orchestrator/campaign agent (lossless blocking contract)?
6. Budget/scope guardrails: max agents, max prompt size, and whether long-running phase scripts stay owned by the orchestrator shell (recommended).
