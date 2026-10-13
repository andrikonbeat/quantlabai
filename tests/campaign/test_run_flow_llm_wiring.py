"""T5 (Gap 8): the campaign's LLM config must reach the dispatch boundary.

Covers ``odd/tasks/gap-remediation.md`` S9-S11: ``ResearchConfig.llm_config`` is
the single source of truth for the optional LLM configuration, and the LLM
generation monitor (``quantlab.sqx.llm_generation_monitor``) is only spawnable
when the dispatch substrate actually receives it
(``cli_wrapper._spawn_llm_monitor`` returns ``None`` without an ``llm_config``).

The observable contract asserted here is the dispatch boundary itself: the
kwargs ``DispatchStage`` forwards to ``builder._dispatch_single``, which is the
same channel the substrate reads to spawn the monitor. The absent case pins the
existing behaviour — no hook key is forwarded, so the orchestrated default stays
byte-identical.

Strict TDD: RED — written before ``cmd_campaign_run_flow`` seeded
``ctx.config['llm_config']`` from ``ResearchConfig.llm_config``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from quantlab.dsl.models import LLMConfig
from quantlab.pipeline.base import Pipeline, PipelineContext, Stage
from quantlab.pipeline.stages.dispatch_stage import (
    GATE_DECISION_ARTIFACT,
    DispatchStage,
)

CAMPAIGN_ID = "llm-wiring-1"
MODEL = "gpt-4o-mini"


class _SeedStage(Stage):
    """Provides the dispatch preconditions: CFX bytes + an approved gate."""

    name = "config"
    requires: list[str] = []
    provides: list[str] = ["cfx_bytes"]

    async def execute(self, ctx: PipelineContext) -> dict[str, bool]:
        ctx.artifacts["cfx_bytes"] = b"<cfx/>"
        ctx.artifacts[GATE_DECISION_ARTIFACT] = {"action": "approve"}
        return {"seeded": True}


class _RecordingBuilder:
    """Captures the kwargs the dispatch boundary forwards to the substrate."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def _dispatch_single(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"status": "success", "campaign_id": kwargs.get("campaign_id")}


def _campaign_payload(*, with_llm: bool) -> dict[str, Any]:
    """Minimal valid ``ResearchConfig`` payload, optionally with an LLM block."""
    payload: dict[str, Any] = {
        "campaign": CAMPAIGN_ID,
        "market": "EURUSD",
        "timeframe": "H1",
    }
    if with_llm:
        payload["llm_config"] = {"provider": "openai", "model": MODEL}
    return payload


def _run_flow(
    monkeypatch: Any,
    pipeline: Pipeline,
    tmp_path: Any,
    *,
    with_llm: bool,
) -> int:
    """Invoke ``cmd_campaign_run_flow`` against a controlled pipeline."""
    from quantlab.agents.research_director import ResearchDirector
    from quantlab.campaign import flow as flow_module
    from quantlab.cli.campaign_commands import cmd_campaign_run_flow

    monkeypatch.setattr(flow_module, "assert_flow_segments", lambda *a, **k: None)
    monkeypatch.setattr(ResearchDirector, "build_pipeline", lambda *a, **k: pipeline)

    config_path = tmp_path / "campaign.json"
    config_path.write_text(
        json.dumps(_campaign_payload(with_llm=with_llm)), encoding="utf-8"
    )

    args = argparse.Namespace(
        config=str(config_path),
        campaign=CAMPAIGN_ID,
        market="EURUSD",
        timeframe="H1",
        knowledge_root="knowledge",
        json=True,
        campaign_id=CAMPAIGN_ID,
        gate_decisions_file=None,
        gate_event_dir=str(tmp_path / "gates"),
        gate_timeout=None,
    )
    return asyncio.run(cmd_campaign_run_flow(args))


class TestRunFlowLlmWiring:
    """Gap 8: ``run-flow`` forwards the campaign LLM config to dispatch."""

    def test_campaign_llm_config_reaches_the_dispatch_boundary(
        self, monkeypatch, tmp_path
    ) -> None:
        """GIVEN a campaign config declaring an LLM block
        WHEN ``campaign run-flow`` executes the dispatch phase
        THEN the substrate receives that ``LLMConfig`` — the LLM generation
        monitor is spawnable, not silently skipped.
        """
        builder = _RecordingBuilder()
        pipeline = Pipeline(
            name="campaign", stages=[_SeedStage(), DispatchStage(builder=builder)]
        )

        code = _run_flow(monkeypatch, pipeline, tmp_path, with_llm=True)

        assert code == 0
        assert len(builder.calls) == 1
        forwarded = builder.calls[0].get("llm_config")
        assert isinstance(forwarded, LLMConfig)
        assert forwarded.provider == "openai"
        assert forwarded.model == MODEL

    def test_absent_llm_config_forwards_no_hook(self, monkeypatch, tmp_path) -> None:
        """GIVEN a campaign config with no LLM block (the orchestrated default)
        WHEN ``campaign run-flow`` executes the dispatch phase
        THEN no ``llm_config`` hook is forwarded — existing behaviour holds.
        """
        builder = _RecordingBuilder()
        pipeline = Pipeline(
            name="campaign", stages=[_SeedStage(), DispatchStage(builder=builder)]
        )

        code = _run_flow(monkeypatch, pipeline, tmp_path, with_llm=False)

        assert code == 0
        assert len(builder.calls) == 1
        assert "llm_config" not in builder.calls[0]
