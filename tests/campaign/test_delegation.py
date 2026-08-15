"""REQ-801..REQ-804, REQ-809, REQ-815, REQ-816: delegation glue tests.

Covers:
- PhaseDirective envelope schema
- Unknown phase rejected
- status!=success halts
- Authority violation rejected
- Long-op script no-wait (handoff_payload present, no await)
- PHASE_AGENTS keys == PHASES
- validate_phase_result() helper
- PRODUCTION_EXECUTORS registry completeness (REQ-815)
- Executor gap fails closed (REQ-815 s2)
- Hybrid delegation split: reasoning vs mechanical vs retest vs live-ops (REQ-816)
"""

from __future__ import annotations

import asyncio

import pytest

from quantlab.campaign import delegation as delegation_module
from quantlab.campaign.delegation import (
    PHASE_AGENTS,
    PRODUCTION_EXECUTORS,
    AuthorityViolationError,
    LongOpSpec,
    PhaseDirective,
    PhaseNotFoundError,
    PhaseResult,
    execute_phase,
    validate_phase_result,
)
from quantlab.campaign.flow import PHASES, STAGE_FOR_PHASE

# Orchestrated stage bindings for the REQ-815 "resolves STAGE_FOR_PHASE"
# contract: the research phase binds to the LLM-routed stage and the monitor
# phase binds to the ADR-3 ExecutionMonitorStage in the orchestrated flow.
_ORCHESTRATED_STAGE = {
    "research": "research_llm",
    "monitor": "execution_monitor",
}


def _expected_stage(phase: str) -> str:
    """The concrete stage the production executor must resolve for *phase*."""
    return _ORCHESTRATED_STAGE.get(phase, STAGE_FOR_PHASE[phase])


def _recording_stage(calls: list[tuple[object, ...]]) -> object:
    """Fake ``_run_sdk_stage`` that records invocations instead of executing."""

    async def _recorded(*args: object, **kwargs: object) -> dict[str, object]:
        calls.append((args, kwargs))
        return {"recorded": True}

    return _recorded


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

    def test_registry_executor_takes_precedence_over_mock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # REQ-815/D2 resolution order: explicit arg → registry → mock → raise.
        # With a registered production executor, SQX_FORCE_MOCK=1 must NOT
        # divert research to the mock — the registry executor runs the SDK
        # stage (classic fallback research is deterministic and pure).
        monkeypatch.setenv("SQX_FORCE_MOCK", "1")
        directive = PhaseDirective(
            phase_id="research",
            scope="research-scope",
            payload={"config": {"objectives": ["Research EURUSD H1"]}},
        )
        result = asyncio.run(execute_phase(directive))
        assert result.status == "success"
        assert result.phase_id == "research"
        assert result.evidence.get("stage") == "research_llm"
        assert result.evidence.get("mock") is not True


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


# --- Production executor registry (REQ-815) -----------------------------------


