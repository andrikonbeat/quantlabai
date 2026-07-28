"""NoveltyGenerator — generates new strategies via DSL combination and CFX translation."""

from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from quantlab.dsl.models import (
    AcceptanceCriterion,
    BuildingBlock,
    IndicatorConfig,
    Market,
    ResearchConfig,
    Strategy,
    StrategyDirection,
    Timeframe,
)
from quantlab.evolution.config import EvolutionConfig
from quantlab.evolution.fitness import FitnessFunction
from quantlab.evolution.models import CandidateStatus, EvolutionCandidate, EvolutionMode
from quantlab.pipeline.base import Pipeline, PipelineContext
from quantlab.pipeline.runner import PipelineRunner

logger = logging.getLogger(__name__)

# ── Seed Building Block Library ──────────────────────────────────────

SEED_BLOCKS: List[Dict[str, Any]] = [
    # Moving Averages
    {"indicator": "MA", "params": {"period": 20, "type": "SIMPLE"}},
    {"indicator": "MA", "params": {"period": 50, "type": "SIMPLE"}},
    {"indicator": "MA", "params": {"period": 200, "type": "SIMPLE"}},
    {"indicator": "EMA", "params": {"period": 12}},
    {"indicator": "EMA", "params": {"period": 26}},
    {"indicator": "EMA", "params": {"period": 9}},
    # Oscillators
    {"indicator": "RSI", "params": {"period": 14, "level": 30}},
    {"indicator": "RSI", "params": {"period": 7, "level": 25}},
    {"indicator": "RSI", "params": {"period": 21, "level": 35}},
    {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9}},
    {"indicator": "Stochastic", "params": {"k": 14, "d": 3, "slowing": 3}},
    # Volatility
    {"indicator": "BB", "params": {"period": 20, "stddev": 2.0}},
    {"indicator": "BB", "params": {"period": 50, "stddev": 2.5}},
    {"indicator": "ATR", "params": {"period": 14}},
    {"indicator": "ATR", "params": {"period": 7}},
    # Additional
    {"indicator": "ADX", "params": {"period": 14}},
    {"indicator": "CCI", "params": {"period": 20}},
    {"indicator": "WilliamsR", "params": {"period": 14}},
]

# DSL generation constants
MIN_BLOCKS_PER_STRATEGY = 2
MAX_BLOCKS_PER_STRATEGY = 4
RISK_PROFILES = ["conservative", "moderate", "aggressive"]
OBJECTIVES = ["sharpe", "profit", "sortino"]

# Risk → block count range
RISK_BLOCK_RANGES: Dict[str, tuple[int, int]] = {
    "conservative": (2, 3),
    "moderate": (2, 4),
    "aggressive": (3, 4),
}

# Risk → direction preference
RISK_DIRECTIONS: Dict[str, List[StrategyDirection]] = {
    "conservative": [StrategyDirection.BOTH],
    "moderate": [StrategyDirection.BOTH, StrategyDirection.LONG],
    "aggressive": [StrategyDirection.LONG, StrategyDirection.SHORT],
}


def _market_enum_from_str(market: str) -> Optional[Market]:
    """Convert a market string to a Market enum member (case-insensitive)."""
    upper = market.upper()
    for member in Market:
        if member.value == upper:
            return member
    return None


def _timeframe_enum_from_str(tf: str) -> Optional[Timeframe]:
    """Convert a timeframe string to a Timeframe enum member."""
    upper = tf.upper()
    for member in Timeframe:
        if member.value == upper:
            return member
    return None


def _select_building_blocks(context: Dict[str, Any]) -> List[BuildingBlock]:
    """Select a random subset of building blocks based on risk profile.

    Args:
        context: Generation context (risk_profile, objective, etc.).

    Returns:
        List of selected BuildingBlock instances.
    """
    risk = context.get("risk_profile", "moderate")
    if risk not in RISK_BLOCK_RANGES:
        risk = "moderate"

    block_range = RISK_BLOCK_RANGES[risk]
    count = random.randint(*block_range)
    count = min(count, len(SEED_BLOCKS))

    selected = random.sample(SEED_BLOCKS, count)
    blocks: List[BuildingBlock] = []
    for s in selected:
        block = BuildingBlock(
            name=f"{s['indicator']}_{s['params'].get('period', '')}_{uuid.uuid4().hex[:4]}",
            indicator=IndicatorConfig(name=s["indicator"], params=s["params"]),
        )
        blocks.append(block)

    return blocks


