"""Run-flow gate execution + headless decisions-file channel (PR2, WU-3).

Covers the Run-Flow Gate Execution requirement and the Headless Gate
Decisions requirement (ADR-4):

- ``read_decisions_file`` parses a JSON map ``gate_id -> decision envelope``.
- ``DecisionsFileGateCallback`` re-reads the file per gate, never writes it,
  and fails closed (HOLD, system) on a missing file or missing key.
- ``cmd_campaign_run_flow`` executes every ``HUMAN_*`` gate with
  stop-on-non-approved semantics: APPROVE/FALLBACK continues, REJECT/HOLD/
  ABORT/missing stops the flow with a non-zero exit; a blocked dispatch is a
  visible failure, never a false success.

Strict TDD: RED — written before ``read_decisions_file``,
``DecisionsFileGateCallback``, or the run-flow gate loop existed.
"""

from __future__ import annotations

import argparse
import asyncio
import json

import pytest

from quantlab.gates.callbacks import (
    DecisionsFileGateCallback,
    decision_path,
    pending_path,
    read_decisions_file,
)
from quantlab.gates.models import GateDecisionAction
from quantlab.pipeline.base import Pipeline, PipelineContext, Stage
from quantlab.pipeline.stages.dispatch_stage import DispatchStage
from quantlab.pipeline.stages.gate_interceptor import (
    FallbackPolicy,
    GateInterceptorStage,
)

HUMAN_APPROVE_CONFIG = "HUMAN_APPROVE_CONFIG"
HUMAN_APPROVE_DEMO = "HUMAN_APPROVE_DEMO"


def _ctx(gate_id: str) -> dict[str, object]:
    """Gate context dict matching what the pipeline passes to callbacks."""
    return {
        "gate_id": gate_id,
        "campaign_id": "flow-gates-1",
        "stage_name": "gate_test",
    }


def _write_decisions(path, decisions: dict[str, dict]) -> None:
    path.write_text(json.dumps(decisions), encoding="utf-8")


# ── read_decisions_file (ADR-4) ──────────────────────────────────────────────


class TestReadDecisionsFile:
    """T-2.2: ``read_decisions_file`` parses the headless decisions map."""

    def test_parses_gate_map_into_decision_files(self, tmp_path) -> None:
        """GIVEN a decisions file mapping two gates to envelopes
        WHEN read_decisions_file parses it
        THEN each gate maps to a DecisionFile with its action and reason.
        """
        path = tmp_path / "decisions.json"
        _write_decisions(path, {
            HUMAN_APPROVE_DEMO: {"action": "approve", "reason": "demo ok"},
            "HUMAN_APPROVE_ARCHIVE": {"action": "reject", "reason": "hold off"},
        })

        decisions = read_decisions_file(path)

        assert set(decisions) == {HUMAN_APPROVE_DEMO, "HUMAN_APPROVE_ARCHIVE"}
        assert decisions[HUMAN_APPROVE_DEMO].action == "approve"
        assert decisions[HUMAN_APPROVE_DEMO].reason == "demo ok"
        assert decisions["HUMAN_APPROVE_ARCHIVE"].action == "reject"

    def test_non_object_root_raises_value_error(self, tmp_path) -> None:
        """GIVEN a decisions file whose root is not an object
        WHEN read_decisions_file parses it
        THEN it raises ValueError (the file is malformed for the protocol)."""
        path = tmp_path / "decisions.json"
        path.write_text(json.dumps(["not", "a", "map"]), encoding="utf-8")

        with pytest.raises(ValueError):
            read_decisions_file(path)

    def test_missing_file_raises_file_not_found(self, tmp_path) -> None:
        """GIVEN no decisions file at the path
        WHEN read_decisions_file is called
        THEN FileNotFoundError propagates (the callback converts it to
        fail-closed, but the reader itself reports the missing input)."""
        with pytest.raises(FileNotFoundError):
            read_decisions_file(tmp_path / "absent.json")


# ── DecisionsFileGateCallback (ADR-4) ────────────────────────────────────────