class TestProductionExecutorsRegistry:
    def test_registry_covers_every_phase(self) -> None:
        # REQ-815: a production executor MUST be registered for every phase of
        # PHASES — no phase may silently fall back to the mock in production.
        assert set(PRODUCTION_EXECUTORS.keys()) == set(PHASES)

    def test_registry_has_fourteen_executors(self) -> None:
        assert len(PRODUCTION_EXECUTORS) == len(PHASES) == 14

    def test_every_executor_resolves_its_stage(self) -> None:
        # REQ-815: every executor resolves its SDK stage from STAGE_FOR_PHASE
        # (research→research_llm and monitor→execution_monitor are the
        # orchestrated bindings). The resolved stage is recorded in evidence.
        for phase in PHASES:
            directive = PhaseDirective(
                phase_id=phase, scope=f"{phase}-scope", payload={}
            )
            result = asyncio.run(execute_phase(directive))
            assert result.phase_id == phase
            assert result.evidence["stage"] == _expected_stage(phase)
            validate_phase_result(result)

    def test_executor_gap_fails_closed_no_stage_runs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # REQ-815 s2: a phase whose executor is not registered, without
        # SQX_FORCE_MOCK, raises AuthorityViolationError and NO SDK stage runs.
        monkeypatch.delenv("SQX_FORCE_MOCK", raising=False)
        monkeypatch.delitem(PRODUCTION_EXECUTORS, "research")
        calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(delegation_module, "_run_sdk_stage", _recording_stage(calls))

        directive = PhaseDirective(
            phase_id="research", scope="research-scope", payload={}
        )
        with pytest.raises(AuthorityViolationError):
            asyncio.run(execute_phase(directive))
        assert calls == [], "an SDK stage ran despite the executor gap"

    def test_mock_fallback_intact_when_gap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # REQ-810/REQ-815: with SQX_FORCE_MOCK=1 and a registry gap the mock
        # executor still runs — the deny-first fallback stays intact.
        monkeypatch.setenv("SQX_FORCE_MOCK", "1")
        monkeypatch.delitem(PRODUCTION_EXECUTORS, "research")
        directive = PhaseDirective(
            phase_id="research", scope="research-scope", payload={}
        )
        result = asyncio.run(execute_phase(directive))
        assert result.status == "success"
        assert result.phase_id == "research"
        assert result.evidence == {"mock": True}

    def test_production_executor_runs_sdk_stage(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # REQ-803 s3: with a production executor registered, execute_phase()
        # without SQX_FORCE_MOCK runs the SDK stage and returns a validated
        # PhaseResult. Classic-fallback research is deterministic and pure.
        monkeypatch.delenv("SQX_FORCE_MOCK", raising=False)
        directive = PhaseDirective(
            phase_id="research",
            scope="research-scope",
            payload={"config": {"objectives": ["Research EURUSD H1"]}},
        )
        result = asyncio.run(execute_phase(directive))
        assert result.status == "success"
        assert result.phase_id == "research"
        assert result.evidence["stage"] == "research_llm"
        assert "research_config" in result.evidence["outcome"]

    def test_archive_executor_resolves_archive_stage(self) -> None:
        # REQ-815 s1: an archive directive resolves the `archive` stage from
        # STAGE_FOR_PHASE, the stage executes, and the envelope carries
        # phase_id=archive.
        directive = PhaseDirective(
            phase_id="archive", scope="archive-scope", payload={}
        )
        result = asyncio.run(execute_phase(directive))
        assert result.status == "success"
        assert result.phase_id == "archive"
        assert result.evidence["stage"] == "archive"
        assert "archive_bundle" in result.evidence["outcome"]


# --- Hybrid delegation split (REQ-816) ----------------------------------------


class TestHybridDelegationSplit:
    # REQ-816: reasoning-heavy phases run as LLM subagent phases (SDK stage,
    # no handoff); mechanical/long phases hand a LongOpSpec to the orchestrator
    # shell; retest is conditional; live-ops delegates to the guardian surface.
    REASONING_PHASES = (
        "research", "hypothesis", "config", "review",
        "portfolio", "optimize", "archive",
    )
    MECHANICAL_PHASES = ("dispatch", "monitor", "compile", "deploy", "demo")

    @pytest.mark.parametrize("phase", REASONING_PHASES)
    def test_reasoning_phase_never_hands_off(self, phase: str) -> None:
        # REQ-816 s1: a reasoning directive dispatches as an LLM subagent phase
        # and returns a PhaseResult WITHOUT a handoff_payload.
        directive = PhaseDirective(
            phase_id=phase, scope=f"{phase}-scope", payload={}
        )
        result = asyncio.run(execute_phase(directive))
        assert result.phase_id == phase
        assert result.handoff_payload is None

    @pytest.mark.parametrize("phase", MECHANICAL_PHASES)
    def test_mechanical_phase_hands_off_long_op(self, phase: str) -> None:
        # REQ-816 s2 + REQ-809: a mechanical directive returns a LongOpSpec in
        # handoff_payload (log under /tmp/opencode, timeout>=240, cleanup set)
        # for the orchestrator shell — the glue never waits on it.
        directive = PhaseDirective(
            phase_id=phase, scope=f"{phase}-scope", payload={}
        )
        result = asyncio.run(execute_phase(directive))
        assert result.phase_id == phase
        assert result.handoff_payload is not None
        spec = LongOpSpec(**result.handoff_payload)
        assert spec.command
        assert spec.log_path.startswith("/tmp/opencode/")
        assert spec.timeout >= 240
        assert spec.cleanup, "long-op handoff MUST carry a cleanup command (D5)"
        assert result.evidence["stage"] == _expected_stage(phase)

    def test_mechanical_phase_never_runs_stage_inline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # REQ-809: the glue must NOT run the mechanical stage inline — it
        # returns the runnable script for the orchestrator shell.
        calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(delegation_module, "_run_sdk_stage", _recording_stage(calls))
        directive = PhaseDirective(
            phase_id="dispatch", scope="dispatch-scope", payload={}
        )
        result = asyncio.run(execute_phase(directive))
        assert result.handoff_payload is not None
        assert calls == [], "mechanical stage ran inline — REQ-809 forbids waiting"

    def test_retest_long_run_hands_off(self) -> None:
        # REQ-816: retest hands off via LongOpSpec when the run is long.
        directive = PhaseDirective(
            phase_id="retest", scope="retest-scope", payload={"long_op": True}
        )
        result = asyncio.run(execute_phase(directive))
        assert result.handoff_payload is not None
        spec = LongOpSpec(**result.handoff_payload)
        assert spec.timeout >= 240
        assert spec.cleanup

    def test_retest_short_run_runs_inline(self) -> None:
        # REQ-816: a short retest runs inline (no handoff). The retester stage
        # with a config that has no retest block returns immediately.
        directive = PhaseDirective(
            phase_id="retest",
            scope="retest-scope",
            payload={"artifacts": {"research_config": {}}},
        )
        result = asyncio.run(execute_phase(directive))
        assert result.handoff_payload is None
        assert result.phase_id == "retest"

    def test_live_ops_folds_guardian_report(self) -> None:
        # REQ-816: live-ops delegates to the guardian surface via
        # execute_guardian_directive(); the GuardianReport is folded into
        # evidence and never adds a flow stage (no handoff).
        directive = PhaseDirective(
            phase_id="live-ops",
            scope="live-ops-scope",
            payload={"kind": "live_ops_status", "campaign_id": "c1"},
        )
        result = asyncio.run(execute_phase(directive))
        assert result.phase_id == "live-ops"
        assert result.handoff_payload is None
        report = result.evidence["guardian_report"]
        assert isinstance(report, dict)
        assert "live_ops_status" in report
        assert "guardian_state" in report
