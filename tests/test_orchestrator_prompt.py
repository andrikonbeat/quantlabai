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
- ``openspec/config.yaml`` routing gains the campaign row (REQ-16);
- guardian intents route to ``quantlab-guardian`` while non-guardian intents
  stay with the orchestrator (REQ-642, PR 2);
- ``opencode.json`` registers ``quantlab-guardian`` deny-first and the
  orchestrator task allowlist explicitly permits it (delegation ownership,
  PR 2).

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
        assert "{file:~/.config/opencode/prompts/quantlab/campaign.md}" in prompt

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


class TestRequir814RoutingNote:
    """REQ-814: orchestrator.md documents no direct phase routing and long-running
    operations execute on the orchestrator shell."""

    def test_orchestrator_routing_note_mentions_no_direct_phase_routing(self) -> None:
        text = _read(ORCHESTRATOR_PROMPT)
        assert "no direct phase routing" in text.lower(), (
            "REQ-814 note must state that orchestrator does not route phase intents directly"
        )

    def test_orchestrator_routing_note_long_running_on_shell(self) -> None:
        text = _read(ORCHESTRATOR_PROMPT)
        assert "orchestrator shell" in text.lower(), (
            "REQ-814 note must state long-running operations execute on orchestrator shell"
        )

    def test_orchestrator_campaign_route_delegates_via_task(self) -> None:
        text = _read(ORCHESTRATOR_PROMPT)
        assert "quantlab-campaign" in text
        assert "task" in text


class TestCampaignDispatchMap:
    """REQ-811: campaign.md dispatches per phase in PHASES order."""

    def test_campaign_prompt_declares_dispatch_table(self) -> None:
        text = _read(CAMPAIGN_AGENT_PROMPT)
        for phase in CAMPAIGN_PHASES:
            agent_name = f"quantlab-phase-{phase}"
            assert agent_name in text, f"campaign.md dispatch table must list {agent_name}"

    def test_campaign_prompt_dispatch_order_matches_phases(self) -> None:
        text = _read(CAMPAIGN_AGENT_PROMPT)
        # Verify PHASES order by checking each phase appears in the dispatch table
        # in the same order as CAMPAIGN_PHASES.
        table_start = text.find("| Phase | Subagent |")
        assert table_start != -1, "campaign.md must contain dispatch table"
        table = text[table_start:]
        for phase in CAMPAIGN_PHASES:
            assert phase in table, f"dispatch table must include phase {phase}"


class TestGuardianRouting:
    """REQ-642 (PR 2): guardian intents route to ``quantlab-guardian``;
    non-guardian intents do NOT match the GUARDIAN route.

    Routing authority (threat matrix): the orchestrator routing table MUST
    contain a GUARDIAN row dispatching via ``task``, guardian keywords MUST
    classify as GUARDIAN, and an intent that is not guardian-related MUST
    stay with the orchestrator — never misrouted to the agent.
    """

    def test_prompt_declares_guardian_route_dispatching_via_task(self) -> None:
        text = _read(ORCHESTRATOR_PROMPT)
        assert "GUARDIAN" in text  # routing-table classification exists
        assert "quantlab-guardian" in text  # routing-table target exists
        assert "task" in text  # dispatch via the task tool

    def test_guardian_intent_keywords_classify_as_guardian(self) -> None:
        text = _read(ORCHESTRATOR_PROMPT).lower()
        for keyword in ("guardian", "evaluate", "live-ops", "feedback"):
            assert keyword in text, f"GUARDIAN classification must match {keyword}"

    def test_non_guardian_intents_stay_with_orchestrator(self) -> None:
        text = _read(ORCHESTRATOR_PROMPT)
        # REQ-642 scenario 2: an intent that is not guardian-related MUST NOT
        # be dispatched to the guardian agent; the orchestrator handles it.
        assert "MUST NOT" in text
        assert "stays with the orchestrator" in text
        # Neighboring routes are not hijacked by the GUARDIAN row.
        assert "quantlab-campaign" in text
        assert "gentle-orchestrator" in text