class TestDecisionsFileGateCallback:
    """T-2.2: headless callback resolves from the file, fails closed."""

    @pytest.mark.asyncio
    async def test_approval_resolves_the_gate(self, tmp_path) -> None:
        """GIVEN a decisions file containing an approval for the pending gate
        WHEN the callback resolves
        THEN the gate resolves approved with the file's reason.
        """
        path = tmp_path / "decisions.json"
        _write_decisions(path, {HUMAN_APPROVE_DEMO: {"action": "approve", "reason": "go"}})

        callback = DecisionsFileGateCallback(path)
        decision = await callback(_ctx(HUMAN_APPROVE_DEMO))

        assert decision.gate_id == HUMAN_APPROVE_DEMO
        assert decision.action == GateDecisionAction.APPROVE
        assert decision.reason == "go"
        assert decision.is_approved()

    @pytest.mark.asyncio
    async def test_missing_key_fails_closed(self, tmp_path) -> None:
        """GIVEN a headless run-flow with no decision for the pending gate
        WHEN the callback resolves
        THEN the gate fails closed (HOLD, system) — never auto-approves."""
        path = tmp_path / "decisions.json"
        _write_decisions(path, {"HUMAN_OTHER": {"action": "approve"}})

        callback = DecisionsFileGateCallback(path)
        decision = await callback(_ctx(HUMAN_APPROVE_DEMO))

        assert decision.action == GateDecisionAction.HOLD
        assert decision.decided_by == "system"
        assert not decision.is_approved()

    @pytest.mark.asyncio
    async def test_missing_file_fails_closed(self, tmp_path) -> None:
        """GIVEN headless mode with no decisions file at all
        WHEN the callback resolves
        THEN the gate fails closed instead of prompting."""
        callback = DecisionsFileGateCallback(tmp_path / "absent.json")
        decision = await callback(_ctx(HUMAN_APPROVE_DEMO))

        assert decision.action == GateDecisionAction.HOLD
        assert not decision.is_approved()

    @pytest.mark.asyncio
    async def test_never_writes_the_decisions_file(self, tmp_path) -> None:
        """GIVEN headless mode with an absent decisions file
        WHEN the callback resolves
        THEN the file is never created — the channel is read-only input."""
        path = tmp_path / "absent.json"
        callback = DecisionsFileGateCallback(path)
        await callback(_ctx(HUMAN_APPROVE_DEMO))

        assert not path.exists()

    @pytest.mark.asyncio
    async def test_re_reads_file_per_gate(self, tmp_path) -> None:
        """GIVEN a decisions file updated while the flow runs
        WHEN the callback resolves a second gate
        THEN the file is re-read and the new decision is honoured."""
        path = tmp_path / "decisions.json"
        _write_decisions(path, {HUMAN_APPROVE_DEMO: {"action": "approve"}})

        callback = DecisionsFileGateCallback(path)

        first = await callback(_ctx(HUMAN_APPROVE_DEMO))
        assert first.is_approved()

        # Gate not in the file yet → fails closed.
        second = await callback(_ctx(HUMAN_APPROVE_CONFIG))
        assert second.action == GateDecisionAction.HOLD

        # File updated mid-flow → the next call sees the new decision.
        _write_decisions(path, {
            HUMAN_APPROVE_DEMO: {"action": "approve"},
            HUMAN_APPROVE_CONFIG: {"action": "reject"},
        })
        third = await callback(_ctx(HUMAN_APPROVE_CONFIG))
        assert third.action == GateDecisionAction.REJECT


# ── cmd_campaign_run_flow gate execution ─────────────────────────────────────


class _RecordingStage(Stage):
    """Sentinel stage that records execution — proves flow continuation."""

    name = "sentinel"
    requires: list[str] = []
    provides: list[str] = []

    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def execute(self, ctx: PipelineContext) -> dict[str, bool]:
        self._log.append("sentinel")
        return {"sentinel": True}


def _gate_stage(gate_id: str) -> GateInterceptorStage:
    gate = GateInterceptorStage()
    gate.gate_id = gate_id
    gate.fallback = FallbackPolicy.HOLD
    return gate


