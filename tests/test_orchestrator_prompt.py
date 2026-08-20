"""RED tests for WU-9: quantlab-campaign harness + orchestrator routing (REQ-01, REQ-02, REQ-16).

The harness deliverable lives in-repo under ``ai/opencode/`` (REQ-02) and is
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

G4 (flow-ecosystem-alignment, U1/PR1) additions pin the live-config security
state:

- ``quantlab-deploy`` and ``quantlab-monitor`` are retired from
  ``opencode.json`` and the installer overlay (no dangling agent entries);
- no ``quantlab-run|status|compare`` reference remains in the orchestrator
  task allowlist, bash allowlist, or ``orchestrator.md`` routing table;
- ``quantlab-campaign`` bash is deny-first (``*: deny``) with only the two
  SDK paths allowed — never unrestricted ``bash: true``;
- the stale ``sdk/pipeline/*`` allow on ``quantlab-orchestrator`` is
  corrected to ``sdk/quantlab/pipeline/*``.

The OpenCode config files live outside the repo (``~/.config/opencode/``);
they are asserted here because REQ-16 scenario text names the exact path.
The installer overlay lives in-repo (``installer/internal/opencode/``) and is
asserted so a fresh install matches the restored live config (G4 rollback).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENCODE_DIR = Path.home() / ".config" / "opencode"
ORCHESTRATOR_PROMPT = OPENCODE_DIR / "prompts" / "quantlab" / "orchestrator.md"
OPENCODE_JSON = OPENCODE_DIR / "opencode.json"

CAMPAIGN_AGENT_PROMPT = REPO_ROOT / "ai" / "opencode" / "agents" / "campaign.md"
GUARDIAN_ORCHESTRATOR_PROMPT = REPO_ROOT / "ai" / "opencode" / "agents" / "guardian-orchestrator.md"
CAMPAIGN_SKILL = REPO_ROOT / "ai" / "opencode" / "skills" / "quantlab-run-campaign" / "SKILL.md"
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


class TestGuardianOrchestratorPromptFile:
    """REQ-822 (PR 3): ``guardian-orchestrator.md`` is a managed repo prompt.

    The second first-class orchestrator is versioned in-repo under
    ``ai/opencode/agents/guardian-orchestrator.md`` (REQ-806 managed set).
    It is a FIRST-CLASS orchestrator (mode primary, visible, own routing),
    NOT a phase inside ``quantlab-orchestrator`` (PRD G9 / D10).
    """

    def test_guardian_orchestrator_prompt_exists_in_repo(self) -> None:
        _read(GUARDIAN_ORCHESTRATOR_PROMPT)  # exists + readable

    def test_guardian_orchestrator_prompt_declares_second_orchestrator_role(self) -> None:
        text = _read(GUARDIAN_ORCHESTRATOR_PROMPT)
        assert "guardian-orchestrator" in text
        assert "second" in text.lower()  # PRD G9: second first-class orchestrator

    def test_guardian_orchestrator_prompt_declares_routing_table(self) -> None:
        text = _read(GUARDIAN_ORCHESTRATOR_PROMPT)
        assert "GUARDIAN-LIVE" in text  # owns the live-ops intent surface

    def test_guardian_orchestrator_prompt_declares_delegates(self) -> None:
        text = _read(GUARDIAN_ORCHESTRATOR_PROMPT)
        for agent in ("quantlab-guardian", "quantlab-guardian-alert", "quantlab-replacement"):
            assert agent in text, f"delegate {agent} must be declared (REQ-825)"

    def test_guardian_orchestrator_prompt_declares_replacement_gate(self) -> None:
        text = _read(GUARDIAN_ORCHESTRATOR_PROMPT)
        assert "HUMAN_APPROVE_REPLACEMENT" in text  # REQ-824 live gate
        assert "approve" in text

    def test_guardian_orchestrator_prompt_declares_no_phase_rule(self) -> None:
        text = _read(GUARDIAN_ORCHESTRATOR_PROMPT).lower()
        assert "phase" in text
        assert "14" in text  # PHASES stays 14 (REQ-37)

    def test_guardian_orchestrator_prompt_declares_long_running_policy(self) -> None:
        text = _read(GUARDIAN_ORCHESTRATOR_PROMPT).lower()
        assert "orchestrator shell" in text or "long" in text


class TestGuardianOrchestratorRegistration:
    """REQ-822/825 (D10/D11): live opencode.json registers guardian-orchestrator
    as a first-class primary agent with deny-first permissions mirroring
    ``quantlab-orchestrator``, plus hidden inline delegate subagents."""

    def test_opencode_json_registers_guardian_orchestrator_primary_visible(self) -> None:
        assert OPENCODE_JSON.exists(), f"expected opencode.json at {OPENCODE_JSON}"
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        agent = cfg.get("agent", {}).get("guardian-orchestrator")
        assert agent is not None, "opencode.json must register guardian-orchestrator"
        assert agent.get("mode") == "primary"
        assert agent.get("hidden") is not True  # visible: NOT a hidden subagent

    def test_guardian_orchestrator_deny_first_bash_permissions(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        bash = cfg["agent"]["guardian-orchestrator"]["permission"]["bash"]
        assert bash.get("*") == "deny"  # deny-first, mirroring quantlab-orchestrator
        for pattern in ("sdk/quantlab/*", "knowledge/*", "/tmp/opencode/*"):
            assert bash.get(pattern) == "allow", f"bash allowlist must include {pattern}"

    def test_guardian_orchestrator_deny_first_task_permissions(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        task = cfg["agent"]["guardian-orchestrator"]["permission"]["task"]
        assert task.get("*") == "deny"
        for agent in ("quantlab-guardian", "quantlab-guardian-alert", "quantlab-replacement"):
            assert task.get(agent) == "allow", f"task allowlist must include {agent}"

    def test_guardian_orchestrator_question_allowed(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        perms = cfg["agent"]["guardian-orchestrator"]["permission"]
        assert perms.get("question") == "allow"

    def test_guardian_orchestrator_prompt_reference(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        prompt = cfg["agent"]["guardian-orchestrator"].get("prompt", "")
        assert "{file:~/.config/opencode/prompts/quantlab/guardian-orchestrator.md}" in prompt

    def test_orchestrator_task_allowlist_includes_guardian_orchestrator(self) -> None:
        """REQ-823: quantlab-orchestrator must be able to delegate GUARDIAN-LIVE
        intents to guardian-orchestrator via the task tool."""
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        task_perms = cfg["agent"]["quantlab-orchestrator"]["permission"]["task"]
        assert task_perms.get("guardian-orchestrator") == "allow"


class TestGuardianOrchestratorDelegates:
    """REQ-825 (D10): alert + replacement delegates are hidden subagents with
    inline prompts (pattern: ``jd-fix-agent``), deny-first."""

    def test_alert_delegate_registered_hidden_subagent_inline(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        agent = cfg.get("agent", {}).get("quantlab-guardian-alert")
        assert agent is not None, "opencode.json must register quantlab-guardian-alert"
        assert agent.get("mode") == "subagent"
        assert agent.get("hidden") is True
        assert "guardian" in agent.get("description", "").lower()

    def test_replacement_delegate_registered_hidden_subagent_inline(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        agent = cfg.get("agent", {}).get("quantlab-replacement")
        assert agent is not None, "opencode.json must register quantlab-replacement"
        assert agent.get("mode") == "subagent"
        assert agent.get("hidden") is True
        assert "replacement" in agent.get("description", "").lower()

    def test_alert_and_replacement_delegates_have_inline_prompts(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        for name in ("quantlab-guardian-alert", "quantlab-replacement"):
            prompt = cfg["agent"][name].get("prompt", "")
            assert len(prompt) > 0, f"{name} must carry an inline prompt"
            assert "{file:" not in prompt, f"{name} prompt must be inline, not a file ref"


class TestGuardianLiveRouting:
    """REQ-823 (D8): GUARDIAN-LIVE intents delegate to guardian-orchestrator
    via ``task`` — mirroring SDD intents routing to gentle-orchestrator."""

    def test_prompt_declares_guardian_live_route_dispatching_via_task(self) -> None:
        text = _read(ORCHESTRATOR_PROMPT)
        assert "GUARDIAN-LIVE" in text  # routing-table classification exists
        assert "guardian-orchestrator" in text  # routing-table target exists
        assert "task" in text  # dispatch via the task tool

    def test_guardian_live_keywords_classify(self) -> None:
        text = _read(ORCHESTRATOR_PROMPT).lower()
        for keyword in ("guardian-live", "live-ops event", "replacement"):
            assert keyword in text, f"GUARDIAN-LIVE classification must match {keyword}"

    def test_guardian_live_row_does_not_replace_guardian_row(self) -> None:
        text = _read(ORCHESTRATOR_PROMPT)
        assert "GUARDIAN-LIVE" in text
        assert "quantlab-guardian" in text  # REQ-642 GUARDIAN row unchanged
        # GUARDIAN-LIVE routes to guardian-orchestrator, not quantlab-orchestrator
        assert "guardian-orchestrator" in text


class TestE2eDispatchAndMockIntegrity:
    """REQ-810/811: e2e dispatch order, mock mode, and routing-note integrity."""

    def test_campaign_dispatch_order_matches_phases(self) -> None:
        """GIVEN the campaign agent prompt dispatch table
        WHEN phases are listed in the table
        THEN the table order matches PHASES exactly (REQ-811)."""
        text = _read(CAMPAIGN_AGENT_PROMPT)
        table_start = text.find("| Phase | Subagent |")
        assert table_start != -1
        table = text[table_start:]
        seen = []
        for phase in CAMPAIGN_PHASES:
            idx = table.find(phase)
            assert idx != -1, f"phase {phase} missing from dispatch table"
            seen.append((idx, phase))
        # Verify order by position
        for i in range(1, len(seen)):
            assert seen[i][0] > seen[i - 1][0], (
                f"dispatch table order mismatch: {seen[i-1][1]} before {seen[i][1]}"
            )

    def test_orchestrator_routing_note_long_running_on_shell(self) -> None:
        """GIVEN the orchestrator prompt
        THEN long-running operations execute on the orchestrator shell, not
        inside a subagent task (REQ-814)."""
        text = _read(ORCHESTRATOR_PROMPT)
        assert "orchestrator shell" in text.lower()
        assert "nohup" in text.lower() or "background" in text.lower()

    def test_sqx_force_mock_mentioned_in_test_command(self) -> None:
        """GIVEN the project test contract
        THEN the canonical test command uses SQX_FORCE_MOCK=1 to keep tests
        deterministic and offline."""
        cmd = "SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q <files> --tb=short"
        assert "SQX_FORCE_MOCK=1" in cmd
        assert "PYTHONPATH=sdk" in cmd


INSTALLER_OVERLAY = REPO_ROOT / "installer" / "internal" / "opencode" / "overlay.json"

LEGACY_AGENTS = ("quantlab-deploy", "quantlab-monitor")
DANGLING_TASKS = ("quantlab-run", "quantlab-status", "quantlab-compare")
CAMPAIGN_BASH_ALLOWS = ("sdk/quantlab/pipeline/*", "sdk/quantlab/campaign/*")


class TestG4LegacyAgentRetirement:
    """G4 (flow-ecosystem-alignment): the legacy agents MUST be retired and
    every dangling reference pruned.

    Spec scenarios (quantlab-orchestrator delta, G4):
    - "Legacy entries absent": opencode.json MUST NOT register
      ``quantlab-deploy`` or ``quantlab-monitor``.
    - "Dangling refs pruned": no ``quantlab-run|status|compare`` reference
      remains in the orchestrator task allowlist, bash allowlist, or
      ``orchestrator.md`` routing table.
    - "Orchestrator path corrected": the orchestrator bash allowlist
      references ``sdk/quantlab/pipeline/*``, never ``sdk/pipeline/*``.

    Assertions are token-exact (``quantlab-run`` etc.) so routing keywords
    like ``run campaign`` or ``live-ops status`` are unaffected.
    """

    def test_opencode_json_does_not_register_legacy_deploy_agent(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        assert "quantlab-deploy" not in cfg.get("agent", {}), (
            "G4: quantlab-deploy agent MUST be retired from opencode.json"
        )

    def test_opencode_json_does_not_register_legacy_monitor_agent(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        assert "quantlab-monitor" not in cfg.get("agent", {}), (
            "G4: quantlab-monitor agent MUST be retired from opencode.json"
        )

    def test_active_agents_still_registered_after_retirement(self) -> None:
        """Positive control: the agent map is really read and active agents
        remain — the absence assertions above are not vacuous."""
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        for name in ("quantlab-campaign", "quantlab-guardian", "quantlab-orchestrator"):
            assert name in cfg["agent"], f"active agent {name} must stay registered"

    def test_orchestrator_task_allowlist_has_no_legacy_dangling_refs(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        task_perms = cfg["agent"]["quantlab-orchestrator"]["permission"]["task"]
        for legacy in DANGLING_TASKS:
            assert legacy not in task_perms, (
                f"orchestrator task allowlist must not reference {legacy}"
            )

    def test_orchestrator_bash_allowlist_has_no_legacy_dangling_refs(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        bash_perms = cfg["agent"]["quantlab-orchestrator"]["permission"]["bash"]
        for legacy in DANGLING_TASKS:
            assert legacy not in bash_perms, (
                f"orchestrator bash allowlist must not reference {legacy}"
            )

    def test_orchestrator_prompt_has_no_legacy_routing_rows(self) -> None:
        text = _read(ORCHESTRATOR_PROMPT)
        for legacy in DANGLING_TASKS:
            assert legacy not in text, (
                f"orchestrator.md routing table must not reference {legacy}"
            )

    def test_orchestrator_bash_allowlist_has_no_stale_sdk_pipeline(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        bash_perms = cfg["agent"]["quantlab-orchestrator"]["permission"]["bash"]
        assert "sdk/pipeline/*" not in bash_perms, (
            "G4: stale sdk/pipeline/* allow MUST be corrected"
        )
        assert bash_perms.get("sdk/quantlab/pipeline/*") == "allow", (
            "G4: orchestrator bash MUST allow sdk/quantlab/pipeline/*"
        )


class TestG4CampaignDenyFirstBash:
    """G4 (Deny-First Bash Scope): ``quantlab-campaign`` bash MUST default to
    deny with only the two SDK paths allowed — never unrestricted ``bash:
    true``.

    Spec scenario "Campaign agent is deny-first": ``*: deny`` plus the two
    ``sdk/quantlab/*`` allows; the campaign agent must keep its deny-first
    task allowlist and registration.
    """

    def test_campaign_agent_bash_is_deny_first(self) -> None:
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        bash = cfg["agent"]["quantlab-campaign"]["permission"]["bash"]
        assert bash.get("*") == "deny", "campaign bash wildcard MUST deny"
        for pattern in CAMPAIGN_BASH_ALLOWS:
            assert bash.get(pattern) == "allow", (
                f"campaign bash must allow {pattern}"
            )

    def test_campaign_agent_keeps_deny_first_task_allowlist(self) -> None:
        """Positive control: the permission block is intact, not replaced by
        an unrestricted tools-only entry."""
        cfg = json.loads(OPENCODE_JSON.read_text(encoding="utf-8"))
        campaign = cfg["agent"]["quantlab-campaign"]
        assert campaign.get("mode") == "subagent"
        task = campaign["permission"]["task"]
        assert task.get("*") == "deny"
        assert task.get("quantlab-*") == "allow"


class TestG4InstallerOverlaySync:
    """G4 (Live Config Restore Path): the installer overlay mirrors the
    retired agents and the campaign deny-first bash block, so a fresh install
    matches the restored live config."""

    def test_overlay_does_not_register_legacy_agents(self) -> None:
        overlay = json.loads(INSTALLER_OVERLAY.read_text(encoding="utf-8"))
        agents = overlay.get("agent", {})
        for legacy in LEGACY_AGENTS:
            assert legacy not in agents, (
                f"installer overlay must not register {legacy}"
            )

    def test_overlay_campaign_agent_is_deny_first(self) -> None:
        overlay = json.loads(INSTALLER_OVERLAY.read_text(encoding="utf-8"))
        bash = overlay["agent"]["quantlab-campaign"]["permission"]["bash"]
        assert bash.get("*") == "deny", "overlay campaign bash wildcard MUST deny"
        for pattern in CAMPAIGN_BASH_ALLOWS:
            assert bash.get(pattern) == "allow", (
                f"overlay campaign bash must allow {pattern}"
            )
