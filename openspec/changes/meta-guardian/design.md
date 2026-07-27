# Design: MetaGuardian for QuantLab AI

## Overview

The MetaGuardian is a governance layer with 6 independent guardian modules coordinated by an orchestrator with a state machine.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MetaGuardian Orchestrator                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────┐ ┌────────────┐ ┌──────────────┐              │
│  │  Market     │ │   Risk     │ │  Portfolio   │              │
│  │  Guardian   │ │  Guardian  │ │  Guardian    │              │
│  └──────┬─────┘ └──────┬─────┘ └──────┬───────┘              │
│         │               │              │                        │
│  ┌──────▼─────┐ ┌──────▼─────┐ ┌──────▼───────┐              │
│  │ Capital     │ │  Quality   │ │  Execution   │              │
│  │ Guardian    │ │  Guardian  │ │  Guardian    │              │
│  └──────┬─────┘ └──────┬─────┘ └──────┬───────┘              │
│         │               │              │                        │
│         └───────────────▼──────────────┘                        │
│                         │                                       │
│                  ┌──────▼──────┐                                │
│                  │  State Machine│                               │
│                  │  NORMAL →     │                               │
│                  │  VIGILANCE →   │                               │
│                  │  DEFENSIVE →   │                               │
│                  │  QUARANTINE →  │                               │
│                  │  RECOVERY →    │                               │
│                  │  NORMAL        │                               │
│                  └──────────────┘                                │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Per-Strategy State Machine                              │  │
│  │  ACTIVE → MONITORING → DEGRADING → REPLACEMENT_PENDING  │  │
│  │  → RETIRED                                               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. models.py — Guardian Types + State Enums

```python
from enum import Enum
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class GuardianType(str, Enum):
    MARKET = "market"
    RISK = "risk"
    PORTFOLIO = "portfolio"
    CAPITAL = "capital"
    QUALITY = "quality"
    EXECUTION = "execution"

class GuardianStatus(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"

class GuardianResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    guardian_type: GuardianType
    status: GuardianStatus
    score: float = Field(ge=0.0, le=1.0)
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)

class PortfolioState(str, Enum):
    NORMAL = "NORMAL"
    VIGILANCE = "VIGILANCE"
    DEFENSIVE = "DEFENSIVE"
    QUARANTINE = "QUARANTINE"
    RECOVERY = "RECOVERY"

class StrategyState(str, Enum):
    ACTIVE = "ACTIVE"
    MONITORING = "MONITORING"
    DEGRADING = "DEGRADING"
    REPLACEMENT_PENDING = "REPLACEMENT_PENDING"
    RETIRED = "RETIRED"

class MetaGuardianConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    weights: dict[GuardianType, float] = Field(default_factory=lambda: {
        GuardianType.MARKET: 0.15,
        GuardianType.RISK: 0.30,
        GuardianType.PORTFOLIO: 0.20,
        GuardianType.CAPITAL: 0.15,
        GuardianType.QUALITY: 0.10,
        GuardianType.EXECUTION: 0.10,
    })
    thresholds: dict[str, float] = Field(default_factory=lambda: {
        "defensive_drawdown": 0.10,
        "quarantine_drawdown": 0.20,
        "recovery_drawdown": 0.05,
        "degradation_checks": 3,
        "retirement_checks": 5,
    })
```

### 2. guardians/base.py — Base Guardian

```python
class BaseGuardian(ABC):
    @abstractmethod
    def check(self) -> GuardianResult:
        """Run the guardian check and return a result."""
        ...

    @abstractmethod
    def guardian_type(self) -> GuardianType:
        """Return the type of this guardian."""
        ...
```

### 3. guardians/market.py — MarketGuardian

```python
class MarketGuardian(BaseGuardian):
    def __init__(self, regime_collector, cost_collector):
        self.regime_collector = regime_collector
        self.cost_collector = cost_collector

    def check(self) -> GuardianResult:
        regime = self.regime_collector.collect("portfolio")
        costs = self.cost_collector.collect_all(["EURUSD", "GBPUSD"])
        # Compute composite score from regime, volatility, liquidity, session
        score = self._compute_score(regime, costs)
        status = self._score_to_status(score)
        return GuardianResult(guardian_type=GuardianType.MARKET, status=status, score=score, message=...)
```

### 4. guardians/risk.py — RiskGuardian

```python
class RiskGuardian(BaseGuardian):
    def check(self) -> GuardianResult:
        drawdown = self._compute_drawdown()
        sharpe = self._compute_sharpe()
        exposure = self._compute_exposure()
        kelly = self._compute_kelly()
        score = self._weighted_score(drawdown, sharpe, exposure, kelly)
        ...
```

### 5. guardians/portfolio.py — PortfolioGuardian

