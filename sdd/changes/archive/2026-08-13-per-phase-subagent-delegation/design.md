# Design: Per-Phase Sub-Agent Delegation

## Technical Approach

Wrap the immutable 14-phase `PHASES` (REQ-37) with a delegation layer: `quantlab-campaign` becomes a dispatcher that tasks exactly one `quantlab-phase-<phase>` subagent per phase in `PHASES` order (REQ-811), folds each `PhaseResult` (REQ-802), and bubbles long-running scripts to the orchestrator shell (REQ-809). Phase agents are deny-first leaf workers over SDK glue (`sdk/quantlab/campaign/delegation.py`) that sits ABOVE `sdk/quantlab/agents/` pipeline stages (REQ-804). Prompts are repo-canonical (`AI/opencode/agents/`) with sync + parity (REQ-806/807). Gates stay primary and fail-closed (MOD REQ-38/REQ-11).

```
flow.py PHASES (immutable) → campaign agent (dispatcher)
  → task(PhaseDirective) → phase agent → execute_phase() glue
  → PhaseResult → campaign folds → orchestrator shell (long ops only)
  → next phase ──→ sdk/quantlab/agents/ stages (research_director.build_pipeline(orchestrated=True))
```

## Architecture Decisions

| # | Decision | Options | Choice — rationale |
|---|---|---|---|
| 1 | Prompt source of truth | repo vs live | **Repo canonical** `AI/opencode/agents/` + sync + parity (REQ-806/807). Drift already diverged both ways (exploration §Current State); 14 prompts × manual sync = guaranteed drift. |
| 2 | Agent naming | `quantlab-<phase>` vs `quantlab-phase-<phase>` | **`quantlab-phase-<phase>`** — `quantlab-deploy`/`quantlab-monitor` already exist (collision); prefix still matches the `quantlab-*` task wildcard, so orchestrator/campaign allowlists need no change. |
| 3 | Prompt filenames | `<phase>.md` vs `phase-<phase>.md` | **`phase-<phase>.md`** — live `deploy.md`/`monitor.md` already exist; prefix avoids clobbering existing agents' prompts. |
| 4 | Phase-agent task authority | wildcard pattern vs leaf-only | **Pattern `{"*": "deny", "quantlab-*": "allow"}`** (REQ-808/812, mirrors campaign/guardian); prompts forbid delegation except live-ops→`quantlab-guardian`; glue enforces phase scope in code (REQ-803). |
| 5 | Prompt thickness | full vs thin | **Thin-by-reference** — role + bounded authority + phase-specific glue + pointers to campaign.md contract (gate protocol, Result Contract, long-running policy). Judgment phases (research/hypothesis/review/retest/optimize/portfolio) add phase-specific guidance (REQ-805). |
| 6 | Envelope home | campaign vs agents | **`sdk/quantlab/campaign/delegation.py`** — `PhaseResult` name already exists in `substrate/executor` and `phase4/models` (different modules/semantics); alias on import if ever co-imported. |
| 7 | Slice order | SDK-first vs prompts-first | **Prompts-first** — fix drift + sync before ×14 multiplication; glue last completes the contract (campaign.md dispatch rewrite lands with glue, slice 3). |

## Component Design

**Agent registry (opencode.json).** 14 entries `agent.quantlab-phase-<phase>`: `mode: subagent`, `prompt: {file:~/.config/opencode/prompts/quantlab/phase-<phase>.md}`, permissions `{"question": "allow", "task": {"*": "deny", "quantlab-*": "allow"}}`, `bash` deny-first allowlist scoped to `sdk/quantlab/pipeline/*` + `sdk/quantlab/campaign/*` (REQ-813). `quantlab-*` wildcards on orchestrator/campaign task lists already cover the new names — no parent permission changes. Live-ops prompt is the only one delegating (→ `quantlab-guardian`).

**Prompt files.** Repo `AI/opencode/agents/campaign.md` (Modify: merge live guardian phase-14 delegation into repo canonical, keeping REQ-104/203-205 content and the `PHASES` tuple block — `test_flow_integrity._doc_phases` parses it) + `phase-<phase>.md` ×14 (Create). Common skeleton per prompt: role; **bounded authority** (MUST NOT mutate flow.py, skip gates, run long ops, touch live trading surface unless granted); phase instructions (which SDK glue/stage to call); gate rules (question tool, fail-closed HOLD); Result Contract pointer.

