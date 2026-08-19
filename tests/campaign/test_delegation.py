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
- Stage artifact persistence (REQ-819 + campaign-artifact-writers): _run_sdk_stage
  writes the outcome JSON + envelope, hooks proposal/spec writers per phase,
  degrades on missing knowledge_root/campaign_id, folds write failures into a
  failed envelope that halts folding, and re-runs idempotently
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

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


# --- Stage artifact persistence (REQ-819 + campaign-artifact-writers) ---------


class _FakeStageRegistry:
    """StageRegistry stand-in resolving every name to a single fake class."""

    def __init__(self, stage_class: object) -> None:
        self._stage_class = stage_class

    def get_stage_class(self, stage_name: str) -> object:
        return self._stage_class


def _make_fake_stage_class(
    outcome: dict | None = None, error: Exception | None = None
) -> type:
    """Build a Stage stand-in with a fixed outcome or a raised error."""

    class _Fake:
        name = "fake"

        def __init__(
            self,
            _outcome: dict | None = outcome,
            _error: Exception | None = error,
        ) -> None:
            self._outcome = _outcome
            self._error = _error

        async def execute(self, ctx: object) -> dict:
            if self._error is not None:
                raise self._error
            return self._outcome or {}

    return _Fake


def _patch_stage(monkeypatch: pytest.MonkeyPatch, stage_class: type) -> None:
    """Force ``_run_sdk_stage`` to resolve *stage_class* for every stage name."""
    monkeypatch.setattr(
        delegation_module,
        "_get_stage_registry",
        lambda: _FakeStageRegistry(stage_class),
    )


