# Archive Report — orchestrated-subagent-wiring

**Change**: `orchestrated-subagent-wiring`
**Archived**: 2026-08-15
**Artifact store**: openspec + engram (hybrid)
**Branch**: `feat/per-phase-subagent-delegation-pr5`

---

## Final State Summary

All 18 implementation tasks are complete across 3 work units (WU1+WU2+WU3). The change has been verified: 208/208 tests pass, 14/14 requirements compliant, 32/32 scenarios compliant, 0 blockers, 0 criticals. Verification verdict: **PASS WITH WARNINGS** (one pre-existing baseline failure).

### Verification Evidence

| Metric | Value |
|--------|-------|
| Focused test command | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/test_delegation.py tests/campaign/test_phase_runner.py tests/campaign/test_prompt_sync.py tests/test_orchestrator_prompt.py tests/gates/test_run_flow_gates.py` |
| Focused test result | 154 passed, 1 warning |
| Build test command | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign tests/gates tests/test_orchestrator_prompt.py` |
| Build test result | 208 passed, 1 warning |
| Requirements | 14/14 |
| Scenarios | 32/32 |
| Blockers | 0 |
| Criticals | 0 |

### Commit Evidence

| WU | Commits | Description |
|----|---------|-------------|
| WU1 | `2a32aed`, `e1875b6`, `6e85c65` | F1: production executor registry + hybrid delegation + phase_runner CLI + `_run_campaign.py` retirement |
| WU2 | `e4c81ed`, `ca069e1`, `4a52cb6`, `6b0a20e` | F2: sync contract flip + allowlist extension + 14-prompt enrichment + apply-progress record |
| WU3 | Uncommitted working-tree changes | F3: guardian-orchestrator prompt + live opencode.json + orchestrator.md routing + replacement gate tests |

**Note on WU3 commits**: WU3 tasks (3.1–3.7) are complete and verified in the working tree, but were not committed before archive. The uncommitted state is recorded here as the terminal state of the change. A future session should commit WU3 changes to preserve the full history.

### Artifact List

| Artifact | Path | State |
|----------|------|-------|
| Proposal | `openspec/changes/orchestrated-subagent-wiring/proposal.md` | Present |
| Spec (delta) | `openspec/changes/orchestrated-subagent-wiring/spec.md` | Present (synced to main specs) |
| Design | `openspec/changes/orchestrated-subagent-wiring/design.md` | Present |
| Tasks | `openspec/changes/orchestrated-subagent-wiring/tasks.md` | Present, 18/18 complete |
| Apply progress | `openspec/changes/orchestrated-subagent-wiring/apply-progress.md` | Present (WU1+WU2+WU3) |
| Verify report | `openspec/changes/orchestrated-subagent-wiring/verify-report.md` | Present, PASS WITH WARNINGS |

### Synced Main Specs

The following main specs were updated from the delta:

| Domain | Action | Details |
|--------|--------|---------|
| `campaign-phase-delegation` | Updated | REQ-803 modified (deny-first mock + long-running script); REQ-815/816/817/818 added |
| `campaign-phase-agents` | Updated | REQ-806 modified (`guardian-orchestrator.md` managed); REQ-819/820/821 added |
| `guardian-agent` | Updated | REQ-642 modified (both orchestrators route guardian intents) |
| `phase-runner` | Created | New spec from delta section |
| `guardian-orchestrator` | Created | New spec from delta section |

---

## Work-Unit Evidence Summary

### WU1 — F1: Real Runner Wiring

**Focused test command**:
```bash
SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/test_delegation.py tests/campaign/test_phase_runner.py
```
**Result**: 61 passed, 1 warning in 1.85s

**Broader test command**:
```bash
SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign tests/gates
```
**Result**: 142 passed

**Runtime harness**:
```bash
python3 sdk/quantlab/campaign/phase_runner.py --phase <name> --directive '<json>'
```
- `research` → success envelope (`research_llm`)
- `dispatch` → `LongOpSpec` handoff + `/tmp/opencode/dispatch.report.md` written
- Error paths exit 1 with JSON envelope (unknown phase / malformed JSON / forbidden scope `mutate flow.py`)

### WU2 — F2: Prompt Enrichment + Sync

**Focused test command**:
```bash
SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign/test_prompt_sync.py
```
**Result**: 12 passed (baseline 11; +1 new `test_guardian_orchestrator_allowlisted`)

**Broader test command**:
```bash
SQX_FORCE_MOCK=1 python3 -m pytest -q tests/campaign
```
**Result**: 101 passed, 1 warning

**Runtime harness**:
```bash
python3 ai/opencode/sync_prompts.py
```
- `updated (14): phase-archive.md … phase-review.md` (live copies pushed)
- `python3 ai/opencode/sync_prompts.py --check` → `parity ok` (exit 0)

### WU3 — F3: Guardian-Orchestrator

**Focused test command**:
```bash
SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/test_orchestrator_prompt.py tests/gates/test_run_flow_gates.py tests/campaign
```
**Result**: 208 passed, 1 warning

**Broader test command**:
```bash
SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/campaign tests/gates tests/test_orchestrator_prompt.py tests/guardian
```
**Result**: 258 passed

**Runtime harness**:
```bash
python3 ai/opencode/sync_prompts.py
```
- `updated (1): guardian-orchestrator.md`
- `python3 ai/opencode/sync_prompts.py --check` → `parity ok` (exit 0)

