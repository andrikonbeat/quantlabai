"""Tests for LLMResearchAgent — Tasks 2.3 (RED), 2.4 (RED), 2.5, 2.6 (RED), 2.7.

Covers:
- parse_response(): valid/invalid JSON → ResearchConfig / fallback signal
- build_prompt(): correct template selection and data injection
- call_llm(): API error → clear error for fallback
- output validation: source_urls required, invalid ticker rejected
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

import pytest

from quantlab.agents.llm_research_agent import LLMResearchAgent
from quantlab.dsl.models import (
    HypothesisConfig,
    LLMConfig,
    Market,
    ResearchConfig,
    Timeframe,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def agent() -> LLMResearchAgent:
    return LLMResearchAgent()


def _make_valid_llm_response() -> dict[str, Any]:
    """Build a minimal valid LLM JSON response."""
    return {
        "campaign": "LLM Research: AAPL opportunities",
        "market": "NASDAQ",
        "timeframe": "D1",
        "building_blocks": [
            {
                "name": "RSI_Momentum",
                "indicator": {"name": "RSI", "params": {"period": 14}},
            },
        ],
        "strategies": [
            {
                "name": "Primary",
                "direction": "LONG",
                "building_blocks": ["RSI_Momentum"],
            },
        ],
        "hypotheses": [
            {
                "name": "bullish_momentum",
                "description": "AAPL has strong momentum from earnings beat",
                "parameters": {"rsi_period": 14, "oversold": 30},
                "expected_outcome": "Sharpe > 1.5, win rate > 45%",
                "confidence": 0.75,
                "llm_rationale": "Strong earnings beat with rising iPhone sales "
                                 "and services revenue growth above 15%",
                "source_urls": [
                    "https://finance.yahoo.com/quote/AAPL/",
                    "https://www.nasdaq.com/market-activity/stocks/aapl",
                ],
                "data_sources": ["yahoo-finance", "fred"],
            },
        ],
        "iteration_config": {
            "max_iterations": 3,
            "convergence_threshold": 0.02,
            "early_stop_patience": 2,
            "auto_iterate": True,
        },
    }


# ── Task 2.3 RED: parse_response() ───────────────────────────────────────────


class TestParseResponse:
    """parse_response() — valid/invalid JSON → ResearchConfig / fallback signal."""

    def test_valid_json_returns_research_config(self, agent: LLMResearchAgent) -> None:
        raw = _make_valid_llm_response()
        json_str = json.dumps(raw)
        result = agent.parse_response(json_str)
        assert isinstance(result, ResearchConfig)
        assert result.campaign == "LLM Research: AAPL opportunities"
        assert result.market == Market.NASDAQ
        assert result.timeframe == Timeframe.D1

    def test_valid_json_populates_hypotheses(self, agent: LLMResearchAgent) -> None:
        raw = _make_valid_llm_response()
        json_str = json.dumps(raw)
        result = agent.parse_response(json_str)
        assert len(result.hypotheses) == 1
        h = result.hypotheses[0]
        assert h.name == "bullish_momentum"
        assert h.confidence == 0.75
        assert h.llm_rationale is not None
        assert "earnings" in (h.llm_rationale or "")
        assert len(h.source_urls) == 2
        assert "yahoo-finance" in h.data_sources

    def test_empty_hypotheses_returns_empty_list(self, agent: LLMResearchAgent) -> None:
        raw = _make_valid_llm_response()
        raw["hypotheses"] = []
        json_str = json.dumps(raw)
        result = agent.parse_response(json_str)
        assert result.hypotheses == []

    def test_invalid_json_raises_value_error(self, agent: LLMResearchAgent) -> None:
        with pytest.raises(ValueError, match="Failed to parse LLM response"):
            agent.parse_response("this is not json")

    def test_missing_required_field_raises_value_error(
        self, agent: LLMResearchAgent
    ) -> None:
        raw = _make_valid_llm_response()
        del raw["market"]
        with pytest.raises(ValueError, match="LLM response missing required"):
            agent.parse_response(json.dumps(raw))

    def test_none_input_raises_value_error(self, agent: LLMResearchAgent) -> None:
        with pytest.raises(ValueError, match="LLM response is empty"):
            agent.parse_response(None)  # type: ignore[arg-type]

    def test_empty_string_raises_value_error(self, agent: LLMResearchAgent) -> None:
        with pytest.raises(ValueError, match="LLM response is empty"):
            agent.parse_response("")


# ── Task 2.4 RED: LLM fallback ────────────────────────────────────────────────


class TestCallLLM:
    """call_llm() — API errors → clear error for fallback."""

    @pytest.mark.asyncio
    async def test_no_openai_sdk_raises_import_error(
        self, agent: LLMResearchAgent, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When openai SDK is not installed, call_llm raises ImportError."""
        monkeypatch.setitem(sys.modules, "openai", None)
        llm_config = LLMConfig(provider="openai", model="gpt-4")
        with pytest.raises(ImportError, match="openai"):
            await agent.call_llm("test prompt", llm_config)

    @pytest.mark.asyncio
    async def test_unknown_provider_raises_value_error(
        self, agent: LLMResearchAgent
    ) -> None:
        """An unsupported provider raises ValueError."""
        with pytest.raises(ValueError, match="Anthropic provider"):
            await agent.call_llm("test", LLMConfig(
                provider="anthropic", model="claude-3",
            ))


