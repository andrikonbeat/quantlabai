"""RED tests for WU-10: documentation accuracy for the orchestrated campaign flow (REQ-01..21 audit).

The docs MUST reflect the shipped behavior of the change so that examples are
runnable and accurate:

- README.md documents the `quantlab-campaign` harness usage and the routing
  entry point (REQ-01, REQ-02, REQ-16);
- the no-deploy boundary (D1), the fail-closed gates (REQ-11, D2/D3), and the
  Dukascopy-only DataManager (REQ-12, D5) are stated explicitly;
- STATE.md mirrors the orchestrated flow so the project status does not
  contradict the shipped SDK.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
STATE = REPO_ROOT / "STATE.md"


def _read(path: Path) -> str:
    assert path.exists(), f"expected file to exist: {path}"
    return path.read_text(encoding="utf-8")


class TestReadmeCampaignSection:
    """The README documents the harness and its boundaries."""

    def test_readme_has_orchestrated_campaign_section(self) -> None:
        text = _read(README)
        assert "Orchestrated Campaign" in text

    def test_readme_campaign_section_shows_harness_usage(self) -> None:
        text = _read(README)
        section = text.split("Orchestrated Campaign", 1)[1]
        assert "quantlab-campaign" in section
        assert "quantlab-orchestrator" in section  # routing entry point

    def test_readme_campaign_section_states_no_deploy_boundary(self) -> None:
        text = _read(README)
        section = text.split("Orchestrated Campaign", 1)[1]
        assert "no deploy" in section.lower() or "no-deploy" in section.lower()

    def test_readme_campaign_section_states_fail_closed_gates(self) -> None:
        text = _read(README)
        section = text.split("Orchestrated Campaign", 1)[1]
        assert "fail" in section.lower()  # fail-closed gate behavior (REQ-11)
        assert "hold" in section.lower()

    def test_readme_campaign_section_states_dukascopy_only_data(self) -> None:
        text = _read(README)
        section = text.split("Orchestrated Campaign", 1)[1]
        assert "dukascopy" in section.lower()  # D5


class TestStateCampaignSection:
    """STATE.md mirrors the orchestrated flow."""

    def test_state_documents_orchestrated_campaign_flow(self) -> None:
        text = _read(STATE)
        assert "orchestrated-campaign-flow" in text or "quantlab-campaign" in text

    def test_state_states_no_deploy_boundary(self) -> None:
        text = _read(STATE)
        assert "deploy" in text  # the boundary is discussed
