"""Tests for LLMConfig model and HypothesisConfig LLM extensions."""

from __future__ import annotations

import pytest

from quantlab.dsl.models import HypothesisConfig, LLMConfig, ResearchConfig
from quantlab.tools.exceptions import ValidationError


class TestLLMConfigDefaults:
    def test_default_openai(self) -> None:
        cfg = LLMConfig()
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-4"
        assert cfg.api_key_env == "OPENAI_API_KEY"
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 2048
        assert cfg.web_sources == []

    def test_anthropic_derives_env(self) -> None:
        cfg = LLMConfig(provider="anthropic", model="claude-3-opus-20240229")
        assert cfg.api_key_env == "ANTHROPIC_API_KEY"

    def test_explicit_env_not_overridden(self) -> None:
        cfg = LLMConfig(provider="openai", api_key_env="MY_CUSTOM_KEY")
        assert cfg.api_key_env == "MY_CUSTOM_KEY"


class TestLLMConfigValidation:
    def test_invalid_provider_raises(self) -> None:
        with pytest.raises(ValidationError, match="Unknown LLM provider"):
            LLMConfig(provider="unknown-llm")

    def test_temperature_clamped(self) -> None:
        with pytest.raises(ValueError):
            LLMConfig(temperature=3.0)

    def test_max_tokens_min(self) -> None:
        with pytest.raises(ValueError):
            LLMConfig(max_tokens=0)

    def test_web_sources_accepts_list(self) -> None:
        cfg = LLMConfig(web_sources=["news", "macro", "sec"])
        assert cfg.web_sources == ["news", "macro", "sec"]


class TestLLMConfigInResearchConfig:
    def test_llm_config_defaults_to_none(self) -> None:
        rc = ResearchConfig(
            campaign="test",
            market="EURUSD",
            timeframe="H1",
        )
        assert rc.llm_config is None

    def test_llm_config_accepts_llmconfig(self) -> None:
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

    def test_llm_config_serialization(self) -> None:
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


class TestHypothesisConfigLLMExtensions:
    def test_llm_fields_default_none(self) -> None:
        h = HypothesisConfig(
            name="test-hyp",
            description="A test hypothesis",
            parameters={},
            expected_outcome="profit",
            confidence=0.5,
        )
        assert h.llm_rationale is None
        assert h.source_urls == []
        assert h.data_sources == []

    def test_llm_fields_accept_values(self) -> None:
        h = HypothesisConfig(
            name="llm-hyp",
            description="LLM-generated hypothesis",
            parameters={},
            expected_outcome="profit",
            confidence=0.8,
            llm_rationale="Based on rising CPI and weak USD",
            source_urls=["https://fred.stlouisfed.org/series/CPIAUCSL"],
            data_sources=["fred"],
        )
        assert h.llm_rationale == "Based on rising CPI and weak USD"
        assert len(h.source_urls) == 1
        assert "fred" in h.data_sources

    def test_llm_fields_serialize(self) -> None:
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
