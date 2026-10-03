"""MetaGuardianOrchestrator: coordinates all guardians and manages state machine."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Tuple

if TYPE_CHECKING:  # pragma: no cover - typing only
    from quantlab.knowledge.guardian_store import GuardianFeedbackStore

from .base import BaseGuardian
from .capital import CapitalGuardian
from .execution import ExecutionGuardian
from .models import (
    GuardianResult,
    GuardianStatus,
    GuardianType,
    MetaGuardianConfig,
    PortfolioState,
    StrategyState,
)
from .portfolio import PortfolioGuardian
from .quality import QualityGuardian
from .risk import RiskGuardian

logger = logging.getLogger(__name__)

# Guardian class -> attributes that MUST hold a concrete provider instance.
# The attribute names are the ones the guardian stores on ``self`` at
# construction time, not the constructor keyword.
REQUIRED_GUARDIAN_PROVIDERS: dict[type, tuple[str, ...]] = {
    RiskGuardian: ("portfolio_data",),
    PortfolioGuardian: ("returns_data",),
    CapitalGuardian: ("performance_data",),
    QualityGuardian: ("health_system",),
    ExecutionGuardian: ("broker",),
}


def validate_guardian_providers(guardians: list[BaseGuardian]) -> None:
    """Assert every known guardian received a concrete provider.

    Args:
        guardians: Guardian instances about to be orchestrated.

    Raises:
        GuardianProviderError: If any required provider attribute is ``None``
            or absent. There is no silent pass-through fallback.
    """
    # Deferred: quantlab.pipeline imports the stages, which import this module.
    from quantlab.pipeline.errors import GuardianProviderError

    for guardian in guardians:
        required = REQUIRED_GUARDIAN_PROVIDERS.get(type(guardian))
        if required is None:
            continue
        for provider_name in required:
            if getattr(guardian, provider_name, None) is None:
                raise GuardianProviderError(
                    f"{type(guardian).__name__} requires a concrete "
                    f"'{provider_name}' provider; got None",
                    guardian_name=type(guardian).__name__,
                    provider_name=provider_name,
                )


class MetaGuardianOrchestrator:
    """Coordinates all guardians and manages the state machine."""

    def __init__(self, config: MetaGuardianConfig, guardians: list[BaseGuardian],
                 action_hooks: list[Callable[[PortfolioState, PortfolioState], None]] | None = None,
                 feedback_store: GuardianFeedbackStore | None = None,
                 campaign_id: str | None = None,
                 correlation_id: str | None = None):
        """Initialize the orchestrator.

        Providers are injected through the guardian instances themselves; a
        guardian missing its provider aborts construction instead of degrading
        to an empty result set.

        Args:
            config: Configuration for the orchestrator
            guardians: List of guardian instances to coordinate
            action_hooks: Optional list of callables(old_state, new_state) for state transitions
            feedback_store: Optional store that receives one
                ``GuardianMetricRecord`` per guardian result on every
                ``evaluate()``. Persistence is opt-in.
            campaign_id: Campaign the metrics belong to. Required together
                with ``feedback_store``; without it nothing is written.
            correlation_id: Optional envelope/phase link recorded on every
                persisted metric.

        Raises:
            GuardianProviderError: If a guardian was built without a concrete
                provider.
        """
        validate_guardian_providers(guardians)
        self.config = config
        self.guardians = guardians
        self.action_hooks = action_hooks or []
        self.feedback_store = feedback_store
        self.campaign_id = campaign_id
        self.correlation_id = correlation_id
        self.state = PortfolioState.NORMAL
        self.state_history: list[tuple[PortfolioState, float]] = []
        self.strategy_states: dict[str, StrategyState] = {}
        self.last_evaluation_time: float = 0.0

    def evaluate(self) -> PortfolioState:
        """Evaluate all guardians and update state.

        Returns:
            PortfolioState: Current portfolio state after evaluation.
        """
        current_time = time.time()
        
        # Collect results from all guardians
        results = self._collect_guardian_results()
        
        # If no guardians, return current state
        if not results:
            return self.state
        
        # Aggregate results into a single score
        aggregated_score = self._aggregate_results(results)
        
        # Determine new state based on score and hysteresis
        new_state = self._determine_state(aggregated_score)
        
        # Check if state changed
        if new_state != self.state:
            # Record state change
            self.state_history.append((self.state, current_time))
            # Execute state transition actions
            self._execute_state_transition(self.state, new_state)
            # Update state
            self.state = new_state
        
        # Update strategy-specific states
        self._update_strategy_states(results)

        # Update last evaluation time
        self.last_evaluation_time = current_time

        # Persist this evaluation's guardian observations
        self._persist_metrics(results)
        
        return self.state

    def _persist_metrics(self, results: list[GuardianResult]) -> None:
        """Write one ``GuardianMetricRecord`` per guardian result.

        Opt-in: no store or no campaign id means no writes. Persistence is
        observability, not authority — a failing sink is logged and skipped so
        a broken metrics path can never take down the governance loop.
        """
        if self.feedback_store is None or not self.campaign_id:
            return

        # Deferred: quantlab.knowledge imports the guardian models.
        from quantlab.knowledge.guardian_store import GuardianMetricRecord

        for result in results:
            record = GuardianMetricRecord(
                campaign_id=self.campaign_id,
                timestamp=datetime.fromtimestamp(result.timestamp.timestamp()),
                guardian_name=result.guardian_type.value,
                score=result.score,
                portfolio_state=self.state,
                risk_metrics={"status": result.status.value, "message": result.message},
                correlation_id=self.correlation_id,
                source="evaluation",
            )
            try:
                self.feedback_store.write(record)
            except Exception:
                logger.exception(
                    "Failed to persist guardian metric for campaign %s", self.campaign_id
                )

    def _collect_guardian_results(self) -> list[GuardianResult]:
        """Collect results from all guardians.
        
        Returns:
            List of GuardianResult from each guardian
        """
        results = []
        for guardian in self.guardians:
            try:
                result = guardian.check()
                results.append(result)
            except Exception:
                # If a guardian fails, create a default error result
                results.append(GuardianResult(
                    guardian_type=guardian.guardian_type(),
                    status=GuardianStatus.RED,
                    score=0.0,
                    message="Guardian execution failed",
                ))
        return results

    def _aggregate_results(self, results: list[GuardianResult]) -> float:
        """Aggregate guardian results into a single score.
        
        Args:
            results: List of guardian results
            
        Returns:
            Aggregated score from 0.0 to 1.0
        """
        if not results:
            return 0.5  # Neutral if no results
        
        # Apply weights from configuration
        weighted_sum = 0.0
        total_weight = 0.0
        
        for result in results:
            weight = self.config.weights.get(result.guardian_type, 0.1)
            weighted_sum += result.score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.5
            
        return min(1.0, max(0.0, weighted_sum / total_weight))

    def _determine_state(self, score: float) -> PortfolioState:
        """Determine portfolio state based on score and hysteresis.
        
        Args:
            score: Aggregated score from 0.0 to 1.0
            
        Returns:
            Appropriate PortfolioState
        """
        # Handle case with no history (first evaluation)
        if len(self.state_history) == 0:
            if score >= 0.8:
                return PortfolioState.NORMAL
            elif score >= 0.6:
                return PortfolioState.VIGILANCE
            elif score >= 0.4:
                return PortfolioState.DEFENSIVE
            else:
                return PortfolioState.QUARANTINE
        
        # Get thresholds from config
        defensive_threshold = self.config.thresholds.get("defensive_drawdown", 0.10)
        quarantine_threshold = self.config.thresholds.get("quarantine_drawdown", 0.20)
        recovery_threshold = self.config.thresholds.get("recovery_drawdown", 0.05)
        
        # Convert thresholds to score equivalents (inverted since lower drawdown = higher score)
        # These are approximations - in reality these would be tuned based on actual data
        defensive_score = max(0.0, min(1.0, 1.0 - (defensive_threshold * 5)))  # 0.10 -> 0.5
        quarantine_score = max(0.0, min(1.0, 1.0 - (quarantine_threshold * 5)))  # 0.20 -> 0.0
        recovery_score = max(0.0, min(1.0, 1.0 - (recovery_threshold * 5)))     # 0.05 -> 0.75
        
        # Apply hysteresis based on current state
        if self.state == PortfolioState.NORMAL:
            if score <= quarantine_score:
                return PortfolioState.QUARANTINE
            elif score <= defensive_score:
                return PortfolioState.DEFENSIVE
            else:
                return PortfolioState.NORMAL
        elif self.state == PortfolioState.DEFENSIVE:
            if score <= quarantine_score * 0.8:  # Need stronger signal to go to quarantine
                return PortfolioState.QUARANTINE
            elif score >= recovery_score:  # Recovery threshold to go back to normal
                return PortfolioState.NORMAL
            else:
                return self.state  # Stay DEFENSIVE
        elif self.state == PortfolioState.QUARANTINE:
            if score >= recovery_score:  # Improvement to go to defensive
                return PortfolioState.DEFENSIVE
            else:
                return self.state  # Stay QUARANTINE
        elif self.state == PortfolioState.RECOVERY:
            if score >= defensive_score:
                return PortfolioState.NORMAL
            elif score <= quarantine_score:
                return PortfolioState.QUARANTINE
            else:
                return self.state  # Stay RECOVERY
        else:
            # Fallback to basic thresholds
            if score >= 0.8:
                return PortfolioState.NORMAL
            elif score >= 0.6:
                return PortfolioState.VIGILANCE
            elif score >= 0.4:
                return PortfolioState.DEFENSIVE
            else:
                return PortfolioState.QUARANTINE

    def _execute_state_transition(self, old_state: PortfolioState, new_state: PortfolioState) -> None:
        """Execute actions when transitioning between states.
        
        Args:
            old_state: Previous state
            new_state: New state
        """
        logger.info("Portfolio state transition: %s -> %s", old_state, new_state)
        
        # Execute configured action hooks
        for hook in self.action_hooks:
            try:
                hook(old_state, new_state)
            except Exception:
                logger.exception("Action hook failed on transition %s -> %s", old_state, new_state)

    def _update_strategy_states(self, results: list[GuardianResult]) -> None:
        """Update individual strategy states based on guardian results.
        
        Args:
            results: List of guardian results
        """
        # Extract quality guardian results for strategy-level assessment
        quality_results = [r for r in results if r.guardian_type == GuardianType.QUALITY]
        
        # In a full implementation, we would:
        # 1. Get individual strategy scores from quality guardian
        # 2. Apply strategy-specific state machine logic
        # 3. Update self.strategy_states accordingly
        # For now, we'll leave this as a placeholder

    # Public methods for inspection
    def get_current_state(self) -> PortfolioState:
        """Get current portfolio state.
        
        Returns:
            Current PortfolioState
        """
        return self.state
    
    def get_state_history(self) -> list[tuple]:
        """Get history of state changes.
        
        Returns:
            List of (state, timestamp) tuples
        """
        return self.state_history.copy()
    
    def get_strategy_states(self) -> dict:
        """Get current state of all strategies.
    
        Returns:
            Dictionary mapping strategy IDs to their states
        """
        return self.strategy_states.copy()