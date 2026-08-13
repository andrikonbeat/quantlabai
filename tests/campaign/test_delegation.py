"""REQ-801..REQ-804, REQ-809: delegation glue tests.

Covers:
- PhaseDirective envelope schema
- Unknown phase rejected
- status!=success halts
- Authority violation rejected
- Long-op script no-wait (handoff_payload present, no await)
- PHASE_AGENTS keys == PHASES
- validate_phase_result() helper
"""

from __future__ import annotations

import asyncio

import pytest

from quantlab.campaign.delegation import (
    PHASE_AGENTS,
    AuthorityViolationError,
    PhaseDirective,
    PhaseNotFoundError,
    PhaseResult,
    execute_phase,
    validate_phase_result,
)
from quantlab.campaign.flow import PHASES


# --- Envelope schema ---------------------------------------------------------


class TestPhaseDirective:
    def test_directive_accepts_valid_fields(self) -> None:
        d = PhaseDirective(
            phase_id="research",
            scope="research-scope",
            payload={"campaign_id": "c1"},
        )
        assert d.phase_id == "research"
        assert d.scope == "research-scope"
        assert d.payload == {"campaign_id": "c1"}
        assert d.previous_result is None

    def test_directive_with_previous_result(self) -> None:
        prev = PhaseResult(
            status="success",
            executive_summary="prev ok",
            artifacts=["prev.json"],
            next_recommended="hypothesis",
            risks=[],
            phase_id="research",
        )
        d = PhaseDirective(
            phase_id="hypothesis",
            scope="hypothesis-scope",
            payload={"campaign_id": "c1"},
            previous_result=prev,
        )
        assert d.previous_result is prev
        assert d.previous_result.phase_id == "research"

    def test_directive_frozen(self) -> None:
        d = PhaseDirective(phase_id="research", scope="s", payload={})
        with pytest.raises(AttributeError):
            d.phase_id = "hypothesis"  # type: ignore[misc]


class TestPhaseResultEnvelope:
    def test_success_envelope_folds(self) -> None:
        r = PhaseResult(
            status="success",
            executive_summary="ok",
            artifacts=["a.json"],
            next_recommended="hypothesis",
            risks=[],
            phase_id="research",
        )
        assert r.status == "success"

    def test_failed_envelope_halts(self) -> None:
        r = PhaseResult(
            status="failed",
            executive_summary="gate denied",
            artifacts=[],
            next_recommended="halt",
            risks=["gate denied"],
            phase_id="demo",
        )
        assert r.status != "success"

    def test_handoff_payload_present_for_long_op(self) -> None:
        payload = {
            "command": "nohup ./backtest.sh",
            "log_path": "/tmp/backtest.log",
            "expected": "DONE",
            "timeout": 300,
            "cleanup": "rm -f /tmp/backtest.log",
        }
        r = PhaseResult(
            status="success",
            executive_summary="long op",
            artifacts=[],
            next_recommended="orchestrator-shell",
            risks=["long operation delegated"],
            phase_id="optimize",
            handoff_payload=payload,
        )
        assert r.handoff_payload is not None
        assert r.handoff_payload["command"] == "nohup ./backtest.sh"
        assert r.handoff_payload["timeout"] >= 240

    def test_handoff_payload_default_none(self) -> None:
        r = PhaseResult(
            status="success",
            executive_summary="ok",
            artifacts=[],
            next_recommended="next",
            risks=[],
            phase_id="research",
        )
        assert r.handoff_payload is None


# --- Registry -----------------------------------------------------------------


class TestPhaseAgentsRegistry:
    def test_phase_agents_keys_match_phases(self) -> None:
        assert list(PHASE_AGENTS.keys()) == list(PHASES)

    def test_phase_agents_values_are_quantlab_phase_names(self) -> None:
        for phase, agent_name in PHASE_AGENTS.items():
            assert agent_name == f"quantlab-phase-{phase}"

    def test_phase_agents_length_equals_phases_length(self) -> None:
        assert len(PHASE_AGENTS) == len(PHASES) == 14


# --- Glue ---------------------------------------------------------------------