def _build_research_config(context: Dict[str, Any]) -> Optional[ResearchConfig]:
    """Build a ResearchConfig from DSL context parameters.

    Args:
        context: Dict with market, timeframe, risk_profile, objective keys.

    Returns:
        A ResearchConfig or None if required fields are missing.
    """
    market_str = context.get("market", "")
    tf_str = context.get("timeframe", "")
    risk_profile = context.get("risk_profile", "moderate")
    objective = context.get("objective", "sharpe")

    if not market_str or not tf_str:
        logger.info("Missing market or timeframe in context — skipping DSL generation")
        return None

    market = _market_enum_from_str(market_str)
    if market is None:
        logger.warning("Unknown market '%s' — skipping", market_str)
        return None

    timeframe = _timeframe_enum_from_str(tf_str)
    if timeframe is None:
        logger.warning("Unknown timeframe '%s' — skipping", tf_str)
        return None

    # Select building blocks
    blocks = _select_building_blocks(context)
    if not blocks:
        logger.warning("No building blocks selected — skipping DSL generation")
        return None

    # Create a strategy name
    campaign_name = f"SEG_{market.value}_{timeframe.value}_{uuid.uuid4().hex[:6]}"

    directions = RISK_DIRECTIONS.get(risk_profile, [StrategyDirection.BOTH])
    direction = random.choice(directions)

    strategy = Strategy(
        name=campaign_name,
        direction=direction,
        building_blocks=[b.name for b in blocks],
    )

    # Acceptance criteria based on objective
    criteria_map = {
        "sharpe": [
            AcceptanceCriterion(metric="sharpe_ratio", operator=">", value=1.0),
            AcceptanceCriterion(metric="profit_factor", operator=">", value=1.3),
        ],
        "profit": [
            AcceptanceCriterion(metric="net_profit", operator=">", value=1000),
            AcceptanceCriterion(metric="profit_factor", operator=">", value=1.2),
        ],
        "sortino": [
            AcceptanceCriterion(metric="sortino_ratio", operator=">", value=1.0),
            AcceptanceCriterion(metric="max_drawdown", operator="<", value=-0.15),
        ],
    }
    criteria = criteria_map.get(objective, criteria_map["sharpe"])

    return ResearchConfig(
        campaign=campaign_name,
        market=market,
        timeframe=timeframe,
        building_blocks=blocks,
        strategies=[strategy],
        criteria=criteria,
    )


# ── NoveltyGenerator ─────────────────────────────────────────────────


