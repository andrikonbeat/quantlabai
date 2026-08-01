"""Tests for the RiskGuardian."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from quantlab.guardian.risk import RiskGuardian
from quantlab.guardian.models import GuardianResult, GuardianStatus, GuardianType


class TestRiskGuardian:
    """Test the RiskGuardian class."""

    def test_risk_guardian_initialization(self):
        """Test that RiskGuardian can be initialized."""
        portfolio_data = Mock()
        guardian = RiskGuardian(portfolio_data)
        
        assert guardian.portfolio_data == portfolio_data

    def test_risk_guardian_guardian_type(self):
        """Test that guardian_type returns correct type."""
        portfolio_data = Mock()
        guardian = RiskGuardian(portfolio_data)
        
        assert guardian.guardian_type() == GuardianType.RISK

    def test_risk_guardian_check_with_valid_data(self):
        """Test check method with valid data returns reasonable result."""
        # Setup mock
        portfolio_data = Mock()
        portfolio_data.get_risk_metrics.return_value = {
            "current_drawdown": 0.05,  # 5%
            "max_drawdown": 0.08,      # 8%
            "sharpe_ratio": 1.2,
            "total_exposure": 0.6,     # 60%
            "kelly_fraction": 0.15,    # 15%
            "var_95": 0.02,
        }
        
        guardian = RiskGuardian(portfolio_data)
        result = guardian.check()
        
        # Verify result structure
        assert isinstance(result, GuardianResult)
        assert result.guardian_type == GuardianType.RISK
        assert result.status in [GuardianStatus.GREEN, GuardianStatus.YELLOW, GuardianStatus.RED]
        assert 0.0 <= result.score <= 1.0
        assert isinstance(result.message, str)
        assert result.timestamp is not None
        
        # Verify mock was called
        portfolio_data.get_risk_metrics.assert_called_once()

    def test_risk_guardian_check_with_exception(self):
        """Test check method handles exceptions gracefully."""
        # Setup mock to raise exception
        portfolio_data = Mock()
        portfolio_data.get_risk_metrics.side_effect = Exception("Database error")
        
        guardian = RiskGuardian(portfolio_data)
        result = guardian.check()
        
        # Should return a RED status result with error message
        assert result.guardian_type == GuardianType.RISK
        assert result.status == GuardianStatus.RED
        assert result.score == 0.0
        assert "Failed" in result.message or "error" in result.message.lower()

    def test_risk_guardian_scoring_methods(self):
        """Test individual scoring methods return valid ranges."""
        guardian = RiskGuardian(Mock())
        
        # Test _score_drawdown
        assert 0.0 <= guardian._score_drawdown(0.0) <= 1.0      # 0% DD
        assert 0.0 <= guardian._score_drawdown(0.1) <= 1.0      # 10% DD
        assert 0.0 <= guardian._score_drawdown(0.2) <= 1.0      # 20% DD
        assert 0.0 <= guardian._score_drawdown(0.3) <= 1.0      # 30% DD
        
        # Test _score_sharpe
        assert 0.0 <= guardian._score_sharpe(-1.0) <= 1.0       # Negative
        assert 0.0 <= guardian._score_sharpe(0.0) <= 1.0        # Zero
        assert 0.0 <= guardian._score_sharpe(1.0) <= 1.0        # Positive
        assert 0.0 <= guardian._score_sharpe(2.0) <= 1.0        # Good
        assert 0.0 <= guardian._score_sharpe(3.0) <= 1.0        # Excellent
        
        # Test _score_exposure
        assert 0.0 <= guardian._score_exposure(0.0) <= 1.0      # 0% exposure
        assert 0.0 <= guardian._score_exposure(0.5) <= 1.0      # 50% exposure
        assert 0.0 <= guardian._score_exposure(1.0) <= 1.0      # 100% exposure
        
        # Test _score_kelly
        assert 0.0 <= guardian._score_kelly(0.0) <= 1.0         # 0% Kelly
        assert 0.0 <= guardian._score_kelly(0.1) <= 1.0         # 10% Kelly
        assert 0.0 <= guardian._score_kelly(0.3) <= 1.0         # 30% Kelly

    def test_risk_guardian_edge_cases(self):
        """Test edge cases in scoring methods."""
        guardian = RiskGuardian(Mock())
        
        # Drawdown edge cases
        assert abs(guardian._score_drawdown(0.0) - 1.0) < 1e-10  # No drawdown
        assert abs(guardian._score_drawdown(0.2) - 0.0) < 1e-10  # 20% drawdown (max)
        assert guardian._score_drawdown(0.3) == 0.0             # Over 20% still 0
        
        # Sharpe edge cases
        assert abs(guardian._score_sharpe(0.0) - 0.0) < 1e-10   # Zero Sharpe
        assert abs(guardian._score_sharpe(2.0) - 1.0) < 1e-10   # Max score
        assert abs(guardian._score_sharpe(3.0) - 1.0) < 1e-10   # Still max
        
        # Exposure edge cases
        assert abs(guardian._score_exposure(0.2) - 1.0) < 1e-10   # Low end of sweet spot
        assert abs(guardian._score_exposure(0.5) - 1.0) < 1e-10   # Middle of sweet spot
        assert abs(guardian._score_exposure(0.8) - 1.0) < 1e-10   # High end of sweet spot
        assert abs(guardian._score_exposure(0.0) - 0.5) < 1e-10   # Below minimum
        assert abs(guardian._score_exposure(1.0) - 0.0) < 1e-10   # Maximum exposure
        
        # Kelly edge cases
        assert abs(guardian._score_kelly(0.05) - 1.0) < 1e-10   # Minimum good
        assert abs(guardian._score_kelly(0.15) - 1.0) < 1e-10   # Middle good
        assert abs(guardian._score_kelly(0.25) - 1.0) < 1e-10   # Maximum good
        assert abs(guardian._score_kelly(0.0) - 0.0) < 1e-10    # Zero Kelly
        assert abs(guardian._score_kelly(0.5) - 0.0) < 1e-10    # Double maximum

if __name__ == "__main__":
    pytest.main([__file__, "-v"])