**Sync script** `AI/opencode/sync_prompts.py` (Create). Deterministic (sorted allowlist `campaign.md` + `phase-*.md`, byte copy), idempotent (identical bytes → no-op), `--dry-run`/`--check` modes; never writes/deletes non-managed live files. Live destination `~/.config/opencode/prompts/quantlab/`.

**PhaseResult envelope** in `delegation.py`: `PhaseDirective(phase_id, scope, payload, previous_result)` + `PhaseResult(status, executive_summary, artifacts, next_recommended, risks, phase_id, evidence, handoff_payload)` + `PHASE_AGENTS` (derived from `PHASES` — wrap-only, REQ-804) + `execute_phase()` glue (validate ∈ PHASES → scope-check → dispatch executor → PhaseResult; out-of-scope → authority-violation result; long op → script spec in `handoff_payload`, never waits — REQ-803/809).

**Orchestrator-shell handoff.** `handoff_payload = {command, log_path, expected, timeout≥240, cleanup}`. Chain: phase agent → campaign folds → orchestrator runs `nohup` script, polls logs, cancel = task-cancel (REQ-809/814). Output feeds next `PhaseDirective.payload`.

**Human gates.** Phase agents present gates via `question` tool (AD-4 decision-file: read `{gate_id}.pending.json`, present, await `decision.json`; stdin fallback). Never auto-approve; HOLD/unanswered → PhaseResult `status≠success` → loop halts. MOD REQ-38: wire `HUMAN_APPROVE_DEMO`/`HUMAN_APPROVE_ARCHIVE` interceptors in the orchestrated pipeline (`research_director.py`, Modify); stage `pending_gate` markers already exist (`demo_stage.py:58`, `archive_stage.py`).

## Data / State Flow

Crosses the boundary per phase: `PhaseDirective` (objective, prior_context, config refs, prev result) down; `PhaseResult` up. **Stays in SDK:** campaign_id, run state, gates (`/tmp/sqx-gates/{campaign_id}/`), memory lake, artifacts — agents pass references (campaign_id + artifact keys), never full state.

## File Changes

| File | Action | Description |
|---|---|---|
| `AI/opencode/agents/campaign.md` | Modify | Merge guardian delegation; loop delegates per phase (dispatch rewrite in slice 3) |
| `AI/opencode/agents/phase-<phase>.md` ×14 | Create | Per-phase prompts (6 judgment, 8 mechanical-thin) |
| `AI/opencode/sync_prompts.py` | Create | Deterministic idempotent repo→live sync |
| `sdk/quantlab/campaign/delegation.py` | Create | `PhaseDirective`/`PhaseResult`/`PHASE_AGENTS`/`execute_phase` |
| `sdk/quantlab/campaign/__init__.py` | Modify | Re-export delegation symbols |
| `sdk/quantlab/agents/research_director.py` | Modify | Wire DEMO/ARCHIVE gate interceptors (orchestrated tail) |
| `~/.config/opencode/opencode.json` | Modify | 14 `agent.quantlab-phase-*` entries (external, test-asserted) |
| `~/.config/opencode/prompts/quantlab/orchestrator.md` | Modify | REQ-814 phase-routing note (live-only, test-asserted) |
| `tests/campaign/test_prompt_sync.py` | Create | Sync idempotency, parity, allowlist classification |
| `tests/campaign/test_delegation.py` | Create | Envelope/directive/glue/authority/long-op/registry/integrity |
| `tests/test_orchestrator_prompt.py` | Modify | Extend (never replace): 14 registrations, routing note |

## Interfaces / Contracts