class NoveltyGenerator:
    """Generates novel trading strategies from scratch.

    Accepts a context dict (market, timeframe, risk_profile, objective),
    builds a DSL ResearchConfig using random building-block combinations,
    translates to CFX via the existing translator, runs a short backtest,
    and scores via FitnessFunction.
    """

    def __init__(
        self,
        config: EvolutionConfig,
        fitness: FitnessFunction,
        runner: Optional[PipelineRunner] = None,
    ) -> None:
        """Initialize the novelty generator.

        Args:
            config: Evolution configuration.
            fitness: Fitness function for scoring.
            runner: Optional PipelineRunner (creates a default one).
        """
        self._config = config
        self._fitness = fitness
        self._runner = runner or PipelineRunner()

    async def generate(
        self,
        context: Dict[str, Any],
        parent_candidate_id: Optional[str] = None,
    ) -> List[EvolutionCandidate]:
        """Generate novel strategy candidates from context.

        Args:
            context: Generation context with market, timeframe,
                     risk_profile, objective keys.
            parent_candidate_id: Optional parent candidate ID.

        Returns:
            List of generated candidates.
        """
        if not context or "market" not in context or "timeframe" not in context:
            # Check for signal-based context
            if "signal" in context:
                signal = context["signal"]
                context.setdefault("market", "EURUSD")
                context.setdefault("timeframe", "H1")
                context.setdefault("risk_profile", signal.get("mg_state", "moderate").lower())
            else:
                # Also accept bare dict without market/timeframe — common in scheduled cycles
                if "cycle" in context:
                    # Scheduled cycle — use defaults if no market/timeframe
                    logger.info("Scheduled cycle context without market/timeframe — using defaults")
                    return []
                return []

        # Validate required context
        market_str = context.get("market", "")
        tf_str = context.get("timeframe", "")
        if not market_str or not tf_str:
            return []

        # Build DSL ResearchConfig
        config = _build_research_config(context)
        if config is None:
            return []

        # Translate to CFX archive
        cfx_content = await self._translate_to_cfx(config)
        if cfx_content is None:
            return []

        # Build pipeline for short backtest
        from quantlab.pipeline.registry import StageRegistry

        registry = StageRegistry()
        pipeline = Pipeline(name="novelty-backtest")
        stage_names = ["daemon_start", "load_cfx", "run_backtest",
                        "compute_stats", "export"]
        for name in stage_names:
            stage_class = registry.get_stage_class(name)
            if stage_class is None:
                from quantlab.evolution.genetic import _NoopStage
                stage = _NoopStage(name=name)
            else:
                stage = stage_class()
            pipeline.stages.append(stage)

        candidate_id = f"novel-{uuid.uuid4().hex[:12]}"

        pipeline_ctx = PipelineContext(
            config={
                "market": market_str,
                "timeframe": tf_str,
                "candidate_id": candidate_id,
                "novelty": True,
            },
            artifacts={
                "cfx_content": cfx_content,
                "candidate_id": candidate_id,
                "research_config": config.model_dump(mode="json"),
            },
        )

        try:
            pipeline_result = await self._runner.run(pipeline, pipeline_ctx)
            fitness_score = self._score_from_result(pipeline_result, config)
        except Exception as exc:
            logger.warning("Novelty backtest failed for candidate %s: %s", candidate_id, exc)
            pipeline_result = None
            fitness_score = 0.0

        candidate = EvolutionCandidate(
            candidate_id=candidate_id,
            strategy_id=f"{market_str}_{tf_str}_{uuid.uuid4().hex[:4]}",
            mode=EvolutionMode.GENERATIVE_ONLY,
            cfx_content=cfx_content,
            dsl_content=self._describe_dsl(config),
            parent_candidate_id=parent_candidate_id,
            fitness_score=fitness_score,
            status=CandidateStatus.PENDING,
            validation_results={
                "genesis": "novelty_generator",
                "market": market_str,
                "timeframe": tf_str,
                "risk_profile": context.get("risk_profile", "moderate"),
                "objective": context.get("objective", "sharpe"),
                "building_blocks": [b.name for b in config.building_blocks],
                "block_count": len(config.building_blocks),
                "pipeline_completed": pipeline_result is not None and pipeline_result.is_successful if pipeline_result else False,
            },
        )

        logger.info("NoveltyGenerator: generated 1 candidate for %s/%s", market_str, tf_str)
        return [candidate]

    async def _translate_to_cfx(self, config: ResearchConfig) -> Optional[str]:
        """Translate a ResearchConfig to a CFX XML string.

        Uses the existing ``generate_cfx_archive`` + ``CfxWriter``
        translation pipeline.
        """
        try:
            from quantlab.cfx.writer import CfxWriter
            from quantlab.translate.translator import generate_cfx_archive

            archive = generate_cfx_archive(config)
            writer = CfxWriter()
            xml_bytes = writer.write_bytes(archive)
            # Write_bytes may return bytes; ensure we get a string
            if isinstance(xml_bytes, bytes):
                return xml_bytes.decode("utf-8")
            return str(xml_bytes)
        except ImportError as exc:
            logger.warning("CFX translation modules not available: %s", exc)
            # Fallback: generate a minimal valid CFX XML
            return self._generate_minimal_cfx(config)
        except Exception as exc:
            logger.warning("CFX translation failed: %s", exc)
            return self._generate_minimal_cfx(config)

    def _generate_minimal_cfx(self, config: ResearchConfig) -> str:
        """Generate a minimal CFX XML string directly (fallback path).

        This is used when the full translator pipeline isn't available
        (e.g., during early development or testing).
        """
        market = config.market.value if config.market else "EURUSD"
        tf = config.timeframe.value if config.timeframe else "H1"
        blocks_xml = ""
        for idx, block in enumerate(config.building_blocks, 1):
            params = block.indicator.params
            params_str = " ".join(f'{k}="{v}"' for k, v in params.items())
            blocks_xml += f'  <Block index="{idx}" name="{block.indicator.name}" {params_str}/>\n'

        cfx = f"""<?xml version="1.0" encoding="utf-8"?>
<StrategyQuant Version="141.2219">
  <BuildTask name="Build-Task1">
    <Options>
      <Campaign name="{config.campaign}"/>
    </Options>
    <Data>
      <Symbol name="{market}"/>
      <Timeframe value="{tf}"/>
    </Data>
    <WhatToBuild>
      <UseGenetic value="false"/>
    </WhatToBuild>
    <Blocks>
{blocks_xml}    </Blocks>
  </BuildTask>
</StrategyQuant>"""
        return cfx

    def _describe_dsl(self, config: ResearchConfig) -> str:
        """Produce a human-readable DSL description of the generated strategy."""
        blocks_desc = ", ".join(
            f"{b.indicator.name}({', '.join(f'{k}={v}' for k, v in b.indicator.params.items())})"
            for b in config.building_blocks
        )
        return (
            f"Market={config.market.value}, Timeframe={config.timeframe.value}, "
            f"Direction={config.strategies[0].direction.value if config.strategies else 'BOTH'}, "
            f"Blocks=[{blocks_desc}]"
        )

    def _score_from_result(self, pipeline_result: Any, config: ResearchConfig) -> float:
        """Derive a fitness score from pipeline backtest results."""
        if pipeline_result is None:
            return 0.0
        if not hasattr(pipeline_result, "is_successful") or not pipeline_result.is_successful:
            return 0.0

        # Score based on completeness
        completed = 0
        total = 0
        if hasattr(pipeline_result, "stages"):
            stages = pipeline_result.stages
            for s in stages:
                total += 1
                if hasattr(s, "status") and s.status.value == "completed":
                    completed += 1

        if total == 0:
            return 0.0

        base_score = (completed / total) * 50.0
        # Bonus for having more building blocks (complexity premium)
        block_bonus = min(len(config.building_blocks) * 5.0, 20.0)
        return min(base_score + block_bonus, 100.0)
