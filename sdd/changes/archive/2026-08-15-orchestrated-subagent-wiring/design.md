# Design: Orchestrated Subagent Wiring

## Technical Approach

Three fronts, one spine: `delegation.py`'s envelope machinery gains a production executor registry (F1) bridged by a new `phase_runner` CLI; the 14 phase prompts get real LLM reasoning over mapped SDK classes (F2); a second first-class orchestrator `guardian-orchestrator` owns the live-ops surface (F3). Spec: REQ-803, REQ-815..825.

## Architecture Overview

```
phase subagent ──bash──► python3 sdk/quantlab/campaign/phase_runner.py --phase X --directive '<json>'
                                │
                                ▼
                        PhaseDirective ──► execute_phase(directive)
                                │              │
                                │     PRODUCTION_EXECUTORS[X] (deny-first: none → AuthorityViolationError,
                                │     mock under SQX_FORCE_MOCK=1)
                                │              │
                    ┌───────────┴───────────┬───────────────┐
                    │ reasoning phases     │ mechanical     │ live-ops
                    │ run SDK stage via    │ return         │ execute_guardian_directive()
                    │ STAGE_FOR_PHASE, LLM │ LongOpSpec     │ (guardian SDK, no new phase)
                    │ reasons over result  │ handoff        │
                    └───────────┬───────────┴───────┬───────┘
                                ▼                   ▼
                     validated PhaseResult (JSON)  orchestrator shell: nohup → /tmp/opencode, timeout≥240
```

```
intent ─► quantlab-orchestrator ──CAMPAIGN──► quantlab-campaign (14-phase loop, PHASES)
                                              └─ per phase: task quantlab-phase-<p> → phase_runner → SDK stage
intent ─► quantlab-orchestrator ──GUARDIAN-LIVE──► guardian-orchestrator (task)
                    ├─ task ► quantlab-guardian (evaluate / live_ops_status)
                    ├─ task ► quantlab-guardian-alert (alert synthesis)
                    ├─ task ► quantlab-replacement (candidate selection)
                    └─ HUMAN_APPROVE_REPLACEMENT gate (decision-file, APPROVE-only)
```

## F1 — Real Runner Wiring

**D1 — `phase_runner` is a standalone module, not a CLI subcommand.** Path `sdk/quantlab/campaign/phase_runner.py`, invoked `python3 sdk/quantlab/campaign/phase_runner.py --phase <name> --directive '<json>'`. Option | tradeoff | decision: CLI subcommand (`sqcli phase run`) | cleaner UX | rejected — phase-agent bash allowlist is `sdk/quantlab/campaign/*`; a subcommand wouldn't match it and would force per-agent permission changes. Module path also satisfies REQ-818 ("under `sdk/quantlab/campaign/`").

**D2 — Executor registry lives in `delegation.py`** (REQ-815): `PRODUCTION_EXECUTORS: dict[str, PhaseExecutor]` keyed by `PHASES` entry; each executor resolves its stage from `STAGE_FOR_PHASE`, rejects out-of-scope before running (deny-first, REQ-803). `execute_phase()` resolution order: explicit `executor` arg → registry → `_mock_executor` when `SQX_FORCE_MOCK=1` → `AuthorityViolationError`. Existing mock behavior and tests preserved (REQ-810).

**D3 — Hybrid split (REQ-816):**

| Phase | Executor action | Mode |
|---|---|---|
| research, hypothesis, config, review, portfolio, optimize, archive | Run SDK stage; LLM reasons over result | subagent reasoning, `handoff_payload=None` |
| dispatch, monitor, compile, deploy, demo | Return `LongOpSpec`; never wait (REQ-809) | mechanical handoff |
| retest | Conditional on `config.retest`; long run → `LongOpSpec` | handoff when long, else inline |
| live-ops | `execute_guardian_directive()` → `GuardianReport` folded into `evidence` | guardian delegation |

**D4 — `_run_campaign.py` retirement (REQ-817).** Migration sweep result: zero live references — only historical openspec archives and method-name false positives (`test_run_campaign_*` targets `CampaignOrchestrator.run_campaign`). Decision: remove in one commit, add migration note (docs) `_run_campaign.py → campaign run-flow`. `cmd_campaign_run_flow` stays the sole real campaign entry; `phase_runner` is the per-phase bridge inside the orchestrated loop — run-flow remains the infrastructure driver.

**D5 — Handoff policy (REQ-818):** `log_path` under `/tmp/opencode/`, `timeout >= 240` (default 300), `cleanup` required (`pkill`/`rm`), per-phase report `/tmp/opencode/{phase}.report.md`. `LongOpSpec.__post_init__` already enforces `>= 240`.

## F2 — Prompt Enrichment (REQ-819)

