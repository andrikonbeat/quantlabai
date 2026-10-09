# Tasks: MetaGuardian Implementation

## Review Workload Forecast

| Metric | Value |
|--------|-------|
| Estimated changed lines | ~970 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Delivery strategy | Chained PRs |
| Decision needed before apply | Yes |

---

## PR 1: Core Models + Base Guardian + Market + Risk Guardians

### Task 1.1: Create guardian models
**File**: `sdk/quantlab/guardian/models.py`
- [x] GuardianType, GuardianStatus, GuardianResult enums/models
- [x] PortfolioState, StrategyState enums
- [x] MetaGuardianConfig with weights and thresholds

### Task 1.2: Create BaseGuardian
**File**: `sdk/quantlab/guardian/base.py`
- [x] Abstract base class with check() and guardian_type()

### Task 1.3: Implement MarketGuardian
**File**: `sdk/quantlab/guardian/market.py`
- [x] Consumes RegimeClassifier output
- [x] Computes volatility, liquidity, session scores
- [x] Returns GuardianResult

### Task 1.4: Implement RiskGuardian
**File**: `sdk/quantlab/guardian/risk.py`
- [x] Drawdown, Sharpe, exposure, Kelly monitoring
- [x] Returns GuardianResult

### Task 1.5: Test models, base, market, risk guardians
**File**: `sdk/tests/test_guardian/test_models.py`
**File**: `sdk/tests/test_guardian/test_market.py`
**File**: `sdk/tests/test_guardian/test_risk.py`
- [x] All tests pass

---

## PR 2: Portfolio + Capital + Quality + Execution Guardians + Orchestrator

### Task 2.1: Implement PortfolioGuardian
**File**: `sdk/quantlab/guardian/portfolio.py`
- [x] Correlation analysis, ENOS, concentration monitoring

### Task 2.2: Implement CapitalGuardian
**File**: `sdk/quantlab/guardian/capital.py`
- [x] Dynamic capital allocation

### Task 2.3: Implement QualityGuardian
**File**: `sdk/quantlab/guardian/quality.py`
- [x] Reuses Health Score System from Change 1

### Task 2.4: Implement ExecutionGuardian
**File**: `sdk/quantlab/guardian/execution.py`
- [x] Broker health, latency, slippage monitoring

### Task 2.5: Implement MetaGuardianOrchestrator
**File**: `sdk/quantlab/guardian/orchestrator.py`
- [x] State machine (NORMAL → VIGILANCE → DEFENSIVE → QUARANTINE → RECOVERY → NORMAL)
- [x] Per-strategy state machine
- [x] Action hooks on state transitions
- [x] Score aggregation with configurable weights

### Task 2.6: Test portfolio, capital, quality, execution guardians + orchestrator
**File**: `sdk/tests/test_guardian/test_portfolio.py`
**File**: `sdk/tests/test_guardian/test_capital.py`
**File**: `sdk/tests/test_guardian/test_quality.py`
**File**: `sdk/tests/test_guardian/test_execution.py`
**File**: `sdk/tests/test_guardian/test_orchestrator.py`
- [x] All tests pass

---

## PR 3: Module Structure + DSL Integration + Pipeline Integration

### Task 3.1: Create __init__.py
**File**: `sdk/quantlab/guardian/__init__.py`
- [x] Public exports for all components

### Task 3.2: DSL Translator integration
**File**: Modify `sdk/quantlab/dsl/` (existing)
- [x] Add `guardian_state` field to ResearchConfig
- [x] Translator uses guardian state to adjust Builder.cfx blocks

### Task 3.3: Pipeline integration
**File**: Modify `sdk/quantlab/pipeline/` (existing)
- [x] Add `guardian_enabled` flag to campaign config
- [x] Call MetaGuardianOrchestrator.evaluate() before Builder runs

### Task 3.4: Test DSL and pipeline integration
**File**: `sdk/tests/test_guardian/test_integration.py`
- [x] Full pipeline with guardian_enabled=true
- [x] DSL translator with guardian_state