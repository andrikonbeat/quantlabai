"""MarketGuardian: monitors market conditions (regime, volatility, liquidity, session)."""

from __future__ import annotations

from .base import BaseGuardian
from .models import GuardianResult, GuardianType, GuardianStatus


class MarketGuardian(BaseGuardian):
    """Monitors market conditions and produces a health score."""

    def __init__(self, regime_collector, cost_collector):
        """Initialize the MarketGuardian.

        Args:
            regime_collector: Collector for regime data (from RegimeClassifier)
            cost_collector: Collector for cost data (from Auto-Costs)
        """
        self.regime_collector = regime_collector
        self.cost_collector = cost_collector

    def guardian_type(self) -> GuardianType:
        """Return the guardian type."""
        return GuardianType.MARKET

    def check(self) -> GuardianResult:
        """Check market conditions and return a health score.

        Returns:
            GuardianResult: Market health assessment.
        """
        # Get regime data
        try:
            regime_data = self.regime_collector.collect("MARKET_PORTFOLIO")
        except Exception:
            # Fallback if regime data unavailable
            regime_data = {"regime": "UNKNOWN", "confidence": 0.0}

        # Get cost data for liquidity proxy
        try:
            # Get costs for major pairs as liquidity indicator
            major_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
            cost_data = self.cost_collector.collect_all(major_pairs)
        except Exception:
            # Fallback if cost data unavailable
            cost_data = {}

        # Calculate component scores (0.0-1.0)
        regime_score = self._score_regime(regime_data)
        volatility_score = self._score_volatility(regime_data)
        liquidity_score = self._score_liquidity(cost_data)
        session_score = self._score_session()

        # Weighted average (can be made configurable)
        weights = {
            "regime": 0.3,
            "volatility": 0.3,
            "liquidity": 0.2,
            "session": 0.2,
        }
        composite_score = (
            weights["regime"] * regime_score +
            weights["volatility"] * volatility_score +
            weights["liquidity"] * liquidity_score +
            weights["session"] * session_score
        )

        # Determine status based on score
        if composite_score >= 0.8:
            status = GuardianStatus.GREEN
            message = "Market conditions normal"
        elif composite_score >= 0.5:
            status = GuardianStatus.YELLOW
            message = "Market conditions warrants caution"
        else:
            status = GuardianStatus.RED
            message = "Market conditions hostile"

        return GuardianResult(
            guardian_type=GuardianType.MARKET,
            status=status,
            score=round(composite_score, 3),
            message=message,
        )

    def _score_regime(self, regime_data: dict) -> float:
        """Score based on market regime."""
        regime = regime_data.get("regime", "UNKNOWN").upper()
        confidence = regime_data.get("confidence", 0.5)

        # TREND and RANGE are good for most strategies
        if regime in ["TREND", "RANGE"]:
            return 0.9 * confidence
        elif regime == "VOLATILE":
            return 0.6 * confidence  # Volatile but tradeable
        elif regime == "QUIET":
            return 0.4 * confidence  # Low opportunity
        else:
            return 0.2  # Unknown regime

    def _score_volatility(self, regime_data: dict) -> float:
        """Score based on volatility levels."""
        # In a full implementation, this would use ATR percentile
        # For now, use regime as proxy
        regime = regime_data.get("regime", "UNKNOWN").upper()
        if regime == "VOLATILE":
            return 0.3  # High volatility = lower score
        elif regime == "QUIET":
            return 0.5  # Low volatility = medium score
        else:
            return 0.8  # Normal volatility = good score

    def _score_liquidity(self, cost_data: dict) -> float:
        """Score based on liquidity (inverse of spreads).

        Expects ``cost_data`` as returned by ``CostCollector.collect_all()``
        — a dict of ``{symbol: {"spread_pips": float, ...}}``.
        """
        if not cost_data:
            return 0.5  # Unknown liquidity

        # Average spread across pairs (lower spread = better liquidity)
        spreads = []
        for pair_data in cost_data.values():
            if isinstance(pair_data, dict) and 'spread_pips' in pair_data:
                spreads.append(pair_data['spread_pips'])

        if not spreads:
            return 0.5

        avg_spread = sum(spreads) / len(spreads)
        # Normalize: 0 pip spread, 5 pips = very bad
        # 0.0 pip = 1.0 score, 5.0 pips = 0.0 score
        return max(0.0, min(1.0, 1.0 - (avg_spread / 5.0)))

    def _score_session(self) -> float:
        """Score based on current trading session."""
        # Simplified: assume we want to trade during major sessions
        # In reality, this would check UTC time against session windows
        return 0.8  # Placeholder - in session