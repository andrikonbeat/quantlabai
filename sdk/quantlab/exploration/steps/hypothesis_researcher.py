"""E6: Hypothesis Researcher.

Researches hypotheses and estimates statistical edge candidates.
Reuses the refutation-layer contract (adversarial / historical / regime
falsification) and adds a deterministic edge-estimation model so the
exploration decision can carry concrete numbers without an LLM call.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EdgeEstimate:
    """Deterministic statistical edge estimate for one hypothesis."""

    hypothesis_id: str
    expected_sharpe: float
    win_rate: float
    profit_factor: float
    avg_win_loss_ratio: float
    expectancy_per_trade: float  # in R multiples
    sample_size: int
    confidence: float  # 0.0–1.0
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "expected_sharpe": round(self.expected_sharpe, 3),
            "win_rate": round(self.win_rate, 3),
            "profit_factor": round(self.profit_factor, 3),
            "avg_win_loss_ratio": round(self.avg_win_loss_ratio, 3),
            "expectancy_per_trade": round(self.expectancy_per_trade, 3),
            "sample_size": self.sample_size,
            "confidence": round(self.confidence, 3),
            "rationale": self.rationale,
        }


@dataclass
class HypothesisCandidate:
    """One research hypothesis with its edge estimate and refutation status."""

    hypothesis_id: str
    statement: str
    market: str
    timeframe: str
    building_blocks: list[str] = field(default_factory=list)
    edge: EdgeEstimate | None = None
    refutation: dict[str, Any] = field(default_factory=dict)
    source: str = "template"

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement,
            "market": self.market,
            "timeframe": self.timeframe,
            "building_blocks": self.building_blocks,
            "edge": self.edge.to_dict() if self.edge else None,
            "refutation": self.refutation,
            "source": self.source,
        }


# Five fixed template hypotheses mirroring research_agent.py generation.
TEMPLATE_HYPOTHESES: tuple[dict[str, Any], ...] = (
    {
        "hypothesis_id": "H1",
        "statement": (
            "Momentum continuation: price breaking the 20-bar Donchian high "
            "with RSI(14) > 55 continues in the breakout direction over the "
            "next N bars."
        ),
        "building_blocks": ["donchian_breakout", "rsi_filter"],
        "base_win_rate": 0.42,
        "base_rr": 1.8,
    },
    {
        "hypothesis_id": "H2",
        "statement": (
            "Mean reversion: RSI(2) < 10 on the daily timeframe reverts to "
            "the 5-day mean within 3 bars."
        ),
        "building_blocks": ["rsi2_oversold", "mean_reversion_exit"],
        "base_win_rate": 0.62,
        "base_rr": 0.8,
    },
    {
        "hypothesis_id": "H3",
        "statement": (
            "Trend filter: EMA(200) slope positive admits long-only entries; "
            "short entries are disabled in uptrends."
        ),
        "building_blocks": ["ema200_trend", "long_only"],
        "base_win_rate": 0.48,
        "base_rr": 1.5,
    },
    {
        "hypothesis_id": "H4",
        "statement": (
            "Volatility breakout: ATR(14) expansion above its 50-bar median "
            "precedes directional continuation entries."
        ),
        "building_blocks": ["atr_expansion", "breakout_entry"],
        "base_win_rate": 0.45,
        "base_rr": 1.6,
    },
    {
        "hypothesis_id": "H5",
        "statement": (
            "Session edge: London-open range breakouts on majors outperform "
            "random entries during the overlap session."
        ),
        "building_blocks": ["session_range", "overlap_breakout"],
        "base_win_rate": 0.47,
        "base_rr": 1.4,
    },
)


def estimate_edge(
    hypothesis_id: str,
    win_rate: float,
    avg_win_loss_ratio: float,
    sample_size: int,
) -> EdgeEstimate:
    """Deterministic edge estimate from win rate and payoff ratio.

    profit_factor = (w * R) / ((1 - w) * 1)
    expectancy_R = w * R - (1 - w)
    sharpe ≈ expectancy_R * sqrt(trades_per_year) / std_R (std_R ≈ 1.2 heuristic)
    confidence grows with sample size: 1 - 1/sqrt(n).
    """
    if not 0.0 < win_rate < 1.0:
        raise ValueError("win_rate must be in (0, 1)")
    if avg_win_loss_ratio <= 0:
        raise ValueError("avg_win_loss_ratio must be > 0")
    if sample_size <= 0:
        raise ValueError("sample_size must be > 0")

    profit_factor = (win_rate * avg_win_loss_ratio) / (1.0 - win_rate)
    expectancy_r = win_rate * avg_win_loss_ratio - (1.0 - win_rate)
    # Heuristic annualised Sharpe assuming ~200 trades/year, R-std 1.2.
    expected_sharpe = (expectancy_r * math.sqrt(200.0)) / 1.2
    confidence = 1.0 - 1.0 / math.sqrt(sample_size)

    rationale = (
        f"PF {profit_factor:.2f} from WR {win_rate:.0%} x R {avg_win_loss_ratio:.2f}; "
        f"expectancy {expectancy_r:+.2f}R/trade over n={sample_size}; "
        f"heuristic Sharpe {expected_sharpe:+.2f}"
    )
    return EdgeEstimate(
        hypothesis_id=hypothesis_id,
        expected_sharpe=expected_sharpe,
        win_rate=win_rate,
        profit_factor=profit_factor,
        avg_win_loss_ratio=avg_win_loss_ratio,
        expectancy_per_trade=expectancy_r,
        sample_size=sample_size,
        confidence=confidence,
        rationale=rationale,
    )


class HypothesisResearcher:
    """Researches hypotheses and statistical edge candidates (E6).

    Generates template hypotheses, attaches deterministic edge estimates,
    and records a refutation-layer placeholder (adversarial / historical /
    regime checks run downstream in the campaign pipeline).
    """

    def __init__(
        self,
        sample_size: int = 200,
        edge_adjustment: float = 1.0,
    ) -> None:
        self.sample_size = sample_size
        self.edge_adjustment = edge_adjustment

    def research(
        self,
        market: str,
        timeframe: str,
        capital_usd: float,
        templates: tuple[dict[str, Any], ...] = TEMPLATE_HYPOTHESES,
    ) -> list[HypothesisCandidate]:
        """Build hypothesis candidates with edge estimates."""
        candidates: list[HypothesisCandidate] = []
        # Small capital degrades edge via costs: scale payoff down.
        cost_drag = 1.0
        if capital_usd < 500:
            cost_drag = 0.80
        elif capital_usd < 1000:
            cost_drag = 0.90

        for tpl in templates:
            rr = tpl["base_rr"] * cost_drag * self.edge_adjustment
            edge = estimate_edge(
                tpl["hypothesis_id"],
                tpl["base_win_rate"],
                rr,
                self.sample_size,
            )
            candidates.append(HypothesisCandidate(
                hypothesis_id=tpl["hypothesis_id"],
                statement=tpl["statement"],
                market=market,
                timeframe=timeframe,
                building_blocks=list(tpl["building_blocks"]),
                edge=edge,
                refutation={
                    "adversarial": "pending",
                    "historical": "pending",
                    "regime": "pending",
                },
                source="template",
            ))

        # Best edge first.
        candidates.sort(
            key=lambda c: c.edge.expectancy_per_trade if c.edge else 0.0,
            reverse=True,
        )
        return candidates
