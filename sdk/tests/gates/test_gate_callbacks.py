"""Tests for gate callbacks — decision-file IPC + fail-closed (REQ-10, REQ-11).

Covers:
- Decision-file protocol round trip under ``{gate_event_dir}/{campaign_id}/``
  (pending.json written by the callback, decision.json consumed).
- Question-tool callback as primary (AD-4); no decision file → timeout
  (fail-closed via the orchestrator's HOLD policy fallback).
- Stdin fallback for headless mode.
- ``fail_closed_callback`` returns HOLD and never auto-approves (REQ-11).
- Legacy CLI path (no orchestrator, no callbacks) still auto-approves —
  the fail-closed flag is orchestrated-mode ONLY (REQ-11 scenario).
- campaign_id sanitisation rejects ``../`` traversal (boundary 2).
"""

import asyncio
import json
import io

import pytest

from quantlab.gates.callbacks import (
    QuestionToolGateCallback,
    StdinGateCallback,
    decision_path,
    fail_closed_callback,
    pending_path,
    sanitize_campaign_id,
)
from quantlab.gates.models import GateDecisionAction

GATE_ID = "HUMAN_APPROVE_CONFIG"


def _ctx(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "gate_id": GATE_ID,
        "campaign_id": "camp-1",
        "stage_name": "config_review",
    }
    base.update(overrides)
    return base


class TestDecisionFileProtocol:
    """REQ-10: decision-file round trip under /tmp/sqx-gates/{campaign_id}/."""

    @pytest.mark.asyncio
    async def test_pending_to_decision_round_trip(self, tmp_path) -> None:
        """GIVEN a pending gate with an agent resolving via the question tool
        WHEN the agent writes the decision file
        THEN the callback returns the human decision to the pipeline.
        """
        callback = QuestionToolGateCallback(
            gate_event_dir=str(tmp_path),
            campaign_id="camp-1",
            poll_interval=0.01,
            timeout=10,
        )
        task = asyncio.create_task(callback(_ctx()))

        pending = pending_path(str(tmp_path), "camp-1", GATE_ID)
        for _ in range(200):
            if pending.exists():
                break
            await asyncio.sleep(0.01)
        assert pending.exists(), "callback must write the pending file"

        pending_data = json.loads(pending.read_text())
        assert pending_data["gate_id"] == GATE_ID
        assert pending_data["campaign_id"] == "camp-1"
        assert pending_data["status"] == "pending"
        assert pending_data["envelope"]["gate_id"] == GATE_ID

        decision_file = decision_path(str(tmp_path), "camp-1", GATE_ID)
        decision_file.write_text(
            json.dumps(
                {
                    "action": "approve",
                    "reason": "human ok",
                    "decided_by": "human",
                    "proposed_changes": {"sl_value_type": "pips"},
                }
            )
        )

        decision = await asyncio.wait_for(task, timeout=10)
        assert decision.gate_id == GATE_ID
        assert decision.action == GateDecisionAction.APPROVE
        assert decision.reason == "human ok"
        assert decision.decided_by == "human"
        assert decision.metadata["proposed_changes"] == {"sl_value_type": "pips"}

    @pytest.mark.asyncio
    async def test_modify_decision_carries_proposed_changes(self, tmp_path) -> None:
        """GIVEN a MODIFY decision file with concrete changes
        WHEN the callback consumes it
        THEN the decision is MODIFY with proposed_changes in metadata.
        """
        callback = QuestionToolGateCallback(
            gate_event_dir=str(tmp_path),
            campaign_id="camp-1",
            poll_interval=0.01,
            timeout=10,
        )
        task = asyncio.create_task(callback(_ctx()))

        pending = pending_path(str(tmp_path), "camp-1", GATE_ID)
        for _ in range(200):
            if pending.exists():
                break
            await asyncio.sleep(0.01)

        decision_file = decision_path(str(tmp_path), "camp-1", GATE_ID)
        decision_file.write_text(
            json.dumps(
                {
                    "action": "modify",
                    "reason": "reduce SL range",
                    "decided_by": "human",
                    "proposed_changes": {"max_sl_pips": 40},
                }
            )
        )

        decision = await asyncio.wait_for(task, timeout=10)
        assert decision.action == GateDecisionAction.MODIFY
        assert decision.metadata["proposed_changes"] == {"max_sl_pips": 40}

    @pytest.mark.asyncio
    async def test_no_decision_fails_closed_with_timeout(self, tmp_path) -> None:
        """GIVEN orchestrated mode with no agent decision file
        WHEN the question-tool callback polls past its timeout
        THEN it raises TimeoutError so the orchestrator applies the HOLD
        fallback — never auto-approve (REQ-11).
        """
        callback = QuestionToolGateCallback(
            gate_event_dir=str(tmp_path),
            campaign_id="camp-1",
            poll_interval=0.01,
            timeout=0.1,
        )
        with pytest.raises(asyncio.TimeoutError):
            await callback(_ctx())

    @pytest.mark.asyncio
    async def test_campaign_id_from_context_when_not_constructed(self, tmp_path) -> None:
        """GIVEN a callback without a fixed campaign_id
        WHEN it fires with campaign_id in the context
        THEN the pending file lands under the context campaign id.
        """
        callback = QuestionToolGateCallback(
            gate_event_dir=str(tmp_path),
            poll_interval=0.01,
            timeout=0.2,
        )
        pending = pending_path(str(tmp_path), "camp-1", GATE_ID)
        assert not pending.exists()

        with pytest.raises(asyncio.TimeoutError):
            await callback(_ctx())  # no decision written; pending still created first
        assert pending.exists()


