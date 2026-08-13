"""REQ-37: flow-integrity invariant — 14 phases, in order, never merged.

The full lifecycle MUST retain all 14 flow phases plus the Guardian live flow,
in order, each gated by human confirmation. The campaign start assertion MUST
abort with a flow-integrity error when a phase is dropped, reordered, merged,
or unknown — never reorder or skip (fail-closed, REQ-37 scenario 2).

The same canonical list is declared in ``AI/opencode/agents/campaign.md``; the
doc must never drift from the code (REQ-37 "asserted at campaign start and
after any harness change").
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from quantlab.campaign.delegation import PHASE_AGENTS
from quantlab.campaign.flow import PHASES, STAGE_FOR_PHASE, FlowIntegrityError, assert_flow

CANONICAL_14 = (
    "research",
    "hypothesis",
    "config",
    "review",
    "dispatch",
    "monitor",
    "retest",
    "optimize",
    "portfolio",
    "compile",
    "deploy",
    "demo",
    "archive",
    "live-ops",
)


class TestCanonicalPhases:
    """The canonical 14-phase lifecycle (REQ-01 modified)."""

    def test_phases_constant_is_the_14_phase_lifecycle(self) -> None:
        """GIVEN the flow module
        THEN PHASES holds exactly the 14 phases in lifecycle order.
        """
        assert PHASES == CANONICAL_14
        assert len(PHASES) == 14

    def test_every_phase_is_human_gated_anchor(self) -> None:
        """The lifecycle spans research through live-ops with archive before
        the Guardian live flow (REQ-01)."""
        assert PHASES[0] == "research"
        assert PHASES[-1] == "live-ops"
        assert "archive" in PHASES
        assert PHASES.index("archive") < PHASES.index("live-ops")


class TestFlowAssert:
    """REQ-37 scenario 2: a dropped/reordered phase aborts the assert."""

    def test_full_flow_assert_passes(self) -> None:
        """GIVEN the canonical 14 phases
        WHEN the campaign-start assertion runs
        THEN it completes without error.
        """
        assert_flow(PHASES)  # must not raise

    def test_dropped_phase_aborts(self) -> None:
        """GIVEN a harness missing the archive phase
        WHEN the campaign-start assertion runs
        THEN the campaign aborts with a flow-integrity error
        AND no execution begins (fail-closed).
        """
        missing_archive = PHASES[: PHASES.index("archive")] + PHASES[
            PHASES.index("archive") + 1 :
        ]
        with pytest.raises(FlowIntegrityError) as exc:
            assert_flow(missing_archive)
        assert "archive" in str(exc.value)

    def test_reordered_phase_aborts(self) -> None:
        """GIVEN two phases swapped out of order
        WHEN the assertion runs
        THEN it aborts naming the out-of-order phase.
        """
        reordered = list(PHASES)
        i, j = PHASES.index("optimize"), PHASES.index("portfolio")
        reordered[i], reordered[j] = reordered[j], reordered[i]
        with pytest.raises(FlowIntegrityError) as exc:
            assert_flow(reordered)
        assert "optimize" in str(exc.value) or "portfolio" in str(exc.value)

    def test_merged_phase_aborts(self) -> None:
        """GIVEN two phases collapsed into one (merge)
        WHEN the assertion runs
        THEN it aborts — merging phases is forbidden.
        """
        merged = list(PHASES[: PHASES.index("compile")]) + [
            "compile-deploy"
        ] + list(PHASES[PHASES.index("deploy") :])
        with pytest.raises(FlowIntegrityError):
            assert_flow(merged)

    def test_duplicated_phase_aborts(self) -> None:
        """GIVEN a phase listed twice
        WHEN the assertion runs
        THEN it aborts.
        """
        duplicated = list(PHASES)
        duplicated.append("research")
        with pytest.raises(FlowIntegrityError):
            assert_flow(duplicated)

    def test_unknown_phase_aborts(self) -> None:
        """GIVEN a phase not part of the lifecycle
        WHEN the assertion runs
        THEN it aborts.
        """
        with pytest.raises(FlowIntegrityError):
            assert_flow(list(PHASES) + ["crypto-import"])

    def test_short_flow_aborts(self) -> None:
        """GIVEN only the first phase
        WHEN the assertion runs
        THEN it aborts (the loop must never start on a partial flow)."""
        with pytest.raises(FlowIntegrityError):
            assert_flow(["research"])


class TestCampaignDoc:
    """REQ-37: the campaign.md doc declares the same canonical phases."""

    def _doc_phases(self) -> tuple[str, ...]:
        doc = Path("AI/opencode/agents/campaign.md").read_text(encoding="utf-8")
        match = re.search(r"PHASES\s*=\s*\((.*?)\)", doc, re.DOTALL)
        assert match is not None, "campaign.md must declare the PHASES tuple"
        body = match.group(1)
        # Normalise the tuple literal into something ast can parse.
        body = "".join(body.splitlines())
        body = re.sub(r",\s*\)$", ")", body)
        return tuple(ast.literal_eval(f"({body})"))

    def test_doc_declares_canonical_phases(self) -> None:
        """GIVEN the campaign agent instructions
        THEN its PHASES declaration equals the canonical 14 (no drift)."""
        assert self._doc_phases() == PHASES

    def test_doc_instructs_campaign_start_assert(self) -> None:
        """GIVEN the campaign agent instructions
        THEN they mandate the flow-integrity assert at campaign start
        AND aborting on any dropped/reordered phase (REQ-37)."""
        doc = Path("AI/opencode/agents/campaign.md").read_text(encoding="utf-8")
        assert "assert_flow" in doc
        assert "FlowIntegrityError" in doc


class TestDelegationIntegrity:
    """REQ-804: the delegation layer wraps PHASES without mutation."""

    def test_phase_agents_keys_equal_phases(self) -> None:
        """GIVEN the delegation registry
        THEN PHASE_AGENTS keys are exactly the canonical PHASES (wrap-only)."""
        assert tuple(PHASE_AGENTS.keys()) == PHASES
        assert len(PHASE_AGENTS) == len(PHASES) == 14

    def test_phase_agents_values_are_quantlab_phase_names(self) -> None:
        """GIVEN the delegation registry
        THEN every value is the expected quantlab-phase-<phase> name."""
        for phase, agent in PHASE_AGENTS.items():
            assert agent == f"quantlab-phase-{phase}", (
                f"phase '{phase}' maps to '{agent}', expected 'quantlab-phase-{phase}'"
            )

    def test_flow_python_unchanged(self) -> None:
        """GIVEN the flow module
        THEN PHASES, STAGE_FOR_PHASE, and assert_flow are unchanged
        (REQ-804 wrap-only invariant)."""
        assert PHASES == CANONICAL_14
        assert "research" in STAGE_FOR_PHASE
        assert "live-ops" in STAGE_FOR_PHASE
        assert_flow(PHASES)  # must not raise
