"""RiskGuardian: monitors portfolio risk metrics."""

from __future__ import annotations

from .base import BaseGuardian
from .models import GuardianResult, GuardianType, GuardianStatus


class RiskGuardian(BaseGuardian):
    """Monitors risk metrics and produces a risk health score."""

    def __init__(self, portfolio_data_provider):
        """Initialize the RiskGuardian.

        Args:
            portfolio_data_provider: Object that provides portfolio metrics
                (drawdown, Sharpe, exposure, etc.)
        """
        self.portfolio_data = portfolio_data_provider

    def guardian_type(self) -> GuardianType:
        """Return the guardian type."""
        return GuardianType.RISK

    def check(self) -> GuardianResult:
        """Check risk metrics and return a health score.

        Returns:
            GuardianResult: Risk health assessment.
        """
        # Get risk metrics from data provider
        try:
            metrics = self._get_risk_metrics()
        except Exception as e:
            return GuardianResult(
                guardian_type=GuardianType.RISK,
                status=GuardianStatus.RED,
                score=0.0,
                message=f"Failed to retrieve risk metrics: {str(e)}",
            )

        # Score individual components
        drawdown_score = self._score_drawdown(metrics.get("current_drawdown", 0.0))
        sharpe_score = self._score_sharpe(metrics.get("sharpe_ratio", 0.0))
        exposure_score = self._score_exposure(metrics.get("total_exposure", 0.0))
        kelly_score = self._score_kelly(metrics.get("kelly_fraction", 0.0))

        # Weighted average
        weights = {
            "drawdown": 0.3,
            "sharpe": 0.3,
            "exposure": 0.2,
            "kelly": 0.2,
        }
        composite_score = (
            weights["drawdown"] * drawdown_score +
            weights["sharpe"] * sharpe_score +
            weights["exposure"] * exposure_score +
            weights["kelly"] * kelly_score
        )

        # Determine status
        if composite_score >= 0.8:
            status = GuardianStatus.GREEN
            message = "Risk levels acceptable"
        elif composite_score >= 0.5:
            status = GuardianStatus.YELLOW
            message = "Elevated risk detected"
        else:
            status = GuardianStatus.RED
            message = "High risk levels - action recommended"

        return GuardianResult(
            guardian_type=GuardianType.RISK,
            status=status,
            score=round(composite_score, 3),
            message=message,
        )

    def _get_risk_metrics(self) -> dict:
        """Get risk metrics from the data provider.
        
        This is a placeholder - in reality, this would query the portfolio
        tracker, trade history, etc.
        """
        # For now, return mock data structure
        # In implementation, this would call actual portfolio methods
        return getattr(self.portfolio_data, 'get_risk_metrics', lambda: {
            "current_drawdown": 0.05,
            "max_drawdown": 0.08,
            "sharpe_ratio": 1.2,
            "total_exposure": 0.6,
            "kelly_fraction": 0.15,
            "var_95": 0.02,
        })()

    def _score_drawdown(self, current_drawdown: float) -> float:
        """Score based on current drawdown (lower is better).
        
        Args:
            current_drawdown: Current drawdown as decimal (0.05 = 5%)
            
        Returns:
            Score from 0.0 (bad) to 1.0 (good)
        """
        # 0% drawdown = 1.0 score
        # 20%+ drawdown = 0.0 score
        return max(0.0, min(1.0, 1.0 - (current_drawdown / 0.20)))

    def _score_sharpe(self, sharpe_ratio: float) -> float:
        """Score based on Sharpe ratio (higher is better).
        
        Args:
            sharpe_ratio: Sharpe ratio (typically -3 to +3)
            
        Returns:
            Score from 0.0 (bad) to 1.0 (good)
        """
        # Sharpe < 0 = 0.0 score
        # Sharpe > 2.0 = 1.0 score
        if sharpe_ratio < 0:
            return 0.0
        elif sharpe_ratio >= 2.0:
            return 1.0
        else:
            return sharpe_ratio / 2.0  # Linear from 0-2

    def _score_exposure(self, total_exposure: float) -> float:
        """Score based on total exposure (lower is better).
        
        Args:
            total_exposure: Total exposure as decimal (0.6 = 60% of capital)
            
        Returns:
            Score from 0.0 (bad) to 1.0 (good)
        """
        # 0% exposure = 0.5 score (not ideal but not terrible)
        # 100% exposure = 0.0 score
        # Ideal range: 20-80%
        if total_exposure <= 0.2:
            return 0.5 + (total_exposure / 0.2) * 0.5  # 0.5 to 1.0
        elif total_exposure >= 0.8:
            return max(0.0, 1.0 - ((total_exposure - 0.8) / 0.2))  # 1.0 to 0.0
        else:
            return 1.0  # Sweet spot

    def _score_kelly(self, kelly_fraction: float) -> float:
        """Score based on Kelly fraction usage.
        
        Args:
            kelly_fraction: Suggested fraction of capital per bet (0.0 to 1.0)
            
        Returns:
            Score from 0.0 (bad) to 1.0 (good)
        """
        # Kelly fraction > 0.25 is aggressive
        # Kelly fraction < 0.05 is too conservative
        # Ideal range: 0.05-0.25
        if kelly_fraction < 0.05:
            return kelly_fraction / 0.05 * 0.5  # 0.0 to 0.5
        elif kelly_fraction > 0.25:
            return max(0.0, 1.0 - ((kelly_fraction - 0.25) / 0.25))  # 1.0 to 0.0
        else:
            return 1.0  # Sweet spot