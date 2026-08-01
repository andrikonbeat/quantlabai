"""Tests for the CapitalGuardian."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from quantlab.guardian.capital import CapitalGuardian
from quantlab.guardian.models import GuardianStatus, GuardianType


class TestCapitalGuardian:
    """Test the CapitalGuardian class."""

    def test_capital_guardian_initialization(self):
        """Test that CapitalGuardian can be initialized."""
        performance_data = Mock()
        guardian = CapitalGuardian(performance_data)
        
        assert guardian.performance_data == performance_data

    def test_capital_guardian_guardian_type(self):
        """Test that guardian_type returns correct type."""
        performance_data = Mock()
        guardian = CapitalGuardian(performance_data)
        
        assert guardian.guardian_type() == GuardianType.CAPITAL

    def test_capital_guardian_check_with_valid_data(self):
        """Test check method with valid data returns reasonable result."""
        # Setup mock
        performance_data = Mock()
        performance_data.get_strategy_performance.return_value = {
            "Strategy_A": {
                "win_rate": 0.6,
                "avg_win": 0.02,
                "avg_loss": 0.01,
                "sharpe": 1.2,
                "expectancy": 0.007,
            },
            "Strategy_B": {
                "win_rate": 0.55,
                "avg_win": 0.015,
                "avg_loss": 0.008,
                "sharpe": 0.9,
                "expectancy": 0.0035,
            },
        }
        
        guardian = CapitalGuardian(performance_data)
        result = guardian.check()
        
        # Verify result structure
        assert hasattr(result, 'guardian_type')
        assert hasattr(result, 'status')
        assert hasattr(result, 'score')
        assert hasattr(result, 'message')
        assert hasattr(result, 'timestamp')
        
        assert result.guardian_type == GuardianType.CAPITAL
        assert result.status in [GuardianStatus.GREEN, GuardianStatus.YELLOW, GuardianStatus.RED]
        assert 0.0 <= result.score <= 1.0
        assert isinstance(result.message, str)
        assert result.timestamp is not None
        
        # Verify mock was called
        performance_data.get_strategy_performance.assert_called_once()

    def test_capital_guardian_check_with_exception(self):
        """Test check method handles exceptions gracefully."""
        # Setup mock to raise exception
        performance_data = Mock()
        performance_data.get_strategy_performance.side_effect = Exception("Performance error")
        
        guardian = CapitalGuardian(performance_data)
        result = guardian.check()
        
        # Should return a RED status result with error message
        assert result.guardian_type == GuardianType.CAPITAL
        assert result.status == GuardianStatus.RED
        assert result.score == 0.0
        assert "Failed" in result.message or "error" in result.message.lower()

    def test_capital_guardian_with_optional_guardians(self):
        """Test CapitalGuardian with optional risk and portfolio guardians."""
        performance_data = Mock()
        performance_data.get_strategy_performance.return_value = {
            "Strategy_A": {"expectancy": 0.01, "sharpe": 1.0, "win_rate": 0.5}
        }
        
        risk_mock = Mock()
        portfolio_mock = Mock()
        
        guardian = CapitalGuardian(performance_data, risk_mock, portfolio_mock)
        
        assert guardian.performance_data == performance_data
        assert guardian.risk_guardian == risk_mock
        assert guardian.portfolio_guardian == portfolio_mock

        # Should still work
        result = guardian.check()
        assert result.guardian_type == GuardianType.CAPITAL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])