| Phase | SDK class (stage) | Reasoning to add |
|---|---|---|
| research | `LLMResearchAgent` (`research_llm`) | KB rationale: `KbStore.consult` hits, REQ-203/204/205 |
| hypothesis | `hypothesis_builder/llm.py` | generation rationale |
| config | `BuildConfig`/`BuilderAgent` (`builder`) | teaching-table rationale (REQ-205) |
| review | `ConfigReviewStage`/`ConfigReviewer` (`config_review`) | verdict + `proposed_changes` |
| monitor | `CampaignMonitor`/`ExecutionMonitor` (`execution_monitor`) | stall diagnosis |
| optimize | `OptimizerStage` (`optimizer`) | recommendation reasoning |
| portfolio | `PortfolioComposer`/`portfolio_agent` (`portfolio`) | composition reasoning |
| archive | `ArchivePhase`/`Archiver` (`archive`) | maintenance-plan reasoning |
| dispatch, retest, compile, deploy, demo, live-ops | grounded instructions + long-op/guardian policy | keep `handoff_payload` contract |

Exemplar structure for `phase-review.md` (applied to all 14): existing Role/Bounded Authority/Instructions/Gates/Result Contract + new `## Reasoning` block — "Run `ConfigReviewStage`; reason over the KB teaching table; emit verdict APPROVE/MODIFY/BLOCK with concrete `proposed_changes`; return `evidence.verdict`" — plus `## SDK Examples` pinned to the mapped class.

**D6 — Permission model (REQ-820):** keep `edit:false, write:false` on all 14 agents; SDK stages (via `phase_runner`) write artifacts. Config file: agent returns the artifact key in the envelope; `phase_runner`/SDK writes it.

**D7 — Sync contract (REQ-806/821):** `sync_prompts.py` `MANAGED_NAMES` gains explicit `guardian-orchestrator.md` (managed set = `campaign.md` + `phase-*.md` + `guardian-orchestrator.md`); `guardian.md`/`orchestrator.md` stay non-managed. Update in same change: `test_guardian_live_prompt_never_synced` (asserts `guardian-orchestrator.md` IS synced, `guardian.md`/`orchestrator.md` untouched) and `test_non_managed_live_prompts_outside_allowlist` allowlist-shape assertion.

## F3 — Guardian-Orchestrator (REQ-822..825)

**Prompt `ai/opencode/agents/guardian-orchestrator.md`** (managed): sections — Role (second first-class orchestrator, own cadence); Routing table (GUARDIAN-LIVE intents); Delegates (`quantlab-guardian`, `quantlab-guardian-alert`, `quantlab-replacement` via `task`, each returning Result Contract, synthesized); Gates (decision-file protocol, fail-closed); NO-phase rule (REQ-37: `PHASES` stays 14, never a pipeline stage); Long-running policy.

**opencode.json entry** (live, outside VCS): `mode: primary`, visible (no `hidden`), deny-first mirroring `quantlab-orchestrator`:

```json
"guardian-orchestrator": {
  "description": "QuantLab guardian orchestrator — live-ops routing, gates, delegates",
  "mode": "primary",
  "permission": {
    "bash": {"*": "deny", "sdk/quantlab/*": "allow", "knowledge/*": "allow", "/tmp/opencode/*": "allow"},
    "question": "allow",
    "task": {"*": "deny", "quantlab-*": "allow",
             "quantlab-guardian": "allow", "quantlab-guardian-alert": "allow", "quantlab-replacement": "allow"}
  },
  "prompt": "{file:~/.config/opencode/prompts/quantlab/guardian-orchestrator.md}",
  "tools": {"bash": true, "read": true, "task": true, "question": true, "edit": false, "write": false}
}
```

**D8 — Routing (REQ-823):** live `orchestrator.md` (non-managed) gains a routing row `guardian evaluation`-adjacent keywords `GUARDIAN-LIVE` → `guardian-orchestrator` via `task`, mirroring SDD→`gentle-orchestrator`. Decision (from exploration): disjoint lifecycles, one interactive session — `task` delegation. Disjoint cadence preserved: campaign loop never reordered (REQ-37).

**D9 — `HUMAN_APPROVE_REPLACEMENT` (REQ-824): guardian-domain gate, NOT a run-flow pipeline gate.** Placing it in `cmd_campaign_run_flow`'s `HUMAN_*` loop would add flow surface to the terminal live-ops phase (REQ-37 risk). It lives in `guardian-orchestrator`: decision-file protocol under `/tmp/sqx-gates/{campaign_id}/` (`pending.json` → `decision.json`), `action == approve` only; HOLD/missing/non-approve blocks the replacement; the strategy is never auto-replaced (D10/D11). Reuses `DecisionsFileGateCallback` semantics (fail-closed).

**D10 — Delegates (REQ-825):** `quantlab-guardian-alert` (alert synthesis/notification) and `quantlab-replacement` (candidate selection from portfolio + reviewer evidence) as new `mode: subagent`, `hidden`, deny-first entries in live `opencode.json` with inline prompts (pattern: `jd-fix-agent`). Rationale: fixed-behavior delegates; inline keeps the sync allowlist scoped to REQ-806's three families. `quantlab-guardian` already exists; its GUARDIAN route is now shared by both orchestrators (REQ-642 modified).

