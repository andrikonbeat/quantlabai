"""Tests for the archive feedback hook (T9 task 4.2)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from quantlab.gates.models import GateDecision, GateDecisionAction
from quantlab.gates.orchestrator import HumanGateOrchestrator


def _approve(gate_id: str) -> GateDecision:
    return GateDecision(gate_id=gate_id, action=GateDecisionAction.APPROVE,
                        reason="looks good")


def _reject(gate_id: str) -> GateDecision:
    return GateDecision(gate_id=gate_id, action=GateDecisionAction.REJECT,
                        reason="not yet")


def _ctx(tmp_path: Path) -> dict:
    return {
        "campaign_id": "camp-1",
        "knowledge_root": str(tmp_path),
        "hypotheses": [
            {"name": "mean_reversion_rsi", "sharpe_ratio": 1.8},
            {"name": "donchian_breakout", "sharpe_ratio": 1.2},
        ],
    }


class TestArchiveFeedbackHook:
    def test_approved_archive_writes_feedback(self, tmp_path: Path) -> None:
        import asyncio

        orch = HumanGateOrchestrator()

        async def _cb(ctx):
            return _approve("HUMAN_APPROVE_ARCHIVE")

        orch.register_callback("HUMAN_APPROVE_ARCHIVE", _cb)
        decision = asyncio.run(orch.on_gate("HUMAN_APPROVE_ARCHIVE", _ctx(tmp_path)))

        assert decision.is_approved()
        meta_path = tmp_path / "structured" / "camp-1" / "metadata.yaml"
        assert meta_path.exists()
        data = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
        assert len(data["feedback"]) == 2
        names = {f["hypothesis_id"] for f in data["feedback"]}
        assert names == {"mean_reversion_rsi", "donchian_breakout"}
        assert all(f["feedback_type"] == "pass" for f in data["feedback"])

    def test_rejected_archive_writes_nothing(self, tmp_path: Path) -> None:
        import asyncio

        orch = HumanGateOrchestrator()

        async def _cb(ctx):
            return _reject("HUMAN_APPROVE_ARCHIVE")

        orch.register_callback("HUMAN_APPROVE_ARCHIVE", _cb)
        decision = asyncio.run(orch.on_gate("HUMAN_APPROVE_ARCHIVE", _ctx(tmp_path)))

        assert not decision.is_approved()
        assert not (tmp_path / "structured" / "camp-1" / "metadata.yaml").exists()

    def test_non_archive_gate_writes_nothing(self, tmp_path: Path) -> None:
        import asyncio

        orch = HumanGateOrchestrator()

        async def _cb(ctx):
            return _approve("HUMAN_APPROVE_DEPLOY")

        orch.register_callback("HUMAN_APPROVE_DEPLOY", _cb)
        asyncio.run(orch.on_gate("HUMAN_APPROVE_DEPLOY", _ctx(tmp_path)))

        assert not (tmp_path / "structured").exists()

    def test_writer_failure_never_breaks_gate(self, tmp_path: Path) -> None:
        import asyncio

        orch = HumanGateOrchestrator()

        async def _cb(ctx):
            return _approve("HUMAN_APPROVE_ARCHIVE")

        orch.register_callback("HUMAN_APPROVE_ARCHIVE", _cb)
        with patch(
            "quantlab.agents.feedback_writer.KnowledgeLakeFeedbackWriter",
            side_effect=RuntimeError("disk on fire"),
        ):
            decision = asyncio.run(
                orch.on_gate("HUMAN_APPROVE_ARCHIVE", _ctx(tmp_path))
            )
        assert decision.is_approved()

    def test_hypotheses_as_objects_supported(self, tmp_path: Path) -> None:
        import asyncio

        from quantlab.dsl.models import HypothesisConfig

        orch = HumanGateOrchestrator()

        async def _cb(ctx):
            return _approve("HUMAN_APPROVE_ARCHIVE")

        orch.register_callback("HUMAN_APPROVE_ARCHIVE", _cb)
        ctx = _ctx(tmp_path)
        ctx["hypotheses"] = [
            HypothesisConfig(name="h1", description="d", parameters={},
                             expected_outcome="", confidence=0.5)
        ]
        asyncio.run(orch.on_gate("HUMAN_APPROVE_ARCHIVE", ctx))
        data = yaml.safe_load(
            (tmp_path / "structured" / "camp-1" / "metadata.yaml").read_text(
                encoding="utf-8"
            )
        )
        assert data["feedback"][0]["hypothesis_id"] == "h1"
