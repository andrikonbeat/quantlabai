"""ResearchAgent — generates ResearchConfig DSL from objectives and Knowledge Lake queries.

Formulates testable hypotheses with confidence scores, queries historical
campaigns for context, produces iteration proposals, and implements the
``ResearchStage.execute()`` contract for pipeline integration.
"""

from __future__ import annotations

import logging
from typing import Any

from quantlab.dsl.models import (
    AcceptanceCriterion,
    BuildingBlock,
    EntryRule,
    ExitRule,
    HypothesisConfig,
    IndicatorConfig,
    IterationConfig,
    Market,
    ResearchConfig,
    Strategy,
    StrategyDirection,
    Timeframe,
)

logger = logging.getLogger(__name__)


class ResearchAgent:
    """Generates research configurations from high-level objectives.

    Translates natural-language research goals into structured ``ResearchConfig``
    Pydantic models, queries Knowledge Lake for historical context, and
    formulates testable hypotheses with calibrated confidence scores.

    Args:
        query_builder_cls: Optional ``QueryBuilder`` class for Knowledge Lake
            queries. Defaults to ``quantlab.knowledge.query.QueryBuilder``.
    """

    def __init__(self, query_builder_cls: Any = None) -> None:
        self._query_builder_cls = query_builder_cls

    # ── Task 2.5: Config generation ────────────────────────────────────────────

    def generate_config(
        self,
        objectives: list[str],
        market_context: dict[str, Any] | None = None,
    ) -> ResearchConfig:
        """Generate a validated ``ResearchConfig`` from high-level objectives.

        Parses objectives to extract market, timeframe, and building blocks,
        then creates a complete ``ResearchConfig`` with hypotheses, iteration
        config, and gate policies.

        Args:
            objectives: List of research objective strings (e.g.
                ``["Find mean-reversion on EURUSD H1"]``).
            market_context: Optional dict with market metadata (e.g.
                ``{"market": "EURUSD", "timeframe": "H1", "tags": ["mean_reversion"]}``).

        Returns:
            A fully validated ``ResearchConfig`` instance.

        Raises:
            ValueError: If no objectives provided or objectives reference
                an unknown market.
        """
        if not objectives:
            raise ValueError("At least one objective is required")

        # Parse first objective to extract market and timeframe
        market, timeframe, tags = self._parse_objective(objectives[0], market_context)

        # Generate building blocks from objectives
        building_blocks = self._generate_building_blocks(objectives)

        # Generate strategies
        strategies = self._generate_strategies(objectives, building_blocks)

        # Generate acceptance criteria
        criteria = self._generate_criteria(objectives)

        # Generate hypotheses
        hypotheses = self.formulate_hypotheses(objectives)

        # Build the complete config
        config = ResearchConfig(
            campaign=objectives[0][:50] if objectives else "Research Campaign",
            market=market,
            timeframe=timeframe,
            building_blocks=building_blocks,
            strategies=strategies,
            criteria=criteria,
            hypotheses=hypotheses,
            iteration_config=IterationConfig(
                max_iterations=5,
                convergence_threshold=0.02,
                early_stop_patience=2,
                auto_iterate=True,
            ),
        )

        return config

    def _parse_objective(
        self,
        objective: str,
        market_context: dict[str, Any] | None = None,
    ) -> tuple[Market, Timeframe, list[str]]:
        """Parse market and timeframe from an objective string or context.

        Args:
            objective: Objective string like "Find mean-reversion on EURUSD H1".
            market_context: Optional context with explicit market/timeframe.

        Returns:
            Tuple of (Market, Timeframe, tags).

        Raises:
            ValueError: If the market/timeframe cannot be determined.
        """
        # First check explicit context
        if market_context:
            ctx_market = market_context.get("market", "")
            ctx_timeframe = market_context.get("timeframe", "")
            ctx_tags = market_context.get("tags", [])

            if ctx_market:
                try:
                    market = Market(ctx_market.upper())
                    tf = Timeframe(ctx_timeframe.upper()) if ctx_timeframe else Timeframe.H1
                    return market, tf, ctx_tags
                except ValueError:
                    pass

        # Parse from objective text
        objective_upper = objective.upper()

        # Detect market
        for m in Market:
            if m.value in objective_upper:
                market = m
                break
        else:
            raise ValueError(
                f"Cannot determine market from objective: '{objective}'. "
                f"Use explicit market_context or include a market name."
            )

        # Detect timeframe
        for tf in Timeframe:
            if tf.value in objective_upper:
                return market, tf, []

        # Default timeframe
        return market, Timeframe.H1, []

    def _generate_building_blocks(
        self,
        objectives: list[str],
    ) -> list[BuildingBlock]:
        """Generate building blocks from objectives.

        Maps common strategy keywords to indicator configurations.

        Args:
            objectives: List of objective strings.

        Returns:
            List of ``BuildingBlock`` instances.
        """
        blocks: list[BuildingBlock] = []
        keywords_seen: set[str] = set()

        for obj in objectives:
            obj_lower = obj.lower()

            # Mean reversion
            if "mean-reversion" in obj_lower or "mean reversion" in obj_lower:
                if "rsi" not in keywords_seen:
                    blocks.append(
                        BuildingBlock(
                            name="RSI_MeanReversion",
                            indicator=IndicatorConfig(
                                name="RSI",
                                params={"period": 14, "oversold": 30, "overbought": 70},
                            ),
                            entry=EntryRule(
                                description="RSI oversold entry",
                                conditions=["rsi(14) < 30"],
                            ),
                            exit=ExitRule(
                                description="RSI overbought exit",
                                conditions=["rsi(14) > 70"],
                            ),
                        )
                    )
                    keywords_seen.add("rsi")

                if "bb" not in keywords_seen and ("bollinger" in obj_lower or "bb" in obj_lower):
                    blocks.append(
                        BuildingBlock(
                            name="BollingerBands",
                            indicator=IndicatorConfig(
                                name="BB",
                                params={"period": 20, "deviation": 2.0},
                            ),
                            entry=EntryRule(
                                description="Bollinger lower band touch",
                                conditions=["close < bb_lower(20, 2)"],
                            ),
                        )
                    )
                    keywords_seen.add("bb")

            # Breakout / trend
            if "breakout" in obj_lower or "break out" in obj_lower:
                if "donchian" not in keywords_seen:
                    blocks.append(
                        BuildingBlock(
                            name="DonchianBreakout",
                            indicator=IndicatorConfig(
                                name="Donchian",
                                params={"period": 20},
                            ),
                            entry=EntryRule(
                                description="Donchian breakout entry",
                                conditions=["high > donchian_high(20)"],
                            ),
                        )
                    )
                    keywords_seen.add("donchian")

            # Momentum / trend
            if "momentum" in obj_lower or "trend" in obj_lower:
                if "ema" not in keywords_seen:
                    blocks.append(
                        BuildingBlock(
                            name="EMATrend",
                            indicator=IndicatorConfig(
                                name="EMA",
                                params={"period": 200},
                            ),
                            entry=EntryRule(
                                description="Price above EMA trend filter",
                                conditions=["close > ema(200)"],
                            ),
                        )
                    )
                    keywords_seen.add("ema")

            # Volatility
            if "volatility" in obj_lower or "atr" in obj_lower:
                if "atr" not in keywords_seen:
                    blocks.append(
                        BuildingBlock(
                            name="ATRFilter",
                            indicator=IndicatorConfig(
                                name="ATR",
                                params={"period": 14},
                            ),
                        )
                    )
                    keywords_seen.add("atr")

        # Default: add RSI if nothing matched
        if not blocks:
            blocks.append(
                BuildingBlock(
                    name="RSI_Default",
                    indicator=IndicatorConfig(
                        name="RSI", params={"period": 14},
                    ),
                )
            )

        return blocks

    def _generate_strategies(
        self,
        objectives: list[str],
        building_blocks: list[BuildingBlock],
    ) -> list[Strategy]:
        """Generate strategies from objectives and building blocks.

        Args:
            objectives: List of objective strings.
            building_blocks: List of building blocks to reference.

        Returns:
            List of ``Strategy`` instances.
        """
        obj_lower = " ".join(objectives).lower()
        direction = StrategyDirection.BOTH
        if "long" in obj_lower and "short" not in obj_lower:
            direction = StrategyDirection.LONG
        elif "short" in obj_lower and "long" not in obj_lower:
            direction = StrategyDirection.SHORT

        return [
            Strategy(
                name="PrimaryStrategy",
                direction=direction,
                building_blocks=[b.name for b in building_blocks],
            ),
        ]

    def _generate_criteria(
        self,
        objectives: list[str],
    ) -> list[AcceptanceCriterion]:
        """Generate acceptance criteria from objectives.

        Args:
            objectives: List of objective strings.

        Returns:
            List of ``AcceptanceCriterion`` instances.
        """
        return [
            AcceptanceCriterion(metric="profit_factor", operator=">=", value=1.5),
            AcceptanceCriterion(metric="sharpe", operator=">=", value=1.0),
            AcceptanceCriterion(metric="max_drawdown", operator="<=", value=0.15),
            AcceptanceCriterion(metric="win_rate", operator=">=", value=0.35),
        ]

    # ── Task 2.6: Hypothesis formulation ────────────────────────────────────────

    def query_knowledge_lake(
        self,
        market: str,
        timeframe: str,
        tags: list[str] | None = None,
        min_sharpe: float = 1.0,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Query Knowledge Lake for historical campaigns matching criteria.

        Uses ``QueryBuilder`` to search for similar campaigns by market,
        timeframe, and strategy tags.

        Args:
            market: Market identifier (e.g. ``"EURUSD"``).
            timeframe: Timeframe (e.g. ``"H1"``).
            tags: Optional list of strategy tags (e.g. ``["mean_reversion"]``).
            min_sharpe: Minimum Sharpe ratio filter.
            limit: Maximum number of results.

        Returns:
            List of campaign summary dicts with metrics, tags, and links.
        """
        try:
            # Lazy import to avoid circular dependency
            from pathlib import Path
            from quantlab.knowledge.query import QueryBuilder

            builder_cls = self._query_builder_cls or QueryBuilder

            # Build a minimal index for query
            knowledge_root = Path("knowledge/structured")
            index: dict[str, Any] = {"directories": {"results": {}, "campaigns": {}}}

            # Use QueryBuilder directly with index
            builder = builder_cls(index, knowledge_root)

            # Apply filters
            query = (
                builder
                .filter_by_sharpe(min_val=min_sharpe)
                .filter_by_date(start="2022-01-01")
                .limit(limit)
            )

            if tags:
                query = query.filter_by_tags(tags)

            result = query.execute()
            return [
                {
                    "campaign_id": c.campaign_id,
                    "name": c.name,
                    "sharpe_ratio": c.metrics.sharpe_ratio if c.metrics else None,
                    "profit_factor": c.metrics.profit_factor if c.metrics else None,
                    "win_rate": c.metrics.win_rate if c.metrics else None,
                    "max_drawdown": c.metrics.max_drawdown if c.metrics else None,
                    "tags": c.tags,
                }
                for c in result.campaigns
            ]

        except Exception as e:
            logger.warning("Knowledge Lake query failed (may not be available): %s", e)
            return []

    def formulate_hypotheses(
        self,
        objectives: list[str],
        query_results: list[dict[str, Any]] | None = None,
    ) -> list[HypothesisConfig]:
        """Generate structured hypotheses from objectives and historical data.

        Produces 3-5 hypotheses covering different strategy approaches with
        calibrated confidence scores based on historical success rates.

        Args:
            objectives: List of research objective strings.
            query_results: Optional list of query results from
                ``query_knowledge_lake()`` to calibrate confidence.

        Returns:
            List of ``HypothesisConfig`` with unique IDs, descriptions,
            confidence scores in [0, 1], parameters, and expected metrics.
        """
        hypotheses: list[HypothesisConfig] = []
        obj_lower = " ".join(objectives).lower()

        # Compute historical baseline confidence from query results
        avg_historical_sharpe = 1.0
        if query_results:
            sharpes = [
                r.get("sharpe_ratio", 0) or 0
                for r in query_results
                if r.get("sharpe_ratio") is not None
            ]
            if sharpes:
                avg_historical_sharpe = sum(sharpes) / len(sharpes)

        # Hypothesis 1: Mean reversion (if objectives suggest it)
        if "mean-reversion" in obj_lower or "mean reversion" in obj_lower:
            base_confidence = min(0.7, 0.4 + avg_historical_sharpe * 0.2)
            hypotheses.append(
                HypothesisConfig(
                    name="mean_reversion_rsi_bb",
                    description="RSI(14) < 30 + Bollinger lower band touch entry, "
                                "take profit at middle band",
                    parameters={
                        "rsi_period": 14,
                        "rsi_oversold": 30,
                        "bb_period": 20,
                        "bb_deviation": 2.0,
                    },
                    expected_outcome=(
                        f"Sharpe > {avg_historical_sharpe:.1f}, "
                        "win rate > 40%, max drawdown < 15%"
                    ),
                    confidence=round(base_confidence, 2),
                )
            )

            hypotheses.append(
                HypothesisConfig(
                    name="mean_reversion_dual_rsi",
                    description="RSI(7) cross above 30 after RSI(14) < 25 confirmation entry",
                    parameters={
                        "fast_rsi": 7,
                        "slow_rsi": 14,
                        "oversold_fast": 30,
                        "oversold_slow": 25,
                    },
                    expected_outcome="Higher win rate than single RSI, sharpe improvement 0.2",
                    confidence=round(max(0.3, base_confidence - 0.15), 2),
                )
            )

        # Hypothesis 2: Breakout / trend (if objectives suggest it)
        if "breakout" in obj_lower or "trend" in obj_lower or "momentum" in obj_lower:
            hypotheses.append(
                HypothesisConfig(
                    name="donchian_breakout",
                    description="Donchian(20) breakout with ATR(14) volatility filter",
                    parameters={
                        "donchian_period": 20,
                        "atr_period": 14,
                        "atr_multiplier": 1.5,
                    },
                    expected_outcome=f"Sharpe > {min(1.6, avg_historical_sharpe + 0.2):.1f}",
                    confidence=round(min(0.75, 0.5 + avg_historical_sharpe * 0.15), 2),
                )
            )

        # Hypothesis 3: Volatility-based (if objectives suggest it)
        if "volatility" in obj_lower or "atr" in obj_lower or "squeeze" in obj_lower:
            hypotheses.append(
                HypothesisConfig(
                    name="bollinger_squeeze",
                    description="Bollinger Band squeeze (bandwidth < 0.1) followed by "
                                "breakout in direction of ATR expansion",
                    parameters={
                        "bb_period": 20,
                        "bb_deviation": 2.0,
                        "squeeze_threshold": 0.1,
                        "atr_period": 14,
                    },
                    expected_outcome="Capture post-squeeze breakouts, sharpe > 1.3",
                    confidence=round(min(0.6, 0.3 + avg_historical_sharpe * 0.2), 2),
                )
            )

        # Hypothesis 4: General robustness
        hypotheses.append(
            HypothesisConfig(
                name="robustness_validation",
                description="Validate top strategies across 2020-2024 with walk-forward "
                            "analysis, minimum 30 trades, max 20% drawdown",
                parameters={
                    "min_trades": 30,
                    "max_drawdown": 0.20,
                    "wf_cycles": 10,
                    "wf_oot_ratio": 0.3,
                },
                expected_outcome="At least 1 strategy passes all robustness checks",
                confidence=0.5,
            )
        )

        # Hypothesis 5: Regime detection (always included)
        hypotheses.append(
            HypothesisConfig(
                name="regime_adaptive_params",
                description="Adapt entry parameters based on market regime "
                            "(trending vs ranging detected via ADX/DMI)",
                parameters={
                    "adx_period": 14,
                    "trend_threshold": 25,
                },
                expected_outcome="Improved Sharpe in ranging markets, reduced drawdown",
                confidence=0.4,
            )
        )

        return hypotheses

    # ── Task 2.9: Pipeline context integration ──────────────────────────────────

    async def run(self, context: Any) -> dict[str, Any]:
        """Execute the research agent stage in a pipeline.

        Implements the ``ResearchStage.execute()`` contract: reads campaign
        objectives from ``context.config``, calls ``generate_config()`` and
        ``formulate_hypotheses()``, and writes the results to ``context.artifacts``.

        Args:
            context: ``PipelineContext`` with config containing ``campaign_name``,
                ``objectives``, and ``market_context``.

        Returns:
            Dict with ``research_config``, ``objectives``, ``hypotheses``,
            ``iteration_config``, and ``gate_policies``.
        """
        config = context.config or {}
        objectives: list[str] = config.get("objectives", config.get("campaign_name", "Research"))
        if isinstance(objectives, str):
            objectives = [objectives]

        market_context: dict[str, Any] | None = config.get("market_context")

        # Generate ResearchConfig from objectives
        research_config = self.generate_config(objectives, market_context)

        # Query Knowledge Lake for historical context
        query_results = self.query_knowledge_lake(
            market=research_config.market.value,
            timeframe=research_config.timeframe.value,
            tags=[config.get("campaign_name", "")],
        )

        # Formulate hypotheses with historical calibration
        hypotheses = self.formulate_hypotheses(objectives, query_results)
        research_config.hypotheses = hypotheses

        # Serialize for context artifacts
        research_config_dict = research_config.model_dump(mode="json")
        hypotheses_dict = [h.model_dump(mode="json") for h in hypotheses]
        iteration_config_dict = research_config.iteration_config.model_dump(mode="json")
        gate_policies_dict = [g.model_dump(mode="json") for g in research_config.gate_policies]

        # Write to context artifacts
        context.artifacts["research_config"] = research_config_dict
        context.artifacts["objectives"] = objectives
        context.artifacts["hypotheses"] = hypotheses_dict
        context.artifacts["iteration_config"] = iteration_config_dict
        context.artifacts["gate_policies"] = gate_policies_dict

        logger.info(
            "ResearchAgent: generated config for '%s' with %d hypotheses",
            research_config.campaign, len(hypotheses),
        )

        return {
            "research_config": research_config_dict,
            "objectives": objectives,
            "hypotheses": hypotheses_dict,
            "iteration_config": iteration_config_dict,
            "gate_policies": gate_policies_dict,
        }
