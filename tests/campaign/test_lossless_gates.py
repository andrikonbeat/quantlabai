"""REQ-11/REQ-38/REQ-824: lossless gate protocol in agent prompts.

Tests verify that agent prompt files contain the required lossless
blocking-prompt discipline text: complete envelope, exact-one answer,
re-present + STOP on invalid input.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REPO_AGENTS = REPO_ROOT / "ai" / "opencode" / "agents"


class TestCampaignLosslessGate:
    """REQ-11/REQ-38: campaign.md must contain the lossless gate protocol."""

    def test_campaign_md_contains_lossless_gate_protocol_section(self) -> None:
        campaign = REPO_AGENTS / "campaign.md"
        text = campaign.read_text(encoding="utf-8")
        assert "Lossless Gate Protocol" in text
        assert "exactly one answer" in text.lower()
        assert "re-present" in text.lower()

    def test_campaign_md_prohibits_auto_approval(self) -> None:
        campaign = REPO_AGENTS / "campaign.md"
        text = campaign.read_text(encoding="utf-8")
        assert "Auto-approval is prohibited" in text


class TestGuardianOrchestratorLosslessGate:
    """REQ-824: guardian-orchestrator.md must contain lossless replacement gate."""

    def test_guardian_orchestrator_md_contains_lossless_discipline(self) -> None:
        guardian = REPO_AGENTS / "guardian-orchestrator.md"
        text = guardian.read_text(encoding="utf-8")
        assert "lossless" in text.lower()
        assert "exactly one answer" in text.lower()
        assert "re-present" in text.lower()
        assert "fail-closed" in text.lower()


class TestPhaseLosslessGates:
    """REQ-11: all phase-*.md files must contain lossless gate sections."""

    def test_all_phase_files_contain_exactly_one_answer(self) -> None:
        phase_files = sorted(REPO_AGENTS.glob("phase-*.md"))
        assert len(phase_files) >= 14
        for phase_file in phase_files:
            text = phase_file.read_text(encoding="utf-8")
            assert "exactly one answer" in text.lower(), (
                f"{phase_file.name} missing 'exactly one answer'"
            )

    def test_all_phase_files_contain_re_present_stop(self) -> None:
        phase_files = sorted(REPO_AGENTS.glob("phase-*.md"))
        for phase_file in phase_files:
            text = phase_file.read_text(encoding="utf-8")
            assert "re-present" in text.lower(), (
                f"{phase_file.name} missing 're-present'"
            )

    def test_all_phase_files_prohibit_auto_approval(self) -> None:
        phase_files = sorted(REPO_AGENTS.glob("phase-*.md"))
        for phase_file in phase_files:
            text = phase_file.read_text(encoding="utf-8")
            assert "Auto-approval is prohibited" in text or "auto-approval" in text.lower(), (
                f"{phase_file.name} missing auto-approval prohibition"
            )
