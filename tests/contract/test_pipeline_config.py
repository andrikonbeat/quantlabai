"""WU8b Contract: verify 14-phase under QUANTLAB_14PHASE=1 and 8-phase under QUANTLAB_14PHASE=0.

Validates that BuilderAgent.generate_pipeline_config() output matches the
expected stage schema, artifact contracts, and gate positions.
"""

from __future__ import annotations

import os

import pytest

from quantlab.agents.builder_agent import BuilderAgent


def _valid_research_config(campaign: str = "test-campaign") -> dict:
    return {
        "campaign": campaign,
        "market": "EURUSD",
        "timeframe": "M15",
    }


class TestBuilderAgentPipelineContract:
    """WU8b: 14-phase vs 8-phase contract validation."""

    def test_8_phase_stage_schema(self, monkeypatch: pytest.MonkeyPatch):
        """8-phase config stages have required keys: name, type, agent, requires, provides."""
        monkeypatch.delenv("QUANTLAB_14PHASE", raising=False)
        agent = BuilderAgent()
        config = agent.generate_pipeline_config(_valid_research_config())
        for stage in config["pipeline"]["stages"]:
            assert "name" in stage
            assert "type" in stage
            assert "agent" in stage
            assert "requires" in stage
            assert "provides" in stage

    def test_14_phase_stage_schema(self, monkeypatch: pytest.MonkeyPatch):
        """14-phase config stages have required keys."""
        monkeypatch.setenv("QUANTLAB_14PHASE", "1")
        agent = BuilderAgent()
        config = agent.generate_pipeline_config(_valid_research_config())
        for stage in config["pipeline"]["stages"]:
            assert "name" in stage
            assert "type" in stage
            assert "agent" in stage
            assert "requires" in stage
            assert "provides" in stage

    def test_14_phase_preserves_original_8_stages(self, monkeypatch: pytest.MonkeyPatch):
        """14-phase config preserves the original 8 stage names in order."""
        monkeypatch.setenv("QUANTLAB_14PHASE", "1")
        agent = BuilderAgent()
        config = agent.generate_pipeline_config(_valid_research_config())
        stage_names = [s["name"] for s in config["pipeline"]["stages"]]
        original = ["research", "builder", "statistics", "analysis",
                    "review", "portfolio", "deploy", "monitor"]
        assert stage_names[:8] == original

    def test_14_phase_new_stages_after_monitor(self, monkeypatch: pytest.MonkeyPatch):
        """14-phase appends compile, demo, archive, live_ops after monitor."""
        monkeypatch.setenv("QUANTLAB_14PHASE", "1")
        agent = BuilderAgent()
        config = agent.generate_pipeline_config(_valid_research_config())
        stage_names = [s["name"] for s in config["pipeline"]["stages"]]
        assert stage_names[8:] == ["compile", "demo", "archive", "live_ops"]

    def test_14_phase_artifact_contracts(self, monkeypatch: pytest.MonkeyPatch):
        """New 14-phase stages declare correct artifact provides."""
        monkeypatch.setenv("QUANTLAB_14PHASE", "1")
        agent = BuilderAgent()
        config = agent.generate_pipeline_config(_valid_research_config())
        stage_map = {s["name"]: s for s in config["pipeline"]["stages"]}
        assert "compiled_strategies" in stage_map["compile"]["provides"]
        assert "compilation_failed" in stage_map["compile"]["provides"]
        assert "demo_result" in stage_map["demo"]["provides"]
        assert "campaign_archive" in stage_map["archive"]["provides"]
        assert "live_equity" in stage_map["live_ops"]["provides"]