class TestStageArtifactPersistence:
    """REQ-819: ``_run_sdk_stage`` persists every claimed artifact to the lake.

    D1: the envelope write happens inside ``_run_sdk_stage`` (the single choke
    point reached by both the inline reasoning executors and the handoff
    subprocess). D2: the claimed ``{phase}_{stage}.json`` key becomes a real
    file under ``campaign-phases/{cid}/{phase}/`` and the envelope lists real
    paths only. Q1: proposal.md is written on research, spec.md on
    hypothesis/config.
    """

    def test_success_persists_envelope_and_outcome_file(
        self, tmp_path: Path
    ) -> None:
        # REQ-819 s1 + campaign-artifact-writers "Claimed artifact becomes a
        # file": a completed research stage leaves envelope.json + the outcome
        # file + proposal.md, and every envelope artifact resolves on disk.
        payload = {
            "campaign_id": "camp_001",
            "knowledge_root": str(tmp_path),
            "config": {"objectives": ["Research EURUSD H1"]},
        }
        result = asyncio.run(delegation_module._run_sdk_stage("research", payload))

        envelope_path = (
            tmp_path / "campaign-phases" / "camp_001" / "research" / "envelope.json"
        )
        assert envelope_path.exists(), "envelope.json must exist after the stage"
        assert (
            tmp_path
            / "campaign-phases"
            / "camp_001"
            / "research"
            / "research_research_llm.json"
        ).exists(), "the claimed outcome key must become a real file (D2)"

        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
        assert envelope["status"] == "completed"
        assert envelope["phase"] == "research"
        assert envelope["started_at"], "started_at captured in _run_sdk_stage (Q2)"
        assert envelope["completed_at"], "completed_at captured in _run_sdk_stage (Q2)"
        assert envelope["next_gate"] == "hypothesis"
        assert envelope["artifacts"], "envelope must list the persisted artifacts"
        for rel in envelope["artifacts"]:
            assert (tmp_path / rel).exists(), (
                f"envelope artifact '{rel}' must resolve to a real file"
            )
        # PhaseResult carries the same real paths — no synthetic claim (REQ-819).
        assert result.artifacts == envelope["artifacts"]

        # Q1 hook: research → proposal.md.
        proposal = tmp_path / "structured" / "camp_001" / "proposal.md"
        assert proposal.exists(), "research must persist proposal.md (Q1)"
        text = proposal.read_text(encoding="utf-8")
        assert "Campaign Proposal" in text
        assert "## Research Configuration" in text
        assert "## Hypotheses" in text

    def test_proposal_hook_renders_research_outcome(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # campaign-artifact-writers "Research stage persists proposal": the
        # writer renders research_config + hypothesis entries deterministically.
        outcome = {
            "research_config": {
                "campaign": "camp_001",
                "market": "EURUSD",
                "timeframe": "H1",
            },
            "hypotheses": [{"id": "hyp_1", "statement": "momentum persists"}],
            "sources": [{"title": "Paper A", "url": "https://example.com/a"}],
        }
        _patch_stage(monkeypatch, _make_fake_stage_class(outcome=outcome))
        payload = {"campaign_id": "camp_001", "knowledge_root": str(tmp_path)}

        asyncio.run(delegation_module._run_sdk_stage("research", payload))

        text = (tmp_path / "structured" / "camp_001" / "proposal.md").read_text(
            encoding="utf-8"
        )
        assert "# Campaign Proposal — camp_001" in text
        assert "EURUSD" in text
        assert "hyp_1" in text, "the proposal must render hypothesis entries"

    def test_spec_hook_renders_hypothesis_outcome(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # campaign-artifact-writers "Spec written with empty hypotheses":
        # hypothesis stage writes spec.md with config sections and an empty
        # hypotheses section.
        outcome = {
            "building_blocks": [{"id": "bb_1"}],
            "strategies": [{"id": "strat_1"}],
            "hypotheses": [],
        }
        _patch_stage(monkeypatch, _make_fake_stage_class(outcome=outcome))
        payload = {"campaign_id": "camp_001", "knowledge_root": str(tmp_path)}

        asyncio.run(delegation_module._run_sdk_stage("hypothesis", payload))

        text = (tmp_path / "structured" / "camp_001" / "spec.md").read_text(
            encoding="utf-8"
        )
        assert "# Campaign Spec — camp_001" in text
        assert "## Hypotheses" in text
        assert "## Builder Configuration" in text
        # Empty hypotheses render as an explicitly empty section, never a lie.
        assert "(none)" in text

    def test_spec_hook_renders_configuration_sections(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Q1: spec.md on the config phase covers builder/retester/optimizer/
        # portfolio configuration + acceptance criteria.
        outcome = {
            "build_config": {"entries": 3},
            "cfx_bytes": b"CFX-archive",
            "retest": {"rounds": 1},
            "optimize": {"metric": "sharpe"},
            "portfolio": {"targets": ["A"]},
        }
        _patch_stage(monkeypatch, _make_fake_stage_class(outcome=outcome))
        payload = {"campaign_id": "camp_001", "knowledge_root": str(tmp_path)}

        asyncio.run(delegation_module._run_sdk_stage("config", payload))

        text = (tmp_path / "structured" / "camp_001" / "spec.md").read_text(
            encoding="utf-8"
        )
        assert "## Builder Configuration" in text
        assert "## Retester Configuration" in text
        assert "## Optimizer Configuration" in text
        assert "## Portfolio Configuration" in text

    def test_missing_knowledge_root_records_risk_no_claim(
        self, tmp_path: Path
    ) -> None:
        # campaign-phase-delegation "Missing knowledge_root degrades": the
        # stage completes, the gap lands in risks, and nothing is claimed.
        result = asyncio.run(
            delegation_module._run_sdk_stage(
                "research",
                {
                    "campaign_id": "camp_001",
                    "config": {"objectives": ["Research EURUSD H1"]},
                },
            )
        )
        assert result.artifacts == [], (
            "no artifact may be claimed without a knowledge_root"
        )
        assert any("knowledge_root" in risk for risk in result.risks)
        assert not (tmp_path / "campaign-phases").exists()

    def test_missing_campaign_id_records_risk_no_claim(
        self, tmp_path: Path
    ) -> None:
        result = asyncio.run(
            delegation_module._run_sdk_stage(
                "research",
                {
                    "knowledge_root": str(tmp_path),
                    "config": {"objectives": ["Research EURUSD H1"]},
                },
            )
        )
        assert result.artifacts == []
        assert any("campaign_id" in risk for risk in result.risks)

    def test_executor_never_claims_without_root(self) -> None:
        # REQ-819 through the full executor path: a completed phase without a
        # knowledge_root succeeds (stage ran) but claims no artifact and notes
        # the gap in risks.
        directive = PhaseDirective(
            phase_id="research",
            scope="research-scope",
            payload={"config": {"objectives": ["Research EURUSD H1"]}},
        )
        result = asyncio.run(execute_phase(directive))
        assert result.status == "success"
        assert result.artifacts == []
        assert any("knowledge_root" in risk for risk in result.risks)

    def test_failed_stage_leaves_failed_envelope_hold(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # campaign-phase-delegation "Failed stage still leaves an envelope":
        # envelope.json carries failed status + the error log, next gate HOLD.
        _patch_stage(
            monkeypatch,
            _make_fake_stage_class(error=RuntimeError("SQX error: backtest failed")),
        )
        directive = PhaseDirective(
            phase_id="retest",
            scope="retest-scope",
            payload={"campaign_id": "camp_001", "knowledge_root": str(tmp_path)},
        )
        result = asyncio.run(execute_phase(directive))
        assert result.status == "failed"
        assert result.next_recommended == "halt"
        assert any("SQX error" in risk for risk in result.risks)

        envelope_path = (
            tmp_path / "campaign-phases" / "camp_001" / "retest" / "envelope.json"
        )
        assert envelope_path.exists(), "a failed stage must still leave an envelope"
        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
        assert envelope["status"] == "failed"
        assert envelope["next_gate"] == "HOLD"
        assert envelope["error"] and "SQX error" in envelope["error"]
        assert envelope["artifacts"], "failed envelope must list the error log"
        for rel in envelope["artifacts"]:
            assert (tmp_path / rel).exists(), (
                f"error log artifact '{rel}' must resolve to a real file"
            )

    def test_write_failure_folds_failed_and_halts(
        self, tmp_path: Path
    ) -> None:
        # campaign-artifact-writers "Write failure is recorded": an unwritable
        # lake folds into a failed envelope and folding halts (REQ-802) — never
        # a fake success.
        blocked = tmp_path / "blocked"
        blocked.write_text("", encoding="utf-8")
        directive = PhaseDirective(
            phase_id="research",
            scope="research-scope",
            payload={
                "campaign_id": "camp_001",
                "knowledge_root": str(blocked),
                "config": {"objectives": ["Research EURUSD H1"]},
            },
        )
        result = asyncio.run(execute_phase(directive))
        assert result.status == "failed", (
            "a failed persistence MUST NOT masquerade as success (REQ-802)"
        )
        assert result.next_recommended == "halt"
        assert result.risks, "the failure must be recorded in risks"

    def test_rerun_is_idempotent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Task 2.6 REFACTOR: re-running the same stage overwrites deterministically
        # — no duplication, no crash, identical final bytes.
        outcome = {
            "research_config": {"campaign": "camp_001", "market": "EURUSD"},
            "hypotheses": [{"id": "hyp_1"}],
        }
        _patch_stage(monkeypatch, _make_fake_stage_class(outcome=outcome))
        payload = {"campaign_id": "camp_001", "knowledge_root": str(tmp_path)}

        first = asyncio.run(delegation_module._run_sdk_stage("research", payload))
        outcome_file = (
            tmp_path / "campaign-phases" / "camp_001" / "research"
            / "research_research_llm.json"
        )
        first_bytes = outcome_file.read_bytes()
        envelope_file = (
            tmp_path / "campaign-phases" / "camp_001" / "research" / "envelope.json"
        )
        first_envelope = envelope_file.read_bytes()

        second = asyncio.run(delegation_module._run_sdk_stage("research", payload))

        assert first.artifacts == second.artifacts
        assert outcome_file.read_bytes() == first_bytes, (
            "re-run must overwrite the outcome deterministically"
        )
        assert envelope_file.read_bytes() == first_envelope, (
            "re-run must overwrite the envelope deterministically"
        )
        assert (
            tmp_path / "structured" / "camp_001" / "proposal.md"
        ).exists()
