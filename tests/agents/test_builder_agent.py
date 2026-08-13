"""WU8a RED: BuilderAgent 14-phase config + contracts.

Tests for WU8a: BuilderAgent.generate_pipeline_config() should emit 14-phase
config when QUANTLAB_14PHASE=1, and 8-phase config otherwise.
"""

from __future__ import annotations

import os

import pytest

from quantlab.agents.builder_agent import BuilderAgent


def _valid_research_config(campaign: str = "test-campaign") -> dict:
    """Build a minimal valid ResearchConfig dict for BuilderAgent tests."""
    return {
        "campaign": campaign,
        "market": "EURUSD",
        "timeframe": "M15",
    }


class TestBuilderAgent14PhaseConfig:
    """WU8a: BuilderAgent 14-phase emission order/determinism, backward-compat, feature-flag."""

    def test_8_phase_by_default(self, monkeypatch: pytest.MonkeyPatch):
        """Default config emits 8 agent stages (backward compatibility)."""
        monkeypatch.delenv("QUANTLAB_14PHASE", raising=False)
        agent = BuilderAgent()
        config = agent.generate_pipeline_config(_valid_research_config())
        stage_names = [s["name"] for s in config["pipeline"]["stages"]]
        assert len(stage_names) == 8
        assert stage_names == [
            "research", "builder", "statistics", "analysis",
            "review", "portfolio", "deploy", "monitor",
        ]

    def test_14_phase_when_flag_enabled(self, monkeypatch: pytest.MonkeyPatch):
        """QUANTLAB_14PHASE=1 appends compile, demo, archive, live_ops stages."""
        monkeypatch.setenv("QUANTLAB_14PHASE", "1")
        agent = BuilderAgent()
        config = agent.generate_pipeline_config(_valid_research_config())
        stage_names = [s["name"] for s in config["pipeline"]["stages"]]
        assert len(stage_names) == 12
        assert stage_names == [
            "research", "builder", "statistics", "analysis",
            "review", "portfolio", "deploy", "monitor",
            "compile", "demo", "archive", "live_ops",
        ]

    def test_14_phase_emission_determinism(self, monkeypatch: pytest.MonkeyPatch):
        """14-phase stage order is deterministic across multiple calls."""
        monkeypatch.setenv("QUANTLAB_14PHASE", "1")
        agent = BuilderAgent()
        configs = [agent.generate_pipeline_config(_valid_research_config()) for _ in range(3)]
        stage_names_list = [
            [s["name"] for s in cfg["pipeline"]["stages"]] for cfg in configs
        ]
        assert all(names == stage_names_list[0] for names in stage_names_list)

    def test_feature_flag_gate(self, monkeypatch: pytest.MonkeyPatch):
        """Only QUANTLAB_14PHASE=1 enables extended phases; '0' or missing keeps 8-phase."""
        monkeypatch.delenv("QUANTLAB_14PHASE", raising=False)
        agent = BuilderAgent()
        config_default = agent.generate_pipeline_config(_valid_research_config())
        assert len(config_default["pipeline"]["stages"]) == 8

        monkeypatch.setenv("QUANTLAB_14PHASE", "0")
        config_off = agent.generate_pipeline_config(_valid_research_config())
        assert len(config_off["pipeline"]["stages"]) == 8
