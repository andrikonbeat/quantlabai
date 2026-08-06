"""RED tests for WU-9: quantlab-campaign harness + orchestrator routing (REQ-01, REQ-02, REQ-16).

The harness deliverable lives in-repo under ``AI/opencode/`` (REQ-02) and is
wired from the OpenCode config (``~/.config/opencode/``).  These tests assert:

- the orchestrator prompt routes campaign intents to ``quantlab-campaign``
  while keeping SDD/CLI/dashboard routes unchanged (REQ-16);
- the campaign agent prompt owns the 14-phase loop and continues past
  optimize through deploy, demo, and archive to live-ops (REQ-37, which
  replaced the old 8-phase loop / REQ-01, D1 behavior);
- the decision-file gate protocol is described (AD-4) with the question tool
  as primary and stdin as headless fallback;
- ``opencode.json`` registers ``quantlab-campaign`` by ``{file:...}``
  reference and the orchestrator's task allowlist includes it (REQ-02, REQ-16);
- ``openspec/config.yaml`` routing gains the campaign row (REQ-16).

The OpenCode config files live outside the repo (``~/.config/opencode/``);
they are asserted here because REQ-16 scenario text names the exact path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENCODE_DIR = Path.home() / ".config" / "opencode"
ORCHESTRATOR_PROMPT = OPENCODE_DIR / "prompts" / "quantlab" / "orchestrator.md"
OPENCODE_JSON = OPENCODE_DIR / "opencode.json"

CAMPAIGN_AGENT_PROMPT = REPO_ROOT / "AI" / "opencode" / "agents" / "campaign.md"
CAMPAIGN_SKILL = REPO_ROOT / "AI" / "opencode" / "skills" / "quantlab-run-campaign" / "SKILL.md"
CONFIG_YAML = REPO_ROOT / "openspec" / "config.yaml"

SDD_SKILLS = ["sdd-spec", "sdd-design", "sdd-tasks", "sdd-apply", "sdd-verify", "sdd-archive"]
CAMPAIGN_PHASES = [
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
]


def _read(path: Path) -> str:
    assert path.exists(), f"expected file to exist: {path}"
    return path.read_text(encoding="utf-8")


class TestOrchestratorPromptFile:
    """REQ-16: prompt file exists at the expected path, readable."""

    def test_prompt_file_exists_and_is_readable(self) -> None:
        text = _read(ORCHESTRATOR_PROMPT)
        assert len(text) > 0

    def test_skills_section_lists_sdd_skills(self) -> None:
        text = _read(ORCHESTRATOR_PROMPT)
        assert "## Skills to load before work" in text
        for skill in SDD_SKILLS:
            assert skill in text, f"skill resolver must list {skill}"

    def test_routing_keeps_sdd_cli_dashboard_rows(self) -> None:
        text = _read(ORCHESTRATOR_PROMPT)
        assert "gentle-orchestrator" in text  # SDD route unchanged
        assert "sqcli" in text  # CLI route unchanged
        assert "dashboard" in text or "DASHBOARD" in text  # dashboard route unchanged


class TestCampaignRouting:
    """REQ-16: campaign intents route to quantlab-campaign."""

    def test_prompt_routes_campaign_to_quantlab_campaign(self) -> None:
        text = _read(ORCHESTRATOR_PROMPT)
        assert "quantlab-campaign" in text
        # The route must be a delegation instruction, not a passing mention.
        assert "campaign" in text.lower()


class TestCampaignAgentPrompt:
    """REQ-37: the harness prompt owns the 14-phase loop through live-ops."""

    def test_campaign_agent_prompt_exists_in_repo(self) -> None:
        _read(CAMPAIGN_AGENT_PROMPT)  # exists + readable

    def test_campaign_agent_prompt_owns_14_phase_loop(self) -> None:
        text = _read(CAMPAIGN_AGENT_PROMPT)
        for phase in CAMPAIGN_PHASES:
            assert phase in text.lower(), f"campaign prompt must include phase {phase}"

    def test_campaign_agent_prompt_continues_past_optimize_through_archive(self) -> None:
        text = _read(CAMPAIGN_AGENT_PROMPT)
        lowered = text.lower()
        # The loop MUST NOT halt at optimize (REQ-37 replaces the old
        # REQ-01/D1 stop-after-optimize behavior).
        assert "optimize" in lowered
        assert "continues past optimize" in lowered
        # It MUST proceed through deploy, demo, and archive to live-ops.
        assert "deploy" in lowered
        assert "archive" in lowered
        assert "live-ops" in lowered

    def test_campaign_agent_prompt_returns_result_contract_envelope(self) -> None:
        text = _read(CAMPAIGN_AGENT_PROMPT)
        for field in ("status", "executive_summary", "artifacts", "next_recommended", "risks"):
            assert field in text, f"Result Contract envelope must include {field}"

    def test_campaign_agent_prompt_describes_gate_protocol(self) -> None:
        text = _read(CAMPAIGN_AGENT_PROMPT)
        assert "question" in text.lower()  # AD-4 primary channel
        assert "stdin" in text.lower()  # AD-4 headless fallback
        assert "decision" in text.lower()  # decision-file protocol


class TestCampaignSkill:
    """REQ-02: the seed skill is versioned in-repo."""

    def test_run_campaign_skill_exists(self) -> None:
        _read(CAMPAIGN_SKILL)


class TestOpencodeJsonRegistration:
    """REQ-02 + REQ-16: opencode.json registers the subagent by file path."""

    def test_opencode_json_registers_campaign_subagent(self) -> None:
        assert OPENCODE_JSON.exists(), f"expected opencode.json at {OPENCODE_JSON}"
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        agent = cfg.get("agent", {}).get("quantlab-campaign")
        assert agent is not None, "opencode.json must register quantlab-campaign"
        assert agent.get("mode") == "subagent"
        prompt = agent.get("prompt", "")
        assert "AI/opencode/agents/campaign.md" in prompt

    def test_orchestrator_task_allowlist_includes_campaign(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        task_perms = cfg["agent"]["quantlab-orchestrator"]["permission"]["task"]
        assert task_perms.get("quantlab-campaign") == "allow"


class TestOpenSpecConfigRouting:
    """REQ-16: openspec/config.yaml routing gains the campaign row."""

    def test_config_routes_campaign_to_quantlab_campaign(self) -> None:
        text = _read(CONFIG_YAML)
        assert "campaign" in text
        assert "quantlab-campaign" in text
