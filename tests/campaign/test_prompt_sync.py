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
SYNC_COMMON_SCRIPT = REPO_ROOT / "ai" / "opencode" / "sync_common.py"


def _load_sync_module():
    spec = importlib.util.spec_from_file_location("sync_prompts", SYNC_SCRIPT)
    assert spec is not None and spec.loader is not None, "sync_prompts.py must load"
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_prompts"] = module
    spec.loader.exec_module(module)
    return module


def _load_sync_common_module():
    spec = importlib.util.spec_from_file_location("sync_common", SYNC_COMMON_SCRIPT)
    assert spec is not None and spec.loader is not None, "sync_common.py must load"
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_common"] = module
    spec.loader.exec_module(module)
    return module


sync_mod = _load_sync_module()


class TestSyncDriver:
    """REQ-806 design: SyncDriver is the shared deterministic idempotent helper."""

    def test_sync_driver_importable(self) -> None:
        """RED: SyncDriver must exist in sync_common before use."""
        common = _load_sync_common_module()
        assert hasattr(common, "SyncDriver"), "sync_common.py must define SyncDriver"

    def test_sync_driver_copies_managed_and_skips_identical(self, tmp_path: Path) -> None:
        common = _load_sync_common_module()
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "campaign.md").write_text("# Campaign\n", encoding="utf-8")
        live = tmp_path / "live"
        live.mkdir()
        driver = common.SyncDriver(
            repo, live, managed_names=lambda r: ["campaign.md"], retired_names=()
        )
        first = driver.sync()
        assert first == ["campaign.md"]
        assert (live / "campaign.md").read_bytes() == b"# Campaign\n"
        second = driver.sync()
        assert second == []  # idempotent

    def test_sync_driver_check_reports_drift(self, tmp_path: Path) -> None:
        common = _load_sync_common_module()
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "campaign.md").write_text("# Campaign\n", encoding="utf-8")
        live = tmp_path / "live"
        live.mkdir()
        (live / "campaign.md").write_text("# Stale\n", encoding="utf-8")
        driver = common.SyncDriver(
            repo, live, managed_names=lambda r: ["campaign.md"], retired_names=()
        )
        assert driver.check() == ["campaign.md"]

    def test_sync_driver_cleanup_retired_removes_stale_live_copies(
        self, tmp_path: Path
    ) -> None:
        common = _load_sync_common_module()
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "campaign.md").write_text("# Campaign\n", encoding="utf-8")
        live = tmp_path / "live"
        live.mkdir()
        (live / "deploy.md").write_text("# Deploy\n", encoding="utf-8")
        (live / "monitor.md").write_text("# Monitor\n", encoding="utf-8")
        driver = common.SyncDriver(
            repo, live, managed_names=lambda r: ["campaign.md"], retired_names=("deploy.md", "monitor.md")
        )
        driver.sync()
        assert (live / "deploy.md").exists() is False
        assert (live / "monitor.md").exists() is False
        assert (live / "campaign.md").exists() is True

    def test_sync_driver_dry_run_reports_retired_but_does_not_delete(
        self, tmp_path: Path
    ) -> None:
        common = _load_sync_common_module()
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "campaign.md").write_text("# Campaign\n", encoding="utf-8")
        live = tmp_path / "live"
        live.mkdir()
        (live / "deploy.md").write_text("# Deploy\n", encoding="utf-8")
        driver = common.SyncDriver(
            repo, live, managed_names=lambda r: ["campaign.md"], retired_names=("deploy.md",)
        )
        changed = driver.sync(dry_run=True)
        assert "deploy.md" in changed
        assert (live / "deploy.md").exists() is True  # not deleted in dry-run


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
        sentinel = "NOTES SENTINEL — must never be overwritten"
        (live / "notes.md").write_text(sentinel, encoding="utf-8")
        sync_mod.sync(repo, live)
        assert (live / "notes.md").read_text(encoding="utf-8") == sentinel

    def test_orchestrator_managed_when_in_repo(self, tmp_path: Path) -> None:
        """REQ-821: orchestrator.md is now managed and must sync to live."""
        repo = _make_repo(tmp_path)
        (repo / "orchestrator.md").write_text(
            "# Orchestrator\n", encoding="utf-8"
        )
        live = tmp_path / "live"
        sync_mod.sync(repo, live)
        assert (live / "orchestrator.md").exists()
        assert (live / "orchestrator.md").read_bytes() == (repo / "orchestrator.md").read_bytes()

    def test_guardian_live_prompt_never_synced(self, tmp_path: Path) -> None:
        """REQ-821 contract: guardian-orchestrator.md IS managed.

        The allowlist extends to the guardian-orchestrator prompt (REQ-806)
        while ``guardian.md`` stays non-managed: never written, never deleted.
        ``orchestrator.md`` IS managed and must propagate byte-for-byte.
        """
        repo = _make_repo(tmp_path)
        (repo / "guardian-orchestrator.md").write_text(
            "# Guardian Orchestrator\n", encoding="utf-8"
        )
        (repo / "orchestrator.md").write_text(
            "# Orchestrator\n", encoding="utf-8"
        )
        live = tmp_path / "live"
        live.mkdir()
        guardian = "GUARDIAN — belongs to quantlab-guardian, not the allowlist"
        (live / "guardian.md").write_text(guardian, encoding="utf-8")
        sync_mod.sync(repo, live)
        # guardian-orchestrator.md propagates byte-for-byte (REQ-806).
        assert (live / "guardian-orchestrator.md").read_bytes() == (
            repo / "guardian-orchestrator.md"
        ).read_bytes()
        # orchestrator.md propagates byte-for-byte (REQ-821).
        assert (live / "orchestrator.md").read_bytes() == (
            repo / "orchestrator.md"
        ).read_bytes()
        # guardian.md remains untouched (REQ-821).
        assert (live / "guardian.md").read_text(encoding="utf-8") == guardian


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
        # Allowlist is campaign.md + phase-*.md + guardian-orchestrator.md + orchestrator.md.
        assert all(
            name == "campaign.md"
            or name.startswith("phase-")
            or name == "guardian-orchestrator.md"
            or name == "orchestrator.md"
            for name in managed
        )

    def test_retired_prompts_removed_from_live(self, tmp_path: Path) -> None:
        """REQ-806: deploy.md and monitor.md are retired from live after sync."""
        repo = _make_repo(tmp_path)
        live = tmp_path / "live"
        live.mkdir()
        (live / "deploy.md").write_text("# Deploy\n", encoding="utf-8")
        (live / "monitor.md").write_text("# Monitor\n", encoding="utf-8")
        changed = sync_mod.sync(repo, live)
        assert "deploy.md" in changed
        assert "monitor.md" in changed
        assert (live / "deploy.md").exists() is False
        assert (live / "monitor.md").exists() is False
