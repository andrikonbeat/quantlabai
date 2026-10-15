"""Exploration Director — orchestrates E1–E11 and emits ExplorationDecision.

Order per spec:
  E1 risk warning → E2 research (delegated to caller/providers) →
  E3 markets → E4 timeframes → E5 assets → E6 hypotheses →
  E7 capital limits → E8 prior observations → E9 broker costs →
  E10 risk management → E11 decision artifact.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from quantlab.exploration.models import BrokerCostSnapshot, ExplorationDecision
from quantlab.exploration.steps.asset_evaluator import AssetEvaluator
from quantlab.exploration.steps.broker_costs import BrokerCostsFetcher, WebFetchFn
from quantlab.exploration.steps.capital_limits import CapitalLimitsResolver
from quantlab.exploration.steps.hypothesis_researcher import HypothesisResearcher
from quantlab.exploration.steps.market_evaluator import MarketEvaluator
from quantlab.exploration.steps.prior_recall import PriorObservationsRecall
from quantlab.exploration.steps.risk_mgmt import RiskManagementEvaluator
from quantlab.exploration.steps.risk_warner import SmallCapitalRiskWarner
from quantlab.exploration.steps.timeframe_evaluator import TimeframeEvaluator


@dataclass
class ExplorationInputs:
    """Inputs for one exploration run."""

    capital_usd: float
    objectives: str = ""
    campaign_id: str = ""
    leverage: float = 30.0
    risk_per_trade_pct: float = 1.0
    candidate_markets: list[str] | None = None
    candidate_timeframes: list[str] | None = None
    candidate_symbols: list[str] | None = None
    max_spread_pips: float | None = None
    forbidden_markets: list[str] | None = None
    research_notes: str = ""  # E2 output supplied by caller (news/API/papers)
    operational_restrictions: dict[str, Any] = field(default_factory=dict)
    web_fetch_fn: WebFetchFn | None = None
    knowledge_root: str = "knowledge"
    sample_size: int = 200


@dataclass
class ExplorationResult:
    """Full exploration result: decision + per-step evidence."""

    decision: ExplorationDecision
    evidence: dict[str, Any]


class ExplorationDirector:
    """Runs E1–E11 in order and emits the decision artifact."""

    def __init__(
        self,
        knowledge_root: str = "knowledge",
        web_fetch_fn: WebFetchFn | None = None,
    ) -> None:
        self.knowledge_root = knowledge_root
        self.web_fetch_fn = web_fetch_fn

    def run(self, inputs: ExplorationInputs) -> ExplorationResult:
        """Execute E1–E11 and return the decision + evidence."""
        if inputs.capital_usd <= 0:
            raise ValueError("capital_usd must be > 0")

        evidence: dict[str, Any] = {}
        warnings: list[str] = []

        # E1: concrete small-capital warning.
        warner = SmallCapitalRiskWarner()
        capital_warning = warner.warn(inputs.capital_usd, inputs.leverage)
        evidence["e1_warning"] = capital_warning.to_dict()
        warnings.append(capital_warning.warning_text)

        # E2: research notes supplied by caller (providers run upstream).
        evidence["e2_research_notes"] = inputs.research_notes or "(no upstream notes)"

        # E3: markets.
        market_eval = MarketEvaluator(
            capital_usd=inputs.capital_usd,
            user_risk_pct=inputs.risk_per_trade_pct,
            max_spread_pips=inputs.max_spread_pips,
            forbidden_markets=inputs.forbidden_markets,
        )
        markets = market_eval.evaluate(inputs.candidate_markets)
        evidence["e3_markets"] = [
            {"market": m.market, "score": m.score, "rationale": m.rationale}
            for m in markets
        ]
        if not markets:
            raise ValueError("No markets passed the E3 filters")
        top_market = markets[0].market

        # E4: timeframes.
        tf_eval = TimeframeEvaluator(
            capital_usd=inputs.capital_usd,
            risk_per_trade_pct=inputs.risk_per_trade_pct,
        )
        timeframes = tf_eval.evaluate(inputs.candidate_timeframes)
        evidence["e4_timeframes"] = [
            {
                "timeframe": t.timeframe,
                "score": t.score,
                "avg_sl_pips": t.avg_sl_pips,
                "typical_sl_pips": t.typical_sl_pips,
                "rationale": t.rationale,
            }
            for t in timeframes
        ]
        if not timeframes:
            raise ValueError("No timeframes passed the E4 filters")
        top_tf = timeframes[0]
        top_timeframe = top_tf.timeframe

        # E5: assets.
        asset_eval = AssetEvaluator(
            capital_usd=inputs.capital_usd,
            max_risk_per_trade_pct=inputs.risk_per_trade_pct,
        )
        assets = asset_eval.evaluate(inputs.candidate_symbols)
        evidence["e5_assets"] = [
            {
                "symbol": a.symbol,
                "score": a.score,
                "tight_sl_feasible": a.tight_sl_feasible,
                "rationale": a.rationale,
            }
            for a in assets
        ]
        instruments = [a.symbol for a in assets if a.tight_sl_feasible][:5]
        if not instruments:
            instruments = [a.symbol for a in assets[:3]]
            warnings.append(
                "No instrument passes tight-SL feasibility; "
                "using top-3 by score with relaxed SL."
            )

        # E6: hypotheses + edge.
        researcher = HypothesisResearcher(sample_size=inputs.sample_size)
        hypotheses = researcher.research(
            top_market, top_timeframe, inputs.capital_usd
        )
        evidence["e6_hypotheses"] = [h.to_dict() for h in hypotheses]
        top_hyp = hypotheses[0]
        edge = top_hyp.edge.to_dict() if top_hyp.edge else {}

        # E7: capital limits + operational restrictions.
        limits_resolver = CapitalLimitsResolver()
        limits = limits_resolver.resolve(
            capital_usd=inputs.capital_usd,
            risk_per_trade_pct=inputs.risk_per_trade_pct,
            instruments=instruments,
            timeframe=top_timeframe,
            leverage=inputs.leverage,
        )
        restrictions = limits_resolver.resolve_restrictions(
            **inputs.operational_restrictions
        )
        evidence["e7_limits"] = limits.to_dict()
        evidence["e7_restrictions"] = restrictions.to_dict()

        # E8: prior observations (production call site).
        recall = PriorObservationsRecall(
            knowledge_root=inputs.knowledge_root or self.knowledge_root
        )
        campaign_id = inputs.campaign_id or f"exploration-{uuid.uuid4().hex[:8]}"
        prior = recall.recall_texts(campaign_id, "research")
        evidence["e8_prior_observations"] = prior

        # E9: broker costs.
        costs_fetcher = BrokerCostsFetcher(
            web_fetch_fn=inputs.web_fetch_fn or self.web_fetch_fn
        )
        broker_symbol = instruments[0] if instruments else top_market
        broker_info = costs_fetcher.fetch(broker_symbol)
        evidence["e9_broker_costs"] = {
            "symbol": broker_symbol,
            "snapshot": broker_info.model_dump(),
        }

        # E10: risk management.
        risk_eval = RiskManagementEvaluator(
            risk_per_trade_pct=inputs.risk_per_trade_pct
        )
        sl_pips = int(top_tf.typical_sl_pips)
        risk = risk_eval.evaluate(
            capital_usd=inputs.capital_usd,
            leverage=inputs.leverage,
            stop_loss_pips=sl_pips,
        )
        evidence["e10_risk"] = {
            "risk": risk.risk_dict(),
            "money": risk.money_dict(),
            "warnings": risk.warnings,
        }
        warnings.extend(risk.warnings)

        # E11: decision artifact.
        now = datetime.now(UTC).isoformat()
        decision = ExplorationDecision(
            capital_usd=inputs.capital_usd,
            market=top_market,
            instruments=instruments,
            timeframe=top_timeframe,
            leverage=inputs.leverage,
            capital_limits=limits.to_dict(),
            operational_restrictions=restrictions.to_dict(),
            risk_management=risk.risk_dict(),
            money_management=risk.money_dict(),
            prior_observations=prior,
            statistical_edge=edge,
            hypothesis=top_hyp.statement,
            broker_info=broker_info,
            exploration_id=campaign_id,
            created_at=now,
            warnings=warnings,
        )
        return ExplorationResult(decision=decision, evidence=evidence)
