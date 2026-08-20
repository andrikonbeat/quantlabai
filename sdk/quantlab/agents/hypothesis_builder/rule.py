"""RuleMode — deterministic keyword-based building block generation.

Maps hypothesis description text to indicator configurations using
a keyword matching table (spec RB-4). Returns validated building blocks
and strategies ready for pipeline consumption.
"""

from __future__ import annotations

import logging
from typing import Any

from quantlab.agents.parameter_validator import ParameterValidator
from quantlab.dsl.models import (
    BuildingBlock,
    EntryRule,
    ExitRule,
    HypothesisConfig,
    IndicatorConfig,
    Strategy,
    StrategyDirection,
)

logger = logging.getLogger(__name__)


class RuleMode:
    """Deterministic keyword engine for the HypothesisBuilder.

    Maps hypothesis ``description`` and ``parameters`` to known indicator
    configurations using the RB-4 keyword table.

    Each keyword pattern maps to one or more ``BuildingBlock`` instances.
    When no keyword matches, a default RSI block is returned so the caller
    always receives valid output.
    """

    # ── Keyword → Building Block definitions (RB-4) ─────────────────────────

    _KEYWORD_MAP: list[tuple[list[str], list[BuildingBlock]]] = []

    @staticmethod
    def _build_keyword_map() -> (
        list[tuple[list[str], list[BuildingBlock]]]
    ):
        """Build the keyword-to-blocks mapping table.

        Returns a list of (keywords, blocks) pairs. Each pair defines which
        keywords trigger which building blocks. Order matters — first match
        wins for already-matched indicators.
        """
        return [
            # mean-reversion → RSI + BB
            (
                ["mean-reversion", "mean reversion"],
                [
                    BuildingBlock(
                        name="RSI_MeanReversion",
                        indicator=IndicatorConfig(
                            name="RSI",
                            params={
                                "period": 14,
                                "oversold": 30,
                                "overbought": 70,
                            },
                        ),
                        entry=EntryRule(
                            description="RSI oversold entry",
                            conditions=["rsi(14) < 30"],
                        ),
                        exit=ExitRule(
                            description="RSI overbought exit",
                            conditions=["rsi(14) > 70"],
                        ),
                    ),
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
                    ),
                ],
            ),
            # breakout → Donchian + Volume
            (
                ["breakout", "break out"],
                [
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
                    ),
                    BuildingBlock(
                        name="VolumeFilter",
                        indicator=IndicatorConfig(
                            name="Volume",
                            params={"period": 20},
                        ),
                        entry=EntryRule(
                            description="Volume confirmation",
                            conditions=["volume > sma_volume(20)"],
                        ),
                    ),
                ],
            ),
            # momentum / trend → EMA + MACD
            (
                ["momentum", "trend", "trend-following", "trend following"],
                [
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
                    ),
                    BuildingBlock(
                        name="MACDTrend",
                        indicator=IndicatorConfig(
                            name="MACD",
                            params={
                                "fast_period": 12,
                                "slow_period": 26,
                                "signal_period": 9,
                            },
                        ),
                        entry=EntryRule(
                            description="MACD line above signal line",
                            conditions=["macd(12,26,9) > signal(12,26,9)"],
                        ),
                    ),
                ],
            ),
            # volatility → ATR
            (
                ["volatility", "atr"],
                [
                    BuildingBlock(
                        name="ATRFilter",
                        indicator=IndicatorConfig(
                            name="ATR",
                            params={"period": 14},
                        ),
                    ),
                ],
            ),
            # divergence → RSI + MACD
            (
                ["divergence"],
                [
                    BuildingBlock(
                        name="RSI_Divergence",
                        indicator=IndicatorConfig(
                            name="RSI",
                            params={
                                "period": 14,
                                "oversold": 30,
                                "overbought": 70,
                            },
                        ),
                        entry=EntryRule(
                            description="RSI divergence entry",
                            conditions=["rsi(14) < 30"],
                        ),
                    ),
                    BuildingBlock(
                        name="MACD_Divergence",
                        indicator=IndicatorConfig(
                            name="MACD",
                            params={
                                "fast_period": 12,
                                "slow_period": 26,
                                "signal_period": 9,
                            },
                        ),
                        entry=EntryRule(
                            description="MACD divergence confirmation",
                            conditions=["macd(12,26,9) < signal(12,26,9)"],
                        ),
                    ),
                ],
            ),
            # volume
            (
                ["volume"],
                [
                    BuildingBlock(
                        name="VolumeSMA",
                        indicator=IndicatorConfig(
                            name="Volume",
                            params={"period": 20},
                        ),
                        entry=EntryRule(
                            description="Volume above average",
                            conditions=["volume > sma_volume(20)"],
                        ),
                    ),
                ],
            ),
            # pullback → EMA + RSI
            (
                ["pullback"],
                [
                    BuildingBlock(
                        name="EMA_Pullback",
                        indicator=IndicatorConfig(
                            name="EMA",
                            params={"period": 50},
                        ),
                        entry=EntryRule(
                            description="Price near EMA support",
                            conditions=["close > ema(50)"],
                        ),
                    ),
                    BuildingBlock(
                        name="RSI_Pullback",
                        indicator=IndicatorConfig(
                            name="RSI",
                            params={
                                "period": 14,
                                "oversold": 30,
                                "overbought": 70,
                            },
                        ),
                        entry=EntryRule(
                            description="RSI oversold on pullback",
                            conditions=["rsi(14) < 30"],
                        ),
                    ),
                ],
            ),
            # support / resistance → BB + RSI
            (
                ["support", "resistance"],
                [
                    BuildingBlock(
                        name="BB_SupportResistance",
                        indicator=IndicatorConfig(
                            name="BB",
                            params={"period": 20, "deviation": 2.0},
                        ),
                        entry=EntryRule(
                            description="Price at support/resistance via BB",
                            conditions=["close < bb_lower(20, 2)"],
                        ),
                    ),
                    BuildingBlock(
                        name="RSI_SupportResistance",
                        indicator=IndicatorConfig(
                            name="RSI",
                            params={
                                "period": 14,
                                "oversold": 30,
                                "overbought": 70,
                            },
                        ),
                        entry=EntryRule(
                            description="RSI oversold near support",
                            conditions=["rsi(14) < 30"],
                        ),
                    ),
                ],
            ),
        ]

    def __init__(self) -> None:
        self._keyword_map = self._build_keyword_map()
        # Cache indicator names already added to avoid duplicates
        self._indicator_names_seen: set[str] = set()
        self._parameter_validator = None

    # ── Public API ──────────────────────────────────────────────────────────

    def build(
        self, hyp: HypothesisConfig
    ) -> tuple[list[BuildingBlock], list[Strategy]]:
        """Generate building blocks and strategies for a single hypothesis.

        Matches keywords in ``hyp.description`` to the RB-4 table and
        produces the corresponding building blocks. If no keyword matches,
        returns a default RSI block.

        Args:
            hyp: The hypothesis config to process.

        Returns:
            Tuple of ``(list[BuildingBlock], list[Strategy])``.
            Always non-empty (minimum 1 default block).
        """
        self._indicator_names_seen.clear()
        blocks: list[BuildingBlock] = []
        desc_lower = hyp.description.lower()

        for keywords, template_blocks in self._keyword_map:
            if any(kw in desc_lower for kw in keywords):
                for tb in template_blocks:
                    if tb.indicator.name not in self._indicator_names_seen:
                        # Apply parameter overrides from hypothesis
                        block = self._apply_parameter_overrides(tb, hyp)
                        blocks.append(block)
                        self._indicator_names_seen.add(tb.indicator.name)

        # Default fallback if nothing matched
        if not blocks:
            blocks.append(self._default_rsi_block(hyp))
            self._indicator_names_seen.add("RSI")

        # Infer direction
        direction = self._infer_direction(hyp)

        # Generate a strategy referencing all blocks
        strategy = Strategy(
            name=f"Strategy_{hyp.name}" if hyp.name else "PrimaryStrategy",
            direction=direction,
            building_blocks=[b.name for b in blocks],
        )

        return blocks, [strategy]

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _apply_parameter_overrides(
        block: BuildingBlock, hyp: HypothesisConfig
    ) -> BuildingBlock:
        """Override default indicator params with hypothesis parameters.

        Maps hypothesis parameter keys (e.g. ``rsi_period``) to the
        indicator's param dict based on the indicator name prefix.
        Rejects invalid overrides and keeps defaults when validation fails.
        """
        params = block.indicator.params.copy()
        prefix = block.indicator.name.lower()

        for hyp_key, hyp_val in hyp.parameters.items():
            # Match keys like "rsi_period" → period for RSI blocks
            if hyp_key.startswith(prefix):
                param_key = hyp_key[len(prefix) + 1 :]  # strip "rsi_" → "period"
                if param_key and param_key in params:
                    # F2 wiring: validate override before applying
                    if RuleMode._is_valid_override(prefix, param_key, hyp_val):
                        params[param_key] = hyp_val

        if params != block.indicator.params:
            return block.model_copy(
                update={"indicator": block.indicator.model_copy(update={"params": params})}
            )
        return block

    @staticmethod
    def _is_valid_override(indicator: str, param_key: str, value: Any) -> bool:
        """Validate a parameter override against SQXDocProvider."""
        try:
            from quantlab.knowledge.sqX_doc_provider import SQXDocProvider

            validator = ParameterValidator(doc_provider=SQXDocProvider())
            hyp = HypothesisConfig(
                name="override_check",
                description="",
                parameters={f"{indicator}_{param_key}": value},
            )
            result = validator.validate_hypothesis(hyp)
            return result.valid
        except Exception:
            return True

    @staticmethod
    def _infer_direction(hyp: HypothesisConfig) -> StrategyDirection:
        """Infer strategy direction from hypothesis parameters or description.

        Args:
            hyp: The hypothesis config.

        Returns:
            The inferred ``StrategyDirection``.
        """
        # Check parameters first
        dir_param = hyp.parameters.get("direction", "").upper()
        if dir_param == "LONG":
            return StrategyDirection.LONG
        if dir_param == "SHORT":
            return StrategyDirection.SHORT

        # Check description as fallback
        desc_lower = hyp.description.lower()
        if "long" in desc_lower and "short" not in desc_lower:
            return StrategyDirection.LONG
        if "short" in desc_lower and "long" not in desc_lower:
            return StrategyDirection.SHORT

        return StrategyDirection.BOTH

    @staticmethod
    def _default_rsi_block(hyp: HypothesisConfig) -> BuildingBlock:
        """Create a default RSI building block when no keyword matches.

        Args:
            hyp: The hypothesis config (may contain param overrides).

        Returns:
            A ``BuildingBlock`` with a default RSI indicator.
        """
        rsi_params: dict[str, Any] = {"period": 14}
        # Apply rsi_* param overrides
        for key, val in hyp.parameters.items():
            if key.startswith("rsi_"):
                param_key = key[4:]  # strip "rsi_"
                rsi_params[param_key] = val

        return BuildingBlock(
            name="RSI_Default",
            indicator=IndicatorConfig(name="RSI", params=rsi_params),
            entry=EntryRule(
                description="RSI entry signal",
                conditions=[f"rsi({rsi_params['period']}) < 30"],
            ),
        )


__all__ = ["RuleMode"]
