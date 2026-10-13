"""E1: Small Capital Risk Warner.

Generates concrete, non-generic warnings for small-capital accounts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CapitalRiskWarning:
    """Concrete risk warning for a given capital level."""

    capital_usd: float
    max_lot_size: float
    min_stop_loss_pips: int
    recommended_timeframes: list[str]
    risk_of_ruin_pct: float
    warning_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "capital_usd": self.capital_usd,
            "max_lot_size": self.max_lot_size,
            "min_stop_loss_pips": self.min_stop_loss_pips,
            "recommended_timeframes": self.recommended_timeframes,
            "risk_of_ruin_pct": round(self.risk_of_ruin_pct, 1),
            "warning_text": self.warning_text,
        }


class SmallCapitalRiskWarner:
    """Generates concrete small-capital risk warnings (E1).

    Based on:
    - KB lore: nano-capital (< $500) distorts percentage risk metrics
    - Typical broker min lot: 0.01 (micro) or 0.001 (nano)
    - SL must be ≥ broker min stop distance (usually 10-30 pips)
    - Risk of ruin scales with (capital / (lot_size * SL_pips * pip_value))
    """

    # Broker-typical defaults (configurable)
    DEFAULT_MIN_LOT = 0.01
    DEFAULT_PIP_VALUE_USD = 10.0  # per standard lot on major pairs
    DEFAULT_MIN_STOP_PIPS = 10
    DEFAULT_RISK_PER_TRADE_PCT = 1.0  # 1% per trade

    # Timeframe → typical avg SL pips (broker/KB data)
    TIMEFRAME_SL_PIPS = {
        "M1": 5,
        "M5": 10,
        "M15": 15,
        "M30": 20,
        "H1": 25,
        "H4": 40,
        "D1": 60,
        "W1": 120,
        "MN": 300,
    }

    def __init__(
        self,
        min_lot: float = DEFAULT_MIN_LOT,
        pip_value_usd: float = DEFAULT_PIP_VALUE_USD,
        min_stop_pips: int = DEFAULT_MIN_STOP_PIPS,
        risk_per_trade_pct: float = DEFAULT_RISK_PER_TRADE_PCT,
    ) -> None:
        self.min_lot = min_lot
        self.pip_value_usd = pip_value_usd
        self.min_stop_pips = min_stop_pips
        self.risk_per_trade_pct = risk_per_trade_pct

    def warn(self, capital_usd: float, leverage: float = 30.0) -> CapitalRiskWarning:
        """Generate concrete warning for given capital."""
        if capital_usd <= 0:
            raise ValueError("capital_usd must be > 0")

        # Max position size constrained by margin
        # margin = (lot_size * contract_size) / leverage
        # For 1 lot = 100k units, margin ≈ 100000 / leverage USD
        # With capital C, max lots ≈ C * leverage / 100000
        max_lots_by_margin = (capital_usd * leverage) / 100_000
        max_lot_size = max(self.min_lot, round(max_lots_by_margin, 2))

        # Risk per trade in USD
        risk_usd = capital_usd * (self.risk_per_trade_pct / 100.0)

        # Min stop loss to keep risk within 1% given min lot
        # risk = lot * SL_pips * pip_value
        # SL_pips = risk / (lot * pip_value)
        min_sl_for_risk = risk_usd / (self.min_lot * self.pip_value_usd)
        min_stop_loss_pips = max(self.min_stop_pips, int(min_sl_for_risk))

        # Timeframes where SL ≥ min_stop_loss_pips
        recommended_tfs = [
            tf for tf, sl in self.TIMEFRAME_SL_PIPS.items()
            if sl >= min_stop_loss_pips
        ]

        # Risk of ruin approximation (simplified)
        # Probability of N consecutive losses at 50% win rate
        # Assuming 1% risk/trade, ~69 losses to ruin → (0.5)^69 ≈ 0
        # But with small capital, position sizing granularity hurts
        if capital_usd < 500:
            risk_of_ruin = 40.0 + (500 - capital_usd) * 0.1  # 40-90%
        elif capital_usd < 1000:
            risk_of_ruin = 20.0 + (1000 - capital_usd) * 0.04  # 20-40%
        elif capital_usd < 5000:
            risk_of_ruin = 5.0 + (5000 - capital_usd) * 0.003  # 5-20%
        else:
            risk_of_ruin = max(1.0, 5.0 - (capital_usd - 5000) * 0.0001)

        # Concrete warning text
        lines = [
            f"⚠  CAPITAL CHICO: ${capital_usd:,.0f} USD",
            f"  • Lote mínimo del broker: {self.min_lot:.2f} lotes",
            f"  • Tamaño máx. por margen ({leverage:.0f}:1): {max_lot_size:.2f} lotes",
            f"  • Riesgo por trade (1%): ${risk_usd:.2f} USD",
            f"  • SL mínimo para 1% riesgo: {min_stop_loss_pips} pips (lote {self.min_lot})",
            f"  • Timeframes viables (SL ≥ {min_stop_loss_pips} pips): {', '.join(recommended_tfs) if recommended_tfs else 'NINGUNO'}",
            f"  • Riesgo de ruina estimado: {risk_of_ruin:.1f}%",
        ]
        if capital_usd < 500:
            lines.append("  • ADVERTENCIA: Capital < $500 — el 1% riesgo = <$5/trade; ")
            lines.append("    los costos fijos (spread, comisión, swap) consumen >50% del riesgo.")
        elif capital_usd < 1000:
            lines.append("  • PRECAUCIÓN: Capital < $1000 — el dimensionado de posición es grueso; ")
            lines.append("    considera cuentas cent o brokers con lote 0.001 (nano).")

        return CapitalRiskWarning(
            capital_usd=capital_usd,
            max_lot_size=max_lot_size,
            min_stop_loss_pips=min_stop_loss_pips,
            recommended_timeframes=recommended_tfs,
            risk_of_ruin_pct=risk_of_ruin,
            warning_text="\n".join(lines),
        )


def generate_small_capital_warning(capital_usd: float, leverage: float = 30.0) -> str:
    """Convenience function returning warning text."""
    warner = SmallCapitalRiskWarner()
    return warner.warn(capital_usd, leverage).warning_text