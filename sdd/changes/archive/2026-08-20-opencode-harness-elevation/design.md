# Design: OpenCode Harness Elevation

## Technical Approach

Map the 9 delta specs to 5 work units: (a) sync extension + test flips + thin skills + deploy/monitor retirement, (b) repo-root AGENTS.md, (c) campaign contract + gatekeeper + lossless gates, (d) review lifecycle docs, (e) model assignments. Reuse `sync_prompts.py` patterns for the sibling `sync_skills.py`; codify existing `campaign.md`/`guardian-orchestrator.md` discipline as explicit algorithms and prompt blocks.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|---|---|---|---|
| Sync sibling | `sync_skills.py` mirrors `sync_prompts.py` exactly | Single parameterized script, Go installer only | Keeps Python parity for `--dry-run`/`--check`/allowlist/retirement; Go installer is atomic but lacks parity mode |
| Shared helper | `ai/opencode/sync_common.py` with `SyncDriver` class | Copy-paste, procedural duplication | Single source of idempotency/determinism/byte-equality logic; both scripts instantiate with their own dirs/allowlists |
| Retired prompt retirement | Sync actively deletes retired names from live | Leave stale copies, manual cleanup | Spec requires `deploy.md`/`monitor.md` absent from live after sync (REQ-806 scenario) |
| Skill dedup | `quantlab-run-campaign` SKILL.md becomes orchestrator gate + executor override + files list + pointer | Keep full text in two places | Proposal D3: canonical `campaign.md`, skill deduped to pointer |
| Model merge | Repo `opencode.json` `agents.<name>.model` per agent | Global `model` key, single `default_agent` model | OpenCode merges partial agent blocks over global config; per-agent block is the documented override path |

## Data Flow

    repo ai/opencode/agents/*.md ──→ sync_prompts.py ──→ ~/.config/opencode/prompts/quantlab/
    repo ai/opencode/skills/*/SKILL.md ──→ sync_skills.py ──→ ~/.config/opencode/skills/
                                                         │
    retire deploy.md/monitor.md ──→ active deletion from live ──→ no stale copies
                                                         │
    opencode.json agents.<name>.model ──→ OpenCode merge ──→ per-agent model override

## File Changes

| File | Action | Description |
|---|---|---|
| `ai/opencode/sync_common.py` | Create | Shared `SyncDriver(repo_dir, live_dir, managed_names, retired_names)` with `sync()`, `check()`, `_cleanup_retired()` |
| `ai/opencode/sync_prompts.py` | Modify | Add `orchestrator.md` to managed allowlist; remove `deploy.md`/`monitor.md` from non-managed comment; import `SyncDriver` from `sync_common` |
| `ai/opencode/sync_skills.py` | Create | Sibling deterministic idempotent sync for `ai/opencode/skills/` → `~/.config/opencode/skills/` with same `--dry-run`/`--check`; allowlist all `quantlab-*` skills |
| `ai/opencode/agents/orchestrator.md` | Create | Versioned router prompt bound to `agent.quantlab-orchestrator` |
| `ai/opencode/agents/deploy.md` | Create | Retired legacy prompt (minimal redirect to skill) |
| `ai/opencode/agents/monitor.md` | Create | Retired legacy prompt (minimal redirect to skill) |
| `ai/opencode/agents/campaign.md` | Modify | Add post-phase gatekeeper loop; add lossless gate protocol section |
| `ai/opencode/agents/guardian-orchestrator.md` | Modify | Add lossless replacement gate discipline |
| `ai/opencode/agents/phase-*.md` (15) | Modify | Add lossless gate section to each phase prompt |
| `ai/opencode/skills/quantlab-run-campaign/SKILL.md` | Modify | Restore preflight parity; dedupe to frontmatter + gates + executor override + pointer to `campaign.md` |
| `ai/opencode/skills/quantlab-deploy-strategy/SKILL.md` | Create | LLM-first rewrite absorbing retired `deploy.md` content |
| `ai/opencode/skills/quantlab-monitor-status/SKILL.md` | Create | LLM-first rewrite absorbing retired `monitor.md` content |
| `AGENTS.md` | Create | Repo-root technical English contract: stack, testing, harness conventions, OpenSpec workflow |
| `docs/guides/review-lifecycle.md` | Create | 4R consent envelope, stop-reason table, `repair --preflight` reference |
| `opencode.json` | Modify | Add `agents.<name>.model: "opencode/deepseek-v4-flash-free"` for all 19 QuantLab agents |
| `tests/campaign/test_prompt_sync.py` | Modify | Flip allowlist assertions for `orchestrator.md` managed; add retired-file cleanup tests; add skills-sync parity tests |

## Interfaces / Contracts

### SyncDriver (sync_common.py)

```python
class SyncDriver:
    def __init__(self, repo_dir: Path, live_dir: Path,
                 managed_names: Callable[[Path], list[str]],
                 retired_names: tuple[str, ...]) -> None: ...

    def sync(self, *, dry_run: bool = False) -> list[str]: ...
    def check(self) -> list[str]: ...
```

### Result Contract (envelope, unchanged)

```json
{
  "status": "success | failed | partial",
  "executive_summary": "one or two sentences",
  "artifacts": ["paths or keys"],
  "next_recommended": "next phase",
  "risks": ["risk notes"]
}
```

### opencode.json agent block merge

```json
{
  "agents": {
    "quantlab-orchestrator": {"model": "opencode/deepseek-v4-flash-free"},
    "quantlab-campaign": {"model": "opencode/deepseek-v4-flash-free"}
  }
}
```

Repo partial blocks merge over global config; `default_agent` stays intact.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | `sync_common.SyncDriver` idempotency, allowlist, retired cleanup | Temp dirs; assert byte-equality, mtime preservation, retired files removed from live |
| Unit | REQ-821 boundary: `orchestrator.md` managed; `guardian.md` untouched | `test_prompt_sync.py` flipped assertions |
| Unit | `sync_skills.py --check`/`--dry-run` parity and scope | Mirror prompt-sync test structure against skills dir |
| Integration | Live parity after sync | `test_repo_campaign_matches_live_campaign` pattern extended to skills |
| E2E | Gatekeeper exactly-once re-run | Mock phase failure → re-run → second failure → halt; assert stop-and-report |

## Threat Matrix

| Boundary | Applicability | Design response | Planned RED tests |
|---|---|---|---|
| Documentation-like paths | Applicable | `orchestrator.md`, `deploy.md`, `monitor.md`, `guardian.md` are docs with special sync classification; allowlist + retired list are the boundary | Allowlist includes/excludes correct names; retired names deleted from live; non-managed `.md` never written |
| Git repository selection | N/A | No git automation in sync scripts or gatekeepers | — |
| Commit state | N/A | No VCS operations in this change | — |
| Push state | N/A | No push/PR automation | — |
| PR commands | N/A | No PR automation | — |

## Migration / Rollout

No data migration. Work unit (a) flips allowlist, tests, and skills in one commit; `--check` gate in CI ensures parity before merge. `opencode.json` model assignment is additive and backward-compatible.

## Open Questions

- [ ] **Spec conflict**: REQ-821 acceptance criteria #3 states `guardian.md`/`orchestrator.md` untouched, but REQ-821 scenarios explicitly say `orchestrator.md` is included in the managed set. Proposal and current codebase intent clearly favor `orchestrator.md` becoming managed. Confirm acceptance criteria wording is a typo and should read `guardian.md` untouched only.
- [ ] **Agent count**: Spec says "19 QuantLab agents"; `opencode.json` currently has only `default_agent`. Confirm exact agent block names to add (router + 18 delegates).
