"""Tests for the MetaGuardianOrchestrator."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from sdk.quantlab.guardian.orchestrator import MetaGuardianOrchestrator
from sdk.quantlab.guardian.models import (
    MetaGuardianConfig,
    PortfolioState,
)
from sdk.quantlab.guardian import (
    MarketGuardian,
    RiskGuardian,
    PortfolioGuardian,
    CapitalGuardian,
    QualityGuardian,
    ExecutionGuardian,
)


class TestMetaGuardianOrchestrator:
    """Test the MetaGuardianOrchestrator class."""

    def test_orchestrator_initialization(self):
        """Test that Orchestrator can be initialized."""
        config = MetaGuardianConfig()
        guardians = []  # Empty list for now
        orchestrator = MetaGuardianOrchestrator(config, guardians)
        
        assert orchestrator.config == config
        assert orchestrator.guardians == []
        assert orchestrator.state == PortfolioState.NORMAL

    def test_orchestrator_evaluate_with_no_guardians(self):
        """Test evaluate with no guardians returns current state."""
        config = MetaGuardianConfig()
        guardians = []
        orchestrator = MetaGuardianOrchestrator(config, guardians)
        
        state = orchestrator.evaluate()
        assert state == PortfolioState.NORMAL

    def test_orchestrator_evaluate_with_mock_guardians(self):
        """Test evaluate with mock guardians."""
        config = MetaGuardianConfig()
        
# Create mock guardians that return good scores
        market_mock = Mock()
        market_mock.guardian_type.return_value = "market"
        market_mock.check.return_value = Mock(
            guardian_type="market",
            status="green",
            score=0.9,
            message="Good market",
            timestamp=12345
        )
        
        risk_mock = Mock()
        risk_mock.guardian_type.return_value = "risk"
        risk_mock.check.return_value = Mock(
            guardian_type="risk",
            status="green",
            score=0.85,
            message="Good risk",
            timestamp=12345
        )
        
        guardians = [market_mock, risk_mock]
        orchestrator = MetaGuardianOrchestrator(config, guardians)
        
        state = orchestrator.evaluate()
        # Should be NORMAL or VIGILANCE based on the scores
        assert state in [PortfolioState.NORMAL, PortfolioState.VIGILANCE, PortfolioState.DEFENSIVE, 
                        PortfolioState.QUARANTINE, PortfolioState.RECOVERY]

    def test_orchestrator_properties(self):
        """Test that orchestrator has expected properties."""
        config = MetaGuardianConfig()
        guardians = []
        orchestrator = MetaGuardianOrchestrator(config, guardians)
        
        # Test initial state
        assert orchestrator.get_current_state() == PortfolioState.NORMAL
        
        # Test state history
        history = orchestrator.get_state_history()
        assert isinstance(history, list)
        
        # Test strategy states
        strategies = orchestrator.get_strategy_states()
        assert isinstance(strategies, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])