---

## Rollback Boundary Notes

### WU1 Rollback

All WU1 changes are confined to:
- `sdk/quantlab/campaign/delegation.py`
- `sdk/quantlab/campaign/__init__.py`
- `sdk/quantlab/campaign/phase_runner.py` (new)
- `_run_campaign.py` (deleted — recoverable via `git restore --source=<parent> _run_campaign.py` or revert of commit `6e85c65`)
- `README.md` (migration note)

**Rollback command**: Revert commits `2a32aed`, `e1875b6`, `6e85c65` (or `git revert` the range). This restores the pre-WU1 tree.

### WU2 Rollback

WU2 changes are confined to:
- `ai/opencode/sync_prompts.py` (allowlist change)
- `ai/opencode/agents/phase-*.md` (14 prompts enriched)
- `tests/campaign/test_prompt_sync.py` (contract tests)
- Live copies under `~/.config/opencode/prompts/quantlab/phase-*.md`

**Rollback command**: Revert commits `e4c81ed`, `ca069e1`, `4a52cb6`. Re-run `python3 ai/opencode/sync_prompts.py` to restore live bytes to repo canonical. Live copies are regenerable from repo canonical (REQ-806).

### WU3 Rollback

WU3 changes are confined to:
- `ai/opencode/agents/guardian-orchestrator.md` (new managed prompt)
- `~/.config/opencode/opencode.json` (live agent entries)
- `~/.config/opencode/prompts/quantlab/orchestrator.md` (live routing row)
- `tests/test_orchestrator_prompt.py` (1 test fix + contract tests)
- `tests/gates/test_run_flow_gates.py` (6 new replacement-gate tests)
- `openspec/config.yaml` (context update, tracked)

**Rollback command for code/tests**: Revert the uncommitted WU3 changes or reset to the last WU2 commit. For live config:
- `~/.config/opencode/opencode.json`: remove `guardian-orchestrator`, `quantlab-guardian-alert`, `quantlab-replacement` entries; remove them from `quantlab-orchestrator` task allowlist.
- `~/.config/opencode/prompts/quantlab/orchestrator.md`: remove the GUARDIAN-LIVE routing row.
- `~/.config/opencode/prompts/quantlab/guardian-orchestrator.md`: will be regenerated from repo canonical on next sync; deleting the live file is safe because it is a managed prompt.

---

## Live Config Parity

The following live config files are outside VCS and parity is enforced by tests:

| Live Config | Repo Canonical | Parity Test |
|-------------|----------------|-------------|
| `~/.config/opencode/opencode.json` | N/A (JSON entry shape pinned by tests) | `tests/test_orchestrator_prompt.py` asserts entry shape (mode primary, deny-first perms, prompt ref) |
| `~/.config/opencode/prompts/quantlab/orchestrator.md` | N/A (non-managed, routing row only) | `tests/test_orchestrator_prompt.py` asserts GUARDIAN-LIVE routing row |
| `~/.config/opencode/prompts/quantlab/guardian-orchestrator.md` | `ai/opencode/agents/guardian-orchestrator.md` | `tests/campaign/test_prompt_sync.py` asserts byte-equality via `sync_prompts.py --check` |

The sync script `ai/opencode/sync_prompts.py` is the ONLY update path for managed prompts. Hand-editing live prompts is not permitted.

---

## Known Risks Carried Forward

1. **Pre-existing baseline failure**: `campaign run-flow` mock loop fails at the research stage with `ValueError: Cannot determine market from objective: 'Research'` because `ResearchAgent._parse_objective` requires explicit market context. Proven pre-existing at HEAD via a clean worktree. Not introduced by this change; WU1/F1 code is not on the run-flow path yet (F2/F3 wiring is later work). File: `quantlab/pipeline/stages/research_stage.py` (baseline).

2. **WU3 uncommitted state**: WU3 changes (guardian-orchestrator prompt, live JSON wiring, replacement gate tests) are present in the working tree but were not committed before archive. The full change history is preserved only for WU1+WU2. A future session should commit WU3 to complete the git history.

3. **Live config outside VCS**: `~/.config/opencode/opencode.json` and `~/.config/opencode/prompts/quantlab/orchestrator.md` are outside VCS. Parity is test-driven, but any manual edit to these files would break the contract without a VCS record.

---

## Maintenance Notes

- `PHASES` remains at 14. No new pipeline stages were added.
- `guardian-orchestrator` is a second first-class orchestrator, NOT a phase inside `quantlab-orchestrator`.
- `HUMAN_APPROVE_REPLACEMENT` lives in the guardian domain (decision-file protocol), not in the run-flow pipeline gate loop.
- `_run_campaign.py` is retired. The only real campaign entry point is `cmd_campaign_run_flow` (`campaign run-flow`).
- All 14 phase agents retain `edit:false, write:false`. Artifact writes happen in SDK stages via `phase_runner`/`execute_phase`.

---

## Observation References

Files read during this archive phase (traceability):
- `openspec/changes/orchestrated-subagent-wiring/spec.md`
- `openspec/changes/orchestrated-subagent-wiring/design.md`
- `openspec/changes/orchestrated-subagent-wiring/tasks.md`
- `openspec/changes/orchestrated-subagent-wiring/apply-progress.md`
- `openspec/changes/orchestrated-subagent-wiring/verify-report.md`
