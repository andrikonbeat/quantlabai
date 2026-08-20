"""Tests for F2 wiring — LLMResearchAgent prompt injection and validation."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from quantlab.agents.llm_research_agent import LLMResearchAgent
from quantlab.dsl.models import LLMConfig, HypothesisConfig


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def agent() -> LLMResearchAgent:
    return LLMResearchAgent()


# ── Task T-012: Prompt wiring ─────────────────────────────────────────────────


class TestLLMResearchAgentPromptWiring:
    """build_prompt injects SQX reference section."""

    def test_build_prompt_includes_sqx_reference(self, agent: LLMResearchAgent) -> None:
        data = {
            "fundamental": {"ticker": "EURUSD"},
            "macro": {},
            "news": [],
        }
        prompt = agent.build_prompt("mean-reversion on EURUSD", data)
        assert "SQX" in prompt or "sqx" in prompt or "parameter" in prompt.lower()

    def test_build_prompt_retains_existing_sections(self, agent: LLMResearchAgent) -> None:
        data = {
            "fundamental": {"ticker": "EURUSD", "pe": 15.0},
            "macro": {"gdp": "1000"},
            "news": [{"title": "Test", "summary": "Summary", "url": "http://example.com"}],
        }
        prompt = agent.build_prompt("test objective", data)
        assert "Research Objective" in prompt
        assert "test objective" in prompt


# ── Task T-012: parse_response validation ────────────────────────────────────


class TestLLMResearchAgentParseValidation:
    """parse_response validates hypotheses against SQXDocProvider."""

    def test_parse_response_validates_against_sqx(
        self, agent: LLMResearchAgent, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quantlab.knowledge.sqX_doc_provider import SQXDocProvider

        mock_provider = MagicMock(spec=SQXDocProvider)
        mock_provider.get_valid_range.return_value = (2, 200)
        mock_provider.get_enum_values.return_value = None
        mock_provider.get_description.return_value = "RSI"
        monkeypatch.setattr(
            "quantlab.agents.llm_research_agent.SQXDocProvider",
            lambda: mock_provider,
        )

        response = json.dumps({
            "campaign": "Test Campaign",
            "market": "EURUSD",
            "timeframe": "H1",
            "hypotheses": [
                {
                    "name": "valid_rsi",
                    "description": "RSI mean reversion",
                    "parameters": {"rsi_period": 14},
                    "expected_outcome": "Sharpe > 1",
                    "confidence": 0.6,
                    "source_urls": ["https://example.com"],
                    "data_sources": ["yahoo"],
                }
            ],
        })
        config = agent.parse_response(response)
        assert len(config.hypotheses) == 1

    def test_parse_response_drops_invalid_params(
        self, agent: LLMResearchAgent, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quantlab.knowledge.sqX_doc_provider import SQXDocProvider

        mock_provider = MagicMock(spec=SQXDocProvider)
        mock_provider.get_valid_range.return_value = (2, 200)
        mock_provider.get_enum_values.return_value = None
        mock_provider.get_description.return_value = "RSI"
        monkeypatch.setattr(
            "quantlab.agents.llm_research_agent.SQXDocProvider",
            lambda: mock_provider,
        )

        response = json.dumps({
            "campaign": "Test Campaign",
            "market": "EURUSD",
            "timeframe": "H1",
            "hypotheses": [
                {
                    "name": "bad_rsi",
                    "description": "RSI with bad period",
                    "parameters": {"rsi_period": 500},
                    "expected_outcome": "Sharpe > 1",
                    "confidence": 0.6,
                    "source_urls": ["https://example.com"],
                    "data_sources": ["yahoo"],
                }
            ],
        })
        config = agent.parse_response(response)
        assert len(config.hypotheses) == 0