```python
@dataclass(frozen=True)
class PhaseDirective:
    phase_id: str            # MUST be in PHASES (REQ-801) else phase-not-found error
    scope: str               # bounded authority label
    payload: dict            # campaign context refs (campaign_id, artifacts, prior_context)
    previous_result: PhaseResult | None

@dataclass(frozen=True)
class PhaseResult:
    status: str              # success | failed | partial — != success halts folding (REQ-802)
    executive_summary: str
    artifacts: list[str]
    next_recommended: str
    risks: list[str]
    phase_id: str
    evidence: dict           # per-phase evidence for audit
    handoff_payload: dict | None  # {command, log_path, expected, timeout>=240, cleanup} (REQ-809)

PHASE_AGENTS: dict[str, str]   # derived from PHASES → "quantlab-phase-<phase>" (REQ-805/804)

def execute_phase(directive: PhaseDirective, *, executor: Callable | None = None) -> PhaseResult: ...
```

## Testing Strategy

| Layer | What | How |
|---|---|---|
| Unit | envelope schema, directive validation, registry==PHASES, glue authority, long-op script-return | `tests/campaign/test_delegation.py` (`SQX_FORCE_MOCK=1`) |
| Unit | sync idempotency, parity byte-equality, non-managed files ignored | `tests/campaign/test_prompt_sync.py` |
| Unit | flow integrity unchanged (REQ-804), doc PHASES parse | existing `test_flow_integrity.py` + registry derivation |
| Integration | 14 deny-first registrations, routing note, dispatch order | extend `tests/test_orchestrator_prompt.py` (exact-path asserts untouched — REQ-810) |
| E2E | full-loop dispatch order, mock-vs-real | existing campaign suite + `assert_flow`/`assert_flow_segments` (extend, REQ-810) |

## Threat Matrix

| Boundary | Applicability | Design response | Planned RED tests |
|---|---|---|---|
| Documentation-like paths (executable Markdown = agent prompts) | **Applicable** — prompt files are executable instructions; sync allowlist is the classification boundary | Sync copies only `campaign.md` + `phase-*.md`; never copies/deletes other live files; parity test enforces byte identity | `test_prompt_sync.py`: sync ignores non-managed live files (guardian.md untouched); drift names file |
| Git repository selection | N/A — no `git -C`/path handling in this change | — | — |
| Commit state | N/A — no commit automation in this change | — | — |
| Push state | N/A — no push automation in this change | — | — |
| PR commands | N/A — slicing is delivery-strategy, not code in this change | — | — |
| Agent task-routing (supplementary) | **Applicable** — REQ-811/814 | Dispatch order == `PHASES`; orchestrator never routes phase intents directly | `test_delegation.py` registry order; `test_orchestrator_prompt.py` routing-note assert |
| Shell/subprocess long-running (supplementary) | **Applicable** — REQ-809 | Glue returns script spec, never waits; prompt asserts "MUST NOT wait"; cancel = task-cancel | `test_delegation.py` long-op no-wait; prompt text asserts |

## Migration / Rollout

No data migration; `flow.py` untouched. Chain: slice 1 → 2 → 3 (stacked-to-main). Per-slice git revert; sync revert restores live prompts (rollback plan).

## Slice Plan (auto-chain, 3 slices)

| Slice | Files | ~Lines | Acceptance |
|---|---|---|---|
| 1 — prompt source + sync + parity | campaign.md (merge), sync_prompts.py, test_prompt_sync.py | ~220 | Sync deterministic + idempotent; parity byte-equal; guardian delegation in repo copy; existing flow/prompt tests green |
| 2 — registry + prompts + routing | 14 phase prompts, opencode.json, orchestrator.md, test_orchestrator_prompt.py extends | ~700–880 (budget risk — sdd-tasks may split 2a/2b) | 14 agents registered deny-first; prompts synced + parity green; REQ-814 note present; existing asserts pass |
| 3 — envelope/glue + loop + integrity | delegation.py, campaign/__init__.py, campaign.md loop rewrite, research_director.py gates, test_delegation.py | ~450 | Envelope validated; unknown phase rejected; authority violation; long-op returns script; PHASE_AGENTS==PHASES; flow asserts pass; SQX_FORCE_MOCK intact |

## Open Questions

- [ ] Judgment-phase prompts: embed concrete SDK call examples or rely on glue docs? (token cost vs. agent accuracy — decide in sdd-tasks)
- [ ] Whether `delegation.py` should expose a `validate_phase_result()` used by the campaign fold step (recommended) — confirm in tasks.
