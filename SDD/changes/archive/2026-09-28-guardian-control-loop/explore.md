# Exploration: guardian-control-loop

## Current State

QuantLab AI uses a 14-phase campaign lifecycle with a `MetaGuardianOrchestrator` that coordinates six guardian types (market, risk, portfolio, capital, quality, execution) through a `PortfolioState` state machine. The guardian evaluation runs as `GuardianEvaluationStage` in the multi-agent pipeline, immediately before `BuilderStage`. However, the guardians are fed by optional data providers that silently degrade to `_NullDataProvider` when absent, the state machine lacks enforcement hooks, risk configuration is not mapped to CFX serialization, templates are static, campaign metrics are not wired back into guardian feedback, and there is no structured correction channel from guardian evaluation to builder.

## Affected Areas

- `sdk/quantlab/pipeline/stages/agent_stages.py:379-383` — `_NullDataProvider` pass-through returns empty dicts for any attribute, allowing guardians to score against no data.
- `sdk/quantlab/pipeline/stages/agent_stages.py:342-376` — `_build_guardians` injects `_NullDataProvider()` as fallback for `RiskGuardian`, `PortfolioGuardian`, `CapitalGuardian`, `QualityGuardian`, and `ExecutionGuardian`.
- `sdk/quantlab/pipeline/stages/agent_stages.py:280-296` — `GuardianEvaluationStage` declares `requires: ["research_config"]` and `provides: ["guardian_state", "portfolio_state"]`, but `BuilderStage` (line 52-68) only requires `research_config`; portfolio state is not enforced as a gate.
- `sdk/quantlab/guardian/orchestrator.py:20-251` — `MetaGuardianOrchestrator` accepts optional `action_hooks` (line 24) but never validates or blocks pipeline flow; `_execute_state_transition` only logs and calls hooks (line 194-210).
- `sdk/quantlab/guardian/models.py:39-45` — `PortfolioState` enum defines `NORMAL`, `VIGILANCE`, `DEFENSIVE`, `QUARANTINE`, `RECOVERY` but has no enforcement contract.
- `sdk/quantlab/pipeline/config/models.py:78-88` — `RiskConfig` defines typed fields (`max_portfolio_drawdown`, `kelly_fraction_cap`, etc.) but is never mapped to CFX `risk_money_mgmt` XML keys.
- `sdk/quantlab/cfx/models.py:505-538` — `BuildTask.risk_money_mgmt` is a generic `SettingsSection | None` (line 511); no typed bridge exists.
- `sdk/quantlab/customproject/templates.py:24-419` — `TemplateParams` exposes only `name`, `databanks`, and `filters`; templates are hardcoded class methods with fixed task lists.
- `sdk/quantlab/guardian/feedback.py:26-108` — `FeedbackRecord` and `FeedbackSignals` exist for live demo feedback, but are not consumed by pre-builder guardian evaluation.
- `sdk/quantlab/knowledge/store.py:1385-1526` — `TimeSeriesStore` persists monitor metrics, but no guardian-facing query API or feedback loop reads from it.
- `sdk/quantlab/guardian/risk.py:80-95` — `_get_risk_metrics` uses `getattr(self.portfolio_data, 'get_risk_metrics', lambda: {...})()` with hardcoded mock values (line 88-95).

## Approaches

1. **Hard-fail on missing providers** — Remove `_NullDataProvider`, require concrete provider injection, and let guardian construction fail fast when data sources are absent.
   - Pros: Eliminates silent scoring on empty data; forces wiring of real collectors.
   - Cons: Breaks existing pipeline runs that rely on passive fallback; requires provider availability guarantees.
   - Effort: Low-Medium

2. **Typed RiskConfig → CFX mapper** — Introduce a `RiskConfigMapper` that serializes `RiskConfig` fields into `BuildTask.risk_money_mgmt` settings with known SQX XML keys.
   - Pros: Single source of truth for risk limits; typed validation before CFX generation.
   - Cons: Requires reverse-engineering or documenting SQX `RiskMoneyManagement` key schema; risk of mismatched semantics.
   - Effort: Medium

3. **PortfolioState gate interceptor** — Insert a `GateInterceptorStage` (or extend existing gate pattern) after `GuardianEvaluationStage` that blocks `BuilderStage` when `portfolio_state` is `QUARANTINE` or `DEFENSIVE` without override.
   - Pros: Reuses existing gate/human-approve pattern; minimal new machinery.
   - Cons: Requires human-gate discipline; may slow iteration if over-blocked.
   - Effort: Low

4. **Adaptive template selector** — Add a `TemplateSelector` that chooses or mutates `CustomProject` tasks based on `PortfolioState` (e.g., skip `Optimize` in `QUARANTINE`, add `AutomaticRetest` in `VIGILANCE`).
   - Pros: Directly ties template topology to portfolio health; keeps templates declarative.
   - Cons: Template mutation logic can become complex; risk of non-deterministic campaign shapes.
   - Effort: Medium

5. **CorrectionBus (event-based)** — Introduce a lightweight in-process event bus where `GuardianEvaluationStage` publishes `CorrectionEvent` (risk deltas, state transitions) and `BuilderStage` subscribes to adjust CFX parameters before dispatch.
   - Pros: Decouples guardian from builder; extensible for future stages.
   - Cons: Adds new abstraction; overkill if only one consumer exists today.
   - Effort: Medium-High

6. **Guardian feedback persistence layer** — Extend `TimeSeriesStore` or add a `CampaignMetricsStore` that writes guardian scores, portfolio state transitions, and risk metrics per campaign run; expose read API for next-cycle research.
   - Pros: Enables data-driven guardian tuning and adaptive templates.
   - Cons: Storage and query design effort; migration path for existing runs.
   - Effort: Medium-High

## Recommendation

Execute in two slices:

- **Slice A (structural integrity):** Remove `_NullDataProvider`, require typed providers, add `PortfolioState` gate enforcement via existing gate interceptor pattern, and introduce typed `RiskConfig` → CFX mapping. These are correctness fixes that shrink the system (delete fallback code, enforce real contracts).
- **Slice B (adaptive behavior):** Add `CorrectionBus` between guardian evaluation and builder, introduce adaptive template selection driven by portfolio state, and persist real campaign metrics for guardian consumption. These extend behavior but build on Slice A's contracts.

## Risks

- Removing `_NullDataProvider` will break local test runs and mock-based CI paths that depend on passive guardians; tests must be updated in lockstep.
- `RiskConfig` → CFX mapping assumes SQX `RiskMoneyManagement` XML keys are stable; version drift could deserialize silently.
- Adaptive templates risk non-reproducible campaign topologies; template mutation must be deterministic and logged.
- A new `CorrectionBus` may introduce circular dependencies if `BuilderStage` also publishes events back to guardians.
- Guardian feedback persistence may grow unbounded without retention policies.

## Ready for Proposal

Yes. The orchestrator should proceed to `sdd-propose` with two slices: Slice A (NullDataProvider removal, PortfolioState gate enforcement, RiskConfig→CFX mapping) and Slice B (CorrectionBus, adaptive templates, campaign metrics persistence). Non-goals for this change: do not alter the 14-phase flow order, do not introduce new human gates beyond enforcing existing portfolio-state transitions, and do not replace the existing `FeedbackRecord` live-demo mechanism.
