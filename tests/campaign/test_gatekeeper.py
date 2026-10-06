"""REQ-01: post-phase gatekeeper tests.

Covers:
- Contract conformance (validate_phase_result passthrough)
- Artifact read-back (artifact existence check)
- No hallucination (spot-check for non-existent file/symbol/command refs)
- No input drift (result.phase_id matches directive.phase_id)
- Routing coherence (next_recommended matches expected next phase)
- Exactly-once corrective re-run
- Second-failure halt (GatekeeperHalt)
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from quantlab.campaign.delegation import (
    PhaseDirective,
    PhaseResult,
)

# The gatekeeper module does not exist yet — this import is the RED trigger.
from quantlab.campaign.gatekeeper import (
    GatekeeperError,
    GatekeeperHalt,
    run_post_phase_gatekeeper,
)


def _research_directive() -> PhaseDirective:
    return PhaseDirective(
        phase_id="research",
        scope="research-scope",
        payload={"campaign_id": "c1"},
    )


def _valid_result() -> PhaseResult:
    return PhaseResult(
        status="success",
        executive_summary="research completed",
        artifacts=[],
        next_recommended="hypothesis",
        risks=[],
        phase_id="research",
    )


class TestPostPhaseGatekeeper:
    """REQ-01: post-phase gatekeeper contract."""

    def test_valid_result_passes(self) -> None:
        """GIVEN a valid PhaseResult
        WHEN the gatekeeper runs
        THEN it returns the same result unchanged.
        """
        result = _valid_result()
        final = asyncio.run(
            run_post_phase_gatekeeper(_research_directive(), result)
        )
        assert final is result

    def test_missing_artifact_fails(self, tmp_path: Path) -> None:
        """GIVEN a result declaring an artifact that does not exist on disk
        WHEN the gatekeeper runs with knowledge_root set
        THEN it raises GatekeeperError (artifact read-back failure).
        """
        result = PhaseResult(
            status="success",
            executive_summary="ok",
            artifacts=["nonexistent.json"],
            next_recommended="hypothesis",
            risks=[],
            phase_id="research",
        )
        with pytest.raises(GatekeeperError, match="artifact"):
            asyncio.run(
                run_post_phase_gatekeeper(
                    _research_directive(), result, knowledge_root=str(tmp_path)
                )
            )

    def test_hallucinated_absolute_path_fails(self) -> None:
        """GIVEN a result with an absolute-path artifact that does not exist
        WHEN the gatekeeper runs
        THEN it raises GatekeeperError (hallucination spot-check failure).
        """
        result = PhaseResult(
            status="success",
            executive_summary="ok",
            artifacts=["/nonexistent/hallucinated.json"],
            next_recommended="hypothesis",
            risks=[],
            phase_id="research",
        )
        with pytest.raises(GatekeeperError, match="hallucination"):
            asyncio.run(
                run_post_phase_gatekeeper(_research_directive(), result)
            )

    def test_routing_mismatch_fails(self) -> None:
        """GIVEN a result whose next_recommended is not the expected next phase
        WHEN the gatekeeper runs
        THEN it raises GatekeeperError (routing coherence failure).
        """
        result = PhaseResult(
            status="success",
            executive_summary="ok",
            artifacts=[],
            next_recommended="compile",
            risks=[],
            phase_id="research",
        )
        with pytest.raises(GatekeeperError, match="routing"):
            asyncio.run(
                run_post_phase_gatekeeper(_research_directive(), result)
            )

    def test_input_drift_phase_id_mismatch_fails(self) -> None:
        """GIVEN a result whose phase_id differs from the directive
        WHEN the gatekeeper runs
        THEN it raises GatekeeperError (input-drift failure).
        """
        directive = PhaseDirective(
            phase_id="research",
            scope="research-scope",
            payload={"campaign_id": "c1"},
        )
        result = PhaseResult(
            status="success",
            executive_summary="ok",
            artifacts=[],
            next_recommended="hypothesis",
            risks=[],
            phase_id="hypothesis",
        )
        with pytest.raises(GatekeeperError, match="input drift"):
            asyncio.run(
                run_post_phase_gatekeeper(directive, result)
            )

    def test_envelope_validation_failure_propagates(self) -> None:
        """GIVEN a result that fails validate_phase_result (missing status)
        WHEN the gatekeeper runs
        THEN it raises ValueError (contract conformance passthrough).
        """
        result = PhaseResult(
            status="",
            executive_summary="ok",
            artifacts=[],
            next_recommended="hypothesis",
            risks=[],
            phase_id="research",
        )
        with pytest.raises(ValueError, match="status"):
            asyncio.run(
                run_post_phase_gatekeeper(_research_directive(), result)
            )

    def test_exactly_once_rerun_succeeds(self) -> None:
        """GIVEN a first result that fails the gatekeeper (hallucinated artifact)
        AND an executor that returns a valid result on the second call
        WHEN the gatekeeper runs
        THEN it calls the executor exactly twice and returns the corrected result.
        """
        call_count = 0

        async def executor(directive: PhaseDirective) -> PhaseResult:
            nonlocal call_count
            call_count += 1
            # The corrective re-run should return a valid result.
            return PhaseResult(
                status="success",
                executive_summary="corrected",
                artifacts=[],
                next_recommended="hypothesis",
                risks=[],
                phase_id=directive.phase_id,
            )

        bad_result = PhaseResult(
            status="success",
            executive_summary="bad artifact",
            artifacts=["/nonexistent.json"],
            next_recommended="hypothesis",
            risks=[],
            phase_id="research",
        )
        final = asyncio.run(
            run_post_phase_gatekeeper(
                _research_directive(), bad_result, executor=executor
            )
        )
        assert call_count == 1
        assert final.executive_summary == "corrected"

    def test_exactly_once_rerun_fails_halts(self) -> None:
        """GIVEN a first result that fails the gatekeeper
        AND an executor that returns another failing result on the second call
        WHEN the gatekeeper runs
        THEN it raises GatekeeperHalt after exactly two executor calls.
        """
        call_count = 0

        async def executor(directive: PhaseDirective) -> PhaseResult:
            nonlocal call_count
            call_count += 1
            return PhaseResult(
                status="success",
                executive_summary=f"still bad call={call_count}",
                artifacts=["/nonexistent.json"],
                next_recommended="compile",
                risks=[],
                phase_id=directive.phase_id,
            )

        bad_result = PhaseResult(
            status="success",
            executive_summary="bad artifact",
            artifacts=["/nonexistent.json"],
            next_recommended="compile",
            risks=[],
            phase_id="research",
        )
        with pytest.raises(GatekeeperHalt):
            asyncio.run(
                run_post_phase_gatekeeper(
                    _research_directive(), bad_result, executor=executor
                )
            )
        assert call_count == 1

    def test_no_executor_on_first_failure_raises(self) -> None:
        """GIVEN a result that fails the gatekeeper but no executor is provided
        WHEN the gatekeeper runs
        THEN it raises GatekeeperError (no corrective re-run possible).
        """
        result = PhaseResult(
            status="success",
            executive_summary="ok",
            artifacts=["/nonexistent.json"],
            next_recommended="hypothesis",
            risks=[],
            phase_id="research",
        )
        with pytest.raises(GatekeeperError, match="hallucination"):
            asyncio.run(
                run_post_phase_gatekeeper(_research_directive(), result, executor=None)
            )

    def test_last_phase_routing_coherence(self) -> None:
        """GIVEN a directive for the last phase (live-ops)
        WHEN the gatekeeper validates routing
        THEN next_recommended='live-ops' is accepted (self-loop boundary).
        """
        directive = PhaseDirective(
            phase_id="live-ops",
            scope="live-ops-scope",
            payload={"campaign_id": "c1"},
        )
        result = PhaseResult(
            status="success",
            executive_summary="live-ops done",
            artifacts=[],
            next_recommended="live-ops",
            risks=[],
            phase_id="live-ops",
        )
        final = asyncio.run(
            run_post_phase_gatekeeper(directive, result)
        )
        assert final is result
