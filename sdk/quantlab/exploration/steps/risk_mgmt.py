"""E10: Risk Management Evaluator.

Evaluates risk management, capital (money) management, and leverage with
concrete numbers for the exploration decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RiskEvaluation:
    """Concrete risk/money-management evaluation."""

    leverage: float
    leverage_fit: float  # 0.0–1.0
    recommended_leverage: float
    risk_per_trade_pct: float
    risk_per_trade_usd: float
    max_portfolio_heat_pct: float
    position_size_lots: float
    stop_loss_pips: int
    take_profit_pips: int
    rr_ratio: float
    money_method: str
    warnings: list[str]

    def risk_dict(self) -> dict[str, Any]:
        return {
            "stop_loss_type": "fixed_pips",
            "stop_loss_pips": self.stop_loss_pips,
            "take_profit_pips": self.take_profit_pips,
            "reward_risk_ratio": round(self.rr_ratio, 2),
            "max_portfolio_heat_pct": self.max_portfolio_heat_pct,
            "leverage": self.leverage,
            "recommended_leverage": self.recommended_leverage,
        }

    def money_dict(self) -> dict[str, Any]:
        return {
            "position_sizing_method": self.money_method,
            "fixed_fractional_pct": self.risk_per_trade_pct,
            "position_size_lots": round(self.position_size_lots, 2),
            "risk_per_trade_usd": round(self.risk_per_trade_usd, 2),
            "compounding": self.risk_per_trade_pct <= 2.0,
        }


class RiskManagementEvaluator:
    """Evaluates leverage, risk and money management (E10)."""

    def __init__(
        self,
        risk_per_trade_pct: float = 1.0,
        max_portfolio_heat_pct: float = 6.0,
        max_concurrent_positions: int = 3,
        rr_ratio: float = 1.5,
        money_method: str = "fixed_fractional",
    ) -> None:
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_portfolio_heat_pct = max_portfolio_heat_pct
        self.max_concurrent_positions = max_concurrent_positions
        self.rr_ratio = rr_ratio
        self.money_method = money_method

    def evaluate(
        self,
        capital_usd: float,
        leverage: float,
        stop_loss_pips: int,
        pip_value: float = 10.0,
        min_lot: float = 0.01,
    ) -> RiskEvaluation:
        """Evaluate risk/money management with concrete numbers."""
        if capital_usd <= 0:
            raise ValueError("capital_usd must be > 0")
        if stop_loss_pips <= 0:
            raise ValueError("stop_loss_pips must be > 0")

        risk_usd = capital_usd * (self.risk_per_trade_pct / 100.0)
        # Position size in lots for the given SL: lots = risk / (SL * pip).
        position_lots = risk_usd / (stop_loss_pips * pip_value)
        position_lots = max(min_lot, round(position_lots, 2))
        # Recomputed actual risk at rounded lots.
        actual_risk = position_lots * stop_loss_pips * pip_value
        take_profit = int(stop_loss_pips * self.rr_ratio)

        # Leverage fit: required margin vs capital.
        # margin ≈ lots * 100_000 / leverage; fit if margin <= 50% capital.
        margin = position_lots * 100_000 / max(leverage, 1.0)
        leverage_fit = max(0.0, min(1.0, 1.0 - margin / max(capital_usd * 0.5, 1e-9)))
        recommended = leverage
        if margin > capital_usd * 0.5:
            # Suggest the leverage that halves margin pressure.
            recommended = min(500.0, leverage * 2.0)

        warnings: list[str] = []
        if actual_risk > risk_usd * 1.1:
            warnings.append(
                f"Lot rounding pushes risk to ${actual_risk:.2f} "
                f"(>{self.risk_per_trade_pct}% of capital)."
            )
        if leverage > 100:
            warnings.append(
                f"Leverage {leverage:.0f}:1 amplifies ruin risk on small capital; "
                "prefer ≤ 50:1."
            )
        heat = self.risk_per_trade_pct * self.max_concurrent_positions
        if heat > self.max_portfolio_heat_pct:
            warnings.append(
                f"Portfolio heat {heat:.1f}% exceeds cap {self.max_portfolio_heat_pct:.1f}%: "
                f"reduce to {int(self.max_portfolio_heat_pct // self.risk_per_trade_pct)} positions."
            )

        return RiskEvaluation(
            leverage=leverage,
            leverage_fit=round(leverage_fit, 3),
            recommended_leverage=recommended,
            risk_per_trade_pct=self.risk_per_trade_pct,
            risk_per_trade_usd=round(actual_risk, 2),
            max_portfolio_heat_pct=self.max_portfolio_heat_pct,
            position_size_lots=position_lots,
            stop_loss_pips=stop_loss_pips,
            take_profit_pips=take_profit,
            rr_ratio=self.rr_ratio,
            money_method=self.money_method,
            warnings=warnings,
        )
