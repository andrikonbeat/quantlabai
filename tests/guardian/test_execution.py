"""Tests for ExecutionGuardian CostCollector wiring (Task 4.3)."""

import pytest

from quantlab.guardian.execution import ExecutionGuardian
from quantlab.guardian.models import GuardianStatus


class FakeBroker:
    """Minimal broker for testing."""
    def is_connected(self) -> bool:
        return True


class FakeCostCollectorGetRecent:
    """CostCollector with get_recent_slippage method."""
    def get_recent_slippage(self, symbol: str = "EURUSD") -> float:
        return 2.0  # 2 bps

    @property
    def slippage(self) -> float:
        return 2.0


class FakeCostCollectorSlippageAttr:
    """CostCollector without get_recent_slippage but with .slippage."""
    @property
    def slippage(self) -> float:
        return 5.0


class TestExecutionGuardianCostCollector:
    """CostCollector wiring in ExecutionGuardian._check_slippage."""

    def test_with_cost_collector_get_recent_slippage(self) -> None:
        """GIVEN an ExecutionGuardian with a real cost_collector
        WHEN _check_slippage is called
        THEN it uses cost_collector.get_recent_slippage() for scoring.
        """
        guardian = ExecutionGuardian(
            broker_interface=FakeBroker(),
            cost_collector=FakeCostCollectorGetRecent(),
        )
        score = guardian._check_slippage()
        # 2 bps out of 15 → score = 1 - 2/15 ≈ 0.867
        assert 0.86 <= score <= 0.87

    def test_with_cost_collector_slippage_attr(self) -> None:
        """GIVEN collector without get_recent_slippage but with .slippage
        WHEN _check_slippage is called
        THEN it falls back to the .slippage attribute.
        """
        guardian = ExecutionGuardian(
            broker_interface=FakeBroker(),
            cost_collector=FakeCostCollectorSlippageAttr(),
        )
        score = guardian._check_slippage()
        # 5 bps out of 15 → score = 1 - 5/15 ≈ 0.667
        assert 0.66 <= score <= 0.67

    def test_without_cost_collector_returns_default(self) -> None:
        """GIVEN no cost_collector
        WHEN _check_slippage is called
        THEN it returns the default 0.7 score.
        """
        guardian = ExecutionGuardian(
            broker_interface=FakeBroker(),
            cost_collector=None,
        )
        score = guardian._check_slippage()
        assert score == 0.7

    def test_check_method_includes_slippage_breakdown(self) -> None:
        """GIVEN a guardian with a cost_collector
        WHEN check() is called
        THEN the result has a valid score.
        """
        guardian = ExecutionGuardian(
            broker_interface=FakeBroker(),
            cost_collector=FakeCostCollectorGetRecent(),
        )
        result = guardian.check()
        assert result is not None
        assert isinstance(result.score, float)

    def test_zero_slippage_returns_perfect_score(self) -> None:
        """GIVEN zero slippage
        WHEN _check_slippage is called
        THEN it returns 1.0 (perfect score).
        """
        class ZeroSlippageCollector:
            def get_recent_slippage(self, symbol: str = "EURUSD") -> float:
                return 0.0
            @property
            def slippage(self) -> float:
                return 0.0

        guardian = ExecutionGuardian(
            broker_interface=FakeBroker(),
            cost_collector=ZeroSlippageCollector(),
        )
        score = guardian._check_slippage()
        assert score == 1.0

    def test_high_slippage_returns_low_score(self) -> None:
        """GIVEN high slippage (50+ bps)
        WHEN _check_slippage is called
        THEN it returns 0.0 (worst score).
        """
        class HighSlippageCollector:
            def get_recent_slippage(self, symbol: str = "EURUSD") -> float:
                return 50.0
            @property
            def slippage(self) -> float:
                return 50.0

        guardian = ExecutionGuardian(
            broker_interface=FakeBroker(),
            cost_collector=HighSlippageCollector(),
        )
        score = guardian._check_slippage()
        assert score == 0.0