class TestStdinFallback:
    """REQ-10: stdin fallback for headless mode."""

    @staticmethod
    async def _line_reader(text: str):
        buf = io.StringIO(text)

        async def reader() -> str:
            return buf.readline()

        return reader

    @pytest.mark.asyncio
    async def test_stdin_fallback_reads_approve_decision(self) -> None:
        """GIVEN headless mode with a decision envelope on stdin
        WHEN StdinGateCallback fires
        THEN the human decision is returned to the pipeline.
        """
        reader = await self._line_reader(
            '{"action": "approve", "reason": "stdin ok", "decided_by": "human"}\n'
        )
        callback = StdinGateCallback(reader=reader)

        decision = await callback(_ctx())

        assert decision.action == GateDecisionAction.APPROVE
        assert decision.reason == "stdin ok"
        assert decision.decided_by == "human"

    @pytest.mark.asyncio
    async def test_stdin_fallback_reads_modify_decision(self) -> None:
        """GIVEN a MODIFY envelope on stdin
        WHEN StdinGateCallback fires
        THEN the modify decision with changes is returned.
        """
        reader = await self._line_reader(
            '{"action": "modify", "reason": "stdin adjust", "proposed_changes": {"sl_value_type": "atr"}}\n'
        )
        callback = StdinGateCallback(reader=reader)

        decision = await callback(_ctx())

        assert decision.action == GateDecisionAction.MODIFY
        assert decision.metadata["proposed_changes"] == {"sl_value_type": "atr"}


class TestFailClosed:
    """REQ-11: unregistered gates fail closed in orchestrated mode."""

    @pytest.mark.asyncio
    async def test_fail_closed_callback_returns_hold(self) -> None:
        """GIVEN orchestrated mode with no callback registered
        WHEN fail_closed_callback fires
        THEN the decision is HOLD — never auto-approve.
        """
        decision = await fail_closed_callback(_ctx())

        assert decision.action == GateDecisionAction.HOLD
        assert decision.decided_by == "system"
        assert "fail" in decision.reason.lower()
        assert not decision.is_approved()

    @pytest.mark.asyncio
    async def test_fail_closed_never_approves_any_gate(self) -> None:
        """GIVEN any gate id in orchestrated mode without a callback
        WHEN fail_closed_callback fires
        THEN the action is never APPROVE.
        """
        for gate_id in ("HUMAN_APPROVE_CONFIG", "HUMAN_REVIEW_OBJECTIVES", "HUMAN_APPROVE_DEPLOY"):
            decision = await fail_closed_callback(_ctx(gate_id=gate_id))
            assert decision.action != GateDecisionAction.APPROVE
            assert decision.gate_id == gate_id


class TestLegacyUnchanged:
    """REQ-11 scenario: legacy CLI auto-approve preserved."""

    @pytest.mark.asyncio
    async def test_legacy_cli_without_orchestrator_still_auto_approves(self) -> None:
        """GIVEN legacy CLI (no orchestrator, no registered gate callbacks)
        WHEN a gate fires
        THEN the prior auto-approve behavior is preserved — fail-closed is
        orchestrated-mode only.
        """
        from quantlab.agents.research_director import ResearchDirector
        from quantlab.dsl.models import IterationConfig, ResearchConfig
        from quantlab.pipeline.base import PipelineContext
        from quantlab.pipeline.stages.gate_interceptor import (
            GateAction,
            GateInterceptorStage,
        )

        director = ResearchDirector()
        config = ResearchConfig(
            campaign="LegacyTest",
            market="EURUSD",
            timeframe="H1",
            iteration_config=IterationConfig(max_iterations=1),
        )
        pipeline = director.build_pipeline(config)
        gates = [s for s in pipeline.stages if isinstance(s, GateInterceptorStage)]
        assert gates, "legacy pipeline must include gate stages"

        result = await gates[0].execute(PipelineContext(config={}))

        assert result["decision"] == GateAction.APPROVED.value
        assert result["reason"] == "Auto-approved (no callback registered)"


class TestCampaignIdSanitisation:
    """Boundary 2: campaign_id restricted to [A-Za-z0-9_-]; traversal rejected."""

    def test_valid_campaign_ids_accepted(self) -> None:
        """GIVEN campaign ids matching [A-Za-z0-9_-]
        WHEN sanitising
        THEN they pass through unchanged.
        """
        for cid in ("campaign-1", "CAMPAIGN_2", "x9_y", "a"):
            assert sanitize_campaign_id(cid) == cid

    def test_traversal_and_invalid_ids_rejected(self) -> None:
        """GIVEN campaign ids with traversal or forbidden characters
        WHEN sanitising
        THEN ValueError is raised — no path escape.
        """
        for cid in ("../etc", "..", "a/b", "a b", "", "a$b", "a.b"):
            with pytest.raises(ValueError):
                sanitize_campaign_id(cid)

    def test_decision_path_uses_sanitized_campaign_dir(self, tmp_path) -> None:
        """GIVEN a sanitised campaign id
        WHEN building the decision path
        THEN the file lands under {gate_event_dir}/{campaign_id}/.
        """
        path = decision_path(str(tmp_path), "campaign-1", GATE_ID)
        assert path.name == f"{GATE_ID}.decision.json"
        assert "campaign-1" in path.parts
