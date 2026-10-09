# Proposal: Guardian Control Loop

## Intent

QuantLab's guardian layer silently degrades when data providers are missing, never blocks the builder on portfolio-state transitions, cannot serialize typed risk configs to CFX, uses static templates, and lacks a feedback path from guardian evaluation to generation. This change closes those gaps.

## Scope

### In Scope
- Hard-fail on missing guardian data providers
- Typed `RiskConfig` → CFX `risk_money_mgmt` mapper
- `PortfolioState` gate enforcement after `GuardianEvaluationStage`
- Adaptive `CustomProject` template selection by portfolio state
- `CorrectionBus` event channel between guardian evaluation and builder
- Guardian feedback persistence

### Out of Scope
- 14-phase flow order (REQ-37)
- New human gates beyond existing portfolio-state transitions
- `FeedbackRecord` live-demo mechanism replacement

## Capabilities

### New Capabilities
- `correction-bus`: Lightweight in-process event bus for `CorrectionEvent`.

### Modified Capabilities
- `meta-guardian`: Enforce `PortfolioState` contracts; block `_NullDataProvider`; require concrete providers.
- `pipeline-orchestration`: Gate interceptor for portfolio-state enforcement.
- `custom-project-generator`: Adaptive templates by `PortfolioState`.
- `guardian-feedback`: Persist scores, transitions, risk metrics; expose read API.
- `knowledge-store`: Guardian-facing metrics query API.
- `cfx-editor`: Typed `RiskConfig` → `BuildTask.risk_money_mgmt` serialization.

## Approach

Two slices:
- **Slice A (structural):** Remove `_NullDataProvider`, require typed providers, enforce `PortfolioState` gate, add `RiskConfig` → CFX mapping. Deletes fallback code.
- **Slice B (adaptive):** Add `CorrectionBus`, adaptive templates, metrics persistence. Builds on Slice A.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/pipeline/stages/agent_stages.py` | Modified | Remove `_NullDataProvider`; add gate interceptor |
| `sdk/quantlab/guardian/orchestrator.py` | Modified | Enforce state transition contracts |
| `sdk/quantlab/cfx/models.py` | Modified | `risk_money_mgmt` typed bridge |
| `sdk/quantlab/customproject/templates.py` | Modified | Adaptive template selector |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Removing `_NullDataProvider` breaks mock CI paths | High | Update tests in lockstep |
| `RiskConfig` → CFX deserializes silently on SQX drift | Medium | Version-safety checks; validate against SQX 144.2953 samples |
| Adaptive templates produce non-reproducible topologies | Medium | Deterministic rules; log every mutation |
| `CorrectionBus` introduces circular dependencies | Low | Unidirectional flow; builder subscribes |

## Rollback Plan

- Slice A: Revert provider injection; restore `_NullDataProvider`.
- Slice B: Disable `CorrectionBus`; revert template selector and persistence schema.
- Each slice ships as an independent revertible unit.

## Dependencies

- Existing gate interceptor pattern (`human-gates`)
- CFX schema version safety (`cfx-editor`)
- SQX CLI readiness probe (`sqcli -h`) before CFX generation

## Success Criteria

- [ ] Pipeline fails closed when any guardian provider is absent.
- [ ] `RiskConfig` round-trips through CFX.
- [ ] `BuilderStage` blocks on `QUARANTINE` or `DEFENSIVE`.
- [ ] Templates adapt by `PortfolioState`.
- [ ] `CorrectionBus` delivers events without cycles.
- [ ] Metrics persist for next-cycle work.
