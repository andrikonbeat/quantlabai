"""FR-005: docs assert the 14-phase lifecycle contract with real gates.

The README and STATE docs MUST assert the canonical 14-phase lifecycle
(research → hypothesis → config → review → dispatch → monitor → retest →
optimize → portfolio → compile → deploy → demo → archive → live-ops) with the
real human gates wired at each boundary (HUMAN_APPROVE_DEPLOY / DEMO /
ARCHIVE). The stale 8-phase "no deploy" assertions are REMOVED: the flow runs
through deploy, demo, and archive to the terminal live-ops phase.

Fail-closed gate behavior (REQ-11, D2/D3) and Dukascopy-only data (D5)
assertions are PRESERVED from the previous contract.

Strict TDD: RED — the current README/STATE still assert the stale 8-phase
"no deploy" contract, so the 14-phase assertions fail until the docs are
updated.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
STATE = REPO_ROOT / "docs" / "STATE.md"

PHASE_CHAIN = (
    "research → hypothesis → config → review → dispatch → monitor → retest → "
    "optimize → portfolio → compile → deploy → demo → archive → live-ops"
)
# Whitespace-insensitive form: docs may wrap the chain across lines.
CHAIN_SQUASHED = "".join(PHASE_CHAIN.split())
REAL_GATES = ("HUMAN_APPROVE_DEPLOY", "HUMAN_APPROVE_DEMO", "HUMAN_APPROVE_ARCHIVE")


def _read(path: Path) -> str:
    assert path.exists(), f"expected file to exist: {path}"
    return path.read_text(encoding="utf-8")


def _squash(text: str) -> str:
    return "".join(text.split())


class TestReadmeCampaignSection:
    """The README documents the harness, the 14 phases, and real gates."""

    def test_readme_has_orchestrated_campaign_section(self) -> None:
        text = _read(README)
        assert "Orchestrated Campaign" in text

    def test_readme_campaign_section_shows_harness_usage(self) -> None:
        text = _read(README)
        section = text.split("Orchestrated Campaign", 1)[1]
        assert "quantlab-campaign" in section
        assert "quantlab-orchestrator" in section  # routing entry point

    def test_readme_lists_all_14_phases_in_order(self) -> None:
        """FR-005: the README asserts the full 14-phase chain, in order."""
        section = _read(README).split("Orchestrated Campaign", 1)[1]
        assert CHAIN_SQUASHED in _squash(section)

    def test_readme_names_real_gates_at_boundaries(self) -> None:
        """FR-005: each deploy/demo/archive boundary names a real gate."""
        section = _read(README).split("Orchestrated Campaign", 1)[1]
        for gate in REAL_GATES:
            assert gate in section, f"gate {gate} missing from README section"

    def test_readme_campaign_section_states_fail_closed_gates(self) -> None:
        """REQ-11/D2/D3 preserved: fail-closed HOLD behavior is stated."""
        section = _read(README).split("Orchestrated Campaign", 1)[1]
        assert "fail" in section.lower()  # fail-closed gate behavior (REQ-11)
        assert "hold" in section.lower()

    def test_readme_campaign_section_states_dukascopy_only_data(self) -> None:
        """D5 preserved: DataManager is Dukascopy-only."""
        section = _read(README).split("Orchestrated Campaign", 1)[1]
        assert "dukascopy" in section.lower()  # D5


class TestStateCampaignSection:
    """STATE.md mirrors the 14-phase orchestrated flow."""

    def test_state_documents_orchestrated_campaign_flow(self) -> None:
        text = _read(STATE)
        assert "orchestrated-campaign-flow" in text or "quantlab-campaign" in text

    def test_state_lists_all_14_phases_in_order(self) -> None:
        """FR-005: STATE asserts the full 14-phase chain, in order."""
        assert CHAIN_SQUASHED in _squash(_read(STATE))

    def test_state_names_real_gates_at_boundaries(self) -> None:
        """FR-005: STATE names the real human gates, not a "no deploy" halt."""
        text = _read(STATE)
        for gate in REAL_GATES:
            assert gate in text, f"gate {gate} missing from STATE.md"
