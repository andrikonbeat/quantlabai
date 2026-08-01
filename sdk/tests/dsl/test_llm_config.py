"""Strict TDD — RED phase: LLMConfig validation + HypothesisConfig extension.

Covers spec scenarios from:
- openspec/changes/llm-research-agent/specs/research-dsl/spec.md
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from quantlab.dsl.models import HypothesisConfig, LLMConfig, ResearchConfig
from quantlab.tools.exceptions import ValidationError as QuantLabValError


class TestLLMConfig:
    """LLMConfig model — provider enum, defaults, temperature range."""

    def test_valid_llm_config_parses(self):
        """GIVEN valid LLMConfig with provider='openai', model='gpt-4'
        WHEN instantiated THEN all fields set correctly AND temperature defaults to 0.7.
        """
        config = LLMConfig(provider="openai", model="gpt-4")
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.temperature == 0.7  # default
        assert config.max_tokens == 2048  # default
        assert config.web_sources == []  # default

    def test_invalid_provider_rejected(self):
        """GIVEN LLMConfig with provider='unknown_vendor'
        WHEN validation runs THEN ValidationError raised.
        """
        with pytest.raises(QuantLabValError, match="Unknown LLM provider"):
            LLMConfig(provider="unknown_vendor", model="gpt-4")

    def test_temperature_out_of_range_rejected(self):
        """GIVEN LLMConfig with temperature < 0 or > 2
        WHEN validation runs THEN ValidationError raised.
        """
        with pytest.raises(PydanticValidationError):
            LLMConfig(provider="openai", model="gpt-4", temperature=-0.1)
        with pytest.raises(PydanticValidationError):
            LLMConfig(provider="openai", model="gpt-4", temperature=2.1)

    def test_temperature_at_boundaries_accepted(self):
        """GIVEN temperature at exactly 0.0 or 2.0
        WHEN validated THEN accepted (boundary values).
        """
        config_lo = LLMConfig(provider="openai", model="gpt-4", temperature=0.0)
        assert config_lo.temperature == 0.0
        config_hi = LLMConfig(provider="openai", model="gpt-4", temperature=2.0)
        assert config_hi.temperature == 2.0

    def test_api_key_env_defaults(self):
        """GIVEN LLMConfig without api_key_env
        WHEN instantiated THEN api_key_env is auto-derived from provider.
        """
        config = LLMConfig(provider="openai", model="gpt-4")
        # openai → OPENAI_API_KEY
        assert config.api_key_env == "OPENAI_API_KEY"

    def test_anthropic_provider_accepted(self):
        """GIVEN LLMConfig with provider='anthropic'
        WHEN instantiated THEN accepted and api_key_env derived as ANTHROPIC_API_KEY.
        """
        config = LLMConfig(provider="anthropic", model="claude-3-opus-20240229")
        assert config.provider == "anthropic"
        assert config.api_key_env == "ANTHROPIC_API_KEY"

    def test_web_sources_custom(self):
        """GIVEN LLMConfig with custom web_sources
        WHEN instantiated THEN web_sources preserved.
        """
        config = LLMConfig(
            provider="openai",
            model="gpt-4",
            web_sources=["yahoo_finance", "google_news"],
        )
        assert config.web_sources == ["yahoo_finance", "google_news"]

    def test_explicit_env_not_overridden(self):
        """GIVEN LLMConfig with explicit api_key_env
        WHEN instantiated THEN the explicit value is preserved (not derived).
        """
        config = LLMConfig(provider="openai", api_key_env="MY_CUSTOM_KEY")
        assert config.api_key_env == "MY_CUSTOM_KEY"

    def test_max_tokens_positive(self):
        """GIVEN max_tokens <= 0
        WHEN validated THEN rejected.
        """
        with pytest.raises(PydanticValidationError):
            LLMConfig(provider="openai", model="gpt-4", max_tokens=0)
        with pytest.raises(PydanticValidationError):
            LLMConfig(provider="openai", model="gpt-4", max_tokens=-100)


class TestHypothesisConfigExtension:
    """HypothesisConfig extended with llm_rationale, source_urls, data_sources."""

    def test_full_audit_fields_populated(self):
        """GIVEN a hypothesis with LLM data
        WHEN HypothesisConfig is inspected
        THEN source_urls and data_sources contain provider URLs AND llm_rationale contains reasoning.
        """
        config = HypothesisConfig(
            name="test-hyp",
            description="LLM-generated hypothesis",
            llm_rationale="The RSI indicates oversold conditions with bullish divergence",
            source_urls=["https://finance.yahoo.com/quote/AAPL", "https://news.google.com/AAPL"],
            data_sources=["yahoo_finance", "google_news"],
        )
        assert config.llm_rationale == (
            "The RSI indicates oversold conditions with bullish divergence"
        )
        assert len(config.source_urls) == 2
        assert "https://finance.yahoo.com/quote/AAPL" in config.source_urls
        assert config.data_sources == ["yahoo_finance", "google_news"]

    def test_classic_agent_produces_null_rationale(self):
        """GIVEN a hypothesis from classic ResearchAgent
        WHEN HypothesisConfig is inspected
        THEN llm_rationale is None AND source_urls is empty.
        """
        config = HypothesisConfig(
            name="classic-hyp",
            description="A classic research hypothesis",
            parameters={"lookback": 14},
        )
        assert config.llm_rationale is None
        assert config.source_urls == []
        assert config.data_sources == []

    def test_existing_fields_still_work(self):
        """GIVEN existing HypothesisConfig fields
        WHEN constructed with new fields
        THEN old and new fields coexist.
        """
        config = HypothesisConfig(
            name="hybrid",
            description="Hybrid hypothesis",
            parameters={"threshold": 0.5},
            expected_outcome="profit_factor > 1.5",
            confidence=0.75,
            llm_rationale="Hybrid rationale",
            source_urls=["https://example.com"],
            data_sources=["example"],
        )
        assert config.name == "hybrid"
        assert config.parameters == {"threshold": 0.5}
        assert config.confidence == 0.75
        assert config.llm_rationale == "Hybrid rationale"
        assert config.source_urls == ["https://example.com"]
        assert config.data_sources == ["example"]

    def test_llm_fields_serialize(self) -> None:
        """GIVEN a hypothesis with LLM audit fields
        WHEN serialized to JSON THEN llm_rationale, source_urls, and data_sources survive.
        """
        h = HypothesisConfig(
            name="serialize-test",
            description="Test",
            parameters={},
            expected_outcome="profit",
            confidence=0.6,
            llm_rationale="rate hike expected",
            source_urls=["https://example.com/news/1"],
            data_sources=["rss-news"],
        )
        d = h.model_dump(mode="json")
        assert d["llm_rationale"] == "rate hike expected"
        assert d["source_urls"] == ["https://example.com/news/1"]
        assert d["data_sources"] == ["rss-news"]


class TestLLMConfigInResearchConfig:
    """ResearchConfig integration — llm_config embed, serialization."""

    def test_llm_config_defaults_to_none(self):
        """GIVEN a ResearchConfig without llm_config
        WHEN instantiated THEN llm_config defaults to None.
        """
        rc = ResearchConfig(
            campaign="test",
            market="EURUSD",
            timeframe="H1",
        )
        assert rc.llm_config is None

    def test_llm_config_accepts_llmconfig(self):
        """GIVEN a ResearchConfig with an LLMConfig
        WHEN instantiated THEN llm_config is preserved.
        """
        llm = LLMConfig(provider="openai", model="gpt-4o-mini")
        rc = ResearchConfig(
            campaign="test",
            market="EURUSD",
            timeframe="H1",
            llm_config=llm,
        )
        assert rc.llm_config is not None
        assert rc.llm_config.provider == "openai"
        assert rc.llm_config.model == "gpt-4o-mini"

    def test_llm_config_serialization(self):
        """GIVEN a ResearchConfig with a populated LLMConfig
        WHEN serialized to JSON THEN llm_config fields survive.
        """
        llm = LLMConfig(
            provider="anthropic",
            model="claude-3-haiku-20240307",
            temperature=0.3,
            max_tokens=1000,
            web_sources=["news"],
        )
        rc = ResearchConfig(
            campaign="test",
            market="EURUSD",
            timeframe="H1",
            llm_config=llm,
        )
        d = rc.model_dump(mode="json")
        assert d["llm_config"]["provider"] == "anthropic"
        assert d["llm_config"]["model"] == "claude-3-haiku-20240307"
        assert d["llm_config"]["web_sources"] == ["news"]
