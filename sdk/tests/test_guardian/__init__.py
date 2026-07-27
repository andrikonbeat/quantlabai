"""Tests for the guardian module imports and basic functionality."""

from __future__ import annotations

import pytest

# Test that we can import the module
def test_guardian_import():
    """Test that the guardian module can be imported."""
    from sdk.quantlab import guardian
    assert guardian is not None

def test_guardian_submodule_imports():
    """Test that we can import the submodules."""
    from sdk.quantlab.guardian import (
        BaseGuardian,
        CapitalGuardian,
        ExecutionGuardian,
        MarketGuardian,
        QualityGuardian,
        RiskGuardian,
        MetaGuardianOrchestrator,
        GuardianResult,
        GuardianStatus,
        GuardianType,
        PortfolioState,
        StrategyState,
        MetaGuardianConfig,
    )
    
    # Verify they're the right types
    assert isinstance(GuardianType.MARKET, GuardianType)
    assert isinstance(GuardianStatus.GREEN, GuardianStatus)
    assert isinstance(PortfolioState.NORMAL, PortfolioState)
    assert isinstance(StrategyState.ACTIVE, StrategyState)
    
    # Verify we can instantiate the config
    config = MetaGuardianConfig()
    assert isinstance(config, MetaGuardianConfig)
    assert isinstance(config.weights, dict)
    assert len(config.weights) == 6

def test_guardian_can_create_instances():
    """Test that we can create basic instances (where dependencies allow)."""
    # Test that we can import and access the classes
    from sdk.quantlab.guardian.models import GuardianResult
    
    # Test creating a simple result
    result = GuardianResult(
        guardian_type="market",  # This will be converted to enum
        status="green",          # This will be converted to enum
        score=0.8,
        message="test",
    )
    
    assert result.guardian_type.value == "market"
    assert result.status.value == "green"
    assert result.score == 0.8
    assert result.message == "test"

    # Test creating a MetaGuardianOrchestrator (with empty list for now)
    from sdk.quantlab.guardian import MetaGuardianOrchestrator, MetaGuardianConfig
    config = MetaGuardianConfig()
    orchestrator = MetaGuardianOrchestrator(config, [])
    assert isinstance(orchestrator, MetaGuardianOrchestrator)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])