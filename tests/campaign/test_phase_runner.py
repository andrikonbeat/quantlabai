"""REQ-818: phase_runner CLI bridge tests.

The runner is a standalone module under ``sdk/quantlab/campaign/`` (D1), NOT
a CLI subcommand: the phase-agent bash allowlist is ``sdk/quantlab/campaign/*``.
It bridges a ``PhaseDirective`` JSON to the production executor (REQ-815) and
emits the validated ``PhaseResult`` envelope as JSON.

Covers:
- build_directive: strict JSON parsing; unknown phase -> PhaseNotFoundError;
  malformed/non-object JSON rejected; D3 injection of knowledge_root +
  campaign_id into the payload
- run: round-trip directive -> validated PhaseResult; out-of-scope directive
  rejected before any SDK stage runs
- main: --phase/--directive CLI, JSON envelope on stdout, exit codes
- mechanical handoff: log under /tmp/opencode, timeout>=240, cleanup set, and
  the per-phase report records the handoff (D5)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from quantlab.campaign.delegation import (
    AuthorityViolationError,
    PhaseNotFoundError,
    validate_phase_result,
)
from quantlab.campaign.phase_runner import build_directive, main, run

_HANDOFF_DIR = Path("/tmp/opencode")


def _recording_stage(calls: list[tuple[object, ...]]) -> object:
    """Fake ``delegation._run_sdk_stage`` that records invocations."""

    async def _recorded(*args: object, **kwargs: object) -> dict[str, object]:
        calls.append((args, kwargs))
        return {"recorded": True}

    return _recorded


class TestBuildDirective:
    def test_parses_scope_and_payload(self) -> None:
        d = build_directive(
            "research",
            '{"scope": "research-scope", "payload": {"campaign_id": "c1"}}',
        )
        assert d.phase_id == "research"
        assert d.scope == "research-scope"
        # D3: the runner injects knowledge_root alongside the caller payload.
        assert d.payload == {"campaign_id": "c1", "knowledge_root": "knowledge"}

    def test_injects_persistence_context_defaults_and_keeps_caller_values(
        self,
    ) -> None:
        # D3: the runner always provides the persistence context — defaults
        # apply when absent, caller-provided values win.
        d = build_directive("research", '{"payload": {}}')
        assert d.payload["knowledge_root"] == "knowledge"
        assert d.payload["campaign_id"] == "campaign"

        d2 = build_directive(
            "research",
            '{"payload": {"knowledge_root": "/tmp/lake", "campaign_id": "c9"}}',
        )
        assert d2.payload == {"knowledge_root": "/tmp/lake", "campaign_id": "c9"}

    def test_missing_scope_defaults_to_phase_scope(self) -> None:
        d = build_directive("optimize", '{"payload": {}}')
        assert d.phase_id == "optimize"
        assert d.scope == "optimize-scope"

    def test_unknown_phase_raises_phase_not_found(self) -> None:
        with pytest.raises(PhaseNotFoundError):
            build_directive("not-a-phase", "{}")

    def test_malformed_json_rejected(self) -> None:
        with pytest.raises(ValueError, match="malformed"):
            build_directive("research", "{not json")

    def test_non_object_json_rejected(self) -> None:
        with pytest.raises(ValueError):
            build_directive("research", "[1, 2, 3]")


class TestRun:
    def test_round_trip_research_directive(self, tmp_path: Path) -> None:
        # REQ-818 s1: the runner bridges a directive to the production executor
        # and returns a validated PhaseResult whose phase id matches. Classic
        # fallback research is deterministic and pure. The payload pins the
        # Knowledge Lake root to tmp_path so the round trip stays hermetic
        # (D3: the runner would otherwise inject the repo's default lake root).
        directive_json = json.dumps({
            "scope": "research-scope",
            "payload": {
                "campaign_id": "c1",
                "knowledge_root": str(tmp_path),
                "config": {"objectives": ["Research EURUSD H1"]},
            },
        })
        result = asyncio.run(run("research", directive_json))
        validate_phase_result(result)
        assert result.phase_id == "research"
        assert result.status == "success"
        assert result.handoff_payload is None

    def test_unknown_phase_rejected(self) -> None:
        with pytest.raises(PhaseNotFoundError):
            asyncio.run(run("not-a-phase", "{}"))

    def test_malformed_directive_rejected(self) -> None:
        with pytest.raises(ValueError):
            asyncio.run(run("research", "{oops"))

    def test_out_of_scope_rejected_before_any_stage(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # REQ-818 s2 + REQ-803 deny-first: a directive whose scope contains a
        # forbidden action is rejected with an authority error and NO SDK stage
        # runs.
        calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "quantlab.campaign.delegation._run_sdk_stage",
            _recording_stage(calls),
        )
        with pytest.raises(AuthorityViolationError):
            asyncio.run(run("research", '{"scope": "mutate flow.py"}'))
        assert calls == [], "an SDK stage ran despite the out-of-scope directive"


class TestMain:
    def test_cli_round_trip_emits_json_envelope(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # REQ-818 s1: --phase/--directive emits a validated PhaseResult as JSON.
        # The payload pins the lake root to tmp_path so the run stays hermetic.
        directive = json.dumps({
            "payload": {
                "campaign_id": "c1",
                "knowledge_root": str(tmp_path),
                "config": {"objectives": ["Research EURUSD H1"]},
            },
        })
        code = main(["--phase", "research", "--directive", directive])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        assert out["status"] == "success"
        assert out["phase_id"] == "research"

    def test_cli_unknown_phase_exits_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["--phase", "bogus", "--directive", "{}"])
        out = json.loads(capsys.readouterr().out)
        assert code == 1
        assert out["error"] == "PhaseNotFoundError"

    def test_cli_malformed_directive_exits_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["--phase", "research", "--directive", "{oops"])
        out = json.loads(capsys.readouterr().out)
        assert code == 1
        assert "malformed" in out["detail"].lower()

    def test_cli_out_of_scope_exits_1_no_stage(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        calls: list[tuple[object, ...]] = []
        monkeypatch.setattr(
            "quantlab.campaign.delegation._run_sdk_stage",
            _recording_stage(calls),
        )
        code = main(["--phase", "research", "--directive", '{"scope": "skip gate"}'])
        out = json.loads(capsys.readouterr().out)
        assert code == 1
        assert out["error"] == "AuthorityViolationError"
        assert calls == [], "an SDK stage ran despite the out-of-scope directive"

    def test_cli_mechanical_handoff_spec_and_report(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # REQ-818 s3: a mechanical phase returns a LongOpSpec whose log_path is
        # under /tmp/opencode, timeout >= 240, cleanup set; the per-phase
        # report records the handoff.
        code = main(["--phase", "dispatch", "--directive", "{}"])
        out = json.loads(capsys.readouterr().out)
        assert code == 0
        handoff = out["handoff_payload"]
        assert handoff is not None
        assert handoff["log_path"].startswith("/tmp/opencode/")
        assert handoff["timeout"] >= 240
        assert handoff["cleanup"]
        assert handoff["command"]

        report = _HANDOFF_DIR / "dispatch.report.md"
        assert report.exists(), "the per-phase report must be written (D5)"
        assert "handoff" in report.read_text(encoding="utf-8")