**D11 — Live-config editing & parity:** agent definitions live only in `~/.config/opencode/opencode.json` (outside VCS). Apply edits it directly; verification is test-driven — `tests/test_orchestrator_prompt.py`-style assertions read live config and assert entry shape (mode primary, deny-first perms, prompt ref). Versioning: the repo prompt is the versioned artifact; the JSON entry shape is pinned by the parity tests (no VCS snapshot — the tests are the contract).

## Interfaces / Contracts

```python
# delegation.py (REQ-815)
PhaseExecutor = Callable[[PhaseDirective], Awaitable[PhaseResult]]
PRODUCTION_EXECUTORS: dict[str, PhaseExecutor]        # keyed by PHASES; exported

# phase_runner.py (REQ-818)
def build_directive(phase: str, directive_json: str) -> PhaseDirective  # strict JSON; PhaseNotFoundError
async def run(phase: str, directive_json: str) -> PhaseResult          # execute_phase + validate
def main(argv: list[str] | None = None) -> int                         # --phase/--directive; JSON envelope to stdout
```

Executor contract: run stage → build validated `PhaseResult` (`phase_id` from directive); mechanical executors set `handoff_payload` per D5; live-ops executor folds `GuardianReport` into `evidence`.

## File Changes

| File | Action | Description |
|---|---|---|
| `sdk/quantlab/campaign/phase_runner.py` | Create | CLI bridge → executor, JSON emit |
| `sdk/quantlab/campaign/delegation.py` | Modify | Registry + resolution (REQ-803/815/816) |
| `sdk/quantlab/campaign/__init__.py` | Modify | Export `PRODUCTION_EXECUTORS` |
| `_run_campaign.py` | Delete | Retired (REQ-817) |
| `ai/opencode/agents/phase-*.md` (14) | Modify | Reasoning enrichment (REQ-819) |
| `ai/opencode/agents/guardian-orchestrator.md` | Create | Second orchestrator (REQ-822) |
| `ai/opencode/sync_prompts.py` | Modify | Allowlist + `guardian-orchestrator.md` |
| `tests/campaign/test_prompt_sync.py` | Modify | Contract change (REQ-821) |
| `tests/campaign/test_delegation.py` | Modify | Registry + hybrid split |
| `tests/campaign/test_phase_runner.py` | Create | Runner round-trip |
| `tests/gates/test_run_flow_gates.py` | Modify | Replacement gate fail-closed |
| `tests/test_orchestrator_prompt.py` | Modify | Guardian-orchestrator registration/routing |
| `~/.config/opencode/opencode.json` | Modify | Entries (live, outside VCS) |
| `~/.config/opencode/prompts/quantlab/orchestrator.md` | Modify | GUARDIAN-LIVE row (live, non-managed) |
| docs (README) | Modify | Migration note `_run_campaign.py → campaign run-flow` |

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Unit | Registry completeness | `PRODUCTION_EXECUTORS.keys() == PHASES`; each resolves `STAGE_FOR_PHASE` |
| Unit | Runner round-trip | `phase_runner` JSON in → validated `PhaseResult` JSON out; unknown phase → `PhaseNotFoundError`; out-of-scope → `AuthorityViolationError`, no stage runs |
| Unit | Hybrid split | reasoning executors return no handoff; mechanical return `LongOpSpec` (timeout≥240, log `/tmp/opencode`, cleanup set); retest conditional |
| Unit | Deny-first | no executor + no mock → `AuthorityViolationError`; mock path intact |
| Integration | Sync contract | allowlist includes `guardian-orchestrator.md`; `guardian.md`/`orchestrator.md` untouched; parity |
| Integration | Flow integrity | `assert_flow` still 14 phases; run-flow gates unchanged |
| E2E | Routing | live `orchestrator.md` GUARDIAN-LIVE row; opencode.json entry mode primary deny-first |
| E2E | Gate fail-closed | `HUMAN_APPROVE_REPLACEMENT`: approve → allow; HOLD/missing → block (decisions-file pattern) |

## Threat Matrix

| Boundary | Applicability | Design response | Planned RED tests |
|---|---|---|---|
| Documentation-like paths | **Applicable** — sync allowlist is the prompt classification boundary; `phase_runner.py` is an executable classification boundary | Allowlist = 3 managed families; runner rejects non-`PHASES` phase ids and malformed directive JSON before any execution | Allowlist classification tests (updated); runner unknown-phase/malformed-JSON tests |
| Git repository selection | N/A — no VCS work in this change | — | — |
| Commit state | N/A | — | — |
| Push state | N/A | — | — |
| PR commands | N/A | — | — |

## Migration / Rollout

1. **F1**: add registry + executors + `phase_runner` (mock mode green); delete `_run_campaign.py` + docs note (sweep clean — no deprecation window needed).
2. **F2**: edit 14 prompts; extend allowlist; update sync tests in the same change; run `sync_prompts.py` to push live copies.
3. **F3**: create repo prompt; apply edits live `opencode.json` + `orchestrator.md`; sync `guardian-orchestrator.md`; parity tests verify. Rollback: remove JSON entry + routing row + revert allowlist/tests.

## Open Questions

- None blocking. Note: `HUMAN_APPROVE_REPLACEMENT` lives guardian-domain (D9) — confirm reviewers accept non-pipeline gate placement.
