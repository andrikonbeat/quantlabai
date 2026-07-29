"""LLMMode — LLM-based building block generation via prompt + JSON parse.

Constructs a structured prompt from hypothesis config (rationale, sources),
calls the configured LLM provider, and parses the structured JSON response
into validated ``BuildingBlock`` and ``Strategy`` instances.

When the LLM call fails (API error, parse error, SDK missing), the caller
(``HypothesisBuilder`` facade) catches the exception and falls back to
Rule mode (RB-6).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from quantlab.agents.llm_research_agent import LLMResearchAgent
from quantlab.dsl.models import (
    BuildingBlock,
    EntryRule,
    ExitRule,
    HypothesisConfig,
    IndicatorConfig,
    LLMConfig,
    Strategy,
    StrategyDirection,
)

logger = logging.getLogger(__name__)


class LLMMode:
    """LLM-driven building block generation mode.

    Constructs a structured prompt from the hypothesis rationale + source data,
    calls the LLM provider, and parses the structured JSON response into
    validated ``BuildingBlock`` and ``Strategy`` instances.

    Args:
        llm_config: Configuration for the LLM provider (provider, model, etc.).
    """

    def __init__(self, llm_config: LLMConfig) -> None:
        self._llm_config = llm_config
        self._llm_agent = LLMResearchAgent()

    # ── Public API ──────────────────────────────────────────────────────────

    async def build(
        self, hyp: HypothesisConfig
    ) -> tuple[list[BuildingBlock], list[Strategy]]:
        """Generate building blocks and strategies via LLM.

        Builds a prompt from the hypothesis config, calls the LLM provider,
        and parses the structured JSON response.

        Args:
            hyp: The hypothesis config to process.

        Returns:
            Tuple of ``(list[BuildingBlock], list[Strategy])`` from the LLM
            response.

        Raises:
            ValueError: If parsing fails or validation fails.
            ImportError: If the LLM SDK is not installed.
            Exception: On API errors from the LLM provider.
        """
        prompt = self._build_prompt(hyp)
        response_text = await self._llm_agent.call_llm(prompt, self._llm_config)
        return self._parse_response(response_text)

    # ── Prompt construction ─────────────────────────────────────────────────

    def _build_prompt(self, hyp: HypothesisConfig) -> str:
        """Build a structured prompt from a hypothesis config.

        Includes hypothesis details, rationale, source URLs, data sources,
        and the expected JSON response schema.

        Args:
            hyp: The hypothesis config.

        Returns:
            A formatted prompt string ready for LLM consumption.
        """
        sections: list[str] = [
            "You are a quantitative analyst. Generate structured trading "
            "building blocks and strategies based on the following hypothesis.\n",
            f"Hypothesis: {hyp.name}",
            f"Description: {hyp.description}",
            f"Expected Outcome: {hyp.expected_outcome or 'N/A'}",
            f"Rationale: {hyp.llm_rationale or 'N/A'}",
            f"Source URLs: {', '.join(hyp.source_urls) if hyp.source_urls else 'N/A'}",
            f"Data Sources: {', '.join(hyp.data_sources) if hyp.data_sources else 'N/A'}",
            "",
            "Return your response as valid JSON with the following structure:",
            "{",
            '  "building_blocks": [',
            "    {",
            '      "name": "Unique block name",',
            '      "indicator": {"name": "RSI", "params": {"period": 14}},',
            '      "entry": {"description": "...", "conditions": ["..."]},',
            '      "exit": {"description": "...", "conditions": ["..."]}',
            "    }",
            "  ],",
            '  "strategies": [',
            "    {",
            '      "name": "Strategy name",',
            '      "direction": "LONG|SHORT|BOTH",',
            '      "building_blocks": ["block_name_1"]',
            "    }",
            "  ]",
            "}",
            "",
            "IMPORTANT: Each building block must have a unique name and a valid "
            "indicator configuration.",
        ]
        return "\n".join(sections)

    # ── Response parsing ────────────────────────────────────────────────────

    @staticmethod
    def _parse_response(
        response_text: str,
    ) -> tuple[list[BuildingBlock], list[Strategy]]:
        """Parse an LLM JSON response into ``BuildingBlock`` and ``Strategy``.

        Args:
            response_text: The raw JSON string from the LLM.

        Returns:
            Tuple of ``(list[BuildingBlock], list[Strategy])``.

        Raises:
            ValueError: If the response is empty, not valid JSON, or missing
                required fields.
        """
        if not response_text or not response_text.strip():
            raise ValueError("LLM response is empty")

        try:
            data: dict[str, Any] = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Failed to parse LLM response as JSON: {exc}"
            ) from exc

        # Validate required top-level keys
        required = {"building_blocks", "strategies"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(
                f"LLM response missing required fields: "
                f"{', '.join(sorted(missing))}"
            )

        # Parse building blocks
        blocks: list[BuildingBlock] = []
        for b_data in data["building_blocks"]:
            indicator = IndicatorConfig(
                name=b_data["indicator"]["name"],
                params=b_data["indicator"].get("params", {}),
            )
            entry: EntryRule | None = None
            if "entry" in b_data and b_data["entry"]:
                entry = EntryRule(
                    description=b_data["entry"].get("description", ""),
                    conditions=b_data["entry"].get("conditions", []),
                )
            exit_rule: ExitRule | None = None
            if "exit" in b_data and b_data["exit"]:
                exit_rule = ExitRule(
                    description=b_data["exit"].get("description", ""),
                    conditions=b_data["exit"].get("conditions", []),
                )
            blocks.append(
                BuildingBlock(
                    name=b_data["name"],
                    indicator=indicator,
                    entry=entry,
                    exit=exit_rule,
                )
            )

        # Parse strategies
        strategies: list[Strategy] = []
        for s_data in data["strategies"]:
            direction = StrategyDirection(
                s_data.get("direction", "BOTH").upper()
            )
            strategies.append(
                Strategy(
                    name=s_data["name"],
                    direction=direction,
                    building_blocks=s_data.get("building_blocks", []),
                )
            )

        return blocks, strategies


__all__ = ["LLMMode"]
