"""REQ-903: uniform model policy for all QuantLab agents.

The repo ``opencode.json`` MUST declare ``model:
"opencode/deepseek-v4-flash-free"`` on every QuantLab agent block.
Split model assignments are rejected. ``default_agent`` MUST remain
``"quantlab-orchestrator"``.

These tests assert the repo config, not the live global config. OpenCode
merges repo partial agent blocks over the global config, so the repo
``opencode.json`` carries only the ``model`` override for each agent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_OPENCODE_JSON = REPO_ROOT / "opencode.json"

EXPECTED_MODEL = "opencode/deepseek-v4-flash-free"
EXPECTED_DEFAULT_AGENT = "quantlab-orchestrator"

QUANTLAB_AGENTS = [
    "quantlab-campaign",
    "quantlab-guardian",
    "quantlab-guardian-alert",
    "quantlab-orchestrator",
    "quantlab-phase-archive",
    "quantlab-phase-compile",
    "quantlab-phase-config",
    "quantlab-phase-demo",
    "quantlab-phase-deploy",
    "quantlab-phase-dispatch",
    "quantlab-phase-hypothesis",
    "quantlab-phase-live-ops",
    "quantlab-phase-monitor",
    "quantlab-phase-optimize",
    "quantlab-phase-portfolio",
    "quantlab-phase-research",
    "quantlab-phase-retest",
    "quantlab-phase-review",
    "quantlab-replacement",
]


def _load_repo_config() -> dict:
    assert REPO_OPENCODE_JSON.exists(), f"expected repo opencode.json at {REPO_OPENCODE_JSON}"
    return json.loads(REPO_OPENCODE_JSON.read_text(encoding="utf-8"))


class TestUniformModelPolicy:
    """REQ-903: all 19 QuantLab agents share one model in repo opencode.json."""

    def test_all_quantlab_agents_declare_uniform_model(self) -> None:
        cfg = _load_repo_config()
        agents = cfg.get("agent", {})
        for name in QUANTLAB_AGENTS:
            agent_block = agents.get(name)
            assert agent_block is not None, f"repo opencode.json must define agent block for {name}"
            assert agent_block.get("model") == EXPECTED_MODEL, (
                f"{name} model must be {EXPECTED_MODEL}, got {agent_block.get('model')!r}"
            )

    def test_default_agent_remains_intact(self) -> None:
        cfg = _load_repo_config()
        assert cfg.get("default_agent") == EXPECTED_DEFAULT_AGENT, (
            f"default_agent must remain {EXPECTED_DEFAULT_AGENT}, got {cfg.get('default_agent')!r}"
        )

    def test_no_split_model_assignments(self) -> None:
        cfg = _load_repo_config()
        agents = cfg.get("agent", {})
        quantlab_blocks = {k: v for k, v in agents.items() if k in QUANTLAB_AGENTS}
        models = {v.get("model") for v in quantlab_blocks.values() if "model" in v}
        assert models == {EXPECTED_MODEL}, (
            f"split model assignments rejected: found models {models}"
        )