class TestExecutePhase:
    def test_unknown_phase_rejected(self) -> None:
        directive = PhaseDirective(
            phase_id="unknown-phase",
            scope="test",
            payload={},
        )

        async def _noop(d: PhaseDirective) -> PhaseResult:
            return PhaseResult(
                status="success",
                executive_summary="",
                artifacts=[],
                next_recommended="",
                risks=[],
                phase_id=d.phase_id,
            )

        with pytest.raises(PhaseNotFoundError):
            asyncio.run(execute_phase(directive, executor=_noop))

    def test_authority_violation_rejected(self) -> None:
        directive = PhaseDirective(
            phase_id="research",
            scope="mutate flow.py",
            payload={},
        )

        async def _noop(d: PhaseDirective) -> PhaseResult:
            return PhaseResult(
                status="success",
                executive_summary="",
                artifacts=[],
                next_recommended="",
                risks=[],
                phase_id=d.phase_id,
            )

        with pytest.raises(AuthorityViolationError):
            asyncio.run(execute_phase(directive, executor=_noop))

    def test_status_not_success_halts(self) -> None:
        async def _fail(d: PhaseDirective) -> PhaseResult:
            return PhaseResult(
                status="failed",
                executive_summary="gate denied",
                artifacts=[],
                next_recommended="halt",
                risks=["gate denied"],
                phase_id=d.phase_id,
            )

        directive = PhaseDirective(phase_id="demo", scope="demo-scope", payload={})
        result = asyncio.run(execute_phase(directive, executor=_fail))
        assert result.status != "success"

    def test_long_op_returns_script_spec_no_wait(self) -> None:
        async def _long_op(d: PhaseDirective) -> PhaseResult:
            return PhaseResult(
                status="success",
                executive_summary="script produced",
                artifacts=["script.json"],
                next_recommended="orchestrator-shell",
                risks=["long operation delegated"],
                phase_id=d.phase_id,
                handoff_payload={
                    "command": "nohup ./backtest.sh",
                    "log_path": "/tmp/backtest.log",
                    "expected": "DONE",
                    "timeout": 300,
                    "cleanup": "rm -f /tmp/backtest.log",
                },
            )

        directive = PhaseDirective(
            phase_id="optimize", scope="long op", payload={}
        )
        result = asyncio.run(execute_phase(directive, executor=_long_op))
        assert result.handoff_payload is not None
        assert result.handoff_payload["timeout"] >= 240
        assert "nohup" in result.handoff_payload["command"]

    def test_success_path_returns_envelope(self) -> None:
        async def _ok(d: PhaseDirective) -> PhaseResult:
            return PhaseResult(
                status="success",
                executive_summary="ok",
                artifacts=["a.json"],
                next_recommended="hypothesis",
                risks=[],
                phase_id=d.phase_id,
            )

        directive = PhaseDirective(
            phase_id="research", scope="research-scope", payload={}
        )
        result = asyncio.run(execute_phase(directive, executor=_ok))
        assert result.status == "success"
        assert result.phase_id == "research"
        assert result.artifacts == ["a.json"]

    def test_mock_executor_available_when_force_mock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SQX_FORCE_MOCK", "1")
        directive = PhaseDirective(
            phase_id="research", scope="research-scope", payload={}
        )
        result = asyncio.run(execute_phase(directive))
        assert result.status == "success"
        assert result.phase_id == "research"


# --- validate_phase_result ----------------------------------------------------


class TestValidatePhaseResult:
    def test_valid_result_passes(self) -> None:
        r = PhaseResult(
            status="success",
            executive_summary="ok",
            artifacts=["a.json"],
            next_recommended="next",
            risks=[],
            phase_id="research",
        )
        validate_phase_result(r)  # must not raise

    def test_missing_status_raises(self) -> None:
        r = PhaseResult(
            status="",
            executive_summary="ok",
            artifacts=[],
            next_recommended="next",
            risks=[],
            phase_id="research",
        )
        with pytest.raises(ValueError, match="status"):
            validate_phase_result(r)

    def test_missing_summary_raises(self) -> None:
        r = PhaseResult(
            status="success",
            executive_summary="",
            artifacts=[],
            next_recommended="next",
            risks=[],
            phase_id="research",
        )
        with pytest.raises(ValueError, match="executive_summary"):
            validate_phase_result(r)

    def test_unknown_phase_raises(self) -> None:
        r = PhaseResult(
            status="success",
            executive_summary="ok",
            artifacts=[],
            next_recommended="next",
            risks=[],
            phase_id="unknown",
        )
        with pytest.raises(PhaseNotFoundError):
            validate_phase_result(r)

    def test_artifacts_must_be_list(self) -> None:
        r = PhaseResult(
            status="success",
            executive_summary="ok",
            artifacts="not-a-list",
            next_recommended="next",
            risks=[],
            phase_id="research",
        )
        with pytest.raises(ValueError, match="artifacts"):
            validate_phase_result(r)

    def test_risks_must_be_list(self) -> None:
        r = PhaseResult(
            status="success",
            executive_summary="ok",
            artifacts=[],
            next_recommended="next",
            risks="not-a-list",
            phase_id="research",
        )
        with pytest.raises(ValueError, match="risks"):
            validate_phase_result(r)


# --- LongOpSpec --------------------------------------------------------------


class TestLongOpSpec:
    def test_valid_spec(self) -> None:
        from quantlab.campaign.delegation import LongOpSpec

        spec = LongOpSpec(
            command="nohup ./backtest.sh",
            log_path="/tmp/backtest.log",
            expected="DONE",
            timeout=300,
            cleanup="rm -f /tmp/backtest.log",
        )
        assert spec.timeout == 300

    def test_timeout_below_240_raises(self) -> None:
        from quantlab.campaign.delegation import LongOpSpec

        with pytest.raises(ValueError, match="timeout"):
            LongOpSpec(
                command="echo hi",
                log_path="/tmp/x.log",
                expected="DONE",
                timeout=60,
            )
