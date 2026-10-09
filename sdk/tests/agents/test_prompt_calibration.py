"""Tests for TagCalibrator injection into build_prompt (T9 task 3.5)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


class TestBuildPromptCalibration:
    def _agent(self):
        from quantlab.agents.llm_research_agent import LLMResearchAgent

        return LLMResearchAgent()

    def _data(self) -> dict:
        return {"fundamental": {}, "macro": {}, "news": [],
                "literature": [], "screener": {}, "ticker": ""}

    def test_calibration_section_rendered(self) -> None:
        agent = self._agent()
        prompt = agent.build_prompt(
            "momentum", self._data(),
            tag_stats={"trend": {"avg_sharpe": 1.8, "sample_count": 4}},
        )
        assert "TAG_CALIBRATION" in prompt
        assert "trend" in prompt
        assert "1.8" in prompt

    def test_calibration_section_omitted_when_none(self) -> None:
        agent = self._agent()
        prompt = agent.build_prompt("momentum", self._data())
        assert "TAG_CALIBRATION" not in prompt

    def test_similar_campaigns_rendered(self) -> None:
        agent = self._agent()
        prompt = agent.build_prompt(
            "momentum", self._data(), similar_campaigns=["camp-9", "camp-3"]
        )
        assert "camp-9" in prompt
        assert "camp-3" in prompt

    def test_similar_omitted_when_none(self) -> None:
        agent = self._agent()
        prompt = agent.build_prompt("momentum", self._data())
        assert "camp-9" not in prompt


class TestLakeCalibration:
    def test_returns_tuple_without_raising(self) -> None:
        from quantlab.agents.llm_research_agent import LLMResearchAgent

        tag_stats, similar = LLMResearchAgent()._lake_calibration(
            "momentum", {"market": "EURUSD", "timeframe": "H1"}
        )
        assert isinstance(tag_stats, dict)
        assert isinstance(similar, list)

    @pytest.mark.asyncio
    async def test_generate_config_injects_calibration(self) -> None:
        from quantlab.agents.llm_research_agent import LLMResearchAgent
        from quantlab.dsl.models import LLMConfig

        agent = LLMResearchAgent()
        captured: dict[str, str] = {}

        async def fake_call_llm(self, prompt: str, cfg):  # type: ignore[no-untyped-def]
            captured["prompt"] = prompt
            return json.dumps(
                {"campaign": "c", "market": "EURUSD",
                 "timeframe": "H1", "hypotheses": []}
            )

        with (
            patch.object(
                LLMResearchAgent, "fetch_data",
                AsyncMock(return_value={
                    "fundamental": {}, "macro": {}, "news": [],
                    "literature": [], "screener": {}, "ticker": ""}),
            ),
            patch.object(
                LLMResearchAgent, "_lake_calibration",
                return_value=(
                    {"trend": {"avg_sharpe": 1.8, "sample_count": 4}},
                    ["camp-9"],
                ),
            ),
            patch.object(LLMResearchAgent, "call_llm", fake_call_llm),
        ):
            await agent.generate_config(
                ["momentum EURUSD"],
                market_context={"market": "EURUSD"},
                llm_config=LLMConfig(provider="openai"),
            )
        assert "TAG_CALIBRATION" in captured["prompt"]
        assert "trend" in captured["prompt"]
        assert "camp-9" in captured["prompt"]
