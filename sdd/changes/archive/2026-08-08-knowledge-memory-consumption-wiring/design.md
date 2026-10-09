# Design: Knowledge Memory Consumption Wiring (REQ-204)

## Technical Approach

Wire `KbStore.consult()` into `BuilderAgent.run()` as a pre-translation guard. After `ResearchConfig` is parsed and validated, the agent derives the active KB tabs from the config, calls `consult()` on each, and either proceeds with warnings (default) or raises `ConfigurationError` (strict mode). This closes the gap between the tested KB surface (`KbStore`) and the agent that consumes it.

## Architecture Decisions

### Decision: Integration point — pre-translation guard

**Choice**: Call `_consult_kb()` immediately after `ResearchConfig` parsing in `run()`, before `_translate()`.
**Alternatives considered**: Inside `_dispatch_with_retry()` (too late — expensive CFX already generated); inside `_translate()` (pollutes translation with side effects).
**Rationale**: Fails fast before expensive CFX generation. Keeps translation pure. Orchestrated mode still benefits because the KB check happens before dispatch is deferred.

### Decision: Tab-level consultation via empty-name fuzzy match

**Choice**: For each active tab, call `KbStore.consult(name="", tab=tab)` which fuzzy-matches all entries in the tab.
**Alternatives considered**: Add a new `tab_exists()` method to `KbStore`; inspect `list()` directly.
**Rationale**: Stays within the existing `consult()` API surface per REQ-204. Empty string fuzzy-match returns all params in the tab — sufficient to detect absence vs. presence.

### Decision: Warning-first blocking contract

**Choice**: Default mode collects `kb_warnings` and proceeds. Opt-in `strict_kb=True` raises `ConfigurationError` with missing tab context.
**Alternatives considered**: Always block (breaks existing flows); always warn (spec says "MUST emit a warning or block").
**Rationale**: Matches proposal risk mitigation. `ConfigurationError` from `quantlab.pipeline.errors` is already used for config invalidity.

## Data Flow

    ResearchConfig parsed
           │
           ▼
    _consult_kb(config)
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
 All tabs        Missing
 have entries    entries
    │             │
    ▼             ▼
 Proceed     kb_warnings list
 with          appended to
 warnings      return dict
 (default)     (strict_kb → raise)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/builder_agent.py` | Modify | Add `_consult_kb()`, `strict_kb` init param, `kb_warnings` in return dict |
| `sdk/tests/test_pr2_builder_agent.py` | Modify | Add `TestKbConsult` class with 4 spec scenarios |

## Interfaces / Contracts

```python
class BuilderAgent:
    def __init__(self, max_retries=2, timeout_minutes=60, poll_interval_seconds=30, *, strict_kb=False):
        ...

    async def run(self, context) -> dict[str, Any]:
        # Returns existing keys + optional "kb_warnings": list[str]
```

`kb_warnings` is present only when warnings are emitted. In strict mode, a missing entry raises `ConfigurationError` before any artifacts are written.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | KB hit — all tabs present | Mock `KbStore.consult` → non-empty for all active tabs; assert `kb_warnings` absent |
| Unit | Missing entry — non-strict | Mock `KbStore.consult` → empty for one tab; assert `kb_warnings` contains tab name |
| Unit | Missing entry — strict | Mock `KbStore.consult` → empty for one tab; assert `ConfigurationError` raised |
| Unit | Needs-review entry | Mock `KbStore.consult` → returns entry with `status="needs_review"`; assert warning logged, translation proceeds |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required. Default mode is non-blocking warnings. Opt into strict mode via `strict_kb=True`.

## Open Questions

- [ ] Confirm `KB_TABS` literal set in `models.py` is the authoritative source for tab names (used by `_active_kb_tabs`).
- [ ] Confirm whether `consult(name="", tab=tab)` fuzzy-match is acceptable or if we should add a dedicated `tab_has_entries()` helper.
