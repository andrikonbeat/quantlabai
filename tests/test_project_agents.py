"""REQ-902: repo-root AGENTS.md contract.

AGENTS.md MUST exist at repo root and define:
- project stack
- testing conventions
- harness conventions
- OpenSpec workflow
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS = REPO_ROOT / "AGENTS.md"


def _read(path: Path) -> str:
    assert path.exists(), f"expected file to exist: {path}"
    return path.read_text(encoding="utf-8")


def _squash(text: str) -> str:
    return "".join(text.split())


class TestAgentsMdContract:
    """Repo-root AGENTS.md is the single source of truth for agent onboarding."""

    def test_agents_md_exists(self) -> None:
        assert AGENTS.exists(), f"AGENTS.md missing at repo root: {AGENTS}"

    def test_agents_md_covers_stack(self) -> None:
        text = _read(AGENTS)
        assert "quantlab" in text.lower()
        assert "pytest" in text.lower()
        assert "SQX_FORCE_MOCK" in text

    def test_agents_md_covers_testing_conventions(self) -> None:
        text = _read(AGENTS)
        assert "strict" in text.lower() and "tdd" in text.lower()
        assert "SQX_FORCE_MOCK=1 python3 -m pytest -q" in text

    def test_agents_md_covers_harness_conventions(self) -> None:
        text = _read(AGENTS)
        # sync contract
        assert "sync" in text.lower()
        assert "repo-wins" in text.lower() or "repo wins" in text.lower()
        # 14-phase flow / REQ-37
        assert "14-phase" in text.lower() or "14 phase" in text.lower() or "REQ-37" in text

    def test_agents_md_covers_sdd_workflow(self) -> None:
        text = _read(AGENTS)
        assert "sdd" in text.lower()
        assert "apply-progress" in text.lower() or "apply progress" in text.lower()

    def test_agents_md_lists_all_14_phases_in_order(self) -> None:
        """REQ-902 / REQ-37: AGENTS.md documents the canonical 14-phase chain."""
        text = _read(AGENTS)
        chain = (
            "research → hypothesis → config → review → dispatch → monitor → "
            "retest → optimize → portfolio → compile → deploy → demo → archive → live-ops"
        )
        assert chain in text, "14-phase lifecycle chain missing from AGENTS.md"

    def test_agents_md_does_not_duplicate_persona_sections(self) -> None:
        """Project AGENTS.md must not duplicate global persona, engram, codegraph,
        or language-contract sections."""
        text = _read(AGENTS)
        # These markers belong to the global ~/.config/opencode/AGENTS.md only.
        assert "<!-- gentle-ai:persona -->" not in text
        assert "<!-- gentle-ai:engram-protocol -->" not in text
        assert "<!-- gentle-ai:codegraph-guidance -->" not in text
        assert "<!-- gentle-ai:agent-language-contract -->" not in text