```python
class PortfolioGuardian(BaseGuardian):
    def check(self) -> GuardianResult:
        correlations = self._compute_correlations()
        enos = self._compute_enos(correlations)
        concentration = self._compute_concentration()
        score = self._weighted_score(correlations, enos, concentration)
        ...
```

### 6. guardians/capital.py — CapitalGuardian

```python
class CapitalGuardian(BaseGuardian):
    def check(self) -> GuardianResult:
        # Dynamic capital allocation based on risk scores
        allocation = self._compute_allocation()
        score = self._score_allocation(allocation)
        ...
```

### 7. guardians/quality.py — QualityGuardian

```python
class QualityGuardian(BaseGuardian):
    def __init__(self, health_score_system):
        self.health_score_system = health_score_system

    def check(self) -> GuardianResult:
        # Reuses Health Score System from Change 1
        scores = self.health_score_system.get_all_scores()
        avg_score = sum(scores.values()) / len(scores) if scores else 0.0
        ...
```

### 8. guardians/execution.py — ExecutionGuardian

```python
class ExecutionGuardian(BaseGuardian):
    def check(self) -> GuardianResult:
        # Broker health, latency, slippage, connection
        broker_status = self._check_broker()
        latency = self._check_latency()
        slippage = self._check_slippage()
        score = self._weighted_score(broker_status, latency, slippage)
        ...
```

### 9. orchestrator.py — MetaGuardianOrchestrator

```python
class MetaGuardianOrchestrator:
    def __init__(self, config: MetaGuardianConfig, guardians: list[BaseGuardian]):
        self.config = config
        self.guardians = guardians
        self.state = PortfolioState.NORMAL
        self.strategy_states: dict[str, StrategyState] = {}

    def evaluate(self) -> PortfolioState:
        results = [g.check() for g in self.guardians]
        aggregated = self._aggregate(results)
        new_state = self._transition_state(aggregated)
        if new_state != self.state:
            self._fire_hooks(self.state, new_state)
            self.state = new_state
        return self.state

    def _aggregate(self, results: list[GuardianResult]) -> float:
        total = sum(r.score * self.config.weights[r.guardian_type] for r in results)
        return total / sum(self.config.weights.values())

    def _transition_state(self, score: float) -> PortfolioState:
        if score >= 0.7:
            return PortfolioState.NORMAL
        elif score >= 0.5:
            return PortfolioState.VIGILANCE
        elif score >= 0.3:
            return PortfolioState.DEFENSIVE
        else:
            return PortfolioState.QUARANTINE

    def _fire_hooks(self, old_state: PortfolioState, new_state: PortfolioState):
        # Trigger configured actions on state transition
        ...
```

### 10. __init__.py

```python
from quantlab.guardian.models import (
    GuardianType, GuardianStatus, GuardianResult,
    PortfolioState, StrategyState, MetaGuardianConfig,
)
from quantlab.guardian.base import BaseGuardian
from quantlab.guardian.market import MarketGuardian
from quantlab.guardian.risk import RiskGuardian
from quantlab.guardian.portfolio import PortfolioGuardian
from quantlab.guardian.capital import CapitalGuardian
from quantlab.guardian.quality import QualityGuardian
from quantlab.guardian.execution import ExecutionGuardian
from quantlab.guardian.orchestrator import MetaGuardianOrchestrator

__all__ = [
    "GuardianType", "GuardianStatus", "GuardianResult",
    "PortfolioState", "StrategyState", "MetaGuardianConfig",
    "BaseGuardian", "MarketGuardian", "RiskGuardian",
    "PortfolioGuardian", "CapitalGuardian", "QualityGuardian",
    "ExecutionGuardian", "MetaGuardianOrchestrator",
]
```

## Integration Points

1. **Health Score System (Change 1)**: QualityGuardian consumes per-strategy health scores
2. **Auto-Costs (Change 2)**: ExecutionGuardian uses cost data
3. **Regime Classifier (Change 3)**: MarketGuardian uses regime classification
4. **DSL Translator**: MetaGuardian state can be passed to translator for regime-aware config
5. **Pipeline**: MetaGuardian.evaluate() called before each research campaign

## Testing Strategy

- Unit tests for each guardian module
- Unit tests for state machine transitions
- Unit tests for score aggregation
- Unit tests for action hooks
- Integration test: full orchestrator with mock guardians
- Per-strategy state machine tests

## Rollback Plan

Delete `sdk/quantlab/guardian/` directory and `tests/test_guardian/`.

## Workload Estimate

- models.py: ~80 lines
- base.py: ~30 lines
- market.py: ~80 lines
- risk.py: ~80 lines
- portfolio.py: ~70 lines
- capital.py: ~50 lines
- quality.py: ~40 lines
- execution.py: ~60 lines
- orchestrator.py: ~100 lines
- __init__.py: ~30 lines
- tests: ~350 lines

**Total: ~970 lines** — needs chained PR (2 PRs)