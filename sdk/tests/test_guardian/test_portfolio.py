"""Tests for the PortfolioGuardian."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from quantlab.guardian.portfolio import PortfolioGuardian
from quantlab.guardian.models import GuardianStatus, GuardianType


class TestPortfolioGuardian:
    """Test the PortfolioGuardian class."""

    def test_portfolio_guardian_initialization(self):
        """Test that PortfolioGuardian can be initialized."""
        returns_data = Mock()
        guardian = PortfolioGuardian(returns_data)
        
        assert guardian.returns_data == returns_data

    def test_portfolio_guardian_guardian_type(self):
        """Test that guardian_type returns correct type."""
        returns_data = Mock()
        guardian = PortfolioGuardian(returns_data)
        
        assert guardian.guardian_type() == GuardianType.PORTFOLIO

    def test_portfolio_guardian_check_with_valid_data(self):
        """Test check method with valid data returns reasonable result."""
        # Setup mock
        returns_data = Mock()
        returns_data.get_strategy_returns.return_value = {
            "Strategy_A": [0.01, -0.005, 0.02, 0.015, -0.01],
            "Strategy_B": [0.008, 0.012, -0.003, 0.01, 0.005],
            "Strategy_C": [-0.002, 0.01, 0.007, -0.005, 0.012],
        }
        
        guardian = PortfolioGuardian(returns_data)
        result = guardian.check()
        
        # Verify result structure
        assert hasattr(result, 'guardian_type')
        assert hasattr(result, 'status')
        assert hasattr(result, 'score')
        assert hasattr(result, 'message')
        assert hasattr(result, 'timestamp')
        
        assert result.guardian_type == GuardianType.PORTFOLIO
        assert result.status in [GuardianStatus.GREEN, GuardianStatus.YELLOW, GuardianStatus.RED]
        assert 0.0 <= result.score <= 1.0
        assert isinstance(result.message, str)
        assert result.timestamp is not None
        
        # Verify mock was called
        returns_data.get_strategy_returns.assert_called_once()

    def test_portfolio_guardian_check_with_exception(self):
        """Test check method handles exceptions gracefully."""
        # Setup mock to raise exception
        returns_data = Mock()
        returns_data.get_strategy_returns.side_effect = Exception("Data error")
        
        guardian = PortfolioGuardian(returns_data)
        result = guardian.check()
        
        # Should return a RED status result with error message
        assert result.guardian_type == GuardianType.PORTFOLIO
        assert result.status == GuardianStatus.RED
        assert result.score == 0.0
        assert "Failed" in result.message or "error" in result.message.lower()

    def test_portfolio_guardian_edge_cases(self):
        """Test edge cases."""
        returns_data = Mock()
        
        # Test with insufficient data
        returns_data.get_strategy_returns.return_value = {
            "Strategy_A": [0.01, 0.02]  # Only one strategy
        }
        guardian = PortfolioGuardian(returns_data)
        result = guardian.check()
        assert result.guardian_type == GuardianType.PORTFOLIO
        # Should handle gracefully - either YELLOW or RED with appropriate message
        
        # Test with empty data
        returns_data.get_strategy_returns.return_value = {}
        guardian = PortfolioGuardian(returns_data)
        result = guardian.check()
        assert result.guardian_type == GuardianType.PORTFOLIO
        assert result.status == GuardianStatus.RED
        assert result.score == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])