class TestGenerateConfigFallback:
    """generate_config() fallback to classic ResearchAgent on LLM failure."""

    @pytest.mark.asyncio
    async def test_value_error_during_parse_triggers_fallback(
        self, agent: LLMResearchAgent, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When parse_response fails, generate_config falls back to ResearchAgent."""
        caplog.set_level(logging.WARNING)

        result = await agent.generate_config(
            objectives=["find long opportunities in tech"],
            market_context={"market": "SP500", "timeframe": "D1"},
            llm_config=LLMConfig(provider="openai", model="gpt-4"),
        )
        # Without openai SDK, it should fallback to ResearchAgent
        assert isinstance(result, ResearchConfig)
        assert result.market == Market.SP500

    @pytest.mark.asyncio
    async def test_no_llm_config_triggers_fallback(
        self, agent: LLMResearchAgent
    ) -> None:
        """When no LLMConfig is provided, fall back to classic immediately."""
        result = await agent.generate_config(
            objectives=["find momentum on EURUSD H1"],
        )
        assert isinstance(result, ResearchConfig)
        assert result.market == Market.EURUSD
        assert len(result.hypotheses) > 0

    @pytest.mark.asyncio
    async def test_generate_config_fallback_returns_valid(
        self, agent: LLMResearchAgent
    ) -> None:
        """With no llm_config, generates a valid ResearchConfig via classic agent."""
        result = await agent.generate_config(
            objectives=["find trend on EURUSD H1"],
        )
        assert isinstance(result, ResearchConfig)
        assert result.market == Market.EURUSD
        assert result.timeframe == Timeframe.H1
        assert "EURUSD" in result.campaign or "find" in result.campaign


# ── Task 2.6 RED: output validation ───────────────────────────────────────────


class TestOutputValidation:
    """validate_output() — source_urls required, ticker correctness."""

    def test_missing_source_urls_raises(self, agent: LLMResearchAgent) -> None:
        """A hypothesis without source_urls should be rejected."""
        config = ResearchConfig(
            campaign="test",
            market="EURUSD",
            timeframe="H1",
            hypotheses=[
                HypothesisConfig(
                    name="bad_hyp",
                    description="No sources",
                    parameters={},
                    expected_outcome="profit",
                    confidence=0.5,
                    source_urls=[],  # empty — should fail validation
                ),
            ],
        )
        with pytest.raises(ValueError, match="source_urls"):
            agent.validate_output(config)

    def test_valid_config_passes_validation(
        self, agent: LLMResearchAgent
    ) -> None:
        """A config with all required fields should pass."""
        config = ResearchConfig(
            campaign="test",
            market="EURUSD",
            timeframe="H1",
            hypotheses=[
                HypothesisConfig(
                    name="valid_hyp",
                    description="Has sources",
                    parameters={},
                    expected_outcome="profit",
                    confidence=0.5,
                    source_urls=["https://example.com/data"],
                    data_sources=["test-provider"],
                ),
            ],
        )
        result = agent.validate_output(config)
        assert result is config  # returns same instance

    def test_invalid_ticker_rejected(self, agent: LLMResearchAgent) -> None:
        """A fake ticker not matching known patterns should be rejected."""
        with pytest.raises(ValueError, match="Invalid ticker"):
            agent.validate_output(
                ResearchConfig(
                    campaign="test",
                    market="EURUSD",
                    timeframe="H1",
                    hypotheses=[
                        HypothesisConfig(
                            name="test",
                            description="Bad ticker ref",
                            parameters={"ticker": "INVALID_TICKER_123"},
                            expected_outcome="x",
                            confidence=0.5,
                            source_urls=["https://example.com"],
                        ),
                    ],
                )
            )

    def test_no_hypotheses_passes_validation(
        self, agent: LLMResearchAgent
    ) -> None:
        """An empty hypotheses list should pass (no hypotheses = no source_urls needed)."""
        config = ResearchConfig(
            campaign="test",
            market="EURUSD",
            timeframe="H1",
            hypotheses=[],
        )
        result = agent.validate_output(config)
        assert result is config
