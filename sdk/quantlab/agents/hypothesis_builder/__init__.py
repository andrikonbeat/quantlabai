"""HypothesisBuilder — bridges hypotheses to validated building blocks.

Transforms qualitative ``HypothesisConfig`` instances into structured
``BuildingBlock`` and ``Strategy`` objects via dual-mode dispatch:

- **Rule mode** (deterministic): keyword matching on hypothesis description.
- **LLM mode**: LLM-generated blocks from rationale (with rule fallback).

Usage::

    builder = HypothesisBuilder(mode="rule")
    blocks, strategies = await builder.build(hypotheses, market_context)
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from quantlab.dsl.models import BuildingBlock, HypothesisConfig, LLMConfig, Strategy
from quantlab.agents.hypothesis_builder.llm import LLMMode
from quantlab.agents.hypothesis_builder.rule import RuleMode
from quantlab.agents.hypothesis_builder.validate import BuildingBlockValidator

logger = logging.getLogger(__name__)


class HypothesisBuilder:
    """Facade that dispatches to the appropriate mode (rule | llm).

    Defaults to rule mode when no LLM config is available.
    LLM mode falls back to rule mode on any error (RB-6).

    Args:
        mode: Operation mode — ``"rule"`` (default) or ``"llm"``.
        llm_config: Optional ``LLMConfig`` for LLM mode.
    """

    def __init__(
        self,
        mode: Literal["rule", "llm"] = "rule",
        llm_config: LLMConfig | None = None,
    ) -> None:
        self._mode = mode
        self._rule_mode = RuleMode()
        self._validator = BuildingBlockValidator()
        self._llm_mode: LLMMode | None = (
            LLMMode(llm_config) if llm_config is not None else None
        )

    async def build(
        self,
        hypotheses: list[HypothesisConfig],
        market_context: dict[str, Any] | None = None,
        mode: Literal["rule", "llm"] | None = None,
    ) -> tuple[list[BuildingBlock], list[Strategy]]:
        """Transform hypotheses into validated building blocks and strategies.

        Args:
            hypotheses: List of hypothesis configs to process.
            market_context: Optional market metadata (e.g. market, timeframe).
            mode: Optional per-call mode override. If ``None``, uses the
                construction-time mode.

        Returns:
            Tuple of ``(list[BuildingBlock], list[Strategy])``.
            Always returns a valid result — fallback to rule on any error.
        """
        if not hypotheses:
            return [], []

        active_mode = mode or self._mode

        if active_mode == "llm" and self._llm_mode is not None:
            return await self._build_with_llm(hypotheses)

        return self._build_with_rule(hypotheses)

    # ── LLM mode with fallback (RB-6) ───────────────────────────────────────

    async def _build_with_llm(
        self,
        hypotheses: list[HypothesisConfig],
    ) -> tuple[list[BuildingBlock], list[Strategy]]:
        """Build using LLM mode, falling back to rule on any error.

        Args:
            hypotheses: List of hypothesis configs.

        Returns:
            Tuple of validated blocks and strategies from LLM, or from rule
            mode if LLM fails.
        """
        all_blocks: list[BuildingBlock] = []
        all_strategies: list[Strategy] = []

        try:
            for hyp in hypotheses:
                blocks, strategies = await self._llm_mode.build(hyp)
                all_blocks.extend(blocks)
                all_strategies.extend(strategies)
        except Exception:
            logger.warning(
                "LLM mode failed — falling back to rule mode",
                exc_info=True,
            )
            return self._build_with_rule(hypotheses)

        return self._merge_and_validate(all_blocks, all_strategies)

    # ── Rule mode (deterministic) ───────────────────────────────────────────

    def _build_with_rule(
        self,
        hypotheses: list[HypothesisConfig],
    ) -> tuple[list[BuildingBlock], list[Strategy]]:
        """Build using rule mode (deterministic keyword matching).

        Args:
            hypotheses: List of hypothesis configs.

        Returns:
            Tuple of validated blocks and strategies from rule matching.
        """
        all_blocks: list[BuildingBlock] = []
        all_strategies: list[Strategy] = []

        for hyp in hypotheses:
            blocks, strategies = self._rule_mode.build(hyp)
            all_blocks.extend(blocks)
            all_strategies.extend(strategies)

        return self._merge_and_validate(all_blocks, all_strategies)

    # ── Merge, dedup, validate ──────────────────────────────────────────────

    def _merge_and_validate(
        self,
        all_blocks: list[BuildingBlock],
        all_strategies: list[Strategy],
    ) -> tuple[list[BuildingBlock], list[Strategy]]:
        """Deduplicate blocks by name, merge strategies, and validate.

        Args:
            all_blocks: Raw building blocks (may contain duplicates).
            all_strategies: Raw strategies (may contain duplicates).

        Returns:
            Tuple of deduplicated, merged, and validated blocks/strategies.
        """
        # Deduplicate blocks by name
        seen_names: set[str] = set()
        deduped_blocks: list[BuildingBlock] = []
        for b in all_blocks:
            if b.name not in seen_names:
                seen_names.add(b.name)
                deduped_blocks.append(b)

        # Merge strategies: keep unique strategies by name
        seen_strat_names: set[str] = set()
        merged_strategies: list[Strategy] = []
        for s in all_strategies:
            if s.name not in seen_strat_names:
                seen_strat_names.add(s.name)
                merged_strategies.append(s)
            else:
                existing = next(
                    es for es in merged_strategies if es.name == s.name
                )
                for ref in s.building_blocks:
                    if ref not in existing.building_blocks:
                        existing.building_blocks.append(ref)

        # Always validate — raises if something is wrong
        try:
            self._validator.validate(deduped_blocks, merged_strategies)
        except ValueError:
            logger.exception(
                "Validation failed — unexpected. "
                "Blocks: %d, Strategies: %d",
                len(deduped_blocks),
                len(merged_strategies),
            )

        return deduped_blocks, merged_strategies


__all__ = ["HypothesisBuilder"]