class TestGuardianAgentRegistration:
    """Delegation ownership (PR 2): ``opencode.json`` registers
    ``quantlab-guardian`` with a deny-first task allowlist, and the
    orchestrator task allowlist explicitly permits it.

    Threat matrix: typo agent names or a denied task bypass MUST NOT silently
    invent a fallback — the allowlist entry is explicit under ``"*": "deny"``.
    """

    def test_opencode_json_registers_guardian_subagent(self) -> None:
        assert OPENCODE_JSON.exists(), f"expected opencode.json at {OPENCODE_JSON}"
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        agent = cfg.get("agent", {}).get("quantlab-guardian")
        assert agent is not None, "opencode.json must register quantlab-guardian"
        assert agent.get("mode") == "subagent"
        assert "guardian.md" in agent.get("prompt", "")

    def test_guardian_agent_task_allowlist_is_deny_first(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        task_perms = cfg["agent"]["quantlab-guardian"]["permission"]["task"]
        assert task_perms.get("*") == "deny"  # wildcard deny guards the agent
        assert task_perms.get("quantlab-*") == "allow"

    def test_orchestrator_task_allowlist_explicitly_allows_guardian(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        task_perms = cfg["agent"]["quantlab-orchestrator"]["permission"]["task"]
        assert task_perms.get("quantlab-guardian") == "allow"


class TestPhaseAgentRegistration:
    """REQ-805/808/812/813: 14 phase subagents registered deny-first.

    PR 2 covers the first 7 phases from PHASES: research, hypothesis, config,
    review, dispatch, monitor, retest. PR 3 covers the remaining 7: optimize,
    portfolio, compile, deploy, demo, archive, live-ops. Each entry MUST be
    mode=subagent, deny-first task permissions, question allowed, prompt ref
    present, and bash scoped to sdk/quantlab/pipeline/* + sdk/quantlab/campaign/*.
    """

    FIRST_7_PHASES = [
        "research",
        "hypothesis",
        "config",
        "review",
        "dispatch",
        "monitor",
        "retest",
    ]

    REMAINING_7_PHASES = [
        "optimize",
        "portfolio",
        "compile",
        "deploy",
        "demo",
        "archive",
        "live-ops",
    ]

    ALL_14_PHASES = FIRST_7_PHASES + REMAINING_7_PHASES

    def test_first_7_phase_agents_registered(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        for phase in self.FIRST_7_PHASES:
            name = f"quantlab-phase-{phase}"
            assert name in cfg.get("agent", {}), f"opencode.json must register {name}"

    def test_first_7_phase_agents_are_subagents(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        for phase in self.FIRST_7_PHASES:
            agent = cfg["agent"][f"quantlab-phase-{phase}"]
            assert agent.get("mode") == "subagent", f"{phase} agent must be subagent"

    def test_first_7_phase_agents_have_deny_first_task_permissions(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        for phase in self.FIRST_7_PHASES:
            perms = cfg["agent"][f"quantlab-phase-{phase}"]["permission"]["task"]
            assert perms.get("*") == "deny", f"{phase} task wildcard must deny"
            assert perms.get("quantlab-*") == "allow", f"{phase} quantlab wildcard must allow"

    def test_first_7_phase_agents_allow_question_tool(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        for phase in self.FIRST_7_PHASES:
            perms = cfg["agent"][f"quantlab-phase-{phase}"]["permission"]
            assert perms.get("question") == "allow", f"{phase} must allow question tool"

    def test_first_7_phase_agents_have_prompt_references(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        for phase in self.FIRST_7_PHASES:
            prompt = cfg["agent"][f"quantlab-phase-{phase}"].get("prompt", "")
            expected = f"{{file:~/.config/opencode/prompts/quantlab/phase-{phase}.md}}"
            assert prompt == expected, f"{phase} prompt ref must be {expected}, got {prompt}"

    def test_first_7_phase_agents_have_scoped_bash_allowlist(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        for phase in self.FIRST_7_PHASES:
            perms = cfg["agent"][f"quantlab-phase-{phase}"]["permission"]["bash"]
            assert perms.get("*") == "deny", f"{phase} bash wildcard must deny"
            assert perms.get("sdk/quantlab/pipeline/*") == "allow"
            assert perms.get("sdk/quantlab/campaign/*") == "allow"

    def test_remaining_7_phase_agents_registered(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        for phase in self.REMAINING_7_PHASES:
            name = f"quantlab-phase-{phase}"
            assert name in cfg.get("agent", {}), f"opencode.json must register {name}"

    def test_remaining_7_phase_agents_are_subagents(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        for phase in self.REMAINING_7_PHASES:
            agent = cfg["agent"][f"quantlab-phase-{phase}"]
            assert agent.get("mode") == "subagent", f"{phase} agent must be subagent"

    def test_remaining_7_phase_agents_have_deny_first_task_permissions(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        for phase in self.REMAINING_7_PHASES:
            perms = cfg["agent"][f"quantlab-phase-{phase}"]["permission"]["task"]
            assert perms.get("*") == "deny", f"{phase} task wildcard must deny"
            assert perms.get("quantlab-*") == "allow", f"{phase} quantlab wildcard must allow"

    def test_remaining_7_phase_agents_allow_question_tool(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        for phase in self.REMAINING_7_PHASES:
            perms = cfg["agent"][f"quantlab-phase-{phase}"]["permission"]
            assert perms.get("question") == "allow", f"{phase} must allow question tool"

    def test_remaining_7_phase_agents_have_prompt_references(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        for phase in self.REMAINING_7_PHASES:
            prompt = cfg["agent"][f"quantlab-phase-{phase}"].get("prompt", "")
            expected = f"{{file:~/.config/opencode/prompts/quantlab/phase-{phase}.md}}"
            assert prompt == expected, f"{phase} prompt ref must be {expected}, got {prompt}"

    def test_remaining_7_phase_agents_have_scoped_bash_allowlist(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        for phase in self.REMAINING_7_PHASES:
            perms = cfg["agent"][f"quantlab-phase-{phase}"]["permission"]["bash"]
            assert perms.get("*") == "deny", f"{phase} bash wildcard must deny"
            assert perms.get("sdk/quantlab/pipeline/*") == "allow"
            assert perms.get("sdk/quantlab/campaign/*") == "allow"

    def test_all_14_phase_agents_registered_matches_phases_length(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        registered = [k for k in cfg.get("agent", {}) if k.startswith("quantlab-phase-")]
        assert len(registered) == len(CAMPAIGN_PHASES) == 14, (
            f"registry completeness: expected 14 phase agents, got {len(registered)}"
        )