def _run_flow(monkeypatch, pipeline, capsys=None, **overrides) -> int:
    """Invoke cmd_campaign_run_flow against a controlled pipeline."""
    from quantlab.agents.research_director import ResearchDirector
    from quantlab.campaign import flow as flow_module
    from quantlab.cli.campaign_commands import cmd_campaign_run_flow

    monkeypatch.setattr(flow_module, "assert_flow_segments", lambda *a, **k: None)
    monkeypatch.setattr(
        ResearchDirector, "build_pipeline", lambda *a, **k: pipeline
    )

    args = argparse.Namespace(
        config=None,
        campaign="FlowGates",
        market="EURUSD",
        timeframe="H1",
        knowledge_root="knowledge",
        json=True,
        campaign_id="flow-gates-1",
        gate_decisions_file=None,
        gate_event_dir="/tmp/sqx-gates",
        gate_timeout=None,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return asyncio.run(cmd_campaign_run_flow(args))


class TestRunFlowGateExecution:
    """REQ Run-Flow Gate Execution: stop-on-non-approved semantics."""

    def test_approved_gate_continues_the_flow(self, monkeypatch, tmp_path, capsys) -> None:
        """GIVEN a run-flow with a pending demo gate
        WHEN the headless decision file approves it
        THEN the flow continues to the next phase and exits zero."""
        log: list[str] = []
        decisions = tmp_path / "decisions.json"
        _write_decisions(decisions, {HUMAN_APPROVE_DEMO: {"action": "approve"}})

        pipeline = Pipeline("gated", stages=[
            _gate_stage(HUMAN_APPROVE_DEMO),
            _RecordingStage(log),
        ])
        code = _run_flow(
            monkeypatch,
            pipeline,
            gate_event_dir=str(tmp_path),
            gate_decisions_file=str(decisions),
        )

        assert code == 0
        assert log == ["sentinel"]
        out = capsys.readouterr().out
        assert '"status": "completed"' in out

    def test_headless_approval_writes_no_pending_prompt(self, monkeypatch, tmp_path, capsys) -> None:
        """GIVEN headless run-flow with a decisions file
        WHEN the gate resolves
        THEN no pending prompt file is written (no interactive prompt)."""
        decisions = tmp_path / "decisions.json"
        _write_decisions(decisions, {HUMAN_APPROVE_DEMO: {"action": "approve"}})

        pipeline = Pipeline("gated", stages=[_gate_stage(HUMAN_APPROVE_DEMO)])
        code = _run_flow(
            monkeypatch,
            pipeline,
            gate_event_dir=str(tmp_path),
            gate_decisions_file=str(decisions),
        )

        assert code == 0
        assert not pending_path(
            str(tmp_path), "flow-gates-1", HUMAN_APPROVE_DEMO
        ).exists()

    def test_rejected_gate_stops_the_flow_non_zero(self, monkeypatch, tmp_path, capsys) -> None:
        """GIVEN a run-flow whose gate decision is REJECT
        WHEN the gate executes
        THEN the flow stops immediately with a non-zero exit."""
        log: list[str] = []
        decisions = tmp_path / "decisions.json"
        _write_decisions(decisions, {HUMAN_APPROVE_DEMO: {"action": "reject", "reason": "no"}})

        pipeline = Pipeline("gated", stages=[
            _gate_stage(HUMAN_APPROVE_DEMO),
            _RecordingStage(log),
        ])
        code = _run_flow(
            monkeypatch,
            pipeline,
            gate_event_dir=str(tmp_path),
            gate_decisions_file=str(decisions),
        )

        assert code == 1
        assert log == []  # sentinel never runs
        err = capsys.readouterr().err
        assert "not approved" in err
        assert "reject" in err

    def test_hold_gate_stops_the_flow_non_zero(self, monkeypatch, tmp_path, capsys) -> None:
        """GIVEN a run-flow whose gate decision holds
        WHEN the gate executes
        THEN the flow stops with a non-zero exit."""
        decisions = tmp_path / "decisions.json"
        _write_decisions(decisions, {HUMAN_APPROVE_DEMO: {"action": "hold"}})

        pipeline = Pipeline("gated", stages=[_gate_stage(HUMAN_APPROVE_DEMO)])
        code = _run_flow(
            monkeypatch,
            pipeline,
            gate_event_dir=str(tmp_path),
            gate_decisions_file=str(decisions),
        )

        assert code == 1
        assert "hold" in capsys.readouterr().err

    def test_abort_gate_stops_the_flow_non_zero(self, monkeypatch, tmp_path, capsys) -> None:
        """GIVEN a run-flow whose gate decision aborts
        WHEN the gate executes
        THEN the flow stops with a non-zero exit."""
        decisions = tmp_path / "decisions.json"
        _write_decisions(decisions, {HUMAN_APPROVE_DEMO: {"action": "abort"}})

        pipeline = Pipeline("gated", stages=[_gate_stage(HUMAN_APPROVE_DEMO)])
        code = _run_flow(
            monkeypatch,
            pipeline,
            gate_event_dir=str(tmp_path),
            gate_decisions_file=str(decisions),
        )

        assert code == 1

    def test_missing_decision_fails_closed(self, monkeypatch, tmp_path, capsys) -> None:
        """GIVEN headless run-flow with no decision for the pending gate
        WHEN the gate executes
        THEN it fails closed and the flow exits non-zero."""
        decisions = tmp_path / "decisions.json"
        _write_decisions(decisions, {"HUMAN_OTHER": {"action": "approve"}})

        pipeline = Pipeline("gated", stages=[_gate_stage(HUMAN_APPROVE_DEMO)])
        code = _run_flow(
            monkeypatch,
            pipeline,
            gate_event_dir=str(tmp_path),
            gate_decisions_file=str(decisions),
        )

        assert code == 1
        assert "not approved" in capsys.readouterr().err

    def test_blocked_dispatch_is_never_silent(self, monkeypatch, tmp_path, capsys) -> None:
        """GIVEN a run-flow where dispatch would be blocked
        WHEN the dispatch stage reports dispatch_blocked
        THEN the flow fails loudly — never a false success."""
        pipeline = Pipeline("gated", stages=[DispatchStage()])
        code = _run_flow(monkeypatch, pipeline, gate_event_dir=str(tmp_path))

        assert code == 1
        err = capsys.readouterr().err
        assert "dispatch blocked" in err.lower()


class TestRunFlowInteractiveChannel:
    """REQ: the interactive decision-file channel also drives run-flow gates."""

    @pytest.mark.asyncio
    async def test_interactive_approval_continues_flow(self, monkeypatch, tmp_path) -> None:
        """GIVEN run-flow without a decisions file (interactive channel)
        WHEN a decision file resolves the pending gate
        THEN the gate approves and the flow continues."""
        from quantlab.agents.research_director import ResearchDirector
        from quantlab.campaign import flow as flow_module
        from quantlab.cli.campaign_commands import cmd_campaign_run_flow

        log: list[str] = []
        pipeline = Pipeline("gated", stages=[
            _gate_stage(HUMAN_APPROVE_DEMO),
            _RecordingStage(log),
        ])

        monkeypatch.setattr(flow_module, "assert_flow_segments", lambda *a, **k: None)
        monkeypatch.setattr(
            ResearchDirector, "build_pipeline", lambda *a, **k: pipeline
        )
        args = argparse.Namespace(
            config=None,
            campaign="FlowGates",
            market="EURUSD",
            timeframe="H1",
            knowledge_root="knowledge",
            json=True,
            campaign_id="flow-gates-1",
            gate_decisions_file=None,
            gate_event_dir=str(tmp_path),
            gate_timeout=10,
        )

        task = asyncio.create_task(cmd_campaign_run_flow(args))

        pending = pending_path(str(tmp_path), "flow-gates-1", HUMAN_APPROVE_DEMO)
        for _ in range(200):
            if pending.exists():
                break
            await asyncio.sleep(0.01)
        assert pending.exists(), "interactive channel must write the pending marker"

        decision_file = decision_path(str(tmp_path), "flow-gates-1", HUMAN_APPROVE_DEMO)
        decision_file.write_text(
            json.dumps({"action": "approve", "reason": "ok", "decided_by": "human"}),
            encoding="utf-8",
        )

        code = await asyncio.wait_for(task, timeout=10)
        assert code == 0
        assert log == ["sentinel"]
