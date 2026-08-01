"""Tests for the QualityGuardian."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from quantlab.guardian.quality import QualityGuardian
from quantlab.guardian.models import GuardianStatus, GuardianType


class TestQualityGuardian:
    """Test the QualityGuardian class."""

    def test_quality_guardian_initialization(self):
        """Test that QualityGuardian can be initialized."""
        health_system = Mock()
        guardian = QualityGuardian(health_system)
        
        assert guardian.health_system == health_system

    def test_quality_guardian_guardian_type(self):
        """Test that guardian_type returns correct type."""
        health_system = Mock()
        guardian = QualityGuardian(health_system)
        
        assert guardian.guardian_type() == GuardianType.QUALITY

    def test_quality_guardian_check_with_valid_data(self):
        """Test check method with valid data returns reasonable result."""
        # Setup mock
        health_system = Mock()
        health_system.get_all_strategy_scores.return_value = {
            "Strategy_A": 0.85,
            "Strategy_B": 0.72,
            "Strategy_C": 0.91,
            "Strategy_D": 0.63,
        }
        
        guardian = QualityGuardian(health_system)
        result = guardian.check()
        
        # Verify result structure
        assert hasattr(result, 'guardian_type')
        assert hasattr(result, 'status')
        assert hasattr(result, 'score')
        assert hasattr(result, 'message')
        assert hasattr(result, 'timestamp')
        
        assert result.guardian_type == GuardianType.QUALITY
        assert result.status in [GuardianStatus.GREEN, GuardianStatus.YELLOW, GuardianStatus.RED]
        assert 0.0 <= result.score <= 1.0
        assert isinstance(result.message, str)
        assert result.timestamp is not None
        
        # Verify mock was called
        health_system.get_all_strategy_scores.assert_called_once()

    def test_quality_guardian_check_with_exception(self):
        """Test check method handles exceptions gracefully."""
        # Setup mock to raise exception
        health_system = Mock()
        health_system.get_all_strategy_scores.side_effect = Exception("Health system error")
        
        guardian = QualityGuardian(health_system)
        result = guardian.check()
        
        # Should return a RED status result with error message
        assert result.guardian_type == GuardianType.QUALITY
        assert result.status == GuardianStatus.RED
        assert result.score == 0.0
        assert "Failed" in result.message or "error" in result.message.lower()

    def test_quality_guardian_edge_cases(self):
        """Test edge cases."""
        # Test with empty data
        health_system = Mock()
        health_system.get_all_strategy_scores.return_value = {}
        guardian = QualityGuardian(health_system)
        result = guardian.check()
        assert result.guardian_type == GuardianType.QUALITY
        assert result.status == GuardianStatus.YELLOW
        assert result.score == 0.5
        assert "No health scores" in result.message

        # Test with single strategy
        health_system.get_all_strategy_scores.return_value = {"Strategy_A": 0.75}
        guardian = QualityGuardian(health_system)
        result = guardian.check()
        assert result.guardian_type == GuardianType.QUALITY
        # Should handle single strategy case gracefully


if __name__ == "__main__":
    pytest.main([__file__, "-v"])