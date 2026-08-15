"""REQ-806/807/810: prompt sync idempotency, parity, and allowlist classification.

The repo directory ``ai/opencode/agents/`` is the single source of truth for
the campaign prompt and all phase prompts (REQ-806). The live copies under
``~/.config/opencode/prompts/quantlab/`` are generated from it by
``ai/opencode/sync_prompts.py``; hand-editing live prompts is not permitted.

These tests assert:

- the sync script is deterministic and idempotent: a second run is a no-op;
- managed prompts (``campaign.md`` + ``phase-*.md`` +
  ``guardian-orchestrator.md``) propagate byte-exact to the live dir, and
  parity holds after sync (REQ-807 "Parity holds");
- non-managed live files (``guardian.md``, ``orchestrator.md``, ...) are
  NEVER written or deleted — the allowlist is the classification boundary
  (threat matrix "Documentation-like paths"); ``guardian-orchestrator.md``
  is managed (REQ-821) while ``guardian.md`` / ``orchestrator.md`` stay
  non-managed;
- drift names the drifted file (REQ-807 "Drift detected"): ``check()``
  reports the file, sync restores parity (RED on drift -> sync -> green);
- the real repo-canonical ``campaign.md`` matches the real live copy
  byte-for-byte (the "Live prompt never hand-edited" contract).

The real-live parity test reads ``~/.config/opencode/prompts/quantlab/``;
idempotency/allowlist tests run against temporary dirs so they never mutate
the live OpenCode config.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SYNC_SCRIPT = REPO_ROOT / "ai" / "opencode" / "sync_prompts.py"
REPO_AGENTS = REPO_ROOT / "ai" / "opencode" / "agents"
LIVE_PROMPTS = Path.home() / ".config" / "opencode" / "prompts" / "quantlab"


def _load_sync_module():
    spec = importlib.util.spec_from_file_location("sync_prompts", SYNC_SCRIPT)
    assert spec is not None and spec.loader is not None, "sync_prompts.py must load"
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_prompts"] = module
    spec.loader.exec_module(module)
    return module


sync_mod = _load_sync_module()


def _make_repo(tmp_path: Path, *phase_files: str) -> Path:
    """Seed a temp repo agents dir: campaign.md (canonical) + optional phase files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "campaign.md").write_text("# QuantLab Campaign\n", encoding="utf-8")
    for name in phase_files:
        (repo / name).write_text(f"# {name}\n", encoding="utf-8")
    return repo


