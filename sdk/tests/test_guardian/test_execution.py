"""Tests for the ExecutionGuardian."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from quantlab.guardian.execution import ExecutionGuardian
from quantlab.guardian.models import GuardianStatus, GuardianType


class TestExecutionGuardian:
    """Test the ExecutionGuardian class."""

    def test_execution_guardian_initialization(self):
        """Test that ExecutionGuardian can be initialized."""
        broker = Mock()
        guardian = ExecutionGuardian(broker)
        
        assert guardian.broker == broker

    def test_execution_guardian_initialization_with_cost_collector(self):
        """Test that ExecutionGuardian can be initialized with cost collector."""
        broker = Mock()
        cost_collector = Mock()
        guardian = ExecutionGuardian(broker, cost_collector)
        
        assert guardian.broker == broker
        assert guardian.cost_collector == cost_collector

    def test_execution_guardian_guardian_type(self):
        """Test that guardian_type returns correct type."""
        broker = Mock()
        guardian = ExecutionGuardian(broker)
        
        assert guardian.guardian_type() == GuardianType.EXECUTION

    def test_execution_guardian_check_with_valid_data(self):
        """Test check method with valid data returns reasonable result."""
        # Setup mock
        broker = Mock()
        broker.is_connected.return_value = True
        broker.get_latency.return_value = 25  # 25ms
        broker.get_health_score.return_value = 0.9
        
        cost_collector = Mock()
        cost_collector.get_recent_slippage.return_value = 2.0  # 2bps
        
        guardian = ExecutionGuardian(broker, cost_collector)
        result = guardian.check()
        
        # Verify result structure
        assert hasattr(result, 'guardian_type')
        assert hasattr(result, 'status')
        assert hasattr(result, 'score')
        assert hasattr(result, 'message')
        assert hasattr(result, 'timestamp')
        
        assert result.guardian_type == GuardianType.EXECUTION
        assert result.status in [GuardianStatus.GREEN, GuardianStatus.YELLOW, GuardianStatus.RED]
        assert 0.0 <= result.score <= 1.0
        assert isinstance(result.message, str)
        assert result.timestamp is not None
        
        # Verify mocks were called
        broker.is_connected.assert_called_once()
        broker.get_latency.assert_called_once()
        broker.get_health_score.assert_called_once()
        cost_collector.get_recent_slippage.assert_called_once()

    def test_execution_guardian_check_with_exception(self):
        """Test check method handles exceptions gracefully."""
        # Setup mock to raise exception
        broker = Mock()
        broker.is_connected.side_effect = Exception("Connection error")
        
        guardian = ExecutionGuardian(broker)
        result = guardian.check()
        
        # Should return a RED status result with error message
        assert result.guardian_type == GuardianType.EXECUTION
        assert result.status == GuardianStatus.RED
        assert result.score == 0.0
        assert "Failed" in result.message or "error" in result.message.lower()

    def test_execution_guardian_disconnected_broker(self):
        """Test behavior when broker is disconnected."""
        broker = Mock()
        broker.is_connected.return_value = False
        
        guardian = ExecutionGuardian(broker)
        result = guardian.check()
        
        # Should return RED status when disconnected
        assert result.guardian_type == GuardianType.EXECUTION
        assert result.status == GuardianStatus.RED
        assert result.score == 0.0
        assert "disconnected" in result.message.lower()

    def test_execution_guardian_without_cost_collector(self):
        """Test ExecutionGuardian works without cost collector."""
        broker = Mock()
        broker.is_connected.return_value = True
        broker.get_latency.return_value = 30
        broker.get_health_score.return_value = 0.8
        
        guardian = ExecutionGuardian(broker)  # No cost collector
        result = guardian.check()
        
        # Should still work and return a reasonable score
        assert result.guardian_type == GuardianType.EXECUTION
        assert result.status in [GuardianStatus.GREEN, GuardianStatus.YELLOW, GuardianStatus.RED]
        assert 0.0 <= result.score <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])