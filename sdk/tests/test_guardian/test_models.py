"""Tests for the MetaGuardian models and base classes."""

from __future__ import annotations

import pytest

from sdk.quantlab.guardian.models import (
    GuardianResult,
    GuardianStatus,
    GuardianType,
    MetaGuardianConfig,
    PortfolioState,
    StrategyState,
)
from sdk.quantlab.guardian.base import BaseGuardian


class TestGuardianModels:
    """Test the Guardian models and enums."""

    def test_guardian_type_enum(self):
        """Test GuardianType enum values."""
        assert GuardianType.MARKET.value == "market"
        assert GuardianType.RISK.value == "risk"
        assert GuardianType.PORTFOLIO.value == "portfolio"
        assert GuardianType.CAPITAL == GuardianType.CAPITAL
        assert len(list(GuardianType)) == 6

    def test_guardian_status_enum(self):
        """Test GuardianStatus enum values."""
        assert GuardianStatus.GREEN.value == "green"
        assert GuardianStatus.YELLOW.value == "yellow"
        assert GuardianStatus.RED.value == "red"
        assert len(list(GuardianStatus)) == 3

    def test_portfolio_state_enum(self):
        """Test PortfolioState enum values."""
        assert PortfolioState.NORMAL == "NORMAL"
        assert PortfolioState.VIGILANCE == "VIGILANCE"
        assert PortfolioState.DEFENSIVE == "DEFENSIVE"
        assert PortfolioState.QUARANTINE == "QUARANTINE"
        assert PortfolioState.RECOVERY == "RECOVERY"
        assert len(list(PortfolioState)) == 5

    def test_strategy_state_enum(self):
        """Test StrategyState enum values."""
        assert StrategyState.ACTIVE == "ACTIVE"
        assert StrategyState.MONITORING == "MONITORING"
        assert StrategyState.DEGRADING == "DEGRADING"
        assert StrategyState.REPLACEMENT_PENDING == "REPLACEMENT_PENDING"
        assert StrategyState.RETIRED == "RETIRED"
        assert len(list(StrategyState)) == 5

    def test_guardian_result_creation(self):
        """Test creating a GuardianResult."""
        result = GuardianResult(
            guardian_type=GuardianType.MARKET,
            status=GuardianStatus.GREEN,
            score=0.85,
            message="Market conditions normal",
        )
        
        assert result.guardian_type == GuardianType.MARKET
        assert result.status == GuardianStatus.GREEN
        assert result.score == 0.85
        assert result.message == "Market conditions normal"
        assert result.timestamp is not None

    def test_guardian_result_validation(self):
        """Test GuardianResult validation."""
        # Valid score
        result = GuardianResult(
            guardian_type=GuardianType.RISK,
            status=GuardianStatus.YELLOW,
            score=0.5,
            message="Test",
        )
        assert result.score == 0.5
        
        # Test bounds
        with pytest.raises(ValueError):
            GuardianResult(
                guardian_type=GuardianType.RISK,
                status=GuardianStatus.GREEN,
                score=1.5,  # Too high
                message="Test",
            )
        
        with pytest.raises(ValueError):
            GuardianResult(
                guardian_type=GuardianType.RISK,
                status=GuardianStatus.GREEN,
                score=-0.1,  # Too low
                message="Test",
            )

    def test_guardian_result_frozen(self):
        """Test that GuardianResult is frozen (immutable)."""
        result = GuardianResult(
            guardian_type=GuardianType.MARKET,
            status=GuardianStatus.GREEN,
            score=0.8,
            message="Test",
        )
        
        with pytest.raises(Exception):  # Should raise FrozenInstanceError or similar
            result.score = 0.9

    def test_meta_guardian_config_defaults(self):
        """Test MetaGuardianConfig default values."""
        config = MetaGuardianConfig()
        
        # Check default weights sum to approximately 1.0
        total_weight = sum(config.weights.values())
        assert abs(total_weight - 1.0) < 0.0001
        
        # Check specific weights
        assert config.weights[GuardianType.MARKET] == 0.15
        assert config.weights[GuardianType.RISK] == 0.30
        assert config.weights[GuardianType.PORTFOLIO] == 0.20
        assert config.weights[GuardianType.CAPITAL] == 0.15
        assert config.weights[GuardianType.QUALITY] == 0.10
        assert config.weights[GuardianType.EXECUTION] == 0.10
        
        # Check default thresholds
        assert config.thresholds["defensive_drawdown"] == 0.10
        assert config.thresholds["quarantine_drawdown"] == 0.20
        assert config.thresholds["recovery_drawdown"] == 0.05
        assert config.thresholds["degradation_checks"] == 3
        assert config.thresholds["retirement_checks"] == 5

    def test_meta_guardian_config_custom(self):
        """Test MetaGuardianConfig with custom values."""
        custom_weights = {
            GuardianType.MARKET: 0.2,
            GuardianType.RISK: 0.2,
            GuardianType.PORTFOLIO: 0.2,
            GuardianType.CAPITAL: 0.2,
            GuardianType.QUALITY: 0.1,
            GuardianType.EXECUTION: 0.1,
        }
        custom_thresholds = {
            "defensive_drawdown": 0.15,
            "quarantine_drawdown": 0.25,
            "recovery_drawdown": 0.08,
            "degradation_checks": 5,
            "retirement_checks": 10,
        }
        
        config = MetaGuardianConfig(
            weights=custom_weights,
            thresholds=custom_thresholds,
        )
        
        assert config.weights == custom_weights
        assert config.thresholds == custom_thresholds

    def test_base_guardian_abstract(self):
        """Test that BaseGuardian cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseGuardian()  # Should fail due to abstract methods


if __name__ == "__main__":
    pytest.main([__file__, "-v"])