class TestSyncIdempotency:
    """REQ-806: identical bytes -> no-op; a second sync changes nothing."""

    def test_second_sync_is_noop(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path, "phase-research.md")
        live = tmp_path / "live"
        first = sync_mod.sync(repo, live)
        assert sorted(first) == ["campaign.md", "phase-research.md"]
        second = sync_mod.sync(repo, live)
        assert second == []  # idempotent: nothing to rewrite

    def test_unchanged_files_never_rewritten(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        live = tmp_path / "live"
        sync_mod.sync(repo, live)
        mtime = (live / "campaign.md").stat().st_mtime_ns
        sync_mod.sync(repo, live)  # no-op
        assert (live / "campaign.md").stat().st_mtime_ns == mtime


class TestAllowlistClassification:
    """Threat matrix: the allowlist is the sync classification boundary."""

    def test_sync_copies_campaign_and_phase_files_only(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path, "phase-research.md", "phase-archive.md")
        (repo / "guardian-orchestrator.md").write_text(
            "# Guardian Orchestrator\n", encoding="utf-8"
        )
        # A non-managed file in the repo dir must NOT be treated as managed.
        (repo / "notes.md").write_text("not a prompt\n", encoding="utf-8")
        live = tmp_path / "live"
        sync_mod.sync(repo, live)
        assert sorted(p.name for p in live.iterdir()) == [
            "campaign.md",
            "guardian-orchestrator.md",
            "phase-archive.md",
            "phase-research.md",
        ]
        assert (live / "notes.md").exists() is False

    def test_guardian_orchestrator_allowlisted(self, tmp_path: Path) -> None:
        """REQ-821: the allowlist includes the guardian-orchestrator prompt."""
        repo = _make_repo(tmp_path)
        (repo / "guardian-orchestrator.md").write_text(
            "# Guardian Orchestrator\n", encoding="utf-8"
        )
        names = sync_mod.managed_prompt_names(repo)
        assert "guardian-orchestrator.md" in names
        assert "campaign.md" in names

    def test_non_managed_live_file_untouched(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path)
        live = tmp_path / "live"
        live.mkdir()
        sentinel = "ORCHESTRATOR SENTINEL — must never be overwritten"
        (live / "orchestrator.md").write_text(sentinel, encoding="utf-8")
        sync_mod.sync(repo, live)
        assert (live / "orchestrator.md").read_text(encoding="utf-8") == sentinel

    def test_guardian_live_prompt_never_synced(self, tmp_path: Path) -> None:
        """REQ-821 contract: guardian-orchestrator.md IS managed.

        The allowlist extends to the guardian-orchestrator prompt (REQ-806)
        while ``guardian.md`` and ``orchestrator.md`` stay non-managed:
        never written, never deleted.
        """
        repo = _make_repo(tmp_path)
        (repo / "guardian-orchestrator.md").write_text(
            "# Guardian Orchestrator\n", encoding="utf-8"
        )
        live = tmp_path / "live"
        live.mkdir()
        guardian = "GUARDIAN — belongs to quantlab-guardian, not the allowlist"
        orchestrator = "ORCHESTRATOR — hand-edited live routing table"
        (live / "guardian.md").write_text(guardian, encoding="utf-8")
        (live / "orchestrator.md").write_text(orchestrator, encoding="utf-8")
        sync_mod.sync(repo, live)
        # guardian-orchestrator.md propagates byte-for-byte (REQ-806).
        assert (live / "guardian-orchestrator.md").read_bytes() == (
            repo / "guardian-orchestrator.md"
        ).read_bytes()
        # guardian.md / orchestrator.md remain untouched (REQ-821).
        assert (live / "guardian.md").read_text(encoding="utf-8") == guardian
        assert (live / "orchestrator.md").read_text(encoding="utf-8") == orchestrator


class TestDriftDetection:
    """REQ-807 "Drift detected": check() names the drifted file; sync -> green."""

    def test_drift_names_file_then_sync_restores_parity(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path, "phase-research.md")
        live = tmp_path / "live"
        sync_mod.sync(repo, live)
        # Introduce drift in a managed live copy.
        (live / "campaign.md").write_text("# STALE DRIFTED COPY\n", encoding="utf-8")
        drifted = sync_mod.check(repo, live)
        assert drifted == ["campaign.md"]  # RED: names the drifted file
        # sync -> green: byte parity restored.
        sync_mod.sync(repo, live)
        assert sync_mod.check(repo, live) == []
        assert (live / "campaign.md").read_bytes() == (repo / "campaign.md").read_bytes()

    def test_missing_live_copy_is_drift(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path, "phase-research.md")
        live = tmp_path / "live"
        live.mkdir()
        assert sorted(sync_mod.check(repo, live)) == ["campaign.md", "phase-research.md"]


class TestLiveParity:
    """REQ-807 "Parity holds": repo-canonical prompts match live byte-for-byte.

    This is the "Live prompt never hand-edited" contract: a mismatch is a sync
    miss, not a manual edit — run ``python3 ai/opencode/sync_prompts.py``.
    """

    def test_managed_allowlist_defined(self) -> None:
        names = sync_mod.managed_prompt_names(REPO_AGENTS)
        assert "campaign.md" in names
        assert all(name.endswith(".md") for name in names)

    def test_repo_campaign_matches_live_campaign(self) -> None:
        assert LIVE_PROMPTS.exists(), f"live prompts dir missing: {LIVE_PROMPTS}"
        assert sync_mod.check(REPO_AGENTS, LIVE_PROMPTS) == []

    def test_every_managed_repo_prompt_has_byte_equal_live_copy(self) -> None:
        for name in sync_mod.managed_prompt_names(REPO_AGENTS):
            repo_file = REPO_AGENTS / name
            live_file = LIVE_PROMPTS / name
            assert live_file.is_file(), f"managed prompt missing live copy: {name}"
            assert live_file.read_bytes() == repo_file.read_bytes(), (
                f"parity drift in {name} — run ai/opencode/sync_prompts.py"
            )

    def test_non_managed_live_prompts_outside_allowlist(self) -> None:
        """Existing live prompts not in the allowlist are never managed."""
        managed = set(sync_mod.managed_prompt_names(REPO_AGENTS))
        # Allowlist is exactly campaign.md + phase-*.md + guardian-orchestrator.md.
        assert all(
            name == "campaign.md"
            or name.startswith("phase-")
            or name == "guardian-orchestrator.md"
            for name in managed
        )
